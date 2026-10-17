"""Block on a horizontal surface, pushed and / or pulled, with friction (F = ma). Renderer:
web/sims/block_on_surface.js.

Textbook model: a rigid block, a uniform field g, one coefficient μ for starting and sliding (μs = μk unless said).
Two forces (S2, user 2026-10-18), either or both: a **push** (its arrow points onto the block, pressing it into the
floor when at an angle θp) and a **pull** (its arrow starts on the block and points away, lifting it a little when at
an angle θq). Each acts forward (+x, "in the direction of motion", to the right) or back ("against the motion"):
    W = m g,  F_x = sp F cos θp + sq P cos θq,  N = W + F sin θp - P sin θq
    |F_x| > μN: the block slides in the direction of F_x, f = μN (kinetic) against it, a = (|F_x| - μN) / m
    otherwise it stays at rest and static friction balances F_x: f = |F_x|, a = 0
    a pull with P sin θq > W + F sin θp lifts the block off the floor: outside this model (nothing computed is printed)
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, run_graphs, value_label,
)
from copilot.simulation.names import G, MASS, MU, PULL, PUSH

EPS = 1e-9     # F == μN on paper may differ by a rounding error: still at rest (on the verge)
TRACK_M = 8.0  # how far the block slides before the motion repeats (drives the picture only, never printed)

SLOTS = (
    Slot("mass_kg", "Mass", "m", "kg", 0.01, 10_000.0, 0.1, 2.0, "mass", names=MASS),
    Slot("applied_n", "Push", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True, names=PUSH),
    # "pushed at an angle" with no number: drawn at 30°, N / f / a not printed (physics review 2026-10-17)
    Slot("push_angle_deg", "Angle of the push", "θ", "°", 0.0, 89.0, 1.0, 0.0, "angle", absent=True,
         names=r"angle|theta|θ", present=r"^(?!.*\b(?:pull\w*|rope|drag\w*)\b).*\bat an angle\b",
         present_value=30.0, follows="applied_n"),
    Slot("pull_n", "Pull", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True, names=PULL),
    Slot("pull_angle_deg", "Angle of the pull", "θ", "°", 0.0, 89.0, 1.0, 0.0, "angle", absent=True,
         names=r"angle of (?:the )?pull|pull(?:ing)? angle", present=r"\b(?:pull\w*|rope|drag\w*)\b.*\bat an angle\b",
         present_value=30.0, follows="pull_n"),
    Slot("mu", "Coefficient of friction", "μ", "", 0.0, 2.0, 0.05, 0.0, "mu", names=MU),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True, names=G),
)
ELEMENTS = (
    Element("surface", "Surface"), Element("block", "Block"), Element("weight", "Weight"),
    Element("normal", "Normal force"), Element("applied", "Push"), Element("pull", "Pull"),
    Element("friction", "Friction"), Element("angle", "Angle of the push"), Element("pull_angle", "Angle of the pull"),
    Element("graph", "Graph"), Element("readout", "Values"),
)
DIRS = {"with": "forward", "against": "back"}  # spoken (values) -> applied_dir / pull_dir


class BlockOnSurfaceParams(_Model):
    mass_kg: float = Field(default=2.0, ge=0.01, le=10_000.0)
    applied_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    push_angle_deg: float = Field(default=0.0, ge=0.0, le=89.0)
    applied_dir: Literal["forward", "back"] = "forward"  # the push acts to the right (with the motion) or back
    pull_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    pull_angle_deg: float = Field(default=0.0, ge=0.0, le=89.0)
    pull_dir: Literal["forward", "back"] = "forward"
    mu: float = Field(default=0.0, ge=0.0, le=2.0)
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class BlockOnSurfaceSim(SimBase):
    template: Literal["block_on_surface"] = "block_on_surface"
    params: BlockOnSurfaceParams = Field(default_factory=BlockOnSurfaceParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)


_SLOTS = {s.name: s for s in SLOTS}


def solve(p: BlockOnSurfaceParams, src: dict[str, str]) -> Solution:
    m, F, P, mu, g = p.mass_kg, p.applied_n, p.pull_n, p.mu, p.g
    tp, tq = math.radians(p.push_angle_deg), math.radians(p.pull_angle_deg)
    sp = 1.0 if p.applied_dir == "forward" else -1.0
    sq = 1.0 if p.pull_dir == "forward" else -1.0
    W = m * g
    Fx = sp * F * math.cos(tp) + sq * P * math.cos(tq)
    N = W + F * math.sin(tp) - P * math.sin(tq)
    lifted = N < -EPS * max(1.0, W)
    N = max(0.0, N)
    f_max = mu * N
    # lifted off: the floor model no longer holds (it would rise too), so it is not slid along the floor
    moving = not lifted and abs(Fx) > f_max * (1 + EPS) + EPS
    direction = (1.0 if Fx > 0 else -1.0) if moving else 0.0
    f = f_max if moving else (0.0 if lifted else abs(Fx))
    f_dir = -direction if moving else (-1.0 if Fx > EPS else 1.0 if Fx < -EPS else 0.0)  # against the (tendency to) move
    a = (abs(Fx) - f) / m if moving else 0.0
    said = lambda s: src.get(s, "default")  # noqa: E731
    by_teacher = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    weight_ok = known(src, _SLOTS, "mass_kg", "g")
    # N depends on a force at an angle (its size and angle must be known). A direction not said is forward: "pull it
    # with 10 N and push with 20 N" is a push from behind and a pull in front, both with the motion (the teacher says
    # "in the opposite direction" / "back" otherwise)
    normal_ok = (weight_ok and (F == 0 or p.push_angle_deg == 0 or known(src, _SLOTS, "applied_n", "push_angle_deg"))
                 and (P == 0 or p.pull_angle_deg == 0 or known(src, _SLOTS, "pull_n", "pull_angle_deg")))
    all_ok = known(src, _SLOTS, "mass_kg", "applied_n", "push_angle_deg", "pull_n", "pull_angle_deg", "mu", "g") \
        and not lifted
    both = F > 0 and P > 0
    labels = {
        "block": value_label("m", m, "kg", said("mass_kg"), by_teacher("mass_kg")),
        "weight": value_label("W", W, "N", "computed", weight_ok),
        "normal": value_label("N", N, "N", "computed", normal_ok and not lifted),
        "applied": value_label("F_push" if both else "F", F, "N", said("applied_n"), by_teacher("applied_n")),
        "pull": value_label("F_pull" if both else "F", P, "N", said("pull_n"), by_teacher("pull_n")),
        "friction": value_label("f", f, "N", "computed", all_ok),
        "surface": value_label("μ", mu, "", said("mu"), by_teacher("mu")),
        "angle": value_label("θ", p.push_angle_deg, "°", said("push_angle_deg"), by_teacher("push_angle_deg")),
        "pull_angle": value_label("θ", p.pull_angle_deg, "°", said("pull_angle_deg"), by_teacher("pull_angle_deg")),
    }
    derived = []
    if all_ok:
        # which way, when the forces do not all point to the right (one may be "against the motion")
        mixed = (F > 0 and sp < 0) or (P > 0 and sq < 0)
        where = (" to the right" if direction > 0 else " to the left" if direction < 0 else "") if mixed else ""
        kind = "kinetic" if moving else "static"
        derived = [
            Derived(id="a", label="Acceleration", symbol="a", value=a, unit="m/s²", text=f"{fmt(a)} m/s²{where}"),
            Derived(id="net", label="Net force", symbol="F_net", value=abs(Fx) - f, unit="N",
                    text=f"{fmt(abs(Fx) - f)} N{where}"),
        ]
        if mu > 0:  # the friction force's value, also when it only holds the block (user 2026-10-18)
            derived.append(Derived(id="f", label="Friction", symbol="f", value=f, unit="N",
                                   text=f"{fmt(f)} N ({kind})" if f > 0 else "0 N"))
    drive = {"m": m, "W": W, "N": N, "F": F, "P": P, "f": f, "a": a, "moving": 1.0 if moving else 0.0,
             "dir": direction, "f_dir": f_dir, "track_m": TRACK_M, "theta_deg": p.push_angle_deg,
             "phi_deg": p.pull_angle_deg, "F_dir": sp, "P_dir": sq, "lifted": 1.0 if lifted else 0.0,
             # the stage says so only when it rests on known values (S2 review: not on a default mass)
             "lift_note": 1.0 if lifted and normal_ok else 0.0}
    # S2 graph: s-t and v-t of the run the stage plays; numbers only when a is printed
    series = run_graphs(a, moving, TRACK_M, all_ok)
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: BlockOnSurfaceParams, src: dict[str, str]) -> list[str]:
    shown = ["surface", "block", "weight", "normal", "readout"]
    if p.applied_n > 0:
        shown.append("applied")
        if p.push_angle_deg > 0:
            shown.append("angle")
    if p.pull_n > 0:
        shown.append("pull")
        if p.pull_angle_deg > 0:
            shown.append("pull_angle")
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
                       r"net|angle|horizontal|coefficient|rope|opposite|motion)\b", re.IGNORECASE),
    guard=re.compile(r"\bblock (?:diagram|of code|chain|cipher|letters?|capitals?|size|level|schedule)|blockchain|"
                     r"code block|human body|body (?:language|mass index|of (?:the|a|an) (?:text|letter|essay|email|"
                     r"function|loop|paragraph))|box plot|black box|text box|object[- ]oriented|object (?:code|file)|"
                     r"(?:direct|indirect) object|(?:air|aero)plane|plane (?:of symmetry|mirror|wave|polari)",
                     re.IGNORECASE),
    aliases=("block", "friction", "force", "newton", "push", "pull", "f = ma", "surface", "horizontal"),
    family="block",
    carry=("mass_kg", "mu", "g"),
    force_dirs=(("push", "applied_dir", DIRS), ("pull", "pull_dir", DIRS)),
)
