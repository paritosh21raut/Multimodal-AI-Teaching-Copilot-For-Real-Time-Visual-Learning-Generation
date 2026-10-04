"""Application entry point and lifecycle: STARTING → READY → (Enter) → LIVE → ENDING → ENDED."""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
import threading
import time
import webbrowser
from collections import Counter
from pathlib import Path
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT, Config, load_config
from copilot.core.events import (
    AudioDeviceLost,
    Command,
    CommandReceived,
    Event,
    Lifecycle,
    LifecycleChanged,
    TranscriptFinal,
    UtteranceDropped,
    new_id,
)
from copilot.core.logging_setup import setup_logging
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.persistence.event_log import EventLog, read_events
from copilot.presentation.deck import Deck
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
    def __init__(
        self,
        config: Config,
        *,
        simulate: Optional[Path] = None,
        audio_file: Optional[Path] = None,
        wait_for_enter: bool = True,
        speed: float = 1.0,
        setup_overrides: Optional[dict[str, str]] = None,
        display: bool = True,
        open_display: bool = False,
        demo_slides: bool = False,
    ) -> None:
        self.config = config
        self.display_enabled = display
        self.open_display = open_display
        self.demo_slides = demo_slides
        self.server = None
        self.simulate = simulate
        self.audio_file = audio_file
        self.setup_overrides = setup_overrides or {}
        self.engine = None
        self.speech = None
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
        self._start_requested = asyncio.Event()
        self.deck = Deck(self.bus)

    async def _lifecycle(self, state: Lifecycle, reason: str = "") -> None:
        await self.bus.publish(LifecycleChanged(state=state, reason=reason))

    def _setup(self, script_setup: dict[str, str]) -> LectureSetup:
        """Precedence: config [setup] < simulator script @setup < CLI flags."""
        merged = self.config.section("setup")
        for src in (script_setup, self.setup_overrides):
            merged.update({k: v for k, v in {
                "subject": src.get("subject"),
                "grade_level": src.get("grade"),
                "expected_topic": src.get("topic"),
            }.items() if v})
        return LectureSetup(theme=self.config.get("app", "theme", "light"), **merged)

    async def _init_speech(self) -> None:
        from copilot.stt.factory import make_engine

        self.engine = make_engine(self.config)
        cfg = self.engine.cfg
        print(f"[INIT]  loading speech model {cfg.model} on {cfg.device} ...", flush=True)
        took = await asyncio.to_thread(self.engine.load)
        print(f"[INIT]  speech model ready ({took:.1f} s)", flush=True)

    async def _print_transcript(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            seg = event.segment
            lat = f" ({event.stt_latency_ms:.0f} ms)" if event.stt_latency_ms is not None else ""
            print(f"  [{seg.start:7.1f}s] {seg.text}{lat}", flush=True)
        elif isinstance(event, UtteranceDropped):
            print(f"  [{event.start:7.1f}s] (dropped: {event.reason}) {event.text}", flush=True)
        elif isinstance(event, AudioDeviceLost):
            print(f"  [AUDIO] device lost: {event.detail}", flush=True)

    async def _on_command(self, event: Event) -> None:
        assert isinstance(event, CommandReceived)
        if event.command.kind == "start":
            self._start_requested.set()
        elif event.command.kind == "end":
            self._stop.set()

    async def _start_display(self) -> None:
        from copilot.display.hub import DisplayHub
        from copilot.display.server import DisplayServer

        hub = DisplayHub(self.bus, theme=self.store.snapshot().setup.theme if self.store else "light")
        hub.attach()
        self.server = DisplayServer(
            hub, self.config.get("display", "host", "127.0.0.1"), int(self.config.get("display", "port", 8765))
        )
        await self.server.start()

    async def run(self) -> int:
        script = parse_script(self.simulate) if self.simulate else None
        self.store = LectureStateStore(self.bus, self.session_id, self._setup(script.setup if script else {}))
        self.store.attach()
        self.deck.attach()
        await self.event_log.open(self.bus)
        self.bus.subscribe("terminal_transcript", self._print_transcript,
                           [TranscriptFinal, UtteranceDropped, AudioDeviceLost])
        self.bus.subscribe("app_commands", self._on_command, [CommandReceived])
        await self._lifecycle(Lifecycle.STARTING)
        TerminalInput(asyncio.get_running_loop(), self._terminal).start()
        try:
            if self.display_enabled:
                await self._start_display()
            if script is None:
                await self._init_speech()
            await self._lifecycle(Lifecycle.READY)
            print(f"\n[READY] session {self.session_id}", flush=True)
            if self.server is not None:
                print(f"        classroom display: {self.server.base_url}/display   (projector, full screen: F11)", flush=True)
                print(f"        teacher control:   {self.server.base_url}/control", flush=True)
                if self.open_display:
                    webbrowser.open(f"{self.server.base_url}/control")
                    webbrowser.open(f"{self.server.base_url}/display")
            setup = self.store.snapshot().setup
            if setup.subject or setup.expected_topic:
                print(f"        subject={setup.subject or '-'} grade={setup.grade_level or '-'} topic={setup.expected_topic or '-'}", flush=True)
            if self.wait_for_enter:
                print("        Press Enter (or Start in the control view) to begin; q + Enter to quit.", flush=True)
                if not await self._wait_for_start():
                    await self._lifecycle(Lifecycle.ENDING, "quit before start")
                    return 0
            await self.bus.publish(CommandReceived(command=Command(kind="start", origin="terminal")))
            await self._lifecycle(Lifecycle.LIVE)
            print("[LIVE]  lecture started. Type q + Enter to end.", flush=True)
            await self._run_live(script)
            await self._lifecycle(Lifecycle.ENDING, "lecture finished")
            return 0
        finally:
            await self._shutdown()

    async def _wait_for_start(self) -> bool:
        """True on Enter or a start command from the control view; False on q / end of input."""
        started = asyncio.create_task(self._start_requested.wait())
        try:
            while True:
                line_task = asyncio.create_task(self._terminal.get())
                done, _ = await asyncio.wait({line_task, started}, return_when=asyncio.FIRST_COMPLETED)
                if started in done:
                    line_task.cancel()
                    return True
                line = line_task.result()
                if line in ("q", "quit", "<eof>"):
                    return False
                if line == "":
                    return True
        finally:
            started.cancel()

    async def _watch_terminal(self) -> None:
        while not self._stop.is_set():
            line = await self._terminal.get()
            if line in ("q", "quit"):
                await self.bus.publish(CommandReceived(command=Command(kind="end", origin="terminal")))
                self._stop.set()

    async def _run_live(self, script) -> None:
        watcher = asyncio.create_task(self._watch_terminal())
        demo = None
        if self.demo_slides:
            from copilot.presentation.demo import run_demo

            demo = asyncio.create_task(run_demo(self.deck, self.config.get("display", "demo_interval_s", 3.0), self._stop))
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
            elif self.audio_file is not None or not self.demo_slides:
                await self._run_speech()
            if demo is not None:
                await demo
        finally:
            watcher.cancel()
            if demo is not None:
                demo.cancel()

    async def _run_speech(self) -> None:
        from copilot.stt.factory import make_source, segmenter_config, vocabulary_prompt
        from copilot.stt.pipeline import SpeechPipeline

        assert self.engine is not None and self.store is not None
        source = make_source(self.config, self.audio_file, self.speed)
        self.speech = SpeechPipeline(
            self.bus,
            source,
            self.engine,
            segmenter=segmenter_config(self.config),
            prompt=vocabulary_prompt(self.store.snapshot().setup),
        )
        try:
            self.speech.start()
            stop_task = asyncio.create_task(self._stop.wait())
            done_task = asyncio.create_task(self.speech.wait_finished())
            try:
                await asyncio.wait({stop_task, done_task}, return_when=asyncio.FIRST_COMPLETED)
            finally:
                stop_task.cancel()
                done_task.cancel()
        finally:
            await self.speech.stop()  # closes the mic even on Ctrl+C / errors

    async def _shutdown(self) -> None:
        await self._lifecycle(Lifecycle.ENDED)
        if self.server is not None:
            await asyncio.sleep(0.2)  # let clients receive the final state
            await self.server.stop()
        await self.bus.close()
        await self.event_log.close()
        self._print_summary()

    def _print_summary(self) -> None:
        if self.store is None:
            return
        s = self.store.snapshot()
        counts = Counter(t for _, t, _ in read_events(self.event_log.path))
        print(f"[ENDED] session {self.session_id}: {s.stats.segments} segments, {s.stats.words} words, "
              f"state v{s.version}, {sum(counts.values())} events logged", flush=True)
        print("        " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())), flush=True)
        if self.speech is not None:
            st = self.speech.stats
            lat = sorted(st["latency_ms"])
            if lat:
                p50 = lat[len(lat) // 2]
                p95 = lat[min(len(lat) - 1, int(len(lat) * 0.95))]
                print(f"        stt: {st['published']} published, {st['dropped']} dropped, "
                      f"latency p50={p50:.0f} ms p95={p95:.0f} ms max={lat[-1]:.0f} ms", flush=True)
            else:
                print(f"        stt: {st['published']} published, {st['dropped']} dropped", flush=True)
        print(f"        log: {self.event_log.path}", flush=True)


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="copilot", description="Multimodal AI Teaching Copilot")
    p.add_argument("--simulate", type=Path, help="lecture script to feed instead of the microphone")
    p.add_argument("--no-wait", action="store_true", help="start immediately without waiting for Enter")
    p.add_argument("--audio-file", type=Path, help="16 kHz WAV played through the real audio pipeline instead of the mic")
    p.add_argument("--speed", type=float, default=None, help="time compression for --simulate / --audio-file")
    p.add_argument("--subject", help="optional lecture setup: subject")
    p.add_argument("--grade", help="optional lecture setup: class/grade level")
    p.add_argument("--topic", help="optional lecture setup: expected topic")
    p.add_argument("--no-display", action="store_true", help="do not start the display server")
    p.add_argument("--open", action="store_true", help="open the display and control pages in the browser")
    p.add_argument("--demo-slides", action="store_true", help="play a scripted slide sequence (display check)")
    p.add_argument("--log-level", default=None)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    config = load_config()
    setup_logging(args.log_level or config.get("app", "log_level", "INFO"))
    speed = args.speed if args.speed is not None else config.get("sim", "speed", 1.0)

    async def _run() -> int:
        app = App(
            config,
            simulate=args.simulate,
            audio_file=args.audio_file,
            wait_for_enter=not args.no_wait,
            speed=speed,
            setup_overrides={"subject": args.subject, "grade": args.grade, "topic": args.topic},
            display=not args.no_display,
            open_display=args.open,
            demo_slides=args.demo_slides,
        )
        return await app.run()

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n[ENDED] interrupted", flush=True)
        return 130
