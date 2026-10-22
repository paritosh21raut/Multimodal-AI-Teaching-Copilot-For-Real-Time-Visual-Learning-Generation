"""Typed domain events. Summary contract: docs/contracts/events.md (keep in sync)."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from copilot.core.interpretation import Interpretation


def new_id() -> str:
    return uuid.uuid4().hex[:12]


class Lifecycle(str, Enum):
    STARTING = "starting"
    READY = "ready"
    LIVE = "live"
    PAUSED = "paused"
    ENDING = "ending"
    ENDED = "ended"
    FAILED = "failed"


class Event(BaseModel):
    """Base class for all events. Immutable."""

    model_config = ConfigDict(frozen=True)

    # Ephemeral events (e.g. audio levels) are not written to the event log.
    ephemeral: ClassVar[bool] = False

    id: str = Field(default_factory=new_id)
    ts: float = Field(default_factory=time.time)
    session_id: str = ""

    @property
    def type(self) -> str:
        return type(self).__name__


class TranscriptSegment(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=new_id)
    text: str
    start: float  # seconds since lecture start
    end: float
    confidence: float = 1.0
    language: str = "en"
    source: Literal["mic", "sim"] = "mic"
    # Test-only annotations from simulator scripts (@expect); never used by production logic.
    expect: dict[str, str] = Field(default_factory=dict)


CommandKind = Literal[
    "start", "end", "pause", "resume", "next", "prev", "goto",  # pause: a break, speech is not interpreted
    "blank", "unblank",  # (pin / unpin removed, user 2026-10-06: Pause, Blank and navigating back cover it)
    "force_new_slide", "resolve_concern",
    "remove_image", "change_image", "set_image",  # F-007b, args {slide_id[, image_id]}
    "image_prev", "image_next",                   # step through the images this slide has shown, args {slide_id}
    "zoom_image", "unzoom_image",                 # the slide's image full screen on the display, args {slide_id}
    "edit_text", "delete_item", "add_point",      # live slide editing, F-008: {slide_id, item_id[, text]} / {slide_id, text}
    "show_equation",                              # a standard equation from the library on the live slide, {id} (F-013 S3)
    "share_start", "share_stop",                  # share /view with students over a Cloudflare quick tunnel (F-008)
    "set_theme",                                  # slide theme mid-lecture, args {theme: light | dark} (F-009)
    "set_mode",                                   # performance mode, args {mode: standard | high} (F-013, app/modes.py)
    "notes_open", "notes_page", "notes_remove",  # the teacher's PDF notes in /control (F-009)
    "notes_follow",  # removed (F-013, nothing handles it); kept so that older session logs still decode
    # lecture materials + past lectures (F-010): create {items, lectures, current}; rename {id, name};
    # share {id, on}; remove {id}; show {id} (a summary / key-concepts slide again); lecture_hide {id}
    "materials_create", "materials_rename", "materials_share", "materials_remove", "materials_show", "lecture_hide",
    # chapters (F-010b): create {name, start?}; rename {id, name}; move {id, index}; delete {id};
    # lecture_move {id, chapter, start?}; notes_project {on}: the notes page on the projector
    "chapter_create", "chapter_rename", "chapter_move", "chapter_delete", "lecture_move", "notes_project",
    "notes_use", "notes_private",  # F-012: study material per file
    # quiz + test (F-011, assess/service.py has the args)
    "assess_create", "assess_edit", "assess_add", "assess_delete", "assess_regen", "assess_open", "assess_start",
    "assess_pause", "assess_resume", "assess_hold", "assess_next", "assess_end", "assess_close", "assess_discard",
    "assess_release",
    # Concept Simulation (F-014): the engine applies them to the simulation block of {slide_id}; sim_show {template}
    # puts one on the live slide; sim_set {slide_id, slot, value} | {slide_id, speed}; sim_toggle {slide_id, element,
    # on?}; sim_pick {slide_id, template}; sim_full {slide_id, on} is a display flag (the Deck, like zoom_image)
    "sim_show", "sim_set", "sim_play", "sim_pause", "sim_step", "sim_reset", "sim_toggle", "sim_pick", "sim_remove",
    "sim_full",
    # F-015 L2a, a live scene: scene_look {slide_id, id, icon | image | own} (a body's picture), scene_frame
    # {slide_id, id} (the relative world seen from that body; "" = the ground)
    "scene_look", "scene_frame",
    # F-016: imagine_mode {on: bool} (/control Imagine / End: every picturable line is drawn until End)
    "imagine_mode",
    # F-014 S1: sim_end = Back to slides (simulation mode ends, the recap follows); sim_accept / sim_dismiss {id}: the
    # Suggest chip; set_simulations {setting: auto | suggest | off} (kept in data/preferences.json)
    "sim_end", "sim_accept", "sim_dismiss", "set_simulations",
    # F-014 S3: a process template's next / previous step {slide_id} (names that step: the teacher chose it)
    "sim_next", "sim_prev",
]


class Command(BaseModel):
    model_config = ConfigDict(frozen=True)

    kind: CommandKind
    args: dict[str, Any] = Field(default_factory=dict)
    origin: Literal["terminal", "control", "system"] = "system"


class LifecycleChanged(Event):
    state: Lifecycle
    reason: str = ""


class TranscriptFinal(Event):
    segment: TranscriptSegment
    stt_latency_ms: Optional[float] = None  # utterance end detected -> text ready (mic only)
    utterance: int = 0  # F-013 S1b: the segmenter's utterance number (mic / WAV); 0 = none (simulator)


class TranscriptPartial(Event):
    """F-013 S1b: what is being said right now (the utterance so far, a fast model), before the utterance ends.
    `stable` is the part two consecutive passes agree on (Whisper revises its last words); only it is used for the
    instant display. Superseded by the TranscriptFinal of the same utterance."""
    utterance: int
    start: float
    text: str            # the latest hypothesis
    stable: str = ""     # the agreed prefix of `text`
    sentences: list[tuple[str, float]] = Field(default_factory=list)  # sentences of `stable`, lecture time each starts
    latency_ms: float = 0.0  # snapshot taken -> published
    infer_ms: float = 0.0    # of which the model pass


class VocabularyChanged(Event):
    """F-013 S3: the lecture glossary grew (understanding.glossary); speech primes Whisper with these terms."""
    terms: list[str] = Field(default_factory=list)


class LiveCue(Event):
    """F-013 S1b: structure heard in a partial transcript (understanding.cues), for the instant display only."""
    utterance: int
    announce: str = ""
    announce_rule: str = ""
    compare: list[str] = Field(default_factory=list)
    list_head: str = ""
    list_items: list[str] = Field(default_factory=list)
    list_count: int = 0
    item: str = ""
    term: str = ""          # "X" of "X is ..." being said
    definition: str = ""    # what has been said of its definition so far
    start: float = -1.0     # lecture time the sentence with the cue starts (-1 = unknown)


class AudioLevel(Event):
    ephemeral: ClassVar[bool] = True
    rms: float
    speaking: bool       # inside an utterance (segmenter state, includes the end-of-utterance hangover)
    voice: bool = False  # VAD heard speech in this window (raw frames; drives pause detection)


class AudioDeviceLost(Event):
    detail: str


class UtteranceDropped(Event):
    start: float
    end: float
    reason: str
    text: str = ""


class CommandReceived(Event):
    command: Command


class StateChanged(Event):
    version: int
    changes: list[str] = Field(default_factory=list)


class SlidePatch(Event):
    """A new or updated slide. `spec` is a SlideSpec dump (core does not import presentation)."""
    slide_id: str
    version: int
    op: Literal["add", "update"]
    spec: dict[str, Any]


class DeckState(Event):
    """Which slide is on screen and the teacher's display flags."""
    live_id: Optional[str]
    slide_ids: list[str]
    following: bool  # live slide auto-advances to new slides
    blank: bool
    zoom: Optional[str] = None  # slide whose image fills the display (teacher clicked it in /control)
    sim_full: Optional[str] = None  # slide whose simulation fills the display (F-014, the teacher's Full stage)
    sim_mode: Optional[str] = None  # F-014 S1: the simulation slide of a running simulation mode (no new slides)
    imagine: bool = False  # F-016: Imagine Mode is on (every picturable line is drawn until the teacher's End)


UtteranceKind = Literal["content", "classroom_management", "meta", "filler", "question_to_class"]


class UtteranceClassified(Event):
    segment_id: str
    kind: UtteranceKind
    maybe_meta: bool = False
    rule: str = ""  # which filter rule decided (debugging/evaluation)


class ConceptSignal(Event):
    segment_id: str
    shift_score: float          # smoothed 1 - cos(utterance, concept centroid); 0 for the first utterance
    topic_shift: float = 0.0    # 1 - cos(utterance, slow topic centroid)
    keyphrases: list[str] = Field(default_factory=list)
    cues: list[str] = Field(default_factory=list)
    boundary: bool = False      # strong cue or shift above threshold at utterance start
    # F-013 spoken structure cues (understanding.cues), for the instant display; "" / [] = none
    announce: str = ""          # announced topic / subtopic name ("A vs B" for a comparison)
    announce_rule: str = ""     # how it was announced (cues.Cue.rule): "section" / "ordinal" = one of a numbered series
    compare: list[str] = Field(default_factory=list)      # members of an announced comparison
    list_head: str = ""         # "X" of "X is classified into ..."
    list_items: list[str] = Field(default_factory=list)   # members heard in this line
    list_count: int = 0         # announced number of members, 0 = not said
    item: str = ""              # one member said on its own ("The second type is ...")
    figure: str = ""            # F-013 S4: a figure the teacher turns to, as an image search ("STM32 block diagram")
    utterance: int = 0          # F-013 S1b: TranscriptFinal.utterance (links the partials' live cues to this line)
    start: float = -1.0         # lecture time the line starts (-1 = unknown): what came before / after a cue


class InterpretRequested(Event):
    request_id: str
    reason: str
    segment_ids: list[str]
    prompt_tokens: int = 0      # approximate, as enforced by the budget


class InterpretationReady(Event):
    request_id: str
    interpretation: Interpretation
    segment_ids: list[str]      # line n of the request = segment_ids[n - 1]
    provider: str = ""          # router entry name; "" for a deterministic fallback
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str = ""
    slide_refs: dict[str, str] = Field(default_factory=dict)  # CURRENT SLIDE refs the prompt showed (revisions)
    reference: str = ""         # the teacher's reference passage the prompt held, "<file> p.N" (F-012); "" = none


class LLMCallFailed(Event):
    provider: str
    error: str
    will_retry: bool


class ConcernRaised(Event):
    concern: dict[str, Any]     # Concern dump (core.state.Concern)


class ConcernResolved(Event):
    concern_id: str
    status: Literal["accepted", "kept", "dismissed"]


class CorrectionPlaced(Event):
    """F-013 S3 (E1): what the slides show for a concern, after the engine placed it (and after each switch).
    correction: the corrected words are on the slide (switched there); said: the teacher's words are (Show correction
    switches them, or replaces the items that say it in other words); rewritten: the model already wrote the correct
    statement in its own words (nothing to switch); absent: neither version is on the slides."""
    concern_id: str
    shows: Literal["correction", "said", "rewritten", "absent"]
    elements: int = 0  # slide elements the switch changes


class SlideContextChanged(Event):
    """Short summary of the slide receiving content, for the interpretation prompt (presentation → store).
    refs: item reference used in the text ("S1") -> "slide_id/item_id", so revisions can be applied exactly."""
    text: str
    refs: dict[str, str] = Field(default_factory=dict)


class SlideOverflow(Event):
    """The display's auto-fit could not fit this slide even at the smallest type step."""
    slide_id: str
    version: int = 0


class ImageRequested(Event):
    """Presentation asks the image service for pictures (F-007b). Never blocks a slide."""
    request_id: str
    slide_id: str
    query: str
    kind: Literal["photo", "diagram"] = "photo"
    exclude: list[str] = Field(default_factory=list)  # image ids already offered for this topic
    deeper: bool = False   # past the first results (Change image after the candidates ran out)
    # auto | change | asked (F-013 S4: the teacher asked for this figure, "the block diagram of STM32") |
    # item:<block id> (F-013 S4: the picture of one concept on a concept-column slide)
    reason: str = "auto"
    pictorial: bool = False  # F-013 S5: a human-body subject, drawings only (no photographs of the body)


class ImageReady(Event):
    """The search result: up to 3 cached images (visuals.cache.CachedImage dumps, best first) or none + why."""
    request_id: str
    slide_id: str
    query: str
    kind: str = "photo"
    images: list[dict[str, Any]] = Field(default_factory=list)
    reason: str = ""        # why there is none ("timeout", "no relevant image", "network: ...")
    cached: bool = False
    seconds: float = 0.0


class ImageChoices(Event):
    """The images a slide has shown, for the teacher's previous / next arrows in /control (index into count)."""
    slide_id: str
    index: int
    count: int


class ShareChanged(Event):
    """Sharing the live slide with students (F-008): the public /view link of the Cloudflare quick tunnel."""
    state: Literal["off", "starting", "on", "failed"]
    url: str = ""     # <tunnel>/view while on
    detail: str = ""  # progress ("downloading cloudflared") or why it failed


class ThemeChanged(Event):
    """The slide theme changed (F-009): the display, the students' pages and the /control preview repaint."""
    theme: Literal["light", "dark"]


class ModeChanged(Event):
    """The performance mode in effect (F-013, app/modes.py): standard (fewer LLM calls) or high (every sentence)."""
    mode: Literal["standard", "high"]


class NotesState(Event):
    """The teacher's PDF notes in /control (F-009): the list, the open one, its page.
    Control only — never the projector or the students."""
    ephemeral: ClassVar[bool] = True  # a view state, not lecture history
    docs: list[dict[str, Any]] = Field(default_factory=list)  # [{id, name, pages, has_text, added}]
    open: str = ""
    page: int = 0
    pages: int = 0
    projecting: bool = False  # the open page is on the projector (F-010b)
    # reference material (F-012): docs carry active / private; files being indexed (id -> 0..1); the passage the
    # last slide used ("<file> p.N"); a refused toggle ("at most 10 files ...")
    indexing: dict[str, float] = Field(default_factory=dict)
    used: str = ""
    notice: str = ""


class NotesProjected(Event):
    """The teacher put a page of their notes on the projector (F-010b), or took it off. Goes to the display, the
    students and /control; only this page is served to them (GET /api/notes/shown/...)."""
    ephemeral: ClassVar[bool] = True
    on: bool = False
    doc_id: str = ""
    page: int = 0
    name: str = ""


class MaterialsState(Event):
    """The lecture materials (F-010): what was made / is being made, for /control; the shared PDFs for students."""
    ephemeral: ClassVar[bool] = True  # a view state; the materials themselves live in data/materials
    items: list[dict[str, Any]] = Field(default_factory=list)   # store.Material.public()
    shared: list[dict[str, Any]] = Field(default_factory=list)  # [{id, name}] PDFs students may download
    current: dict[str, Any] = Field(default_factory=dict)       # this lecture: {id, title, chapter, test_run}
    llm: bool = False         # an LLM is configured (summary, concepts, notes, assignment need it)
    lectures_changed: int = 0  # bumps when the past-lecture list changed (a lecture hidden / moved)
    chapters: list[dict[str, Any]] = Field(default_factory=list)  # [{id, name, number, label}] in order (F-010b)
    last_chapter: str = ""    # preselected on the start card


class AssessState(Event):
    """The quiz / test (F-011). `control` (everything, the answer keys included) goes to /control only; `public`
    (never a key before it is due) to /display and the students' pages. Both empty: none open. Saved in
    data/assessments, so ephemeral here."""
    ephemeral: ClassVar[bool] = True
    control: dict[str, Any] = Field(default_factory=dict)
    public: dict[str, Any] = Field(default_factory=dict)
    notice: str = ""   # why the teacher's last action was refused (control only)
    llm: bool = False  # questions can be written (an LLM is configured)
    now: float = 0.0   # server clock when made (pages count `left` down from their receipt)


VisualKind = Literal["simulation", "scene", "story"]  # scene: F-015 Live Scene Engine


class RepresentationIntent(Event):
    """What a stretch of the lecture asks for beyond slide text (RULES #6): modes plug in here and never change audio,
    STT or understanding. Produced by deterministic detectors (simulation.detector, F-014 S0) and later by the
    interpretation's closed-list field (S2); the presentation engine's policy decides what is done with it.
    `values` are plain dicts (core does not import the simulation package): slot -> {value, unit, said, ok, why}."""
    segment_ids: list[str] = Field(default_factory=list)
    visual_kind: VisualKind = "simulation"
    template: str = ""          # template id; "" = values for whichever simulation is open
    # cue: "consider a block ..."; setup: a template noun alone; score (S1): a strong setup without a cue (a Suggest
    # chip); values: quantities only; end (S1): "let's get back to the slides" (simulation mode ends); edit (F-015): a
    # line said while a scene is open (the scene controller decides whether it changes the scene)
    strength: Literal["cue", "setup", "score", "values", "end", "edit"] = "cue"
    values: dict[str, dict[str, Any]] = Field(default_factory=dict)
    reveal: list[str] = Field(default_factory=list)  # element ids the line names ("friction opposes it")
    origin: Literal["cue", "policy", "llm", "teacher"] = "cue"
    text: str = ""              # the line (logs, evaluation)


class SimulationNotice(Event):
    """/control only (F-014): something about a simulation the teacher should know ("heard 95° - not used")."""
    ephemeral: ClassVar[bool] = True
    slide_id: str = ""
    text: str


class SimulationModeChanged(Event):
    """F-014 S1: simulation mode started (a simulation on its own slide; no new slides, content slides unchanged,
    interpretations collected) or ended (slides resume; the recap's slides, if anything worth keeping was said)."""
    on: bool
    slide_id: str = ""            # the simulation slide
    template: str = ""
    reason: str = ""              # "spoken cue", "Back to slides", "removed", "'let's get back to the slides'", ...
    recap_ids: list[str] = Field(default_factory=list)
    kept: int = 0                 # recap items kept / dropped as parameter talk
    dropped: int = 0


class SimulationSuggestion(Event):
    """F-014 S1: a /control chip "Show the <name> simulation?" (setting Suggest, a setup with its quantities and no
    spoken cue, or the same template's setup heard twice in a topic);
    active = False when it is accepted, dismissed or expired."""
    id: str
    template: str = ""
    name: str = ""
    text: str = ""                # the line that suggested it
    active: bool = True


class SimulationSettingChanged(Event):
    """F-014 S1: Auto (a spoken cue shows a simulation) | Suggest (a /control chip) | Off; the teacher's switch."""
    setting: Literal["auto", "suggest", "off"]


class ErrorRaised(Event):
    component: str
    error: str
    fatal: bool = False


EVENT_TYPES: dict[str, type[Event]] = {
    cls.__name__: cls
    for cls in (
        LifecycleChanged, TranscriptFinal, TranscriptPartial, LiveCue, AudioLevel, AudioDeviceLost, UtteranceDropped,
        CommandReceived, StateChanged, SlidePatch, DeckState, ErrorRaised,
        UtteranceClassified, ConceptSignal, InterpretRequested, InterpretationReady, LLMCallFailed,
        ConcernRaised, ConcernResolved, SlideContextChanged, SlideOverflow, ImageRequested, ImageReady,
        ImageChoices, ThemeChanged, VocabularyChanged, RepresentationIntent, SimulationModeChanged,
        SimulationSuggestion, SimulationSettingChanged,
    )
}


def register_event(cls: type[Event]) -> type[Event]:
    """Decorator for events defined in other packages so the event log can decode them."""
    EVENT_TYPES[cls.__name__] = cls
    return cls


def decode_event(type_name: str, payload: str) -> Optional[Event]:
    cls = EVENT_TYPES.get(type_name)
    return cls.model_validate_json(payload) if cls else None
