"""p-n junction (F-014 S4). Renderer: web/sims/pn_junction.js.

An abrupt junction, acceptors N_A on the p side, donors N_D on the n side, at 300 K (user 2026-10-20: silicon with its
standard constants, germanium only when said). Depletion approximation:

    V_T = kT / q = 0.025852 V;  V_bi = V_T ln(N_A N_D / n_i²)
    W = √(2 ε (V_bi − V) / q · (N_A + N_D) / (N_A N_D)),  x_p = W N_D / (N_A + N_D),  x_n = W N_A / (N_A + N_D)
    E_max = q N_A x_p / ε (at the junction);  ideal diode: I = I_s (e^(V / V_T) − 1)
    silicon n_i = 1.0 × 10¹⁰ cm⁻³, ε_r = 11.7; germanium n_i = 2.4 × 10¹³ cm⁻³, ε_r = 16.0

    Si, N_A = N_D = 10¹⁶ cm⁻³, no bias: V_bi = 0.025852 ln(10¹²) = 0.7143 V, W = 0.4298 µm, E_max = 33.2 kV/cm;
    5 V reverse: W = 0.4298 √(5.714 / 0.714) = 1.216 µm; I_s = 10⁻¹² A and 0.6 V forward: I = 10⁻¹² (e^23.209 − 1) = 12.0 mA

V (bias) > 0 is forward. At or above V_bi the depletion approximation fails: W is not printed (a note says why). The
I–V curve's numbers need I_s said; V_bi and W need both dopings. Breakdown, Zener, LEDs, photodiodes and transistors
are not drawn (notices). The carriers (holes, electrons) are a decorative particle layer: no number rests on them.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Line, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt, graph, known, si_scale,
    si_text,
)
from copilot.simulation.values import spoken_number

K_B = 8.617333262e-5   # eV/K
T_K = 300.0
VT = K_B * T_K         # 0.025852 V
Q = 1.602176634e-19    # C
EPS0 = 8.8541878128e-14  # F/cm
BREAKDOWN_V_CM = 3e5   # about where silicon breaks down (avalanche): above it a note, the picture goes on
I_LIMIT = 1.0          # A: the ideal diode law past this is not printed
MATERIAL = {"si": ("silicon", 1.0e10, 11.7, 1e-12), "ge": ("germanium", 2.4e13, 16.0, 1e-6)}  # name, n_i, ε_r, shape I_s

SLOTS = (
    Slot("na_cm3", "Acceptor doping (p side)", "N_A", "cm⁻³", 1e13, 1e20, 1e15, 1e16, "doping",
         names=r"acceptors?|acceptor (?:doping|concentration|density)|p[- ]?(?:side|type|region)|N_?A|N sub A"),
    Slot("nd_cm3", "Donor doping (n side)", "N_D", "cm⁻³", 1e13, 1e20, 1e15, 1e16, "doping",
         names=r"donors?|donor (?:doping|concentration|density)|n[- ]?(?:side|type|region)|N_?D|N sub D"),
    Slot("bias_v", "Bias (+ forward, − reverse)", "V", "V", -100.0, 2.0, 0.05, 0.0, "bias", absent=True,
         names=r"bias(?: voltage)?|applied voltage"),
    Slot("is_a", "Saturation current", "I_s", "A", 1e-18, 1e-3, 1e-12, 1e-12, "saturation",
         names=r"(?:reverse )?saturation current|leakage current|I sub s"),
)
ELEMENTS = (
    Element("regions", "p and n regions"), Element("depletion", "Depletion region"), Element("ions", "Fixed ions"),
    Element("carriers", "Holes and electrons"), Element("currents", "Drift and diffusion"),
    Element("field", "Electric field"), Element("battery", "Bias battery"), Element("graph", "I–V curve"),
    Element("readout", "Values"),
)


class PnJunctionParams(_Model):
    na_cm3: float = Field(default=1e16, ge=1e13, le=1e20)
    nd_cm3: float = Field(default=1e16, ge=1e13, le=1e20)
    bias_v: float = Field(default=0.0, ge=-100.0, le=2.0)
    is_a: float = Field(default=1e-12, ge=1e-18, le=1e-3)
    material: Literal["si", "ge"] = "si"


class PnJunctionSim(SimBase):
    template: Literal["pn_junction"] = "pn_junction"
    params: PnJunctionParams = Field(default_factory=PnJunctionParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("na", "nd", "bias", "is", "e", "w", "note", "p", "n", "mat")


_SLOTS = {s.name: s for s in SLOTS}
_SUP = str.maketrans("0123456789-−", "⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁻")


def sci(x: float, unit: str = "") -> str:
    """1e16 -> "10¹⁶", 2.5e15 -> "2.5 × 10¹⁵", with the unit after ("10¹⁶ cm⁻³")."""
    e = math.floor(math.log10(abs(x)) + 1e-12)
    m = x / 10 ** e
    if abs(m - 10) < 5e-3:
        m, e = 1.0, e + 1
    base = f"10{str(e).translate(_SUP)}"
    text = base if abs(m - 1) < 5e-4 else f"{fmt(m)} × {base}"
    return f"{text} {unit}".strip()


def bias_text(v: float) -> str:
    if abs(v) < 1e-12:
        return "0 V (no bias)"
    return f"{fmt(abs(v))} V {'forward' if v > 0 else 'reverse'}"


def junction(na: float, nd: float, v: float, material: str) -> dict[str, float]:
    _, ni, er, _ = MATERIAL[material]
    eps = er * EPS0
    vbi = VT * math.log(na * nd / ni ** 2)
    out = {"vbi": vbi}
    if v < vbi:
        w = math.sqrt(2 * eps * (vbi - v) / Q * (na + nd) / (na * nd))  # cm
        xp, xn = w * nd / (na + nd), w * na / (na + nd)
        out.update(w_um=w * 1e4, xp_um=xp * 1e4, xn_um=xn * 1e4, emax=Q * na * xp / eps)
    return out


def current(v: float, i_s: float) -> float:
    return i_s * math.expm1(v / VT)


def solve(p: PnJunctionParams, src: dict[str, str]) -> Solution:
    said = lambda n: src.get(n, "default") in ("said", "teacher", "computed")  # noqa: E731
    shape_is = MATERIAL[p.material][3]
    j = junction(p.na_cm3, p.nd_cm3, p.bias_v, p.material)
    dop = said("na_cm3") and said("nd_cm3")
    bias_ok = known(src, _SLOTS, "bias_v")
    is_ok = said("is_a")
    labels = {
        "p": SimLabel(symbol="p"), "n": SimLabel(symbol="n"),
        "na": SimLabel(symbol="N_A", text=sci(p.na_cm3, "cm⁻³"), source=src["na_cm3"]) if said("na_cm3")  # type: ignore[arg-type]
        else SimLabel(symbol="N_A"),
        "nd": SimLabel(symbol="N_D", text=sci(p.nd_cm3, "cm⁻³"), source=src["nd_cm3"]) if said("nd_cm3")  # type: ignore[arg-type]
        else SimLabel(symbol="N_D"),
        "bias": SimLabel(symbol="V", text=bias_text(p.bias_v), source=src["bias_v"]) if said("bias_v")  # type: ignore[arg-type]
        else SimLabel(symbol="V"),
        "is": SimLabel(symbol="I_s", text=sci(p.is_a, "A"), source=src["is_a"]) if is_ok  # type: ignore[arg-type]
        else SimLabel(symbol="I_s"),
        "e": SimLabel(symbol="E"), "w": SimLabel(symbol="W"),
        "note": SimLabel(symbol=""),
        # the assumptions every printed number rests on (review: they were nowhere on the stage)
        "mat": SimLabel(symbol=f"{MATERIAL[p.material][0]}, 300 K"),
    }
    derived: list[Derived] = []
    if dop:
        derived.append(Derived(id="vbi", label="Built-in potential", symbol="V_bi", value=j["vbi"], unit="V",
                               text=f"{fmt(j['vbi'])} V"))
    if dop and bias_ok and "w_um" in j:
        w = j["w_um"] * 1e-6
        derived.append(Derived(id="w", label="Depletion width", symbol="W", value=j["w_um"], unit="µm",
                               text=si_text(w, "m")))
        derived.append(Derived(id="emax", label="Peak field", symbol="E_max", value=j["emax"], unit="V/cm",
                               text=si_text(j["emax"], "V/cm")))
        labels["w"] = SimLabel(symbol="W", text=si_text(w, "m"), source="computed")
        if j["emax"] > BREAKDOWN_V_CM:
            labels["note"] = SimLabel(symbol="field above ~3 × 10⁵ V/cm: a real junction breaks down before this")
    elif dop and bias_ok:
        labels["note"] = SimLabel(symbol="forward bias ≥ V_bi: no depletion width (the approximation fails)")
    if is_ok and bias_ok and said("bias_v"):
        i = current(p.bias_v, p.is_a)
        if i <= I_LIMIT:
            derived.append(Derived(id="i", label="Diode current", symbol="I", value=i, unit="A",
                                   text=si_text(i, "A") if abs(i) >= 1e-15 else "≈ 0 A"))
        else:  # the ideal law runs away (63 kA at 1 V): a real diode's own resistance limits it (review)
            labels["note"] = SimLabel(symbol="past ~1 A the diode's own resistance limits the current: not printed")
    # the I-V curve: up to where it reaches 100 mA, down to −1 V (or the reverse bias said)
    i_s = p.is_a if is_ok else shape_is
    v_top = VT * math.log(0.1 / i_s + 1)
    v_lo = min(-1.0, p.bias_v * 1.1)
    vs = [v_lo + (v_top - v_lo) * k / 199 for k in range(200)]
    i_max = current(v_top, i_s)
    ku, pu = si_scale(i_max)
    mark = (p.bias_v, current(p.bias_v, i_s) / ku) if said("bias_v") and p.bias_v <= v_top else None
    series = [graph("I_V", "Current–voltage", ("V", "V"), ("I", f"{pu}A"),
                    [Line(id="iv", xs=vs, ys=[current(v, i_s) / ku for v in vs], role="applied", mark=mark)],
                    is_ok, time=False)]
    if not is_ok:  # the current's unit rests on I_s
        series = [series[0].model_copy(update={"y_unit": ""})]
    # drawing: the depletion width against the unbiased one (1 = as at no bias), the split, how forward / reverse
    w0 = junction(p.na_cm3, p.nd_cm3, 0.0, p.material).get("w_um", 1.0)
    ratio = j["w_um"] / w0 if "w_um" in j else 0.08
    fwd = 0.0 if p.bias_v <= 0 else min(1.0, p.bias_v / max(j["vbi"], 1e-9))
    rev = 0.0 if p.bias_v >= 0 else min(1.0, -p.bias_v / 10.0)
    drive = {"w_ratio": ratio, "p_share": p.nd_cm3 / (p.na_cm3 + p.nd_cm3), "fwd": fwd, "rev": rev,
             "bias": 1.0 if p.bias_v > 0 else -1.0 if p.bias_v < 0 else 0.0, "still_t": 1.0,
             "dop_ratio": math.log10(p.na_cm3 / p.nd_cm3)}
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: PnJunctionParams, src: dict[str, str]) -> list[str]:
    shown = ["regions", "depletion", "ions", "carriers", "currents", "field", "graph", "readout"]
    if src.get("bias_v", "default") in ("said", "teacher"):
        shown.append("battery")
    return shown


# ---- speech: dopings in powers of ten, the bias with its direction, I_s, notices ---------------------------------
_ONES = r"one|two|three|four|five|six|seven|eight|nine"
_EXP_WORD = (rf"(?:\d+|(?:twenty|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|"
             rf"{_ONES})(?:[- ](?:{_ONES})\b)?)")
_SCI = re.compile(
    rf"(?:(?P<m>\d+(?:\.\d+)?|{_ONES})\s*(?:x|×|\*|times|into)\s*)?(?:10|ten)\s*(?:\^|\*\*|to the power(?: of)?|raised to"
    rf"(?: the power)?(?: of)?|to the|e)\s*(?P<neg>minus\s+|negative\s+|-|−)?(?P<e>{_EXP_WORD})"
    r"|(?P<m2>\d+(?:\.\d+)?)[eE](?P<e2>[-+]?\d+)", re.IGNORECASE)
_PER_CM3 = re.compile(r"^\s*(?:per\s+(?:cubic\s+)?(?:centimet(?:re|er)s?|cm)(?:\s+cubed?|\s+cube)?|/\s?cm\s?3|/\s?cc|"
                      r"cm\s?\^?\s?-\s?3|cm⁻³|per\s+cc)", re.IGNORECASE)
_PER_M3 = re.compile(r"^\s*(?:per\s+(?:cubic\s+)?met(?:re|er)s?(?:\s+cubed?)?|/\s?m\s?3|m\s?\^?\s?-\s?3|m⁻³)",
                     re.IGNORECASE)
_AMPS = re.compile(r"^\s*(?:amperes?|amps?|A\b)", re.IGNORECASE)
_P_SIDE = re.compile(r"(?i:acceptor|\bp[- ]?(?:side|type|region|doping)|N sub A)|\bN_?A\b|\bp\b")  # symbols: case
_N_SIDE = re.compile(r"(?i:donor|\bn[- ]?(?:side|type|region|doping)|N sub D)|\bN_?D\b|\bn\b")
_BOTH = re.compile(r"\bboth\b|\beach side\b|\bequally\b|\bsymmetric\w*\b|\bthe same\b", re.IGNORECASE)
_FWD = re.compile(r"\bforward\b", re.IGNORECASE)
_REV = re.compile(r"\breverse\b(?!\s+saturation)", re.IGNORECASE)
_NO_BIAS = re.compile(r"\b(?:unbiased|no bias|zero bias|without (?:any )?bias|no (?:external |applied )?voltage|"
                      r"(?:in|at|under|thermal) equilibrium)\b", re.IGNORECASE)
_NI = re.compile(r"\bn\s?_?i\b|\bn sub i\b|\bintrinsic\b", re.IGNORECASE)
_JUNCTION_V = re.compile(r"\bbuilt[- ]in\b|\bbarrier\b|\bknee\b|\bcut[- ]?in\b|\bthreshold\b|\bdrops?\b|"
                         r"\bcontact (?:potential|voltage)\b|\bV\s?_?bi\b|\bV sub bi\b|\bdiffusion potential\b",
                         re.IGNORECASE)
_SAT = re.compile(r"(?i:saturation|leakage|I sub s|I naught)|\bI_s\b|\bI_?0\b")  # never the word "is"
_GE = re.compile(r"\bgermanium\b|\bGe\b(?= diode| junction| crystal)", re.IGNORECASE)
_SI = re.compile(r"\bsilicon\b", re.IGNORECASE)
_NOT_DRAWN = (
    (re.compile(r"\bzener\b", re.I), "A Zener diode is not drawn: the simulation is a plain p-n junction"),
    (re.compile(r"\b(?:avalanche|reverse breakdown|breakdown voltage|breaks down)\b", re.I),
     "Breakdown is not modelled: the simulation stops short of it"),
    (re.compile(r"\b(?:light emitting diodes?|LEDs?|photo ?diodes?|solar cells?)\b", re.I),
     "Light (LEDs, photodiodes, solar cells) is not drawn: the simulation is a plain p-n junction"),
    (re.compile(r"\b(?:transistors?|bjt|mosfet|npn|pnp)\b", re.I), "Transistors are not drawn"),
)


def _exponent(s: str) -> Optional[float]:
    s = s.strip().replace("−", "-")
    try:
        return float(s)
    except ValueError:
        return spoken_number(s)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    """Dopings ("10^16 per cubic centimetre", "ten to the power sixteen", "2 x 10^15 cm^-3") tied to their side; the
    bias with its direction ("a forward bias of 0.6 V", "5 V reverse"); I_s; the material; notices."""
    state = state or {}
    out: list[tuple[str, Any, str, int]] = []
    taken: list[tuple[int, int]] = []
    for m in _SCI.finditer(line):
        if m.group("e2") is not None:
            mant, e = float(m.group("m2")), _exponent(m.group("e2"))
        else:
            mant, e = _exponent(m.group("m") or "1"), _exponent(m.group("e"))  # "two times ten to the ..."
            if e is not None and m.group("neg"):
                e = -e
        if mant is None or e is None or e != int(e):
            continue
        value = mant * 10 ** e
        rest = line[m.end():]
        before = line[max(0, m.start() - 50):m.start()]
        if _AMPS.match(rest) or (value < 1e-2 and _SAT.search(before)):
            out.append(("is_a", value, m.group(0), m.start()))
        elif _PER_CM3.match(rest) or _PER_M3.match(rest) or value >= 1e10:
            if _PER_M3.match(rest):
                value /= 1e6
            if _NI.search(before[-30:]):  # "n i is 1.5 x 10^10": the intrinsic concentration, a constant here
                out.append(("!", f"n_i is fixed in the simulation ({sci(MATERIAL[state.get('material', 'si')][1], 'cm⁻³')}"
                                 " at 300 K)", m.group(0), m.start()))
                taken.append(m.span())
                continue
            sides = []
            if _BOTH.search(before + rest[:40]):
                sides = ["na_cm3", "nd_cm3"]
            else:
                hits = [(mm.end(), "na_cm3") for mm in _P_SIDE.finditer(before)] + \
                       [(mm.end(), "nd_cm3") for mm in _N_SIDE.finditer(before)]
                after = [(mm.start(), "na_cm3") for mm in _P_SIDE.finditer(rest[:40])] + \
                        [(mm.start(), "nd_cm3") for mm in _N_SIDE.finditer(rest[:40])]
                done = {o[0] for o in out}
                if hits and (max(hits)[1] not in done or not after):
                    sides = [max(hits)[1]]
                elif after:  # "the p side at 10^16 and 10^17 on the n side": the second is the side named after it
                    sides = [min(after)[1]]
            if not sides:
                out.append(("!", f"Heard “{m.group(0)}” - say which side it dopes (p side / n side)", m.group(0),
                            m.start()))
            for sl in sides:
                if sl in {o[0] for o in out}:  # never dropped without a word
                    out.append(("!", f"Heard “{m.group(0)}” - a second doping for the same side, not used", m.group(0),
                                m.start()))
                else:
                    out.append((sl, value, m.group(0), m.start()))
        else:
            continue
        taken.append(m.span())
    # the bias: a voltage with forward / reverse in its clause, else the direction said before (state)
    for h in items:
        if h.kind != "voltage" or h.start < 0 or any(a <= h.start < b for a, b in taken):
            continue
        a = max(line.rfind(",", 0, h.start), line.rfind(";", 0, h.start), line.rfind(". ", 0, h.start))
        b = min([x for x in (line.find(",", h.start), line.find(";", h.start), line.find(". ", h.start)) if x >= 0],
                default=len(line))
        clause = line[a + 1:b]
        if _JUNCTION_V.search(clause):
            out.append(("~", None, h.said, h.start))  # a result of the junction, not the bias
            continue
        if re.search(r"\bby\s*$", line[:h.start], re.I) and not (_REV.search(clause) or _FWD.search(clause)):
            continue  # "reduce the bias by 2 V": a change, the relative reading's (values._steps)
        neg = re.search(r"(?:\bminus|\bnegative|−|-)\s*$", line[:h.start], re.I)
        if neg:  # "apply minus 5 V": a reverse bias (reported at the minus so it is not refused as a negative)
            out += [("bias_v", -abs(h.value), h.said, neg.start()), ("~", None, h.said, h.start)]
            continue
        if _REV.search(clause):
            out.append(("bias_v", -abs(h.value), h.said, h.start))
        elif _FWD.search(clause):
            out.append(("bias_v", abs(h.value), h.said, h.start))
        elif state.get("bias_v", 0) and state.get("_src", {}).get("bias_v") in ("said", "teacher"):
            out.append(("bias_v", math.copysign(abs(h.value), state["bias_v"]), h.said, h.start))
        else:
            if not any(rx.search(line) for rx, _ in _NOT_DRAWN):  # "a Zener breaks down at 5 V": that notice only
                out.append(("!", f"Heard “{h.said}” - say forward or reverse bias", h.said, h.start))
            out.append(("~", None, h.said, h.start))
    m = _NO_BIAS.search(line)
    if m and not any(o[0] == "bias_v" for o in out):
        out.append(("bias_v", 0.0, m.group(0), m.start()))
    # a current with saturation / leakage before it is I_s; any other current is a result (the diode's), not read
    for h in items:
        if h.kind == "current" and h.start >= 0 and not any(a <= h.start < b for a, b in taken):
            if _SAT.search(line[max(0, h.start - 50):h.start]):
                out.append(("is_a", h.value, h.said, h.start))
            else:
                out.append(("~", None, h.said, h.start))
    for h in items:  # V_bi and W are worked out at 300 K only
        if h.kind == "temperature" and h.start >= 0 and abs(h.value - T_K) > 1.0:
            out += [("!", f"Heard “{h.said}” - the simulation is at 300 K only", h.said, h.start),
                    ("~", None, h.said, h.start)]
    m = _GE.search(line)
    if m:
        out.append(("material", "ge", m.group(0), m.start()))
    elif _SI.search(line):
        out.append(("material", "si", "silicon", _SI.search(line).start()))  # type: ignore[union-attr]
    for rx, msg in _NOT_DRAWN:
        mm = rx.search(line)
        if mm:
            out.append(("!", msg, mm.group(0), mm.start()))
    return out


TEMPLATE = Template(
    id="pn_junction", name="p-n junction", subject="electronics",
    sim=PnJunctionSim, params=PnJunctionParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\bp\s?-?\s?n\s?-?\s?junctions?\b|\bjunction diodes?\b|\bsemiconductor diodes?\b"
                     r"|\b(?:a|the) (?:silicon |germanium |rectifier )?diode\b(?! (?:laser|lamp))"
                     r"|\bdiode\b[^.;]{0,30}\b(?:characteristics?|I-V|V-I|I V|V I) (?:curve|characteristics?|graph)\b"
                     r"|\b(?:I-V|V-I) characteristics? of (?:a |the )?diode\b"
                     r"|\bdepletion (?:region|layer|zone|width)\b"
                     r"|\b(?:forward|reverse)[- ]bias\w*\b[^.;]{0,60}\b(?:diode|junction)s?\b"
                     r"|\b(?:diode|junction)s?\b[^.;]{0,60}\b(?:forward|reverse)[- ]bias\w*", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:junction|diode|depletion|bias\w*|forward|reverse|holes?|electrons?|carriers?|"
                       r"diffusion|drift|doping|doped|donors?|acceptors?|p[- ]type|n[- ]type|barrier|semiconductor|"
                       r"silicon|germanium|saturation|current|voltage|ions?)\b", re.IGNORECASE),
    guard=re.compile(r"\b(?:road|railway|rail|traffic|street|river|highway) junctions?\b|\bT[- ]junctions?\b|"
                     r"\bjunction (?:box|boxes|point|station|rule|law|of (?:the )?(?:two|three) (?:roads|rivers|streets))\b|"
                     r"\bgap junctions?\b|\bneuromuscular junctions?\b|\btight junctions?\b|\bkirchhoff\w*\b|"
                     r"\bclapham\b|\bozone\b|\bdepletion of (?:the )?(?:ozone|resources?|groundwater|soil|stock)\b|"
                     r"\b(?:aquifers?|groundwater|reservoirs?|soil|stocks?)\b",
                     re.IGNORECASE),
    aliases=("pn junction", "p-n junction", "diode", "depletion", "semiconductor", "bias", "electronics"),
    parse=parse, listens=r"\b(?:forward|reverse|unbiased|no bias|zero bias|germanium|silicon|zener|breakdown|LED)\b",
)
