"""Planner: the deterministic slide-frame decision for one interpretation (F-005). Pure; no I/O.

A new concept is not a new slide: the planner compares the interpretation's frame (topic, facet) with the
working slide and decides update / continue / new / retitle / noop. A topic change needs confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from copilot.core.interpretation import Interpretation
from copilot.core.memory import titles_match

Op = Literal["noop", "update", "continue", "new", "retitle"]


@dataclass(frozen=True)
class Frame:
    topic: str
    facet: str  # subtopic, or the topic itself when there is none

    @classmethod
    def of(cls, it: Interpretation) -> "Frame":
        return cls(it.topic, it.subtopic or it.topic)

    def same_topic(self, other: "Frame") -> bool:
        return titles_match(self.topic, other.topic)

    def same(self, other: "Frame") -> bool:
        return self.same_topic(other) and titles_match(self.facet, other.facet)


@dataclass(frozen=True)
class Working:
    """What the planner needs to know about the slide currently receiving content."""
    frame: Frame
    has_content: bool   # teacher content on it (not only a title or a provisional item)
    is_title: bool = False


@dataclass(frozen=True)
class Signal:
    shift_score: float
    boundary: bool


@dataclass(frozen=True)
class Decision:
    op: Op
    frame: Frame
    candidate: Optional[str]  # unconfirmed new topic carried to the next interpretation
    reason: str


def topic_confirmed(it: Interpretation, signals: Sequence[Signal], candidate: Optional[str],
                    shift_threshold: float) -> tuple[bool, str]:
    if any(s.boundary for s in signals):
        return True, "boundary cue/shift"
    if any(s.shift_score >= shift_threshold for s in signals):
        return True, "shift score"
    if candidate is not None and titles_match(candidate, it.topic):
        return True, "two interpretations agree"
    return False, ""


def decide(working: Optional[Working], it: Interpretation, signals: Sequence[Signal], candidate: Optional[str],
           *, has_pieces: bool, shift_threshold: float = 0.75) -> Decision:
    frame = Frame.of(it)
    if it.relation == "digression":
        return Decision("noop", frame, candidate, "digression")
    if not has_pieces:
        return Decision("noop", frame, candidate, "nothing to display")
    if working is None or working.is_title:
        return Decision("new", frame, None, "first content slide")
    if not frame.same_topic(working.frame):
        ok, why = topic_confirmed(it, signals, candidate, shift_threshold)
        if ok:
            return Decision("new", frame, None, f"new topic confirmed ({why})")
        # unconfirmed: keep showing it under the current frame; remember the candidate
        return Decision("update" if working.has_content else "retitle", working.frame, it.topic,
                        "new topic not yet confirmed")
    if not frame.same(working.frame):
        if not working.has_content:
            return Decision("retitle", frame, None, "new facet on an empty slide")
        return Decision("continue", frame, None, "new facet")
    return Decision("update", working.frame, None, "same frame")
