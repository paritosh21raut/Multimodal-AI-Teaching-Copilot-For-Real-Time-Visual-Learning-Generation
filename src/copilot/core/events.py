"""Typed domain events. Summary contract: docs/contracts/events.md (keep in sync)."""
from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Literal, Optional

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


class CommandReceived(Event):
    command: Command


class StateChanged(Event):
    version: int
    changes: list[str] = Field(default_factory=list)


class ErrorRaised(Event):
    component: str
    error: str
    fatal: bool = False


EVENT_TYPES: dict[str, type[Event]] = {
    cls.__name__: cls
    for cls in (LifecycleChanged, TranscriptFinal, CommandReceived, StateChanged, ErrorRaised)
}


def register_event(cls: type[Event]) -> type[Event]:
    """Decorator for events defined in other packages so the event log can decode them."""
    EVENT_TYPES[cls.__name__] = cls
    return cls


def decode_event(type_name: str, payload: str) -> Optional[Event]:
    cls = EVENT_TYPES.get(type_name)
    return cls.model_validate_json(payload) if cls else None
