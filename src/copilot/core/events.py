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
    "start", "end", "pause", "resume", "next", "prev", "goto",
    "freeze", "unfreeze", "pin", "unpin", "blank", "unblank",
    "force_new_slide", "resolve_concern",
    "remove_image", "change_image", "set_image",  # F-007b, args {slide_id[, image_id]}
    "image_prev", "image_next",                   # step through the images this slide has shown, args {slide_id}
    "zoom_image", "unzoom_image",                 # the slide's image full screen on the display, args {slide_id}
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
    pinned: bool
    frozen: bool
    blank: bool
    zoom: Optional[str] = None  # slide whose image fills the display (teacher clicked it in /control)


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


class LLMCallFailed(Event):
    provider: str
    error: str
    will_retry: bool


class ConcernRaised(Event):
    concern: dict[str, Any]     # Concern dump (core.state.Concern)


class ConcernResolved(Event):
    concern_id: str
    status: Literal["accepted", "kept", "dismissed"]


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
    reason: str = "auto"   # auto | change


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


class ErrorRaised(Event):
    component: str
    error: str
    fatal: bool = False


EVENT_TYPES: dict[str, type[Event]] = {
    cls.__name__: cls
    for cls in (
        LifecycleChanged, TranscriptFinal, AudioLevel, AudioDeviceLost, UtteranceDropped,
        CommandReceived, StateChanged, SlidePatch, DeckState, ErrorRaised,
        UtteranceClassified, ConceptSignal, InterpretRequested, InterpretationReady, LLMCallFailed,
        ConcernRaised, ConcernResolved, SlideContextChanged, SlideOverflow, ImageRequested, ImageReady,
        ImageChoices,
    )
}


def register_event(cls: type[Event]) -> type[Event]:
    """Decorator for events defined in other packages so the event log can decode them."""
    EVENT_TYPES[cls.__name__] = cls
    return cls


def decode_event(type_name: str, payload: str) -> Optional[Event]:
    cls = EVENT_TYPES.get(type_name)
    return cls.model_validate_json(payload) if cls else None
