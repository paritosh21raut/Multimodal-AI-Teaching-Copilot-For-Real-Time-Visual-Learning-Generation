"""Transverse travelling wave on a string: y(x, t) = A sin(2π (x/λ − f t)), travelling to the right. Renderer:
web/sims/wave.js (the shape and one marked particle of the string, which only moves up and down; every printed number
is from here).

    wave speed v = f λ,  period T = 1 / f
Inputs are f, λ and A. A speed said in the lecture is a result (v = f λ), not a third input: three inputs could
contradict each other.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, value_label,
)

SLOTS = (
    # a length said without a name is the wavelength ("a wave 2 m long"); the amplitude is named ("amplitude of 5 cm")
    Slot("wavelength_m", "Wavelength", "λ", "m", 0.001, 10_000.0, 0.01, 2.0, "length",
         names=r"wavelength|wave length|lambda|λ|distance between (?:two )?(?:successive |consecutive )?crests"),
    Slot("frequency_hz", "Frequency", "f", "Hz", 0.01, 100_000.0, 0.1, 1.0, "frequency",
         names=r"frequency|freq|oscillations? per second|vibrations? per second"),
    Slot("amplitude_m", "Amplitude", "A", "m", 0.0001, 100.0, 0.01, 0.3, "length",
         # "a 2 cm high wave", "each crest is 10 cm high" (wave review 2026-10-17)
         names=r"amplitude|height of (?:a|the) crest|maximum displacement|high|tall|height"),
)
ELEMENTS = (
    Element("axis", "Rest position"), Element("wave", "Wave"), Element("particle", "One particle"),
    Element("wavelength", "Wavelength"), Element("amplitude", "Amplitude"), Element("readout", "Values"),
)


class WaveParams(_Model):
    wavelength_m: float = Field(default=2.0, ge=0.001, le=10_000.0)
    frequency_hz: float = Field(default=1.0, ge=0.01, le=100_000.0)
    amplitude_m: float = Field(default=0.3, ge=0.0001, le=100.0)


class WaveSim(SimBase):
    template: Literal["wave"] = "wave"
    params: WaveParams = Field(default_factory=WaveParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)


_SLOTS = {s.name: s for s in SLOTS}
def period_text(T: float) -> str:
    """0.2 s, 2.27 ms, 10 µs: never "≈ 0 s" for a fast wave (wave review 2026-10-17)."""
    if T >= 0.1:
        return f"{fmt(T)} s"
    if T >= 1e-4:
        return f"{fmt(T * 1e3)} ms"
    return f"{fmt(T * 1e6)} µs"


SHOWN_HZ = 1.2  # the fastest the picture oscillates; a faster wave is shown slowed down, and the stage says so


def solve(p: WaveParams, src: dict[str, str]) -> Solution:
    lam, f, A = p.wavelength_m, p.frequency_hz, p.amplitude_m
    said = lambda s: src.get(s, "default")  # noqa: E731
    printed = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    labels = {
        "wavelength": value_label("λ", lam, "m", said("wavelength_m"), printed("wavelength_m")),
        "amplitude": value_label("A", A, "m", said("amplitude_m"), printed("amplitude_m")),
        "wave": value_label("f", f, "Hz", said("frequency_hz"), printed("frequency_hz")),
    }
    derived = []
    if known(src, _SLOTS, "frequency_hz", "wavelength_m"):
        derived.append(Derived(id="v", label="Wave speed", symbol="v", value=f * lam, unit="m/s",
                               text=f"{fmt(f * lam)} m/s"))
    if known(src, _SLOTS, "frequency_hz"):
        derived.append(Derived(id="T", label="Period", symbol="T", value=1 / f, unit="s", text=period_text(1 / f)))
    shown_f = min(f, SHOWN_HZ)
    drive = {"lambda": lam, "f": f, "A": A, "shown_f": shown_f, "slowed": f / shown_f}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: WaveParams, src: dict[str, str]) -> list[str]:
    return ["axis", "wave", "particle", "wavelength", "amplitude", "readout"]


TEMPLATE = Template(
    id="wave", name="Travelling wave", subject="waves",
    sim=WaveSim, params=WaveParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        # not "sine wave" alone: maths and signals (wave review 2026-10-17)
        r"\b(?:transverse|travel?ling|progressive|mechanical) waves?\b"
        r"|\bwaves? (?:on|along|in) (?:a|the) (?:string|rope|slinky|spring|water surface)\b|\bwaves? on water\b"
        r"|\bwaves?\b.*\b(?:frequency|wavelength)\b|\b(?:frequency|wavelength)\b.*\bwaves?\b", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:waves?|wavelength|frequency|amplitude|crests?|troughs?|period|hertz|hz|speed|velocity|"
                       r"oscillat\w*|vibrat\w*|particles?|medium|string|rope|transverse|longitudinal|lambda)\b",
                       re.IGNORECASE),
    guard=re.compile(r"\bmicrowaves?\b|\bheat ?waves?\b|\bwaves? of (?:protest|immigration|violence|strikes|"
                     r"infections?|covid|change|nostalgia)|\bbrain ?waves?\b|\bnew wave\b|\bcrime wave\b|"
                     r"\bmexican wave\b|\bwave (?:goodbye|hello|(?:his|her|their|your) hands?)\b|\bshort ?wave radio\b|"
                     r"\bfrequency of (?:use|words?|visits|errors|the disease)|\bword frequenc|"
                     # another picture (standing waves, square waves) or not a wave on a string (light, radio,
                     # signals): wave review 2026-10-17
                     r"\b(?:stationary|standing|square|triangle|sawtooth|electromagnetic|em|radio|light|sound|"
                     r"longitudinal|seismic) waves?\b|\bsignals?\b|\bfourier\b|\blight is\b|\bradio\b",
                     re.IGNORECASE),
    results=re.compile(r"\b(?:speed|velocity|travels? at|moves? at)\b", re.IGNORECASE),
    aliases=("wave", "wavelength", "frequency", "amplitude", "v = f lambda", "crest", "transverse"),
    restart_on=("wavelength_m", "frequency_hz"),
)
