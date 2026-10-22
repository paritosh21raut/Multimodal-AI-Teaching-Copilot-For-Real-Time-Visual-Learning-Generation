"""Series RLC step response (F-014 S4). Renderer: web/sims/rlc_transient.js.

A DC source V is switched on at t = 0 across R, L and C in series; the capacitor starts uncharged, no current flows
(V_C(0) = 0, i(0) = 0). With α = R / 2L, ω₀ = 1 / √(LC), ζ = α / ω₀ = (R / 2) √(C / L):

    underdamped  ζ < 1: ω_d = √(ω₀² − α²)
                 V_C = V [1 − e^(−αt) (cos ω_d t + (α / ω_d) sin ω_d t)],  i = V / (L ω_d) e^(−αt) sin ω_d t
                 peak V_C = V (1 + e^(−απ / ω_d)) at t = π / ω_d; peak i at t* = atan2(ω_d, α) / ω_d
    critical     ζ = 1: V_C = V [1 − (1 + αt) e^(−αt)],  i = (V / L) t e^(−αt); peak i = V / (eLα) at t = 1 / α
    overdamped   ζ > 1: s₁,₂ = −α ± √(α² − ω₀²);  V_C = V [1 + (s₂ e^(s₁t) − s₁ e^(s₂t)) / (s₁ − s₂)],
                 i = V / (L (s₁ − s₂)) (e^(s₁t) − e^(s₂t)); peak i at t* = ln(s₂ / s₁) / (s₁ − s₂)

    V 10 V, R 10 Ω, L 10 mH, C 100 µF: α 500 /s, ω₀ 1000 rad/s, ζ 0.5 (underdamped), f₀ 159 Hz, peak V_C 11.6 V,
    peak i 0.546 A; R 20 Ω: ζ 1 (critically damped), peak i 0.368 A; R 50 Ω: ζ 2.5 (overdamped).

The transient lasts micro- to milliseconds: the stage plays it in STAGE_S seconds (drive `t_end` real seconds), the
graphs' time axis is the real one (s / ms / µs). ζ and f₀ print with R, L and C said; anything in volts or amperes
needs V said too.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt, known, si_text, si_value_label, time_graph,
)

STAGE_S = 4.0       # stage seconds one run takes (then it holds HOLD_S and runs again)
HOLD_S = 1.5
N_PTS = 200         # samples per curve

VOLTAGE = r"battery|cell|emf|e\.m\.f|supply|source|step(?: voltage)?|d\.?c\.? (?:source|supply|voltage)|voltage"
R_NAMES = r"resistor|resistance|\bR\b"
L_NAMES = r"inductor|inductance|coil|\bL\b"
C_NAMES = r"capacitor|capacitance|\bC\b"

SLOTS = (
    Slot("voltage_v", "Source voltage (DC step)", "V", "V", 0.1, 1000.0, 0.5, 10.0, "voltage", names=VOLTAGE),
    Slot("r_ohm", "Resistance", "R", "Ω", 0.01, 1e6, 1.0, 10.0, "resistance", names=R_NAMES),
    Slot("l_h", "Inductance", "L", "H", 1e-9, 100.0, 0.001, 0.01, "inductance", names=L_NAMES),
    Slot("c_f", "Capacitance", "C", "F", 1e-15, 10.0, 1e-6, 1e-4, "capacitance", names=C_NAMES),
)
ELEMENTS = (
    Element("source", "Source + switch"), Element("resistor", "Resistor"), Element("inductor", "Inductor"),
    Element("capacitor", "Capacitor"), Element("current", "Current"), Element("graph", "V_C(t) and I(t)"),
    Element("readout", "Values"),
)


class RlcTransientParams(_Model):
    voltage_v: float = Field(default=10.0, ge=0.1, le=1000.0)
    r_ohm: float = Field(default=10.0, ge=0.01, le=1e6)
    l_h: float = Field(default=0.01, ge=1e-9, le=100.0)
    c_f: float = Field(default=1e-4, ge=1e-15, le=10.0)


class RlcTransientSim(SimBase):
    template: Literal["rlc_transient"] = "rlc_transient"
    params: RlcTransientParams = Field(default_factory=RlcTransientParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("v", "r", "l", "c", "slow")


_SLOTS = {s.name: s for s in SLOTS}
CRITICAL_TOL = 1e-6  # |ζ − 1| below this is critical damping (R = 2√(L/C) said exactly)


class Response:
    """The closed forms of one series RLC step response (V_C(t) and i(t)), and its regime."""

    def __init__(self, V: float, R: float, L: float, C: float) -> None:
        self.V, self.R, self.L, self.C = V, R, L, C
        self.alpha = R / (2 * L)
        self.w0 = 1 / math.sqrt(L * C)
        self.zeta = self.alpha / self.w0
        if abs(self.zeta - 1) <= CRITICAL_TOL:
            self.regime = "critically damped"
        elif self.zeta < 1:
            self.regime = "underdamped"
            self.wd = math.sqrt(self.w0 ** 2 - self.alpha ** 2)
        else:
            self.regime = "overdamped"
            r = math.sqrt(self.alpha ** 2 - self.w0 ** 2)
            self.s1, self.s2 = -self.alpha + r, -self.alpha - r  # s1 the slow root

    def vc(self, t: float) -> float:
        V, a = self.V, self.alpha
        if self.regime == "underdamped":
            return V * (1 - math.exp(-a * t) * (math.cos(self.wd * t) + a / self.wd * math.sin(self.wd * t)))
        if self.regime == "critically damped":
            return V * (1 - (1 + a * t) * math.exp(-a * t))
        s1, s2 = self.s1, self.s2
        return V * (1 + (s2 * math.exp(s1 * t) - s1 * math.exp(s2 * t)) / (s1 - s2))

    def i(self, t: float) -> float:
        V, L, a = self.V, self.L, self.alpha
        if self.regime == "underdamped":
            return V / (L * self.wd) * math.exp(-a * t) * math.sin(self.wd * t)
        if self.regime == "critically damped":
            return V / L * t * math.exp(-a * t)
        s1, s2 = self.s1, self.s2
        return V / (L * (s1 - s2)) * (math.exp(s1 * t) - math.exp(s2 * t))

    def t_peak_i(self) -> float:
        if self.regime == "underdamped":
            return math.atan2(self.wd, self.alpha) / self.wd
        if self.regime == "critically damped":
            return 1 / self.alpha
        return math.log(self.s2 / self.s1) / (self.s1 - self.s2)

    def t_end(self) -> float:
        """How long the graphs run: until it has settled (5 time constants of the slow decay), at most 6 periods."""
        if self.regime == "underdamped":
            return min(5 / self.alpha, 6 * 2 * math.pi / self.wd)
        if self.regime == "critically damped":
            return 7 / self.alpha
        return 5 / abs(self.s1)


def solve(p: RlcTransientParams, src: dict[str, str]) -> Solution:
    r = Response(p.voltage_v, p.r_ohm, p.l_h, p.c_f)
    printed = lambda s: src.get(s, "default") in ("said", "teacher", "computed")  # noqa: E731
    rlc = known(src, _SLOTS, "r_ohm", "l_h", "c_f")
    lc = known(src, _SLOTS, "l_h", "c_f")
    all_ok = rlc and known(src, _SLOTS, "voltage_v")
    labels = {
        "v": si_value_label("V", p.voltage_v, "V", src.get("voltage_v", "default"), printed("voltage_v")),
        "r": si_value_label("R", p.r_ohm, "Ω", src.get("r_ohm", "default"), printed("r_ohm")),
        "l": si_value_label("L", p.l_h, "H", src.get("l_h", "default"), printed("l_h")),
        "c": si_value_label("C", p.c_f, "F", src.get("c_f", "default"), printed("c_f")),
    }
    derived: list[Derived] = []
    if rlc:
        derived.append(Derived(id="zeta", label="Damping ratio", symbol="ζ", value=r.zeta,
                               text=f"{fmt(r.zeta)} ({r.regime})"))
    if lc:
        f0 = r.w0 / (2 * math.pi)
        derived.append(Derived(id="f0", label="Natural frequency", symbol="f₀", value=f0, unit="Hz",
                               text=si_text(f0, "Hz")))
    if all_ok:
        if r.regime == "underdamped":
            peak = r.V * (1 + math.exp(-r.alpha * math.pi / r.wd))
            derived.append(Derived(id="vpeak", label="Peak capacitor voltage", symbol="V_C,max", value=peak,
                                   unit="V", text=si_text(peak, "V")))
        ip = r.i(r.t_peak_i())
        derived.append(Derived(id="ipeak", label="Peak current", symbol="I_max", value=ip, unit="A",
                               text=si_text(ip, "A")))
    t_end = r.t_end()
    # the stage is slowed down: by how much, once R, L and C are known (the transient's length rests on them)
    labels["slow"] = SimLabel(symbol=f"slowed: {fmt(STAGE_S)} s here = {si_text(t_end, 's')} real" if rlc
                              else "slowed down")
    ts = [t_end * k / N_PTS for k in range(N_PTS + 1)]
    series = [time_graph("vc_t", "Capacitor voltage", ("V_C", "V"), ts, [r.vc(t) for t in ts], all_ok),
              time_graph("i_t", "Current", ("I", "A"), ts, [r.i(t) for t in ts], all_ok, role="applied")]
    if not rlc:  # the time axis' unit (ms, µs) rests on R, L and C: not printed while they are defaults
        series = [x.model_copy(update={"x_unit": ""}) for x in series]
    drive = {"t_end": t_end, "stage_s": STAGE_S, "hold_s": HOLD_S, "still_t": STAGE_S,
             "regime": {"underdamped": 0.0, "critically damped": 1.0, "overdamped": 2.0}[r.regime],
             "i_peak": r.i(r.t_peak_i()), "V": r.V}
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: RlcTransientParams, src: dict[str, str]) -> list[str]:
    # the step response is the point of this one: its graphs show from the start (the S2 strip is off elsewhere)
    return ["source", "resistor", "inductor", "capacitor", "current", "graph", "readout"]


_PARALLEL = re.compile(r"\bparallel (?:rlc|lcr|r ?l ?c|l ?c ?r)\b|\b(?:rlc|lcr) (?:circuit )?in parallel\b", re.I)
_CHARGED = re.compile(r"\b(?:initially|already|pre-?)\s*charged\b|\binitial charge\b", re.I)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    """Notices for what this template does not draw: a parallel RLC, a capacitor that starts charged."""
    out: list[tuple[str, Any, str, int]] = []
    m = _PARALLEL.search(line)
    if m:
        out.append(("!", "A parallel RLC circuit is not drawn: the simulation is the series circuit", m.group(0),
                    m.start()))
    m = _CHARGED.search(line)
    if m:
        out.append(("!", "The simulation starts with the capacitor uncharged and no current", m.group(0), m.start()))
    return out


RLC = r"(?:series\s+)?(?:rlc|lcr|r\s?l\s?c|l\s?c\s?r)"
TRANSIENT = (r"transients?|step (?:response|input|voltage)|damp\w*|switch(?:ed|es)? on|switch is closed|"
             r"d\.?c\.? (?:source|supply|voltage)|battery|charg\w*|natural response")
TEMPLATE = Template(
    id="rlc_transient", name="RLC step response", subject="electricity",
    sim=RlcTransientSim, params=RlcTransientParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        rf"\b{RLC}\b[^.;]{{0,60}}\b(?:{TRANSIENT})\b|\b(?:{TRANSIENT})\b[^.;]{{0,60}}\b{RLC}\b"
        r"|\b(?:transient|step) response of (?:an? |the )?(?:series )?circuit\b"
        r"|\b(?:under|over|critically)[- ]?damped\b[^.;]{0,60}\b(?:circuit|capacitor)\b"
        r"|\b(?:circuit|capacitor)\b[^.;]{0,60}\b(?:under|over|critically)[- ]?damped\b",
        re.IGNORECASE),
    lexicon=re.compile(r"\b(?:rlc|lcr|transient|damp\w*|inductors?|inductance|capacitors?|capacitance|resistors?|"
                       r"resistance|current|voltage|charg\w*|switch\w*|step|oscillat\w*|decay\w*|settles?|"
                       r"time constant|henry|farads?|ohms?|natural frequency)\b", re.IGNORECASE),
    guard=re.compile(r"\bparallel (?:rlc|lcr|r ?l ?c|l ?c ?r)\b|\b(?:rlc|lcr) (?:circuit )?in parallel\b|"
                     r"\bresonance (?:structures?|hybrids?)\b|\bdamp(?:ed|ens?|ing)? (?:the |our |their )?"
                     r"(?:spirits?|enthusiasm|mood|hopes?|cloth|towel|hair|soil|weather)\b|\btransient "
                     r"(?:population|workers?|visitors?|ischemic|global amnesia)\b|\bdamp (?:air|climate|room|walls?)\b|"
                     r"\ba\.?c\.? (?:source|supply|voltage|circuit)\b|\balternating\b|\bphasors?\b",
                     re.IGNORECASE),
    aliases=("rlc", "lcr", "transient", "step response", "damping", "underdamped", "overdamped", "inductor",
             "capacitor", "circuit"),
    carry=("r_ohm", "l_h", "c_f"), family="rlc", parse=parse,
    results=re.compile(r"\b(?:natural frequency|resonant frequency|peak\w*|maximum|damping ratio|time constant|"
                       r"overshoot|settl\w+|current|voltage across|across the (?:capacitor|inductor|resistor)|"
                       r"charge|angular frequency|omega)\b", re.IGNORECASE),
    listens=_PARALLEL.pattern + "|" + _CHARGED.pattern,
)
