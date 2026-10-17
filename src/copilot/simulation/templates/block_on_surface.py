"""Block on a horizontal surface pushed (or pulled) by a force, with friction (F = ma). Renderer:
web/sims/block_on_surface.js.

Textbook model: a rigid block, a uniform field g, one coefficient μ for starting and sliding (μs = μk unless said).
The force F acts at θ to the horizontal (θ = 0: horizontal, the S0 case). A push at θ presses the block into the
floor, a pull at θ lifts it a little (F-014 S1; the user's lecture of 2026-10-17: "a pushing force of 20 N is acted
at an angle of 30 degree with the horizontal"):
    W = m g,  F_x = F cos θ,  N = W + F sin θ (push)  or  W - F sin θ (pull)
    F_x > μN: the block slides, f = μN (kinetic), a = (F_x - f) / m
    otherwise it stays at rest and static friction balances F_x: f = F_x, a = 0
    a pull with F sin θ > W lifts the block off the floor: outside this model (nothing computed is printed)
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, value_label,
)
from copilot.simulation.names import FORCE, G, MASS, MU

EPS = 1e-9     # F == μN on paper may differ by a rounding error: still at rest (on the verge)
TRACK_M = 8.0  # how far the block slides before the motion repeats (drives the picture only, never printed)

SLOTS = (
    Slot("mass_kg", "Mass", "m", "kg", 0.01, 10_000.0, 0.1, 2.0, "mass", names=MASS),
    Slot("applied_n", "Push", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True, names=FORCE),
    # "pushed at an angle" with no number: drawn at 30°, N / f / a not printed (physics review 2026-10-17)
    Slot("push_angle_deg", "Angle of the push", "θ", "°", 0.0, 89.0, 1.0, 0.0, "angle", absent=True,
         names=r"angle|theta|θ", present=r"\bat an angle\b", present_value=30.0),
    Slot("mu", "Coefficient of friction", "μ", "", 0.0, 2.0, 0.05, 0.0, "mu", names=MU),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True, names=G),
)
ELEMENTS = (
    Element("surface", "Surface"), Element("block", "Block"), Element("weight", "Weight"),
    Element("normal", "Normal force"), Element("applied", "Push"), Element("friction", "Friction"),
    Element("angle", "Angle of the push"), Element("readout", "Values"),
)


class BlockOnSurfaceParams(_Model):
    mass_kg: float = Field(default=2.0, ge=0.01, le=10_000.0)
    applied_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    push_angle_deg: float = Field(default=0.0, ge=0.0, le=89.0)
    applied_mode: Literal["push", "pull"] = "push"  # at an angle: pressed into the floor, or pulled up from it
    mu: float = Field(default=0.0, ge=0.0, le=2.0)
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class BlockOnSurfaceSim(SimBase):
    template: Literal["block_on_surface"] = "block_on_surface"
    params: BlockOnSurfaceParams = Field(default_factory=BlockOnSurfaceParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)


_SLOTS = {s.name: s for s in SLOTS}


def solve(p: BlockOnSurfaceParams, src: dict[str, str]) -> Solution:
    m, F, mu, g = p.mass_kg, p.applied_n, p.mu, p.g
    th = math.radians(p.push_angle_deg)
    W = m * g
    Fx, Fy = F * math.cos(th), F * math.sin(th)
    N = W + Fy if p.applied_mode == "push" else W - Fy
    lifted = N < -EPS * max(1.0, W)
    N = max(0.0, N)
    f_max = mu * N
    # lifted off: the floor model no longer holds (it would rise too), so it is not slid along the floor
    moving = not lifted and Fx > f_max * (1 + EPS) + EPS
    f = f_max if moving else (0.0 if lifted else Fx)
    a = (Fx - f) / m if moving else 0.0
    weight_ok = known(src, _SLOTS, "mass_kg", "g")
    angled = F > 0 and p.push_angle_deg > 0
    # at an angle N depends on F, θ and on a push or a pull, which must have been said; horizontal: N = W
    mode_ok = not angled or src.get("applied_mode") in ("said", "teacher")
    normal_ok = weight_ok and (not angled or (known(src, _SLOTS, "applied_n", "push_angle_deg") and mode_ok))
    all_ok = known(src, _SLOTS, "mass_kg", "applied_n", "push_angle_deg", "mu", "g") and mode_ok and not lifted
    said = lambda s: src.get(s, "default")  # noqa: E731
    labels = {
        "block": value_label("m", m, "kg", said("mass_kg"), said("mass_kg") in ("said", "teacher")),
        "weight": value_label("W", W, "N", "computed", weight_ok),
        "normal": value_label("N", N, "N", "computed", normal_ok and not lifted),
        "applied": value_label("F", F, "N", said("applied_n"), said("applied_n") in ("said", "teacher")),
        "friction": value_label("f", f, "N", "computed", all_ok),
        "surface": value_label("μ", mu, "", said("mu"), said("mu") in ("said", "teacher")),
        "angle": value_label("θ", p.push_angle_deg, "°", said("push_angle_deg"),
                             said("push_angle_deg") in ("said", "teacher")),
    }
    derived = []
    if all_ok:
        derived = [
            Derived(id="a", label="Acceleration", symbol="a", value=a, unit="m/s²", text=f"{fmt(a)} m/s²"),
            Derived(id="net", label="Net force", symbol="F_net", value=Fx - f, unit="N", text=f"{fmt(Fx - f)} N"),
        ]
    drive = {"m": m, "W": W, "N": N, "F": F, "f": f, "a": a, "moving": 1.0 if moving else 0.0, "track_m": TRACK_M,
             "theta_deg": p.push_angle_deg, "pull": 1.0 if p.applied_mode == "pull" else 0.0,
             "lifted": 1.0 if lifted else 0.0}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: BlockOnSurfaceParams, src: dict[str, str]) -> list[str]:
    shown = ["surface", "block", "weight", "normal", "readout"]
    if p.applied_n > 0:
        shown.append("applied")
        if p.push_angle_deg > 0:
            shown.append("angle")
    if p.mu > 0:
        shown.append("friction")
    return shown


TEMPLATE = Template(
    id="block_on_surface", name="Block on a surface", subject="mechanics",
    sim=BlockOnSurfaceSim, params=BlockOnSurfaceParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    # a body AND a horizontal surface or a push / pull in the same line ("a block of 5 kg on a rough table", "a box on
    # a plane": a plane without "inclined" is the flat surface)
    setup=re.compile(r"^(?=.*\b(?:block|box|crate|trolley|cart|brick|object|body)\b)"  # not "mass": "the pull grows with the mass"
                     r"(?=.*\b(?:surface|floor|table|ground|road|plane|push(?:es|ed|ing)?|pull(?:s|ed|ing)?|"
                     r"drag(?:s|ged|ging)?)\b)", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:friction\w*|push\w*|pull\w*|force|forces|newtons?|accelerat\w*|mass|weight|normal|"
                       r"slid\w*|mov(?:e|es|ed|ing)|rest|rough|smooth|frictionless|surface|block|box|kg|kilograms?|"
                       r"net|angle|horizontal|coefficient)\b", re.IGNORECASE),
    guard=re.compile(r"\bblock (?:diagram|of code|chain|cipher|letters?|capitals?|size|level|schedule)|blockchain|"
                     r"code block|human body|body (?:language|mass index|of (?:the|a|an) (?:text|letter|essay|email|"
                     r"function|loop|paragraph))|box plot|black box|text box|object[- ]oriented|object (?:code|file)|"
                     r"(?:direct|indirect) object|(?:air|aero)plane|plane (?:of symmetry|mirror|wave|polari)",
                     re.IGNORECASE),
    aliases=("block", "friction", "force", "newton", "push", "pull", "f = ma", "surface", "horizontal"),
    family="block",
    carry=("mass_kg", "mu", "g"),
)
