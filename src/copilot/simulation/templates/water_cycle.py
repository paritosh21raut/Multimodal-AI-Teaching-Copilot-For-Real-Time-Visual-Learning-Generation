"""The water cycle (F-014 S3, the first process template): evaporation, condensation, precipitation and collection,
with transpiration, runoff and infiltration drawn once the teacher says them. Renderer: web/sims/water_cycle.js.

A discrete process: no clock-driven physics and no numbers. The current step follows the teacher's speech
(simulation.steps): the step named is highlighted and its name prints; a step nobody said is drawn with its number
only. Arrows (textbook directions): evaporation up from the sea, transpiration up from the plants, condensation into
the cloud, precipitation down onto the land, runoff down the slope into the sea, infiltration down into the ground
(groundwater flows on to the sea), collection: water gathers in the sea, lakes and rivers.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import Element, Part, SimBase, Solution, StepDef, Template, _Model

STEPS = (
    StepDef("evaporation", "Evaporation",
            r"\bevaporat\w*|\b(?:turns?|changes?|converts?) (?:in)?to (?:water )?vapou?r\b", weak=r"\bwater vapou?r rises\b"),
    # Whisper heard "transcription" in the user's water-cycle lecture (test28): only beside the vapour / plants
    StepDef("transpiration", "Transpiration",
            r"\btranspir\w*|\b(?:plants?|leaves|trees?) (?:\w+ )?(?:release|releases|give out|gives out|lose|loses|give off|gives off) water(?: vapou?r)?\b"
            r"|\bevaporation and transcription\b|\btranscription\b(?=.*\b(?:vapou?r|plants?|leaves|stomata)\b)",
            optional=True, element="transpiration"),
    StepDef("condensation", "Condensation",
            r"\bcondens\w*|\bclouds? (?:form|forms|are formed|is formed)\b|\bcloud formation\b|\bforms? clouds?\b"
            r"|\b(?:turns?|changes?) (?:back )?into (?:tiny )?(?:water )?droplets\b"),
    StepDef("precipitation", "Precipitation",
            r"\bprecipitat\w*|\b(?:fall|falls|falling|comes? down|come back) (?:back )?(?:down )?"
            r"(?:to (?:the )?(?:earth|ground) )?(?:as|in the form of) (?:rain|snow|hail|sleet)\b"
            r"|\b(?:falls?|falling|comes? down) (?:back )?(?:down )?to (?:the )?(?:earth|ground)\b"
            r"|\brain(?:s|fall|ing)\b|\bsnow(?:s|fall|ing)\b|\bhail\b|\bsleet\b",
            weak=r"\brain(?:drops?)?\b|\bsnow\b"),
    StepDef("runoff", "Runoff",
            r"\brun[- ]?offs?\b|\bflows? (?:over|across|down) the (?:land|ground|surface|slopes?|hills?)\b",
            optional=True, element="runoff"),
    StepDef("infiltration", "Infiltration",
            r"\binfiltrat\w*|\bin[- ]filtration\b|\bground ?water\b|\baquifers?\b"
            r"|\b(?:seeps?|soaks?|sinks?) (?:in)?to the (?:soil|ground)\b",
            optional=True, element="infiltration"),
    StepDef("collection", "Collection",
            r"\bcollect(?:s|ed|ion|ing)?\b|\baccumulat\w*|\bgathers? in\b"
            r"|\b(?:carry|carries|bring|brings|take|takes) (?:the |this )?water back to the (?:seas?|oceans?|lakes?)\b"
            r"|\b(?:flows?|returns?|goes) (?:back )?(?:in)?to the (?:oceans?|seas?|lakes?)\b"),
)
PARTS = (
    Part("sun", "Sun", r"\bsun\b|\bsun'?s (?:heat|energy|rays)|\bsunlight\b|\bsolar (?:energy|heat)\b"),
    Part("cloud", "Cloud", r"\bclouds?\b"),
    Part("ocean", "Sea", r"\boceans?\b|\bseas?\b"),
)
ELEMENTS = (
    Element("sun", "Sun"), Element("sea", "Sea"), Element("land", "Land"), Element("cloud", "Cloud"),
    Element("evaporation", "Evaporation"), Element("transpiration", "Transpiration"),
    Element("condensation", "Condensation"), Element("precipitation", "Precipitation"), Element("runoff", "Runoff"),
    Element("infiltration", "Infiltration"), Element("collection", "Collection"),
)


class WaterCycleParams(_Model):
    pass


class WaterCycleSim(SimBase):
    template: Literal["water_cycle"] = "water_cycle"
    params: WaterCycleParams = Field(default_factory=WaterCycleParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("ocean",)  # the part "Sea" labels the sea element


def solve(p: WaterCycleParams, src: dict[str, str]) -> Solution:
    return Solution(drive={})  # nothing to compute: the steps and parts carry the picture


def default_shown(p: WaterCycleParams, src: dict[str, str]) -> list[str]:
    # the optional steps' arrows come with their step (registry.solved, StepDef.element)
    return ["sun", "sea", "land", "cloud", "evaporation", "condensation", "precipitation", "collection"]


_STEP_WORDS = "|".join(d.words for d in STEPS)

TEMPLATE = Template(
    id="water_cycle", name="The water cycle", subject="geography",
    sim=WaterCycleSim, params=WaterCycleParams, slots=(), elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\bwater cycle\b|\bhydrolog(?:ical|ic) cycle\b|\bcycle of water\b|\bwater'?s cycle\b",
                     re.IGNORECASE),
    lexicon=re.compile(rf"{_STEP_WORDS}|\b(?:water|vapou?r|clouds?|sun|heat|oceans?|seas?|rivers?|lakes?|cycle|"
                       rf"droplets?|atmosphere|moisture)\b", re.IGNORECASE),
    # a machine's water cycle is not this one
    guard=re.compile(r"\bwashing machine|\bdish ?washer|\bwasher\b|\bcooling (?:system|tower)|\bboiler\b|"
                     r"\bpower (?:plant|station)\b|\bturbine\b|\bsteam engine\b", re.IGNORECASE),
    aliases=("water cycle", "hydrological cycle", "evaporation", "condensation", "precipitation", "rain"),
    steps=STEPS, parts=PARTS,
)
