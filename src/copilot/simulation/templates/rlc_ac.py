"""Series RLC on an AC source: resonance and phasors (F-014 S4). Renderer: web/sims/rlc_ac.js.

A sinusoidal source of rms voltage V and frequency f drives R, L and C in series (steady state):

    ω = 2πf,  X_L = ωL,  X_C = 1 / (ωC),  Z = √(R² + (X_L − X_C)²),  I = V / Z (rms),  φ = atan((X_L − X_C) / R)
    V_R = I R,  V_L = I X_L,  V_C = I X_C (V_L and V_C are opposite: V² = V_R² + (V_L − V_C)²)
    f₀ = 1 / (2π √(LC)),  Q = (1 / R) √(L / C),  P = I² R (average)
    φ > 0: the voltage leads the current (inductive); φ < 0: it lags (capacitive); f = f₀: Z = R, φ = 0

    V 10 V, f 50 Hz, R 10 Ω, L 0.1 H, C 100 µF: X_L 31.4 Ω, X_C 31.8 Ω, Z 10.0 Ω, I 0.999 A, φ −2.4°, f₀ 50.3 Hz, Q 3.16

The phasor diagram turns slowly on the stage (PHASOR_REV_S revolutions a second, a note says so); the resonance curve
is I against f from the solver (300 points), marked at the frequency said. The voltage said is the rms value; "a peak
voltage of 10 V" is read as V = 10 / √2 (computed). X_L needs f and L said, X_C f and C, f₀ L and C, Q R, L and C;
the current and the voltages need V too.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Line, Read, SimBase, Slot, Solution, Template, _Model, fmt, graph, known, si_scale, si_text,
    si_value_label,
)
from copilot.simulation.templates.rlc_transient import C_NAMES, L_NAMES, R_NAMES, RLC

PHASOR_REV_S = 0.25  # the stage's phasor turns per second (any real f: the angles are right, the speed is not)
N_PTS = 300

SLOTS = (
    Slot("voltage_v", "Source voltage (rms)", "V", "V", 0.1, 1e5, 1.0, 10.0, "voltage",
         names=r"supply|source|emf|e\.m\.f|rms voltage|voltage"),
    Slot("frequency_hz", "Frequency", "f", "Hz", 0.01, 1e8, 1.0, 50.0, "frequency",
         names=r"(?<!resonant )(?<!natural )frequency|\bf\b"),
    Slot("r_ohm", "Resistance", "R", "Ω", 0.01, 1e6, 1.0, 10.0, "resistance", names=R_NAMES),
    Slot("l_h", "Inductance", "L", "H", 1e-9, 100.0, 0.001, 0.1, "inductance", names=L_NAMES),
    Slot("c_f", "Capacitance", "C", "F", 1e-15, 10.0, 1e-6, 1e-4, "capacitance", names=C_NAMES),
)
ELEMENTS = (
    Element("source", "AC source"), Element("resistor", "Resistor"), Element("inductor", "Inductor"),
    Element("capacitor", "Capacitor"), Element("phasors", "Phasor diagram"), Element("graph", "Resonance curve"),
    Element("readout", "Values"),
)


class RlcAcParams(_Model):
    voltage_v: float = Field(default=10.0, ge=0.1, le=1e5)
    frequency_hz: float = Field(default=50.0, ge=0.01, le=1e8)
    r_ohm: float = Field(default=10.0, ge=0.01, le=1e6)
    l_h: float = Field(default=0.1, ge=1e-9, le=100.0)
    c_f: float = Field(default=1e-4, ge=1e-15, le=10.0)


class RlcAcSim(SimBase):
    template: Literal["rlc_ac"] = "rlc_ac"
    params: RlcAcParams = Field(default_factory=RlcAcParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("v", "f", "r", "l", "c", "xl", "xc", "vr", "vl", "vc", "i")


_SLOTS = {s.name: s for s in SLOTS}


def steady(V: float, f: float, R: float, L: float, C: float) -> dict[str, float]:
    w = 2 * math.pi * f
    xl, xc = w * L, 1 / (w * C)
    z = math.hypot(R, xl - xc)
    i = V / z
    return {"xl": xl, "xc": xc, "z": z, "i": i, "phi": math.degrees(math.atan2(xl - xc, R)),
            "vr": i * R, "vl": i * xl, "vc": i * xc, "f0": 1 / (2 * math.pi * math.sqrt(L * C)),
            "q": math.sqrt(L / C) / R, "p": i * i * R}


def solve(p: RlcAcParams, src: dict[str, str]) -> Solution:
    s = steady(p.voltage_v, p.frequency_hz, p.r_ohm, p.l_h, p.c_f)
    k = lambda *n: known(src, _SLOTS, *n)  # noqa: E731
    printed = lambda n: src.get(n, "default") in ("said", "teacher", "computed")  # noqa: E731
    src_of = lambda n: src.get(n, "default")  # noqa: E731
    z_ok = k("frequency_hz", "r_ohm", "l_h", "c_f")
    all_ok = z_ok and k("voltage_v")
    labels = {
        "v": si_value_label("V", p.voltage_v, "V", src_of("voltage_v"), printed("voltage_v")),
        "f": si_value_label("f", p.frequency_hz, "Hz", src_of("frequency_hz"), printed("frequency_hz")),
        "r": si_value_label("R", p.r_ohm, "Ω", src_of("r_ohm"), printed("r_ohm")),
        "l": si_value_label("L", p.l_h, "H", src_of("l_h"), printed("l_h")),
        "c": si_value_label("C", p.c_f, "F", src_of("c_f"), printed("c_f")),
        "xl": si_value_label("X_L", s["xl"], "Ω", "computed", k("frequency_hz", "l_h")),
        "xc": si_value_label("X_C", s["xc"], "Ω", "computed", k("frequency_hz", "c_f")),
        "vr": si_value_label("V_R", s["vr"], "V", "computed", all_ok),
        "vl": si_value_label("V_L", s["vl"], "V", "computed", all_ok),
        "vc": si_value_label("V_C", s["vc"], "V", "computed", all_ok),
        "i": si_value_label("I", s["i"], "A", "computed", all_ok),
    }
    derived: list[Derived] = []
    if k("l_h", "c_f"):
        derived.append(Derived(id="f0", label="Resonant frequency", symbol="f₀", value=s["f0"], unit="Hz",
                               text=si_text(s["f0"], "Hz")))
    if k("r_ohm", "l_h", "c_f"):
        derived.append(Derived(id="q", label="Quality factor", symbol="Q", value=s["q"], text=fmt(s["q"])))
    for key, sym, label, slots in (("xl", "X_L", "Inductive reactance", ("frequency_hz", "l_h")),
                                   ("xc", "X_C", "Capacitive reactance", ("frequency_hz", "c_f"))):
        if k(*slots):
            derived.append(Derived(id=key, label=label, symbol=sym, value=s[key], unit="Ω", text=si_text(s[key], "Ω")))
    if z_ok:
        derived.append(Derived(id="z", label="Impedance", symbol="Z", value=s["z"], unit="Ω", text=si_text(s["z"], "Ω")))
        lead = abs(s["phi"]) < 0.05
        how = "in phase: resonance" if lead else ("V leads I" if s["phi"] > 0 else "V lags I")
        derived.append(Derived(id="phi", label="Phase angle", symbol="φ", value=s["phi"], unit="°",
                               text=f"{fmt(s['phi']).replace('-', '−') if not lead else '0'}° ({how})"))
    if all_ok:
        derived.append(Derived(id="i", label="Current (rms)", symbol="I", value=s["i"], unit="A",
                               text=si_text(s["i"], "A")))
    # the resonance curve: I against f (the frequency said marked); numbers only with every input known
    f0 = s["f0"]
    f_hi = max(2.5 * f0, 1.3 * p.frequency_hz)
    bw = f0 / max(s["q"], 1e-9)  # the bandwidth: the peak is sampled finely within a few of them
    fs = sorted({*(f_hi * (j + 1) / N_PTS for j in range(N_PTS)),
                 *(f0 + bw * (j - 20) / 5 for j in range(41) if 0 < f0 + bw * (j - 20) / 5 <= f_hi)})
    kf, pf = si_scale(f_hi)
    curve = [steady(p.voltage_v, f, p.r_ohm, p.l_h, p.c_f)["i"] for f in fs]
    ku, pu = si_scale(max(curve))
    mark = (p.frequency_hz / kf, s["i"] / ku) if printed("frequency_hz") else None
    lines = [Line(id="i_f", xs=[f / kf for f in fs], ys=[c / ku for c in curve], role="applied", mark=mark)]
    series = [graph("I_f", "Resonance curve", ("f", f"{pf}Hz" if all_ok else ""), ("I", f"{pu}A" if all_ok else ""),
                    lines, all_ok, time=False, y_floor=0.0)]
    drive = {"xl": s["xl"], "xc": s["xc"], "phi": s["phi"], "vr": s["vr"], "vl": s["vl"], "vc": s["vc"],
             "v": p.voltage_v, "rev_s": PHASOR_REV_S, "still_t": 0.0}  # still: I along +x
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: RlcAcParams, src: dict[str, str]) -> list[str]:
    return ["source", "resistor", "inductor", "capacitor", "phasors", "graph", "readout"]


_PARALLEL = re.compile(r"\bparallel (?:rlc|lcr|r ?l ?c|l ?c ?r|resonance)\b|\b(?:rlc|lcr) (?:circuit )?in parallel\b"
                       r"|\banti-?resonance\b", re.I)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    m = _PARALLEL.search(line)
    return [("!", "A parallel RLC circuit is not drawn: the simulation is the series circuit", m.group(0),
             m.start())] if m else []


AC = r"a\.?c\.?|alternating"
TEMPLATE = Template(
    id="rlc_ac", name="RLC circuit: resonance and phasors", subject="electricity",
    sim=RlcAcSim, params=RlcAcParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        rf"\b{RLC}(?: series)? circuits?\b|\btun(?:ed|ing) circuits?\b"
        r"|\b(?:series )?resonan(?:ce|t) (?:in|of) (?:an? |the )?(?:series )?(?:rlc |lcr |a\.?c\.? |electrical |"
        r"series )?circuits?\b"
        r"|\bresonan(?:ce|t frequency)\b[^.;]{0,60}\b(?:inductors?|capacitors?|inductance|capacitance|rlc|lcr|"
        r"impedance|reactance)\b"
        r"|\b(?:inductors?|capacitors?|inductance|capacitance|impedance|reactance)\b[^.;]{0,60}\bresonan(?:ce|t)\b"
        r"|\bphasors?(?: diagrams?)?\b"
        rf"|\b(?:{AC}) (?:circuit|source|supply|voltage)\b[^.;]{{0,60}}\b(?:inductors?|capacitors?)\b"
        rf"|\b(?:inductors?|capacitors?)\b[^.;]{{0,60}}\b(?:{AC}) (?:circuit|source|supply|voltage)\b",
        re.IGNORECASE),
    lexicon=re.compile(r"\b(?:rlc|lcr|resonan\w*|phasors?|impedance|reactance|inductors?|inductance|capacitors?|"
                       r"capacitance|resistors?|frequency|hertz|current|voltage|phase|leads?|lags?|quality factor|"
                       r"bandwidth|rms|a\.?c\.?|alternating|power factor)\b", re.IGNORECASE),
    guard=re.compile(r"\bparallel (?:rlc|lcr|r ?l ?c|l ?c ?r)\b|\b(?:rlc|lcr) (?:circuit )?in parallel\b|"
                     r"\bresonance (?:structures?|hybrids?|energy)\b|\bresonating structures?\b|\bbenzene\b|"
                     r"\bmagnetic resonance\b|\b(?:nmr|mri|esr|epr)\b|\bresonates? with\b|\bresonan\w* (?:in|of) "
                     r"(?:a |the )?(?:voice|music|room|guitar|string|bridge|air column|tube|pipe)\b|\bacoustic\w*\b|"
                     r"\btacoma\b|\bmechanical resonance\b|\bsimple harmonic\b|\bSHM\b", re.IGNORECASE),
    aliases=("rlc", "lcr", "resonance", "phasor", "impedance", "reactance", "ac circuit", "inductor", "capacitor"),
    carry=("r_ohm", "l_h", "c_f"), family="rlc", parse=parse, listens=_PARALLEL.pattern,
    # "the resonant frequency is 50 Hz", "the impedance is 10 ohms", "the current is 2 A": results, not inputs
    results=re.compile(r"\b(?:resonan(?:t|ce) frequency|natural frequency|f ?0|f nought|impedance|reactance|"
                       r"current|power|v ?r|v ?l|v ?c|voltage across|charge|angular frequency|omega)\b", re.IGNORECASE),
    reads=(Read("voltage", r"\b(?:peak|maximum|max)\s+(?:value\s+of\s+(?:the\s+)?)?(?:voltage|emf|e\.m\.f)\b[^.;,]{0,20}$"
                r"|\bamplitude\b[^.;,]{0,20}$", "voltage_v", factor=1 / math.sqrt(2)),),
)
