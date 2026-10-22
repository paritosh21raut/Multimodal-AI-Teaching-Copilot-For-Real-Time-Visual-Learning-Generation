"""PresentationEngine: InterpretationReady + ConceptSignal + teacher commands → Deck (F-005).

Deterministic. Owns the planner state (working slide, dwell queue, corrections, new-topic candidate) and is the
only caller of Deck.add/update in a real lecture. Display flags (pin/blank/navigation) stay in the Deck.

Truthful projector: interpretations carry the corrected content. A concern says what the teacher actually said
(`wrong`) and what the slide shows instead (`right`). When the model is not confident enough the slide shows what
the teacher said; the teacher can switch either way from the control view.
"""
from __future__ import annotations

import asyncio
import difflib
import json
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
    CorrectionPlaced,
    DeckState,
    Event,
    ImageChoices,
    ImageReady,
    ImageRequested,
    InterpretationReady,
    LiveCue,
    Lifecycle,
    RepresentationIntent,
    SimulationNotice,
    LifecycleChanged,
    SlideContextChanged,
    SlideOverflow,
    TranscriptFinal,
    new_id,
)
from copilot.core.state import Concern, LectureStateStore
from copilot.core.textutil import normalise_spoken, stem
from copilot.presentation.composer import (
    BODY_BUDGET_PX, TERM_SUFFIX, add_point, body_height, clear_cue_list, clear_provisional, continue_numbering,
    describe, edit_text, set_cue_list, set_live_definition, clear_block, LIVE_DEF_PREFIX,
    element_texts, fits,
    fits_unshrunk, frame_slide, image_of, is_about, is_duplicate, is_set_label, is_small, member_of, merge, rejoin,
    remove_elements, can_parent,
    revise_item, set_provisional, sim_of, split_to_fit, substitute, teacher_items, title_slide, with_image,
    without_image,
)
from copilot.presentation import equations
from copilot.presentation.content import Piece, clean, pieces_and_chain
from copilot.presentation.deck import Deck
from copilot.core.memory import is_child_facet, same_subject, same_title, short_name, title_key, titles_match
from copilot.presentation.planner import Decision, Frame, Signal, Working, decide
from copilot.presentation.scenes import SceneController
from copilot.presentation.simulations import SimulationController
from copilot.core.interpretation import VisualHint
from copilot.presentation.spec import DefinitionBlock, ImageBlock, ItemImage, SlideSpec
from copilot.visuals.policy import (FrameVisual, blocked, body_subject, names_a_thing, names_an_object, norm_query,
                                     sibling_hint)
from copilot.visuals.policy import decide as image_decision

log = logging.getLogger(__name__)

TICK_S = 0.25
APPLY_WAIT_S = 5.0
MAX_SIGNALS = 300
MAX_CORRECTIONS = 100
CUE_TIME_SLACK_S = 0.6  # a final line's start vs the cue sentence's start from the live pass (word timings, splits)
IMAGE_RETRY_S = 60.0  # lecture seconds before a failed image search (network, timeout) is tried again
# An automatic image must be about the slide it goes on: query vs slide text (MiniLM cosine). Live test 2026-10-06
# put "human digestive system diagram" on the quadratic-equation slide (0.07); the weakest right pairing recorded
# so far is 0.33 (stomata diagram / photosynthesis process slide). Only clearly unrelated images are stopped.
IMAGE_MIN_RELEVANCE = 0.25
MAX_EDIT_CHARS = 300  # one edited / added element (F-008)
MAX_CHILDREN = 60     # registered members of announced sets (F-013 S2)


@dataclass
class PresentationSettings:
    min_dwell_s: float = 15.0
    part_dwell_s: float = 6.0   # the next part of the same frame (the slide is full): a short wait is enough
    provisional: bool = True
    provisional_ttl_s: float = 20.0
    cues: bool = True \
            # F-013: an announced topic / a named list shows at once, before the interpretation
    cue_ttl_s: float = 30.0      # an announced slide nothing confirmed (no content) is taken down after this
    cue_list_ttl_s: float = 40.0
    live_def_ttl_s: float = 20.0  # S1b: a definition being said, not interpreted after this, is taken down
    shift_threshold: float = 0.75
    title_slide: bool = True
    simulations: str = "auto"  # F-014: auto (a spoken cue shows one) | suggest (a /control chip) | off
    templates_auto: bool = True  # F-015: a spoken cue starts a template (config: off; the teacher's pick still works)
    scenes: bool = True          # F-015: live scenes from spoken cues (an LLM call each; follows `simulations`)

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
    wrong: str \
            # as the teacher said it
    right: str \
            # the correction
    showing_right: bool = True
    # F-013 S3 (E1): no element has the exact words. `reworded`: elements that state the teacher's version in other
    # words (Show correction replaces each with `statement`, Show what I said puts `originals` back); `version`: what
    # the elements made from the concern's lines say ("right" / "wrong" / "" = neither, or nothing was placed)
    reworded: list[tuple[str, str]] = field(default_factory=list)
    statement: str = ""
    originals: dict[tuple[str, str], str] = field(default_factory=dict)
    version: str = ""

    @property
    def shows(self) -> str:
        if self.targets:
            return "correction" if self.showing_right else "said"
        if self.reworded:
            return "correction" if self.originals else "said"
        return "rewritten" if self.version == "right" else "absent"


@dataclass
class Tentative:
    """Content of a not-yet-confirmed new topic, shown on the current slide meanwhile; it moves to the new topic's
    slide once the topic is confirmed (so it does not stay on the previous topic's slide)."""
    topic: str
    elements: set[tuple[str, str]]  # (slide id, element id) on every slide the content reached
    pieces: list[Piece]


@dataclass
class CueSlide:
    """F-013: the slide opened from a spoken announcement, before any interpretation of it."""
    slide_id: str
    segment_id: str
    name: str
    previous: Optional[str]   # the working slide before it (restored if the announcement comes to nothing)
    expires: float
    adopted: bool = False     # an interpretation of the announcement (or later lines) reached it
    utterance: int = 0 \
            # S1b: the utterance that announced it (the title grows while it is said)
    start: float = -1.0       # lecture time the announcing sentence started (-1 = unknown)
    mark: int = 0 \
            # final lines received when it opened (order fallback without times)
    rule: str = "" \
            # cues rule: "section" / "ordinal" = one of a numbered series (F-013 S2)
    parent: str = "" \
            # the subtopic it is a member of ("" = none known)


SERIES_RULES = ("section", "ordinal")  # a numbered series: its name stays the title (no misheard topic name)


@dataclass
class CueList:
    """F-013: list members named by the teacher, shown as a provisional tree until the interpretation of their lines."""
    slide_id: str
    head: str
    items: list[str]
    count: int
    segments: set[str]
    expires: float
    utterances: set[int] = field(default_factory=set)
    start: float = -1.0
    mark: int = 0


@dataclass
class LiveDef:
    """F-013 S1b: a definition shown as it is being said, until the interpretation of its line."""
    slide_id: str
    term: str
    utterance: int
    segments: set[str]
    expires: float
    start: float = -1.0
    mark: int = 0


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


def mentions(it, name: str) -> bool:
    """The interpretation's content talks about the announced name (every longer word of it appears): a misheard
    announcement ("momentum" for matter) does not, so its slide takes the model's title instead."""
    words = [w[:5] for w in re.findall(r"[a-z0-9]{4,}", name.lower())]
    if not words:
        return False
    text = json.dumps(it.model_dump(include={"acts", "subtopic", "topic"}), ensure_ascii=False).lower()
    return all(w in text for w in words)


_VERSION_STOP = {"the", "a", "an", "of", "and", "or", "in", "on", "to", "is", "are", "was", "were", "be", "it", "its",
                 "that", "this", "by", "for", "with", "as", "at", "from"}


def _version_words(text: str) -> set[str]:
    return {stem(w) for w in re.findall(r"[a-z0-9]+", normalise_spoken(text)) if w not in _VERSION_STOP}


def slide_version(text: str, wrong: str, right: str) -> str:
    """Which version of a concern an element states when neither exact phrase is in it (F-013 S3, E1): "right" when it
    has a word only the correction has and none only the teacher's words have, "wrong" the other way round, "" when
    it has neither or both. test8: "AI is not limited to deep learning; deep learning is one advanced method within
    AI" for "AI is deep learning" -> "AI includes many methods; deep learning is a subset" is neither."""
    w, r = _version_words(wrong), _version_words(right)
    have = _version_words(text)
    says_right, says_wrong = bool(have & (r - w)), bool(have & (w - r))
    return "right" if says_right and not says_wrong else "wrong" if says_wrong and not says_right else ""


def contains_words(text: str, words: str) -> bool:
    return bool(words) and re.search(rf"(?<![A-Za-z0-9]){re.escape(words)}(?![A-Za-z0-9])", text, re.IGNORECASE) \
        is not None


def item_query(term: str, facet: str) -> str:
    """The picture search for one concept card (F-013 S4): a one-word term is named with the set it belongs to, in the
    singular ("Mars" under "Planets" -> "Mars planet", as the model named Mercury and Venus in test21); with the
    lecture topic instead, "Mars Solar System" found an Italian-labelled orbit diagram. Otherwise the term alone."""
    head = facet.strip().lower()
    if len(term.split()) > 1 or len(head.split()) != 1 or not names_a_thing(facet) or head in term.lower():
        return term
    one = head[:-3] + "y" if head.endswith("ies") else head[:-1] if head.endswith("s") and not head.endswith("ss") else head
    return f"{term} {one}"


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
        self._said: OrderedDict[str, str] = OrderedDict()  # segment id -> text (named equations, F-013 S3)
        self._shown_eq: set[str] = set()  # library equations already shown in this lecture
        self._corrections: OrderedDict[str, Correction] = OrderedDict()
        self._tentative: Optional[Tentative] = None
        self._placements: Optional[list[tuple[Piece, set[tuple[str, str]]]]] = None  # collected by _place
        self._prov: Optional[tuple[str, str, float]] = None  # (slide id, segment id, expires at)
        self._cue: Optional[CueSlide] = None
        self._cue_list: Optional[CueList] = None
        self._live_def: Optional[LiveDef] = None
        self._seg_order: OrderedDict[str, int] = OrderedDict()  # segment id -> arrival number (bounded)
        self._seg_start: OrderedDict[str, float] = OrderedDict()  # segment id -> lecture time it starts (bounded)
        self._seg_n = 0
        self._hold_screen = False  # an earlier unit is placed while an announced slide is on screen
        self._cue_keep = ""  # the announced name, kept as the title of the slide that holds its content
        self._early: set[int] = set()  # lines of the unit being placed said before the announcement (F-013 S2)
        # F-013 S2: members the teacher announced or the lecture classified, by name -> (topic, the subtopic they are
        # members of); a member's slide is that subtopic's child (crumb Topic — Set, Lecture Structure nests it)
        self._children: OrderedDict[str, tuple[str, str]] = OrderedDict()
        self._boundary_seg: Optional[str] = None  # a concept boundary not yet interpreted: the slide may change
        self._live_id: Optional[str] = None
        self._live_since = 0.0
        self._context: tuple[str, dict[str, str]] = ("", {})
        self._tasks: list[asyncio.Task] = []
        self._visuals: list[tuple[Frame, FrameVisual]] = []      # per frame: its image, candidates, teacher choices
        self._image_requests: dict[str, tuple[str, str]] = {}   # request id -> (slide id, reason)
        # F-013 S4 (D2): the topics each automatic image was shown under: another topic's image is not repeated
        self._image_topics: dict[str, set[str]] = {}
        # F-013 S4 (D1): the pictures of a slide's concept cards, per slide -> block id -> image (None = none found);
        # a block id missing while its request runs
        self._items: dict[str, dict[str, Optional[ItemImage]]] = {}
        self._item_asked: set[tuple[str, str]] = set()  # (slide id, block id) whose picture was searched
        self._image_history: dict[str, tuple[list[ImageBlock], int]] = {}  # slide id -> (images it showed, current)
        self._tails: dict[str, tuple[str, list]] = {}  # slide id -> (next part, blocks moved there for an image)
        # the teacher's edits are final (F-008): the elements the teacher wrote (ids are unique across slides, so they
        # stay the teacher's when a block moves to another part), slides whose title the teacher wrote, and per slide
        # the texts the teacher deleted or replaced (they do not come back there)
        self._teacher: set[str] = set()
        self._teacher_titles: set[str] = set()
        self._dismissed: dict[str, list[str]] = {}
        self._sims = SimulationController(self)  # F-014 Concept Simulation (owns the one visual mode)
        self._scenes = SceneController(self)     # F-015 Live Scene Engine (runs in that mode)

    # ---- wiring -------------------------------------------------------------------------------
    def attach(self) -> None:
        self.bus.subscribe("presentation", self._on_event, [
            InterpretationReady, ConceptSignal, LiveCue, CommandReceived, ConcernResolved, SlideOverflow,
            LifecycleChanged, DeckState, ImageReady, TranscriptFinal, RepresentationIntent,
        ])
        self._tasks = [asyncio.create_task(self._ticker(), name="presentation:ticker")]

    async def stop(self) -> None:
        if self._scenes.open is not None and self._scenes.open.task is not None:
            self._scenes.open.task.cancel()  # F-015: a scene call still streaming
        for t in self._tasks:
            t.cancel()
        if self._tasks:
            await asyncio.wait(self._tasks, timeout=2.0)
        self._tasks = []

    async def flush_pending(self) -> None:
        """Lecture ending: put slides still waiting for the dwell time into the deck; nothing provisional stays."""
        async with self._lock:
            if self._sims.collecting:  # F-014 S1: the lecture ended during a simulation: its recap still comes
                await self._sims.end("the lecture ended")
            while self._pending:
                await self._add_to_deck(self._pending.pop(0))
            ld, self._live_def = self._live_def, None
            spec = self._spec(ld.slide_id) if ld is not None else None
            if spec is not None:
                await self._commit(clear_block(spec, LIVE_DEF_PREFIX + spec.id))
            await self._drop_cue()
            cl, self._cue_list = self._cue_list, None
            spec = self._spec(cl.slide_id) if cl is not None else None
            if spec is not None:
                await self._commit(clear_cue_list(spec))

    def now(self) -> float:
        return (self.clock() - self._t0) * self.speed

    async def _on_event(self, event: Event) -> None:
        async with self._lock:
            if isinstance(event, InterpretationReady):
                await self._on_interpretation(event)
            elif isinstance(event, ConceptSignal):
                await self._on_signal(event)
            elif isinstance(event, LiveCue):
                await self._on_live_cue(event)
            elif isinstance(event, ConcernResolved):
                await self._on_resolved(event)
            elif isinstance(event, CommandReceived):
                if event.command.kind == "force_new_slide":
                    await self._force_new()
                elif event.command.kind in ("remove_image", "change_image", "set_image", "image_prev", "image_next"):
                    await self._on_image_command(event.command.kind, event.command.args)
                elif event.command.kind in ("edit_text", "delete_item", "add_point"):
                    await self._on_edit(event.command.kind, event.command.args)
                elif event.command.kind == "show_equation":
                    await self._show_equation(str(event.command.args.get("id") or ""))
                elif event.command.kind.startswith(("sim_", "scene_")) and event.command.kind != "sim_full":
                    kind, args = event.command.kind, event.command.args
                    if kind != "sim_end" and self._scenes.owns(kind, args):  # F-015: a scene's slide / chip
                        await self._scenes.on_command(kind, args)
                    else:
                        await self._sims.on_command(kind, args)
            elif isinstance(event, RepresentationIntent):
                await self._sims.on_intent(event)
                await self._scenes.on_intent(event)
            elif isinstance(event, TranscriptFinal):  # what was said, for named equations (F-013 S3)
                self._said[event.segment.id] = event.segment.text
                while len(self._said) > MAX_SIGNALS:
                    self._said.popitem(last=False)
                return
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
                    await self._expire_cues()
                    await self._sims.tick()
                    await self._scenes.tick()
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

    def _in_deck(self, slide_id: str) -> bool:
        try:
            self.deck.get(slide_id)
            return True
        except KeyError:
            return False

    def _all_specs(self) -> list[SlideSpec]:
        return self.deck.slides + list(self._pending)

    def _plain_items(self) -> set[tuple[str, str]]:
        """Elements whose whole text is one string (points, a card's notes): a reworded concern can replace it and put
        it back exactly (a definition card, a fact tile or a step with its detail is two fields)."""
        out: set[tuple[str, str]] = set()
        for s in self._all_specs():
            for b in s.blocks:
                if b.type == "points":
                    out |= {(s.id, i.id) for i in b.items}
                elif b.type == "definition":
                    out |= {(s.id, n.id) for n in b.notes}
        return out

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
        if self._hold_screen:  # an earlier unit's slide never replaces the announced one on screen (F-013)
            adopt = False
        if not adopt:  # content for an earlier frame: into the deck without taking the screen, behind its part
            prev = spec.continuation_of if spec.continuation_of and self._in_deck(spec.continuation_of) else None
            await self.deck.add(spec, activate=False, after=prev)
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

    def _named_equations(self, ev: InterpretationReady, it, pieces: list[Piece]) -> list[Piece]:
        """Standard equations the unit's lines name ("time-dependent Schrödinger equation", "Maxwell's equations"),
        or ask for ("let us write the equation" on a slide about one), from the library (F-013 S3, C10). The
        formula the teacher says wins: none when the unit has its own. Each equation once per lecture."""
        if any(p.kind == "formula" for p in pieces):
            return []
        lines = [self._said[s] for s in ev.segment_ids if s in self._said]
        subject = f"{it.subtopic} {it.topic}"
        context = " ".join([subject, *lines])
        ids: list[str] = []
        for line in lines:
            ids += equations.named(line, context) or equations.asked_for(line, subject)
        out = []
        for i in dict.fromkeys(ids):
            e = equations.entry(i)
            if e is not None and i not in self._shown_eq:
                self._shown_eq.add(i)
                out.append(equations.piece(e))
                log.info("[EQ] %s: standard form from the library", e.name)
        return out

    async def _show_equation(self, eq_id: str) -> None:
        """/control Show equation: the library entry on the live slide, or on its next part when it does not fit."""
        e = equations.entry(eq_id)
        live = self.deck.live
        meta = self._meta.get(live.id) if live is not None else None
        if e is None or live is None or meta is None or meta.is_title:
            log.warning("show_equation: %r not shown (unknown equation or no content slide on screen)", eq_id)
            return
        self._shown_eq.add(eq_id)
        new, rest = merge(live, equations.piece(e))
        if rest is None:
            await self._commit(new)
        else:
            nxt = await self._next_part(live, meta.frame)
            new, _ = merge(nxt, rest)
            await self._open(new, SlideMeta(meta.frame), exempt=True)
            self._working_id = new.id
        self.stats.ops["teacher_show_equation"] += 1
        log.info("teacher show_equation on %r: %s", live.title, e.name)

    async def _force_new(self) -> None:
        self.stats.ops["force_new"] += 1
        if self._sims.collecting and await self._sims.end("the teacher's New slide"):
            return  # the recap is the new slide
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
            spec = frame_slide(frame.topic, frame.facet, continuation_of=self._working_id, parent=frame.parent)
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
        nxt = frame_slide(frame.topic, frame.facet, continuation_of=prev.id, parent=frame.parent)
        return nxt.model_copy(update={"title": prev.title, "part": part + 1})

    # ---- fast path ----------------------------------------------------------------------------
    async def _on_signal(self, ev: ConceptSignal) -> None:
        await self._sims.on_signal(ev.segment_id)
        self._signals[ev.segment_id] = Signal(ev.shift_score, ev.boundary)
        while len(self._signals) > MAX_SIGNALS:
            self._signals.popitem(last=False)
        self._seg_n += 1
        self._seg_order[ev.segment_id] = self._seg_n
        self._seg_start[ev.segment_id] = ev.start
        while len(self._seg_order) > MAX_SIGNALS:
            self._seg_order.popitem(last=False)
        while len(self._seg_start) > MAX_SIGNALS:
            self._seg_start.popitem(last=False)
        if ev.utterance:  # the final line of an utterance whose partials already showed something (S1b)
            if self._cue is not None and self._cue.utterance == ev.utterance:
                self._cue.segment_id = ev.segment_id
            if self._cue_list is not None and ev.utterance in self._cue_list.utterances:
                self._cue_list.segments.add(ev.segment_id)
            if self._live_def is not None and self._live_def.utterance == ev.utterance:
                self._live_def.segments.add(ev.segment_id)
        if self._sims.collecting:  # F-014 S1: no cue slides, teasers or figures while a simulation runs ...
            if not (ev.announce and self.s.cues) or self._sims.about_open(ev.announce):
                return
            await self._sims.end(f"a new topic was announced ({ev.announce!r})")  # ... unless a new topic is announced
        if self.s.cues:
            if ev.announce:
                await self._on_announce(ev)
            if ev.list_items or ev.list_count or ev.item:
                await self._on_list_cue(ev)
        if ev.figure:
            await self._on_figure(ev.figure)
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

    # ---- spoken cues (F-013) --------------------------------------------------------------------
    def _open_cue_slide(self) -> Optional[str]:
        return self._cue.slide_id if self._cue is not None else None

    async def _on_live_cue(self, ev: LiveCue) -> None:
        """F-013 S1b: structure heard while the teacher is still speaking (partial transcript)."""
        if not self.s.cues or self._sims.collecting:  # F-014 S1: the final line decides during a simulation
            return
        if ev.announce:
            await self._on_announce(ev)
        if ev.list_items or ev.list_count or ev.item:
            await self._on_list_cue(ev)
        if ev.term and ev.definition:
            await self._on_live_definition(ev)

    async def _on_live_definition(self, ev: LiveCue) -> None:
        live = self.deck.live
        meta = self._meta.get(live.id) if live is not None else None
        if live is None or meta is None or meta.is_title or not self.deck.following:
            return
        announced = self._cue is not None and self._cue.slide_id == live.id and not self._cue.adopted
        if not (announced or titles_match(ev.term, live.title) or titles_match(ev.term, meta.frame.facet)
                or titles_match(ev.term, meta.frame.topic)):
            return  # only the subject of the slide on screen (precision: no card for a passing "X is ...")
        if any(b.type == "definition" and not getattr(b, "provisional", False) and titles_match(b.term, ev.term)
               for b in live.blocks):
            return  # already defined: the teacher is elaborating
        new = set_live_definition(live, ev.term, ev.definition)
        if new is None:
            return
        await self._commit(new)
        ld = self._live_def
        if ld is None or ld.slide_id != live.id or ld.utterance != ev.utterance:
            self._live_def = LiveDef(live.id, ev.term, ev.utterance, set(), self.now() + self.s.live_def_ttl_s,
                                     start=ev.start, mark=self._mark(ev))
        else:
            ld.expires = self.now() + self.s.live_def_ttl_s

    async def _on_announce(self, ev) -> None:
        """The teacher announced a topic: its slide opens now, titled by the announcement and marked pending; the
        interpretation of that unit fills, renames or (when nothing comes of it) removes it. `ev` is the final line's
        ConceptSignal or, while the teacher is still speaking, a LiveCue (S1b: the title grows as it is said)."""
        name = ev.announce
        rule = getattr(ev, "announce_rule", "")
        seg = getattr(ev, "segment_id", "")
        if not self.deck.following:
            return  # the teacher is looking at another slide: nothing jumps
        cue = self._cue
        if cue is not None:  # adopted by a unit with nothing to show ("Let us discuss the causes.") is empty too
            spec = self._spec(cue.slide_id)
            if spec is not None and teacher_items(spec) == 0:  # a second announcement before any content
                same_line = bool(ev.utterance) and cue.utterance == ev.utterance  # heard further: the newest wins
                if not same_line and rule in SERIES_RULES and cue.rule not in SERIES_RULES \
                        and not titles_match(spec.title, name):
                    # "Now let us discuss the causes." then "1. Social. ...": the first section of what was announced
                    cue.parent = short_name(spec.title, self._meta[spec.id].frame.topic)
                if spec.title != name and (same_line or not titles_match(spec.title, name)):
                    frame = Frame(self._meta[spec.id].frame.topic, name, parent=cue.parent)
                    fresh = frame_slide(frame.topic, frame.facet, parent=frame.parent)
                    await self._commit(spec.model_copy(update={"title": name, "facet": fresh.facet,
                                                               "parent": fresh.parent}))
                    self._meta[spec.id].frame = frame
                cue.rule = rule
                cue.segment_id = seg or (cue.segment_id if cue.utterance == ev.utterance else "")
                cue.name, cue.expires, cue.utterance = name, self.now() + self.s.cue_ttl_s, ev.utterance
                if not same_line:  # a newer announcement: what belongs to the slide starts from it
                    cue.start, cue.mark = ev.start, self._mark(ev)
                log.info("cue: announced slide renamed %r", name)
                return
        meta = self._meta.get(self._working_id or "")
        if meta is not None and not meta.is_title and (same_title(name, meta.frame.facet)
                                                      or same_title(name, meta.frame.topic)):
            return  # the slide on screen already is about it ("Causes of X" is not X: F-013 S2)
        while self._pending:  # the teacher has moved on: waiting slides go into the deck behind the new one
            await self.deck.add(self._pending.pop(0), activate=False)
            self.stats.slides += 1
        if meta is not None and not meta.is_title:
            topic = meta.frame.topic
        else:
            topic = self.store.snapshot().setup.expected_topic or name
        if self._cue is not None:
            await self._drop_cue(keep_working=True)
        parent = self._announced_parent(name, topic, rule, meta)
        spec = frame_slide(topic, name, parent=parent).model_copy(update={"pending": True})
        if titles_match(topic, name):
            spec = spec.model_copy(update={"title": name})
        await self._open(spec, SlideMeta(Frame(topic, name, parent=parent)), exempt=True)
        self._cue = CueSlide(spec.id, seg, name, self._working_id, self.now() + self.s.cue_ttl_s,
                             utterance=ev.utterance, start=ev.start, mark=self._mark(ev), rule=rule, parent=parent)
        self.stats.ops["cue_slide"] += 1
        log.info("cue: %r shown at once (pending)", name)

    async def _on_list_cue(self, ev) -> None:
        """Members of a list as the teacher names them: a provisional tree on the slide on screen."""
        live = self.deck.live
        if live is None or not self.deck.following or live.id not in self._meta or self._meta[live.id].is_title:
            return
        cl = self._cue_list
        seg = getattr(ev, "segment_id", "")
        utts = {ev.utterance} if ev.utterance else set()
        if ev.list_items or ev.list_count:
            head = ev.list_head or live.title
            if cl is not None and cl.slide_id == live.id and ev.utterance and ev.utterance in cl.utterances:
                # the same sentence heard further (partials, then the final line): the list grows in place
                items = list(ev.list_items) if len(ev.list_items) >= len(cl.items) else cl.items
                cl.head, cl.items, cl.count = head, items, max(cl.count, ev.list_count)
                cl.expires = self.now() + self.s.cue_list_ttl_s
                if seg:
                    cl.segments.add(seg)
            else:
                cl = CueList(live.id, head, list(ev.list_items), ev.list_count, {seg} if seg else set(),
                             self.now() + self.s.cue_list_ttl_s, utts, start=ev.start, mark=self._mark(ev))
        elif cl is not None and cl.slide_id == live.id and ev.item and len(cl.items) < max(cl.count, 2) \
                and not any(titles_match(ev.item, x) for x in cl.items):
            cl.items.append(ev.item)
            if seg:
                cl.segments.add(seg)
            cl.utterances |= utts
            cl.expires = self.now() + self.s.cue_list_ttl_s
        else:
            return
        self._cue_list = cl
        lm = self._meta.get(live.id)
        if lm is not None and cl.items:
            facet = cl.head if cl.head and not same_title(cl.head, live.title) \
                    and not same_title(cl.head, lm.frame.topic) else lm.frame.facet
            self._register(lm.frame.topic, facet, cl.items)
        if len(cl.items) < 1:
            return  # "three types of X": nothing to show until the first one is named
        new = set_cue_list(live, cl.head, cl.items)
        if new is not None:
            await self._commit(new)
            log.info("cue: list %r %s", cl.head, cl.items)

    def _announced_parent(self, name: str, topic: str, rule: str, meta: Optional[SlideMeta]) -> str:
        """F-013 S2: where an announced slide sits — a member the teacher announced earlier ("three types: ..."), or
        the next of a numbered series whose previous member is on screen ("The 7th topic is Jupiter" after Mars,
        under Planets)."""
        reg = self._registered(name, topic)
        if reg is not None:
            return reg
        if rule in SERIES_RULES and meta is not None and not meta.is_title and meta.frame.parent \
                and titles_match(meta.frame.topic, topic):
            return meta.frame.parent
        return ""

    def _mark(self, ev) -> int:
        """Arrival-order mark of a cue: its own final line, or the next final line for a cue heard live."""
        return self._seg_n if isinstance(ev, ConceptSignal) else self._seg_n + 1

    def _covers(self, segments: list[str], start: float, mark: int) -> bool:
        """Does a unit hold speech from the cue's sentence on? By lecture time when both are known (a live cue and the
        final lines are linked by when they were said; utterance numbers shift with sentence cuts), else by order."""
        times = [self._seg_start.get(s, -1.0) for s in segments]
        if start >= 0 and any(t >= 0 for t in times):
            return any(t >= start - CUE_TIME_SLACK_S for t in times)
        return any(self._seg_order.get(s, -1) >= mark for s in segments)

    def _lines_before(self, segments: list[str], start: float, mark: int) -> set[int]:
        """Line numbers (1-based) of a unit said before a cue's sentence (same linkage as _covers)."""
        out = set()
        for n, sid in enumerate(segments, start=1):
            t = self._seg_start.get(sid, -1.0)
            if start >= 0 and t >= 0:
                if t < start - CUE_TIME_SLACK_S:
                    out.add(n)
            elif self._seg_order.get(sid, mark) < mark:
                out.add(n)
        return out

    async def _place_early(self, pieces: list[Piece]) -> list[Piece]:
        """F-013 S2: a unit that holds the end of the previous subject and the announcement of the next one (the gate
        could not cut it, e.g. one long line): what was said before the announcement stays on the previous slide."""
        early, self._early = self._early, set()
        cue = self._cue
        prev = self._spec(cue.previous) if cue is not None else None
        meta = self._meta.get(prev.id) if prev is not None else None
        if not early or prev is None or meta is None or meta.is_title:
            return pieces
        before = [p for p in pieces if p.lines and set(p.lines) <= early]
        if not before:
            return pieces
        log.info("cue: %d piece(s) said before %r stay on %r", len(before), cue.name, prev.title)
        self.stats.ops["early"] += 1
        await self._place(prev, False, meta.frame, before, adopt=False)
        return [p for p in pieces if not any(p is b for b in before)]

    async def _settle_cues(self, ev: InterpretationReady) -> None:
        """Before planning: does this unit belong to the announced slide (it holds the announcement or later lines)?
        Its provisional list goes; the interpretation's own content replaces it."""
        self._cue_keep = ""
        cue = self._cue
        if cue is not None:
            later = self._covers(ev.segment_ids, cue.start, cue.mark)
            frame = Frame.of(ev.interpretation)
            # a unit just before the announcement that is already about it belongs there too (test28: two
            # "Transpiration" slides)
            about = titles_match(frame.facet, cue.name) or titles_match(frame.topic, cue.name)
            named = mentions(ev.interpretation, cue.name)
            prev = self._meta.get(cue.previous or "")
            if later and not about and not named and prev is not None and not prev.is_title \
                    and prev.frame.same(frame):
                # the unit also holds the announcement, but the model says it is still the previous subject and its
                # content never names the announced one (the end of transpiration + "The third topic is
                # condensation"): it stays on the previous slide. Content that names it ("Venus ..." while the model
                # still says "Planets", test21) goes to the announced slide (F-013 S2)
                later = False
            self._cue_keep = cue.name if (later or about) and (named or cue.rule in SERIES_RULES) else ""
            if later and not about:
                self._early = self._lines_before(ev.segment_ids, cue.start, cue.mark)
            if later or about:
                if not cue.adopted and self._spec(cue.slide_id) is not None:
                    cue.adopted = True
                    self._working_id = cue.slide_id
            else:
                self._hold_screen = True
        ld = self._live_def
        if ld is not None and self._covers(ev.segment_ids, ld.start, ld.mark):
            self._live_def = None
            spec = self._spec(ld.slide_id)
            if spec is not None:
                await self._commit(clear_block(spec, LIVE_DEF_PREFIX + spec.id))
        cl = self._cue_list
        if cl is not None and self._covers(ev.segment_ids, cl.start, cl.mark):
            spec = self._spec(cl.slide_id)
            if spec is not None:
                await self._commit(clear_cue_list(spec))
            if cl.count <= len(cl.items):
                self._cue_list = None
            else:  # more members announced than named so far: later ones still show
                cl.items, cl.segments, cl.mark = [], set(), self._seg_n + 1
                cl.start = -1.0 if cl.start < 0 else max(cl.start, max(
                    (self._seg_start.get(s, -1.0) for s in ev.segment_ids), default=cl.start) + CUE_TIME_SLACK_S)

    async def _superseded(self, it) -> None:
        """Real content of the same kind replaces what was shown live on the slide receiving it, whatever lines it came
        from (a provisional tree beside the real one made the slide overflow into a second part, audio run
        20261016-032558-f162)."""
        spec = self._spec(self._working_id)
        if spec is None:
            return
        kinds = {a.act for a in it.acts}
        new = spec
        if kinds & {"classification", "groups"} or any(a.items.groups for a in it.acts):
            new = clear_cue_list(new)
            if self._cue_list is not None and self._cue_list.slide_id == spec.id:
                self._cue_list = None
        if "definition" in kinds:
            new = clear_block(new, LIVE_DEF_PREFIX + spec.id)
            if self._live_def is not None and self._live_def.slide_id == spec.id:
                self._live_def = None
        if new is not spec and new != spec:
            await self._commit(new)

    async def _confirm_cue(self, it=None) -> None:
        """After placing an adopted unit: the announced slide is a normal slide once it holds content. F-013 S2: when
        the model names a set for it ("Stages" for the announced "Stage 3"), the set is its parent."""
        cue = self._cue
        if cue is None or not cue.adopted:
            return
        spec = self._spec(cue.slide_id)
        if spec is None:
            self._cue = None
        elif teacher_items(spec) > 0:
            meta = self._meta.get(spec.id)
            if it is not None and meta is not None and not meta.frame.parent and it.subtopic \
                    and is_set_label(it.subtopic) and titles_match(it.topic, meta.frame.topic) \
                    and not same_subject(it.subtopic, meta.frame.facet, it.topic) and not same_title(it.subtopic, it.topic):
                meta.frame = Frame(meta.frame.topic, meta.frame.facet, parent=it.subtopic)
                spec = spec.model_copy(update={"parent": frame_slide(meta.frame.topic, meta.frame.facet,
                                                                     parent=it.subtopic).parent})
            if spec.pending or spec != self._spec(cue.slide_id):
                await self._commit(spec.model_copy(update={"pending": False}))
            self._cue = None
            log.info("cue: %r confirmed as %r", cue.name, spec.title)

    async def _expire_cues(self) -> None:
        ld = self._live_def
        if ld is not None and self.now() >= ld.expires:
            self._live_def = None
            spec = self._spec(ld.slide_id)
            if spec is not None:
                await self._commit(clear_block(spec, LIVE_DEF_PREFIX + spec.id))
        if self._cue is not None and self.now() >= self._cue.expires:
            await self._drop_cue()
        cl = self._cue_list
        if cl is not None and self.now() >= cl.expires:
            self._cue_list = None
            spec = self._spec(cl.slide_id)
            if spec is not None:
                await self._commit(clear_cue_list(spec))

    async def _drop_cue(self, keep_working: bool = False) -> None:
        """An announced slide nothing came of: removed while it is still empty (else it simply stays)."""
        cue, self._cue = self._cue, None
        if cue is None:
            return
        spec = self._spec(cue.slide_id)
        if spec is None:
            return
        if teacher_items(spec) > 0:
            if spec.pending:
                await self._commit(spec.model_copy(update={"pending": False}))
            return
        await self.deck.remove(spec.id)
        self._meta.pop(spec.id, None)
        if self._working_id == spec.id and not keep_working:
            self._working_id = cue.previous if self._spec(cue.previous) is not None else None
        log.info("cue: %r came to nothing; its slide was removed", cue.name)

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
        if self._sims.collecting:  # F-014 S1: simulation mode: no new slides, no content slide changed
            await self._collect_for_sim(ev)
            return
        await self._settle_cues(ev)
        await self._superseded(it)
        revised = await self._apply_revisions(ev)
        frame = Frame.of(it)
        carry = self._about_chain[1] if self._about_chain[0] == frame else ""
        pieces, chain = pieces_and_chain(it, carry)  # which concept each piece is about (concept columns)
        pieces += self._named_equations(ev, it, pieces)
        pieces = await self._sims.take_late(ev, pieces)  # F-014 S1: said during the last simulation: its recap
        self._about_chain = (frame, chain)
        signals = [self._signals[x] for x in ev.segment_ids if x in self._signals]
        self._placements = []
        moved: list[Piece] = []
        removed: set[tuple[str, str]] = set()
        nav: Optional[str] = None
        try:
            if self._early:
                pieces = await self._place_early(pieces)
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
                d = self._with_parent(self._next_member(d, working, pieces), working)
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
        wm = self._meta.get(self._working_id or "")
        if wm is not None and not wm.is_title:
            self._register_sets(it, wm.frame)
        if it.visual is not None:  # remembered per frame: a new topic's first unit may still wait on the old slide
            self._fv(Frame.of(it)).hint = it.visual
        if nav is None and self._working_id and (placements or it.visual is not None):
            await self._consider_image(self._working_id)
        self._hold_screen = False
        await self._confirm_cue(it)

    async def _collect_for_sim(self, ev: InterpretationReady) -> None:
        """Simulation mode (F-014 S1): the unit's pieces wait for the recap. Lines said before the simulation's cue
        still go to the slide that was being built (without taking the screen); nothing else is placed."""
        it = ev.interpretation
        pieces, _ = pieces_and_chain(it, "")
        pieces += self._named_equations(ev, it, pieces)
        early, later = self._sims.split_early(ev, pieces)
        mode = self._sims.mode
        before = mode.before_id if mode is not None else None
        spec, meta = self._spec(before), self._meta.get(before or "")
        if early and spec is not None and meta is not None and not meta.is_title:
            self.stats.ops["update"] += 1
            await self._place(spec, False, meta.frame, early, adopt=False)
        else:
            later = early + later
        self._sims.collect(later)

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
                # F-013 S3 (E1): the words are on no element. Say what the elements made from the concern's lines
                # state (the heart lecture's card said "corrected" while the slide kept "one ventricle" in other
                # words; replay of tests 1-30: 62 of 135 such concerns were already rewritten correctly, 73 not on
                # the slide at all)
                said = {k: slide_version(texts.get(k, ""), c.wrong, c.right) for k in sorted(own)}
                corr = Correction(c.id, [], c.wrong, c.right, showing_right=want_right,
                                  reworded=[k for k, v in said.items() if v == "wrong" and k in self._plain_items()]
                                  if c.suggested_correction else [],
                                  statement=c.suggested_correction,
                                  version="right" if "right" in said.values() and "wrong" not in said.values() else "")
            self._corrections[c.id] = corr
            while len(self._corrections) > MAX_CORRECTIONS:
                self._corrections.popitem(last=False)
            if corr.targets:
                await self._toggle(corr, show_right=want_right)
                if corr.showing_right:
                    self.stats.corrections_shown += 1
            log.info("concern %s (%s, applied=%s): %d element(s); slide shows %r (%s)", c.id, c.kind, c.applied,
                     len(corr.targets), c.right if corr.showing_right else c.wrong, corr.shows)
            await self.bus.publish(CorrectionPlaced(concern_id=c.id, shows=corr.shows,  # type: ignore[arg-type]
                                                    elements=len(corr.targets or corr.reworded)))

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
            await self._reword(corr, show_right=True)
        elif ev.status == "kept":
            await self._toggle(corr, show_right=False)
            await self._reword(corr, show_right=False)
        log.info("concern %s %s: slide shows %r (%s)", ev.concern_id, ev.status,
                 corr.right if corr.showing_right else corr.wrong, corr.shows)
        if ev.status != "dismissed":
            await self.bus.publish(CorrectionPlaced(concern_id=ev.concern_id, shows=corr.shows,  # type: ignore[arg-type]
                                                    elements=len(corr.targets or corr.reworded)))

    async def _reword(self, corr: Correction, show_right: bool) -> None:
        """F-013 S3 (E1): items that state the teacher's version in other words get the corrected statement (Show
        correction), or their own text back (Show what I said). The teacher's own edits are never replaced."""
        if not corr.reworded or show_right == bool(corr.originals):
            return
        texts = self._elements()
        for sid, eid in corr.reworded:
            spec = self._spec(sid)
            if spec is None or eid in self._locked():
                continue
            text = corr.statement if show_right else corr.originals.get((sid, eid), "")
            new = edit_text(spec, eid, text) if text else None
            if new is None:
                continue
            if show_right:
                corr.originals[(sid, eid)] = texts.get((sid, eid), "")
            await self._commit(new)
        if not show_right:
            corr.originals.clear()

    async def _apply(self, d: Decision, working: Optional[Working], pieces: list[Piece],
                     relation: str = "") -> Optional[str]:
        """Carry out a decision; returns the id of the slide the content went to."""
        frame = d.frame
        if d.op == "new" and self._open_cue_slide() == self._working_id and working is not None \
                and not working.has_content:
            d = Decision("retitle", frame, d.candidate, d.reason + "; on the announced slide")
        elif d.op == "new" and working is not None and not working.is_title and self._titled_by(frame.topic):
            # F-013 S2: the announced slide already carries the confirmed topic's name (test23: "Integral Calculus"
            # was filed under Differential Calculus until two interpretations agreed): it becomes that topic's
            # slide instead of a second "Integral Calculus" right after it
            d = Decision("retitle", frame, d.candidate, d.reason + "; the slide on screen is titled by it")
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
            spec = frame_slide(frame.topic, frame.facet, continuation_of=cont, parent=frame.parent)
            return await self._place(spec, True, frame, pieces, exempt=working is None or working.is_title)
        if d.op == "retitle":
            spec = self._spec(self._working_id)
            assert spec is not None
            fresh = frame_slide(frame.topic, frame.facet, parent=frame.parent)
            title = spec.title if spec.id in self._teacher_titles else fresh.title  # the teacher's title stays
            if spec.id == self._open_cue_slide() and self._cue_keep and spec.id not in self._teacher_titles:
                # the teacher named it ("The third topic is Mercury") and the content is about it: the announced
                # name stays the title (test21). F-013 S2: when the model's label is a set ("Planets"), the announced
                # name is one of its members: its own facet, the set is its parent (the next member, "Venus", is a
                # sibling, not a part of the Mercury slide)
                title = self._cue_keep
                cue = self._cue
                assert cue is not None
                # (a generic facet, "Introduction", is never a parent; "Important Components" is the same subtopic
                # as the announced "Important components of a satellite", not its parent)
                # (test23: "Statics" - Statistics misheard - announced a new topic whose first unit the model labelled
                # "Measures of Central Tendency": the name is the topic, not a member of that set)
                names_topic = same_title(title, frame.topic) or difflib.SequenceMatcher(
                    None, title.lower(), frame.topic.lower()).ratio() >= 0.8
                if names_topic and not same_title(title, frame.topic):
                    title = frame.topic  # the model's spelling of the misheard name ("Fourier Seize": Fourier Series)
                model_set = is_set_label(frame.facet) and not same_subject(title, frame.facet, frame.topic) \
                    and not names_topic and working is not None and working.frame.same_topic(frame)
                if model_set:  # the model's own set label for this unit ("Planets") is the newest judgement
                    frame = Frame(frame.topic, title, parent=frame.facet)
                elif cue.parent and not same_subject(title, cue.parent, frame.topic):
                    frame = Frame(frame.topic, title, parent=cue.parent)  # the member of a set announced earlier
                elif cue.rule in SERIES_RULES and not names_topic:
                    # one of a numbered series: a subtopic of its own, never a part (when it names the model's topic,
                    # "The third topic is Integral Calculus", the model's frame is already its own)
                    frame = Frame(frame.topic, title)
                fresh = frame_slide(frame.topic, frame.facet, parent=frame.parent)
            spec = spec.model_copy(update={"title": title, "subtitle": fresh.subtitle, "facet": fresh.facet,
                                           "parent": fresh.parent})
            self._meta[spec.id].frame = frame
            return await self._place(spec, False, frame, pieces)
        spec = self._spec(self._working_id)
        assert spec is not None
        return await self._place(spec, False, self._meta[spec.id].frame, pieces)

    def _titled_by(self, topic: str) -> bool:
        """The working slide is titled by `topic` while filed under another topic (its frame was not yet confirmed)."""
        spec = self._spec(self._working_id)
        meta = self._meta.get(self._working_id or "")
        return spec is not None and meta is not None and same_title(spec.title, topic) \
            and not titles_match(meta.frame.topic, topic)

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
                # F-013 S2: what overflows belongs to the facet the model moved to while the content stayed on a
                # sparse definition slide (absorb): a slide titled by that facet, not "part N" of the definition
                subject = self._new_subject(cur, frame) if member is None and not cur_member else None
                nxt_frame = subject or frame
                nxt = frame_slide(nxt_frame.topic, nxt_frame.facet, continuation_of=cur.id, parent=nxt_frame.parent)
                if member is not None:
                    nxt = nxt.model_copy(update={"title": member.term})
                elif subject is None:
                    nxt = nxt.model_copy(update={"title": cur.title})
                nxt, rest = merge(nxt, left)
                nxt = continue_numbering(cur, nxt) if subject is None else nxt
                if not nxt.blocks or rest == left:
                    log.error("piece does not fit an empty slide; dropped: %s", left.all_text()[:3])
                    break
                # a member's slides are not parts of the set; the set's parts are numbered once the next has content
                part = None if nxt_member or subject is not None else self._last_part(frame, cur) + 1
                if cur.part is None and part is not None:
                    cur = cur.model_copy(update={"part": 1})
                await self._finish(cur, cur_new, frame, exempt, adopt, cur_member)
                finished.append(cur)
                exempt = False
                if member is not None:
                    log.info("member %r explained in depth: its own slide under %s > %s", member.term, frame.topic,
                             frame.facet)
                if subject is not None:
                    log.info("%r continues on its own slide, not as a next part of %r", subject.facet, cur.title)
                    self.stats.ops["facet_slide"] += 1
                cur, cur_new, cur_member = nxt.model_copy(update={"part": part}), True, nxt_member
                left = rest
            if self._placements is not None:
                produced = {(s.id, e) for s in finished + [cur] for e in element_texts(s)} - ids_before
                self._placements.append((piece, produced))
        await self._finish(cur, cur_new, frame, exempt, adopt, cur_member)
        return cur.id

    def _new_subject(self, cur: SlideSpec, frame: Frame) -> Optional[Frame]:
        """The frame for overflowing content when the slide was titled by another facet (F-013 S2): a sparse
        definition slide took the next facet's content (absorb) and then filled up — the rest opens a slide titled by
        that facet, not a "part II" of the definition's title (test21: "What is Solar System?" II held "Formation and
        Structure"). A newly defined term alone is not enough: the replay of the 18 annotated lectures showed most are
        supporting terms ("Bolus", "SSID", "Downlink"), so naming subtopics stays the interpretation's job."""
        if cur.facet and frame.facet and not titles_match(cur.facet, frame.facet) \
                and not same_title(frame.facet, frame.topic):
            return frame
        return None

    # ---- structure (F-013 S2) -----------------------------------------------------------------------
    def _register(self, topic: str, parent: str, names) -> None:
        """Members of a set (announced list, classification) under the subtopic that holds the set."""
        if not parent or same_title(parent, topic) or not can_parent(parent):
            parent = ""
        for n in names:
            key = " ".join(sorted(title_key(n)))
            if key and len(n.split()) <= 6 and not same_title(n, parent or topic):
                self._children[key] = (topic, parent)
                self._children.move_to_end(key)
        while len(self._children) > MAX_CHILDREN:
            self._children.popitem(last=False)

    def _registered(self, name: str, topic: str) -> Optional[str]:
        """The subtopic a name was announced as a member of (None: not announced; "" = directly under the topic)."""
        hit = self._children.get(" ".join(sorted(title_key(name))))
        if hit is None or not titles_match(hit[0], topic):
            return None
        return hit[1]

    def _register_sets(self, it, frame: Frame) -> None:
        """The kinds a classification names ("Types of reproduction": sexual, asexual) become expected children of
        the subtopic it was taught under."""
        for a in it.acts:
            if a.act != "classification":
                continue
            names = [x for x in a.items.points if len(x.split()) <= 4] + [g.label for g in a.items.groups]
            if names:
                self._register(frame.topic, frame.facet, names)

    def _next_member(self, d: Decision, working: Optional[Working], pieces: list[Piece]) -> Decision:
        """The teacher leaves a member's slide ("Venus") for content the model files under the set ("Planets") that
        starts by defining another thing: the next member of the set ("Earth is the third planet ...", whose
        announcement was not heard), not a slide titled by the set."""
        if d.op != "continue" or working is None or not working.frame.parent or not working.frame.within(d.frame):
            return d
        first = pieces[0] if pieces else None
        if first is None or first.kind != "definition":
            return d
        term = clean(first.term)
        if not term or len(term.split()) > 4 or same_title(term, working.frame.parent) \
                or same_title(term, working.frame.facet) or same_title(term, d.frame.topic):
            return d
        return Decision("continue", Frame(d.frame.topic, term, parent=working.frame.parent), None,
                        d.reason + f"; the next member {term!r}")

    def _with_parent(self, d: Decision, working: Optional[Working]) -> Decision:
        """A new facet's place in the outline: an announced member of a set, or a sibling of the member on screen
        ("Political Causes" after "Social Causes" under "Causes")."""
        f = d.frame
        if d.op not in ("new", "continue", "retitle") or f.parent or same_title(f.facet, f.topic):
            return d
        parent = self._registered(f.facet, f.topic)
        if parent is None and working is not None and working.frame.parent and working.frame.same_topic(f) \
                and is_child_facet(f.facet, working.frame.parent):
            parent = working.frame.parent
        if not parent or same_title(parent, f.facet):
            return d
        return Decision(d.op, Frame(f.topic, f.facet, parent=parent), d.candidate, d.reason + f"; under {parent!r}")

    async def _set_part(self, frame: Frame, cur: SlideSpec) -> SlideSpec:
        """An empty next part of a frame's set (after a member's own slide): the set's title, the next part number."""
        first = self._first_part(frame, cur)
        await self._number_first_part(frame, cur)
        nxt = frame_slide(frame.topic, frame.facet, continuation_of=cur.id, parent=frame.parent)
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
        return max(parts + [cur.part or 1]) \
                # is no part of the set

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
    async def _on_figure(self, query: str) -> None:
        """F-013 S4: the teacher turns to a figure ("let's look at the block diagram of STM32"): it is fetched at once
        (the teacher's own files first, then the web) for the slide being built, whatever the slide holds; it may
        push content to the next part, like an image the teacher placed."""
        target = self._spec(self._open_cue_slide() or self._working_id or "") or self.deck.live
        meta = self._meta.get(target.id) if target is not None else None
        if target is None or meta is None or meta.is_title:
            log.info("figure %r asked: no slide to put it on", query)
            return
        fv = self._fv(meta.frame)
        fv.removed = False  # asked for: the teacher wants a picture here after all
        fv.pending = query
        await self._request_image(target.id, query, "diagram", fv, "asked")
        log.info("figure asked: %r for %r", query, target.title)

    def _visual_topic(self, frame: Frame) -> str:
        """The kind of picture ("photo" / "diagram") this frame's topic has shown already, "" = none: a topic the
        model judged worth seeing (its hint found an image)."""
        for f, v in self._visuals:
            if f.same_topic(frame) and v.image is not None:
                return v.kind or "photo"
        return ""

    def _item_cards(self, spec: SlideSpec) -> list[DefinitionBlock]:
        """The concepts shown side by side as cards (2-6 definitions), [] when the slide is not that layout (one member
        card keeps the slide's single image)."""
        defs = [b for b in spec.blocks if b.type == "definition" and not b.provisional]
        return defs if 2 <= len(defs) <= 6 else []

    async def _consider_items(self, spec: SlideSpec, meta: SlideMeta, fv: FrameVisual) -> bool:
        """F-013 S4 (D1, user 2026-10-17: "describing each planet, each planet's image must be loaded"): concept
        cards of concrete things in a topic that shows pictures get one picture each (all or none). True when this
        slide is such a slide (no single image then)."""
        defs = self._item_cards(spec)
        kind = (fv.kind if fv.image is not None else "") or self._visual_topic(meta.frame) or \
            (fv.hint.kind if fv.hint is not None and fv.hint.query else "")
        if not defs or not kind or fv.removed:
            return False
        if not all(names_an_object(d.term) and len(d.term.split()) <= 4 for d in defs):
            return False
        have = self._items.setdefault(spec.id, {})
        for d in defs:
            if d.id in have or d.image is not None or (spec.id, d.id) in self._item_asked:
                continue
            self._item_asked.add((spec.id, d.id))
            # a card's picture is the lead image of the term's own article: a photo, whatever the topic's kind
            await self._request_image(spec.id, item_query(d.term, meta.frame.facet), "photo", fv, f"item:{d.id}")
        return True

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
        if await self._consider_items(spec, meta, fv):
            return
        hint = fv.hint
        if hint is None and fv.image is None and not fv.removed:
            hint = sibling_hint(meta.frame.facet, [(f.facet, v.hint) for f, v in self._visuals
                                                   if v.hint is not None and f.same_topic(meta.frame)
                                                   and not f.same(meta.frame)])
            if hint is not None:
                log.info("image hint %r for %r from its sibling subtopic", hint.query, spec.title)
            # F-013 S4 (D1): a subtopic naming a thing, in a topic whose pictures were shown already (test13:
            # Hypothalamus, Tectum, Pons had none while Forebrain / Hindbrain had theirs)
            kind = self._visual_topic(meta.frame) if hint is None else ""
            if kind and meta.frame.facet and not same_title(meta.frame.facet, meta.frame.topic) \
                    and names_a_thing(meta.frame.facet) and len(meta.frame.facet.split()) <= 4:
                hint = VisualHint(query=meta.frame.facet, kind=kind)
                log.info("image hint %r for %r: a thing in a topic with pictures", hint.query, spec.title)
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
        meta = self._meta.get(slide_id)
        # F-013 S4 (D2): an image shown under another topic is not offered again (test30: 13 repeats); within the
        # same topic it may come back (a continuation, or the same picture still about it: user 2026-10-17)
        elsewhere = {i for i, topics in self._image_topics.items()
                     if meta is not None and not any(titles_match(t, meta.frame.topic) for t in topics)}
        # F-013 S5: the human body is drawn, never photographed ("Mouth" under "Digestive system")
        pictorial = body_subject(query, *((meta.frame.topic, meta.frame.facet) if meta is not None else ()))
        await self.bus.publish(ImageRequested(request_id=rid, slide_id=slide_id, query=query,
                                              kind=kind if kind in ("photo", "diagram") else "photo",
                                              exclude=sorted(fv.shown_ids | elsewhere), deeper=deeper, reason=reason,
                                              pictorial=pictorial))

    async def _show_image(self, spec: SlideSpec, image: ImageBlock, teacher: bool, remember: bool = True) -> bool:
        """Put the image on the slide. Automatic: only when the content still fits at the default type size.
        The teacher's choice: the type may shrink; if even that is not enough, the last content moves to the next
        part (the image never shrinks the content out of sight). Every image shown joins the slide's history
        (the teacher's previous / next arrows) unless it is a step through that history."""
        if sim_of(spec) is not None:  # F-014: one visual column; the simulation keeps it
            if teacher:
                await self.bus.publish(SimulationNotice(slide_id=spec.id,
                                                        text="This slide shows a simulation: remove it to add an image"))
            return False
        new = with_image(spec, image.model_copy(update={"id": new_id()}))
        if not teacher and not fits_unshrunk(new):
            log.info("no room for an image on %r", spec.title)
            return False
        meta = self._meta.get(spec.id)
        if meta is not None and image.image_id and image.origin == "auto":
            self._image_topics.setdefault(image.image_id, set()).add(meta.frame.topic)
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
        tail = frame_slide(meta.frame.topic, meta.frame.facet, continuation_of=head.id, parent=meta.frame.parent)
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
        if reason.startswith("item:"):
            await self._on_item_image(slide_id, reason[5:], ev)
            return
        if norm_query(fv.pending) == norm_query(ev.query):
            fv.pending = ""
        blocks = [self._block(i, ev.query) for i in ev.images]
        elsewhere = {i for i, topics in self._image_topics.items()
                     if not any(titles_match(t, meta.frame.topic) for t in topics)}
        blocks = [b for b in blocks if b.image_id not in elsewhere]  # a cached answer skips the exclude list
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
        if reason == "asked":  # F-013 S4: the figure the teacher turned to, on its slide (or where the frame went)
            target = spec if spec is not None else self._spec(self._working_id or "")
            blocks[0] = blocks[0].model_copy(update={"large": True})
            if target is not None and await self._show_image(target, blocks[0], teacher=True):
                fv.image, fv.query, fv.kind = blocks[0], ev.query, ev.kind
                fv.shown_ids.add(blocks[0].image_id)
                meta_t = self._meta.get(target.id)
                if meta_t is not None and blocks[0].image_id:
                    self._image_topics.setdefault(blocks[0].image_id, set()).add(meta_t.frame.topic)
                log.info("figure %r on %r: %s", ev.query, target.title, ev.images[0].get("title", ""))
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

    async def _on_item_image(self, slide_id: str, block_id: str, ev: ImageReady) -> None:
        """F-013 S4: one concept card's picture arrived. When every card of the slide has its answer: all pictures
        go on together if each card has one and the slide still fits at its type size, else none (a row where some
        cards have a picture and some not looks broken)."""
        have = self._items.setdefault(slide_id, {})
        if not ev.images and ev.reason not in ("no relevant image", "no usable candidates", "no match (cached)"):
            # a timeout / failed download says nothing about the picture: searched again on the slide's next update
            self._item_asked.discard((slide_id, block_id))
            log.info("concept picture %r: %s, will search again", ev.query, ev.reason)
            return
        img = next((i for i in ev.images if i["id"] not in self._image_topics), None)  # not shown elsewhere
        have[block_id] = ItemImage(url=f"/media/{img['id']}.jpg", alt=img.get("alt") or ev.query, image_id=img["id"],
                                   aspect=round((img.get("width") or 4) / (img.get("height") or 3), 3)) if img else None
        spec = self._spec(slide_id)
        if spec is None:
            return
        defs = self._item_cards(spec)
        if not defs or any(d.id not in have for d in defs if d.image is None):
            return  # still waiting for some
        if any(have.get(d.id) is None and d.image is None for d in defs):
            log.info("concept pictures on %r: not every card has one (%d of %d): none", spec.title,
                     sum(1 for d in defs if have.get(d.id) is not None or d.image is not None), len(defs))
            if any(d.image is not None for d in defs):  # a card joined later without one: the others give theirs up
                await self._commit(spec.model_copy(update={"blocks": [
                    b.model_copy(update={"image": None}) if b.type == "definition" else b for b in spec.blocks]}))
            return
        blocks = [b.model_copy(update={"image": have[b.id]}) if b.type == "definition" and b.image is None
                  and have.get(b.id) is not None and b in defs else b for b in spec.blocks]
        new = spec.model_copy(update={"blocks": blocks})
        if not fits_unshrunk(new):
            log.info("concept pictures on %r: no room", spec.title)
            return
        await self._commit(new)
        meta = self._meta.get(slide_id)
        for d in defs:
            if have.get(d.id) is not None and meta is not None:
                self._image_topics.setdefault(have[d.id].image_id, set()).add(meta.frame.topic)
        log.info("concept pictures on %r: %s", spec.title, ", ".join(d.term for d in defs))

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
            # large: a figure from the teacher's notes (F-013 S5), shown in the wide column like an asked figure
            block = ImageBlock(url=f"/media/{image_id}.jpg", alt=str(args.get("alt") or spec.title)[:120],
                               image_id=image_id, aspect=aspect, origin="teacher", large=bool(args.get("large")))
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
