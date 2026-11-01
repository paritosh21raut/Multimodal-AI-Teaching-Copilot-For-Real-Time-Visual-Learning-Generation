"""Diagram or stage (F-018 §2, ADR-0013), deterministic, from the line's nouns.

A line whose drawable nouns are all concept parts (circuit parts, apparatus, chemicals, magnets, atoms, celestial
bodies, blocks / inclines / springs / pulleys, plain shapes) is a diagram, also when it says "imagine" or "you"
("Imagine in a beaker you have HCl": "you" is not drawn). A person or an animal, "you" doing a stage action (riding,
throwing, reading …) or a stage thing the part library does not have (a car, a tree) leaves it to the stage. A shape
line with a measurement ("a circle of radius 5 cm") stays an F-015 geometry scene (it computes).
"""
from __future__ import annotations

import re
from typing import Optional

from copilot.diagram import fastpath, motion
from copilot.diagram.graph import Graph

SHAPES = {"circle", "square", "triangle", "rectangle", "pentagon", "hexagon"}
_MEASURE = re.compile(r"\b(?:radius|radii|diameter|side|sides|length|area|perimeter|circumference|chord|tangent|"
                      r"diagonal|angle\s+[A-Z]{2,3}|cm|centimet\w*|met(?:er|re)s?|inch\w*)\b|\d", re.IGNORECASE)
_YOU_ACT = re.compile(r"\b(?:you|yourself)(?:'re|\s+are|\s+were|\s+)?\s*(?:\w+ly\s+)?(?:riding|ride|driving|drive|"
                      r"throwing|throw|pushing|push|pulling|pull|carrying|carry|lifting|lift|kicking|kick|running|"
                      r"run|walking|walk|sitting|sit|standing|stand|swinging|swing|reading|read|holding|hold|playing|"
                      r"play|jumping|jump|climbing|climb|swimming|swim|studying|study|eating|eat|sleeping|sleep|"
                      r"going|travel\w*|flying|fly|floating|in|on|at|inside)\b",  # the listener in a scene
                      re.IGNORECASE)
_SKIP = {"you", "it", "he", "she", "they", "we", "i", "field", "lines", "line", "system", "plane", "surface", "solution",
         "rope", "string", "thread", "cord"}  # F-019 M1: the rope over a pulley is drawn by the diagram


def stage_nouns(text: str, spans: list[tuple[int, int]]) -> list[str]:
    """Words the stage would draw that the diagram does not cover (people, animals, other things, places)."""
    from copilot.stage.fastpath import index
    idx = index()
    out = []
    for m in re.finditer(r"[A-Za-z]+", text):
        w = m.group(0).lower()
        if w in _SKIP or any(s <= m.start() < e for s, e in spans):
            continue
        if w in idx:
            out.append(idx[w])
    return out


def route(text: str) -> Optional[str]:
    """"diagram" for a concept line, else None (the stage / F-015 / nothing decides as before)."""
    ms = fastpath.mentions(text)
    if not ms:
        return None
    if _YOU_ACT.search(text) and not _you_move(text, ms):
        return None
    spans = [(m.start, m.end) for m in ms]
    pm = motion.people(text, ms, Graph())
    if pm is not None:  # M5: "a man walks in the rain" is the K1 man
        spans.append(pm.span(1))
    if any(m.kind in motion.KINDS for m in ms) and motion.moving(text):  # "a ball thrown in the sky", "on the road"
        spans += [x.span() for x in _BACKDROP.finditer(text)]
    if stage_nouns(text, spans):
        return None
    kinds = {m.kind for m in ms}
    if kinds <= set(motion.MOVERS) and not motion.moving(text):
        return None  # M5: "two balls colliding", "hit a ball with a bat": no motion said, as before (the stage)
    if kinds <= SHAPES and _measured(text):
        return None
    if all(m.word in fastpath.AMBIGUOUS for m in ms) and not fastpath.CONTEXT.search(text):
        return None  # "imagine a spring morning", "consider the cell": everyday words, no physics around them
    return "diagram"


_YOU_MOVE = re.compile(r"\b(?:you|yourself)(?:'re|\s+are|\s+were|\s+)?\s*(?:\w+ly\s+)?(?:throw\w*|threw|kick\w*|"
                       r"drop\w*|walk\w*|run\w*|ran|driv\w*|drove|swim\w*|row\w*|cross\w*|whirl\w*|launch\w*|toss\w*|"
                       r"project\w*|release\w*|cycl\w*|travel\w*|mov\w*)\b", re.IGNORECASE)
_BACKDROP = re.compile(r"\b(?:sky|air|road|street|highway|track|lane)s?\b", re.IGNORECASE)  # M5: where it moves
_YOU_STAGE = re.compile(r"\byou(?:'re|\s+are)?\s+(?:push|pull|carry|lift|hold|hit)\w*", re.IGNORECASE)


def _you_move(text: str, ms: list) -> bool:
    """M5: "you throw a ball", "you walk in the rain": the listener moves a motion part (a diagram); "you push a car"
    stays as before."""
    return any(m.kind in motion.KINDS for m in ms) and bool(_YOU_MOVE.search(text)) and not _YOU_STAGE.search(text)


def _measured(text: str) -> bool:
    """A number that is not a shape's name ("C1") or a count word: a measurement."""
    t = re.sub(r"\b[A-Z]\d{1,2}\b", " ", text)
    return bool(_MEASURE.search(t))
