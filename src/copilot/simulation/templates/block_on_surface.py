"""Block on a horizontal surface pushed by a horizontal force, with friction (F = ma). Renderer: web/sims/block_on_surface.js.

Textbook model: a rigid block, a uniform field g, one coefficient μ for starting and sliding (μs = μk unless said).
    W = m g,  N = W (the push is horizontal)
    the push F moves the block only when F > μN: then f = μN (kinetic), a = (F - f) / m
    otherwise the block stays at rest and static friction balances the push: f = F, a = 0
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, value_label,
)

EPS = 1e-9     # F == μN on paper may differ by a rounding error: still at rest (on the verge)
TRACK_M = 8.0  # how far the block slides before the motion repeats (drives the picture only, never printed)

SLOTS = (
    Slot("mass_kg", "Mass", "m", "kg", 0.01, 10_000.0, 0.1, 2.0, "mass"),
    Slot("applied_n", "Push", "F", "N", 0.0, 100_000.0, 1.0, 0.0, "force", absent=True),
    Slot("mu", "Coefficient of friction", "μ", "", 0.0, 2.0, 0.05, 0.0, "mu"),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True),
)
ELEMENTS = (
    Element("surface", "Surface"), Element("block", "Block"), Element("weight", "Weight"),
    Element("normal", "Normal force"), Element("applied", "Push"), Element("friction", "Friction"),
    Element("readout", "Values"),
)


class BlockOnSurfaceParams(_Model):
    mass_kg: float = Field(default=2.0, ge=0.01, le=10_000.0)
    applied_n: float = Field(default=0.0, ge=0.0, le=100_000.0)
    mu: float = Field(default=0.0, ge=0.0, le=2.0)
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class BlockOnSurfaceSim(SimBase):
    template: Literal["block_on_surface"] = "block_on_surface"
    params: BlockOnSurfaceParams = Field(default_factory=BlockOnSurfaceParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)


_SLOTS = {s.name: s for s in SLOTS}


def solve(p: BlockOnSurfaceParams, src: dict[str, str]) -> Solution:
    m, F, mu, g = p.mass_kg, p.applied_n, p.mu, p.g
    W = m * g
    N = W
    f_max = mu * N
    moving = F > f_max * (1 + EPS) + EPS
    f = f_max if moving else F
    a = (F - f) / m if moving else 0.0
    weight_ok = known(src, _SLOTS, "mass_kg", "g")
    all_ok = known(src, _SLOTS, "mass_kg", "applied_n", "mu", "g")
    said = lambda s: src.get(s, "default")  # noqa: E731
    labels = {
        "block": value_label("m", m, "kg", said("mass_kg"), said("mass_kg") in ("said", "teacher")),
        "weight": value_label("W", W, "N", "computed", weight_ok),
        "normal": value_label("N", N, "N", "computed", weight_ok),
        "applied": value_label("F", F, "N", said("applied_n"), said("applied_n") in ("said", "teacher")),
        "friction": value_label("f", f, "N", "computed", all_ok),
        "surface": value_label("μ", mu, "", said("mu"), said("mu") in ("said", "teacher")),
    }
    derived = []
    if all_ok:
        derived = [
            Derived(id="a", label="Acceleration", symbol="a", value=a, unit="m/s²", text=f"{fmt(a)} m/s²"),
            Derived(id="net", label="Net force", symbol="F_net", value=F - f, unit="N", text=f"{fmt(F - f)} N"),
        ]
    drive = {"m": m, "W": W, "N": N, "F": F, "f": f, "a": a, "moving": 1.0 if moving else 0.0, "track_m": TRACK_M}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: BlockOnSurfaceParams, src: dict[str, str]) -> list[str]:
    shown = ["surface", "block", "weight", "normal", "readout"]
    if p.applied_n > 0:
        shown.append("applied")
    if p.mu > 0:
        shown.append("friction")
    return shown


TEMPLATE = Template(
    id="block_on_surface", name="Block on a surface", subject="mechanics",
    sim=BlockOnSurfaceSim, params=BlockOnSurfaceParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    # a body AND a horizontal surface or a push / pull in the same line ("a block of 5 kg on a rough table")
    setup=re.compile(r"^(?=.*\b(?:block|box|crate|trolley|cart|brick|object|body|mass)\b)"
                     r"(?=.*\b(?:surface|floor|table|ground|road|push(?:es|ed|ing)?|pull(?:s|ed|ing)?|"
                     r"drag(?:s|ged|ging)?)\b)", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:friction\w*|push\w*|pull\w*|force|forces|newtons?|accelerat\w*|mass|weight|normal|"
                       r"slid\w*|mov(?:e|es|ed|ing)|rest|rough|smooth|frictionless|surface|block|box|kg|kilograms?|"
                       r"net)\b", re.IGNORECASE),
    guard=re.compile(r"\bblock (?:diagram|of code|chain|cipher|letters?|capitals?|size|level|schedule)|blockchain|"
                     r"code block|human body|body (?:language|mass index|of (?:the|a|an) (?:text|letter|essay|email|"
                     r"function|loop|paragraph))|box plot|black box|text box|object[- ]oriented|object (?:code|file)|"
                     r"(?:direct|indirect) object", re.IGNORECASE),
    aliases=("block", "friction", "force", "newton", "push", "f = ma", "surface", "horizontal"),
    carry=("mass_kg", "mu", "g"),
)
