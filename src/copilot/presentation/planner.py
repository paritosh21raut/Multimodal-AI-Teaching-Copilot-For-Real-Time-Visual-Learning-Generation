"""Planner: the deterministic slide-frame decision for one interpretation (F-005). Pure; no I/O.

A new concept is not a new slide: the planner compares the interpretation's frame (topic, facet) with the
working slide and decides update / continue / new / retitle / noop. A topic change needs confirmation.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Optional, Sequence

from copilot.core.interpretation import Interpretation
from copilot.core.memory import is_child_facet, same_subject, same_title, title_key, titles_match

Op = Literal["noop", "update", "continue", "new", "retitle"]


@dataclass(frozen=True)
class Frame:
    topic: str
    facet: str  # subtopic, or the topic itself when there is none
    parent: str = ""  # F-013 S2: the subtopic this facet is a part of ("Causes" for "Social"), "" = under the topic

    @classmethod
    def of(cls, it: Interpretation) -> "Frame":
        facet = it.subtopic or it.topic
        parent = it.parent if it.parent and not same_title(it.parent, facet) \
            and not same_title(it.parent, it.topic) else ""
        return cls(it.topic, facet, parent)

    def same_topic(self, other: "Frame") -> bool:
        return titles_match(self.topic, other.topic)

    def same(self, other: "Frame") -> bool:
        if not self.same_topic(other) or not titles_match(self.facet, other.facet):
            return False
        if self.parent and other.parent:
            return titles_match(self.parent, other.parent)
        if self.parent or other.parent:
            # a child slide and a frame without a parent: the same only when named alike ("Sexual Reproduction" is not
            # its parent "Reproduction", although the titles match by one extra word)
            return title_key(self.facet) == title_key(other.facet)
        return True

    def within(self, other: "Frame") -> bool:
        """`other` is this frame's parent subtopic: the model still names the set ("Planets") while the teacher is on
        one of its members ("Venus"), so its content belongs on the member's slide."""
        return bool(self.parent) and self.same_topic(other) and same_subject(self.parent, other.facet, self.topic)


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


def names(it: Interpretation, name: str) -> bool:
    """The unit's content names it (every longer word of the name, by its stem): content the model files under the
    set ("Causes") stays on the member's slide ("Social") only when it is about that member (F-013 S2; test20 put
    "Economic strain from wars" on the Social slide). The model's one-sentence summary counts: facts without their
    subject ("Diameter: 4879 km") are still summarised as Mercury's."""
    words = [w[:5] for w in re.findall(r"[a-z0-9]{4,}", name.lower())]
    if not words:
        return False
    text = json.dumps(it.model_dump(include={"acts", "summary_delta"}), ensure_ascii=False).lower()
    return all(w in text for w in words)


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
        # "Now let's talk about galaxies" alone: nothing to show yet, but remember the announced topic so the next
        # unit about it opens its slide without waiting for another confirmation
        if working is not None and not working.is_title and not frame.same_topic(working.frame) \
                and it.relation == "new_topic":
            return Decision("noop", frame, it.topic, "new topic announced")
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
    if working.frame.within(frame) and names(it, working.frame.facet):
        return Decision("update", working.frame, None, "the member of the set on screen")
    if is_child_facet(frame.facet, working.frame.facet):
        child = Frame(frame.topic, frame.facet, parent=working.frame.facet)
        return Decision("continue" if working.has_content else "retitle", child, None, "a narrower kind of the facet")
    if not frame.same(working.frame):
        if not working.has_content:
            return Decision("retitle", frame, None, "new facet on an empty slide")
        return Decision("continue", frame, None, "new facet")
    return Decision("update", working.frame, None, "same frame")
