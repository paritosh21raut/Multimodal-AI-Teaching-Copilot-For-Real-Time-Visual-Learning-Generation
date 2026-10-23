"""Transcript lines -> RepresentationIntent(visual_kind="scene") for the Live Scene Engine (F-015), deterministic,
0 tokens.

    cue   a cue word (imagine, picture, suppose, consider, let's say, draw, visualise, think of, look at) followed
          within a few words by a drawable noun of an L1 world (a square, a circle, the graph of, a ball ...)
    edit  any content line while a scene is open; the scene controller asks `wants_edit` (edit words, a drawable
          noun, a number, a name in the scene) before it spends a call on it

A cue for another world's noun while a scene is open is a new scene ("now imagine a ball" over a square); a cue for
the same world is an edit ("now draw a circle inside it").

F-016 canvas: a cue word followed by any picture noun (scene.pictures.words: the emoji / icon names, places, shape
nouns) is a cue; it is a "canvas" cue when that noun is not one of an L1 world's or a relation word ("on", "under")
follows an object noun. Canvas cues are always published while a scene is open: the scene controller decides
(an edit when the line refers to the open scene, else a new scene). The end of a scene comes from the shared end cue
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
from copilot.scene import pictures

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
    r"(?:boy|girl|man|woman|person) (?:runs|walks|running|walking|moving|cycling|riding|standing)|"
    # the relative world (L2a) is cued like motion: a river and its boat, rain and its walker are one scene
    r"rain(?:drops?)?\b(?!bow)|raining|rivers?|swimmers?|streams? (?:of water|flowing)|"
    r"(?:an? |the )?(?:object|body|box) (?:moving|thrown|dropped|falling|rolling|sliding|launched|travel+ing)": "motion",
}
_NOUN = [(re.compile(rf"\b(?:{rx})", re.IGNORECASE), w) for rx, w in NOUNS.items()]
_ANY_NOUN = re.compile("|".join(rf"\b(?:{rx})" for rx in NOUNS), re.IGNORECASE)
# the words an L1 world's noun patterns are written for (their look-alike guards stay theirs)
_L1_WORDS = frozenset(x for rx in NOUNS for w in re.findall(r"[a-z]{3,}", rx.replace("?", " "))
                     for x in (w, w[:-1] if w.endswith("s") else w)) - {"bus", "buses", "plane", "planes"}
# look-alike compounds: not a thing to picture ("the address bus", "a plane mirror", "a cube root", "the cube of x")
_LOOKALIKE = re.compile(r"\b(?:(?:address|data|control|system)\s+bus|bus\s+(?:topology|network|lines?|width)|"
                        r"plane\s+(?:mirrors?|waves?|polari\w+)|(?:inclined|xy|x-y|cartesian|complex|coordinate|focal|"
                        r"image|horizontal|vertical)\s+plane|cube\s+(?:roots?|of)|cones?\s+(?:cells?|in\s+the))\b",
                        re.IGNORECASE)
# "imagine you are on a mountain", "imagine yourself at the top of a building": the listener in a scene (test32: "imagine
# you are standing with a tall stick in your hand" had no picture noun and was lost)
_YOU = re.compile(r"^\W*(?:that\s+)?(?:you(?:'re|\s+are|\s+were)|yourself|yourselves)\s+(?:\w+ly\s+)?(?:standing|"
                  r"sitting|lying|walking|running|riding|driving|flying|floating|swimming|climbing|jumping|falling|"
                  r"holding|carrying|throwing|reading|playing|sleeping|on|in|at|inside|under|near|beside|above)\b",
                  re.IGNORECASE)  # review: "imagine you are given a triangle" is geometry, "... solving" nothing
_EDIT = re.compile(r"\b(?:now|make|add|increase|decrease|double|halve|half|triple|change|move|speed(?:s)? up|"
                   r"slow(?:s)? down|accelerat\w*|decelerat\w*|remove|draw|mark|its|another|second|inside|around|"
                   r"bigger|smaller|larger|faster|slower|extend|rotate|join|connect|shade|label|put|place|replace|"
                   r"instead|again|let(?:'?s| us))\b", re.IGNORECASE)
_NUMBER = re.compile(NUM, re.IGNORECASE)


def cue(text: str) -> Optional[str]:
    """The world of the drawable noun after a cue word in the line ("canvas": any other picture noun, or a relation
    word with an object noun), or None."""
    for m in _CUE.finditer(text):
        you = m.group(0).lower().startswith(("imagine", "picture", "visuali")) and _YOU.search(text[m.end():])
        tail = " ".join(text[m.end():].split()[:NOUN_REACH + 2])
        best: Optional[tuple[int, str]] = None
        for rx, world in _NOUN:
            n = rx.search(tail)
            if n and len(tail[:n.start()].split()) <= NOUN_REACH and (best is None or n.start() < best[0]):
                best = (n.start(), world)
        own = {w.lower() for x in _ANY_NOUN.finditer(tail) for w in x.group(0).split()}
        # a noun after "as a" is a metaphor ("the human body as a machine"), after "this" / "our" the real one
        # ("the objects in this room"): neither is imagined
        words = re.findall(r"[a-z]+", _LOOKALIKE.sub(" ", tail).lower())
        toks = [w for i, w in enumerate(words) if not (i and words[i - 1] in ("this", "these", "our"))
                and not (i > 1 and words[i - 2] == "as" and words[i - 1] in ("a", "an"))]
        # a motion problem's road or track is its ground, not a canvas ("think of a car on a straight road"); a word
        # an L1 world judges keeps its guards ("a cube root", "an inclined plane"); "look at" focuses, never opens one
        setting = set(pictures.PLACES["street"]) if best is not None and best[1] == "motion" else set()
        canvas = not m.group(0).lower().startswith("look") and any(
            t not in own and t not in setting and t not in _L1_WORDS and pictures.assets.singular(t) not in _L1_WORDS
            and pictures.assets.singular(t) in pictures.words() for t in toks)
        if canvas or (you and (best is None or best[1] == "motion")):  # the listener in a scene (a vehicle: canvas)
            return "canvas"
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
            # a scene opened by its cue, or by the teacher (Imagine Mode, no cue): a canvas
            self.open_world = (self._cued or "canvas") if event.on and event.template == "scene" else None
            self._cued = ""
            return
        assert isinstance(event, UtteranceClassified)
        text = self._text.get(event.segment_id, "")
        if event.kind != "content" or event.maybe_meta or not text or end_cue(text):
            return
        world = cue(text)
        if world is not None and (world != self.open_world or world == "canvas"):  # none open, another world's noun
            # (a new scene), or a canvas cue (the controller: an edit when it refers to the open scene)
            self._cued = world
            await self._publish(event.segment_id, text, "cue")
        elif self.open_world is not None:
            await self._publish(event.segment_id, text, "edit")
