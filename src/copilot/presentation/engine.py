"""PresentationEngine: InterpretationReady + ConceptSignal + teacher commands → Deck (F-005).

Deterministic. Owns the planner state (working slide, dwell queue, corrections, new-topic candidate) and is the
only caller of Deck.add/update in a real lecture. Display flags (pin/freeze/blank/navigation) stay in the Deck.

Truthful projector: interpretations carry the corrected content. A concern says what the teacher actually said
(`wrong`) and what the slide shows instead (`right`). When the model is not confident enough the slide shows what
the teacher said; the teacher can switch either way from the control view.
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
from copilot.core.state import Concern, LectureStateStore
from copilot.presentation.composer import (
    BODY_BUDGET_PX, body_height, clear_provisional, describe, element_texts, fits, frame_slide, is_small, merge,
    remove_elements, revise_item,
    set_provisional, substitute, teacher_items, title_slide,
)
from copilot.presentation.content import Piece, clean, pieces_and_chain
from copilot.presentation.deck import Deck
from copilot.presentation.planner import Decision, Frame, Signal, Working, decide
from copilot.presentation.spec import SlideSpec

log = logging.getLogger(__name__)

TICK_S = 0.25
APPLY_WAIT_S = 5.0
MAX_SIGNALS = 300
MAX_CORRECTIONS = 100


@dataclass
class PresentationSettings:
    min_dwell_s: float = 15.0
    part_dwell_s: float = 6.0   # the next part of the same frame (the slide is full): a short wait is enough
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
class Correction:
    """Where a concern's words appear on the slides, and which version is shown."""
    concern_id: str
    targets: list[tuple[str, str]]  # (slide id, element id)
    wrong: str                      # as the teacher said it
    right: str                      # the correction
    showing_right: bool = True


@dataclass
class Tentative:
    """Content of a not-yet-confirmed new topic, shown on the current slide meanwhile; it moves to the new topic's
    slide once the topic is confirmed (so it does not stay on the previous topic's slide)."""
    topic: str
    elements: set[tuple[str, str]]  # (slide id, element id) on every slide the content reached
    pieces: list[Piece]


@dataclass
class EngineStats:
    ops: Counter = field(default_factory=Counter)
    slides: int = 0
    revisions: int = 0
    corrections_shown: int = 0
    shown_as_said: int = 0


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


def contains_words(text: str, words: str) -> bool:
    return bool(words) and re.search(rf"(?<![A-Za-z0-9]){re.escape(words)}(?![A-Za-z0-9])", text, re.IGNORECASE) \
        is not None


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
        self._about_chain: tuple[Optional[Frame], str] = (None, "")  # concept chain of the last unit, per frame
        self._signals: OrderedDict[str, Signal] = OrderedDict()
        self._corrections: OrderedDict[str, Correction] = OrderedDict()
        self._tentative: Optional[Tentative] = None
        self._placements: Optional[list[tuple[Piece, set[tuple[str, str]]]]] = None  # collected by _place
        self._prov: Optional[tuple[str, str, float]] = None  # (slide id, segment id, expires at)
        self._boundary_seg: Optional[str] = None  # a concept boundary not yet interpreted: the slide may change
        self._live_id: Optional[str] = None
        self._live_since = 0.0
        self._context: tuple[str, dict[str, str]] = ("", {})
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

    def _all_specs(self) -> list[SlideSpec]:
        return self.deck.slides + list(self._pending)

    def _elements(self) -> dict[tuple[str, str], str]:
        return {(s.id, eid): text for s in self._all_specs() for eid, text in element_texts(s).items()}

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
        nxt = self._meta.get(self._pending[0].id) if self._pending else None
        dwell = self.s.part_dwell_s if nxt is not None and nxt.frame.same(meta.frame) else self.s.min_dwell_s
        return self.now() - self._live_since >= dwell

    async def _add_to_deck(self, spec: SlideSpec) -> None:
        before = self.deck.live_id
        await self.deck.add(spec)
        self.stats.slides += 1
        if self.deck.live_id != before:
            self._live_id, self._live_since = self.deck.live_id, self.now()

    async def _open(self, spec: SlideSpec, meta: SlideMeta, exempt: bool = False, adopt: bool = True) -> None:
        self._meta[spec.id] = meta
        if not adopt:  # content for an earlier frame: into the deck without taking the screen
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
        ctx = describe(spec) if spec is not None and not self._meta[spec.id].is_title else ("", {})
        if ctx != self._context:
            self._context = ctx
            await self.bus.publish(SlideContextChanged(text=ctx[0], refs=ctx[1]))

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
        prev = self._spec(self._working_id)
        if meta is None or meta.is_title or prev is None:
            state = self.store.snapshot()
            topic = state.topic(state.current_topic_id)
            if topic is None:
                return
            sub = state.subtopic()
            frame = Frame(topic.title, sub.title if sub else topic.title)
            spec = frame_slide(frame.topic, frame.facet, continuation_of=self._working_id)
        else:
            frame = meta.frame
            spec = await self._next_part(prev, frame)
        await self._open(spec, SlideMeta(frame), exempt=True)
        self._working_id = spec.id

    async def _next_part(self, prev: SlideSpec, frame: Frame) -> SlideSpec:
        """The next slide of the same frame: same title, part badge I, II, III (never "(cont.)")."""
        part = self._last_part(frame, prev)
        if prev.part is None:
            numbered = prev.model_copy(update={"part": 1})
            await self._commit(numbered)
        nxt = frame_slide(frame.topic, frame.facet, continuation_of=prev.id)
        return nxt.model_copy(update={"title": prev.title, "part": part + 1})

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
        revised = await self._apply_revisions(ev)
        frame = Frame.of(it)
        carry = self._about_chain[1] if self._about_chain[0] == frame else ""
        pieces, chain = pieces_and_chain(it, carry)  # which concept each piece is about (concept columns)
        self._about_chain = (frame, chain)
        signals = [self._signals[x] for x in ev.segment_ids if x in self._signals]
        self._placements = []
        moved: list[Piece] = []
        removed: set[tuple[str, str]] = set()
        try:
            nav = self._navigated_back_to(Frame.of(it))
            if nav is not None:  # the teacher went back to the slide this content belongs to: update it there
                meta = self._meta[nav]
                spec = self._spec(nav)
                assert spec is not None
                self.stats.ops["update"] += 1
                await self._place(spec, False, meta.frame, pieces, adopt=False)
            else:
                working = self._working()
                d = decide(working, it, signals, self._candidate, has_pieces=bool(pieces),
                           shift_threshold=self.s.shift_threshold)
                self._candidate = d.candidate
                self.stats.ops[d.op] += 1
                log.info("planner: %s %s > %s (%s)", d.op, d.frame.topic, d.frame.facet, d.reason)
                tentative = self._tentative
                if d.op == "new" and tentative is not None and Frame(tentative.topic, "").same_topic(d.frame):
                    moved, removed = await self._take_back(tentative)  # the confirmed topic gets its earlier lines
                    pieces = moved + pieces
                if d.candidate is None or (tentative and not Frame(tentative.topic, "").same_topic(
                        Frame(d.candidate, ""))):
                    self._tentative = None
                if d.op != "noop":
                    await self._apply(d, working, pieces)
                    if d.candidate is not None:
                        placed = {k for _, ks in self._placements for k in ks}
                        if self._tentative is None:
                            self._tentative = Tentative(d.candidate, placed, list(pieces))
                        else:
                            self._tentative.elements |= placed
                            self._tentative.pieces += pieces
            placements = self._placements
        finally:
            self._placements = None
        if moved:
            await self._retarget_moved(moved, removed, placements)
        line_of = {sid: n for n, sid in enumerate(ev.segment_ids, start=1)}
        await self._track_corrections([c for c in snap.concerns if c.request_id == ev.request_id], line_of,
                                      [(p, ks) for p, ks in placements if not any(p is m for m in moved)], revised)

    async def _take_back(self, t: Tentative) -> tuple[list[Piece], set[tuple[str, str]]]:
        """Remove a confirmed topic's early items from the slides they were shown on; the caller places them on the
        new topic's slide."""
        self._tentative = None
        by_slide: dict[str, set[str]] = {}
        for sid, eid in t.elements:
            by_slide.setdefault(sid, set()).add(eid)
        for sid, ids in by_slide.items():
            spec = self._spec(sid)
            if spec is None:
                continue
            left = remove_elements(spec, ids)
            if left.blocks:
                await self._commit(left)
            else:  # nothing else was on it: no empty slide stays in the deck
                self._pending = [x for x in self._pending if x.id != sid]
                await self.deck.remove(sid)
                self._meta.pop(sid, None)
                if self._working_id == sid:
                    self._working_id = None
        log.info("moving %d item(s) of %r to the new topic's slide", len(t.elements), t.topic)
        return t.pieces, set(t.elements)

    async def _retarget_moved(self, moved: list[Piece], removed: set[tuple[str, str]],
                              placements: list[tuple[Piece, set[tuple[str, str]]]]) -> None:
        """Corrections that pointed at moved items follow them (and keep showing the version chosen)."""
        new_ids = {k for p, ks in placements if any(p is m for m in moved) for k in ks}
        texts = self._elements()
        for corr in self._corrections.values():
            if not removed & set(corr.targets):
                continue
            corr.targets = [k for k in new_ids if contains_words(texts.get(k, ""), corr.right)]
            if not corr.showing_right and corr.targets:  # moved items carry the corrected words again
                corr.showing_right = True
                await self._toggle(corr, show_right=False)

    async def _apply_revisions(self, ev: InterpretationReady) -> set[tuple[str, str]]:
        """Rewrite CURRENT SLIDE items the new lines completed or corrected (refs from the prompt's context)."""
        done: set[tuple[str, str]] = set()
        for r in ev.interpretation.revisions:
            target = ev.slide_refs.get(r.ref.strip().upper())
            text = clean(r.text)
            if not target or not text or "/" not in target:
                continue
            slide_id, item_id = target.split("/", 1)
            spec = self._spec(slide_id)
            new = revise_item(spec, item_id, text) if spec is not None else None
            if new is None:
                log.info("revision %s -> %s: item no longer on the slide", r.ref, target)
                continue
            await self._commit(new)
            done.add((slide_id, item_id))
            self.stats.revisions += 1
            log.info("revised %s: %s", r.ref, text)
        return done

    async def _track_corrections(self, concerns: list[Concern], line_of: dict[str, int],
                                 placements: list[tuple[Piece, set[tuple[str, str]]]],
                                 revised: set[tuple[str, str]]) -> None:
        """Find the elements each concern is about — those made from the concern's own transcript lines — and show
        the chosen version there: the correction when applied, otherwise what the teacher said. Word matching alone
        would hit unrelated items ("Jupiter is the largest planet" for a largest/smallest concern)."""
        texts = self._elements()
        all_new = {k for _, ks in placements for k in ks} | revised
        for c in concerns:
            if not (c.wrong and c.right):
                continue
            lines = {line_of[x] for x in c.segment_ids if x in line_of}
            own = {k for p, ks in placements if lines & set(p.lines) for k in ks}
            candidates = (own | revised) if own else all_new
            right_hits = [k for k in candidates if contains_words(texts.get(k, ""), c.right)]
            wrong_hits = [k for k in candidates if k not in right_hits and contains_words(texts.get(k, ""), c.wrong)]
            want_right = (c.applied and c.status != "kept") or c.status == "accepted"
            if right_hits:
                corr = Correction(c.id, right_hits, c.wrong, c.right, showing_right=True)
            elif wrong_hits:  # the model raised the correction but left the teacher's words in its items
                corr = Correction(c.id, wrong_hits, c.wrong, c.right, showing_right=False)
            else:
                corr = Correction(c.id, [], c.wrong, c.right, showing_right=want_right)
            self._corrections[c.id] = corr
            while len(self._corrections) > MAX_CORRECTIONS:
                self._corrections.popitem(last=False)
            if corr.targets:
                await self._toggle(corr, show_right=want_right)
                if corr.showing_right:
                    self.stats.corrections_shown += 1
            log.info("concern %s (%s, applied=%s): %d element(s); slide shows %r", c.id, c.kind, c.applied,
                     len(corr.targets), c.right if corr.showing_right else c.wrong)

    async def _toggle(self, corr: Correction, show_right: bool) -> None:
        if corr.showing_right == show_right:
            return
        old, new = (corr.wrong, corr.right) if show_right else (corr.right, corr.wrong)
        by_slide: dict[str, set[str]] = {}
        for sid, eid in corr.targets:
            by_slide.setdefault(sid, set()).add(eid)
        for sid, ids in by_slide.items():
            spec = self._spec(sid)
            if spec is not None:
                await self._commit(substitute(spec, ids, old, new))
        corr.showing_right = show_right
        if not show_right:
            self.stats.shown_as_said += 1

    async def _on_resolved(self, ev: ConcernResolved) -> None:
        corr = self._corrections.get(ev.concern_id)
        if corr is None:
            return
        if ev.status == "accepted":
            await self._toggle(corr, show_right=True)
        elif ev.status == "kept":
            await self._toggle(corr, show_right=False)
        log.info("concern %s %s: slide shows %r", ev.concern_id, ev.status,
                 corr.right if corr.showing_right else corr.wrong)

    async def _apply(self, d: Decision, working: Optional[Working], pieces: list[Piece]) -> Optional[str]:
        """Carry out a decision; returns the id of the slide the content went to."""
        frame = d.frame
        if d.op == "continue" and self._absorbs(pieces):
            # a sparse definition slide takes its supporting content (the branches of chemistry under its
            # definition) instead of a new, equally sparse slide replacing it seconds later
            spec = self._spec(self._working_id)
            assert spec is not None
            self._meta[spec.id].frame = frame
            log.info("supporting %s content stays on the sparse definition slide %r", frame.facet, spec.title)
            return await self._place(spec, False, frame, pieces)
        if d.op in ("new", "continue"):
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

    ABSORB_KINDS = ("tree", "groups", "facts", "points", "example")
    ABSORB_MAX_FILL = 0.45

    def _absorbs(self, pieces: list[Piece]) -> bool:
        """The working slide is just a definition with room to spare and the new facet is supporting content
        (no new definition, no big diagram) that fits completely."""
        spec = self._spec(self._working_id)
        if spec is None or not pieces or any(p.kind not in self.ABSORB_KINDS for p in pieces):
            return False
        if [b.type for b in spec.blocks] != ["definition"] or body_height(spec) > BODY_BUDGET_PX * self.ABSORB_MAX_FILL:
            return False
        trial = spec
        for p in pieces:
            trial, left = merge(trial, p)
            if left is not None:
                return False
        return fits(trial)

    def _navigated_back_to(self, frame: Frame) -> Optional[str]:
        """The slide the teacher navigated back to, if it shows this frame (and is not the working slide)."""
        live = self.deck.live_id
        if (live and live != self._working_id and not self.deck.following and live in self._meta
                and not self._meta[live].is_title and self._meta[live].frame.same(frame)):
            return live
        return None

    async def _place(self, spec: SlideSpec, is_new: bool, frame: Frame, pieces: list[Piece],
                     exempt: bool = False, adopt: bool = True) -> str:
        """Merge pieces into spec, opening the next part of the frame when the slide is full. adopt=False: content
        for another frame (navigated-back slide) never becomes the working slide nor takes the screen.
        Records which elements each piece produced (self._placements) for corrections and tentative moves."""
        cur, cur_new = spec, is_new
        for piece in pieces:
            ids_before = {(cur.id, e) for e in element_texts(cur)}
            finished: list[SlideSpec] = []
            full = (not cur_new) and self._meta.get(cur.id, SlideMeta(frame)).full
            cur, left = merge(cur, piece, full=full)
            if left is not None and not full and is_small(left):
                cur, left = merge(cur, left, squeeze=True)  # one short item: squeeze it in, no lonely next part
            while left is not None:
                nxt = frame_slide(frame.topic, frame.facet, continuation_of=cur.id)
                nxt = nxt.model_copy(update={"title": cur.title})
                nxt, rest = merge(nxt, left)
                if not nxt.blocks or rest == left:
                    log.error("piece does not fit an empty slide; dropped: %s", left.all_text()[:3])
                    break
                part = self._last_part(frame, cur) + 1  # numbered only once the next part really has content
                if cur.part is None:
                    cur = cur.model_copy(update={"part": 1})
                await self._finish(cur, cur_new, frame, exempt, adopt)
                finished.append(cur)
                exempt = False
                cur, cur_new = nxt.model_copy(update={"part": part}), True
                left = rest
            if self._placements is not None:
                produced = {(s.id, e) for s in finished + [cur] for e in element_texts(s)} - ids_before
                self._placements.append((piece, produced))
        await self._finish(cur, cur_new, frame, exempt, adopt)
        return cur.id

    def _last_part(self, frame: Frame, cur: SlideSpec) -> int:
        """Highest part number of this frame so far (a navigated-back part I must not create a second II)."""
        parts = [s.part or 1 for s in self._all_specs() if s.id in self._meta and self._meta[s.id].frame.same(frame)]
        return max(parts + [cur.part or 1])

    async def _finish(self, spec: SlideSpec, is_new: bool, frame: Frame, exempt: bool, adopt: bool = True) -> None:
        if is_new:
            if not spec.blocks:
                return
            await self._open(spec, SlideMeta(frame), exempt, adopt)
            if adopt:
                self._working_id = spec.id
        else:
            await self._commit(spec)
            if spec.id not in self._meta:
                self._meta[spec.id] = SlideMeta(frame)
