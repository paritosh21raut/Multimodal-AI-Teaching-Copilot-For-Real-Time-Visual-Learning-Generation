"""Interpretation acts → typed content pieces (F-005). Pure; no slide knowledge.

A piece is one unit of displayable content with the transcript lines it came from (for concern hold-back) and
the `added` flag. The composer decides where pieces go.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field, replace
from typing import Literal, Optional, Sequence

from copilot.core.interpretation import DiscourseAct, Interpretation

PieceKind = Literal["definition", "points", "steps", "comparison", "timeline", "formula", "causes", "example",
                    "facts", "tree", "groups"]

MAX_TEXT_CHARS = 140
NO_CONTENT_ACTS = {"question", "transition"}
# An item that only announces what comes next is not content ("Now let's learn about matter").
_ANNOUNCE = re.compile(r"^(?:so\s+|now\s*,?\s+|okay\s*,?\s+)*(?:let'?s|let us|we will|we'll|we are going to|"
                       r"today we|next we)\b", re.IGNORECASE)


def is_announcement(text: str) -> bool:
    return bool(_ANNOUNCE.match(text.strip()))


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
    pairs: tuple[tuple[str, str], ...] = ()          # timeline (when, what) / causes / facts (label, value)
    groups: tuple[tuple[str, tuple[str, ...]], ...] = ()  # named groups (label, items)
    formula: Optional[FormulaData] = None
    # the concept this piece is about, as named in the lecture ("KE", "Kinetic energy"); "" = not known. The
    # composer resolves it against the definitions on the slide (concept columns, live energy test 2026-10-06).
    about: str = ""
    meta: dict = field(default_factory=dict, compare=False, hash=False)

    def with_texts(self, texts: Sequence[str]) -> "Piece":
        return replace(self, texts=tuple(texts))

    def all_text(self) -> list[str]:
        out = [self.term, self.definition, *self.texts, *self.columns]
        out += [a for a, cells in self.rows for a in (a, *cells)]
        out += [x for p in self.pairs for x in p]
        out += [x for g, items in self.groups for x in (g, *items)]
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
            groups=tuple((fn(g), tuple(fn(x) for x in items)) for g, items in self.groups),
            formula=FormulaData(fn(self.formula.expression), tuple((fn(s), fn(m)) for s, m in self.formula.variables))
            if self.formula else None,
        )


MAX_DEFINITION_CHARS = 320  # definitions stay exact (RULES.md); live kinematics: "... without looking at the…"


def clean(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = " ".join(str(text).split()).strip(" -–•;,")
    if len(text) > max_chars:
        cut = text[:max_chars].rsplit(" ", 1)[0]
        text = cut + "…"
    return text


def _key(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


# Long test 2026-10-06: a misheard name corrected by the model left lines that only repeat themselves: "Bond angle is
# also known as Bond Angle", "Electron pairs: Known as electron pairs", "... (also called Bond Angle)".
_ALIAS_OF = re.compile(r"^(?P<a>.+?)\s+(?:is|are)\s+(?:also\s+)?(?:known as|called|termed|referred to as)\s+(?P<b>.+?)"
                       r"\.?$", re.IGNORECASE)
_ALIAS_ONLY = re.compile(r"^(?:(?:is|are)\s+)?(?:also\s+)?(?:known as|called|termed)\s+(?P<b>.+?)\.?$", re.IGNORECASE)
_ALIAS_PAREN = re.compile(r"\s*\((?:also\s+)?(?:called|known as|termed)\s+(?P<b>[^)]+)\)", re.IGNORECASE)


def is_tautology(text: str, term: str = "") -> bool:
    """A line that only says a name is itself."""
    m = _ALIAS_OF.match(text.strip())
    if m and _key(m.group("a")) == _key(m.group("b")):
        return True
    m = _ALIAS_ONLY.match(text.strip())
    return bool(m and term and _key(m.group("b")) == _key(term))


def drop_self_alias(text: str, term: str) -> str:
    """"Angle between bonds (also called Bond Angle)" for the term "Bond angle" → "Angle between bonds"."""
    return _ALIAS_PAREN.sub(lambda m: "" if _key(m.group("b")) == _key(term) else m.group(0), text).strip()


def _texts(values: Sequence[str]) -> tuple[str, ...]:
    out: list[str] = []
    for v in values:
        c = clean(v)
        if c and c not in out and not is_announcement(c) and not is_tautology(c):
            out.append(c)
    return tuple(out)


# "1 Debye (SI)": "3.33564 × 10⁻³⁰ Coulomb-meter" — a value, not a meaning (long test 2026-10-06)
_VALUE = re.compile(r"^[≈~<>]?\s*[-+]?\d[\d.,]*(?:\s*[×x*]\s*10\S*)?(?:\s+\S+){0,3}$")


def cap(text: str) -> str:
    return text[:1].upper() + text[1:] if text else text


# "PAN (Personal Area Network) – connects personal devices within ~10 m": a member named, then what it is. Not the
# colon form: "Physical: solid, liquid, gas" is a named group with its kinds (chemistry live 2026-10-05).
_MEMBER = re.compile(r"^(?P<term>[^–—:]{1,50}?)\s+[–—-]\s+(?P<text>\S.{8,})$")


def _members(points: tuple[str, ...]) -> Optional[list[tuple[str, str]]]:
    """The kinds of a classification given each with its meaning are the members of a set, each defined (live run
    2026-10-06: the network types came as "PAN (…) – connects personal devices …")."""
    found = [m for m in (_MEMBER.match(p) for p in points) if m]
    if not points or len(found) != len(points) or any(len(m.group("term").split()) > 6 for m in found):
        return None
    return [(m.group("term").strip(), m.group("text").strip()) for m in found]


def pieces_from_act(act: DiscourseAct) -> list[Piece]:
    it = act.items
    base = dict(lines=tuple(act.lines), added=act.added)
    out: list[Piece] = []
    if act.act in NO_CONTENT_ACTS:
        return out  # transitions and questions never put text on the slide
    points = _texts(it.points)
    members = _members(points) if act.act == "classification" and not it.groups else None
    if members:
        return [Piece("definition", term=term, definition=text, **base) for term, text in members]
    steps = _texts(it.steps)
    if act.act == "process" and not steps and points:
        steps, points = points, ()  # a process given as points is still a process
    term, definition = clean(it.term), clean(it.definition, MAX_DEFINITION_CHARS)
    definition = drop_self_alias(definition, term) if term else definition
    if term and is_tautology(definition, term):
        definition = ""
        term = ""
    if term and definition and _VALUE.match(definition):
        out.append(Piece("facts", pairs=((cap(term), definition),), **base))
    elif term and definition:
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
    facts = tuple((cap(clean(f.label)), cap(clean(f.value))) for f in it.facts if f.label.strip())
    # a yes/no "fact" is a statement ("Milky Way contains our solar system: Yes") -> a point
    yes = tuple(lb for lb, v in facts if v.lower() in ("yes", "true"))
    facts = tuple((lb, v) for lb, v in facts if v.lower() not in ("yes", "true", "no", "false"))
    points = points + _texts(yes)
    if facts:
        out.append(Piece("facts", pairs=facts, **base))
    groups = tuple((cap(clean(g.label)), _texts(g.items)) for g in it.groups if g.label.strip())
    if groups and not any(items for _, items in groups):
        # groups named but none with members ("By memory type": "Embedded memory", "External memory") are the kinds
        # of the classification; live test 2026-10-06 lost this classification ("nothing to display")
        points = points + _texts([g for g, _ in groups])
    groups = tuple(g for g in groups if g[1])
    if groups:
        out.append(Piece("groups", groups=groups, term=cap(clean(it.label)), **base))
    label = cap(clean(it.label))
    if act.act == "classification" and label and len(points) == 1 and len(points[0].split()) <= 4 and not groups \
            and not out:
        return out  # "Types of molecular velocities: Most probable velocity" announces the kinds (long test)
    if act.act == "classification" and label and points and 2 <= len(points) <= 6 \
            and all(len(x) <= 40 for x in points) and not groups:
        # a labelled classification of short kinds reads best as a tree ("Branches of chemistry" -> 4 kinds); a
        # labelled explanation is a list of properties ("Characteristics of ionic compounds", long test 2026-10-06)
        out.append(Piece("tree", term=label, texts=tuple(cap(x) for x in points), **base))
        points = ()
    if points:
        out.append(Piece("points", texts=points, term=label, **base))
    examples = _texts(it.examples)
    if examples and act.act not in ("example", "application"):
        # an explanation's "examples" are its points (the model mixes them up); real examples come from example acts
        out.append(Piece("points", texts=examples, **base))
        examples = ()
    for ex in examples:
        out.append(Piece("example", texts=(ex,), **base))
    return out


def pieces_from(it: Interpretation) -> list[Piece]:
    return pieces_and_chain(it)[0]


def pieces_and_chain(it: Interpretation, carry: str = "") -> tuple[list[Piece], str]:
    """Pieces of one interpretation, attributed to concepts. `carry`: the concept chain left by the previous unit of
    the same slide frame (the teacher is still on KE when the examples come in the next unit, live energy re-run)."""
    meta = set(it.meta_lines)
    out: list[Piece] = []
    for act in it.acts:
        if act.lines and set(act.lines) <= meta:
            continue  # content extracted from classroom-management lines is not displayed
        pieces = pieces_from_act(act)
        if act.act in NO_CONTENT_ACTS and not pieces:
            continue
        out += pieces
    return _attribute(_drop_covered_headings(_group_classifications(out)), carry)


def _drop_covered_headings(pieces: list[Piece]) -> list[Piece]:
    """A comparison with headings but no rows ("Speed" | "Velocity") whose sides the same unit already explains as
    points ("Speed is how fast ...", "Velocity includes ...") would be an empty table (live kinematics re-run)."""
    texts = " ".join(t.lower() for p in pieces if p.kind == "points" for t in p.texts)
    return [p for p in pieces if not (p.kind == "comparison" and not p.rows and p.columns
                                      and all(c.lower() in texts for c in p.columns))]


_ABOUT_KINDS = ("points", "example", "formula", "facts")


def _attribute(pieces: list[Piece], carry: str = "") -> tuple[list[Piece], str]:
    """Name the concept each piece is about: a definition names its term, a formula its left side ("KE = ½mv²");
    points / examples / facts right after them in the same unit follow the same concept ("Examples are a rolling
    ball ..." after the KE formula). Resolution against the slide is the composer's job."""
    out: list[Piece] = []
    current = carry  # newest last, one per line: names, and point texts that may mention a concept
    carried = bool(carry)  # nothing of this unit named a concept yet
    for p in pieces:
        own = ""
        if p.kind == "definition":
            own = p.term
        elif p.kind == "formula" and p.formula and "=" in p.formula.expression:
            own = p.formula.expression.split("=", 1)[0].strip()
        if own:
            current, carried = own, False
        if p.kind in _ABOUT_KINDS or p.kind == "definition":
            # carried: the concept comes only from the previous unit; the composer uses it when it is unambiguous
            # (long test 2026-10-06: the properties of covalent compounds went into the "Non-polar covalent bond"
            # card although two member cards were on the slide)
            p = replace(p, about=own or current, meta={**p.meta, "carried": carried and not own})
            if not own and p.texts:  # "Mass and height determine potential energy", then "e.g. a dam": PE
                current = "\n".join([*current.split("\n"), " ".join(p.texts)][-3:]).strip("\n")
        else:
            current = ""  # a diagram in between ends the chain
        out.append(p)
    return out, current


def _group_classifications(pieces: list[Piece]) -> list[Piece]:
    """Two or more labelled classifications taught together ("Inner planets: ...", "Outer planets: ...") are
    one set of named groups side by side, not separate diagrams."""
    trees = [p for p in pieces if p.kind == "tree"]
    if len(trees) < 2:
        return pieces
    lines = tuple(sorted({n for t in trees for n in t.lines}))
    groups = Piece("groups", lines=lines, groups=tuple((t.term, t.texts) for t in trees),
                   added=all(t.added for t in trees))
    out: list[Piece] = []
    for p in pieces:
        if p.kind != "tree":
            out.append(p)
        elif p is trees[0]:
            out.append(groups)
    return out
