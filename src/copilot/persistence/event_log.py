"""Append-only SQLite event log (docs/architecture/persistence.md).

Events are buffered and written in batches from a worker thread so the event loop never blocks on disk.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
import time
from pathlib import Path
from typing import Iterator, Optional

from copilot.core.bus import EventBus
from copilot.core.events import Event, decode_event

log = logging.getLogger(__name__)

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    ts REAL NOT NULL,
    type TEXT NOT NULL,
    payload TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS snapshots (
    seq INTEGER PRIMARY KEY,
    state TEXT NOT NULL
);
"""


# F-013 S4 (G1): events kept in memory while the disk refuses them (test15: "database or disk is full" killed the
# flush task, so nothing more was written and shutdown ended in a traceback); the oldest go first past this many
MAX_UNWRITTEN = 200_000
RETRY_S = 5.0  # while failing, a write is tried at most this often


class EventLog:
    def __init__(self, path: Path, flush_interval_s: float = 0.5, flush_batch: int = 200) -> None:
        self.path = path
        self._flush_interval = flush_interval_s
        self._flush_batch = flush_batch
        self._buffer: list[tuple[float, str, str]] = []
        self._conn: Optional[sqlite3.Connection] = None
        self._flusher: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
        self.written = 0
        self.failing = ""  # why the last write failed ("" = writing); the events wait in memory meanwhile
        self.dropped = 0   # events lost because the memory buffer was full too
        self._retry_at = 0.0

    async def open(self, bus: EventBus) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = await asyncio.to_thread(self._connect)
        except (OSError, sqlite3.Error) as e:  # a full / read-only disk must not stop the lecture
            self._fail(e)
        bus.subscribe("event_log", self._on_event, queue_size=10_000)
        self._flusher = asyncio.create_task(self._periodic_flush(), name="event_log:flush")

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.executescript(SCHEMA)
        return conn

    async def _on_event(self, event: Event) -> None:
        if event.ephemeral:
            return
        self._buffer.append((event.ts, event.type, event.model_dump_json()))
        if len(self._buffer) >= self._flush_batch:
            await self.flush()

    async def _periodic_flush(self) -> None:
        while True:
            await asyncio.sleep(self._flush_interval)
            await self.flush()

    async def flush(self, force: bool = False) -> None:
        async with self._lock:
            if not self._buffer or (self.failing and not force and time.monotonic() < self._retry_at):
                return
            if self._conn is None:
                try:  # the disk may have room again
                    self._conn = await asyncio.to_thread(self._connect)
                except (OSError, sqlite3.Error) as e:
                    self._fail(e)
                    return
            batch, self._buffer = self._buffer, []
            try:
                await asyncio.to_thread(self._write, batch)
            except (OSError, sqlite3.Error) as e:
                self._buffer = batch + self._buffer  # kept, in order; written when the disk has room again
                self._fail(e)
                return
            self.written += len(batch)
            if self.failing:
                log.warning("event log writing again (%d events kept in memory were saved)", len(batch))
                self.failing = ""

    def _fail(self, e: BaseException) -> None:
        if len(self._buffer) > MAX_UNWRITTEN:
            self.dropped += len(self._buffer) - MAX_UNWRITTEN
            del self._buffer[: len(self._buffer) - MAX_UNWRITTEN]
        if not self.failing:  # once per failure streak, without a traceback: the lecture goes on
            log.warning("event log %s cannot be written (%s); events are kept in memory until the disk has room",
                        self.path, e)
        self.failing = str(e) or type(e).__name__
        self._retry_at = time.monotonic() + RETRY_S

    def _write(self, batch: list[tuple[float, str, str]]) -> None:
        assert self._conn is not None
        with self._conn:
            self._conn.executemany("INSERT INTO events(ts, type, payload) VALUES (?, ?, ?)", batch)

    async def close(self) -> None:
        """Call after the bus has been drained/closed so every event is buffered."""
        if self._flusher:
            self._flusher.cancel()
            try:
                await self._flusher
            except asyncio.CancelledError:
                pass
        await self.flush(force=True)
        if self.failing:
            log.warning("event log: %d event(s) of this lecture could not be saved (%s)%s", len(self._buffer),
                        self.failing, f", {self.dropped} more dropped" if self.dropped else "")
        if self._conn is not None:
            conn, self._conn = self._conn, None
            try:
                await asyncio.to_thread(conn.close)
            except sqlite3.Error as e:
                log.warning("event log close: %s", e)


def read_events(path: Path) -> Iterator[tuple[int, str, Optional[Event]]]:
    """Yield (seq, type, decoded event or None if the type is unknown)."""
    conn = sqlite3.connect(path)
    try:
        for seq, type_name, payload in conn.execute("SELECT seq, type, payload FROM events ORDER BY seq"):
            yield seq, type_name, decode_event(type_name, payload)
    finally:
        conn.close()
