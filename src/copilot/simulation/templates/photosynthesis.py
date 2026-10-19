"""Photosynthesis: gas exchange in a leaf (F-014 S3). Renderer: web/sims/photosynthesis.js.

A plant with one large leaf: light from the Sun falls on the leaf, water rises from the roots up the stem, carbon
dioxide enters through the stomata, glucose is made in the leaf, oxygen leaves through the stomata (textbook,
class 7-10). Five steps in that order; the current one follows the speech (simulation.steps). The word equation
under the picture is built as the teacher says its terms (user 2026-10-19):

    carbon dioxide + water --(light, chlorophyll)--> glucose + oxygen

a term not said yet is an empty box. Respiration (the reverse: glucose + oxygen -> carbon dioxide + water, with
energy released) is shown only once said. Directions are the science's, never the speech's: "plants take in oxygen
during photosynthesis" (a mistake V1 reports) does not turn the arrows round. No numbers.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import Element, Part, SimBase, Solution, StepDef, Template, _Model

STEPS = (
    StepDef("light", "Light is absorbed by chlorophyll",
            r"\b(?:sun)?light (?:is |gets )?(?:absorbed|trapped|captured|falls)\b|\babsorbs? (?:the )?(?:sun)?light\b"
            r"|\bchlorophyll (?:absorbs|traps|captures)\b|\blight energy\b|\btraps? (?:the )?(?:sun)?light\b"),
    StepDef("water", "Water rises from the roots",
            r"\bwater (?:is )?(?:absorbed|taken up|enters|travels|moves|rises|goes up|comes up|reaches)\b"
            r"|\broots? (?:absorb|take up|draw)\b|\b(?:absorbed|taken) (?:in )?(?:by|through|from) the roots\b|\bxylem\b"),
    StepDef("co2", "Carbon dioxide enters through the stomata",
            r"\bcarbon dioxide (?:enters|is taken|diffuses (?:in|into)|goes in|comes in|moves in|gets in)\b"
            r"|\btakes? in carbon dioxide\b|\b(?:CO2|CO₂) (?:enters|goes in)\b"
            r"|\bcarbon dioxide\b(?:(?!\b(?:leaves|released|given out|gives out|comes out|goes out|escapes)\b)[^.;])*"
            r"\bthrough (?:the |tiny )?(?:pores|stomata)\b"),
    StepDef("glucose", "Glucose is made",
            r"\bglucose (?:is )?(?:made|formed|produced|prepared)\b"
            r"|\b(?:make|makes|form|forms|produce|produces) glucose\b|\bcombines? with carbon dioxide to (?:make|form)\b",
            weak=r"\bmakes? (?:its |their )?(?:own )?food\b|\bfood is (?:made|produced|prepared)\b"),
    StepDef("o2", "Oxygen leaves through the stomata",
            r"\boxygen (?:is )?(?:released|given out|given off|comes out|leaves|escapes|goes out|diffuses out)\b"
            r"|\breleases? oxygen\b|\bgives? (?:out|off) oxygen\b|\boxygen is (?:a |the )?by-?product\b"),
)
PARTS = (  # the word equation's terms, the conditions on its arrow, and respiration
    Part("t_co2", "carbon dioxide", r"\bcarbon dioxide\b|\bCO2\b|\bCO₂\b"),
    Part("t_water", "water", r"\bwater\b|\bH2O\b"),
    Part("t_glucose", "glucose", r"\bglucose\b|\bC6H12O6\b"),
    Part("t_o2", "oxygen", r"\boxygen\b|\bO2\b|\bO₂\b"),
    Part("t_light", "light", r"\b(?:sun)?light\b"),
    Part("t_chlorophyll", "chlorophyll", r"\bchlorophyll\b"),
    Part("stomata", "Stomata", r"\bstomat(?:a|e|al)\b|\bstoma\b"),
    Part("roots", "Roots", r"\broots?\b"),
    Part("leaf", "Leaf", r"\bleaf\b|\bleaves\b"),
    # respiration as the reverse (aerobic; "animals take in oxygen for respiration" is an aside: S3 review)
    Part("respiration", "Respiration",
         r"(?<!anaerobic )\brespiration\b(?=[^.;]*\b(?:reverse|opposite|glucose)\b)|\breverse of photosynthesis\b"),
)
ELEMENTS = (
    Element("plant", "Plant"), Element("sun", "Sun"), Element("light", "Light"), Element("water", "Water"),
    Element("co2", "Carbon dioxide"), Element("glucose", "Glucose"), Element("o2", "Oxygen"),
    Element("equation", "Word equation"),
)


class PhotosynthesisParams(_Model):
    pass


class PhotosynthesisSim(SimBase):
    template: Literal["photosynthesis"] = "photosynthesis"
    params: PhotosynthesisParams = Field(default_factory=PhotosynthesisParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = tuple(p.id for p in PARTS)


def solve(p: PhotosynthesisParams, src: dict[str, str]) -> Solution:
    return Solution(drive={})  # no numbers: the steps and the named terms carry the picture


def default_shown(p: PhotosynthesisParams, src: dict[str, str]) -> list[str]:
    return [e.id for e in ELEMENTS]


_STEP_WORDS = "|".join(d.words for d in STEPS)

TEMPLATE = Template(
    id="photosynthesis", name="Photosynthesis in a leaf", subject="biology",
    sim=PhotosynthesisSim, params=PhotosynthesisParams, slots=(), elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\bphotosynthesis\b|\bstomata\b|\bchlorophyll\b|\bgas exchange in (?:the |a )?(?:leaf|leaves|plants?)\b"
                     r"|\bhow (?:green )?plants make (?:their |its )?(?:own )?food\b", re.IGNORECASE),
    lexicon=re.compile(rf"{_STEP_WORDS}|\b(?:photosynthesis|leaf|leaves|stomata|chlorophyll|sunlight|light|"
                       rf"carbon dioxide|oxygen|water|glucose|roots?|plants?|food|energy)\b", re.IGNORECASE),
    # not a leaf: man-made "artificial photosynthesis", bacteria, the chemistry of the reaction centre
    guard=re.compile(r"\bartificial photosynthesis\b|\bsolar fuels?\b|\bphotosynthetic bacteria\b|\bphotosystem\b"
                     r"|\bcalvin cycle\b|\blight[- ]dependent reactions?\b"
                     # "show you the photosynthesis equation": V1's equation, not the leaf (S0 negative)
                     r"|\bphotosynthesis (?:equation|formula|reaction)\b|\bequation (?:of|for) photosynthesis\b"
                     r"|\bsolar cells?\b|\bdye[- ]sensiti[sz]ed\b",
                     re.IGNORECASE),
    aliases=("photosynthesis", "leaf", "stomata", "plants", "gas exchange", "chlorophyll"),
    steps=STEPS, parts=PARTS,
)
