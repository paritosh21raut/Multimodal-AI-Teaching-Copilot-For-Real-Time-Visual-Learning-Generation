"""Interpretation acts → typed content pieces (F-005). Pure; no slide knowledge.

A piece is one unit of displayable content with the transcript lines it came from (for concern hold-back) and
the `added` flag. The composer decides where pieces go.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal, Optional, Sequence

from copilot.core.interpretation import DiscourseAct, Interpretation

PieceKind = Literal["definition", "points", "steps", "comparison", "timeline", "formula", "causes", "example"]

MAX_TEXT_CHARS = 140
NO_CONTENT_ACTS = {"question", "transition"}


@dataclass(frozen=True)
class FormulaData:
    expression: str
    variables: tuple[tuple[str, str], ...] = ()  # (symbol, meaning)


@dataclass(frozen=True)
class Piece:
    kind: PieceKind
    lines: tuple[int, ...] = ()
    added: bool = False
    term: str = ""
    definition: str = ""
    texts: tuple[str, ...] = ()                      # points / steps / examples
    columns: tuple[str, ...] = ()                    # comparison headings
    rows: tuple[tuple[str, tuple[str, ...]], ...] = ()  # comparison (aspect, cells)
    pairs: tuple[tuple[str, str], ...] = ()          # timeline (when, what) / causes (cause, effect)
    formula: Optional[FormulaData] = None
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    def with_texts(self, texts: Sequence[str]) -> "Piece":
        return replace(self, texts=tuple(texts))

    def all_text(self) -> list[str]:
        out = [self.term, self.definition, *self.texts, *self.columns]
        out += [a for a, cells in self.rows for a in (a, *cells)]
        out += [x for p in self.pairs for x in p]
        if self.formula:
            out += [self.formula.expression, *(x for v in self.formula.variables for x in v)]
        return [t for t in out if t]

    def map_text(self, fn) -> "Piece":
        """Apply fn to every text field (e.g. an accepted transcription correction)."""
        return replace(
            self, term=fn(self.term), definition=fn(self.definition), texts=tuple(fn(t) for t in self.texts),
            columns=tuple(fn(c) for c in self.columns),
            rows=tuple((fn(a), tuple(fn(c) for c in cells)) for a, cells in self.rows),
            pairs=tuple((fn(a), fn(b)) for a, b in self.pairs),
            formula=FormulaData(fn(self.formula.expression), tuple((fn(s), fn(m)) for s, m in self.formula.variables))
            if self.formula else None,
        )


def clean(text: str) -> str:
    text = " ".join(str(text).split()).strip(" -–•;,")
    if len(text) > MAX_TEXT_CHARS:
        cut = text[:MAX_TEXT_CHARS].rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def _texts(values: Sequence[str]) -> tuple[str, ...]:
    out: list[str] = []
    for v in values:
        c = clean(v)
        if c and c not in out:
            out.append(c)
    return tuple(out)


def pieces_from_act(act: DiscourseAct) -> list[Piece]:
    it = act.items
    base = dict(lines=tuple(act.lines), added=act.added)
    out: list[Piece] = []
    points = _texts(it.points)
    steps = _texts(it.steps)
    if act.act == "process" and not steps and points:
        steps, points = points, ()  # a process given as points is still a process
    term, definition = clean(it.term), clean(it.definition)
    if term and definition:
        out.append(Piece("definition", term=term, definition=definition, **base))
    elif definition:
        points = (definition, *points)
    if steps:
        out.append(Piece("steps", texts=steps, **base))
    columns = _texts(it.compare)
    rows = tuple((clean(p.aspect) or "—", (clean(p.left), clean(p.right))) for p in it.pairs if p.left or p.right)
    if rows or len(columns) >= 2:
        # rows have exactly two cells (left, right): other column counts are unusable (the model sometimes lists
        # the aspect as "compare"); unknown columns merge into the current comparison
        cols = (columns if len(columns) == 2 else ()) if rows else columns[:3]
        out.append(Piece("comparison", columns=cols, rows=rows, **base))
    events = tuple((clean(e.when), clean(e.what)) for e in it.events if e.what.strip())
    if events:
        out.append(Piece("timeline", pairs=events, **base))
    causes = tuple((clean(c.cause), clean(c.effect)) for c in it.causes if c.cause.strip() and c.effect.strip())
    if causes:
        out.append(Piece("causes", pairs=causes, **base))
    if it.formula and it.formula.expression.strip():
        out.append(Piece("formula", formula=FormulaData(
            clean(it.formula.expression),
            tuple((clean(v.symbol), clean(v.meaning)) for v in it.formula.variables if v.symbol.strip()),
        ), **base))
    if points:
        out.append(Piece("points", texts=points, **base))
    examples = _texts(it.examples)
    if examples and act.act not in ("example", "application"):
        # an explanation's "examples" are its points (the model mixes them up); real examples come from example acts
        out.append(Piece("points", texts=examples, **base))
        examples = ()
    for ex in examples:
        out.append(Piece("example", texts=(ex,), **base))
    return out


def pieces_from(it: Interpretation) -> list[Piece]:
    meta = set(it.meta_lines)
    out: list[Piece] = []
    for act in it.acts:
        if act.lines and set(act.lines) <= meta:
            continue  # content extracted from classroom-management lines is not displayed
        pieces = pieces_from_act(act)
        if act.act in NO_CONTENT_ACTS and not pieces:
            continue
        out += pieces
    return out
