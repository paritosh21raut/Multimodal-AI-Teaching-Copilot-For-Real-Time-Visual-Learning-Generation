"""DC circuit: an ideal cell (EMF V, no internal resistance) and two resistors in series or in parallel, ideal wires.
Renderer: web/sims/dc_circuit.js (charges drift round the circuit, faster where the current is larger; every printed
number is from here).

    series:    R_eq = R₁ + R₂,             I = V / R_eq,  I₁ = I₂ = I,   V₁ = I R₁,  V₂ = I R₂   (V₁ + V₂ = V)
    parallel:  R_eq = R₁ R₂ / (R₁ + R₂),   I = V / R_eq,  V₁ = V₂ = V,   I₁ = V / R₁, I₂ = V / R₂ (I₁ + I₂ = I)
    power from the cell P = V I
The arrangement must be said ("in series", "in parallel") before anything that depends on it is printed.
"""
from __future__ import annotations

import math

import re
from typing import Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, Slot, Solution, Template, _Model, fmt, known, Line, graph, value_label,
)

VOLTAGE = r"battery|cell|emf|e\.m\.f|voltage|potential difference|p\.d|supply|source"
R1 = r"r ?1|r one|first resistor|first resistance|resistor one|resistance one|one resistor"
R2 = r"r ?2|r two|second resistor|second resistance|resistor two|resistance two|other resistor|other one"

SLOTS = (
    Slot("voltage_v", "Cell voltage", "V", "V", 0.1, 1000.0, 0.5, 12.0, "voltage", names=VOLTAGE),
    Slot("r1_ohm", "Resistor 1", "R₁", "Ω", 0.1, 1e6, 1.0, 4.0, "resistance", names=R1),
    Slot("r2_ohm", "Resistor 2", "R₂", "Ω", 0.1, 1e6, 1.0, 6.0, "resistance", names=R2),
)
ELEMENTS = (
    Element("cell", "Cell"), Element("wires", "Wires"), Element("resistors", "Resistors"),
    Element("current", "Current (conventional)"), Element("currents", "Currents"), Element("voltages", "Voltages"),
    Element("graph", "Graph"), Element("readout", "Values"),
)


class DcCircuitParams(_Model):
    voltage_v: float = Field(default=12.0, ge=0.1, le=1000.0)
    r1_ohm: float = Field(default=4.0, ge=0.1, le=1e6)
    r2_ohm: float = Field(default=6.0, ge=0.1, le=1e6)
    arrangement: Literal["series", "parallel"] = "series"


class DcCircuitSim(SimBase):
    template: Literal["dc_circuit"] = "dc_circuit"
    params: DcCircuitParams = Field(default_factory=DcCircuitParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("r1", "r2", "i", "i1", "i2", "v1", "v2")


_SLOTS = {s.name: s for s in SLOTS}
_PREFIX = ((1e6, "M"), (1e3, "k"), (1.0, ""), (1e-3, "m"), (1e-6, "µ"))


def si(value: float, unit: str) -> tuple[float, str]:
    """4700 Ω -> (4.7, "kΩ"), 0.001 A -> (1, "mA"): the classroom form (circuit review 2026-10-17: "1e+06 Ω")."""
    a = abs(value)
    for k, p in _PREFIX:
        if a >= k * 0.9995 or k == 1e-6:
            return value / k, p + unit
    return value, unit


def si_label(symbol: str, value: float, unit: str, source: str, printable: bool):
    v, u = si(value, unit)
    return value_label(symbol, v, u, source, printable)


def solve(p: DcCircuitParams, src: dict[str, str]) -> Solution:
    V, R1v, R2v = p.voltage_v, p.r1_ohm, p.r2_ohm
    series = p.arrangement == "series"
    Req = R1v + R2v if series else R1v * R2v / (R1v + R2v)
    I = V / Req
    I1, I2 = (I, I) if series else (V / R1v, V / R2v)
    V1, V2 = (I * R1v, I * R2v) if series else (V, V)
    said = lambda s: src.get(s, "default")  # noqa: E731
    printed = lambda s: said(s) in ("said", "teacher")  # noqa: E731
    how = src.get("arrangement") in ("said", "teacher")
    all_ok = how and known(src, _SLOTS, "voltage_v", "r1_ohm", "r2_ohm")
    labels = {
        "cell": si_label("V", V, "V", said("voltage_v"), printed("voltage_v")),
        "r1": si_label("R₁", R1v, "Ω", said("r1_ohm"), printed("r1_ohm")),
        "r2": si_label("R₂", R2v, "Ω", said("r2_ohm"), printed("r2_ohm")),
        "i": si_label("I", I, "A", "computed", all_ok),
        "i1": si_label("I₁", I1, "A", "computed", all_ok),
        "i2": si_label("I₂", I2, "A", "computed", all_ok),
        "v1": si_label("V₁", V1, "V", "computed", all_ok),
        "v2": si_label("V₂", V2, "V", "computed", all_ok),
    }
    derived = []
    if all_ok:
        text = lambda v, u: "{} {}".format(fmt(si(v, u)[0]), si(v, u)[1])  # noqa: E731
        derived = [
            Derived(id="req", label="Equivalent resistance", symbol="R_eq", value=Req, unit="Ω", text=text(Req, "Ω")),
            Derived(id="i", label="Current from the cell", symbol="I", value=I, unit="A", text=text(I, "A")),
            Derived(id="p", label="Power from the cell (total)", symbol="P_cell", value=V * I, unit="W",
                    text=text(V * I, "W")),
        ]
    drive = {"I": I, "I1": I1, "I2": I2, "series": 1.0 if series else 0.0}
    # S2 graph: V-I of R1, R2 and the whole circuit (straight lines through 0: Ohm's law), each marked where it works
    top = max(I1, I2, I)
    k = si(top, "A")[0] / top  # displayed current units per ampere (mA: 1000)
    iu = si(top, "A")[1]
    line = lambda id, label, role, i, v: Line(id=id, label=label, role=role, xs=[0.0, 1.25 * i * k],  # noqa: E731
                                              ys=[0.0, 1.25 * v], mark=(i * k, v))
    series = [graph("V_I", "Voltage–current", ("I", iu), ("V", "V"),
                    [line("r1", "R₁", "applied", I1, V1), line("r2", "R₂", "pull", I2, V2),
                     line("eq", "R_eq", "ink", I, V)], all_ok, time=False)]
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: DcCircuitParams, src: dict[str, str]) -> list[str]:
    shown = ["cell", "wires", "resistors", "current", "readout"]
    if src.get("arrangement") in ("said", "teacher"):
        shown += ["currents", "voltages"]
    return shown


TEMPLATE = Template(
    id="dc_circuit", name="Series and parallel circuit", subject="electricity",
    sim=DcCircuitSim, params=DcCircuitParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(
        r"\b(?:series|parallel) circuits?\b"
        r"|\b(?:series|parallel) (?:combination|connection|arrangement)s? of (?:the )?(?:two |three )?"
        r"(?:resistors?|resistances?|bulbs?|lamps?|cells?|batteries)\b"
        r"|\b(?:resistors?|resistances?|bulbs?|lamps?|cells?|batteries) (?:are |is )?(?:connected |joined |placed |"
        r"arranged )?in (?:series|parallel)\b"
        # "registers in series and parallel" (Whisper's resistors, the user's lecture 2026-10-06), without "registers"
        # (CPU registers): the phrase "in series and parallel" itself
        r"|\bin series and (?:in )?parallel\b"
        # "In series, r equivalent equals to r1 plus r2" (the same lecture)
        r"|\b(?:equivalent resistance|r equivalent|r eq)\b"
        r"|\bcircuit\b.*\b(?:resistors?|battery|batteries|bulbs?|lamps?)\b"
        r"|\b(?:resistors?|battery|batteries)\b.*\bcircuit\b", re.IGNORECASE | re.DOTALL),
    lexicon=re.compile(r"\b(?:circuit|current|voltage|resistance|resistors?|ohms?|volts?|amp\w*|battery|cells?|series|"
                       r"parallel|potential difference|emf|power|watts?|equivalent|charges?|electrons?|branch\w*|"
                       r"junction)\b", re.IGNORECASE),
    guard=re.compile(r"\bintegrated circuits?\b|short[- ]circuit(?:ed|ing)? (?:the|our|your) (?:brain|thinking|process)|"
                     r"\bcircuit (?:court|training|board game)|racing circuit|\bparallel (?:universe|lines?|computing|"
                     r"processing|port|postulate)|in parallel with (?:this|that|the|our) (?:project|work|course)|"
                     r"\ba series of (?!resistors|bulbs|cells|batteries)|tv series|time series|taylor series|"
                     r"fourier series|power series|neural circuit|\bbrain\b|\bneur\w+|\bmembrane\b|\bspring|"
                     r"\bcapacitors?\b|\bregisters?\b(?! in series and)|\b(?:cpu|alu|processor)\b",
                     re.IGNORECASE),
    said_as=((r"\bin series\b|\bseries (?:circuit|combination|connection|arrangement)\b", "arrangement", "series"),
             (r"\bin parallel\b|\bparallel (?:circuit|combination|connection|arrangement)\b", "arrangement", "parallel")),
    aliases=("circuit", "series", "parallel", "resistor", "ohm", "current", "voltage", "electricity"),
)
