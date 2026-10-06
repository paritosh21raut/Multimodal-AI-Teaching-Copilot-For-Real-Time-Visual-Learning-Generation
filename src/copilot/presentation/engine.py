"""PresentationEngine: InterpretationReady + ConceptSignal + teacher commands → Deck (F-005).

Deterministic. Owns the planner state (working slide, dwell queue, corrections, new-topic candidate) and is the
only caller of Deck.add/update in a real lecture. Display flags (pin/blank/navigation) stay in the Deck.

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
    ImageChoices,
    ImageReady,
    ImageRequested,
    InterpretationReady,
    Lifecycle,
    LifecycleChanged,
    SlideContextChanged,
    SlideOverflow,
    new_id,
)
from copilot.core.state import Concern, LectureStateStore
from copilot.presentation.composer import (
    BODY_BUDGET_PX, TERM_SUFFIX, add_point, body_height, clear_provisional, continue_numbering, describe, edit_text,
    element_texts, fits,
    fits_unshrunk, frame_slide, image_of, is_about, is_duplicate, is_small, member_of, merge, rejoin, remove_elements,
    revise_item, set_provisional, split_to_fit, substitute, teacher_items, title_slide, with_image, without_image,
)
from copilot.presentation.content import Piece, clean, pieces_and_chain
from copilot.presentation.deck import Deck
from copilot.presentation.planner import Decision, Frame, Signal, Working, decide
from copilot.presentation.spec import ImageBlock, SlideSpec
from copilot.visuals.policy import FrameVisual, blocked, names_a_thing, norm_query, sibling_hint
from copilot.visuals.policy import decide as image_decision

log = logging.getLogger(__name__)

TICK_S = 0.25
APPLY_WAIT_S = 5.0
MAX_SIGNALS = 300
MAX_CORRECTIONS = 100
IMAGE_RETRY_S = 60.0  # lecture seconds before a failed image search (network, timeout) is tried again
# An automatic image must be about the slide it goes on: query vs slide text (MiniLM cosine). Live test 2026-10-06
# put "human digestive system diagram" on the quadratic-equation slide (0.07); the weakest right pairing recorded
# so far is 0.33 (stomata diagram / photosynthesis process slide). Only clearly unrelated images are stopped.
IMAGE_MIN_RELEVANCE = 0.25
MAX_EDIT_CHARS = 300  # one edited / added element (F-008)


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
    full: bool = False  # the display reported overflow: nothing more is added ...
    full_items: int = 0  # ... while the slide holds at least as many items as then (it may have shrunk since)
    member: str = ""     # the slide of one member of the frame's set, explained in depth (titled by it, no part)


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
                 clock: Callable[[], float] = time.monotonic,
                 relevance: Optional[Callable[[str, str], float]] = None) -> None:
        self.bus = bus
        self.store = store
        self.deck = deck
        self.s = settings or PresentationSettings()
        self.speed = speed
        self.clock = clock
        self.relevance = relevance  # (image query, slide text) -> similarity; None: no check (embedder missing)
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
        self._visuals: list[tuple[Frame, FrameVisual]] = []      # per frame: its image, candidates, teacher choices
        self._image_requests: dict[str, tuple[str, str]] = {}   # request id -> (slide id, reason)
        self._image_history: dict[str, tuple[list[ImageBlock], int]] = {}  # slide id -> (images it showed, current)
        self._tails: dict[str, tuple[str, list]] = {}  # slide id -> (next part, blocks moved there for an image)
        # the teacher's edits are final (F-008): the elements the teacher wrote (ids are unique across slides, so they
        # stay the teacher's when a block moves to another part), slides whose title the teacher wrote, and per slide
        # the texts the teacher deleted or replaced (they do not come back there)
        self._teacher: set[str] = set()
        self._teacher_titles: set[str] = set()
        self._dismissed: dict[str, list[str]] = {}

    # ---- wiring -------------------------------------------------------------------------------
    def attach(self) -> None:
        self.bus.subscribe("presentation", self._on_event, [
            InterpretationReady, ConceptSignal, CommandReceived, ConcernResolved, SlideOverflow,
            LifecycleChanged, DeckState, ImageReady,
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
                elif event.command.kind in ("remove_image", "change_image", "set_image", "image_prev", "image_next"):
                    await self._on_image_command(event.command.kind, event.command.args)
                elif event.command.kind in ("edit_text", "delete_item", "add_point"):
                    await self._on_edit(event.command.kind, event.command.args)
            elif isinstance(event, ImageReady):
                await self._on_image_ready(event)
            elif isinstance(event, SlideOverflow):
                meta = self._meta.get(event.slide_id)
                spec = self._spec(event.slide_id)
                stale = spec is not None and event.version and event.version != spec.version
                if meta is not None and not meta.full and not stale:
                    meta.full, meta.full_items = True, teacher_items(spec) if spec is not None else 0
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
        if live is None or not self.deck.following:
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
        spec = self._without_dismissed(spec)
        for i, p in enumerate(self._pending):
            if p.id == spec.id:
                self._pending[i] = spec
                return
        old = self._spec(spec.id)
        if old is not None and old.model_dump(exclude={"version"}) != spec.model_dump(exclude={"version"}):
            await self.deck.update(spec)

    # ---- the teacher's edits (F-008) --------------------------------------------------------------------
    def _locked(self) -> set[str]:
        """Element ids the system must not change (a card's term edit locks the whole card)."""
        return {x.removesuffix(TERM_SUFFIX) for x in self._teacher}

    def _without_dismissed(self, spec: SlideSpec) -> SlideSpec:
        """New content repeating what the teacher deleted or replaced on this slide is left out."""
        gone = self._dismissed.get(spec.id)
        if not gone:
            return spec
        old = self._spec(spec.id)
        before = set(element_texts(old)) if old is not None else set()
        mine = self._locked()
        drop = {eid for eid, text in element_texts(spec).items()
                if eid not in before and eid not in mine and any(is_duplicate(text, g) for g in gone)}
        if drop:
            log.info("left out on %r (the teacher deleted or replaced it): %s", spec.title,
                     [element_texts(spec)[e] for e in drop])
            spec = remove_elements(spec, drop)
        return spec

    async def _on_edit(self, kind: str, args: dict) -> None:
        """The teacher's edit, final: the element is the teacher's from now on (revisions, correction switches,
        moves and retitles leave it alone) and the text it replaced or deleted does not come back on this slide."""
        slide_id = args.get("slide_id")
        spec = self._spec(slide_id) if isinstance(slide_id, str) else None
        if spec is None:
            log.warning("%s: unknown slide %r", kind, slide_id)
            return
        item_id = str(args.get("item_id") or "")
        text = clean(str(args.get("text") or ""), MAX_EDIT_CHARS)
        texts = element_texts(spec)
        gone = self._dismissed.setdefault(spec.id, [])
        if kind == "add_point":
            if not text:
                return
            new, item_id = add_point(spec, text)
            self._teacher.add(item_id)
        elif kind == "delete_item":
            if item_id not in texts:
                log.warning("delete_item: %r is not on %r", item_id, spec.title)
                return
            gone.append(texts[item_id])
            new = remove_elements(spec, {item_id})
        elif item_id == "title":
            if not text:
                return
            new = spec.model_copy(update={"title": text})  # the slide always shows its title (slide.js shownTitle)
            self._teacher_titles.add(spec.id)
        else:
            new = edit_text(spec, item_id, text) if text else None
            if new is None:
                log.warning("edit_text: %r is not an editable element of %r", item_id, spec.title)
                return
            old = texts.get(item_id, "")  # a term edit replaces no content
            if old and not is_duplicate(old, text):
                gone.append(old)
            self._teacher.add(item_id)
        self.stats.ops["teacher_" + kind] += 1
        log.info("teacher %s on %r: %s %r", kind, spec.title, item_id, text)
        await self._commit(new)

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
        nav: Optional[str] = None
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
                    await self._apply(d, working, pieces, it.relation)
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
        if it.visual is not None:  # remembered per frame: a new topic's first unit may still wait on the old slide
            self._fv(Frame.of(it)).hint = it.visual
        if nav is None and self._working_id and (placements or it.visual is not None):
            await self._consider_image(self._working_id)

    async def _take_back(self, t: Tentative) -> tuple[list[Piece], set[tuple[str, str]]]:
        """Remove a confirmed topic's early items from the slides they were shown on; the caller places them on the
        new topic's slide."""
        self._tentative = None
        by_slide: dict[str, set[str]] = {}
        for sid, eid in t.elements:
            by_slide.setdefault(sid, set()).add(eid)
        for sid, ids in by_slide.items():
            spec = self._spec(sid)
            ids = ids - self._locked()  # what the teacher edited stays where the teacher edited it
            if spec is None or not ids:
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
            if item_id in self._locked():
                log.info("revision %s -> %s: the teacher's text stays", r.ref, target)
                continue
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
            ids = ids - self._locked()  # the teacher's own text is never switched
            if spec is not None and ids:
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

    async def _apply(self, d: Decision, working: Optional[Working], pieces: list[Piece],
                     relation: str = "") -> Optional[str]:
        """Carry out a decision; returns the id of the slide the content went to."""
        frame = d.frame
        # a narrower concept with a name of its own (the female reproductive system) is no supporting content: it
        # gets its own slide like its siblings (live test 2026-10-06: female stayed on the definition, male did not)
        own = relation == "sub_concept" and names_a_thing(frame.facet)
        if d.op == "continue" and not own and self._absorbs(pieces):
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
            title = spec.title if spec.id in self._teacher_titles else fresh.title  # the teacher's title stays
            spec = spec.model_copy(update={"title": title, "subtitle": fresh.subtitle, "facet": fresh.facet})
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
        cur_member = self._meta[cur.id].member if cur.id in self._meta else ""
        for piece in pieces:
            ids_before = {(cur.id, e) for e in element_texts(cur)}
            finished: list[SlideSpec] = []
            if cur_member and not is_about(piece, cur_member):
                # the teacher is back at the set after one member in depth: the set continues on its next part
                await self._finish(cur, cur_new, frame, exempt, adopt, cur_member)
                finished.append(cur)
                exempt = False
                cur, cur_new, cur_member = await self._set_part(frame, cur), True, ""
            m = self._meta.get(cur.id, SlideMeta(frame))
            # overflow applies to the slide as reported: after a revision made it smaller (live test 2026-10-06:
            # 7 items reported, then 6) new content may join it again instead of opening a lonely next part
            full = (not cur_new) and m.full and teacher_items(cur) >= m.full_items
            before = cur
            cur, left = merge(cur, piece, full=full)
            if cur is not before and (cur.part or 1) > 1:  # e.g. steps on a part the teacher opened (New slide)
                prev = self._part_before(frame, cur)
                cur = continue_numbering(prev, cur) if prev is not None else cur
            if left is not None and image_of(before) is not None and teacher_items(before) > 0:
                # beside an image the type may shrink to take a piece; when even that is not enough the slide
                # stays as it was and the whole piece opens the next part (user 2026-10-06)
                cur, left = before, piece
            elif left is not None and not full and is_small(left):
                cur, left = merge(cur, left, squeeze=True)  # one short item: squeeze it in, no lonely next part
            while left is not None:
                # details of one member that no longer fit its card: that member is explained in depth and gets its
                # own slide, titled by it, under the same crumb (Topic — Types); the set continues afterwards
                member = member_of(cur, left) if not cur_member else None
                nxt_member = cur_member or (member.term if member is not None else "")
                nxt = frame_slide(frame.topic, frame.facet, continuation_of=cur.id)
                nxt = nxt.model_copy(update={"title": member.term if member is not None else cur.title})
                nxt, rest = merge(nxt, left)
                nxt = continue_numbering(cur, nxt)
                if not nxt.blocks or rest == left:
                    log.error("piece does not fit an empty slide; dropped: %s", left.all_text()[:3])
                    break
                # a member's slides are not parts of the set; the set's parts are numbered once the next has content
                part = None if nxt_member else self._last_part(frame, cur) + 1
                if cur.part is None and not nxt_member:
                    cur = cur.model_copy(update={"part": 1})
                await self._finish(cur, cur_new, frame, exempt, adopt, cur_member)
                finished.append(cur)
                exempt = False
                if member is not None:
                    log.info("member %r explained in depth: its own slide under %s > %s", member.term, frame.topic,
                             frame.facet)
                cur, cur_new, cur_member = nxt.model_copy(update={"part": part}), True, nxt_member
                left = rest
            if self._placements is not None:
                produced = {(s.id, e) for s in finished + [cur] for e in element_texts(s)} - ids_before
                self._placements.append((piece, produced))
        await self._finish(cur, cur_new, frame, exempt, adopt, cur_member)
        return cur.id

    async def _set_part(self, frame: Frame, cur: SlideSpec) -> SlideSpec:
        """An empty next part of a frame's set (after a member's own slide): the set's title, the next part number."""
        first = self._first_part(frame, cur)
        await self._number_first_part(frame, cur)
        nxt = frame_slide(frame.topic, frame.facet, continuation_of=cur.id)
        return nxt.model_copy(update={"title": first.title if first is not None else nxt.title,
                                      "part": self._last_part(frame, cur) + 1})

    def _run(self, frame: Frame, cur: SlideSpec) -> list[SlideSpec]:
        """The frame's slides in one unbroken stretch of the deck around `cur` (a new slide: around the slide it
        continues). Parts count within it: the teacher back at Covalent Bond after Dipole Moment starts again at I
        (long test 2026-10-06 showed I, then V)."""
        specs = self._all_specs()
        at = {s.id: i for i, s in enumerate(specs)}
        anchor = cur.id if cur.id in at else cur.continuation_of
        if anchor not in at:
            return []
        same = lambda s: s.id in self._meta and self._meta[s.id].frame.same(frame)  # noqa: E731
        lo = hi = at[anchor]
        if not same(specs[lo]):
            return []
        while lo > 0 and same(specs[lo - 1]):
            lo -= 1
        while hi + 1 < len(specs) and same(specs[hi + 1]):
            hi += 1
        return specs[lo:hi + 1]

    def _first_part(self, frame: Frame, cur: SlideSpec) -> Optional[SlideSpec]:
        return next((s for s in self._run(frame, cur) if not self._meta[s.id].member
                     and not self._meta[s.id].is_title), None)

    async def _number_first_part(self, frame: Frame, cur: SlideSpec) -> None:
        first = self._first_part(frame, cur)
        if first is not None and first.part is None:
            await self._commit(first.model_copy(update={"part": 1}))

    def _part_before(self, frame: Frame, cur: SlideSpec) -> Optional[SlideSpec]:
        """The frame's part right before `cur` (part II → part I), or None."""
        want = (cur.part or 1) - 1
        return next((s for s in self._run(frame, cur) if s.id != cur.id and not self._meta[s.id].member
                     and not self._meta[s.id].is_title and (s.part or 1) == want), None) if want >= 1 else None

    def _last_part(self, frame: Frame, cur: SlideSpec) -> int:
        """Highest part number in the frame's current run (a navigated-back part I must not create a second II)."""
        parts = [s.part or 1 for s in self._run(frame, cur) if not self._meta[s.id].member]  # a member's own slide
        return max(parts + [cur.part or 1])                                                  # is no part of the set

    async def _finish(self, spec: SlideSpec, is_new: bool, frame: Frame, exempt: bool, adopt: bool = True,
                      member: str = "") -> None:
        if is_new:
            if not spec.blocks:
                return
            await self._open(spec, SlideMeta(frame, member=member), exempt, adopt)
            if adopt:
                self._working_id = spec.id
        else:
            await self._commit(spec)
            if spec.id not in self._meta:
                self._meta[spec.id] = SlideMeta(frame)

    # ---- images (F-007b) ----------------------------------------------------------------------------
    def _fv(self, frame: Frame) -> FrameVisual:
        for f, v in self._visuals:
            if f.same(frame):
                return v
        v = FrameVisual()
        self._visuals.append((frame, v))
        return v

    async def _consider_image(self, slide_id: str) -> None:
        """After content reached a slide: the policy decides whether it gets an image (search / keep / none), with
        the model's latest hint for the slide's frame."""
        spec, meta = self._spec(slide_id), self._meta.get(slide_id)
        if spec is None or meta is None or meta.is_title:
            return
        fv = self._fv(meta.frame)
        img = image_of(spec)
        if img is not None and img.origin == "auto" and blocked(spec):
            # a full-width diagram (process, comparison, formula ...) arrived: the automatic image yields to it
            await self._commit(without_image(spec))
            log.info("image removed from %r: %s", spec.title, blocked(spec))
            return
        hint = fv.hint
        if hint is None and fv.image is None and not fv.removed:
            hint = sibling_hint(meta.frame.facet, [(f.facet, v.hint) for f, v in self._visuals
                                                   if v.hint is not None and f.same_topic(meta.frame)
                                                   and not f.same(meta.frame)])
            if hint is not None:
                log.info("image hint %r for %r from its sibling subtopic", hint.query, spec.title)
        d = image_decision(spec, hint, fv)
        if d.action == "keep" and fv.image is not None:
            if await self._about(fv.query, spec) and await self._show_image(spec, fv.image, teacher=False):
                log.info("image %r kept on %r (%s)", fv.query, spec.title, d.reason)
        elif d.action == "search":
            if self.now() < fv.retry_at:
                return  # the last search failed (network, timeout): not again on every unit
            if not await self._about(d.query, spec):
                return
            fv.pending = d.query
            await self._request_image(spec.id, d.query, d.kind, fv, "auto")
            log.info("image search %r (%s) for %r", d.query, d.kind, spec.title)
        elif hint is not None:
            log.info("no image for %r: %s", spec.title, d.reason)

    async def _about(self, query: str, spec: SlideSpec) -> bool:
        """Is an automatic image for `query` about this slide's content? (meaning, not shared words)"""
        if self.relevance is None:
            return True
        text = ". ".join([spec.title, *element_texts(spec).values()])
        try:
            sim = await asyncio.to_thread(self.relevance, query, text)
        except Exception:  # the check must never stop the lecture; without it the image is not shown
            log.exception("image relevance check failed for %r", query)
            return False
        if sim < IMAGE_MIN_RELEVANCE:
            log.info("no image %r on %r: not about the slide (similarity %.2f)", query, spec.title, sim)
            return False
        return True

    async def _request_image(self, slide_id: str, query: str, kind: str, fv: FrameVisual, reason: str,
                             deeper: bool = False) -> None:
        rid = new_id()
        self._image_requests[rid] = (slide_id, reason)
        await self.bus.publish(ImageRequested(request_id=rid, slide_id=slide_id, query=query,
                                              kind=kind if kind in ("photo", "diagram") else "photo",
                                              exclude=sorted(fv.shown_ids), deeper=deeper, reason=reason))

    async def _show_image(self, spec: SlideSpec, image: ImageBlock, teacher: bool, remember: bool = True) -> bool:
        """Put the image on the slide. Automatic: only when the content still fits at the default type size.
        The teacher's choice: the type may shrink; if even that is not enough, the last content moves to the next
        part (the image never shrinks the content out of sight). Every image shown joins the slide's history
        (the teacher's previous / next arrows) unless it is a step through that history."""
        new = with_image(spec, image.model_copy(update={"id": new_id()}))
        if not teacher and not fits_unshrunk(new):
            log.info("no room for an image on %r", spec.title)
            return False
        moved: list = []
        if teacher and not fits(new):
            new, moved = split_to_fit(new)
        await self._commit(new)
        if moved:
            await self._open_tail(new, moved)
        if remember:
            await self._remember_image(spec.id, image)
        return True

    async def _remember_image(self, slide_id: str, image: ImageBlock) -> None:
        images, _ = self._image_history.get(slide_id, ([], -1))
        at = next((i for i, b in enumerate(images) if b.image_id == image.image_id), None)
        if at is None:  # a new image goes to the end, also after the teacher stepped back (nothing is lost)
            images, at = images + [image], len(images)
        self._image_history[slide_id] = (images, at)
        await self.bus.publish(ImageChoices(slide_id=slide_id, index=at, count=len(images)))

    async def _step_image(self, spec: SlideSpec, fv: FrameVisual, step: int) -> None:
        images, at = self._image_history.get(spec.id, ([], -1))
        to = at + step
        if not 0 <= to < len(images):
            return
        block = images[to]
        if await self._show_image(spec, block, teacher=True, remember=False):
            self._image_history[spec.id] = (images, to)
            if block.origin == "auto":
                fv.image = block
            await self.bus.publish(ImageChoices(slide_id=spec.id, index=to, count=len(images)))
            log.info("teacher stepped to image %d/%d on %r", to + 1, len(images), spec.title)

    async def _open_tail(self, head: SlideSpec, blocks: list) -> None:
        """Content that no longer fits beside the teacher's image continues on the next part, right after it."""
        meta = self._meta[head.id]
        part = self._last_part(meta.frame, head) + 1
        if head.part is None:
            head = head.model_copy(update={"part": 1})
            await self._commit(head)
        tail = frame_slide(meta.frame.topic, meta.frame.facet, continuation_of=head.id)
        tail = tail.model_copy(update={"title": head.title, "part": part, "blocks": blocks, "layout": head.layout})
        self._meta[tail.id] = SlideMeta(meta.frame)
        await self.deck.add(tail, activate=False, after=head.id)
        self._tails[head.id] = (tail.id, list(blocks))
        self.stats.slides += 1
        if self._working_id == head.id:
            self._working_id = tail.id  # new content continues after the moved content
        log.info("teacher image on %r: %d block(s) moved to part %d", head.title, len(blocks), part)

    async def _take_back_tail(self, head: SlideSpec) -> SlideSpec:
        """The image that pushed content to the next part is gone: the content comes back, when that part still holds
        only it and it fits again (live test 2026-10-06: Find image, then Remove, left a thin part IV)."""
        tail_id, moved = self._tails.pop(head.id, ("", []))
        tail = self._spec(tail_id)
        if tail is None or list(tail.blocks) != moved:  # gone, or new content joined it: it stays as it is
            return head
        back = rejoin(head, moved)
        if not fits(back):
            return head
        await self.deck.remove(tail_id)
        self._meta.pop(tail_id, None)
        if self._working_id == tail_id:
            self._working_id = head.id
        if head.part == 1 and self._last_part(self._meta[head.id].frame, head) == 1:
            back = back.model_copy(update={"part": None})
        log.info("content of %r part %s back on part %s (image removed)", head.title, tail.part, head.part)
        return back

    @staticmethod
    def _block(img: dict, query: str) -> ImageBlock:
        w, h = img.get("width") or 4, img.get("height") or 3
        return ImageBlock(url=f"/media/{img['id']}.jpg", alt=img.get("alt") or query, image_id=img["id"],
                          credit=(img.get("author") or "")[:120], licence=img.get("licence") or "",
                          aspect=round(w / h, 3), origin="auto")

    async def _on_image_ready(self, ev: ImageReady) -> None:
        slide_id, reason = self._image_requests.pop(ev.request_id, (ev.slide_id, "auto"))
        meta = self._meta.get(slide_id)
        if meta is None:
            return
        fv = self._fv(meta.frame)
        if norm_query(fv.pending) == norm_query(ev.query):
            fv.pending = ""
        blocks = [self._block(i, ev.query) for i in ev.images]
        if not blocks:
            if reason == "auto" and ev.reason in ("no relevant image", "no usable candidates", "no match (cached)"):
                fv.no_match.add(norm_query(ev.query))
            elif reason == "auto":  # timeout / network / no relevance model: try again later, not on every unit
                fv.retry_at = self.now() + IMAGE_RETRY_S
            log.info("image %r: none (%s)", ev.query, ev.reason)
            return
        fv.query, fv.kind = ev.query, ev.kind
        known = {c.image_id for c in fv.candidates}
        fv.candidates += [b for b in blocks if b.image_id not in known]
        spec = self._spec(slide_id)
        if reason == "change":
            fresh = [b for b in blocks if b.image_id not in fv.shown_ids]
            if spec is not None and fresh:
                await self._replace_image(spec, fresh[0], fv)
            return
        if fv.removed:
            return
        # the content may have moved on to the next part while the search ran: then the frame's working slide
        targets = [x.id for x in (spec, self._spec(self._working_id)) if x is not None
                   and x.id in self._meta and self._meta[x.id].frame.same(meta.frame)]
        for target in dict.fromkeys(targets):
            t = self._spec(target)
            if t is None or image_of(t) is not None or blocked(t) or not await self._about(ev.query, t):
                continue
            if await self._show_image(t, blocks[0], teacher=False):
                fv.image = blocks[0]
                fv.shown_ids.add(blocks[0].image_id)
                log.info("image %r on %r: %s", ev.query, t.title, ev.images[0].get("title", ""))
                return
        fv.image = fv.image or blocks[0]  # no room now: a later part of this topic may take it

    async def _replace_image(self, spec: SlideSpec, block: ImageBlock, fv: FrameVisual) -> None:
        fv.shown_ids.add(block.image_id)
        if await self._show_image(spec, block, teacher=True):
            fv.image = block

    async def _on_image_command(self, kind: str, args: dict) -> None:
        slide_id = args.get("slide_id")
        spec = self._spec(slide_id) if isinstance(slide_id, str) else None
        meta = self._meta.get(slide_id) if isinstance(slide_id, str) else None
        if spec is None or meta is None or meta.is_title:
            log.warning("%s: unknown or title slide %r", kind, slide_id)
            return
        fv = self._fv(meta.frame)
        cur = image_of(spec)
        if kind in ("image_prev", "image_next"):
            await self._step_image(spec, fv, -1 if kind == "image_prev" else 1)
            return
        if kind == "remove_image":
            if cur is not None:
                await self._commit(await self._take_back_tail(without_image(spec)))
                if cur.origin == "auto":
                    fv.removed, fv.image = True, None  # the teacher does not want this topic's picture
                log.info("teacher removed the image of %r", spec.title)
            return
        if kind == "set_image":
            image_id = str(args.get("image_id") or "")
            if not re.fullmatch(r"[0-9a-f]{16}", image_id):
                log.warning("set_image: bad image id %r", image_id)
                return
            try:
                aspect = min(5.0, max(0.2, float(args.get("aspect") or 4 / 3)))
            except (TypeError, ValueError):
                aspect = 4 / 3
            block = ImageBlock(url=f"/media/{image_id}.jpg", alt=str(args.get("alt") or spec.title)[:120],
                               image_id=image_id, aspect=aspect, origin="teacher")
            await self._show_image(spec, block, teacher=True)
            log.info("teacher image on %r", spec.title)
            return
        # change_image: the next accepted candidate, then a deeper search for the same scenario. On a slide without
        # an image it is the teacher's "Find image": the topic's unused candidates, else a search for the model's
        # hint or the slide's topic (also where the policy said no, or the teacher removed the automatic image)
        if cur is not None:
            fv.shown_ids.add(cur.image_id)
        nxt = next((c for c in fv.candidates if c.image_id not in fv.shown_ids), None)
        if nxt is not None:
            await self._replace_image(spec, nxt, fv)
            return
        generic = ("definition", "meaning", "overview", "introduction", "process", "importance")
        hinted = fv.hint.query if fv.hint is not None and fv.hint.query else ""
        kind = fv.kind if fv.query else (fv.hint.kind if hinted else "photo")
        facet = meta.frame.facet
        query = fv.query or hinted or (meta.frame.topic if not facet or facet.lower() in generic else facet) or spec.title
        deeper = bool(fv.query) or norm_query(query) in fv.no_match  # its first results were offered or not relevant
        await self._request_image(spec.id, query, kind, fv, "change", deeper=deeper)
