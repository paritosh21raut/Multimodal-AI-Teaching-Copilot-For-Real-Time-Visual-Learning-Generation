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
    ConcernRaised,
    Event,
    ImageReady,
    InterpretationReady,
    Lifecycle,
    LifecycleChanged,
    SlidePatch,
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

OPEN_AFTER_READY_S = 3.0     # pages left open from an earlier run reconnect by themselves within this time ...
OPEN_AFTER_SERVER_S = 4.0    # ... and the client's reconnect backoff is capped at 2 s (web/shared/ws.js)
PAGES = (("control", "teacher control"), ("display", "classroom display"))

# Rough planning number for the startup view: ~4.5 interpretations/min x ~1.8k tokens (real Groq runs, 2026-10-05).
TOKENS_PER_LECTURE_MINUTE = 8000


def print_quota(router) -> None:
    """Free-tier tokens left today per model and key, and roughly how many lecture minutes that covers. Terminal
    only, shown while the system loads (before Enter); the teacher's screen does not show it."""
    print("\n[QUOTA] AI models, free tokens left today (rolling 24 h, counted by this app + Groq's replies):",
          flush=True)
    tokens_left = 0
    for q in router.quota():
        if q["tpd"]:
            left = 0 if q["spent"] else max(0, q["tpd"] - q["used"])
            tokens_left += left
            amount = f"{left / 1000:4.0f}k of {q['tpd'] / 1000:.0f}k tokens"
        else:
            amount = "not tracked"
        if q["spent"]:
            again = q["free_in_s"]
            status = "SPENT" + (f", free again in ~{again / 3600:.1f} h" if again >= 3600
                                else f", free again in ~{again / 60:.0f} min" if again >= 60 else "")
        else:
            status = "IN USE" if q["in_use"] else ("unused" if q["used"] == 0 else "ok")
        print(f"        {q['env'] or q['name']:22} {q['model']:28} {amount:20} {status}", flush=True)
    minutes = tokens_left / TOKENS_PER_LECTURE_MINUTE
    if minutes < 1:
        print("        !! No Groq quota left: slides will come from the backup model (if it answers) or the simple\n"
              "           built-in fallback. Add another key as GROQ_API_KEY_<name> in .env, or wait.", flush=True)
    else:
        print(f"        enough for about {minutes:.0f} lecture minutes", flush=True)


def text_similarity(embedder):
    """(a, b) -> cosine of their sentence embeddings: is an image query about a slide's text (F-007b)."""
    def similarity(a: str, b: str) -> float:
        v = embedder.embed([a, b])
        return float(v[0] @ v[1])
    return similarity


def lifecycle_for_command(kind: str, now: Lifecycle) -> Optional[Lifecycle]:
    """Pause / Resume (replaces Freeze, user 2026-10-06): a break in a running lecture. While PAUSED the
    understanding service discards what is said; navigation and editing still work. None: nothing changes."""
    if kind == "pause" and now == Lifecycle.LIVE:
        return Lifecycle.PAUSED
    if kind == "resume" and now == Lifecycle.PAUSED:
        return Lifecycle.LIVE
    return None


def pages_to_open(connects: dict[str, int]) -> list[str]:
    """Roles with no page connected since the server started (a reconnecting old tab counts as connected)."""
    return [role for role, _ in PAGES if not connects.get(role)]


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
        open_pages: bool = False,
        demo_slides: bool = False,
        understanding: bool = True,
    ) -> None:
        self.config = config
        self.understanding_enabled = understanding
        self.understanding = None
        self.presentation = None
        self.images = None  # visuals.service.ImageService (F-007b)
        self._http = None
        self.display_enabled = display
        self.open_pages = open_pages
        self._opener: Optional[asyncio.Task] = None
        self._router = None
        self.hub = None
        self._server_started = 0.0
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
        self._now = Lifecycle.STARTING

    async def _lifecycle(self, state: Lifecycle, reason: str = "") -> None:
        self._now = state
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
        from copilot.stt.pipeline import SpeechPipeline  # noqa: F401  (import before the terminal thread starts)

        self.engine = make_engine(self.config)
        cfg = self.engine.cfg
        print(f"[INIT]  loading speech model {cfg.model} on {cfg.device} ...", flush=True)
        took = await asyncio.to_thread(self.engine.load)
        print(f"[INIT]  speech model ready ({took:.1f} s)", flush=True)

    async def _init_understanding(self) -> None:
        import httpx

        from copilot.core.events import LLMCallFailed
        from copilot.llm.router import build_router
        from copilot.understanding.embedder import MiniLmEmbedder
        from copilot.understanding.interpreter import Interpreter
        from copilot.understanding.service import UnderstandingService, UnderstandingSettings

        assert self.store is not None
        u = self.config.section("understanding")
        embedder: Optional[MiniLmEmbedder] = MiniLmEmbedder(
            PROJECT_ROOT / u.get("embed_dir", "models/minilm"), u.get("embed_repo", "sentence-transformers/all-MiniLM-L6-v2")
        )
        print("[INIT]  loading concept embedder (MiniLM ONNX, CPU) ...", flush=True)
        try:
            took = await asyncio.to_thread(embedder.load)
            print(f"[INIT]  concept embedder ready ({took:.1f} s)", flush=True)
        except Exception as e:  # explicit degraded mode: cue words only
            log.exception("embedder load failed")
            print(f"[INIT]  concept embedder unavailable ({type(e).__name__}); using cue words only", flush=True)
            embedder = None

        async def on_failure(entry: str, error: str, will_retry: bool) -> None:
            await self.bus.publish(LLMCallFailed(provider=entry, error=error[:300], will_retry=will_retry))

        from copilot.llm.usage import UsageLedger

        self._http = httpx.AsyncClient()
        usage = UsageLedger(PROJECT_ROOT / self.config.get("llm", "usage_file", "data/llm_usage.json"))
        router = build_router(self.config, self._http, on_failure, usage)
        self._router = router
        names = [e.name for e in router.entries]
        print(f"[INIT]  LLM providers: {' -> '.join(names)}", flush=True)
        settings = UnderstandingSettings.from_config(self.config)
        self.understanding = UnderstandingService(
            self.bus, self.store, Interpreter(router, settings.interpreter), embedder, settings,
            speed=self.speed if self.simulate or self.audio_file else 1.0,
        )
        self.understanding.attach()
        if not self.demo_slides:
            from copilot.presentation.engine import PresentationEngine, PresentationSettings

            self.presentation = PresentationEngine(
                self.bus, self.store, self.deck, PresentationSettings.from_config(self.config),
                speed=self.speed if self.simulate or self.audio_file else 1.0,
                relevance=text_similarity(embedder) if embedder is not None else None,
            )
            self.presentation.attach()
            self._init_images()

    def _init_images(self) -> None:
        """Automatic images (F-007b): needs the `images` extra (Pillow) and the CLIP model (loads in the background)."""
        if not self.config.get("images", "enabled", True):
            print("[INIT]  images: automatic images off (config)", flush=True)
            return
        try:
            import PIL  # noqa: F401

            from copilot.visuals.service import ImageService
        except ImportError as e:
            print(f"[INIT]  images: off ({e}; pip install -e \".[images]\")", flush=True)
            return
        self.images = ImageService.from_config(self.bus, self.config)
        self.images.attach()
        self.bus.subscribe("terminal_images", self._print_image, [ImageReady])
        print("[INIT]  images: Wikipedia/Commons + CLIP (CPU), loading in the background", flush=True)

    async def _print_image(self, event: Event) -> None:
        if isinstance(event, ImageReady):
            found = event.images[0].get("title", "") if event.images else f"none ({event.reason})"
            print(f"  [IMAGE] {event.query!r} -> {found} ({event.seconds:.1f} s{', cached' if event.cached else ''})",
                  flush=True)

    async def _print_understanding(self, event: Event) -> None:
        if isinstance(event, InterpretationReady):
            it = event.interpretation
            acts = ",".join(a.act for a in it.acts) or "-"
            src = "FALLBACK " + event.fallback_reason[:80] if event.fallback else event.provider
            print(f"  [UNDERSTAND] {it.topic} > {it.subtopic or '-'} ({it.relation}) acts={acts} "
                  f"hint={it.representation_hint} lines={len(event.segment_ids)} via {src} {event.latency_ms:.0f} ms",
                  flush=True)
            if it.summary_delta:
                print(f"               {it.summary_delta}", flush=True)
        elif isinstance(event, ConcernRaised):
            c = event.concern
            if c.get("kind") == "transcription":  # misheard words: no card for the teacher, only this log line
                shown = "corrected on the slide" if c.get("applied") else "kept as heard (low confidence)"
                print(f"  [HEARD] {c.get('wrong') or c.get('claim')!r} -> {c.get('right') or c.get('suggested_correction')!r}"
                      f" {shown} ({c.get('confidence')})", flush=True)
            else:
                print(f"  [CONCERN] ({c.get('kind')}) {c.get('claim')} -> {c.get('suggested_correction')} "
                      f"({c.get('confidence')}, slide shows {'the correction' if c.get('applied') else 'as said'})",
                      flush=True)

    async def _print_slide(self, event: Event) -> None:
        if isinstance(event, SlidePatch):
            spec = event.spec
            n = sum(len(b.get("items", b.get("steps", b.get("rows", b.get("events", b.get("links", [])))))) or 1
                    for b in spec.get("blocks", []))
            print(f"  [SLIDE] {event.op:6} {spec.get('title')!r} [{spec.get('layout')}] v{event.version} "
                  f"({n} items)", flush=True)

    async def _print_transcript(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            seg = event.segment
            lat = f" ({event.stt_latency_ms:.0f} ms)" if event.stt_latency_ms is not None else ""
            paused = "(paused, not used) " if self._now == Lifecycle.PAUSED else ""
            print(f"  [{seg.start:7.1f}s] {paused}{seg.text}{lat}", flush=True)
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
        else:
            nxt = lifecycle_for_command(event.command.kind, self._now)
            if nxt is not None:
                await self._lifecycle(nxt, "teacher")
                print("[PAUSE] paused: what is said now is not put on slides (Resume to continue)"
                      if nxt == Lifecycle.PAUSED else "[LIVE]  resumed", flush=True)

    async def _start_display(self) -> None:
        from copilot.display.hub import DisplayHub
        from copilot.display.server import DisplayServer

        hub = DisplayHub(self.bus, theme=self.store.snapshot().setup.theme if self.store else "light")
        hub.attach()
        self.hub = hub
        from copilot.visuals.service import cache_from_config

        self.server = DisplayServer(
            hub, self.config.get("display", "host", "127.0.0.1"), int(self.config.get("display", "port", 8765)),
            media=cache_from_config(self.config),
            upload_max_bytes=int(float(self.config.get("images", "upload_max_mb", 10)) * 1024 * 1024),
        )
        await self.server.start()
        self._server_started = asyncio.get_running_loop().time()

    async def run(self) -> int:
        script = parse_script(self.simulate) if self.simulate else None
        self.store = LectureStateStore(self.bus, self.session_id, self._setup(script.setup if script else {}))
        self.store.attach()
        self.deck.attach()
        await self.event_log.open(self.bus)
        self.bus.subscribe("terminal_transcript", self._print_transcript,
                           [TranscriptFinal, UtteranceDropped, AudioDeviceLost])
        self.bus.subscribe("app_commands", self._on_command, [CommandReceived])
        self.bus.subscribe("terminal_understanding", self._print_understanding, [InterpretationReady, ConcernRaised])
        self.bus.subscribe("terminal_slides", self._print_slide, [SlidePatch])
        await self._lifecycle(Lifecycle.STARTING)
        try:
            if self.display_enabled:
                await self._start_display()
            if script is None:
                await self._init_speech()
            if self.understanding_enabled:
                await self._init_understanding()
            # Started only after every heavy import: on Windows a DLL import (numpy) can deadlock while another
            # thread is blocked reading a piped stdin (seen with tools/screenshot_app.py).
            TerminalInput(asyncio.get_running_loop(), self._terminal).start()
            await self._lifecycle(Lifecycle.READY)
            if self._router is not None:
                print_quota(self._router)
            print(f"\n[READY] session {self.session_id}", flush=True)
            if self.server is not None:
                print(f"        classroom display: {self.server.base_url}/display   (projector, full screen: F11)", flush=True)
                print(f"        teacher control:   {self.server.base_url}/control", flush=True)
                if self.open_pages:
                    self._opener = asyncio.create_task(self._auto_open(), name="app:auto-open")
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
            if self.understanding is not None:
                pending = len(self.understanding.buffer.lines)
                print(f"[END]   finishing lecture understanding ({pending} buffered lines) ...", flush=True)
                if not await self.understanding.flush(timeout=90.0):
                    print("[END]   understanding did not finish in 90 s; remaining lines stay in the event log", flush=True)
                await self.bus.drain()  # the last interpretation reaches the presentation engine
            if self.presentation is not None:
                await self.presentation.flush_pending()
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
                    vad=True,  # simulated mic VAD, so the gate sees pauses only where the script pauses
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

    async def _auto_open(self) -> None:
        """After READY, open the control/display pages in the default browser unless a page of that role has
        (re)connected: tabs left open from an earlier run reconnect on their own, so no duplicate tabs."""
        assert self.server is not None and self.hub is not None
        loop = asyncio.get_running_loop()
        await asyncio.sleep(max(OPEN_AFTER_READY_S, self._server_started + OPEN_AFTER_SERVER_S - loop.time()))
        for role in pages_to_open(self.hub.connects):
            url = f"{self.server.base_url}/{role}"
            try:
                opened = await asyncio.to_thread(webbrowser.open, url)
            except Exception as e:  # no browser available: the URLs are printed at READY
                log.warning("could not open %s: %s", url, e)
                continue
            print(f"[OPEN]  {url}" if opened else f"[OPEN]  no browser opened {url}; open it manually", flush=True)

    async def _shutdown(self) -> None:
        if self._opener is not None:
            self._opener.cancel()
        if self.presentation is not None:
            await self.presentation.stop()
        if self.images is not None:
            await self.images.stop()
        if self.understanding is not None:
            await self.understanding.stop()
        if self._http is not None:
            await self._http.aclose()
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
        if self.understanding is not None:
            u = self.understanding.stats
            toks = list(u.prompt_tokens)
            lat = sorted(u.latencies_ms)
            print(f"        understanding: {u.requests} interpretations ({s.stats.llm_calls} by LLM, {u.fallbacks} fallbacks, "
                  f"{u.repaired} repaired), max {u.max_calls_per_minute} calls/min, "
                  f"prompt tokens max={u.max_prompt_tokens} avg={sum(toks) // max(1, len(toks))}, "
                  f"latency p50={lat[len(lat) // 2] if lat else 0:.0f} ms max={lat[-1] if lat else 0:.0f} ms", flush=True)
            if self.presentation is not None:
                ps = self.presentation.stats
                print(f"        presentation: {ps.slides} slides; planner ops {dict(ps.ops)}; "
                      f"revisions {ps.revisions}, corrections shown {ps.corrections_shown}, "
                      f"shown as said {ps.shown_as_said}", flush=True)
                if self.images is not None:
                    shown = sum(1 for sp in self.deck.slides if any(b.type == "image" for b in sp.blocks))
                    print(f"        images: {self.images.stats}; slides with an image {shown}/{len(self.deck.slides)}",
                          flush=True)
                for i, spec in enumerate(self.deck.slides, 1):
                    part = f" [part {spec.part}]" if spec.part else ""
                    print(f"          {i}. [{spec.layout}] {spec.title}{part}  (v{spec.version}, "
                          f"{[b.type for b in spec.blocks]})",
                          flush=True)
            print(f"        providers: {u.providers or '-'}; triggers: {u.reasons or '-'}; "
                  f"outline: {[t.title + ' > ' + ', '.join(x.title for x in t.subtopics) for t in s.outline]}; "
                  f"concerns: {len(s.concerns)}", flush=True)
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
    p.add_argument("--open", action="store_true", help=argparse.SUPPRESS)  # old flag: opening is the default now
    p.add_argument("--no-open", action="store_true",
                   help="do not open the control/display pages (by default they open ~3 s after READY unless a page "
                        "of that role is already connected)")
    p.add_argument("--demo-slides", action="store_true", help="play a scripted slide sequence (display check)")
    p.add_argument("--no-understanding", action="store_true", help="disable lecture understanding (no LLM calls)")
    p.add_argument("--log-level", default=None)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # LLM text can contain characters the console codepage lacks
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
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
            open_pages=not args.no_open,
            demo_slides=args.demo_slides,
            understanding=not args.no_understanding,
        )
        return await app.run()

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n[ENDED] interrupted", flush=True)
        return 130
