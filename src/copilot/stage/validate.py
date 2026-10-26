"""Checks every stage op before the event log takes it (contract §6). A bad op is refused with a logged reason (the
reject log is a paper dataset), never repaired by guessing.

- schema (pydantic), id pattern, unique ids, referenced ids exist;
- verb, relation, law, recipe, view, shot, manner, state and direction come from the closed lists (stage.ops);
- a `given` quotes the teacher: the quote is in the recent lines, its number is the value (after number-word
  normalising: "ten" = 10, "from rest" = 0 for a speed), and the unit fits the symbol's dimension (pint); a unit said
  in the quote must be the op's unit;
- law preconditions (sliding_friction needs the body on the surface ...); laws not built yet are refused;
- budgets: ≤ 16 ops per delta, ≤ 12 visible entities;
- safety: an `unsafe` op or a blocklist hit drops the whole delta;
- a noun must be drawable (`w` or its `near` stand-in in the catalog).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Optional

import pint
from pydantic import ValidationError

from copilot.scene import safety
from copilot.scene.validate import Corpus, said_words
from copilot.simulation.values import NUM, spoken_number
from copilot.stage import catalog, ops
from copilot.stage.graph import Graph, apply
from copilot.stage.laws import ANGLE, LAWS, PURE

SI_UNIT = {"[length] / [time]": "m/s", "[length] / [time] ** 2": "m/s^2", "[length]": "m", "[time]": "s",
           "[mass]": "kg", "[mass] * [length] / [time] ** 2": "N", "[mass] / [length] ** 3": "kg/m^3",
           "[length] ** 3": "m^3"}
ANGLE_UNITS = {"deg": "deg", "degree": "deg", "degrees": "deg", "°": "deg", "rad": "rad", "radian": "rad",
               "radians": "rad"}
U_ALIAS = {"m/s²": "m/s^2", "m/s2": "m/s^2", "mps": "m/s", "kmph": "km/h", "kph": "km/h", "km/hr": "km/h",
           "kg/m³": "kg/m^3", "m³": "m^3", "newton": "N", "newtons": "N", "kilogram": "kg", "kilograms": "kg",
           "metre": "m", "metres": "m", "meter": "m", "meters": "m", "second": "s", "seconds": "s", "litre": "L",
           "litres": "L", "liter": "L", "liters": "L", "ms^-2": "m/s^2", "N m": "N*m"}
# unit words said right after a number -> the unit (longest first)
_SAID_UNITS = [(re.compile(r"\s*(?:" + rx + r")(?![a-z])", re.I), u) for rx, u in (
    (r"(?:metres?|meters?) per second (?:squared|per second)|m/s²|m/s\^2|m/s2|mps2|mps squared|m s\^-2", "m/s^2"),
    (r"(?:kilometres?|kilometers?) (?:per|an) hour|km/h|kmph|kph|km/hr", "km/h"),
    (r"(?:metres?|meters?) per second|m/s|mps", "m/s"),
    (r"(?:centimetres?|centimeters?) per second|cm/s", "cm/s"),
    (r"kilograms? per cubic (?:metres?|meters?)|kg/m³|kg/m\^3", "kg/m^3"),
    (r"cubic (?:metres?|meters?)|m³|m\^3", "m^3"),
    (r"(?:centimetres?|centimeters?)|cm", "cm"), (r"(?:millimetres?|millimeters?)|mm", "mm"),
    (r"(?:kilometres?|kilometers?)|km", "km"), (r"metres?|meters?|m", "m"),
    (r"degrees?|deg|°", "deg"), (r"radians?|rad", "rad"),
    (r"seconds?|secs?|s", "s"), (r"minutes?|mins?", "min"), (r"hours?|hrs?", "h"),
    (r"kilograms?|kilos?|kg", "kg"), (r"grams?|g", "g"), (r"newtons?|N", "N"),
    (r"litres?|liters?|L", "L"),
)]
_REST = re.compile(r"\b(?:from|at) rest\b|\bstationary\b|\bstands? still\b|\bstarts? from rest\b", re.I)
_NUM_RX = re.compile(NUM, re.I)
_NOUN = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,39}$")
# a negative given needs a said minus or a slowing word ("slows down at 2 m/s²", "minus 3")
_MINUS = re.compile(r"-\s*\d|\bminus\b|\bnegative\b|\bslow(?:s|ing)? down\b|\bdecelerat|\bretard|\bbrak", re.I)
RANGE = {"mu_k": (0.0, 2.0), "mu_s": (0.0, 2.0), "theta": (-90.0, 90.0), "theta0": (0.0, 90.0), "e": (0.0, 1.0)}
OPEN_LOW = ("theta0",)  # a pendulum released at 0° never swings


@lru_cache(maxsize=1)
def ureg() -> pint.UnitRegistry:
    return pint.UnitRegistry()


@dataclass
class Rejected:
    raw: Any
    reason: str


@dataclass
class Delta:
    """One line's checked ops (op, resolved facts) and the refused ones; `dropped` = the whole delta was refused."""
    ok: list[tuple[Any, dict[str, Any]]] = field(default_factory=list)
    rejected: list[Rejected] = field(default_factory=list)
    dropped: str = ""


def _clean(s: str) -> str:
    return " ".join(re.sub(r"[^\w°²³/.^ -]", " ", s.lower()).split())


def _unit(u: str) -> str:
    u = (u or "").strip()
    return U_ALIAS.get(u, U_ALIAS.get(u.lower(), u))


def quoted_numbers(q: str) -> list[tuple[float, int]]:
    """The numbers said in a quote (digits or words) with the end offset of each."""
    out = []
    for m in _NUM_RX.finditer(q):
        if m.start() > 0 and (q[m.start() - 1].isalpha() or q[m.start() - 1] in "/^"):
            continue  # an exponent ("m/s2") or a name ("C1")
        v = spoken_number(m.group("num"))
        if v is not None:
            out.append((v, m.end()))
    return out


def said_unit(q: str, end: int) -> Optional[str]:
    for rx, u in _SAID_UNITS:
        if rx.match(q, end):
            return u
    return None


def check_given(op: Any, g: Graph, lines: list[str]) -> tuple[str, dict[str, Any]]:
    """("" , {si, si_u}) or (why refused, {})."""
    law = g.laws.get(op.law)
    if law is None:
        return f"given for unknown law {op.law!r}", {}
    spec = LAWS[law.name]
    if op.sym not in spec.syms:
        return f"{law.name} has no given {op.sym!r} (has {', '.join(spec.syms)})", {}
    if not math.isfinite(op.v):
        return "not a finite number", {}
    q = _clean(op.q)
    # the quote is whole words of a line: "5 m/s" is not in "at 25 m/s"
    rx = re.compile(r"(?<![\w.])" + re.escape(q) + r"(?![\w])") if q else None
    if not rx or not any(rx.search(_clean(line)) for line in lines):
        return f"quote {op.q!r} is not in the teacher's recent lines", {}
    dim = spec.syms[op.sym]
    nums = quoted_numbers(op.q)
    hit = [(v, e) for v, e in nums if math.isclose(abs(v), abs(op.v), rel_tol=1e-9, abs_tol=1e-12)]
    if not hit and not (op.v == 0 and dim == "[length] / [time]" and _REST.search(op.q)):
        return f"{op.v} is not said in the quote {op.q!r}", {}
    if op.v < 0 and not any(v < 0 for v, _ in hit) and not _MINUS.search(op.q):
        return f"{op.sym} = {op.v}: the quote says no minus sign or slowing down", {}
    lo, hi = RANGE.get(op.sym, (-math.inf, math.inf))
    if not lo <= op.v <= hi or (op.sym in OPEN_LOW and op.v <= lo):
        return f"{op.sym} = {op.v} is out of range", {}
    u = _unit(op.u)
    if dim == ANGLE:
        if u not in ANGLE_UNITS and u != "":
            return f"{op.sym}: {op.u!r} is not an angle unit", {}
        u = ANGLE_UNITS.get(u, "deg")
    elif dim == PURE:
        if u not in ("", "1"):
            return f"{op.sym} is a pure number, not {op.u!r}", {}
    else:
        try:
            unit = ureg().parse_units(u) if u else None
        except (pint.errors.UndefinedUnitError, AttributeError, ValueError, AssertionError):
            return f"unknown unit {op.u!r}", {}
        if unit is None or ureg().Quantity(1, unit).dimensionality != ureg().get_dimensionality(dim):
            return f"{op.sym}: unit {op.u!r} does not fit {dim}", {}
    for v, e in hit:  # a unit said after the number must be the op's
        su = said_unit(op.q, e)
        if su and dim not in (PURE,):
            if dim == ANGLE:
                if ANGLE_UNITS.get(su) != u:
                    return f"the quote says {su}, the op says {op.u!r}", {}
            elif ureg().Quantity(1, su).dimensionality != ureg().Quantity(1, u).dimensionality or not math.isclose(
                    ureg().Quantity(1, su).to(u).magnitude, 1.0, rel_tol=1e-9):
                return f"the quote says {su}, the op says {op.u!r}", {}
    if dim == ANGLE:
        si, si_u = (op.v if u == "deg" else math.degrees(op.v)), "deg"
    elif dim == PURE:
        si, si_u = op.v, "1"
    else:
        si_u = SI_UNIT[dim]
        si = ureg().Quantity(op.v, u).to(si_u).magnitude
        if dim in ("[length]", "[time]", "[mass]", "[length] ** 3", "[mass] / [length] ** 3",
                   "[mass] * [length] / [time] ** 2") and si <= 0:
            return f"{op.sym} must be positive", {}
    return "", {"si": float(si), "si_u": si_u}


def _ids(g: Graph) -> set[str]:
    """One id space: entities, actions, laws and diagrams never share an id."""
    return set(g.ents) | set(g.actions) | set(g.laws) | set(g.diagrams)


def _dir_ok(d: str, g: Graph) -> bool:
    if d in ops.PLAIN_DIRS:
        return True
    kind, _, ref = d.partition(":")
    return kind in ("toward", "away") and ref in g.ents


def check(op: Any, g: Graph, lines: list[str]) -> tuple[str, dict[str, Any]]:
    """("", resolved facts) or (why refused, {}) for one parsed op against the graph so far."""
    E = g.ents
    k = op.op
    if k == "add":
        if not ops.ID.match(op.id):
            return f"bad id {op.id!r}", {}
        if op.kind not in ops.KINDS:
            return f"unknown kind {op.kind!r}", {}
        if op.id in E and E[op.id].kind != op.kind:
            return f"id {op.id!r} is already a {E[op.id].kind}", {}
        if op.id in _ids(g) and op.id not in E:
            return f"id {op.id!r} is already used", {}
        if not _NOUN.match(op.w):
            return f"bad noun {op.w!r}", {}
        if op.near and not catalog.known(op.near):
            return f"near noun {op.near!r} is not in the catalog", {}
        used = {e.draw[5:] for e in E.values() if e.draw.startswith("cast:")}
        d = catalog.resolve(op.kind, op.w, op.near, op.attr, used)
        if d is None:
            return f"nothing draws {op.w!r} as a {op.kind} (give a `near` noun from the catalog)", {}
        drawn = d.draw not in ("ground", "fluid") and not d.draw.startswith("backdrop:")
        if drawn and op.id not in E and len(g.visible()) >= ops.MAX_ENTITIES:
            return f"more than {ops.MAX_ENTITIES} visible entities", {}
        return "", {"draw": d.draw, "size": d.size}
    if k in ("set", "remove", "label") and op.id not in E:
        return f"unknown id {op.id!r}", {}
    if k == "set":
        if op.state and op.state not in ops.STATES:
            return f"unknown state {op.state!r}", {}
        if op.w:
            used = {e.draw[5:] for e in E.values() if e.draw.startswith("cast:") and e.id != op.id}
            d = catalog.resolve(E[op.id].kind, op.w, E[op.id].near, op.attr or E[op.id].attr, used)
            if d is None:
                return f"nothing draws {op.w!r}", {}
            return "", {"draw": d.draw, "size": d.size}
        return "", {}
    if k == "remove":
        return "", {}
    if k == "relate":
        if op.kind not in ops.RELATIONS:
            return f"unknown relation {op.kind!r}", {}
        for i in (op.a, op.b):
            if i not in E:
                return f"unknown id {i!r}", {}
        if op.a == op.b:
            return "an entity cannot relate to itself", {}
        if op.kind == "holding" and E[op.a].kind not in ("agent", "animal"):
            return f"{op.a} cannot hold (not a person)", {}
        if op.kind == "sitting_on" and E[op.a].kind not in ("agent", "animal"):
            return f"{op.a} cannot sit", {}
        return "", {}
    if k == "act":
        if not ops.ID.match(op.id) or op.id in _ids(g):
            return f"bad action id {op.id!r} (new and unused)", {}
        if op.verb not in ops.AGENT_VERBS + ops.OBJECT_VERBS:
            return f"unknown verb {op.verb!r}", {}
        if op.agent not in E:
            return f"unknown id {op.agent!r}", {}
        a = E[op.agent]
        if op.verb in ops.AGENT_VERBS and op.verb not in ops.OBJECT_VERBS:
            if a.kind == "animal":
                if op.verb not in ops.ANIMAL_VERBS:
                    return f"a {a.w} cannot {op.verb}", {}
            elif a.kind != "agent":
                return f"{op.verb} needs a person or an animal, {op.agent} is a {a.kind}", {}
        if op.obj is not None and op.obj not in E:
            return f"unknown id {op.obj!r}", {}
        if op.verb in ops.NEEDS_OBJ and op.obj is None:
            return f"{op.verb} needs an object", {}
        if op.dir and not _dir_ok(op.dir, g):
            return f"bad direction {op.dir!r}", {}
        if op.manner and op.manner not in ops.MANNERS:
            return f"unknown manner {op.manner!r}", {}
        if op.verb == "put_down" and g.holder(op.obj) != op.agent and not any(
                x.obj == op.obj and x.verb in ("carry", "hold", "pick_up") for x in g.active(op.agent)):
            return f"{op.agent} is not holding {op.obj}", {}
        return "", {}
    if k == "end":
        if op.id not in g.actions or not g.actions[op.id].active:
            return f"no active action {op.id!r}", {}
        return "", {}
    if k == "law":
        if not ops.ID.match(op.id) or (op.id in _ids(g) and op.id not in g.laws):
            return f"bad law id {op.id!r}", {}
        if op.name not in ops.LAWS:
            return f"unknown law {op.name!r}", {}
        if op.name not in LAWS:
            return f"law {op.name!r} is not built yet", {}
        spec = LAWS[op.name]
        for role in spec.roles:
            if role not in op.roles:
                return f"{op.name} needs the role {role!r}", {}
        for role, v in op.roles.items():
            if role not in spec.roles + spec.optional:
                return f"{op.name} has no role {role!r}", {}
            ids = v if isinstance(v, list) else [v]
            if (role in spec.lists) != isinstance(v, list):
                return f"role {role!r} must be {'a list' if role in spec.lists else 'one id'}", {}
            for i in ids:
                if i not in E:
                    return f"unknown id {i!r}", {}
        why = spec.pre(g, op.roles) if spec.pre else ""
        return (f"precondition: {why}", {}) if why else ("", {})
    if k == "given":
        return check_given(op, g, lines)
    if k == "view":
        mode, _, ref = op.mode.partition(":")
        if op.mode not in ops.VIEWS and not (mode == "inset_from" and ref in E):
            return f"unknown view {op.mode!r}", {}
        for i in op.ids:
            if i not in E:
                return f"unknown id {i!r}", {}
        return "", {}
    if k == "frame":
        if op.shot not in ops.SHOTS:
            return f"unknown shot {op.shot!r}", {}
        bad = [i for i in op.ids if i not in E]
        return (f"unknown id {bad[0]!r}", {}) if bad else ("", {})
    if k == "diagram":
        if not ops.ID.match(op.id) or (op.id in _ids(g) and op.id not in g.diagrams):
            return f"bad id {op.id!r}", {}
        if op.recipe not in ops.RECIPES:
            return f"unknown recipe {op.recipe!r}", {}
        heard = [v for line in lines for v, _ in quoted_numbers(line)]
        for key, v in op.params.items():
            if isinstance(v, (int, float)) and not isinstance(v, bool) and not any(
                    math.isclose(abs(v), abs(h), rel_tol=1e-9) for h in heard):
                return f"diagram param {key}={v} was not said", {}
            if isinstance(v, str) and v not in E and not said_words(v, Corpus.of(lines)):
                return f"diagram param {key}={v!r} was not said", {}
        return "", {}
    if k == "label":
        if not said_words(op.text, Corpus.of(lines)):
            return f"label {op.text!r} has words the teacher did not say", {}
        return "", {}
    return f"op {k!r} cannot be checked here", {}


def _words(raw: dict) -> str:
    return " ".join(str(raw.get(k, "")) for k in ("w", "near", "text", "q", "attr"))


def check_delta(raws: list[dict], g: Graph, lines: list[str], line_id: str = "") -> Delta:
    """One line's ops, checked in order against a working copy of the graph (a later op may use an earlier add).
    `lines`: the teacher's recent lines (bounded by the caller), the last one being this line."""
    out = Delta()
    if len(raws) > ops.MAX_OPS:
        out.dropped = f"{len(raws)} ops > {ops.MAX_OPS} per delta"
        return out
    if any(isinstance(r, dict) and r.get("op") == "unsafe" for r in raws):
        out.dropped = "unsafe"
        return out
    hit = next((b for b in (safety.blocked(_words(r)) for r in raws if isinstance(r, dict)) if b), "")
    if hit or (lines and safety.blocked(lines[-1])):
        out.dropped = f"blocked: {hit or safety.blocked(lines[-1])}"
        return out
    work = g.copy()
    for raw in raws:
        try:
            op = ops.parse(raw)
        except ValidationError as e:
            err = e.errors()[0]
            out.rejected.append(Rejected(raw, f"schema: {'.'.join(map(str, err['loc']))}: {err['msg']}"))
            continue
        if op.op == "undo":
            out.rejected.append(Rejected(raw, "undo is a teacher command, not an op"))
            continue
        why, facts = check(op, work, lines)
        if why:
            out.rejected.append(Rejected(raw, why))
            continue
        apply(work, op, facts, line_id)
        out.ok.append((op, facts))
    return out
