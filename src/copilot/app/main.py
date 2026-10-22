"""Application entry point and lifecycle: STARTING → READY → (Enter) → LIVE → ENDING → ENDED."""
from __future__ import annotations

import argparse
import asyncio
import logging
import secrets
import shutil
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
    ShareChanged,
    SlidePatch,
    TranscriptFinal,
    UtteranceDropped,
    CorrectionPlaced,
    ModeChanged,
    SimulationSettingChanged,
    VocabularyChanged,
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
MATERIALS_FINISH_S = 180.0  # at the end of the lecture, materials being made get this long to finish (F-010)

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


def disk_warning(path: Path, min_free_gb: float) -> str:
    """F-013 S4 (G1): a warning when the disk holding the data folder has less than `min_free_gb` free ("" = enough).
    test15 ran out mid-lecture: the usage file and the event log could not be written."""
    probe = path
    while not probe.exists() and probe.parent != probe:
        probe = probe.parent
    try:
        free = shutil.disk_usage(probe).free / 1e9
    except OSError:
        return ""
    if free >= min_free_gb:
        return ""
    return (f"only {free:.2f} GB free on the disk of {path} (less than {min_free_gb:g} GB): the lecture runs, but its "
            "log, images and files may not be saved; free some space")


# what the slide shows for a concern (F-013 S3, E1: CorrectionPlaced)
SHOWS = {"correction": "shows the correction", "said": "shows what was said (Show correction in /control)",
         "rewritten": "already states it correctly", "absent": "does not show it"}


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
        self.partial_engine = None  # F-013 S1b
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
        self.share = None  # display.share.ShareService (F-008)
        self.notes = None  # notes.service.NotesService (F-009)
        self.reference = None  # notes.reference.ReferenceIndex: the notes as study material (F-012)
        self.materials = None  # materials.service.MaterialsService (F-010)
        self.assess = None  # assess.service.AssessService: quiz + test (F-011)
        self._notes_loader: Optional[asyncio.Task] = None
        self.control_key = secrets.token_urlsafe(18)  # the teacher key for /control from outside this machine
        # performance mode (F-013): standard (fewer LLM calls) or high (every sentence); the teacher's last choice
        from copilot.app.modes import Preferences, mode_from_config

        self.prefs = Preferences(PROJECT_ROOT / config.get("app", "data_dir", "data") / "preferences.json",
                                 config.get("performance", "mode", "standard"))
        self.mode = mode_from_config(config, self.prefs.mode)

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
        from copilot.stt.factory import make_partial_engine
        partial = make_partial_engine(self.config)
        if partial is not None:  # F-013 S1b: live text while the teacher speaks; optional, never blocks the lecture
            try:
                took = await asyncio.to_thread(partial.load)
                self.partial_engine = partial
                print(f"[INIT]  live speech model {partial.cfg.model} ready ({took:.1f} s)", flush=True)
            except Exception as e:
                log.warning("live speech model %s not loaded (%s); slides follow finished sentences only",
                            partial.cfg.model, e)

    async def _load_notes_embedder(self) -> None:
        from copilot.understanding.embedder import MiniLmEmbedder

        u = self.config.section("understanding")
        embedder = MiniLmEmbedder(PROJECT_ROOT / u.get("embed_dir", "models/minilm"),
                                  u.get("embed_repo", "sentence-transformers/all-MiniLM-L6-v2"))
        try:
            await asyncio.to_thread(embedder.load)
        except Exception:  # the study material is not indexed; the notes still open
            log.exception("notes: embedder load failed")
            return
        if self.notes is not None:
            self.notes.set_embedder(embedder)
            await self.notes.announce()

    async def _init_understanding(self) -> None:
        import httpx

        from copilot.core.events import LLMCallFailed
        from copilot.llm.router import build_router
        from copilot.understanding.embedder import MiniLmEmbedder
        from copilot.understanding.interpreter import Interpreter
        from copilot.understanding.service import UnderstandingService, UnderstandingSettings, apply_pace

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
        if self.notes is not None and embedder is not None:
            # the notes are indexed as study material with the same model (0 tokens)
            self.notes.set_embedder(embedder)
            await self.notes.announce()

        async def on_failure(entry: str, error: str, will_retry: bool) -> None:
            await self.bus.publish(LLMCallFailed(provider=entry, error=error[:300], will_retry=will_retry))

        from copilot.llm.usage import UsageLedger

        self._http = httpx.AsyncClient()
        usage = UsageLedger(PROJECT_ROOT / self.config.get("llm", "usage_file", "data/llm_usage.json"))
        router = build_router(self.config, self._http, on_failure, usage)
        self._router = router
        if self.materials is not None:  # summary, key concepts, notes, assignment (F-010) use the same keys
            self.materials.writer.router = router
            await self.materials.announce()
        if self.assess is not None:  # quiz / test questions (F-011) are written by the same writer
            await self.assess.announce()
        names = [e.name for e in router.entries]
        print(f"[INIT]  LLM providers: {' -> '.join(names)}", flush=True)
        settings = UnderstandingSettings.from_config(self.config)
        apply_pace(settings, self.mode.pause_s, self.mode.min_call_interval_s)  # F-013 performance mode
        self.understanding = UnderstandingService(
            self.bus, self.store, Interpreter(router, settings.interpreter), embedder, settings,
            speed=self.speed if self.simulate or self.audio_file else 1.0,
        )
        self.understanding.reference = self.reference  # F-012: a matching passage of the study material
        self.understanding.attach()
        if not self.demo_slides:
            from copilot.presentation.engine import PresentationEngine, PresentationSettings

            settings = PresentationSettings.from_config(self.config)
            settings.simulations = self.prefs.simulations(settings.simulations)  # F-014 S1: the teacher's last choice
            self.presentation = PresentationEngine(
                self.bus, self.store, self.deck, settings,
                speed=self.speed if self.simulate or self.audio_file else 1.0,
                relevance=text_similarity(embedder) if embedder is not None else None,
            )
            self.presentation.attach()
            from copilot.simulation.detector import SimulationDetector

            self.sim_detector = SimulationDetector(self.bus)  # F-014: spoken cue -> RepresentationIntent (0 tokens)
            self.sim_detector.attach()
            if settings.scenes:  # F-015: "imagine a square ..." -> a live scene (one LLM call per cue / edit)
                from copilot.scene.compiler import SceneCompiler
                from copilot.scene.detector import SceneDetector

                self.scene_detector = SceneDetector(self.bus)
                self.scene_detector.attach()
                if self._router is not None:
                    self.presentation._scenes.compiler = SceneCompiler(self._router)
                from copilot.scene.assets import Pictures

                # a body's picture: icons by word, else by meaning (the concept embedder); glyphs cached here
                self.presentation._scenes.pictures = Pictures(embedder)
                if embedder is not None:  # the icons' vectors once, off the event loop (not on the first noun)
                    await asyncio.to_thread(self.presentation._scenes.pictures.warm)
                self.presentation._scenes.glyph_dir = PROJECT_ROOT / "data" / "assets" / "glyphs"
                # F-016: a thing's Fluent 3D picture, by word, else by meaning (1.6k names embedded in the background)
                from copilot.scene.pictures import Emoji

                self.presentation._scenes.emoji = Emoji(embedder)
                self.presentation._scenes.pics_dir = PROJECT_ROOT / "data" / "assets" / "pictures"
                if embedder is not None:
                    self._emoji_warm = asyncio.create_task(asyncio.to_thread(self.presentation._scenes.emoji.warm),
                                                           name="scene:emoji-warm")
                print(f"[INIT]  scenes: {'on' if self._router is not None else 'off (no LLM configured)'}", flush=True)
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
        self.images.reference = self.reference  # F-012: the teacher's own figures before the web
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
                      f"({c.get('confidence')}, {'correct it on the slide' if c.get('applied') else 'keep as said'})",
                      flush=True)
        elif isinstance(event, CorrectionPlaced):  # F-013 S3 (E1): what the slide really shows
            print(f"            slide: {SHOWS.get(event.shows, event.shows)}"
                  f"{f' ({event.elements} element(s))' if event.elements else ''}", flush=True)

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
        elif event.command.kind == "set_mode":
            await self._set_mode(str(event.command.args.get("mode", "")))
        elif event.command.kind == "set_simulations":
            await self._set_simulations(str(event.command.args.get("setting", "")))
        else:
            nxt = lifecycle_for_command(event.command.kind, self._now)
            if nxt is not None:
                await self._lifecycle(nxt, "teacher")
                print("[PAUSE] paused: what is said now is not put on slides (Resume to continue)"
                      if nxt == Lifecycle.PAUSED else "[LIVE]  resumed", flush=True)

    async def _set_mode(self, name: str) -> None:
        """The teacher's performance switch (F-013), before or during the lecture; kept for the next lecture."""
        from copilot.app.modes import MODES, mode_from_config
        from copilot.understanding.service import apply_pace

        if name not in MODES:
            log.warning("set_mode ignored: %r", name)
            return
        self.mode = mode_from_config(self.config, name)
        await asyncio.to_thread(self.prefs.set_mode, name)
        if self.understanding is not None:
            apply_pace(self.understanding.s, self.mode.pause_s, self.mode.min_call_interval_s)
        if self.speech is not None:
            self.speech.set_split(self.mode.split_sentences)
        await self.bus.publish(ModeChanged(mode=name))
        print(f"[MODE]  {self._mode_line()}", flush=True)

    async def _set_simulations(self, setting: str) -> None:
        """F-014 S1: Auto (a spoken cue shows a simulation) | Suggest (a /control chip) | Off; kept for the next lecture."""
        from copilot.simulation.policy import SETTINGS

        if setting not in SETTINGS:
            log.warning("set_simulations ignored: %r", setting)
            return
        await asyncio.to_thread(self.prefs.set_simulations, setting)
        if self.presentation is not None:
            self.presentation.s.simulations = setting
        await self.bus.publish(SimulationSettingChanged(setting=setting))  # type: ignore[arg-type]
        print(f"[SIM]   simulations: {setting}", flush=True)

    def _mode_line(self) -> str:
        m = self.mode
        return (f"{'high performance' if m.name == 'high' else 'standard'}: "
                f"{'every finished sentence' if m.split_sentences else 'each pause'} goes to the LLM "
                f"(pause {m.pause_s:g} s, calls >= {m.min_call_interval_s:g} s apart)")

    async def _start_display(self) -> None:
        from copilot.display.hub import DisplayHub
        from copilot.display.server import DisplayServer

        hub = DisplayHub(self.bus, theme=self.store.snapshot().setup.theme if self.store else "light")
        hub.attach()
        self.hub = hub
        from copilot.notes.library import NotesLibrary
        from copilot.notes.service import NotesService
        from copilot.visuals.service import cache_from_config

        # the teacher's PDF notes (F-009): on this laptop, shown only in /control
        library = NotesLibrary(PROJECT_ROOT / self.config.get("app", "data_dir", "data") / "notes")
        # ... which are also the lectures' study material (F-012): a local index, apart from the transcript
        from copilot.notes.reference import ReferenceIndex, load_vocab

        u = self.config.section("understanding")
        self.reference = ReferenceIndex(
            library, vocab=load_vocab(PROJECT_ROOT / u.get("embed_dir", "models/minilm") / "tokenizer.json"))
        self.notes = NotesService(self.bus, library, reference=self.reference)
        self.notes.attach()
        await self.notes.announce()
        # lecture materials + past lectures (F-010): made when the teacher asks, from this and / or past lectures
        from copilot.materials.archive import LectureArchive
        from copilot.materials.render import Renderer
        from copilot.materials.service import MaterialsService
        from copilot.materials.store import MaterialStore
        from copilot.materials.writer import Writer

        data = PROJECT_ROOT / self.config.get("app", "data_dir", "data")
        from copilot.materials.chapters import ChapterBook

        archive = LectureArchive(data / "sessions", data / "archive.json", current_id=self.session_id)
        store = MaterialStore(data / "materials")
        chapters = ChapterBook(data / "chapters.json")  # F-010b: lectures grouped in chapters
        # quiz + test (F-011): only when the teacher asks; students answer on the share link (the server's
        # student endpoints call it); its questions come from the materials service's lectures (below)
        from copilot.assess.generator import LectureQuestions
        from copilot.assess.service import AssessService
        from copilot.assess.store import AssessmentStore

        self.assess = AssessService(self.bus, AssessmentStore(data / "assessments"), self.session_id)
        self.server = DisplayServer(
            hub, self.config.get("display", "host", "127.0.0.1"), int(self.config.get("display", "port", 8765)),
            media=cache_from_config(self.config),
            upload_max_bytes=int(float(self.config.get("images", "upload_max_mb", 10)) * 1024 * 1024),
            control_key=self.control_key, notes=library, archive=archive, materials=store, chapters=chapters,
            assess=self.assess,
        )
        await self.server.start()
        self._server_started = asyncio.get_running_loop().time()
        self.materials = MaterialsService(self.bus, store, archive, self.deck, Writer(None),
                                          Renderer(f"http://127.0.0.1:{self.server.port}"), self.session_id,
                                          flush=self.event_log.flush, chapters=chapters,
                                          test_run=self.simulate is not None)
        self.materials.on_done = self._print_material
        self.materials.attach()
        await self.materials.announce()
        self.assess.source = LectureQuestions(self.materials, reference=self.reference)  # F-012: checks facts
        self.assess.on_generated = self._print_assess
        self.assess.attach()
        await self.assess.announce()
        from copilot.display.share import ShareService

        self.share = ShareService(
            self.bus, f"http://127.0.0.1:{self.server.port}",
            PROJECT_ROOT / self.config.get("app", "data_dir", "data") / "bin",
            configured=self.config.get("display", "cloudflared", ""),
            download_url=self.config.get("display", "cloudflared_url", ""),
            start_timeout_s=float(self.config.get("display", "share_start_timeout_s", 45.0)))
        self.share.attach()
        self.bus.subscribe("terminal_share", self._print_share, [ShareChanged])

    def _print_assess(self, a, spent) -> None:
        cost = f", {spent.calls} LLM call{'s' if spent.calls != 1 else ''}, {spent.tokens:,} tokens" if spent.calls else ""
        print(f"[{a.kind.upper()}] {len(a.questions)} questions ready{cost}" + (f" ({a.error})" if a.error else ""),
              flush=True)

    def _print_material(self, m) -> None:
        if m.status == "ready":
            cost = f", {m.calls} LLM call{'s' if m.calls != 1 else ''}, {m.tokens:,} tokens" if m.calls else ""
            print(f"[MATERIAL] {m.name} ready{cost}", flush=True)
        else:
            print(f"[MATERIAL] {m.name} failed: {m.detail}", flush=True)

    async def _print_share(self, event: Event) -> None:
        if not isinstance(event, ShareChanged):
            return
        if event.state == "on":
            base = event.url.removesuffix("/view")
            print(f"[SHARE] students: {event.url}", flush=True)
            print(f"        teacher control from another device: {base}/control?key={self.control_key}", flush=True)
        elif event.state == "failed":
            print(f"[SHARE] could not share: {event.detail}", flush=True)
        elif event.state == "off":
            print("[SHARE] stopped", flush=True)
        else:
            print(f"[SHARE] {event.detail} ...", flush=True)

    async def run(self) -> int:
        script = parse_script(self.simulate) if self.simulate else None
        self.store = LectureStateStore(self.bus, self.session_id, self._setup(script.setup if script else {}))
        self.store.attach()
        self.deck.attach()
        await self.event_log.open(self.bus)
        low = disk_warning(PROJECT_ROOT / self.config.get("app", "data_dir", "data"),
                           float(self.config.get("app", "min_free_gb", 1.0)))
        if low:  # F-013 S4 (G1): said at the start, not as a traceback at the end
            print(f"[DISK]  {low}", flush=True)
            log.warning(low)
        self.bus.subscribe("terminal_transcript", self._print_transcript,
                           [TranscriptFinal, UtteranceDropped, AudioDeviceLost])
        self.bus.subscribe("app_commands", self._on_command, [CommandReceived])
        self.bus.subscribe("terminal_understanding", self._print_understanding,
                           [InterpretationReady, ConcernRaised, CorrectionPlaced])
        self.bus.subscribe("terminal_slides", self._print_slide, [SlidePatch])
        await self._lifecycle(Lifecycle.STARTING)
        try:
            if self.display_enabled:
                await self._start_display()
            if script is None:
                await self._init_speech()
            if self.understanding_enabled:
                await self._init_understanding()
            elif self.notes is not None:  # no understanding: study material is still indexed (model in background)
                self._notes_loader = asyncio.create_task(self._load_notes_embedder())
            # Started only after every heavy import: on Windows a DLL import (numpy) can deadlock while another
            # thread is blocked reading a piped stdin (seen with tools/screenshot_app.py).
            TerminalInput(asyncio.get_running_loop(), self._terminal).start()
            await self.bus.publish(ModeChanged(mode=self.mode.name))  # F-013: /control shows the switch
            if self.presentation is not None:  # F-014 S1: and the simulation setting
                await self.bus.publish(SimulationSettingChanged(setting=self.presentation.s.simulations))  # type: ignore[arg-type]
            print(f"[MODE]  {self._mode_line()}  (switch in /control)", flush=True)
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

    async def _study_terms(self) -> list[str]:
        """Rare words of the study material in use, for Whisper (F-012; 0 tokens). Fixed when speech starts."""
        if self.reference is None:
            return []
        try:
            terms = await asyncio.to_thread(self.reference.terms)
        except Exception:  # the lecture is heard without them
            log.exception("study material terms failed")
            return []
        if terms:
            print(f"[INIT]  speech: {len(terms)} terms from your study material ({', '.join(terms[:6])} ...)",
                  flush=True)
        return terms

    async def _run_speech(self) -> None:
        from copilot.stt.factory import make_source, segmenter_config, vocabulary_prompt
        from copilot.stt.pipeline import SpeechPipeline

        assert self.engine is not None and self.store is not None
        source = make_source(self.config, self.audio_file, self.speed)
        study = await self._study_terms()
        if self.understanding is not None:
            self.understanding.study_terms(study)
        self.speech = SpeechPipeline(
            self.bus,
            source,
            self.engine,
            segmenter=segmenter_config(self.config),
            prompt=vocabulary_prompt(self.store.snapshot().setup, study),
            partial_engine=self.partial_engine,
            partial_interval_s=float(self.config.get("stt", "partial_interval_s", 0.8)),
            split_sentences=self.mode.split_sentences,
        )
        speech = self.speech

        async def on_vocabulary(e: VocabularyChanged) -> None:  # F-013 S3: Whisper hears the lecture's terms
            speech.set_prompt(vocabulary_prompt(self.store.snapshot().setup, e.terms))
            log.info("[STT] vocabulary prompt: %d terms (newest: %s)", len(e.terms), ", ".join(e.terms[-3:]))

        self.bus.subscribe("speech_vocabulary", on_vocabulary, [VocabularyChanged])
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
        if self._notes_loader is not None:
            self._notes_loader.cancel()
        if self.materials is not None:  # a PDF being written when the lecture ends is finished first
            if self.materials.busy:
                print("[END]   finishing the lecture materials being made ...", flush=True)
                if not await self.materials.wait_idle(MATERIALS_FINISH_S):
                    print("[END]   materials not finished; they show as interrupted", flush=True)
            await self.materials.close()
        if self.assess is not None:  # a running quiz / test is saved as it is
            await self.assess.close()
        if self.presentation is not None:
            await self.presentation.stop()
        if self.images is not None:
            await self.images.stop()
        if self.share is not None:
            await self.share.stop()  # the students' link closes with the lecture
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
    p.add_argument("--mode", choices=["standard", "high"], default=None,
                   help="performance mode for this run (default: the last one chosen in /control)")
    p.add_argument("--log-level", default=None)
    return p.parse_args(argv)


def quiet_peer_resets(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Loop exception handler. On Windows (Python 3.10 proactor) a browser that drops a kept-alive connection — the
    PDF / PPTX renderer's Edge closing (F-010), a student closing the tab — makes the transport raise
    ConnectionResetError while it closes a socket the peer already closed (seen 2026-10-07: 5 s after a PPTX, uvicorn's
    keep-alive timeout). Nothing is lost; only this case is quiet, every other loop error is reported as before."""
    exc = context.get("exception")
    if isinstance(exc, ConnectionResetError) and "_call_connection_lost" in repr(context.get("handle")):
        log.debug("a client reset its connection: %s", exc)
        return
    loop.default_exception_handler(context)


def main(argv: Optional[list[str]] = None) -> int:
    args = parse_args(argv)
    for stream in (sys.stdout, sys.stderr):  # LLM text can contain characters the console codepage lacks
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="replace")
    config = load_config()
    setup_logging(args.log_level or config.get("app", "log_level", "INFO"))
    speed = args.speed if args.speed is not None else config.get("sim", "speed", 1.0)

    async def _run() -> int:
        asyncio.get_running_loop().set_exception_handler(quiet_peer_resets)
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
        if args.mode:  # this run only; the /control switch is what is remembered
            from copilot.app.modes import mode_from_config
            app.mode = mode_from_config(config, args.mode)
        return await app.run()

    try:
        return asyncio.run(_run())
    except KeyboardInterrupt:
        print("\n[ENDED] interrupted", flush=True)
        return 130
