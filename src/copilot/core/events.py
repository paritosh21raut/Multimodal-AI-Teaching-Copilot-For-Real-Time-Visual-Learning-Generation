"""Typed domain events. Summary contract: docs/contracts/events.md (keep in sync)."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


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
    speaking: bool


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


class ErrorRaised(Event):
    component: str
    error: str
    fatal: bool = False


EVENT_TYPES: dict[str, type[Event]] = {
    cls.__name__: cls
    for cls in (
        LifecycleChanged, TranscriptFinal, AudioLevel, AudioDeviceLost, UtteranceDropped,
        CommandReceived, StateChanged, SlidePatch, DeckState, ErrorRaised,
    )
}


def register_event(cls: type[Event]) -> type[Event]:
    """Decorator for events defined in other packages so the event log can decode them."""
    EVENT_TYPES[cls.__name__] = cls
    return cls


def decode_event(type_name: str, payload: str) -> Optional[Event]:
    cls = EVENT_TYPES.get(type_name)
    return cls.model_validate_json(payload) if cls else None
