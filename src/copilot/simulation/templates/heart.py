"""The human heart (F-014 S3): the four chambers, the path of the blood (double circulation) and the beat. Renderer:
web/sims/heart.js.

Blood path, six steps in order (textbook):
    1 body -> right atrium (venae cavae)            4 lungs -> left atrium (pulmonary veins)
    2 right atrium -> right ventricle (tricuspid)   5 left atrium -> left ventricle (mitral / bicuspid valve)
    3 right ventricle -> lungs (pulmonary valve,    6 left ventricle -> body (aortic valve, aorta)
      pulmonary artery)
The current step follows the speech (simulation.steps); a step nobody said is drawn with its number only.

The beat (a clock-driven cycle, at the said rate): one cardiac cycle lasts T = 60 / HR seconds. The textbook cycle of
0.8 s (75 beats per minute) is atrial systole 0.1 s, ventricular systole 0.3 s, joint diastole 0.4 s; the picture
keeps these fractions at any rate (1/8, 3/8, 1/2 of T: a simplification, at a fast rate diastole shortens most; the
phases are never printed). Valves follow the phases: the atrioventricular valves (tricuspid, mitral) are open except
in ventricular systole; the semilunar valves (pulmonary, aortic) open only in ventricular systole.

Printed numbers: the heart rate when said; computed from it: the time of one beat T = 60 / HR; with a stroke volume
said: cardiac output CO = HR x SV (72 x 70 mL = 5.04 L/min). A heart rate nobody said (72) only drives the picture.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Part, Read, SimBase, SimLabel, Slot, Solution, StepDef, Template, _Model, fmt, known,
)

ATRIAL, VENTRICULAR = 0.125, 0.375  # fractions of the cycle (0.1 s and 0.3 s of the textbook 0.8 s)

SLOTS = (
    Slot("rate_bpm", "Heart rate", "HR", "beats/min", 30.0, 220.0, 1.0, 72.0, "rate",
         names=r"heart ?rate|pulse(?: rate)?|beat rate|beats per minute|rate of (?:the )?(?:heart ?beat|heart)"),
    Slot("stroke_ml", "Stroke volume", "SV", "mL", 10.0, 200.0, 1.0, 70.0, "volume", names=r"stroke volume"),
)
_SV = r"stroke volume|pumps? out|ejects?|(?:in|with|per|during) (?:each|every|one|a single) (?:beat|contraction|heart ?beat)"
READS = (
    # "each beat lasts 0.8 seconds", "a cardiac cycle of 0.8 s": the rate, computed (60 / T)
    # a range ("60 to 100 times a minute"): its bound is no value (S3 review)
    Read("rate", r"\d\s*(?:to|-|–|or|and)\s*$", ""),
    # only the time said straight after the beat / cycle: "the ventricles contract for 0.3 s" in a cardiac-cycle line
    # is a phase, not one beat (S3 review)
    Read("time", r"(?:heart ?beat|beat|cardiac cycle)\s+(?:lasts|takes|is|of|=)(?:\s+(?:about|around|roughly|nearly|"
                 r"only|just))?\s*$", "rate_bpm", factor=60.0, inverse=True),
    # a volume is the stroke volume only when said so ("70 mL per beat", "the stroke volume is 70 mL")
    Read("volume", rf"(?:{_SV})[^.;]*$", "stroke_ml"),
    Read("volume", r"", "stroke_ml", after=r"\s*(?:of blood\s+)?(?:per|each|every|with each|in each|in one) (?:beat|contraction|heart ?beat)"),
    Read("volume", r"", ""),  # any other volume (the body's 5 litres of blood) sets nothing
)
STEPS = (
    StepDef("ra", "Body → right atrium",
            r"\bvenae? cavae?\b|\b(?:into|enters?|entering|to|reach\w*|returns? to|comes? (?:in)?to|fills?) the right atrium\b"
            r"|\bright atrium (?:receives|collects|gets)\b"),
    StepDef("rv", "Right atrium → right ventricle",
            r"\btricuspid\b|\b(?:into|enters?|entering|to|reach\w*|passes? (?:in)?to|fills?) the right ventricle\b"),
    StepDef("lungs", "Right ventricle → lungs",
            r"\bpulmonary (?:arter(?:y|ies)|trunk|valve)\b|\bpumps? (?:it |blood |the blood )?(?:to|towards) the lungs\b"
            r"|\b(?:blood|it)\b[^.;]{0,40}\b(?:to|towards) the lungs\b"),
    StepDef("la", "Lungs → left atrium",
            r"\bpulmonary veins?\b|\b(?:into|enters?|entering|to|reach\w*|returns? to|comes? (?:back )?(?:in)?to|fills?) the left atrium\b"
            r"|\bleft atrium (?:receives|collects|gets)\b"),
    StepDef("lv", "Left atrium → left ventricle",
            r"\bmitral\b|\bbicuspid\b|\b(?:into|enters?|entering|to|reach\w*|passes? (?:in)?to|fills?) the left ventricle\b"),
    StepDef("body", "Left ventricle → body",
            r"\baorta\b|\baortic\b|\b(?:to|into|out to|around) the (?:rest of the |whole |entire )?body\b"),
)
PARTS = (
    Part("ra", "Right atrium", r"\bright atri(?:um|a)\b"),
    Part("rv", "Right ventricle", r"\bright ventricles?\b"),
    Part("la", "Left atrium", r"\bleft atri(?:um|a)\b"),
    Part("lv", "Left ventricle", r"\bleft ventricles?\b"),
    Part("lungs", "Lungs", r"\blungs?\b"),
    Part("body", "Body", r"\b(?:rest of the |whole |entire )?body\b"),
    Part("vena_cava", "Vena cava", r"\bvenae? cavae?\b"),
    Part("pulmonary_artery", "Pulmonary artery", r"\bpulmonary (?:arter(?:y|ies)|trunk)\b"),
    Part("pulmonary_veins", "Pulmonary veins", r"\bpulmonary veins?\b"),
    Part("aorta", "Aorta", r"\baorta\b"),
)
ELEMENTS = (
    Element("chambers", "Chambers"), Element("vessels", "Blood vessels"), Element("valves", "Valves"),
    Element("blood", "Blood flow"), Element("lungs", "Lungs"), Element("body", "Body"), Element("readout", "Values"),
)


class HeartParams(_Model):
    rate_bpm: float = Field(default=72.0, ge=30.0, le=220.0)
    stroke_ml: float = Field(default=70.0, ge=10.0, le=200.0)


class HeartSim(SimBase):
    template: Literal["heart"] = "heart"
    params: HeartParams = Field(default_factory=HeartParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("rate", "ra", "rv", "la", "lv", "vena_cava", "pulmonary_artery", "pulmonary_veins", "aorta")


_SLOTS = {s.name: s for s in SLOTS}


def solve(p: HeartParams, src: dict[str, str]) -> Solution:
    T = 60.0 / p.rate_bpm
    rate_ok = known(src, _SLOTS, "rate_bpm")
    labels = {"rate": SimLabel(symbol="Heart rate", text=f"{fmt(p.rate_bpm)} beats/min",
                               source="computed" if src.get("rate_bpm") == "computed" else src.get("rate_bpm"))
              if rate_ok else SimLabel(symbol="Heart rate")}
    derived = []
    if rate_ok:
        derived.append(Derived(id="T", label="One beat", symbol="T", value=T, unit="s", text=f"{fmt(T)} s"))
        if known(src, _SLOTS, "stroke_ml"):
            co = p.rate_bpm * p.stroke_ml / 1000.0
            derived.append(Derived(id="co", label="Cardiac output", symbol="CO", value=co, unit="L/min",
                                   text=f"{fmt(co)} L/min"))
    drive = {"period_s": T, "atrial_s": ATRIAL * T, "ventricular_s": VENTRICULAR * T}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: HeartParams, src: dict[str, str]) -> list[str]:
    return ["chambers", "vessels", "valves", "blood", "lungs", "body", "readout"]


_STEP_WORDS = "|".join(d.words for d in STEPS)

TEMPLATE = Template(
    id="heart", name="The human heart", subject="biology",
    sim=HeartSim, params=HeartParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        r"\b(?:human|the|our|your|a|mammalian) heart (?:has|is (?:a|made|divided)|pumps|beats|works|contracts|consists)\b"
        r"|\b(?:chambers|structure|working|functioning|function) of (?:the |a |our )?(?:human )?heart\b"
        r"|\bfour[- ]chambered heart\b|\bdouble circulation\b|\bcardiac cycle\b"
        r"|\b(?:blood|circulation) (?:flows? )?(?:through|in) the heart\b|\bhow the heart (?:works|pumps|beats)\b"
        r"|\bthe human heart\b|\bthe heart\b[^.;]{0,40}\bpumps? (?:the )?blood\b", re.IGNORECASE),
    lexicon=re.compile(rf"{_STEP_WORDS}|\b(?:heart|atri(?:um|a)|ventricles?|valves?|blood|oxygenated|deoxygenated|"
                       rf"pumps?|beats?|contract\w*|relax\w*|systole|diastole|lungs?|arter(?:y|ies)|veins?|"
                       rf"circulation)\b", re.IGNORECASE),
    # the traps (user 2026-10-19): "the heart of the matter", "learn by heart", a network's heartbeat
    guard=re.compile(r"\bheart of (?:the|a|an|this|that|our|every|it)\b(?! human)|(?:^|[,;.]\s*)at heart\b|"
                     r"\bat the heart of\b|\bby heart\b|\b(?:change|piece) of heart\b|"
                     r"\b(?:leader|servers?|cluster|followers?|raft|timeouts?|packets?)\b|"
                     r"\bpoe(?:t|ts|m|ms|try)\b|\bbroken heart\b|"
                     r"\btake heart\b|\bheart(?:s)? (?:and|&) minds?\b|"
                     r"\bheart ?beat (?:message|packet|signal|protocol|interval|timer|thread)s?\b|\bsweetheart\b|"
                     r"\bheart[- ]?(?:shaped|felt|warming|broken|less)\b|\bkind[- ]hearted\b|\bwhole[- ]?hearted",
                     re.IGNORECASE),
    aliases=("heart", "circulation", "blood", "atrium", "ventricle", "cardiac cycle", "heartbeat"),
    reads=READS,
    results=re.compile(r"\b(?:cardiac output|blood volume)\b[^.;]*$", re.IGNORECASE),
    steps=STEPS, parts=PARTS,
)
