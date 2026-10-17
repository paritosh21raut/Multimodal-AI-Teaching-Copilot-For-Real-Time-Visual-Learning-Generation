"""Simple pendulum: a point bob on a light inextensible string, released from rest at the amplitude θ₀, no air
resistance. θ₀ ≤ 90°: past that a string goes slack at the release (its tension there is m g cos θ₀ < 0) and
the bob falls instead of swinging (physics review 2026-10-17). Renderer: web/sims/pendulum.js (it integrates θ'' = -(g/L) sin θ for the picture; every printed number is
from here).

    ω₀ = √(g/L),  small swings: T₀ = 2π √(L/g)
    any amplitude: T = 4 K(k) / ω₀ with k = sin(θ₀/2), K the complete elliptic integral of the first kind
                   (K = π / (2 AGM(1, √(1-k²))); T → T₀ as θ₀ → 0, T ≈ 1.018 T₀ at 30°)
    f = 1/T;  energy: h = L (1 - cos θ₀) (rise of the bob),  v_max = √(2 g h) (at the bottom)
The mass changes neither T nor v_max (that is the lesson); it sets the weight W = m g.
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, value_label,
)
from copilot.simulation.names import ANGLE, G, MASS

LENGTH = r"length(?: of the (?:string|pendulum|thread))?|string|thread|pendulum|long"
AMPLITUDE = rf"amplitude|displace(?:d|ment)|pulled (?:aside|back)|released (?:at|from)|{ANGLE}"

SLOTS = (
    Slot("length_m", "Length", "L", "m", 0.05, 100.0, 0.01, 1.0, "length", names=LENGTH),
    Slot("amplitude_deg", "Amplitude", "θ₀", "°", 1.0, 90.0, 1.0, 20.0, "angle", names=AMPLITUDE),
    Slot("mass_kg", "Mass of the bob", "m", "kg", 0.001, 1000.0, 0.01, 0.5, "mass", names=MASS + r"|bob"),
    Slot("g", "Gravity", "g", "m/s²", 0.1, 30.0, 0.01, 9.81, "g", standard=True, names=G),
)
ELEMENTS = (
    Element("support", "Support"), Element("string", "String"), Element("bob", "Bob"), Element("angle", "Amplitude"),
    Element("path", "Path"), Element("velocity", "Velocity"), Element("weight", "Weight"), Element("readout", "Values"),
)


class PendulumParams(_Model):
    length_m: float = Field(default=1.0, ge=0.05, le=100.0)
    amplitude_deg: float = Field(default=20.0, ge=1.0, le=90.0)
    mass_kg: float = Field(default=0.5, ge=0.001, le=1000.0)
    g: float = Field(default=9.81, ge=0.1, le=30.0)


class PendulumSim(SimBase):
    template: Literal["pendulum"] = "pendulum"
    params: PendulumParams = Field(default_factory=PendulumParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("length",)


_SLOTS = {s.name: s for s in SLOTS}


def agm(a: float, b: float) -> float:
    while abs(a - b) > 1e-15 * a:
        a, b = (a + b) / 2, math.sqrt(a * b)
    return a


def period(length_m: float, amplitude_deg: float, g: float) -> float:
    """The exact period of a pendulum released from rest at amplitude_deg (s)."""
    k = math.sin(math.radians(amplitude_deg) / 2)
    K = math.pi / (2 * agm(1.0, math.sqrt(1 - k * k)))
    return 4 * K / math.sqrt(g / length_m)


def solve(p: PendulumParams, src: dict[str, str]) -> Solution:
    L, th0, m, g = p.length_m, math.radians(p.amplitude_deg), p.mass_kg, p.g
    T0 = 2 * math.pi * math.sqrt(L / g)
    T = period(L, p.amplitude_deg, g)
    h = L * (1 - math.cos(th0))
    v_max = math.sqrt(2 * g * h)
    said = lambda s: src.get(s, "default")  # noqa: E731
    printed = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    length_ok = known(src, _SLOTS, "length_m", "g")
    swing_ok = length_ok and known(src, _SLOTS, "amplitude_deg")
    labels = {
        "length": value_label("L", L, "m", said("length_m"), printed("length_m")),
        "angle": value_label("θ₀", p.amplitude_deg, "°", said("amplitude_deg"), printed("amplitude_deg")),
        "bob": value_label("m", m, "kg", said("mass_kg"), printed("mass_kg")),
        "weight": value_label("W", m * g, "N", "computed", known(src, _SLOTS, "mass_kg", "g")),
    }
    derived: list[Derived] = []
    if swing_ok:  # the exact period needs the amplitude too
        derived = [
            Derived(id="T", label="Period", symbol="T", value=T, unit="s", text=f"{fmt(T)} s"),
            Derived(id="f", label="Frequency", symbol="f", value=1 / T, unit="Hz", text=f"{fmt(1 / T)} Hz"),
            Derived(id="v", label="Speed at the bottom", symbol="v_max", value=v_max, unit="m/s",
                    text=f"{fmt(v_max)} m/s"),
        ]
    elif length_ok:  # the amplitude was not said: the small-swing period, said as such
        derived = [Derived(id="T", label="Period (small swings)", symbol="T", value=T0, unit="s",
                           text=f"≈ {fmt(T0)} s (small swings)")]
    drive = {"L": L, "theta0_deg": p.amplitude_deg, "T": T, "m": m, "W": m * g, "g": g}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: PendulumParams, src: dict[str, str]) -> list[str]:
    shown = ["support", "string", "bob", "angle", "path", "readout"]
    if src.get("mass_kg") in ("said", "teacher"):
        shown.append("weight")
    return shown


TEMPLATE = Template(
    id="pendulum", name="Simple pendulum", subject="mechanics",
    sim=PendulumSim, params=PendulumParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\b(?:simple )?pendulum\b|\bbob\b.*\b(?:string|thread)\b|\b(?:string|thread)\b.*\bbob\b",
                     re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:pendulum|swing\w*|oscillat\w*|period|frequency|bob|string|thread|length|amplitude|"
                       r"gravity|seconds?|time period|harmonic|restoring|vibration|to and fro|mean position|"
                       r"extreme position|release\w*|degrees?|metres?|meters?)\b", re.IGNORECASE),
    # the metaphor ("the pendulum of public opinion has swung back"), not "a pendulum of length 2 m"
    guard=re.compile(r"\bpendulum of (?:public|history|opinion|fashion|politics|power|fortune|taste)|"
                     r"\bpendulum (?:has swung|swings? back)|\bswung back\b|swing (?:states?|voters?)|mood swings?|"
                     r"\bbob (?:dylan|marley)\b|\bpolitical pendulum", re.IGNORECASE),
    aliases=("pendulum", "swing", "oscillation", "period", "bob", "simple harmonic"),
    carry=("g",),
    restart_on=("length_m", "amplitude_deg", "g"),
)
