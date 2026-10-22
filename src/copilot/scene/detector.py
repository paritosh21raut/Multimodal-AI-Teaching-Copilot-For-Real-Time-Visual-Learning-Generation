"""Transcript lines -> RepresentationIntent(visual_kind="scene") for the Live Scene Engine (F-015), deterministic,
0 tokens.

    cue   a cue word (imagine, picture, suppose, consider, let's say, draw, visualise, think of, look at) followed
          within a few words by a drawable noun of an L1 world (a square, a circle, the graph of, a ball ...)
    edit  any content line while a scene is open; the scene controller asks `wants_edit` (edit words, a drawable
          noun, a number, a name in the scene) before it spends a call on it

A cue for another world's noun while a scene is open is a new scene ("now imagine a ball" over a square); a cue for
the same world is an edit ("now draw a circle inside it"). The end of a scene comes from the shared end cue
(simulation.detector: "let's get back to the slides"), which ends whichever mode is open.
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.events import Event, RepresentationIntent, SimulationModeChanged, TranscriptFinal, \
    UtteranceClassified
from copilot.simulation.detector import end_cue
from copilot.simulation.values import NUM

log = logging.getLogger(__name__)

MAX_LINES = 300
NOUN_REACH = 6  # words between the cue word and its noun ("imagine a really big red square")

_CUE = re.compile(r"\b(?:imagine|picture|suppose|consider|visuali[sz]e|draw|sketch|think of|look at|"
                  r"let(?:'?s| us) (?:say|draw|take|consider|imagine|picture|plot))\b", re.IGNORECASE)
NOUNS: dict[str, str] = {  # drawable noun (regex) -> its world
    r"squares?|rectangles?|circles?|triangles?|polygons?|hexagons?|pentagons?|octagons?|diagonals?|"
    r"chords?|radius|diameter|tangents?|line segments?|segments?|points? [A-Z]\b|bisectors?|"
    r"cubes?\b(?!\s+(?:roots?\b|of\s+(?:\d|a number\b|the number\b|[a-z]\b)))|cuboids?|cylinders?|cones?\b(?!\s+(?:cells?|in the (?:retina|eye))\b)|"
    r"spheres?": "geometry",
    r"graph of (?:y|f|the (?:function|line|curve|equation))|plot of|parabola|function (?:f|y)\b|f of x|"
    r"y\s*(?:=|equals)|sine (?:wave|curve)|straight line y": "plot",
    r"balls?|blocks?|cars?|trains?|stones?|particles?|rockets?|bullets?|carts?|bikes?|marbles?|projectiles?|"
    r"trucks?|boats?|ships?|(?:aero|air)planes?|bicycles?|cyclists?|runners?|"
    r"(?:bus|buses|planes?) (?:moving|travel+ing|going|running|flying|taking off|landing)|"
    r"(?:boy|girl|man|woman|person) (?:running|walking|moving|cycling|riding)|"
    r"(?:an? |the )?(?:object|body|box) (?:moving|thrown|dropped|falling|rolling|sliding|launched|travel+ing)": "motion",
}
_NOUN = [(re.compile(rf"\b(?:{rx})", re.IGNORECASE), w) for rx, w in NOUNS.items()]
_ANY_NOUN = re.compile("|".join(rf"\b(?:{rx})" for rx in NOUNS), re.IGNORECASE)
_EDIT = re.compile(r"\b(?:now|make|add|increase|decrease|double|halve|half|triple|change|move|speed(?:s)? up|"
                   r"slow(?:s)? down|accelerat\w*|decelerat\w*|remove|draw|mark|its|another|second|inside|around|"
                   r"bigger|smaller|larger|faster|slower|extend|rotate|join|connect|shade|label|put|place|replace|"
                   r"instead|again|let(?:'?s| us))\b", re.IGNORECASE)
_NUMBER = re.compile(NUM, re.IGNORECASE)


def cue(text: str) -> Optional[str]:
    """The world of the drawable noun after a cue word in the line, or None."""
    for m in _CUE.finditer(text):
        tail = " ".join(text[m.end():].split()[:NOUN_REACH + 2])
        best: Optional[tuple[int, str]] = None
        for rx, world in _NOUN:
            n = rx.search(tail)
            if n and len(tail[:n.start()].split()) <= NOUN_REACH and (best is None or n.start() < best[0]):
                best = (n.start(), world)
        if best is not None:
            return best[1]
    return None


def wants_edit(text: str, names: list[str]) -> bool:
    """A line said while a scene is open that may change it: edit words, a drawable noun, a number, or a name of a
    thing in the scene."""
    if _EDIT.search(text) or _ANY_NOUN.search(text) or _NUMBER.search(text):
        return True
    low = text.lower()
    return any(n and re.search(rf"\b{re.escape(n.lower())}", low) for n in names)


class SceneDetector:
    """Publishes a scene cue for each content line with one, and an edit candidate for each content line while a scene
    is open. Holds no deck state: it learns that a scene is open from SimulationModeChanged."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._text: OrderedDict[str, str] = OrderedDict()
        self.open_world: Optional[str] = None  # the open scene's world (None: no scene open)
        self._cued: str = ""                    # the world of the last cue published (the scene it opens)
        self.intents = 0

    def attach(self) -> None:
        self.bus.subscribe("scene_detector", self._on_event,
                           [TranscriptFinal, UtteranceClassified, SimulationModeChanged])

    async def _publish(self, segment_id: str, text: str, strength: str) -> None:
        self.intents += 1
        log.info("[SCENE] %s %r", strength, text[:80])
        await self.bus.publish(RepresentationIntent(
            segment_ids=[segment_id], visual_kind="scene", strength=strength,  # type: ignore[arg-type]
            origin="cue", text=text[:300]))

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            self._text[event.segment.id] = event.segment.text
            while len(self._text) > MAX_LINES:
                self._text.popitem(last=False)
            return
        if isinstance(event, SimulationModeChanged):
            self.open_world = self._cued if event.on and event.template == "scene" else None
            return
        assert isinstance(event, UtteranceClassified)
        text = self._text.get(event.segment_id, "")
        if event.kind != "content" or event.maybe_meta or not text or end_cue(text):
            return
        world = cue(text)
        if world is not None and world != self.open_world:  # none open, or another world's noun: a new scene
            self._cued = world
            await self._publish(event.segment_id, text, "cue")
        elif self.open_world is not None:
            await self._publish(event.segment_id, text, "edit")
