"""The stage event log (contract §7): every op the validator saw, accepted or refused, in order. The scene graph is a
fold of the accepted events; undo is a compensating event (nothing is deleted). Draft ops of the fast path
(`src: fast`) count until the LLM delta of the same line arrives, which replaces them.

    Event = {seq, t_ms, src: fast | llm | teacher, line_id, op, ok, reason?}
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional

from copilot.stage import ops
from copilot.stage.graph import Graph, apply
from copilot.stage.validate import Delta, check, check_delta

RECENT = 6  # lines a quote may come from (the context stays bounded)


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
        return {k: v for k, v in asdict(self).items() if v is not None}


@dataclass
class EventLog:
    events: list[Event] = field(default_factory=list)
    lines: list[tuple[str, str]] = field(default_factory=list)  # (line id, said text)

    def say(self, line_id: str, text: str) -> None:
        if not any(i == line_id for i, _ in self.lines):
            self.lines.append((line_id, text))

    def recent(self, upto: Optional[str] = None) -> list[str]:
        ids = [i for i, _ in self.lines]
        end = ids.index(upto) + 1 if upto in ids else len(ids)
        return [t for _, t in self.lines[max(0, end - RECENT):end]]

    def _add(self, t_ms: int, src: str, line_id: str, op: Any, ok: bool, reason: Optional[str] = None) -> Event:
        e = Event(len(self.events) + 1, t_ms, src, line_id, op, ok, reason)
        self.events.append(e)
        return e

    def delta(self, raws: list[dict], line_id: str, src: str = "llm", t_ms: int = 0) -> Delta:
        """Check one line's ops against the current graph (for an LLM delta: without that line's fast drafts, which
        it replaces) and log every op with its outcome."""
        base = self.fold(skip_fast_of=line_id if src == "llm" else None)
        d = check_delta(raws, base, self.recent(line_id), line_id)
        if d.dropped:
            for r in raws:
                self._add(t_ms, src, line_id, r, False, f"delta dropped: {d.dropped}")
            return d
        for op, _ in d.ok:
            self._add(t_ms, src, line_id, ops.dump(op), True)
        for rj in d.rejected:
            self._add(t_ms, src, line_id, rj.raw, False, rj.reason)
        return d

    def undo(self, seq: int, t_ms: int = 0, line_id: str = "") -> Event:
        ok = any(e.seq == seq and e.ok for e in self.events)
        return self._add(t_ms, "teacher", line_id, {"op": "undo", "seq": seq}, ok, None if ok else "no such event")

    def rejects(self) -> list[Event]:
        return [e for e in self.events if not e.ok]

    def fold(self, upto: Optional[int] = None, skip_fast_of: Optional[str] = None) -> Graph:
        """The graph after the accepted events (up to seq `upto`). An undone event is skipped; a fast draft is
        skipped once its line has an LLM delta. Ops are re-checked as they fold: one that no longer holds (it used
        an entity that was undone) is skipped."""
        evs = [e for e in self.events if upto is None or e.seq <= upto]
        undone = {e.op["seq"] for e in evs if e.ok and e.op.get("op") == "undo"}
        llm_lines = {e.line_id for e in evs if e.ok and e.src == "llm"} | ({skip_fast_of} if skip_fast_of else set())
        # an LLM delta that replaces a line's fast drafts folds where those drafts were (it may arrive after later
        # lines' ops, which can depend on it: "add man" of line 1 before "man walks" of line 2)
        first_fast: dict[str, int] = {}
        for e in evs:
            if e.src == "fast":
                first_fast.setdefault(e.line_id, e.seq)
        evs = sorted(evs, key=lambda e: (first_fast.get(e.line_id, e.seq) if e.src == "llm" else e.seq, e.seq))
        g = Graph()
        seen_lines: list[str] = []
        for e in evs:
            if not e.ok or e.seq in undone or e.op.get("op") == "undo":
                continue
            if e.src == "fast" and e.line_id in llm_lines:
                continue
            if e.line_id and e.line_id not in seen_lines:
                seen_lines.append(e.line_id)
                text = next((t for i, t in self.lines if i == e.line_id), "")
                g.lines.append((e.line_id, text))
            op = ops.parse(e.op)
            why, facts = check(op, g, self.recent(e.line_id))
            if why:
                continue
            apply(g, op, facts, e.line_id)
        return g
