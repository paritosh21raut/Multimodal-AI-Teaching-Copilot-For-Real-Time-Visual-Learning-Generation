"""Quantities said about the open diagram (F-019 §2, 0 tokens): "the mass of the box is 5 kg", "we push it up the slope
with 5 newtons", "the coefficient of friction between the blocks is 0.4", "the spring constant is 100 newtons per
metre", "now make it 45 degrees" -> `qty` ops attached to the scene's parts.

    values     read by `copilot.simulation.values.heard` (spoken numbers, "5kg", "fifty newtons") plus the friction
               coefficients (static / kinetic, "frictionless" / "smooth" = 0) and spring constants it does not read;
               converted to SI here (500 g -> 0.5 kg); the validator converts the quote again and compares
    attachment the noun said with the value ("of the box", "on the bottom block", "the hanging mass", "one block … the
               other", "it"); no noun and one candidate -> that one; else unattached (logged, never guessed)
    direction  a force's way from its words: up / down the slope, to the left / right, upward / downward; a push on
               the floor with no way said goes right (drawn, flagged unsaid); on an incline it stays unsaid
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Optional

from copilot.diagram.graph import Graph
from copilot.simulation.values import NUM as _NUM, heard, spoken_number

NUM = _NUM.replace("(?P<num>", "(?:")  # a bare number (each pattern names its own groups)

BODIES = ("block", "mass")
GROUNDS = ("floor", "incline")
_FRICTIONLESS = re.compile(r"\b(?:frictionless|smooth|(?:no|zero|without)\s+friction)\b", re.IGNORECASE)  # M3: "no friction"
_HEDGE = re.compile(r"\b(?:not|cannot|can't|don't|doesn't|isn't|aren't|never|assume\w*|if|unless|but|rough|top)\b",
                    re.IGNORECASE)
_NOT = re.compile(r"\b(?:not|never|isn't|aren't|no\s+longer)\s+(?:a\s+|an\s+|very\s+|so\s+)?$", re.IGNORECASE)
# after a μ's number: more of a spoken number ("one hundred", "2 point 5") or a unit ("5 N" is a force, not a μ)
_NOT_MU_END = re.compile(r"\s*(?:point\b|hundred|thousand|and\s+(?:a\s+)?(?:half|\w+ty|one|two|three|four|five|six|"
                         r"seven|eight|nine)\b|(?:-|\s)?(?:one|two|three|four|five|six|seven|eight|nine)\b|\d|newton|"
                         r"N\b|kg|kilo|grams?\b|g\b|degree|°|met(?:re|er)|m\b|percent|%)", re.IGNORECASE)
_MU = re.compile(rf"\b(?:(?P<kind>static|kinetic|sliding|limiting)\s+)?(?:coefficient\s+of\s+)?(?:(?:static|kinetic|"
                 rf"sliding|limiting)\s+)?friction(?:al)?\s*(?:coefficient\s*)?(?:(?:[\w']+\s+){{0,8}}?(?:is|of|=|"
                 rf"equals|as|be|to)\s+)?(?P<num>{NUM})(?!\s*(?:kg|kilo|newton|N\b|degree|°|metre|meter|m\b))|\b(?:mu|μ)(?:\s*(?P<k2>static|kinetic|sliding|s|k)\b)?"
                 rf"\s*(?:is|=|of|equals|equal\s+to|as|be|to)?\s*(?P<num2>{NUM})", re.IGNORECASE)  # M3: "mu static is 0.5"
_K = re.compile(rf"(?P<num>{NUM})\s*(?P<u>(?:kilo\s?)?newtons?\s+per\s+(?:centi)?met(?:re|er)s?|k?N\s*/\s*c?m)\b",
                re.IGNORECASE)
# test40: Whisper writes "100 newtons per metre" as "100Nm"; after "spring constant" that unit can only be N/m
_KSAID = re.compile(rf"\b(?:spring\s+constant|force\s+constant|stiffness)\s+(?:(?:[\w']+\s+){{0,4}}?(?:is|of|=|equals|"
                    rf"be|to)\s+)?(?P<num>{NUM})\s*(?P<u>(?:kilo\s?)?newtons?\s+per\s+(?:centi)?met(?:re|er)s?|"
                    rf"k?N\s*/\s*c?m\b|N\s*m\b|Nm\b)", re.IGNORECASE)
_FORCE = re.compile(rf"(?P<num>{NUM})\s*(?:newtons?\b|N\b)(?!\s*(?:per|/))", re.IGNORECASE)
_ACT = re.compile(r"\b(?:push\w*|pull\w*|appl\w*|exert\w*|drag\w*|forc(?:e|ing)\s+of)\b", re.IGNORECASE)
_WEIGHT = re.compile(r"\bweighs?\b|\bweight\b", re.IGNORECASE)
_DIR = (("up_slope", re.compile(r"\bup\s+(?:the\s+|along\s+the\s+)?(?:slope|incline|inclined\s+plane|plane|ramp)\b|"
                                r"\bupwards?\s+along\b|\bup\s+the\s+hill\b", re.I)),
        ("down_slope", re.compile(r"\bdown\s+(?:the\s+|along\s+the\s+)?(?:slope|incline|inclined\s+plane|plane|ramp)\b|"
                                  r"\bdownwards?\s+along\b", re.I)),
        ("left", re.compile(r"\b(?:to(?:wards)?\s+the\s+left|leftwards?|left\s*-?\s*wards?)\b", re.I)),
        ("right", re.compile(r"\b(?:to(?:wards)?\s+the\s+right|rightwards?)\b", re.I)),
        ("up", re.compile(r"\b(?:upwards?|vertically\s+up(?:wards?)?|straight\s+up)\b", re.I)),
        ("down", re.compile(r"\b(?:downwards?|vertically\s+down(?:wards?)?|straight\s+down)\b", re.I)))
_CLAUSE = re.compile(r"[,.;]|\band\b|\bwhile\b|\bbut\b", re.IGNORECASE)


# ---- values and units (shared with the validator) ------------------------------------------------------------------
def si_values(q: str, sym: str) -> list[float]:
    """Every SI value the quote states for the symbol (the validator compares the op's v with these)."""
    if sym in ("mu", "mu_s", "mu_k"):
        out = [0.0] if _FRICTIONLESS.search(q) else []
        for m in _MU.finditer(q):
            v = spoken_number(m.group("num") or m.group("num2"))
            if v is not None:
                out.append(v)
        if not out and re.fullmatch(rf"\s*{NUM}\s*", q, re.IGNORECASE):
            v = spoken_number(q.strip())
            out += [v] if v is not None else []
        return out
    if sym == "k":
        out = []
        for m in [*_KSAID.finditer(q), *_K.finditer(q)]:
            v = spoken_number(m.group("num"))
            if v is None:
                continue
            u = m.group("u").lower().replace(" ", "")
            f = (1000.0 if u.startswith("k") else 1.0) * (100.0 if "centi" in u or u.endswith("/cm") else 1.0)
            out.append(v * f)
        return out
    kind = {"m": "mass", "F": "force", "theta": "angle"}.get(sym)
    return [h.value for h in heard(q) if h.kind == kind] if kind else []


def said_ok(q: str, sym: str, v: float) -> bool:
    return any(math.isclose(x, v, rel_tol=1e-9, abs_tol=1e-12) for x in si_values(q, sym))


# ---- attachment -----------------------------------------------------------------------------------------------------
@dataclass
class Said:
    sym: str
    v: float
    q: str
    start: int
    end: int
    dir: str = ""
    note: str = ""


def found(text: str) -> list[Said]:
    """The quantities of the line, in the order said."""
    out: list[Said] = []
    taken: list[tuple[int, int]] = []

    def put(s: Said) -> None:
        if not any(s.start < b and a < s.end for a, b in taken):
            taken.append((s.start, s.end))
            out.append(s)

    for m in [*_KSAID.finditer(text), *_K.finditer(text)]:
        v = si_values(m.group(0), "k")
        if v:
            put(Said("k", v[0], m.group(0).strip(), m.start(), m.end()))
    for m in _MU.finditer(text):
        v = si_values(m.group(0), "mu")
        if not v or _NOT_MU_END.match(text, m.end()):
            continue  # "friction is one hundred newtons": a force (or a cut number), never μ = 1
        k = (m.group("kind") or m.group("k2") or "").lower()
        if not k:
            k = next((w.lower() for w in re.findall(r"\b(static|kinetic|sliding|limiting)\b", m.group(0), re.I)), "")
        sym = "mu_s" if k in ("static", "limiting", "s") else "mu_k" if k in ("kinetic", "sliding", "k") else "mu"
        put(Said(sym, v[-1], m.group(0).strip(), m.start(), m.end()))
    for m in _FRICTIONLESS.finditer(text):
        if " " in m.group(0) and _HEDGE.search(clause(text, m.start(), m.end())):
            continue  # review: "we cannot assume zero friction", "no friction on its top but the floor is rough"
        if not _NOT.search(text[max(0, m.start() - 20):m.start()]):  # "the floor is not smooth": no μ = 0
            put(Said("mu", 0.0, m.group(0), m.start(), m.end()))
    for h in heard(text):
        sym = {"mass": "m", "force": "F", "angle": "theta"}.get(h.kind)
        if not sym or h.start < 0:
            continue
        i = text.find(h.said, max(0, h.start - 2))
        if i < 0:
            continue
        s = Said(sym, h.value, h.said, i, i + len(h.said))
        if sym == "F":
            s.dir = direction(clause(text, s.start, s.end))
        if sym == "m" and _WEIGHT.search(text[max(0, i - 40):i]):
            s.note = "weight"
        put(s)
    for m in _FORCE.finditer(text):  # "the floor is frictionless and we push it with 10 newtons": heard() reads a
        c = clause(text, m.start(), m.end())  # force after "friction" as a stated result; a push word says input
        v = spoken_number(m.group("num"))
        if v is not None and _ACT.search(c) and not re.search(r"\bfriction", c, re.IGNORECASE):
            put(Said("F", v, m.group(0).strip(), m.start(), m.end(), dir=direction(c)))
    out.sort(key=lambda s: s.start)
    return out


def clause(t: str, start: int, end: int) -> str:
    a = 0
    for m in _CLAUSE.finditer(t, 0, start):
        a = m.end()
    m = _CLAUSE.search(t, end)
    return t[a:m.start() if m else len(t)]


def direction(text: str) -> str:
    return next((d for d, rx in _DIR if rx.search(text)), "")


def bodies(g: Graph) -> list[str]:
    return [p.id for p in g.parts.values() if p.kind in BODIES]


def under(g: Graph, b: str) -> Optional[str]:
    """What the body rests on (another body or the ground), or None."""
    r = g.rels.get(b)
    return r[1] if r and r[0] == "on" else None


def above(g: Graph, b: str) -> list[str]:
    return [a for a, (r, x) in g.rels.items() if r == "on" and x == b and g.parts[a].kind in BODIES]


def hanging(g: Graph, b: str) -> bool:
    r = g.rels.get(b)
    return bool(r and r[0] in ("hang_from", "attached_to"))


_REF = (  # a phrase that names a body: (regex, picker(g) -> ids)
    # test41: STT plurals ("the bottom blocks") name the one body there
    (re.compile(r"\b(?:top|upper)\s+(?:block|box|one|mass)(?:e?s)?\b", re.I),
     lambda g: [b for b in bodies(g) if under(g, b) in g.parts and g.parts[under(g, b)].kind in BODIES]),
    (re.compile(r"\b(?:bottom|lower)\s+(?:block|box|one|mass)(?:e?s)?\b", re.I),
     lambda g: [b for b in bodies(g) if above(g, b)]),
    (re.compile(r"\bhanging\s+(?:block|box|mass|weight|one|body)\b|\b(?:block|box|mass)\s+(?:that\s+is\s+)?hanging\b", re.I),
     lambda g: [b for b in bodies(g) if hanging(g, b)]),
    (re.compile(r"\b(?:block|box|mass)\s+on\s+the\s+(?:table|floor|ground|surface)\b", re.I),
     lambda g: [b for b in bodies(g) if under(g, b) in g.parts and g.parts[under(g, b)].kind == "floor"]),
    (re.compile(r"\b(?:block|box|mass)\s+on\s+the\s+(?:incline|inclined\s+plane|slope|ramp|plane)\b", re.I),
     lambda g: [b for b in bodies(g) if under(g, b) in g.parts and g.parts[under(g, b)].kind == "incline"]),
    (re.compile(r"\b(?:the\s+)?other\b|\bsecond\s+(?:block|box|mass|one)\b", re.I), lambda g: bodies(g)[1:2]),
    (re.compile(r"\b(?:one\s+(?:block|box|mass)|the\s+first\s+(?:block|box|mass|one)|one\s+of\s+them)\b|^\s*one\b", re.I),
     lambda g: bodies(g)[:1]),
)
_PRON = re.compile(r"\b(?:it|its)\b", re.IGNORECASE)


def _named(g: Graph, text: str) -> list[tuple[int, str]]:
    """(position, body id) for every body named in the text."""
    hits: list[tuple[int, str]] = []
    for rx, pick in _REF:
        for m in rx.finditer(text):
            ids = pick(g)
            if len(ids) == 1:
                hits.append((m.start(), ids[0]))
    spans = [h[0] for h in hits]
    for p in g.parts.values():
        if p.kind not in BODIES:
            continue
        words = {p.label.lower()} if p.label else set()
        if len([b for b in bodies(g) if g.parts[b].kind == p.kind]) == 1 and not p.label:
            words.add(p.kind)
        for w in [w for w in words if w]:
            # M3: a one-letter label ("block A") only after its noun, in capitals: "A 50 newton force" names no block
            L = re.escape(p.label)  # review: "... and B is 3 kg" (after "and" / a comma) names B too
            rx = rf"\b(?i:block|box|mass|body)\s+{L}\b|(?<=\band\s){L}\b|(?<=,\s){L}\b" if len(w) == 1 else rf"(?i:\b{re.escape(w)}s?\b)"
            for m in re.finditer(rx, text):
                if len([b for b in bodies(g) if (g.parts[b].label or "").lower() == w or g.parts[b].kind == w]) == 1 \
                        and not any(abs(m.start() - s) < 12 for s in spans):
                    hits.append((m.start(), p.id))
    return sorted(hits)


def attach(text: str, g: Graph) -> tuple[list[dict], list[tuple[str, str]]]:
    """The line's quantities as `qty` ops on g's parts (g already holds this line's parts) + the unattached ones."""
    said = found(text)
    ops: list[dict] = []
    lost: list[tuple[str, str]] = []
    names = _named(g, text)
    prons = [m.start() for m in _PRON.finditer(text)]
    for i, s in enumerate(said):
        lo = said[i - 1].end if i else 0
        hi = said[i + 1].start if i + 1 < len(said) else len(text)
        on = _target(g, s, text, lo, hi, names, prons)
        if on is None:
            lost.append((s.sym, s.q))
            continue
        old = g.qty.get((on, "F")) if s.sym == "F" and not s.dir else None
        if old and old.get("dir") and math.isclose(old["v"], s.v):
            s.dir = old["dir"]  # test40: the same push said again, its way misheard ("up with the slope"): kept
        ops.append({"op": "qty", "on": on, "sym": s.sym, "v": s.v, "u": _unit(s.sym), "q": s.q,
                    **({"dir": s.dir} if s.dir else {}), **({"note": s.note} if s.note else {})})
    return ops, lost


def _unit(sym: str) -> str:
    from copilot.diagram.ops import QSYMS
    return QSYMS[sym]


def _ground(g: Graph, b: str) -> Optional[str]:
    x, seen = b, set()
    while x in g.rels and x not in seen:
        seen.add(x)
        r, y = g.rels[x]
        if r != "on":
            return None
        if g.parts[y].kind in GROUNDS:
            return g.parts[y].kind
        x = y
    return None


def _target(g: Graph, s: Said, text: str, lo: int, hi: int, names: list[tuple[int, str]],
            prons: list[int]) -> Optional[str]:
    if s.sym == "theta":
        inc = [p.id for p in g.parts.values() if p.kind == "incline"]
        return inc[0] if len(inc) == 1 else None
    if s.sym == "k":
        sp = [p.id for p in g.parts.values() if p.kind == "spring"]
        return sp[0] if len(sp) == 1 else None
    if s.sym in ("mu", "mu_s", "mu_k"):
        return _contact(g, text, lo, hi)
    near = [(p, b) for p, b in names if lo <= p < hi]
    after = [b for p, b in near if p >= s.end]
    before = [b for p, b in near if p < s.start]
    nxt = next((p for p, b in near if p >= s.end), None)
    if s.sym == "m" and nxt is not None and re.fullmatch(r"\s*(?:(?!and\b|or\b|but\b)[a-z]+\s+)?", text[s.end:nxt]):
        return after[0]  # M3: "a 4 kg block ... to a 1 kg mass": each value on the noun right after it
    # "push the box with 5 N" (the noun before), "50 N on the bottom block" (the noun after, with on / to / of)
    if after and re.match(r"^\W*(?:\w+\s+){0,2}?(?:on|to|of|at)\b", text[s.end:hi], re.IGNORECASE):
        return after[0]
    if before:
        return before[-1]
    if any(lo <= p < hi for p in prons) and g.last in g.parts and g.parts[g.last].kind in BODIES:
        return g.last
    if after:
        return after[0]
    bs = bodies(g)
    if any(lo <= p < hi for p in prons):
        return bs[0] if len(bs) == 1 else None
    return bs[0] if len(bs) == 1 else None


def _contact(g: Graph, text: str, lo: int, hi: int) -> Optional[str]:
    """A friction coefficient belongs to a contact; it is stored on the body that rests on it."""
    win = text[max(0, lo - 0):hi]
    contacts = [b for b in bodies(g) if under(g, b) in g.parts]
    if re.search(r"\bbetween\s+the\s+(?:two\s+)?(?:blocks?|box(?:es)?|mass(?:es)?)\b|\bbetween\s+them\b", win, re.I):
        c = [b for b in contacts if g.parts[under(g, b)].kind in BODIES]
        return c[0] if len(c) == 1 else None
    m = re.search(r"\b(floor|ground|table|surface|incline|inclined plane|slope|ramp|plane)\b", win, re.I)
    if m:
        kind = "incline" if m.group(1).lower() in ("incline", "inclined plane", "slope", "ramp", "plane") else "floor"
        c = [b for b in contacts if g.parts[under(g, b)].kind == kind]
        if len(c) == 1:
            return c[0]
        if c or m.group(1).lower() != "surface":
            return None  # "the incline is frictionless" with no incline here: not the table's μ
        c = [b for b in contacts if g.parts[under(g, b)].kind in GROUNDS]
        return c[0] if len(c) == 1 else None
    names = [b for p, b in _named(g, win)]
    bt = re.search(r"\b(?i:between)\s+(?:(?i:the\s+)?(?i:block|box|mass)\s+)?(\w+)\s+and\s+(?:(?i:the\s+)?(?i:block|box|mass)\s+)?"
                   r"(\w+)", win)
    if bt:  # "between A and B": the bare labels name the two bodies
        lab = {g.parts[b].label: b for b in bodies(g) if g.parts[b].label}
        if bt.group(1) in lab and bt.group(2) in lab:
            names = [lab[bt.group(1)], lab[bt.group(2)]]
    if bt and len(set(names)) == 2:  # "between A and B": their contact, kept on
        x, y = sorted(set(names))                                       # the upper one (M3 review)
        top = x if under(g, x) == y else y if under(g, y) == x else None
        return top if top in contacts else None
    if len(set(names)) == 1 and names[0] in contacts:
        return names[0]
    return contacts[0] if len(contacts) == 1 else None
