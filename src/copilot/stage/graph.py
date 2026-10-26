"""The stage scene graph (contract §7): a fold of the event log. Only checked ops reach `apply` (stage.validate).

    entities   id, kind, said noun, attrs, state, what draws it (kit / cast / species), row (near / far)
    relations  one placement per entity (on, in, behind, ...; a new one replaces it); holding / attached_to are kept
               until the held thing is put somewhere ("puts the box on the table" ends the holding)
    actions    by act id: verb, agent, object, direction, manner; active until an `end`
    laws       by law id: name, roles, the givens said for it (value, unit, quote, SI value)
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Optional

PLACEMENT = ("on", "under", "in", "above", "behind", "in_front_of", "left_of", "right_of", "near", "sitting_on", "at")
KEEP = ("holding", "attached_to")


@dataclass
class Ent:
    id: str
    kind: str
    w: str
    draw: str
    size: tuple[float, float]
    near: Optional[str] = None
    attr: list[str] = field(default_factory=list)
    state: Optional[str] = None
    label: Optional[str] = None
    row: str = "near"
    added: int = 0       # seq of the add
    said: int = 0        # seq of the last op naming it (dimming)
    line: str = ""       # line id of the last op naming it (framing: the current sentence)


@dataclass
class Rel:
    a: str
    kind: str
    b: str


@dataclass
class Action:
    id: str
    verb: str
    agent: str
    obj: Optional[str] = None
    dir: Optional[str] = None
    manner: Optional[str] = None
    active: bool = True
    seq: int = 0
    line: str = ""


@dataclass
class GivenRec:
    sym: str
    v: float
    u: str
    q: str
    si: float
    si_u: str
    line: str = ""


@dataclass
class LawRec:
    id: str
    name: str
    roles: dict[str, Any]
    givens: dict[str, GivenRec] = field(default_factory=dict)


@dataclass
class Graph:
    ents: dict[str, Ent] = field(default_factory=dict)
    rels: list[Rel] = field(default_factory=list)
    actions: dict[str, Action] = field(default_factory=dict)
    laws: dict[str, LawRec] = field(default_factory=dict)
    view: dict[str, Any] = field(default_factory=lambda: {"mode": "side", "ids": []})
    frame: dict[str, Any] = field(default_factory=lambda: {"shot": "establish", "ids": []})
    diagrams: dict[str, dict[str, Any]] = field(default_factory=dict)
    lines: list[tuple[str, str]] = field(default_factory=list)  # (line id, said text) in order
    seq: int = 0

    def copy(self) -> "Graph":
        return copy.deepcopy(self)

    # ---------- queries ----------
    def rel(self, a: str, kind: Optional[str] = None) -> Optional[Rel]:
        return next((r for r in self.rels if r.a == a and (kind is None or r.kind == kind) and r.kind in PLACEMENT
                     + KEEP), None)

    def rels_of(self, x: str) -> list[Rel]:
        return [r for r in self.rels if x in (r.a, r.b)]

    def holder(self, x: str) -> Optional[str]:
        return next((r.a for r in self.rels if r.kind == "holding" and r.b == x), None)

    def active(self, agent: Optional[str] = None) -> list[Action]:
        return [a for a in self.actions.values() if a.active and (agent is None or a.agent == agent)]

    def law_of(self, name: str) -> Optional[LawRec]:
        return next((l for l in self.laws.values() if l.name == name), None)

    def visible(self) -> list[Ent]:
        """Entities drawn as kit / cast / species (a place is the backdrop; a ground or fluid noun is drawn by it)."""
        return [e for e in self.ents.values() if e.draw not in ("ground", "fluid") and not e.draw.startswith("backdrop:")]

    def place(self) -> Optional[Ent]:
        return next((e for e in reversed(list(self.ents.values())) if e.kind == "place"), None)

    def current_line(self) -> str:
        return self.lines[-1][0] if self.lines else ""


def _touch(g: Graph, ids: list[Optional[str]], line: str) -> None:
    for i in ids:
        if i and i in g.ents:
            g.ents[i].said, g.ents[i].line = g.seq, line


def apply(g: Graph, op: Any, checked: dict[str, Any], line: str) -> None:
    """Fold one checked op into the graph (in place). `checked` carries what the validator resolved (draw, SI value)."""
    g.seq += 1
    k = op.op
    if k == "add":
        if op.id in g.ents:  # a retried add: merge
            e = g.ents[op.id]
            e.attr = sorted(set(e.attr) | set(op.attr))
        else:
            g.ents[op.id] = Ent(op.id, op.kind, op.w, checked["draw"], tuple(checked["size"]), op.near, list(op.attr),
                                added=g.seq)
        _touch(g, [op.id], line)
    elif k == "set":
        e = g.ents[op.id]
        if op.w:
            e.w = op.w
            e.draw, e.size = checked.get("draw", e.draw), tuple(checked.get("size", e.size))
        if op.attr is not None:
            e.attr = list(op.attr)
        if op.state:
            e.state = op.state
        _touch(g, [op.id], line)
    elif k == "remove":
        g.ents.pop(op.id, None)
        g.rels = [r for r in g.rels if op.id not in (r.a, r.b)]
        for a in g.actions.values():
            if op.id in (a.agent, a.obj):
                a.active = False
        # a law or a view / frame that used it goes too (its roles are gone)
        g.laws = {k: l for k, l in g.laws.items() if op.id not in
                  [i for v in l.roles.values() for i in (v if isinstance(v, list) else [v])]}
        for d in (g.view, g.frame):
            d["ids"] = [i for i in d["ids"] if i != op.id]
        if g.view["mode"] == f"inset_from:{op.id}":
            g.view = {"mode": "side", "ids": []}
    elif k == "relate":
        if op.kind in PLACEMENT:
            g.rels = [r for r in g.rels if not (r.a == op.a and r.kind in PLACEMENT)]
            g.rels = [r for r in g.rels if not (r.kind == "holding" and r.b == op.a)]  # put somewhere: let go
        g.rels = [r for r in g.rels if not (r.a == op.a and r.kind == op.kind and r.b == op.b)]
        g.rels.append(Rel(op.a, op.kind, op.b))
        if op.a in g.ents:
            g.ents[op.a].row = "far" if op.kind == "behind" else ("near" if op.kind in PLACEMENT else g.ents[op.a].row)
        _touch(g, [op.a, op.b], line)
    elif k == "act":
        # one active action per agent: a new verb replaces the old ("now he pushes harder" restates push)
        for a in g.active(op.agent):
            if a.id != op.id:
                a.active = False
        g.actions[op.id] = Action(op.id, op.verb, op.agent, op.obj, op.dir, op.manner, True, g.seq, line)
        _touch(g, [op.agent, op.obj], line)
    elif k == "end":
        a = g.actions[op.id]
        a.active, a.seq, a.line = False, g.seq, line
        _touch(g, [a.agent, a.obj], line)
    elif k == "law":
        prev = g.laws.get(op.id)
        g.laws[op.id] = LawRec(op.id, op.name, dict(op.roles), prev.givens if prev and prev.name == op.name else {})
        _touch(g, [v for r in op.roles.values() for v in (r if isinstance(r, list) else [r])], line)
    elif k == "given":
        g.laws[op.law].givens[op.sym] = GivenRec(op.sym, op.v, op.u, op.q, checked["si"], checked["si_u"], line)
    elif k == "view":
        g.view = {"mode": op.mode, "ids": list(op.ids)}
    elif k == "frame":
        g.frame = {"shot": op.shot, "ids": list(op.ids)}
        _touch(g, list(op.ids), line)
    elif k == "diagram":
        g.diagrams[op.id] = {"recipe": op.recipe, "params": dict(op.params), "line": line}
    elif k == "label":
        g.ents[op.id].label = op.text
        _touch(g, [op.id], line)
