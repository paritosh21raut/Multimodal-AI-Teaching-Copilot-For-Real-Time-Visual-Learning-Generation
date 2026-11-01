"""The diagram validator (contract §5): every op is checked against the graph before it reaches the log; a refused op
is logged with its reason (the reject log is a paper dataset).

- schema, unique ids, referenced ids exist (a port "R1.2" names its part);
- kind / rel / verb / show in the closed lists; `in` / `contain` need a container; `hang_from` an `end` anchor;
- a said count ("two circles") equals the parts of that kind the line adds (counts are drawn exactly);
- a `given` matches its quote (the number is in it, the unit fits the symbol);
- a `qty` (F-019 §2) sits on a part that can have it and its v is what Python reads from the quote, in SI;
- a label is the teacher's word (in the recent lines), an auto name (R1, R2 … counted by Python) or a table name;
- budgets (ops per line, parts per diagram).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from pydantic import ValidationError

from copilot.diagram import ops as O
from copilot.diagram import parts as P
from copilot.diagram.graph import Graph, apply
from copilot.stage.validate import _clean, quoted_numbers, said_unit

_AUTO = re.compile(r"^[A-Z]\d{1,2}$")
_UNIT_WORDS = {"deg": r"deg|degree|°", "kg": r"kg|kilo", "N/m": r"newtons? per met|N/m", "V": r"volt|\bV\b",
               "ohm": r"ohm|Ω"}


@dataclass
class Delta:
    ok: list[Any] = field(default_factory=list)
    rejected: list[tuple[Any, str]] = field(default_factory=list)


def _said(word: str, lines: list[str]) -> bool:
    w = _clean(word)
    rx = re.compile(r"(?<![\w])" + re.escape(w) + r"(?![\w])") if w else None
    return bool(rx) and any(rx.search(_clean(x)) for x in lines)


def _table_names() -> set[str]:
    names = {p["name"].lower() for p in P.table("planets")} | set(P.table("elements"))
    names |= {c["show"].lower() for c in P.table("chemicals").values()} | {c["name"] for c in P.table("chemicals").values()}
    return names | {"sun", "nucleus", "electron", "shell", "n", "s", "atom", "water"}


# the attributes a part may carry (anything else is refused: no free numbers reach the layout)
ATTR: dict[str, Any] = {
    "label_src": lambda v: v in ("said", "auto", "table"),
    "name": lambda v: P.planet(str(v)) is not None,
    "element": lambda v: P.element(str(v)) is not None,
    "chem": lambda v: P.chemical(str(v)) is not None,
    "state": lambda v: v in ("open", "closed"),
    "implied": lambda v: v is True,
}


def check_attr(op: O.Part) -> str:
    for k, v in op.attr.items():
        if k not in ATTR:
            return f"attribute {k!r} is not allowed"
        if not ATTR[k](v):
            return f"attribute {k}={v!r} is not in the tables"
    return ""


def check_label(op: O.Part, lines: list[str], g: Graph, trusted: bool, counts: dict[str, int]) -> str:
    """Said (in the recent lines), auto (R1 … up to the count of that kind) or table (only the fast path's own
    expansions: the sun, the planets by their table name)."""
    if not op.label:
        return ""
    src = op.attr.get("label_src", "said")
    if src == "auto":
        m = _AUTO.match(op.label)
        if not m or not op.label.startswith(op.kind[0].upper()):
            return f"auto label {op.label!r} is not a counted name"
        if int(op.label[1:]) > counts.get(op.kind, 0) or counts.get(op.kind, 0) < 2:
            return f"auto label {op.label!r} is beyond the {counts.get(op.kind, 0)} {op.kind}(s)"
        return ""
    if src == "table":
        if not trusted:
            return f"table label {op.label!r} only from the fast path's tables"
        ok = op.label == op.attr.get("name") if op.kind == "planet" else op.label.lower() in _table_names()
        return "" if ok else f"label {op.label!r} is not a table name"
    return "" if _said(op.label, lines) else f"label {op.label!r} is not in the teacher's recent lines"


def check_given(op: O.Given, lines: list[str]) -> str:
    if op.sym not in O.SYMS:
        return f"no given {op.sym!r} (has {', '.join(O.SYMS)})"
    if not math.isfinite(op.v):
        return "not a finite number"
    q = _clean(op.q)
    rx = re.compile(r"(?<![\w.])" + re.escape(q) + r"(?![\w])") if q else None
    if not rx or not any(rx.search(_clean(x)) for x in lines):
        return f"quote {op.q!r} is not in the teacher's recent lines"
    hit = [e for v, e in quoted_numbers(op.q) if math.isclose(v, op.v, rel_tol=1e-9, abs_tol=1e-12)]
    if not hit:
        return f"{op.v} is not said in the quote {op.q!r}"
    want = O.SYMS[op.sym]
    if op.u and op.u != want:
        return f"{op.sym} takes {want}, not {op.u!r}"
    su = said_unit(op.q, hit[0])
    if su != want and not re.match(rf"\s*(?:{_UNIT_WORDS[want]})", op.q[hit[0]:], re.IGNORECASE):
        return f"the quote says {su or 'no unit'} after {op.v:g}, {op.sym} needs {want}"
    return ""


_QTY_ON = {"m": ("block", "mass"), "F": ("block", "mass"), "mu": ("block", "mass"), "mu_s": ("block", "mass"),
           "mu_k": ("block", "mass"), "theta": ("incline", "ball"), "k": ("spring",),
           "v": ("ball", "car", "boat", "man", "river", "rain"), "h": ("ball",), "t": ("ball", "car", "boat", "man"),
           "a": ("car", "ball", "boat", "man"), "r": ("ball", "car"), "d": ("car", "boat", "man", "river", "ball")}  # M5


def check_qty(op: O.Qty, g: Graph, lines: list[str]) -> str:
    from copilot.diagram.quantities import said_ok
    if op.sym not in O.QSYMS:
        return f"no quantity {op.sym!r} (has {', '.join(O.QSYMS)})"
    if op.on not in g.parts:
        return "unknown id"
    if g.parts[op.on].kind not in _QTY_ON[op.sym]:
        return f"{op.sym} does not go on a {g.parts[op.on].kind}"
    if op.u != O.QSYMS[op.sym]:
        return f"{op.sym} is kept in {O.QSYMS[op.sym] or 'no unit'}, not {op.u!r}"
    if op.dir not in O.DIRS or op.dir and op.sym != "F":
        return f"bad direction {op.dir!r}"
    if not math.isfinite(op.v) or op.v < 0 or op.sym.startswith("mu") and op.v > 2 \
            or op.sym in ("h", "r", "d") and op.v <= 0:  # M5 review: a zero height / radius / width moves nothing
        return f"{op.v} is not a {op.sym}"
    if op.sym == "theta" and g.parts[op.on].kind == "ball" and not 0 <= op.v <= 90:
        return f"a launch angle of {op.v:g}° is not drawn (0–90°)"
    if op.sym == "theta" and g.parts[op.on].kind == "incline" and not 3 <= op.v <= 75:  # the slope the layout can draw (layout.theta); else it would
        return f"an incline of {op.v:g}° is not drawn (3–75°)"  # show 30° while the solver used the said angle
    q = _clean(op.q)
    rx = re.compile(r"(?<![\w.])" + re.escape(q) + r"(?![\w])", re.IGNORECASE) if q else None
    if not rx or not any(rx.search(_clean(x)) for x in lines):
        return f"quote {op.q!r} is not in the teacher's recent lines"
    if not said_ok(op.q, op.sym, op.v):
        return f"{op.v:g} {op.u} is not what the quote {op.q!r} says"
    return ""


def _ref(i: str, g: Graph) -> bool:
    return i.split(".", 1)[0] in g.parts or i in g.groups


def check(op: Any, g: Graph, lines: list[str], trusted: bool = False, counts: Optional[dict[str, int]] = None) -> str:
    """'' or why the op is refused (g already holds this line's earlier accepted ops). trusted: the fast path."""
    if isinstance(op, (O.Part, O.Solution)):
        if op.id in g.parts or op.id in g.groups:
            return f"id {op.id!r} exists"
        if isinstance(op, O.Part):
            if P.kind(op.kind) is None:
                return f"unknown part kind {op.kind!r}"
            if len(g.parts) >= O.MAX_PARTS:
                return f"more than {O.MAX_PARTS} parts"
            return check_attr(op) or check_label(op, lines, g, trusted, counts or {})
        return "" if op.solute.strip() and _said(op.solute, lines) or P.chemicals().get(op.solute.lower()) \
            else f"solute {op.solute!r} is not said"
    if isinstance(op, O.Contain):
        if not (op.a in g.parts and op.b in g.parts):
            return "unknown id"
        return "" if P.kind(g.parts[op.a].kind).get("container") else f"{g.parts[op.a].kind} holds nothing"
    if isinstance(op, O.Place):
        if op.rel not in O.RELS:
            return f"unknown relation {op.rel!r}"
        if not (op.a in g.parts and op.b in g.parts):
            return "unknown id"
        if op.a == op.b:
            return "a part placed on itself"
        b = g.parts[op.b]
        if op.rel == "in" and not P.kind(b.kind).get("container"):
            return f"{b.kind} holds nothing"
        if op.rel == "inside" and not (P.kind(b.kind).get("domain") == P.kind(g.parts[op.a].kind).get("domain")
                                       == "shape"):
            return "only a shape goes inside a shape"
        if op.rel in ("hang_from", "attached_to") and "end" not in P.kind(b.kind)["anchors"]:
            return f"{b.kind} has no end to hang from"
        if op.rel == "at_edge" and not (g.parts[op.a].kind == "pulley" and b.kind == "floor"):
            return "only a pulley is clamped at the edge of a table"
        if op.rel == "orbit" and b.kind not in ("sun", "planet", "nucleus", "atom"):
            return f"nothing orbits a {b.kind}"
        x, seen = op.b, {op.a}
        while x in g.rels:  # a placement cycle (a on b on a)
            if x in seen:
                return "a placement cycle"
            seen.add(x)
            x = g.rels[x][1]
        return "" if x not in seen else "a placement cycle"
    if isinstance(op, O.Group):
        if op.id in g.parts:
            return f"id {op.id!r} exists"
        if op.id in g.groups and (g.groups[op.id][0] != op.mode or not set(g.groups[op.id][1]) <= set(op.items)):
            return f"group {op.id!r} can only grow"  # the open loop takes the new parts said later
        bad = [i for i in op.items if not _ref(i, g) or i == op.id]
        one = op.mode == "series" and len(op.items) == 1 and op.items[0] in g.groups  # a lone parallel set
        return f"unknown id(s) {bad}" if bad else ("" if len(op.items) >= 2 or one else "a group needs two items")
    if isinstance(op, O.Wire):
        return "" if _ref(op.a, g) and _ref(op.b, g) else "unknown id"
    if isinstance(op, O.Process):
        if op.verb not in O.VERBS:
            return f"unknown process {op.verb!r}"
        return "" if op.target in g.parts and (op.src is None or op.src in g.parts) else "unknown id"
    if isinstance(op, O.Given):
        if op.on is not None and op.on not in g.parts:
            return "unknown id"
        return check_given(op, lines)
    if isinstance(op, O.Qty):
        return check_qty(op, g, lines)
    if isinstance(op, O.Show):
        if op.what not in O.SHOWS:
            return f"unknown show {op.what!r}"
        return "" if op.on is None or op.on in g.parts else "unknown id"
    if isinstance(op, O.Mode):
        return ""
    return "unknown op"


def check_delta(raws: list[dict], g: Graph, lines: list[str], text: str = "", max_ops: Optional[int] = O.MAX_OPS) -> Delta:
    """One line's ops, in order, each against the graph with the line's earlier accepted ops; then the said counts.
    max_ops None: the fast path's expansions from the tables (the solar system is 17 ops)."""
    d = Delta()
    work = g.copy()
    counts: dict[str, int] = {}
    for p in g.parts.values():
        counts[p.kind] = counts.get(p.kind, 0) + 1
    for raw in raws:
        if isinstance(raw, dict) and raw.get("op") == "part":
            counts[str(raw.get("kind"))] = counts.get(str(raw.get("kind")), 0) + 1
    for i, raw in enumerate(raws):
        if max_ops is not None and i >= max_ops:
            d.rejected.append((raw, f"more than {O.MAX_OPS} ops in a line"))
            continue
        try:
            op = O.parse(raw)
        except (ValidationError, ValueError) as err:
            d.rejected.append((raw, f"schema: {str(err).splitlines()[0][:120]}"))
            continue
        why = check(op, work, lines, trusted=max_ops is None, counts=counts)
        if why:
            d.rejected.append((raw, why))
            continue
        apply(work, op, "", 0)
        d.ok.append(op)
    if text:
        _counts(d, g, text)
    return d


def _counts(d: Delta, g: Graph, text: str) -> None:
    """A said count is drawn exactly: "two circles" adds 2 circles (when none are there yet); extra ones are refused."""
    from copilot.diagram.fastpath import said_counts
    for kind, n in said_counts(text).items():
        if g.of(kind):
            continue
        mine = [op for op in d.ok if isinstance(op, O.Part) and op.kind == kind]
        gone = set()
        for op in mine[n:]:
            d.ok.remove(op)
            gone.add(op.id)
            d.rejected.append((op.model_dump(exclude_none=True), f"said {n} {kind}(s); this would be {len(mine)}"))
        for op in [o for o in d.ok if gone & {getattr(o, k, None) for k in ("a", "b", "target", "src", "on")}]:
            d.ok.remove(op)
            d.rejected.append((op.model_dump(exclude_none=True), "names a refused part"))
        for op in [o for o in d.ok if isinstance(o, O.Group) and gone & set(o.items)]:
            op.items = [i for i in op.items if i not in gone]  # a group keeps the parts that stay
            if len(op.items) < 2 and op.mode == "parallel":
                d.ok.remove(op)
                d.rejected.append((op.model_dump(exclude_none=True), "names a refused part"))
        if 0 < len(mine) < n:
            d.rejected.append(({"op": "part", "kind": kind}, f"said {n} {kind}(s), only {len(mine)} given"))
