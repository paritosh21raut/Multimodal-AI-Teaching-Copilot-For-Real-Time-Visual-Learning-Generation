"""LectureState and its single writer. Contract: docs/contracts/lecture-state.md."""
from __future__ import annotations

import logging
from typing import Literal, Optional

from pydantic import BaseModel, Field

from copilot.core.bus import EventBus
from copilot.core.events import (
    CommandReceived,
    Event,
    Lifecycle,
    LifecycleChanged,
    StateChanged,
    TranscriptFinal,
    new_id,
)

log = logging.getLogger(__name__)

MAX_TOPICS = 20
MAX_SUBTOPICS = 8


class LectureSetup(BaseModel):
    subject: str = ""
    grade_level: str = ""
    expected_topic: str = ""
    output_language: str = "en"
    theme: Literal["light", "dark"] = "light"


class TopicNode(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    summary: str = ""
    subtopics: list["TopicNode"] = Field(default_factory=list)
    first_seen: float = 0.0
    last_seen: float = 0.0


class Concern(BaseModel):
    id: str = Field(default_factory=new_id)
    claim: str
    issue: str
    suggested_correction: str = ""
    confidence: float = 0.5
    status: Literal["open", "accepted", "kept", "dismissed"] = "open"
    segment_id: str = ""


class LectureStats(BaseModel):
    segments: int = 0
    words: int = 0
    llm_calls: int = 0
    fallbacks: int = 0


class LectureState(BaseModel):
    session_id: str
    version: int = 0
    lifecycle: Lifecycle = Lifecycle.STARTING
    setup: LectureSetup = Field(default_factory=LectureSetup)
    level_estimate: str = ""
    subject_estimate: str = ""
    outline: list[TopicNode] = Field(default_factory=list)
    current_topic_id: Optional[str] = None
    current_subtopic_id: Optional[str] = None
    rolling_summary: str = ""
    concerns: list[Concern] = Field(default_factory=list)
    stats: LectureStats = Field(default_factory=LectureStats)
    lecture_clock_s: float = 0.0  # end time of the latest transcript segment


class LectureStateStore:
    """The only component allowed to mutate LectureState (ADR-0004).

    Subscribes to events, applies them, bumps the version, publishes StateChanged.
    Readers get deep copies via snapshot().
    """

    def __init__(self, bus: EventBus, session_id: str, setup: Optional[LectureSetup] = None) -> None:
        self._bus = bus
        self._state = LectureState(session_id=session_id, setup=setup or LectureSetup())

    def attach(self) -> None:
        self._bus.subscribe(
            "state_store",
            self._on_event,
            [LifecycleChanged, TranscriptFinal, CommandReceived],
        )

    def snapshot(self) -> LectureState:
        return self._state.model_copy(deep=True)

    @property
    def version(self) -> int:
        return self._state.version

    async def _on_event(self, event: Event) -> None:
        changes = self._apply(event)
        if changes:
            self._state.version += 1
            await self._bus.publish(StateChanged(version=self._state.version, changes=changes))

    def _apply(self, event: Event) -> list[str]:
        s = self._state
        if isinstance(event, LifecycleChanged):
            if s.lifecycle != event.state:
                s.lifecycle = event.state
                return ["lifecycle"]
        elif isinstance(event, TranscriptFinal):
            seg = event.segment
            s.stats.segments += 1
            s.stats.words += len(seg.text.split())
            s.lecture_clock_s = max(s.lecture_clock_s, seg.end)
            return ["stats"]
        elif isinstance(event, CommandReceived):
            # Lifecycle commands are executed by the app; slide commands by the planner (M4).
            return []
        return []
