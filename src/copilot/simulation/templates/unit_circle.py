"""Unit circle → sine: a point goes round the circle of radius 1; its height is sin φ and its horizontal position cos φ,
and the height traced against the angle draws the sine curve. Renderer: web/sims/unit_circle.js (the point sweeps one
turn every few seconds; an angle said in the lecture is marked and its sin, cos and tan printed, from here).

    P = (cos θ, sin θ),  tan θ = sin θ / cos θ (undefined where cos θ = 0: 90°, 270°)
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt, value_label,
)

SLOTS = (
    Slot("angle_deg", "Angle", "θ", "°", 0.0, 720.0, 5.0, 30.0, "angle", names=r"angle|theta|θ"),
)
ELEMENTS = (
    Element("axes", "Axes"), Element("circle", "Unit circle"), Element("point", "Moving point"),
    Element("graph", "Sine curve"), Element("marked", "Marked angle"), Element("components", "sin and cos"),
    Element("readout", "Values"),
)


class UnitCircleParams(_Model):
    angle_deg: float = Field(default=30.0, ge=0.0, le=720.0)


class UnitCircleSim(SimBase):
    template: Literal["unit_circle"] = "unit_circle"
    params: UnitCircleParams = Field(default_factory=UnitCircleParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("theta", "sin", "cos")


def trig(deg: float) -> tuple[float, float, float | None]:
    """sin, cos, tan of an angle in degrees, exact at the multiples of 90° (no "1.2e-16"); tan None where undefined."""
    r = math.radians(deg)
    s, c = math.sin(r), math.cos(r)
    s, c = (0.0 if abs(s) < 1e-12 else s), (0.0 if abs(c) < 1e-12 else c)
    return s, c, (None if c == 0.0 else s / c)


def num(x: float) -> str:
    return fmt(x).replace("-", "−")  # the minus sign, as on the axes ("−0.866", not "-0.866")


def solve(p: UnitCircleParams, src: dict[str, str]) -> Solution:
    th = p.angle_deg
    said = src.get("angle_deg", "default") in ("said", "teacher")
    s, c, tn = trig(th)
    labels = {
        "theta": value_label("θ", th, "°", src.get("angle_deg", "default"), said),
        "sin": SimLabel(symbol="sin θ", text=num(s), source="computed") if said else SimLabel(symbol="sin θ"),
        "cos": SimLabel(symbol="cos θ", text=num(c), source="computed") if said else SimLabel(symbol="cos θ"),
    }
    derived = []
    if said:
        derived = [
            Derived(id="sin", label="sine", symbol="sin θ", value=s, unit="", text=num(s)),
            Derived(id="cos", label="cosine", symbol="cos θ", value=c, unit="", text=num(c)),
            Derived(id="tan", label="tangent", symbol="tan θ", value=tn if tn is not None else 0.0, unit="",
                    text=num(tn) if tn is not None else "undefined"),  # value 0 there: read the text
        ]
    drive = {"theta": th, "marked": 1.0 if said else 0.0}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: UnitCircleParams, src: dict[str, str]) -> list[str]:
    shown = ["axes", "circle", "point", "graph", "components", "readout"]
    if src.get("angle_deg") in ("said", "teacher"):
        shown.append("marked")
    return shown


TEMPLATE = Template(
    id="unit_circle", name="Unit circle and the sine curve", subject="trigonometry",
    sim=UnitCircleSim, params=UnitCircleParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        # the sine only: the scene draws no cosine curve (unit circle review 2026-10-17)
        r"\bunit circle\b|\bgraph of (?:the )?(?:sine|sin)(?: function| curve| theta| x)?\b"
        r"|\bsine (?:curve|graph|function)\b|\bsine wave from (?:a|the) circle\b"
        r"|\b(?:sine|sin) (?:theta|θ|x)\b.*\b(?:graph|curve|circle)\b", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:sine|sin|cosine|cos|tangent|tan|theta|angle|degrees?|radians?|circle|radius|"
                       r"trigonometr\w*|quadrant|periodic|graph|curve|unit)\b", re.IGNORECASE),
    guard=re.compile(r"\bcircle of (?:friends|life|trust)\b|\binner circle\b|\bfull circle\b|\bvicious circle\b|"
                     r"\bsine qua non\b|\bsignals?\b|\bfourier\b|\bcomplex (?:numbers?|plane)\b|\bcos(?:ine)? (?:x|theta|θ|curve|graph)\b",
                     re.IGNORECASE),
    aliases=("unit circle", "sine", "sine curve", "cosine", "trigonometry", "sin theta"),
)
