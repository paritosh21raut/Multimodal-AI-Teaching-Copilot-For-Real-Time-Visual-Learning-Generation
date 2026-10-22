"""An ideal gas under a piston: P V = n R T and the gas laws (F-014 S4). Renderer: web/sims/gas_piston.js.

A fixed amount of gas in a cylinder closed by a free piston. The state is P (kPa), V (mL on the wire, said in L or
mL), T (K; °C said is converted) and n (mol); P V = n R T with R = 8.314 J/(mol K) (kPa · L = J):

    any three known: the fourth from P V = n R T
    a change with one quantity held (said: "at constant temperature", "isobaric", "in a rigid container"):
        T held (Boyle):        P₁V₁ = P₂V₂     P held (Charles):  V₁/T₁ = V₂/T₂     V held (Gay-Lussac): P₁/T₁ = P₂/T₂
    the third follows from the two said, n stays

    100 kPa, 2 L, 300 K: n = 100 · 2 / (8.314 · 300) = 0.0802 mol; then heated to 600 K at constant pressure: V = 4 L;
    then compressed to 1 L at constant temperature: P = 400 kPa (600 K)

Truthfulness: P, V, T, n print when said; the one worked out from the others prints computed; a change said without
what is held asks for it (a notice) and changes only what was said. The molecules' speed follows √T, their number is
fixed (the picture's), the piston's height follows V on a log scale (a doubling is one step up).
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import Derived, Element, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt
from copilot.simulation.values import spoken_number

R = 8.314
SLOTS = (
    Slot("p_kpa", "Pressure", "P", "kPa", 1.0, 10000.0, 1.0, 100.0, "pressure", names=r"pressure"),
    Slot("v_ml", "Volume", "V", "mL", 1.0, 100000.0, 10.0, 2000.0, "volume", names=r"volume"),
    Slot("t_k", "Temperature", "T", "K", 20.0, 3000.0, 1.0, 300.0, "temperature", names=r"temperature"),
    Slot("n_mol", "Amount of gas", "n", "mol", 0.0001, 100.0, 0.01, 0.08, "amount", names=r"moles?|amount"),
)
ELEMENTS = (
    Element("cylinder", "Cylinder"), Element("molecules", "Molecules"), Element("gauge", "Pressure gauge"),
    Element("thermometer", "Thermometer"), Element("readout", "Values"),
)
QTY = {"p": "p_kpa", "v": "v_ml", "t": "t_k", "n": "n_mol"}
RANGE = {sl.name: (sl.lo, sl.hi) for sl in SLOTS}
HOLD_NAME = {"t": "constant temperature (Boyle's law)", "p": "constant pressure (Charles's law)",
             "v": "constant volume (Gay-Lussac's law)"}


class GasParams(_Model):
    p_kpa: float = Field(default=100.0, ge=1.0, le=10000.0)
    v_ml: float = Field(default=2000.0, ge=1.0, le=100000.0)
    t_k: float = Field(default=300.0, ge=20.0, le=3000.0)
    n_mol: float = Field(default=0.08, ge=0.0001, le=100.0)
    hold: Literal["", "t", "p", "v"] = ""


class GasSim(SimBase):
    template: Literal["gas_piston"] = "gas_piston"
    params: GasParams = Field(default_factory=GasParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("p", "v", "t", "n", "hold")


def vol_text(ml: float) -> str:
    return f"{fmt(ml / 1000)} L" if ml >= 100 else f"{fmt(ml)} mL"


TEXT = {"p_kpa": lambda x: f"{fmt(x)} kPa", "v_ml": vol_text, "t_k": lambda x: f"{fmt(x)} K",
        "n_mol": lambda x: f"{fmt(x)} mol"}
SYM = {"p_kpa": "P", "v_ml": "V", "t_k": "T", "n_mol": "n"}


def missing(p: dict[str, float], unknown: str) -> float:
    """The one quantity from the other three (P V = n R T, P in kPa, V in L)."""
    P, V, T, n = p["p_kpa"], p["v_ml"] / 1000, p["t_k"], p["n_mol"]
    return {"p_kpa": n * R * T / V, "v_ml": 1000 * n * R * T / P, "t_k": P * V / (n * R), "n_mol": P * V / (R * T)}[unknown]


def solve(p: GasParams, src: dict[str, str]) -> Solution:
    said = lambda n: src.get(n, "default") in ("said", "teacher")  # noqa: E731
    comp = lambda n: src.get(n, "default") == "computed"  # noqa: E731
    vals = {k: getattr(p, k) for k in SYM}
    known = [k for k in SYM if said(k) or comp(k)]
    derived: list[Derived] = []
    draw = dict(vals)
    if len(known) == 3:  # the fourth from P V = n R T (printed only inside the range drawn)
        k4 = next(k for k in SYM if k not in known)
        draw[k4] = missing(vals, k4)
        lo, hi = RANGE[k4]
        if not lo <= draw[k4] <= hi:
            draw[k4] = max(lo, min(hi, draw[k4]))
        else:
                derived.append(Derived(id=k4, label=next(s.label for s in SLOTS if s.name == k4), symbol=SYM[k4],
                                   value=draw[k4], text=TEXT[k4](draw[k4])))
    labels = {
        k[0] if k != "n_mol" else "n": SimLabel(symbol=SYM[k], text=TEXT[k](vals[k]),
                                                source="computed" if comp(k) else src[k])  # type: ignore[arg-type]
        if (said(k) or comp(k)) else SimLabel(symbol=SYM[k])
        for k in SYM
    }
    labels = {"p": labels["p"], "v": labels["v"], "t": labels["t"], "n": labels["n"],
              "hold": SimLabel(symbol=HOLD_NAME[p.hold] if p.hold and said("hold") else "")}
    V_l = draw["v_ml"] / 1000
    drive = {"h": max(0.12, min(0.8, 0.45 + 0.12 * math.log2(max(V_l, 1e-6) / 2.0))),
             "speed": math.sqrt(max(draw["t_k"], 1.0) / 300.0), "gauge": max(0.0, min(1.0, math.log10(max(draw["p_kpa"], 1.0)) / 4.0)),
             "temp": max(0.0, min(1.0, draw["t_k"] / 1000.0)), "still_t": 1.0}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: GasParams, src: dict[str, str]) -> list[str]:
    return ["cylinder", "molecules", "gauge", "thermometer", "readout"]


# ---- speech: what is held, the amount in moles, a change worked out by the law said, notices -------------------------
_HOLD = ((re.compile(r"\b(?:constant|same|fixed) temperature\b|\bisotherm\w*\b|\bboyle'?s?\b|\btemperature (?:is )?"
                     r"(?:kept |held )?constant\b", re.I), "t"),
         (re.compile(r"\b(?:constant|same|fixed) pressure\b|\bisobaric\w*\b|\bcharles'?s?\b|\bpressure (?:is )?"
                     r"(?:kept |held )?constant\b|\bfree piston\b", re.I), "p"),
         (re.compile(r"\b(?:constant|same|fixed) volume\b|\bisochoric\w*\b|\bisovolumetric\b|\bgay[- ]lussac'?s?\b|"
                     r"\brigid (?:container|vessel|cylinder)\b|\bvolume (?:is )?(?:kept |held )?constant\b|"
                     r"\bpiston (?:is )?(?:locked|fixed|clamped)\b", re.I), "v"))
_MOL = re.compile(r"(?<![\w.])(?P<v>\d+(?:\.\d+)?|one|two|three|four|five|half a)\s+(?:moles?|mol)\b(?!\s*(?:per|/))",
                  re.IGNORECASE)
_TIMES = {"doubled": 2.0, "doubles": 2.0, "double": 2.0, "halved": 0.5, "halves": 0.5, "half": 0.5, "tripled": 3.0,
          "triples": 3.0, "triple": 3.0}
_SCALE = re.compile(r"\b(?P<q>pressure|volume|(?:absolute )?temperature)\s+(?:is\s+|gets\s+)?(?P<k>doubled|doubles|halved|"
                    r"halves|tripled|triples)\b|\b(?P<k2>double|halve|triple)s?\s+(?:the\s+)?(?P<q2>pressure|volume|"
                    r"(?:absolute )?temperature)\b", re.IGNORECASE)
_BY = re.compile(r"\b(?P<w>increas\w*|decreas\w*|rais\w*|lower\w*|heat\w*|cool\w*|ris\w*|rose|fall\w*|fell|"
                 r"drop\w*|reduc\w*|goes up|goes down|go up|go down|change\w*)\s+by\s*$", re.IGNORECASE)
_DOWN = re.compile(r"^(?:decreas|lower|cool|fall|fell|drop|reduc|goes down|go down)", re.IGNORECASE)
_CELSIUS = re.compile(r"celsius|centigrade|°\s*c\b|\bdegrees? c\b", re.IGNORECASE)
_NOT_DRAWN = (
    (re.compile(r"\badiabatic\w*\b", re.I), "An adiabatic change is not drawn: say what is held constant"),
    (re.compile(r"\breal gas\w*\b|\bvan der waals?\b|\bcompressibility\b", re.I),
     "A real gas is not drawn: the simulation is an ideal gas"),
    (re.compile(r"\bmixture of gases\b|\bpartial pressures?\b|\bdalton'?s\b", re.I), "A gas mixture is not drawn"),
)


def _before(st: dict, src: dict) -> tuple[dict[str, float], set[str]]:
    """The state before the line: the known quantities (said, set, computed), the fourth worked out when three are."""
    vals = {k: float(st[k]) for k in SYM if st.get(k) is not None}
    known = {k for k in vals if src.get(k) in ("said", "teacher", "computed")}
    if len(known) == 3 and len(vals) == 4:
        k4 = next(k for k in SYM if k not in known)
        vals[k4] = missing(vals, k4)
        known.add(k4)
    return vals, known


def _in_range(slot: str, x: float) -> bool:
    lo, hi = RANGE[slot]
    return lo <= x <= hi


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    st = state or {}
    src = st.get("_src", {}) or {}
    out: list[tuple[str, Any, str, int]] = []
    old, known = _before(st, src)
    hold = ""
    for rx, h in _HOLD:
        if (m := rx.search(line)) is not None:
            hold = h
            out.append(("hold", h, m.group(0), m.start()))
            break
    n_said = None
    if (m := _MOL.search(line)) is not None:
        v = 0.5 if m.group("v").lower() == "half a" else spoken_number(m.group("v"))
        if v:
            n_said = float(v)
            out.append(("n_mol", n_said, m.group(0), m.start()))
    # what this line changes: a value said (by its kind), a change by an amount ("heated by 100 K") or a scale
    kinds = {"pressure": "p_kpa", "volume": "v_ml", "temperature": "t_k"}
    new: dict[str, float] = {}
    by_amount: set[str] = set()
    for h in items:
        if h.start < 0 or h.kind not in kinds or h.value is None:
            continue
        slot = kinds[h.kind]
        if (b := _BY.search(line[:h.start])) is not None:  # "increased by 100 K": the change, not the new value
            out.append(("~", None, h.said, h.start))
            delta = h.value - (273.15 if slot == "t_k" and _CELSIUS.search(h.said) else 0.0)
            if slot in known:
                x = old[slot] + (-delta if _DOWN.match(b.group("w")) else delta)
                if _in_range(slot, x):
                    new.setdefault(slot, x)
                    by_amount.add(slot)
                    out.append((slot, x, "=" + SYM[slot], -1))
            continue
        new.setdefault(slot, h.value)
    for m in _SCALE.finditer(line):
        q = (m.group("q") or m.group("q2")).split()[-1].lower()
        k = _TIMES[(m.group("k") or m.group("k2")).lower()]
        slot = kinds[q]
        if slot in known and _in_range(slot, old[slot] * k):
            new.setdefault(slot, old[slot] * k)
            out.append((slot, old[slot] * k, m.group(0), m.start()))
    hold = hold or (st.get("hold") if src.get("hold") in ("said", "teacher") else "") or ""
    # a change of a full state: the law of the quantity held gives the third (n stays)
    full = all(QTY[q] in known for q in "pvt")
    changed = [k for k in new if k in old and abs(new[k] - old[k]) > 1e-9 * max(1.0, abs(new[k]))]
    back = ""
    applied = False
    if full and len(new) == 1 and len(changed) == 1:  # one quantity changed (a line stating a new state is not)
        held = QTY.get(hold, "")
        c = changed[0]
        if not _in_range(c, new[c]):
            back = f"{SYM[c]} said is outside what the simulation draws: not changed"
        elif not held or c == held:  # n would change without anyone saying so (or the held one changes)
            back = "Say what is held constant (temperature, pressure or volume) to work out the rest"
        else:
            third = next(QTY[q] for q in "pvt" if QTY[q] not in (c, held))
            ratio = new[c] / old[c]
            # T held: P V const -> the third (P or V) goes as 1 / ratio; P held: V / T const; V held: P / T const
            val = old[third] * (1 / ratio if held == "t_k" else ratio)
            if _in_range(third, val):
                out.append((third, val, "=" + SYM[third], -1))
                applied = True
            else:
                back = f"{SYM[third]} would be outside what the simulation draws: not changed"
    elif full and len(changed) == 2 and len(new) == 2:  # two changed, the third stays: does n stay too?
        after = {**old, **new}
        if abs(missing(after, "n_mol") / old["n_mol"] - 1) > 0.02:
            back = "These values change the amount of gas: say what is held constant"
        else:  # consistent: both are taken as said (a result word like "becomes" does not drop the second)
            out += [(k, new[k], "=" + SYM[k] if k in by_amount else next(
                (h.said for h in items if h.start >= 0 and kinds.get(h.kind) == k), SYM[k]), -1) for k in changed]
            out += [("~", None, h.said, h.start) for h in items if h.start >= 0]
            applied = True
    if back:
        out = [x for x in out if x[0] not in QTY.values() or x[0] == "n_mol"]
        out.append(("!", back, line[:12], 0))
        out += [("~", None, h.said, h.start) for h in items if h.start >= 0]
    elif not applied:  # four said that do not fit P V = n R T: kept as said, with a notice
        said_now = {k for k in SYM if src.get(k) in ("said", "teacher")} | set(new) | ({"n_mol"} if n_said else set())
        if (new or n_said) and said_now == set(SYM):
            after = {**old, **new, **({"n_mol": n_said} if n_said else {})}
            r = after["n_mol"] * R * after["t_k"] / (after["p_kpa"] * after["v_ml"] / 1000)
            if abs(r - 1) > 0.02:
                out.append(("!", f"These four values do not fit P V = n R T (n R T = {fmt(r)} × P V)", line[:12], 0))
    for rx, msg in _NOT_DRAWN:
        if (m := rx.search(line)) is not None:
            out.append(("!", msg, m.group(0), m.start()))
    return out


TEMPLATE = Template(
    id="gas_piston", name="An ideal gas under a piston", subject="physics",
    sim=GasSim, params=GasParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\bideal gas(?: law| equation)?\b|\bgas laws?\b|\bboyle'?s law\b|\bcharles'?s? law\b|"
                     r"\bgay[- ]lussac'?s? law\b|\bPV ?= ?nRT\b|\b(?:a|the) gas (?:in|inside) (?:a |the )?"
                     r"(?:cylinder|container|syringe|piston|vessel)\b|\bcylinder with a (?:movable |free )?piston\b|"
                     r"\b(?:isothermal|isobaric|isochoric) (?:process|change|expansion|compression)\b|"
                     r"\bgas\b[^.;]{0,40}\bcylinder\b[^.;]{0,30}\bpiston\b|\bair in (?:a|the) syringe\b",
                     re.IGNORECASE),
    lexicon=re.compile(r"\b(?:gas|gases|pressure|volume|temperature|kelvin|piston|cylinder|moles?|isothermal|isobaric|"
                       r"isochoric|boyle|charles|compress\w*|expand\w*|expansion|heated|cooled|molecules)\b", re.I),
    guard=re.compile(r"\bgas (?:station|stove|cylinder for cooking|bill|prices?|leak)\b|\bgreenhouse gas\w*\b|"
                     r"\bblood pressure\b|\bpeer pressure\b|\bhigh[- ]pressure (?:job|situation)\b|\bnatural gas\b|"
                     r"\bbody temperature\b|\bfever\b|\b(?:car|petrol|diesel|combustion) engines?\b", re.IGNORECASE),
    aliases=("gas", "ideal gas", "gas laws", "boyle's law", "charles's law", "piston", "pv = nrt"),
    parse=parse, listens=r"\b(?:constant (?:temperature|pressure|volume)|isotherm\w*|isobaric|isochoric|adiabatic|"
                         r"rigid|moles?|doubled|halved|tripled|double|halve|real gas)\b",
    results=re.compile(r"\b(?:new|final|becomes|will be)\b", re.IGNORECASE),
)
