"""Circular orbit: a small satellite round a body of mass M (Earth, Moon, Mars, Sun, Jupiter), gravity the only
force. Renderer: web/sims/orbit.js (the satellite goes round, its velocity along the orbit and gravity to the centre;
every printed number is from here).

    r = R_body + h  (or the orbital radius said),  v = √(G M / r),  T = 2π r / v,  g(r) = G M / r²
The body must be said ("orbiting the Earth") before anything that depends on M is printed. An orbital radius said
wins over an altitude said; a radius at or below the surface is no orbit (nothing printed, the stage says so).
"""
from __future__ import annotations

import math
import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Read, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt, value_label,
)

G = 6.674e-11
BODIES = {  # mass (kg), mean radius (m)
    "earth": (5.972e24, 6.371e6), "moon": (7.342e22, 1.7374e6), "mars": (6.417e23, 3.3895e6),
    "sun": (1.989e30, 6.957e8), "jupiter": (1.898e27, 6.9911e7),
}
NAMES = {"earth": "Earth", "moon": "Moon", "mars": "Mars", "sun": "Sun", "jupiter": "Jupiter"}

SLOTS = (
    # "400 km above the Earth": a length said without a name is the altitude
    Slot("altitude_m", "Altitude", "h", "m", 0.0, 1e13, 1000.0, 400_000.0, "length",
         names=r"altitude|height|above the (?:surface|earth|moon|planet|ground)|above (?:the )?(?:earth|moon|mars)"),
    Slot("radius_m", "Orbital radius", "r", "m", 1e5, 1e13, 1000.0, 6.771e6, "length", absent=True,
         # centre-to-centre: "42164 km from the centre", "the Moon is 384400 km from the Earth" (orbit review 2026-10-17)
         names=r"orbital radius|orbit radius|radius of (?:the |its )?orbit|distance from the cent(?:re|er)|"
               r"from (?:the |its )?cent(?:re|er)|from the (?:earth|moon|mars|sun|jupiter|planet)"),
)
ELEMENTS = (
    Element("body", "Body"), Element("path", "Orbit"), Element("satellite", "Satellite"),
    Element("velocity", "Velocity"), Element("gravity", "Gravity"), Element("radius", "Radius"),
    Element("readout", "Values"),
)


class OrbitParams(_Model):
    altitude_m: float = Field(default=400_000.0, ge=0.0, le=1e13)
    radius_m: float = Field(default=6.771e6, ge=1e5, le=1e13)
    body: Literal["earth", "moon", "mars", "sun", "jupiter"] = "earth"


class OrbitSim(SimBase):
    template: Literal["orbit"] = "orbit"
    params: OrbitParams = Field(default_factory=OrbitParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("altitude",)


def length(m: float) -> tuple[float, str]:
    if abs(m) >= 1e9:  # 1 AU: "150 million km", not "1.5e+08 km" (orbit review 2026-10-17)
        return m / 1e9, "million km"
    return (m / 1000, "km") if abs(m) >= 1000 else (m, "m")


def duration(s: float) -> str:
    if s < 120:
        return f"{fmt(s)} s"
    if s < 7200:
        return f"{fmt(s / 60)} min"
    if s < 172_800:
        return f"{fmt(s / 3600)} h"
    return f"{fmt(s / 86_400)} days"


def speed(v: float) -> str:
    return f"{fmt(v / 1000)} km/s" if v >= 1000 else f"{fmt(v)} m/s"


def solve(p: OrbitParams, src: dict[str, str]) -> Solution:
    M, R = BODIES[p.body]
    said = lambda s: src.get(s, "default")  # noqa: E731
    printed = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    by_radius = printed("radius_m")
    r = p.radius_m if by_radius else R + p.altitude_m
    h = r - R
    above = r >= R * 0.9999  # at the surface is the ideal lowest orbit; below it there is none
    body_ok = printed("body")
    where_ok = by_radius or printed("altitude_m")
    all_ok = body_ok and where_ok and above
    v = math.sqrt(G * M / r) if r > 0 else 0.0
    T = 2 * math.pi * r / v if v > 0 else 0.0
    hv, hu = length(h)
    rv, ru = length(r)
    labels = {
        "body": SimLabel(text=NAMES[p.body], source="said") if body_ok else SimLabel(),  # the scene prints the name
        # the altitude is printed as said, or computed from a said radius once the body is known
        "altitude": value_label("h", hv, hu, said("altitude_m") if not by_radius else "computed",
                                (printed("altitude_m") and not by_radius) or (by_radius and body_ok and above)),
        "radius": value_label("r", rv, ru, "said" if by_radius else "computed",
                              by_radius or (body_ok and printed("altitude_m") and above)),
    }
    derived = []
    if all_ok:
        derived = [
            Derived(id="v", label="Orbital speed", symbol="v", value=v, unit="m/s", text=speed(v)),
            Derived(id="T", label="Period", symbol="T", value=T, unit="s", text=duration(T)),
            Derived(id="g", label="Gravity at the orbit", symbol="g_r", value=G * M / r ** 2, unit="m/s²",
                    text=f"{fmt(G * M / r ** 2)} m/s²"),
        ]
    drive = {"r": r, "R": R, "v": v, "T": T, "above": 1.0 if above else 0.0}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: OrbitParams, src: dict[str, str]) -> list[str]:
    return ["body", "path", "satellite", "velocity", "gravity", "radius", "readout"]


def _around(body: str) -> str:
    b = {"earth": r"earth", "moon": r"moon", "mars": r"mars", "sun": r"sun", "jupiter": r"jupiter"}[body]
    return (rf"\b(?:orbit(?:s|ing|ed)?|revolv\w*|goes|going|circl\w*|moves?|moving) (?:round |around |about )?"
            rf"(?:the )?{b}\b|\b(?:around|round|above|over) (?:the )?{b}\b|\b(?:the )?{b}'?s surface\b|"
            rf"\b(?:satellites?|moons?) of (?:the )?{b}\b|\b{b} satellites?\b")  # not "the Earth's orbit": that is the orbiter


TEMPLATE = Template(
    id="orbit", name="Circular orbit", subject="gravitation",
    sim=OrbitSim, params=OrbitParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        r"\bsatellites?\b.*\b(?:orbit\w*|revolv\w*|around|round|above)\b"
        r"|\b(?:circular|geostationary|geosynchronous|polar|low earth) orbits?\b"
        r"|\borbit(?:s|ing)? (?:round |around )?(?:the )?(?:earth|moon|mars|sun|jupiter|planet)\b"
        r"|\b(?:orbital speed|orbital velocity|orbital period)\b"
        r"|\b(?:moon|iss|space station|spacecraft|satellite)\b.*\b(?:goes|go|revolves?|travels?|moves?|circles?) "
        r"(?:round|around) (?:the )?(?:earth|moon|mars|sun|jupiter)\b", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:orbit\w*|satellites?|gravit\w*|planets?|earth|moon|mars|sun|jupiter|period|speed|"
                       r"velocity|altitude|radius|centripetal|kepler|newton|revolv\w*|geostationary)\b", re.IGNORECASE),
    # an ellipse is another picture (comets, Kepler's first law): orbit review 2026-10-17
    guard=re.compile(r"\borbitals?\b(?! (?:speed|velocity|period|radius))|\belectrons?\b|\bbohr\b|\beye\b|"
                     r"\bellip\w*|\bcomets?\b|"
                     r"\bsocket\b|\borbit of (?:his|her|their|its|our) (?:influence|friends|life)|\bsatellite "
                     r"(?:town|campus|office|city|dish|tv|television|channel|navigation|state)s?\b|"
                     r"\b(?:sun|moon) ?(?:light|rise|set|screen|burn|day)\b", re.IGNORECASE),
    said_as=tuple((_around(b), "body", b) for b in BODIES),
    # S2 (S1 open item): "the Moon orbits the Earth at 384000 km" is the Moon's distance from the Earth's centre (the
    # radius of its orbit), not a height above the surface (unless "above" / "high" is said)
    reads=(Read("length", r"\bmoon\b[^.;]*\b(?:orbit\w*|revolv\w*|goes (?:a)?round|moves (?:a)?round|circl\w*)\b[^.;]*$",
                "radius_m", after=r"(?!\s*(?:above|over|high|from the surface|altitude))"),),
    results=re.compile(r"\b(?:speed|velocity|period|takes|time)\b", re.IGNORECASE),
    aliases=("orbit", "satellite", "orbital speed", "gravitation", "geostationary", "kepler"),
    restart_on=("altitude_m", "radius_m"),
)
