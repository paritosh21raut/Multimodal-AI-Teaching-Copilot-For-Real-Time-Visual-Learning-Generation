"""Append-only SQLite event log (docs/architecture/persistence.md).

Events are buffered and written in batches from a worker thread so the event loop never blocks on disk.
"""
from __future__ import annotations

import asyncio
import logging
import sqlite3
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

    async def open(self, bus: EventBus) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await asyncio.to_thread(self._connect)
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

    async def flush(self) -> None:
        async with self._lock:
            if not self._buffer or self._conn is None:
                return
            batch, self._buffer = self._buffer, []
            await asyncio.to_thread(self._write, batch)
            self.written += len(batch)

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
        await self.flush()
        if self._conn is not None:
            conn, self._conn = self._conn, None
            await asyncio.to_thread(conn.close)


def read_events(path: Path) -> Iterator[tuple[int, str, Optional[Event]]]:
    """Yield (seq, type, decoded event or None if the type is unknown)."""
    conn = sqlite3.connect(path)
    try:
        for seq, type_name, payload in conn.execute("SELECT seq, type, payload FROM events ORDER BY seq"):
            yield seq, type_name, decode_event(type_name, payload)
    finally:
        conn.close()
