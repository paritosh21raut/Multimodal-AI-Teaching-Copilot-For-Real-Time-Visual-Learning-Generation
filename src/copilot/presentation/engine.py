"""PresentationEngine: InterpretationReady + ConceptSignal + teacher commands → Deck (F-005).

Deterministic. Owns the planner state (working slide, dwell queue, held content, new-topic candidate) and is the
only caller of Deck.add/update in a real lecture. Display flags (pin/freeze/blank/navigation) stay in the Deck.
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from typing import Callable, Optional

from copilot.core.bus import EventBus
from copilot.core.config import Config
from copilot.core.events import (
    CommandReceived,
    ConceptSignal,
    ConcernResolved,
    DeckState,
    Event,
    InterpretationReady,
    Lifecycle,
    LifecycleChanged,
    SlideContextChanged,
    SlideOverflow,
)
from copilot.core.state import LectureStateStore
from copilot.presentation.composer import (
    LAYOUT_FOR, clear_provisional, describe, frame_slide, merge, set_provisional, teacher_items, title_slide,
)
from copilot.presentation.content import Piece, pieces_from
from copilot.presentation.deck import Deck
from copilot.presentation.holds import ConcernInfo, HeldPiece, apply_known, replace_spoken, resolve, split  # noqa: F401
from copilot.presentation.planner import Decision, Frame, Signal, Working, decide
from copilot.presentation.spec import SlideSpec

log = logging.getLogger(__name__)

TICK_S = 0.25
APPLY_WAIT_S = 5.0
MAX_SIGNALS = 300
CONT_SUFFIX = " (cont.)"


@dataclass
class PresentationSettings:
    min_dwell_s: float = 15.0
    provisional: bool = True
    provisional_ttl_s: float = 20.0
    shift_threshold: float = 0.75
    title_slide: bool = True

    @classmethod
    def from_config(cls, config: Config) -> "PresentationSettings":
        p = config.section("presentation")
        s = cls(**{k: p[k] for k in cls.__dataclass_fields__ if k in p})
        u = config.section("understanding")
        if "shift_threshold" in u and "shift_threshold" not in p:
            s.shift_threshold = u["shift_threshold"]
        return s


@dataclass
class SlideMeta:
    frame: Frame
    is_title: bool = False
    full: bool = False  # the display reported overflow: nothing more is added


@dataclass
class HeldEntry:
    held: HeldPiece
    frame: Frame
    slide_id: Optional[str]  # where the content would have gone (None: no slide was opened for it)


@dataclass
class EngineStats:
    ops: Counter = field(default_factory=Counter)
    slides: int = 0
    held: int = 0
    released: int = 0
    dropped_added: int = 0


def provisional_text(keyphrases: list[str], max_phrases: int = 3) -> str:
    """Short keyword teaser from the tracker's keyphrases: multi-word phrases first, no repeated words."""
    chosen: list[str] = []
    used: set[str] = set()
    ordered = sorted(keyphrases, key=lambda k: -min(len(k.split()), 3))
    for k in ordered:
        words = k.lower().split()
        if len(set(words)) < len(words) or used & set(words):
            continue
        if len(words) == 1 and len(words[0]) < 6:
            continue
        chosen.append(k)
        used |= set(words)
        if len(chosen) == max_phrases:
            break
    return " · ".join(chosen)


KIND_SUFFIX = {"formula": ": the equation", "comparison": ": compared", "example": ": an example",
               "timeline": ": timeline", "causes": ": causes and effects", "definition": ": key terms"}


def continuation_title(frame_title: str, previous: SlideSpec, piece: Piece) -> str:
    """Same kind of content that did not fit → "(cont.)"; a different representation → a short suffix."""
    if LAYOUT_FOR[piece.kind] == previous.layout or piece.kind in ("points", "example"):
        return frame_title + CONT_SUFFIX
    suffix = KIND_SUFFIX.get(piece.kind, "")
    if suffix and frame_title.endswith("?"):  # "What is respiration?" -> "Respiration: compared"
        return (previous.subtitle or frame_title.rstrip("?")) + suffix
    return frame_title + suffix


class PresentationEngine:
    def __init__(self, bus: EventBus, store: LectureStateStore, deck: Deck,
                 settings: Optional[PresentationSettings] = None, *, speed: float = 1.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.bus = bus
        self.store = store
        self.deck = deck
        self.s = settings or PresentationSettings()
        self.speed = speed
        self.clock = clock
        self._t0 = clock()
        self.stats = EngineStats()
        self._lock = asyncio.Lock()
        self._meta: dict[str, SlideMeta] = {}
        self._pending: list[SlideSpec] = []      # planner slides waiting for the dwell time (not in the deck yet)
        self._working_id: Optional[str] = None
        self._candidate: Optional[str] = None
        self._signals: OrderedDict[str, Signal] = OrderedDict()
        self._held: list[HeldEntry] = []
        self._concerns: dict[str, ConcernInfo] = {}
        self._prov: Optional[tuple[str, str, float]] = None  # (slide id, segment id, expires at)
        self._boundary_seg: Optional[str] = None  # a concept boundary not yet interpreted: the slide may change
        self._live_id: Optional[str] = None
        self._live_since = 0.0
        self._context = ""
        self._tasks: list[asyncio.Task] = []

    # ---- wiring -------------------------------------------------------------------------------
    def attach(self) -> None:
        self.bus.subscribe("presentation", self._on_event, [
            InterpretationReady, ConceptSignal, CommandReceived, ConcernResolved, SlideOverflow,
            LifecycleChanged, DeckState,
        ])
        self._tasks = [asyncio.create_task(self._ticker(), name="presentation:ticker")]

    async def stop(self) -> None:
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        self._tasks = []

    async def flush_pending(self) -> None:
        """Lecture ending: put slides still waiting for the dwell time into the deck."""
        async with self._lock:
            while self._pending:
                await self._add_to_deck(self._pending.pop(0))

    def now(self) -> float:
        return (self.clock() - self._t0) * self.speed

    async def _on_event(self, event: Event) -> None:
        async with self._lock:
            if isinstance(event, InterpretationReady):
                await self._on_interpretation(event)
            elif isinstance(event, ConceptSignal):
                await self._on_signal(event)
            elif isinstance(event, ConcernResolved):
                await self._on_resolved(event)
            elif isinstance(event, CommandReceived):
                if event.command.kind == "force_new_slide":
                    await self._force_new()
            elif isinstance(event, SlideOverflow):
                meta = self._meta.get(event.slide_id)
                spec = self._spec(event.slide_id)
                stale = spec is not None and event.version and event.version != spec.version
                if meta is not None and not meta.full and not stale:
                    meta.full = True
                    log.info("slide %s overflows on the display; further content continues on a new slide",
                             event.slide_id)
            elif isinstance(event, DeckState):
                if event.live_id != self._live_id:
                    self._live_id, self._live_since = event.live_id, self.now()
            elif isinstance(event, LifecycleChanged) and event.state == Lifecycle.LIVE:
                await self._on_live()
            await self._publish_context()

    async def _ticker(self) -> None:
        while True:
            await asyncio.sleep(TICK_S)
            try:
                async with self._lock:
                    if self._pending and self._dwell_ok():
                        await self._add_to_deck(self._pending.pop(0))
                        await self._publish_context()
                    if self._prov and self.now() >= self._prov[2]:
                        await self._clear_provisional()
            except asyncio.CancelledError:
                raise
            except Exception:
                log.exception("presentation ticker failed")

    # ---- slide bookkeeping --------------------------------------------------------------------
    def _spec(self, slide_id: Optional[str]) -> Optional[SlideSpec]:
        if slide_id is None:
            return None
        for p in self._pending:
            if p.id == slide_id:
                return p
        try:
            return self.deck.get(slide_id)
        except KeyError:
            return None

    def _working(self) -> Optional[Working]:
        spec = self._spec(self._working_id)
        meta = self._meta.get(self._working_id or "")
        if spec is None or meta is None:
            return None
        return Working(meta.frame, teacher_items(spec) > 0, meta.is_title)

    def _dwell_ok(self) -> bool:
        live = self.deck.live
        if live is None or not self.deck.following or self.deck.pinned:
            return True  # nothing would be replaced on screen
        meta = self._meta.get(live.id)
        if meta is None or meta.is_title or teacher_items(live) == 0:
            return True
        return self.now() - self._live_since >= self.s.min_dwell_s

    async def _add_to_deck(self, spec: SlideSpec) -> None:
        before = self.deck.live_id
        await self.deck.add(spec)
        self.stats.slides += 1
        if self.deck.live_id != before:
            self._live_id, self._live_since = self.deck.live_id, self.now()

    async def _open(self, spec: SlideSpec, meta: SlideMeta, exempt: bool = False, adopt: bool = True) -> None:
        self._meta[spec.id] = meta
        if not adopt:  # content for an earlier frame (released late): into the deck without taking the screen
            await self.deck.add(spec, activate=False)
            self.stats.slides += 1
            return
        if not self._pending and (exempt or self._dwell_ok()):
            await self._add_to_deck(spec)
        else:
            log.info("slide %r waits for the min dwell time", spec.title)
            self._pending.append(spec)

    async def _commit(self, spec: SlideSpec) -> None:
        for i, p in enumerate(self._pending):
            if p.id == spec.id:
                self._pending[i] = spec
                return
        old = self._spec(spec.id)
        if old is not None and old.model_dump(exclude={"version"}) != spec.model_dump(exclude={"version"}):
            await self.deck.update(spec)

    async def _publish_context(self) -> None:
        spec = self._spec(self._working_id)
        text = describe(spec) if spec is not None and not self._meta[spec.id].is_title else ""
        if text != self._context:
            self._context = text
            await self.bus.publish(SlideContextChanged(text=text))

    # ---- lifecycle / commands -----------------------------------------------------------------
    async def _on_live(self) -> None:
        setup = self.store.snapshot().setup
        if not self.s.title_slide or not setup.expected_topic or self._meta:
            return
        sub = " · ".join(x for x in (setup.subject, f"Grade {setup.grade_level}" if setup.grade_level else "") if x)
        spec = title_slide(setup.expected_topic, sub)
        await self._open(spec, SlideMeta(Frame(setup.expected_topic, setup.expected_topic), is_title=True), True)
        self._working_id = spec.id
        self.stats.ops["title"] += 1

    async def _force_new(self) -> None:
        self.stats.ops["force_new"] += 1
        if self._pending:  # the teacher wants the next slide now
            while self._pending:
                await self._add_to_deck(self._pending.pop(0))
            return
        meta = self._meta.get(self._working_id or "")
        if meta is None:
            state = self.store.snapshot()
            topic = state.topic(state.current_topic_id)
            if topic is None:
                return
            sub = state.subtopic()
            frame = Frame(topic.title, sub.title if sub else topic.title)
        else:
            frame = meta.frame
        spec = frame_slide(frame.topic, frame.facet, continuation_of=self._working_id)
        await self._open(spec, SlideMeta(frame), exempt=True)
        self._working_id = spec.id

    # ---- fast path ----------------------------------------------------------------------------
    async def _on_signal(self, ev: ConceptSignal) -> None:
        self._signals[ev.segment_id] = Signal(ev.shift_score, ev.boundary)
        while len(self._signals) > MAX_SIGNALS:
            self._signals.popitem(last=False)
        if ev.boundary:
            self._boundary_seg = ev.segment_id
            if self._prov:
                await self._clear_provisional()
        if not self.s.provisional or self._boundary_seg is not None or self._pending:
            return
        live = self.deck.live
        meta = self._meta.get(live.id) if live is not None else None
        if live is None or meta is None or live.id != self._working_id or meta.is_title:
            return
        text = provisional_text(ev.keyphrases)
        if not text:
            return
        if self._prov and self._prov[0] != live.id:
            await self._clear_provisional()  # never leave a teaser behind on another slide
            live = self.deck.live
            assert live is not None
        new = set_provisional(live, text)
        if new is not None:
            await self._commit(new)
            self._prov = (live.id, ev.segment_id, self.now() + self.s.provisional_ttl_s)

    async def _clear_provisional(self) -> None:
        if self._prov is None:
            return
        spec = self._spec(self._prov[0])
        self._prov = None
        if spec is not None:
            await self._commit(clear_provisional(spec))

    # ---- refined path -------------------------------------------------------------------------
    async def _on_interpretation(self, ev: InterpretationReady) -> None:
        if not await self.store.wait_applied(ev.request_id, APPLY_WAIT_S):
            log.warning("state did not apply %s in time; concerns may be missing", ev.request_id)
        snap = self.store.snapshot()
        it = ev.interpretation
        if self._prov and self._prov[1] in ev.segment_ids:
            await self._clear_provisional()
        if self._boundary_seg in ev.segment_ids:
            self._boundary_seg = None
        pieces = pieces_from(it)
        line_of = {sid: n for n, sid in enumerate(ev.segment_ids, start=1)}
        mine = [c for c in snap.concerns if c.request_id == ev.request_id]
        infos = [ConcernInfo(c.id, c.kind, c.claim, c.suggested_correction,
                             frozenset(line_of[x] for x in c.segment_ids if x in line_of)) for c in mine]
        self._concerns.update({c.id: c for c in infos})
        shown, held = split(pieces, infos)
        statuses = {c.id: c.status for c in mine}  # a decision may already have been made (engine backlog)
        waiting: list[HeldPiece] = []
        for h in held:
            h2 = apply_known(h, self._concerns, statuses)
            if h2 is None:
                continue
            if h2.pending:
                waiting.append(h2)
            else:
                shown.append(h2.piece)
        signals = [self._signals[x] for x in ev.segment_ids if x in self._signals]
        nav = self._navigated_back_to(Frame.of(it))
        if nav is not None:  # the teacher went back to the slide this content belongs to: update it there
            meta = self._meta[nav]
            spec = self._spec(nav)
            assert spec is not None
            self.stats.ops["update"] += 1
            target = await self._place(spec, False, meta.frame, shown, adopt=False)
            self._hold(waiting, meta.frame, target)
            return
        working = self._working()
        d = decide(working, it, signals, self._candidate, has_pieces=bool(shown or waiting),
                   shift_threshold=self.s.shift_threshold)
        self._candidate = d.candidate
        self.stats.ops[d.op] += 1
        log.info("planner: %s %s > %s (%s)", d.op, d.frame.topic, d.frame.facet, d.reason)
        if d.op == "noop":
            return
        target_id = await self._apply(d, working, shown)
        if d.op == "new" and target_id is None:
            self._candidate = it.topic  # confirmed, but everything is held: the next unit opens the topic
        self._hold(waiting, d.frame, target_id)

    def _hold(self, held: list[HeldPiece], frame: Frame, slide_id: Optional[str]) -> None:
        for h in held:
            self._held.append(HeldEntry(h, frame, slide_id))
            self.stats.held += 1
            log.info("holding %s piece for concern(s) %s", h.piece.kind, sorted(h.pending))

    async def _apply(self, d: Decision, working: Optional[Working], pieces: list[Piece]) -> Optional[str]:
        """Carry out a decision; returns the id of the slide the content went to (for held content)."""
        frame = d.frame
        if d.op in ("new", "continue"):
            if not pieces:
                return None  # everything is held: no empty slide
            cont = self._working_id if d.op == "continue" else None
            spec = frame_slide(frame.topic, frame.facet, continuation_of=cont)
            return await self._place(spec, True, frame, pieces, exempt=working is None or working.is_title)
        if d.op == "retitle":
            spec = self._spec(self._working_id)
            assert spec is not None
            fresh = frame_slide(frame.topic, frame.facet)
            spec = spec.model_copy(update={"title": fresh.title, "subtitle": fresh.subtitle, "facet": fresh.facet})
            self._meta[spec.id].frame = frame
            return await self._place(spec, False, frame, pieces)
        spec = self._spec(self._working_id)
        assert spec is not None
        return await self._place(spec, False, self._meta[spec.id].frame, pieces)

    def _navigated_back_to(self, frame: Frame) -> Optional[str]:
        """The slide the teacher navigated back to, if it shows this frame (and is not the working slide)."""
        live = self.deck.live_id
        if (live and live != self._working_id and not self.deck.following and live in self._meta
                and not self._meta[live].is_title and self._meta[live].frame.same(frame)):
            return live
        return None

    async def _place(self, spec: SlideSpec, is_new: bool, frame: Frame, pieces: list[Piece],
                     exempt: bool = False, adopt: bool = True) -> str:
        """Merge pieces into spec, opening continuation slides as needed. adopt=False: content for another
        frame (late release, navigated-back slide) never becomes the working slide nor takes the screen."""
        cur, cur_new = spec, is_new
        for piece in pieces:
            full = (not cur_new) and self._meta.get(cur.id, SlideMeta(frame)).full
            cur, left = merge(cur, piece, full=full)
            while left is not None:
                await self._finish(cur, cur_new, frame, exempt, adopt)
                exempt = False
                nxt = frame_slide(frame.topic, frame.facet, continuation_of=cur.id)
                nxt = nxt.model_copy(update={"title": continuation_title(nxt.title, cur, left)})
                cur, cur_new = nxt, True
                cur, rest = merge(cur, left)
                if rest == left:
                    log.error("piece does not fit an empty slide; dropped: %s", left.all_text()[:3])
                    break
                left = rest
        await self._finish(cur, cur_new, frame, exempt, adopt)
        return cur.id

    async def _finish(self, spec: SlideSpec, is_new: bool, frame: Frame, exempt: bool, adopt: bool = True) -> None:
        if is_new:
            if not spec.blocks:
                return
            await self._open(spec, SlideMeta(frame), exempt, adopt)
            if adopt:
                self._working_id = spec.id
        else:
            await self._commit(spec)
            if spec.id != self._working_id and spec.id not in self._meta:
                self._meta[spec.id] = SlideMeta(frame)

    # ---- concerns -----------------------------------------------------------------------------
    async def _on_resolved(self, ev: ConcernResolved) -> None:
        info = self._concerns.pop(ev.concern_id, None)
        if info is None:
            return
        remaining: list[HeldEntry] = []
        for e in self._held:
            if ev.concern_id not in e.held.pending:
                remaining.append(e)
                continue
            piece = resolve(e.held.piece, info, ev.status)
            e.held.pending.discard(ev.concern_id)
            if piece is None:
                log.info("concern %s %s: held content not shown", ev.concern_id, ev.status)
                continue
            e.held.piece = piece
            if e.held.pending:
                remaining.append(e)  # still waits for another open concern
            else:
                await self._release(e)
        self._held = remaining

    async def _release(self, e: HeldEntry) -> None:
        self.stats.released += 1
        pieces = [e.held.piece]
        spec = self._spec(e.slide_id)
        if spec is None:
            working = self._working()
            if working is not None and working.frame.same(e.frame):
                spec = self._spec(self._working_id)
        if spec is not None:
            frame = self._meta[spec.id].frame if spec.id in self._meta else e.frame
            await self._place(spec, False, frame, pieces, adopt=spec.id == self._working_id)
            return
        working = self._working()
        if working is None or working.is_title:  # nothing on screen yet: this is the first content
            await self._place(frame_slide(e.frame.topic, e.frame.facet), True, e.frame, pieces, exempt=True)
        else:
            new = frame_slide(e.frame.topic, e.frame.facet, continuation_of=self._working_id)
            await self._place(new, True, e.frame, pieces, adopt=working.frame.same(e.frame))
