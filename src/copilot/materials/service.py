"""MaterialsService (F-010): the teacher's Create in /control → summary / key-concepts slides, notes and assignment
PDFs, the PPTX of the slides — from this lecture and / or past ones, one job at a time, any time.

Commands: materials_create {items: [{kind, name?, scope?, count?, theme?}], lectures: [past ids], current: bool},
materials_rename {id, name}, materials_share {id, on}, materials_remove {id}, materials_show {id}, lecture_hide {id}.
Every change → `MaterialsState` (control; the shared PDF list also goes to the students' pages).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, Optional

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, DeckState, Event, MaterialsState
from copilot.materials.archive import LectureArchive, LectureRecord, lecture_title
from copilot.materials.content import Lecture, lecture_content, topic_of
from copilot.materials.render import Renderer, assignment_html, notes_html
from copilot.materials.slides import key_concepts_slides, lecture_summary_slides, topic_summary_slide
from copilot.materials.store import EXT, Material, MaterialStore, joined_title
from copilot.materials.writer import DEFAULT_QUESTIONS, MAX_QUESTIONS, Concept, MaterialError, Usage, Writer
from copilot.presentation.deck import Deck
from copilot.presentation.spec import SlideSpec

log = logging.getLogger(__name__)

KINDS = ("summary", "concepts", "notes", "assignment", "pptx")
NEEDS_LLM = {"summary", "concepts", "notes", "assignment"}
COMMANDS = {"materials_create", "materials_rename", "materials_share", "materials_remove", "materials_show",
            "lecture_hide"}


class _Request:
    """One Create: its lectures are read once and the key concepts written once (notes + slide share them)."""

    def __init__(self, lectures: list[str], current: bool) -> None:
        self.lecture_ids = lectures
        self.current = current
        self.records: Optional[list[LectureRecord]] = None
        self.concepts: Optional[list[Concept]] = None


class MaterialsService:
    def __init__(self, bus: EventBus, store: MaterialStore, archive: LectureArchive, deck: Deck,
                 writer: Writer, renderer: Optional[Renderer], session_id: str,
                 flush: Optional[Callable[[], Awaitable[None]]] = None) -> None:
        self._bus = bus
        self.store = store
        self.archive = archive
        self.deck = deck
        self.writer = writer
        self.renderer = renderer
        self.session_id = session_id
        self._flush = flush
        self._queue: asyncio.Queue[tuple[Material, _Request]] = asyncio.Queue()
        self._worker: Optional[asyncio.Task] = None
        self._running: Optional[Material] = None
        self._title = ""
        self._lectures_changed = 0
        self.on_done: Optional[Callable[[Material], None]] = None  # terminal line (app)

    def attach(self) -> None:
        self._bus.subscribe("materials", self._on_event, [CommandReceived, DeckState])
        self._worker = asyncio.create_task(self._work(), name="materials:worker")

    @property
    def busy(self) -> bool:
        return self._running is not None or not self._queue.empty()

    async def wait_idle(self, timeout: float) -> bool:
        """True when every queued material was made (or failed) within `timeout` seconds."""
        loop = asyncio.get_running_loop()
        end = loop.time() + timeout
        while self.busy:
            if loop.time() >= end:
                return False
            await asyncio.sleep(0.2)
        return True

    async def close(self) -> None:
        if self._worker is not None:
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass

    # ---- state ------------------------------------------------------------------------------------------
    def current_title(self) -> str:
        return lecture_title([s.model_dump() for s in self.deck.slides]) if self.deck.slides else ""

    def state(self) -> MaterialsState:
        return MaterialsState(items=[m.public() for m in self.store.items()],
                              shared=[{"id": m.id, "name": m.name} for m in self.store.shared()],
                              current={"id": self.session_id, "title": self._title},
                              llm=self.writer.available, lectures_changed=self._lectures_changed)

    async def announce(self) -> None:
        await self._bus.publish(self.state())

    # ---- commands ---------------------------------------------------------------------------------------
    async def _on_event(self, event: Event) -> None:
        if isinstance(event, DeckState):
            title = self.current_title()
            if title != self._title:  # the name fields in /control start from it
                self._title = title
                await self.announce()
            return
        assert isinstance(event, CommandReceived)
        kind, args = event.command.kind, event.command.args
        if kind not in COMMANDS:
            return
        changed = False
        if kind == "materials_create":
            changed = self._create(args)
        elif kind == "materials_rename":
            changed = self.store.rename(str(args.get("id", "")), str(args.get("name", "")))
        elif kind == "materials_share":
            changed = self.store.share(str(args.get("id", "")), bool(args.get("on")))
        elif kind == "materials_remove":
            changed = self.store.remove(str(args.get("id", "")))
        elif kind == "materials_show":
            await self._show_again(str(args.get("id", "")))
        elif kind == "lecture_hide":
            lid = str(args.get("id", ""))
            if lid and lid != self.session_id:
                await asyncio.to_thread(self.archive.hide, lid)
                self._lectures_changed += 1
                changed = True
        if changed:
            await self.announce()
        elif kind != "materials_show":
            log.warning("%s ignored: %s", kind, args)

    def _create(self, args: dict[str, Any]) -> bool:
        items = [i for i in args.get("items") or [] if isinstance(i, dict) and i.get("kind") in KINDS]
        past = [str(x) for x in args.get("lectures") or [] if isinstance(x, str) and x != self.session_id]
        current = bool(args.get("current", True))
        if not items or (not past and not current):
            return False
        ids = ([self.session_id] if current else []) + list(dict.fromkeys(past))
        request = _Request(ids, current)
        titles = [self._title or "This lecture"] if current else []
        for lid in past:
            rec = self.archive.load(lid)
            titles.append(rec.title if rec else lid)
        title = joined_title(titles)
        for item in items:
            kind = item["kind"]
            options: dict[str, Any] = {}
            if kind == "summary":
                options["scope"] = "topic" if item.get("scope") == "topic" else "lecture"
            if kind == "assignment":
                try:
                    options["count"] = max(1, min(MAX_QUESTIONS, int(item.get("count") or DEFAULT_QUESTIONS)))
                except (TypeError, ValueError):
                    options["count"] = DEFAULT_QUESTIONS
            if kind == "pptx":
                options["theme"] = "dark" if item.get("theme") == "dark" else "light"
            m = self.store.new(kind, str(item.get("name") or ""), title, ids, options)
            m.detail = "waiting"
            self._queue.put_nowait((m, request))
        self.store.save()
        return True

    async def _show_again(self, material_id: str) -> None:
        m = self.store.get(material_id)
        if m is None or not m.slides:
            return
        live = [sid for sid in m.slide_ids if sid in {s.id for s in self.deck.slides}]
        if live:
            await self._bus.publish(CommandReceived(command=_goto(live[0])))
            return
        added = await self.deck.present([SlideSpec.model_validate({**s, "id": _fresh()}) for s in m.slides])
        m.slide_ids = [s.id for s in added]
        self.store.save()

    # ---- jobs -------------------------------------------------------------------------------------------
    async def _work(self) -> None:
        while True:
            m, request = await self._queue.get()
            self._running = m
            try:
                await self._run(m, request)
            except asyncio.CancelledError:
                self._fail(m, "interrupted (the app was closed)")
                self.store.save()
                raise
            except MaterialError as e:
                self._fail(m, str(e))
            except Exception as e:  # a bug must not stop the next job
                log.exception("material %s (%s) failed", m.id, m.kind)
                self._fail(m, f"unexpected error: {type(e).__name__}: {e}")
            finally:
                self._running = None
            self.store.save()
            await self.announce()
            if self.on_done is not None:
                self.on_done(m)

    def _fail(self, m: Material, reason: str) -> None:
        m.status, m.detail = "failed", reason[:300]
        log.warning("material %s (%s) failed: %s", m.name, m.kind, reason)

    async def _progress(self, m: Material, detail: str) -> None:
        m.detail = detail
        await self.announce()

    async def _records(self, request: _Request) -> list[LectureRecord]:
        if request.records is None:
            if request.current and self._flush is not None:
                await self._flush()  # the running lecture's latest slides are in its log
            out = []
            for lid in request.lecture_ids:
                rec = await asyncio.to_thread(self.archive.load, lid, lid != self.session_id)
                if rec is None:
                    raise MaterialError("this lecture has no slides yet" if lid == self.session_id
                                        else f"lecture {lid} not found")
                out.append(rec)
            request.records = out
        return request.records

    async def _lectures(self, request: _Request) -> list[Lecture]:
        return [lecture_content(r, n) for n, r in enumerate(await self._records(request), start=1)]

    async def _concepts(self, request: _Request, lectures: list[Lecture], usage: Usage) -> list[Concept]:
        if request.concepts is None:
            request.concepts = await self.writer.key_concepts(lectures, usage)
        return request.concepts

    async def _run(self, m: Material, request: _Request) -> None:
        if m.kind in NEEDS_LLM and not self.writer.available:
            raise MaterialError("needs the LLM, which is off in this run (started with --no-understanding)")
        if m.kind in EXT and self.renderer is None:
            raise MaterialError("files need the display server")
        await self._progress(m, "reading the lecture")
        lectures = await self._lectures(request)
        usage = Usage()
        if m.kind == "summary":
            await self._progress(m, "writing the summary")
            if m.options.get("scope") == "topic":
                if not request.current:
                    raise MaterialError("a topic summary is about this lecture: include it")
                live = self.deck.live
                topic = topic_of(lectures[0], live.model_dump() if live else None)
                if topic is None:
                    raise MaterialError("no topic taught yet")
                points = await self.writer.topic_summary(lectures[0], topic, usage)
                specs = [topic_summary_slide(topic.name, points)]
            else:
                topics = await self.writer.lecture_summary(lectures, usage)
                specs = lecture_summary_slides(m.title, topics)
            await self._present(m, specs)
        elif m.kind == "concepts":
            await self._progress(m, "finding the key concepts")
            concepts = await self._concepts(request, lectures, usage)
            if not concepts:
                raise MaterialError("no key concepts found")
            await self._present(m, key_concepts_slides(m.title, concepts))
        elif m.kind == "notes":
            def step(n: int, total: int) -> None:
                m.detail = f"writing the notes ({n + 1} of {total})" if total > 1 else "writing the notes"
                asyncio.get_running_loop().create_task(self.announce())
            sections = await self.writer.note_sections(lectures, usage, step)
            await self._progress(m, "key concepts")
            concepts = await self._concepts(request, lectures, usage)
            await self._progress(m, "making the PDF")
            assert self.renderer is not None
            await self.renderer.pdf(notes_html(m.title, lectures, sections, concepts), self.store.file_for(m),
                                    f"{m.title} · Study notes")
            m.count = sum(len(l.subtopics) for l in lectures)
            m.shared = True
        elif m.kind == "assignment":
            count = int(m.options.get("count") or DEFAULT_QUESTIONS)
            await self._progress(m, f"writing {count} questions")
            questions = await self.writer.questions(lectures, count, usage)
            await self._progress(m, "making the PDF")
            assert self.renderer is not None
            await self.renderer.pdf(assignment_html(m.title, lectures, questions), self.store.file_for(m),
                                    f"{m.title} · Assignment")
            m.count = len(questions)
            m.shared = True
            if len(questions) < count:
                m.detail = f"{len(questions)} of {count} questions"
        elif m.kind == "pptx":
            records = await self._records(request)
            slides = [s for r in records for s in r.slides]
            if not slides:
                raise MaterialError("no slides yet")
            await self._progress(m, f"drawing {len(slides)} slides")
            assert self.renderer is not None
            m.count = await self.renderer.pptx(slides, m.options.get("theme", "light"), self.store.file_for(m),
                                               m.title)
        m.tokens, m.calls = usage.tokens, usage.calls
        m.status = "ready"
        if m.detail in ("", "waiting") or m.detail.startswith(("reading", "writing", "making", "drawing", "key",
                                                               "finding")):
            m.detail = ""
        log.info("material ready: %s (%s, %d LLM calls, %d tokens)", m.name, m.kind, m.calls, m.tokens)

    async def _present(self, m: Material, specs: list[SlideSpec]) -> None:
        m.slides = [s.model_dump() for s in specs]
        added = await self.deck.present(specs)
        m.slide_ids = [s.id for s in added]
        m.count = len(added)


def _goto(slide_id: str):
    from copilot.core.events import Command

    return Command(kind="goto", args={"slide_id": slide_id}, origin="system")


def _fresh() -> str:
    from copilot.core.events import new_id

    return new_id()
