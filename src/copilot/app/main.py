"""Application entry point and lifecycle: STARTING → READY → (Enter) → LIVE → ENDING → ENDED."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT, Config, load_config
from copilot.core.events import (
    Command,
    CommandReceived,
    Lifecycle,
    LifecycleChanged,
    new_id,
)
from copilot.core.logging_setup import setup_logging
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.persistence.event_log import EventLog, read_events
from copilot.sim.simulator import LectureSimulator, parse_script

log = logging.getLogger("copilot")


def new_session_id() -> str:
    return f"{time.strftime('%Y%m%d-%H%M%S')}-{new_id()[:4]}"


class TerminalInput:
    """Reads terminal lines on a daemon thread; Enter → start, 'q' → end."""

    def __init__(self, loop: asyncio.AbstractEventLoop, queue: "asyncio.Queue[str]") -> None:
        self._loop = loop
        self._queue = queue

    def start(self) -> None:
        threading.Thread(target=self._run, name="terminal-input", daemon=True).start()

    def _run(self) -> None:
        for line in sys.stdin:
            self._loop.call_soon_threadsafe(self._queue.put_nowait, line.strip().lower())
        self._loop.call_soon_threadsafe(self._queue.put_nowait, "<eof>")


class App:
    def __init__(self, config: Config, *, simulate: Optional[Path], wait_for_enter: bool, speed: float) -> None:
        self.config = config
        self.simulate = simulate
        self.wait_for_enter = wait_for_enter
        self.speed = speed
        self.session_id = new_session_id()
        self.session_dir = PROJECT_ROOT / config.get("app", "data_dir", "data") / "sessions" / self.session_id
        self.bus = EventBus(config.get("bus", "default_queue_size", 1000))
        self.bus.session_id = self.session_id
        self.event_log = EventLog(
            self.session_dir / "session.sqlite",
            config.get("persistence", "flush_interval_s", 0.5),
            config.get("persistence", "flush_batch", 200),
        )
        self.store: Optional[LectureStateStore] = None
        self._terminal: "asyncio.Queue[str]" = asyncio.Queue()
        self._stop = asyncio.Event()

    async def _lifecycle(self, state: Lifecycle, reason: str = "") -> None:
        await self.bus.publish(LifecycleChanged(state=state, reason=reason))

    def _setup(self, script_setup: dict[str, str]) -> LectureSetup:
        base = self.config.section("setup")
        merged = {**base, **{k: v for k, v in {
            "subject": script_setup.get("subject"),
            "grade_level": script_setup.get("grade"),
            "expected_topic": script_setup.get("topic"),
        }.items() if v}}
        return LectureSetup(theme=self.config.get("app", "theme", "light"), **merged)

    async def run(self) -> int:
        script = parse_script(self.simulate) if self.simulate else None
        self.store = LectureStateStore(self.bus, self.session_id, self._setup(script.setup if script else {}))
        self.store.attach()
        await self.event_log.open(self.bus)
        await self._lifecycle(Lifecycle.STARTING)
        TerminalInput(asyncio.get_running_loop(), self._terminal).start()
        try:
            # Heavy components (STT, models, display server) initialize here in later milestones.
            await self._lifecycle(Lifecycle.READY)
            print(f"\n[READY] session {self.session_id}")
            setup = self.store.snapshot().setup
            if setup.subject or setup.expected_topic:
                print(f"        subject={setup.subject or '-'} grade={setup.grade_level or '-'} topic={setup.expected_topic or '-'}")
            if self.wait_for_enter:
                print("        Press Enter to start the lecture (q + Enter to quit).")
                if not await self._wait_for_start():
                    await self._lifecycle(Lifecycle.ENDING, "quit before start")
                    return 0
            await self.bus.publish(CommandReceived(command=Command(kind="start", origin="terminal")))
            await self._lifecycle(Lifecycle.LIVE)
            print("[LIVE]  lecture started. Type q + Enter to end.")
            await self._run_live(script)
            await self._lifecycle(Lifecycle.ENDING, "lecture finished")
            return 0
        finally:
            await self._shutdown()

    async def _wait_for_start(self) -> bool:
        while True:
            line = await self._terminal.get()
            if line in ("q", "quit", "<eof>"):
                return False
            if line == "":
                return True

    async def _watch_terminal(self) -> None:
        while not self._stop.is_set():
            line = await self._terminal.get()
            if line in ("q", "quit"):
                await self.bus.publish(CommandReceived(command=Command(kind="end", origin="terminal")))
                self._stop.set()

    async def _run_live(self, script) -> None:
        watcher = asyncio.create_task(self._watch_terminal())
        try:
            if script is not None:
                sim = LectureSimulator(
                    self.bus,
                    script,
                    words_per_minute=self.config.get("sim", "words_per_minute", 150),
                    min_utterance_s=self.config.get("sim", "min_utterance_s", 1.0),
                    speed=self.speed,
                )
                await sim.run(self._stop)
            else:
                log.warning("No audio source yet (M1). Waiting for q to end.")
                await self._stop.wait()
        finally:
            watcher.cancel()

    async def _shutdown(self) -> None:
        await self._lifecycle(Lifecycle.ENDED)
        await self.bus.close()
        await self.event_log.close()
        self._print_summary()

    def _print_summary(self) -> None:
        if self.store is None:
            return
        s = self.store.snapshot()
        counts = Counter(t for _, t, _ in read_events(self.event_log.path))
        print(f"[ENDED] session {self.session_id}: {s.stats.segments} segments, {s.stats.words} words, "
              f"state v{s.version}, {sum(counts.values())} events logged")
        print("        " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
        print(f"        log: {self.event_log.path}")


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="copilot", description="Multimodal AI Teaching Copilot")
    p.add_argument("--simulate", type=Path, help="lecture script to feed instead of the microphone")
    p.add_argument("--no-wait", action="store_true", help="start immediately without waiting for Enter")
    p.add_argument("--speed", type=float, default=None, help="simulator time compression factor")
    p.add_argument("--log-level", default=None)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config = load_config()
    setup_logging(args.log_level or config.get("app", "log_level", "INFO"))
    speed = args.speed if args.speed is not None else config.get("sim", "speed", 1.0)

    async def _run() -> int:
        app = App(config, simulate=args.simulate, wait_for_enter=not args.no_wait, speed=speed)
        return await app.run()

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n[ENDED] interrupted")
        return 130
