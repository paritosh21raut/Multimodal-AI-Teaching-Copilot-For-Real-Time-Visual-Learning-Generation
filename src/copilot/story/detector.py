"""Transcript lines -> RepresentationIntent(visual_kind="story") (V3 ST1), deterministic, 0 tokens.

    cue    strong: "let me tell you the story of ...", "once upon a time", "imagine you are a red blood cell",
           "follow a drop of water as it ...", "the journey of ..." -> the story opens (Auto) or a chip (Suggest)
    setup  weak: a year and a past-tense narrative opener ("In 1905, a young clerk in Bern wrote ...") with no story
           open -> a Suggest chip
    edit   every line while a story is open (content, a question in the story, a short reply "Me too!")
    end    "that's the end of the story", "the end" (the shared "back to the slides" is simulation.detector's)

A line with a story cue is not a scene / stage cue (scene.detector asks `cue`), and while a story is open the scene
detector publishes nothing: the story owns the lines.
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.events import (Event, RepresentationIntent, SimulationModeChanged, TranscriptFinal,
                                 UtteranceClassified)
from copilot.simulation.detector import end_cue
from copilot.story import beats

log = logging.getLogger(__name__)

MAX_LINES = 64
_ADJ = r"(?:(?:little|short|true|famous|real|small|sad|funny|old)\s+)?"
_STRONG = re.compile(
    rf"\blet me tell you (?:a|the|one|this|about the)?\s*{_ADJ}(?:story|tale)\b"
    rf"|\b(?:here(?:'s| is)|this is|i(?:'ll| will) tell you|i want to tell you) (?:a|the|one)\s+{_ADJ}(?:story|tale)\b"
    r"|\bonce upon a time\b"
    r"|\bimagine (?:that )?you are (?:a|an|one|the) (?!passenger|driver|rider|person standing)\w+"
    r"|\bimagine (?:yourself|you) as (?:a|an) \w+"
    r"|\b(?:let(?:'s| us) |we(?:'ll| will) )?follow (?:a|an|the|one) (?!(?:\w+ ){0,2}?(?:" + "|".join(sorted(
        "current electron electrons charge signal packet packets steps step arrows arrow path curve procedure line "
        "lines instructions rules example diagram graph flow method process algorithm code recipe link order "
        "sequence chart pattern trend rule logic proof derivation equation".split(), key=len, reverse=True)) +
    r")\b)(?:\w+ ){0,3}?(?:through|as (?:it|he|she|they)|on (?:its|his|her|their) (?:journey|way|trip))\b"
    r"|\bthe (?:journey|story|tale|adventures?) of (?:a|an|one|(?-i:[A-Z]\w+))|\bthe life of (?-i:[A-Z]\w+)"
    r"|\blet me narrate\b", re.IGNORECASE)
# while a story is open only these start the next one ("the journey of the drop continues" is the same story)
_NEW = re.compile(rf"\blet me tell you (?:a|the|one|this|about the)?\s*{_ADJ}(?:story|tale)\b"
                  rf"|\b(?:here(?:'s| is)|i(?:'ll| will) tell you|i want to tell you) (?:a|the|one)\s+{_ADJ}(?:story|tale)\b"
                  r"|\bonce upon a time\b|\bimagine (?:that )?you are (?:a|an|one) \w+", re.IGNORECASE)
# a physics situation said as "imagine you are a ..." is the stage's (F-017), not a story
_PHYSICS = re.compile(r"\b(?:brak\w*|accelerat\w*|speed|velocity|force|friction|mass|kg|km/h|m/s|metres? per|"
                      r"meters? per|push\w*|pull\w*|throw\w*|thrown|falls?|falling|incline|slope|pulley|spring)\b",
                      re.IGNORECASE)
_WEAK = re.compile(r"^\W*(?:(?:so|now|okay|well)\W+)*(?:back\s+)?(?:in|around)\s+(?:the\s+year\s+)?(?:1[0-9]|20)\d{2}\b"
                   r".*\b(?:was|were|went|lived|met|wrote|found|discovered|became|had|saw|made|began|worked|\w+ed)\b"
                   r"|^\W*(?:long ago|many years ago|a long time ago)\b", re.IGNORECASE)
_END = re.compile(r"\b(?:that(?:'s| is| was) the end of (?:the|our|this|my) (?:story|tale|journey)|"
                  r"(?:and|so) that(?:'s| is| was) (?:the|our) story|end of (?:the|our|this) story|"
                  r"the story ends here)\b|^\W*(?:and\s+)?the end\W*$", re.IGNORECASE)
_QUESTION_TO_CLASS = re.compile(r"\b(?:any questions|do you understand|is that clear|got it)\b", re.IGNORECASE)


def cue(text: str) -> str:
    """'strong', 'weak' or '' for a line said with no story open."""
    if _STRONG.search(text) and not _PHYSICS.search(text):
        return "strong"
    if _WEAK.search(text) and not _PHYSICS.search(text):
        b = beats.beat(text)  # a person in it ("Newton published"), not "in 1990 the population increased"
        if b.names or b.people:
            return "weak"
    return ""


_END_OPEN = re.compile(r"\bthat(?:'s| is| was) the end of (?:the|our|this|my|today's)\s+\w+", re.IGNORECASE)


def ends(text: str, open_: bool = False) -> bool:
    """The story's end. open_ (a story is open): "that's the end of this tutorial" too (test53: STT for "story")."""
    return bool(_END.search(text) or open_ and _END_OPEN.search(text))


class StoryDetector:
    """Publishes a story cue, and while a story is open every line it can use. Holds no deck state: it learns that a
    story is open from SimulationModeChanged."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._text: OrderedDict[str, str] = OrderedDict()
        self.open = False
        self.intents = 0

    def attach(self) -> None:
        self.bus.subscribe("story_detector", self._on_event, [TranscriptFinal, UtteranceClassified,
                                                               SimulationModeChanged])

    async def _publish(self, segment_id: str, text: str, strength: str) -> None:
        self.intents += 1
        log.info("[STORY] %s %r", strength, text[:80])
        await self.bus.publish(RepresentationIntent(segment_ids=[segment_id], visual_kind="story",
                                                    strength=strength, origin="cue", text=text[:300]))  # type: ignore[arg-type]

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            self._text[event.segment.id] = event.segment.text
            while len(self._text) > MAX_LINES:
                self._text.popitem(last=False)
            return
        if isinstance(event, SimulationModeChanged):
            self.open = event.on and event.template == "story"
            return
        assert isinstance(event, UtteranceClassified)
        text = self._text.get(event.segment_id, "")
        if not text or end_cue(text):  # "back to the slides": simulation.detector ends the mode
            return
        if self.open:
            if ends(text, open_=True):
                await self._publish(event.segment_id, text, "end")
            elif event.kind == "content" and cue(text) == "strong" and _NEW.search(text):  # the next story or this one
                await self._publish(event.segment_id, text, "cue")
            elif event.kind == "content" or beats.speech(text) is not None or \
                    event.kind in ("question_to_class", "filler") and not _QUESTION_TO_CLASS.search(text) and \
                    len(text.split()) <= 12:
                await self._publish(event.segment_id, text, "edit")  # "Me too!" / "Do you play?" in the story
            return
        if event.kind != "content" or event.maybe_meta:
            return
        c = cue(text)
        if c:
            await self._publish(event.segment_id, text, "cue" if c == "strong" else "setup")


def story_cue(text: Optional[str]) -> bool:
    """For scene.detector: this line opens a story, it is not a scene cue."""
    return bool(text) and cue(text or "") == "strong"
