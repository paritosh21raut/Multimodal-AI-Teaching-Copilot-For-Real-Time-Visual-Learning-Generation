"""The diagram event log and graph (contract §6): every op the validator saw, accepted or refused, in order; the graph
is a fold of the accepted events of the lines not undone (undo = a logged event that marks its line)."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from copilot.diagram import ops as O

RECENT = 6  # lines a quote or a label may come from (the context stays bounded)


@dataclass
class Part:
    id: str
    kind: str
    label: str = ""
    label_src: str = ""          # said | auto | table
    attr: dict[str, Any] = field(default_factory=dict)
    line_id: str = ""
    seq: int = 0


@dataclass
class Graph:
    parts: dict[str, Part] = field(default_factory=dict)
    rels: dict[str, tuple[str, str]] = field(default_factory=dict)   # a -> (rel, b): one placement per part
    groups: dict[str, tuple[str, list[str]]] = field(default_factory=dict)
    wires: list[tuple[str, str]] = field(default_factory=list)
    processes: list[dict[str, Any]] = field(default_factory=list)
    givens: dict[str, dict[str, Any]] = field(default_factory=dict)  # sym -> {v, u, q, on}
    shows: list[tuple[str, Optional[str]]] = field(default_factory=list)
    last: str = ""                                                    # the part the last line named (focus)
    qty: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)  # (on, sym) -> {v, u, q, dir, …}; latest wins

    def copy(self) -> "Graph":
        return Graph({k: Part(**asdict(v)) for k, v in self.parts.items()}, dict(self.rels),
                     {k: (m, list(i)) for k, (m, i) in self.groups.items()}, list(self.wires),
                     [dict(p) for p in self.processes], {k: dict(v) for k, v in self.givens.items()},
                     list(self.shows), self.last, {k: dict(v) for k, v in self.qty.items()})

    def of(self, kind: str) -> list[Part]:
        return [p for p in self.parts.values() if p.kind == kind]

    def children(self, b: str, rel: Optional[str] = None) -> list[str]:
        return [a for a, (r, x) in self.rels.items() if x == b and (rel is None or r == rel)]

    def value(self, on: str, sym: str) -> Optional[dict[str, Any]]:
        return self.qty.get((on, sym))

    def has_process(self, verb: str) -> bool:
        return any(p["verb"] == verb for p in self.processes)


def apply(g: Graph, op: Any, line_id: str, seq: int) -> None:
    """One accepted op into the graph (the validator already checked it)."""
    if isinstance(op, O.Part):
        a = dict(op.attr)
        src = str(a.pop("label_src", "") or ("said" if op.label else ""))
        g.parts[op.id] = Part(op.id, op.kind, op.label or "", src, a, line_id, seq)
        g.last = op.id
    elif isinstance(op, O.Solution):
        g.parts[op.id] = Part(op.id, "liquid", op.solute, "said", {"solute": op.solute, "conc": op.conc}, line_id, seq)
        g.last = op.id
    elif isinstance(op, O.Contain):
        g.rels[op.b] = ("in", op.a)
    elif isinstance(op, O.Place):
        g.rels[op.a] = (op.rel, op.b)
    elif isinstance(op, O.Group):
        g.groups[op.id] = (op.mode, list(op.items))
    elif isinstance(op, O.Wire):
        g.wires.append((op.a, op.b))
    elif isinstance(op, O.Process):
        g.processes = [p for p in g.processes if not (p["verb"] == op.verb and p["target"] == op.target)]
        g.processes.append({"verb": op.verb, "target": op.target, "src": op.src, "manner": op.manner, "seq": seq})
    elif isinstance(op, O.Given):
        g.givens[op.sym] = {"v": op.v, "u": op.u, "q": op.q, "on": op.on}
    elif isinstance(op, O.Qty):
        g.qty[(op.on, op.sym)] = {"v": op.v, "u": op.u, "q": op.q, "dir": op.dir, "note": op.note, "line_id": line_id,
                                  "seq": seq}
    elif isinstance(op, O.Show):
        if (op.what, op.on) not in g.shows:
            g.shows.append((op.what, op.on))


@dataclass
class Event:
    seq: int
    t_ms: int
    src: str
    line_id: str
    op: Any
    ok: bool
    reason: Optional[str] = None

    def row(self) -> dict[str, Any]:
        d = {k: v for k, v in asdict(self).items() if v is not None and k != "op"}
        d["op"] = self.op.model_dump(exclude_none=True) if hasattr(self.op, "model_dump") else self.op
        return d


@dataclass
class DiagramLog:
    events: list[Event] = field(default_factory=list)
    lines: list[tuple[str, str]] = field(default_factory=list)
    undone: set[str] = field(default_factory=set)

    def say(self, line_id: str, text: str) -> None:
        if not any(i == line_id for i, _ in self.lines):
            self.lines.append((line_id, text))

    def recent(self) -> list[str]:
        return [t for i, t in self.lines if i not in self.undone][-RECENT:]

    def delta(self, raws: list[dict], line_id: str, src: str = "fast", t_ms: int = 0, text: str = "") -> Any:
        """Check one line's ops against the current graph and log every op with its outcome."""
        from copilot.diagram.validate import check_delta
        g = self.fold(skip_fast_of=line_id if src == "llm" else None)  # M3: the answer stands for the whole line
        d = check_delta(raws, g, self.recent(), text, max_ops=None if src == "fast" else O.MAX_OPS)
        for raw, why in d.rejected:
            self.events.append(Event(len(self.events) + 1, t_ms, src, line_id, raw, False, why))
        for op in d.ok:
            self.events.append(Event(len(self.events) + 1, t_ms, src, line_id, op, True))
        return d

    def undo(self, line_id: str, t_ms: int = 0) -> None:
        self.undone.add(line_id)
        self.events.append(Event(len(self.events) + 1, t_ms, "teacher", line_id, {"op": "undo", "line": line_id}, True))

    def last_line(self) -> Optional[str]:
        """The newest line (in speech order: a late LLM answer for an older line is not "the last line") that drew."""
        drew = {e.line_id for e in self.events if e.ok and e.src != "teacher" and e.line_id not in self.undone}
        return next((i for i, _ in reversed(self.lines) if i in drew), None)

    def later_refs(self, line_id: str) -> set[str]:
        """M3 review: the ids the lines said after `line_id` use (a late answer must keep them: a value of l2 on the
        block l1 drew stays on a part that exists)."""
        order = [i for i, _ in self.lines]
        after = set(order[order.index(line_id) + 1:]) if line_id in order else set()
        out: set[str] = set()
        for e in self.events:
            if e.ok and e.line_id in after and e.line_id not in self.undone and not isinstance(e.op, dict):
                for k in ("a", "b", "on", "target", "src"):
                    v = getattr(e.op, k, None)
                    if isinstance(v, str):
                        out.add(v.split(".")[0])
                out.update(getattr(e.op, "items", None) or [])
        return out

    def superseded(self) -> set[str]:
        """M3: the lines an LLM answer replaced (their fast events stay in the log, the fold skips them)."""
        return {e.line_id for e in self.events if e.ok and e.src == "llm"}

    def fold(self, skip_fast_of: Optional[str] = None) -> Graph:
        g = Graph()
        skip = self.superseded() | ({skip_fast_of} if skip_fast_of else set())
        for e in self.events:
            if e.ok and e.line_id not in self.undone and not isinstance(e.op, dict) \
                    and not (e.src == "fast" and e.line_id in skip):
                apply(g, e.op, e.line_id, e.seq)
        return g
