"""Block on an inclined plane, with friction and an optional push and / or pull along the slope. Renderer:
web/sims/incline.js.

Textbook model: a rigid block, a fixed rough plane at angle θ, one coefficient μ for starting and sliding.
Along the slope, positive = down the slope. The push's arrow points onto the block, the pull's starts on it and points
away (S2, user 2026-10-18); each acts up or down the slope ("against the motion" = up, "with the motion" = down: the
way the block would slide by itself):
    W = m g,  W∥ = m g sin θ,  W⊥ = m g cos θ,  N = W⊥ (both forces act along the slope)
    driving force D = W∥ ± F ± P (+ down the slope)
    |D| > μN: the block slides in the direction of D, kinetic friction f = μN opposes it, a = (|D| - μN) / m
    otherwise it stays at rest and static friction balances D: f = |D| against D, a = 0
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, run_graphs, value_label,
)
from copilot.simulation.names import ANGLE, G, MASS, MU, PULL, PUSH

TRACK_M = 8.0  # length of slope the block travels before the motion repeats (picture only, never printed)
EPS = 1e-9

SLOTS = (
    Slot("mass_kg", "Mass", "m", "kg", 0.01, 10_000.0, 0.1, 2.0, "mass", names=MASS),
    Slot("angle_deg", "Angle", "θ", "°", 0.0, 89.0, 1.0, 30.0, "angle", names=ANGLE),
    Slot("mu", "Coefficient of friction", "μ", "", 0.0, 2.0, 0.05, 0.0, "mu", names=MU),
    Slot("applied_n", "Push along the slope", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True, names=PUSH),
    Slot("pull_n", "Pull along the slope", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True, names=PULL),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True, names=G),
)
ELEMENTS = (
    Element("surface", "Incline"), Element("block", "Block"), Element("angle", "Angle"),
    Element("weight", "Weight"), Element("normal", "Normal force"), Element("friction", "Friction"),
    Element("applied", "Push"), Element("pull", "Pull"), Element("components", "Weight components"),
    Element("graph", "Graph"), Element("readout", "Values"),
)
DIRS = {"up": "up", "down": "down", "with": "down", "against": "up"}  # spoken (values) -> applied_dir / pull_dir


class InclineParams(_Model):
    mass_kg: float = Field(default=2.0, ge=0.01, le=10_000.0)
    angle_deg: float = Field(default=30.0, ge=0.0, le=89.0)
    mu: float = Field(default=0.0, ge=0.0, le=2.0)
    applied_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    applied_dir: Literal["up", "down"] = "up"  # the push acts up or down the slope
    pull_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    pull_dir: Literal["up", "down"] = "up"
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class InclineSim(SimBase):
    template: Literal["incline"] = "incline"
    params: InclineParams = Field(default_factory=InclineParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("w_par", "w_perp")  # the two weight components (element "components")


_SLOTS = {s.name: s for s in SLOTS}


def solve(p: InclineParams, src: dict[str, str]) -> Solution:
    m, th, mu, F, P, g = p.mass_kg, math.radians(p.angle_deg), p.mu, p.applied_n, p.pull_n, p.g
    W = m * g
    w_par, w_perp = W * math.sin(th), W * math.cos(th)
    N = w_perp
    F_down = F if p.applied_dir == "down" else -F    # the push, positive down the slope
    P_down = P if p.pull_dir == "down" else -P       # the pull
    D = w_par + F_down + P_down                      # driving force along the slope, positive down
    f_max = mu * N
    if abs(D) > f_max * (1 + EPS) + EPS:
        direction = 1.0 if D > 0 else -1.0           # +1 slides down, -1 moves up the slope
        f = f_max
        a = (abs(D) - f_max) / m
    else:
        direction = 0.0
        f = abs(D)                                   # static friction balances D exactly
        a = 0.0
    # friction acts against the motion, or against the tendency to move when at rest; + = down the slope
    f_dir = -direction if direction else (-1.0 if D > 0 else 1.0 if D < 0 else 0.0)
    said = lambda s: src.get(s, "default")  # noqa: E731
    weight_ok = known(src, _SLOTS, "mass_kg", "g")
    comp_ok = known(src, _SLOTS, "mass_kg", "g", "angle_deg")
    # a force whose direction was never said (only "push it with 20 N") is drawn up the slope but decides nothing
    # printed: up or down changes every result here
    dir_ok = (F == 0 or src.get("applied_dir") in ("said", "teacher")) and \
        (P == 0 or src.get("pull_dir") in ("said", "teacher"))
    all_ok = known(src, _SLOTS, "mass_kg", "angle_deg", "mu", "applied_n", "pull_n", "g") and dir_ok
    both = F > 0 and P > 0
    labels = {
        "block": value_label("m", m, "kg", said("mass_kg"), said("mass_kg") in ("said", "teacher")),
        "angle": value_label("θ", p.angle_deg, "°", said("angle_deg"), said("angle_deg") in ("said", "teacher")),
        "weight": value_label("W", W, "N", "computed", weight_ok),
        "normal": value_label("N", N, "N", "computed", comp_ok),
        "friction": value_label("f", f, "N", "computed", all_ok),
        "applied": value_label("F_push" if both else "F", F, "N", said("applied_n"), said("applied_n") in ("said", "teacher")),
        "pull": value_label("F_pull" if both else "F", P, "N", said("pull_n"), said("pull_n") in ("said", "teacher")),
        "w_par": value_label("mg sin θ", w_par, "N", "computed", comp_ok),
        "w_perp": value_label("mg cos θ", w_perp, "N", "computed", comp_ok),
        "surface": value_label("μ", mu, "", said("mu"), said("mu") in ("said", "teacher")),
    }
    derived = []
    if all_ok:
        where = " down the slope" if direction > 0 else " up the slope" if direction < 0 else ""
        net = (abs(D) - f) if direction else 0.0
        derived = [
            Derived(id="a", label="Acceleration", symbol="a", value=a, unit="m/s²", text=f"{fmt(a)} m/s²{where}"),
            Derived(id="net", label="Net force", symbol="F_net", value=net, unit="N", text=f"{fmt(net)} N{where}"),
        ]
        if mu > 0:  # the friction force's value, also when it only holds the block (user 2026-10-18)
            derived.append(Derived(id="f", label="Friction", symbol="f", value=f, unit="N",
                                   text=f"{fmt(f)} N ({'kinetic' if direction else 'static'})"
                                   if f > EPS * max(1.0, W) else "0 N"))  # a rounding error is no friction (S3)
    drive = {"m": m, "theta_deg": p.angle_deg, "W": W, "N": N, "w_par": w_par, "w_perp": w_perp, "F": F,
             "F_dir": 1.0 if p.applied_dir == "down" else -1.0, "P": P, "P_dir": 1.0 if p.pull_dir == "down" else -1.0,
             "f": f, "f_dir": f_dir, "a": a, "dir": direction,
             "track_m": TRACK_M}
    # S2 graph: distance along the slope and speed of the run the stage plays; numbers only when a is printed
    series = run_graphs(a, bool(direction), TRACK_M, all_ok)
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: InclineParams, src: dict[str, str]) -> list[str]:
    shown = ["surface", "block", "angle", "weight", "normal", "readout"]
    if p.mu > 0:
        shown.append("friction")
    if p.applied_n > 0:
        shown.append("applied")
    if p.pull_n > 0:
        shown.append("pull")
    return shown


TEMPLATE = Template(
    id="incline", name="Block on an incline", subject="mechanics",
    sim=InclineSim, params=InclineParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\b(?:inclined plane|incline|inclination|inclined (?:surface|plank|board|track)|slope|ramp|wedge|"
                     r"tilt(?:s|ed|ing)?)\b", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:friction\w*|incline\w*|slope|ramp|angle|degrees?|slid\w*|push\w*|pull\w*|force|forces|"
                       r"newtons?|accelerat\w*|mass|weight|normal|component\w*|sin|cos|sine|cosine|theta|rest|rough|"
                       r"smooth|frictionless|block|kg|kilograms?|net)\b", re.IGNORECASE),
    guard=re.compile(r"\bslope of (?:the|a|this|that) (?:line|graph|curve|tangent|function|secant)|slope[- ]intercept|"
                     r"slope (?:is|equals|=) (?:rise|dy|delta)|axial tilt|tilt of (?:the )?earth|earth'?s tilt|"
                     r"inclined to|ramp (?:function|signal|up)|block diagram|learning curve|"
                     r"\b(?:windward|leeward|rainfall|valley|vegetation|erosion|mountain|hill ?side)\b", re.IGNORECASE),
    aliases=("incline", "inclined plane", "slope", "ramp", "friction", "angle", "sin", "cos", "component"),
    family="block",
    carry=("mass_kg", "mu", "g", "applied_n", "pull_n"),  # S3: the forces too (not one pushed at an angle)
    force_dirs=(("push", "applied_dir", DIRS), ("pull", "pull_dir", DIRS)),
)
