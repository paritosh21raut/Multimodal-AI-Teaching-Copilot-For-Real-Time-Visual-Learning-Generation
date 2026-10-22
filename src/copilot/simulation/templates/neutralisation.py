"""Acid-base neutralisation (F-014 S3). Renderer: web/sims/neutralisation.js.

A flask of acid, base added from a burette: H+ + OH- -> H2O, the spectator ions (the salt's) stay in the solution.
Steps: the acid's H+ ions, the base's OH- ions added, water formed, the salt left.

pH, computed in Python only (user 2026-10-19), for the strong acids HCl, HNO3, HBr, HI, HClO4 and the strong bases
NaOH, KOH, LiOH, Ca(OH)2, Ba(OH)2 at 25 °C (Kw = 1e-14), from the amounts said:
    n(H+) = c_a V_a,  n(OH-) = k c_b V_b  (k = 2 for Ca(OH)2 and Ba(OH)2),  c = (n(H+) - n(OH-)) / (V_a + V_b)
    c > 0: [H+] = (c + √(c² + 4 Kw)) / 2;  c < 0: [OH-] = (-c + √(c² + 4 Kw)) / 2, [H+] = Kw / [OH-];  pH = -log10[H+]
    25 mL of 0.1 M HCl + 10 mL of 0.1 M NaOH: c = 1.5 mmol / 35 mL = 0.04286 M, pH = 1.37; + 25 mL: pH 7.00;
    + 30 mL: [OH-] = 0.5 / 55 = 0.009091 M, pH = 11.96
Equivalence volume V_eq = c_a V_a / (k c_b). Not printed: the pH of H2SO4 (its second proton is not fully strong at
these concentrations; drawn, salt named) and of any weak acid or base ("acetic acid", "ammonia": a notice). The pH-
volume graph only with the acid's concentration and volume and the base's concentration said (user 2026-10-19).
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional, Literal

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, Line, Part, SimBase, SimLabel, Slot, Solution, StepDef, Template, _Model, fmt, graph, known,
)

KW = 1e-14
# id: (spoken words, formula, H+ per formula unit, anion name, anion formula, anion charge)
ACIDS = {
    "hcl": (r"hydrochloric acid|\bH\s?C\s?L\b", "HCl", 1, "chloride", "Cl", 1),
    "hno3": (r"nitric acid|\bHNO3\b|\bHNO₃\b", "HNO₃", 1, "nitrate", "NO₃", 1),
    "hbr": (r"hydrobromic acid|\bHBr\b", "HBr", 1, "bromide", "Br", 1),
    "hi": (r"hydroiodic acid|hydrogen iodide|\bHI\b(?= acid)", "HI", 1, "iodide", "I", 1),
    "hclo4": (r"perchloric acid|\bHClO4\b", "HClO₄", 1, "perchlorate", "ClO₄", 1),
    "h2so4": (r"sul(?:ph|f)uric acid|\bH2SO4\b|\bH₂SO₄\b", "H₂SO₄", 2, "sulfate", "SO₄", 2),
}
WEAK_ACID = r"acetic acid|ethanoic acid|vinegar|citric acid|carbonic acid|formic acid|oxalic acid|lactic acid|weak acids?"
BASES = {  # id: (words, formula, OH- per formula unit, cation name, cation formula, cation charge)
    "naoh": (r"sodium hydroxide|caustic soda|\bN\s?a\s?O\s?H\b", "NaOH", 1, "sodium", "Na", 1),
    "koh": (r"potassium hydroxide|caustic potash|\bK\s?O\s?H\b", "KOH", 1, "potassium", "K", 1),
    "lioh": (r"lithium hydroxide|\bLiOH\b", "LiOH", 1, "lithium", "Li", 1),
    "caoh2": (r"calcium hydroxide|lime ?water|slaked lime|\bCa\(OH\)2\b", "Ca(OH)₂", 2, "calcium", "Ca", 2),
    "baoh2": (r"barium hydroxide|\bBa\(OH\)2\b", "Ba(OH)₂", 2, "barium", "Ba", 2),
}
WEAK_BASE = r"ammonia|ammonium hydroxide|\bNH4OH\b|weak bases?"
SUB = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")

SLOTS = (
    Slot("acid_m", "Acid concentration", "c(acid)", "M", 0.0001, 10.0, 0.01, 0.1, "concentration",
         names=r"(?:concentration|molarity) of (?:the )?acid|acid(?:'s)? (?:concentration|molarity)"),
    Slot("acid_ml", "Acid volume", "V(acid)", "mL", 0.1, 1000.0, 1.0, 25.0, "volume",
         names=r"volume of (?:the )?acid|acid volume"),
    Slot("base_m", "Base concentration", "c(base)", "M", 0.0001, 10.0, 0.01, 0.1, "concentration",
         names=r"(?:concentration|molarity) of (?:the )?(?:base|alkali)|(?:base|alkali)(?:'s)? (?:concentration|molarity)"),
    Slot("base_ml", "Base added", "V(base)", "mL", 0.0, 1000.0, 1.0, 0.0, "volume", absent=True,
         names=r"volume of (?:the )?(?:base|alkali)|(?:base|alkali) (?:volume|added)"),
)
STEPS = (
    StepDef("acid", "The acid gives H⁺ ions",
            r"\bacids? (?:gives?|releases?|provides?|produces?|has|have|contains?|forms?|dissociates?)\b",
            # the ions alone ("H+ and OH- combine to form water"): only when no step is said by its verb
            weak=r"\b(?:H|hydrogen)\s?(?:\+|plus|positive)?\s?ions?\b|\bH\s?(?:\+|plus)(?=\s|$|[,.])"),
    StepDef("base", "The base adds OH⁻ ions",
            r"\b(?:bases?|alkali) (?:gives?|releases?|provides?|produces?|forms?)\b"
            r"|\badd(?:s|ed|ing)? (?:the |some |more )?(?:base|alkali)\b",
            weak=r"\b(?:OH|hydroxide)\s?(?:-|minus|negative)?\s?ions?\b|\bOH\s?(?:-|minus|negative)(?=\s|$|[,.])"),
    StepDef("water", "H⁺ + OH⁻ → H₂O",
            r"\b(?:combine|combines|react|reacts|join|joins)\b[^.;]{0,30}\b(?:to )?(?:form|forms|make|makes|give|gives|"
            r"produce|produces)? ?water\b|\b(?:forms?|makes?|gives?|produces?) (?:H2O|water)\b"
            r"|\b(?:gives?|forms?|produces?)\b[^.;]{0,30}\bH2O\b"),  # not a bare "water is H2O" (review)
    StepDef("salt", "The salt stays in the solution",
            r"\bsalt (?:is formed|remains|is left|stays|is produced)\b|\bspectator ions?\b"
            r"|\b(?:forms?|gives?|produces?|makes?) (?:a )?salt\b|\bsalt (?:and|plus) water\b"),
)
PARTS = (
    Part("h", "H⁺", r"\b(?:H|hydrogen)\s?(?:\+|plus|positive)?\s?ions?\b|\bH\s?(?:\+|plus)(?=\s|$|[,.])"),
    Part("oh", "OH⁻", r"\b(?:OH|hydroxide)\s?(?:-|minus|negative)?\s?ions?\b|\bOH\s?(?:-|minus|negative)(?=\s|$|[,.])"),
    Part("water", "H₂O", r"\bwater\b|\bH2O\b"),
    Part("salt", "Salt", r"\bsalt\b"),
    Part("indicator", "Indicator", r"\bindicator\b|\bphenolphthalein\b|\blitmus\b|\bmethyl orange\b"),
)
ELEMENTS = (
    Element("flask", "Flask"), Element("burette", "Burette"), Element("ions", "Ions"), Element("graph", "pH graph"),
    Element("readout", "Values"),
)


class NeutralisationParams(_Model):
    acid: Literal["hcl", "hno3", "hbr", "hi", "hclo4", "h2so4", "weak", "unknown"] = "unknown"
    base: Literal["naoh", "koh", "lioh", "caoh2", "baoh2", "weak", "unknown"] = "unknown"
    acid_m: float = Field(default=0.1, ge=0.0001, le=10.0)
    acid_ml: float = Field(default=25.0, ge=0.1, le=1000.0)
    base_m: float = Field(default=0.1, ge=0.0001, le=10.0)
    base_ml: float = Field(default=0.0, ge=0.0, le=1000.0)


class NeutralisationSim(SimBase):
    template: Literal["neutralisation"] = "neutralisation"
    params: NeutralisationParams = Field(default_factory=NeutralisationParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("acid", "base", "salt", "ph", "h", "oh", "water", "indicator")


_SLOTS = {s.name: s for s in SLOTS}


def ph(acid: str, base: str, ca: float, va_ml: float, cb: float, vb_ml: float) -> float:
    """pH of a strong acid + strong base mixture at 25 °C (both ids known, not H2SO4)."""
    k = BASES[base][2]
    n_h, n_oh = ca * va_ml / 1000, k * cb * vb_ml / 1000
    v = (va_ml + vb_ml) / 1000
    c = (n_h - n_oh) / v
    if c >= 0:
        h = (c + math.sqrt(c * c + 4 * KW)) / 2
    else:
        h = KW / ((-c + math.sqrt(c * c + 4 * KW)) / 2)
    return -math.log10(h)


def salt(acid: str, base: str) -> tuple[str, str]:
    """The salt's name and formula ("sodium chloride", "NaCl"; "calcium sulfate", "CaSO₄"; "sodium sulfate", "Na₂SO₄")."""
    _, _, _, an, af, aq = ACIDS[acid]
    _, _, _, cn, cf, cq = BASES[base]
    g = math.gcd(aq, cq)
    nc, na = aq // g, cq // g
    poly = len(re.findall(r"[A-Z]", af)) > 1
    anion = (f"({af}){str(na).translate(SUB)}" if poly else f"{af}{str(na).translate(SUB)}") if na > 1 else af
    return f"{cn} {an}", f"{cf}{str(nc).translate(SUB) if nc > 1 else ''}{anion}"


def _src_ok(src: dict[str, str], *names: str) -> bool:
    return all(src.get(n) in ("said", "teacher", "computed") for n in names)


def solve(p: NeutralisationParams, src: dict[str, str]) -> Solution:
    acid_ok = p.acid in ACIDS and _src_ok(src, "acid")
    base_ok = p.base in BASES and _src_ok(src, "base")
    strong = acid_ok and p.acid != "h2so4"
    labels: dict[str, SimLabel] = {}
    derived: list[Derived] = []
    if acid_ok:
        labels["acid"] = SimLabel(symbol=ACIDS[p.acid][1], text=ACIDS[p.acid][1], source="said")
    elif p.acid == "weak" and _src_ok(src, "acid"):  # drawn, its pH not worked out
        labels["acid"] = SimLabel(symbol="weak acid", text="weak acid", source="said")
    if base_ok:
        labels["base"] = SimLabel(symbol=BASES[p.base][1], text=BASES[p.base][1], source="said")
    elif p.base == "weak" and _src_ok(src, "base"):
        labels["base"] = SimLabel(symbol="weak base", text="weak base", source="said")
    if acid_ok and base_ok:
        name, formula = salt(p.acid, p.base)
        labels["salt"] = SimLabel(symbol="Salt", text=f"{formula} ({name})", source="computed")
        derived.append(Derived(id="salt", label="Salt", symbol="Salt", value=0.0, text=f"{formula} ({name})"))
    # the amounts as moles (the picture's proportions); the picture's own when not said
    amounts = _src_ok(src, "acid_m", "acid_ml", "base_m") and known(src, _SLOTS, "base_ml")
    k_oh = BASES[p.base][2] if p.base in BASES else 1
    k_h = ACIDS[p.acid][2] if p.acid in ACIDS else 1
    n_h = k_h * p.acid_m * p.acid_ml
    frac = (k_oh * p.base_m * p.base_ml / n_h) if amounts and n_h > 0 else -1.0
    drive = {"frac": frac, "added": 1.0 if p.base_ml > 0 and _src_ok(src, "base_ml") else 0.0,
             "two_oh": 1.0 if k_oh == 2 else 0.0, "two_h": 1.0 if k_h == 2 else 0.0}
    v_eq = None
    if _src_ok(src, "acid_m", "acid_ml", "base_m") and p.acid in ACIDS and p.base in BASES:
        v_eq = n_h / (k_oh * p.base_m)
        derived.append(Derived(id="veq", label="Equivalence point", symbol="V(eq)", value=v_eq, unit="mL",
                               text=f"{fmt(v_eq)} mL of base"))
    series = []
    if strong and base_ok and _src_ok(src, "acid_m", "acid_ml", "base_m"):
        ph_now = None
        if _src_ok(src, "base_ml"):  # a volume of base said (0 included): the pH now, marked on the curve
            ph_now = ph(p.acid, p.base, p.acid_m, p.acid_ml, p.base_m, p.base_ml)
            labels["ph"] = SimLabel(symbol="pH", text=f"{ph_now:.2f}", source="computed")  # pH: 2 decimals
            derived.append(Derived(id="ph", label="pH", symbol="pH", value=ph_now, text=labels["ph"].text))
        elif known(src, _SLOTS, "base_ml") and p.base_ml == 0:  # no volume said: the acid's own pH, no "now" mark
            v = ph(p.acid, p.base, p.acid_m, p.acid_ml, p.base_m, 0.0)
            labels["ph"] = SimLabel(symbol="pH", text=f"{v:.2f}", source="computed")
            derived.append(Derived(id="ph", label="pH of the acid", symbol="pH of the acid", value=v,
                                   text=labels["ph"].text))
        v_end = max(2 * v_eq, p.base_ml * 1.1 if _src_ok(src, "base_ml") else 0.0)
        xs = [v_end * i / 119 for i in range(120)]
        ys = [ph(p.acid, p.base, p.acid_m, p.acid_ml, p.base_m, x) for x in xs]
        mark = (p.base_ml, ph_now) if ph_now is not None else None
        series.append(graph("pH_V", "pH–volume of base", ("V", "mL"), ("pH", ""),
                            [Line(id="ph", xs=xs, ys=ys, role="acid", mark=mark)], printable=True, time=False,
                            y_floor=0.0))
    elif acid_ok and p.acid in ACIDS and p.acid != "h2so4" and _src_ok(src, "acid_m") and \
            (not _src_ok(src, "base_ml") or p.base_ml == 0):  # the acid alone: pH = -log10 c
        v = -math.log10((p.acid_m + math.sqrt(p.acid_m ** 2 + 4 * KW)) / 2)
        labels["ph"] = SimLabel(symbol="pH", text=f"{v:.2f}", source="computed")
        derived.append(Derived(id="ph", label="pH", symbol="pH", value=v, text=f"{v:.2f}"))
    return Solution(drive=drive, labels=labels, derived=derived, series=series)


def default_shown(p: NeutralisationParams, src: dict[str, str]) -> list[str]:
    return ["flask", "burette", "ions", "readout"]


_CHEM = [(k, "acid", re.compile(w, re.IGNORECASE)) for k, (w, *_) in ACIDS.items()] + \
    [("weak", "acid", re.compile(WEAK_ACID, re.IGNORECASE))] + \
    [(k, "base", re.compile(w, re.IGNORECASE)) for k, (w, *_) in BASES.items()] + \
    [("weak", "base", re.compile(WEAK_BASE, re.IGNORECASE))]
_ROLE_WORD = [("acid", re.compile(r"\bacids?\b|\bflask\b|\bpipette\b", re.IGNORECASE)),
              ("base", re.compile(r"\b(?:bases?|alkali)\b|\bburette\b", re.IGNORECASE))]


_INSTEAD = re.compile(r"\binstead of\s+(?:the\s+)?$", re.IGNORECASE)
_DILUTE = re.compile(r"\bwater\b|\bdilut\w*", re.IGNORECASE)
_MORE = re.compile(r"\b(?:more|another|extra|further)\b", re.IGNORECASE)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    """The acid and base named, and each amount tied to the chemical named nearest it ("25 mL of 0.1 M HCl ... with
    0.1 M NaOH"): (slot, value, said, pos); ("!", notice, said, pos) for a weak acid / base and H2SO4's pH; ("~", None,
    said, pos) for an amount read as nothing (the unit-first reading must not guess it: review 2026-10-19)."""
    out: list[tuple[str, Any, str, int]] = []
    found: list[tuple[int, int, str, str, str]] = []  # (start, end, role, id, said)
    for cid, role, rx in _CHEM:
        for m in rx.finditer(line):
            if not any(a <= m.start() < b for a, b, *_ in found):
                found.append((m.start(), m.end(), role, cid, m.group(0)))
    found.sort()
    chosen: set[str] = set()
    for start, _, role, cid, said in found:  # the first said per role, in line order; "instead of HCl" is not used
        if role in chosen or _INSTEAD.search(line[:start]):
            continue
        chosen.add(role)
        out.append((role, cid, said, start))
        if cid == "weak":
            out.append(("!", f"Heard “{said}” - a weak {role}: drawn, its pH is not worked out", said, start))
        if cid == "h2so4":
            out.append(("!", "Sulfuric acid: drawn, its pH is not worked out (its second H⁺ is not fully strong)",
                        said, start))
    mentions = [(a, b, role) for a, b, role, *_ in found]
    for role, rx in _ROLE_WORD:
        for m in rx.finditer(line):
            if not any(a <= m.start() < b for a, b, _ in mentions):
                mentions.append((m.start(), m.end(), role))
    roles = {r for *_, r in mentions}
    amounts = [h for h in items if h.kind in ("volume", "concentration") and h.start >= 0]
    def dist(h: Any, mn: tuple[int, int, str]) -> tuple[int, int]:
        a, b, _ = mn
        end = h.start + len(h.said)
        return (a - end, 1) if a >= end else ((h.start - b, 0) if b <= h.start else (0, 0))  # a tie: the name before

    # amounts to chemicals nearest pair first over the whole line ("acid 0.1 molar sodium hydroxide 0.2 molar")
    pairs = sorted((dist(h, mn), i, mn[2]) for i, h in enumerate(amounts) for mn in mentions)
    nearest: dict[int, str] = {}
    claimed: set[str] = set()
    for _, i, role in pairs:
        cand = f"{role}_{'m' if amounts[i].kind == 'concentration' else 'ml'}"
        if i not in nearest and cand not in claimed:
            nearest[i] = cand
            claimed.add(cand)
    taken: set[str] = set()
    for i, h in enumerate(amounts):
        end = h.start + len(h.said)
        near = line[max(0, h.start - 30):end + 30]
        slot = None
        if h.kind == "volume" and not mentions and _DILUTE.search(near):
            pass  # "10 mL of water added": a dilution, not the base
        elif h.kind == "volume" and _MORE.search(near):
            out.append(("!", f"Heard “{h.said} more” - say the total volume of base added", h.said, h.start))
        elif not mentions:  # "now 30 mL": in a titration the volume said alone is the base added
            slot = "base_ml" if h.kind == "volume" else None  # a concentration of nothing named: not read
        elif h.kind == "concentration" and re.search(r"\bboth\b", line, re.IGNORECASE) and roles == {"acid", "base"} \
                and sum(x.kind == "concentration" for x in amounts) == 1:
            for sl in ("acid_m", "base_m"):  # "the acid and the base are both 0.1 molar"
                taken.add(sl)
                out.append((sl, float(h.value), h.said, h.start))
            continue
        else:
            slot = nearest.get(i)
            if slot in taken:
                slot = None
        if slot is None:
            out.append(("~", None, h.said, h.start))
            continue
        taken.add(slot)
        out.append((slot, float(h.value), h.said, h.start))
    return out


_STEP_WORDS = "|".join(d.words for d in STEPS)
_ALL_CHEM = "|".join([w for w, *_ in ACIDS.values()] + [w for w, *_ in BASES.values()] + [WEAK_ACID, WEAK_BASE])

TEMPLATE = Template(
    id="neutralisation", name="Acid–base neutralisation", subject="chemistry",
    sim=NeutralisationSim, params=NeutralisationParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    # "neutralise" alone is antibodies, earthing, charges (review): only with an acid / base word, or "a
    # neutralisation reaction"
    setup=re.compile(r"\bneutrali[sz]ation reactions?\b|\btitration\b|\btitrate\w*"
                     r"|\b(?:acid\w*|bases?|basic|alkal\w*|antacids?|pH|salt)\b[^.;]{0,60}\bneutrali[sz](?:e|es|ed|ing|ation)\b"
                     r"|\bneutrali[sz](?:e|es|ed|ing|ation)\b[^.;]{0,60}\b(?:acid\w*|bases?|basic|alkal\w*|pH|salt)\b"
                     r"|\bacid (?:reacts? with|and|plus) (?:a |an )?(?:base|alkali)\b|\bacid[- ]base reaction\b",
                     re.IGNORECASE),
    lexicon=re.compile(rf"{_STEP_WORDS}|\b(?:acids?|bases?|alkali|salt|water|pH|neutral\w*|titrat\w*|burette|"
                       rf"pipette|flask|indicator|ions?|molar|mol)\b|{_ALL_CHEM}", re.IGNORECASE),
    # the traps (user 2026-10-19): "the acid test", "base case", a database, ACID transactions, DNA base pairs, the base
    # of a triangle / an exponent, a military base, a neutral wire
    guard=re.compile(r"\bacid test\b|\bbase cases?\b|\bdatabases?\b|\bACID (?:properties|transactions?|compliant)\b|"
                     r"\bbase pairs?\b|\bbase of (?:a |the )?(?:triangle|prism|pyramid|cone|cylinder|logarithm|log|"
                     r"exponent|power)\b|\bnumber base\b|\bbase (?:2|ten|10|two|sixteen)\b|\bmilitary base\b|"
                     r"\bcustomer base\b|\bcode ?base\b|\bfan base\b|\bacid rain\b|\bamino acids?\b|\bnucleic acids?\b|"
                     r"\bfatty acids?\b|\bneutral (?:wire|conductor|line)\b|\bnet neutrality\b", re.IGNORECASE),
    aliases=("acid", "base", "neutralisation", "neutralization", "titration", "pH", "salt"),
    steps=STEPS, parts=PARTS, parse=parse, listens=_ALL_CHEM,
)
