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
# "The third topic is Integral Calculus" (test23 showed it as a bullet): the series form, short
_ANNOUNCE_ORDINAL = re.compile(r"^(?:so\s+|now\s*,?\s+|and\s+)*(?:the\s+|our\s+)?(?:first|second|third|fourth|fifth|"
                               r"sixth|seventh|eighth|ninth|tenth|next|last|final|\d+(?:st|nd|rd|th))\s+(?:topic|"
                               r"chapter|unit|section|concept|subtopic)\s+(?:is|will be|for today is)\b", re.IGNORECASE)


def is_announcement(text: str) -> bool:
    t = text.strip()
    return bool(_ANNOUNCE.match(t)) or (bool(_ANNOUNCE_ORDINAL.match(t)) and len(t.split()) <= 10)


@dataclass(frozen=True)
class FormulaData:
    expression: str
    variables: tuple[tuple[str, str], ...] = ()  # (symbol, meaning)
    # F-013 S3 (C10): a named standard equation from presentation.equations (its own KaTeX and symbol latex)
    latex: str = ""
    name: str = ""
    standard: bool = False
    var_latex: tuple[str, ...] = ()


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
            formula=replace(self.formula, expression=fn(self.formula.expression),
                            variables=tuple((fn(s), fn(m)) for s, m in self.formula.variables))
            if self.formula and not self.formula.standard else self.formula,
        )


MAX_DEFINITION_CHARS = 320  # definitions stay exact (RULES.md); live kinematics: "... without looking at the…"


def clean(text: str, max_chars: int = MAX_TEXT_CHARS) -> str:
    text = " ".join(str(text).split()).rstrip(" -–•;,")
    # a leading dash is a list marker, but not a minus sign: "-55 °C" became "55 °C" on the slide (test5, F-013 S3)
    if not re.match(r"[-–]\s*\d", text):
        text = text.lstrip(" -–•;,")
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
    """First letter upper; a Greek symbol keeps its case (test15: the term "ν" became "Ν", capital nu)."""
    return text[:1].upper() + text[1:] if text and not "\u0370" <= text[0] <= "\u03ff" else text


# a "definition" that only tells a fact about the term (test4 "Electron: was discovered as a result of study of
# cathode rays") is a point: "Electron was discovered ..." (F-013 S3)
_NOT_A_DEFINITION = re.compile(r"^(?:was|were|has|had|have|can|could|will|would|did|does|became|got)\b", re.IGNORECASE)


def _list_not_definition(definition: str) -> tuple[str, ...]:
    """"Encryption; Secure communication; Digital signature; Cyber security" (test23, as the "definition" of prime
    numbers) is a list of short items, not a definition: its parts, else ()."""
    parts = [p.strip() for p in definition.split(";") if p.strip()]
    return tuple(parts) if len(parts) >= 3 and all(len(p.split()) <= 3 for p in parts) else ()


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


# a date or time of a timeline event: a number (1930, 6 April), a month, an era ("18th century", "BC")
_DATED = re.compile(r"\d|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b|\b(?:century|centuries|era|"
                    r"age|period|dynasty|bc|bce|ad|ce|ancient|medieval|modern|today|now|later|earlier|before|after|"
                    r"during|spring|summer|autumn|winter|morning|evening|night)\b", re.IGNORECASE)

# "Label: rest" points (F-013 S3, layouts): what the rest is decides the block
LABELLED = re.compile(r"^(?P<label>[^:]{1,40}?):\s+(?P<rest>\S.*)$")


def list_items(rest: str) -> tuple[str, ...]:
    """"Germany, Austria, Hungary, Turkey" -> the names; () when the rest is a description ("warm year-round, often
    heavy rainfall"). A list: three or more short items, or two or more capitalised names."""
    items = [x.strip() for x in re.split(r",\s*|\s+and\s+", rest.rstrip(".")) if x.strip()]
    if len(items) < 2 or any(len(x.split()) > 4 for x in items):
        return ()
    return tuple(items) if len(items) >= 3 or all(x[:1].isupper() for x in items) else ()


def _labelled(points: tuple[str, ...]) -> tuple[tuple, tuple, tuple[str, ...]]:
    """Points that are really named groups or attribute tiles, from at least two of the same shape (one line alone
    stays a point):
    - groups: "Central Powers: Germany, Austria, Hungary, Turkey" + "Allied Powers: France, …" (test7, said as a
      text wall),
    - facts: "Distance: 240 miles", "Initial followers: 78" (test6): short values, most with a number.
    Returns (groups, facts, the other points)."""
    found = [(p, LABELLED.match(p)) for p in points]
    lists = [(p, m.group("label"), list_items(m.group("rest"))) for p, m in found if m and len(m.group("label").split()) <= 4]
    lists = [x for x in lists if x[2]]
    groups = tuple((cap(lb), items) for _, lb, items in lists) if len(lists) >= 2 else ()
    used = {p for p, _, _ in lists} if groups else set()
    attrs = [(p, m.group("label"), m.group("rest")) for p, m in found
             if m and p not in used and len(m.group("label").split()) <= 4 and len(m.group("rest").split()) <= 4]
    with_number = sum(1 for _, _, v in attrs if re.search(r"\d", v))
    facts = tuple((cap(lb), v) for _, lb, v in attrs) if len(attrs) >= 2 and 2 * with_number >= len(attrs) else ()
    used |= {p for p, _, _ in attrs} if facts else set()
    return groups, facts, tuple(p for p in points if p not in used)


def _described_kinds(points: tuple[str, ...]) -> Optional[list[tuple[str, str]]]:
    """A classification whose every point is "Kind: what it is" ("Star: Devices connect to a central switch or hub",
    test24; "Ready: Waiting for CPU time", test25): the members of the set, each defined (member cards, not a text
    wall). A named group with its kinds ("Physical: solid, liquid, gas") is not one."""
    found = [LABELLED.match(p) for p in points]
    if len(points) < 2 or not all(found):
        return None
    if any(len(m.group("label").split()) > 4 or len(m.group("rest").split()) < 3 or list_items(m.group("rest"))
           for m in found if m):
        return None
    return [(m.group("label").strip(), cap(m.group("rest").strip())) for m in found if m]


MAX_COLUMNS = 4
# a cell that names its column: "TNN: fixed-length input", "ANN: moderate" (test18: three networks squeezed into a
# two-way table whose only "compared" name was the aspect)
_NAMED_CELL = re.compile(r"^(?P<n>[A-Z][\w.+&-]{0,15}(?: [A-Z][\w.+&-]{0,15})?):\s+(?P<v>\S.*)$")


def comparison_pieces(it, base: dict) -> list[Piece]:
    """An N-way comparison (F-013 S3, C1): columns = the compared names (2-4), rows = (aspect, one cell per column).
    Repairs of the model's shapes, all from its own words: cells "Name: value" name the columns; one heading over
    rows that each name a different thing are attribute facts, not a table (test5: mixture -> freezing point); a row
    that only repeats the column names is no content (test15 "frequency: blue light | red light"). Without names the
    rows continue the slide's comparison (the composer turns them into points when there is none)."""
    names = list(_texts(it.compare))
    rows = [(clean(r.aspect), [clean(v) for v in r.values]) for r in it.rows]
    rows += [(clean(p.aspect), [clean(p.left), clean(p.right)]) for p in it.pairs]
    rows = [(a, vs) for a, vs in rows if any(vs)]
    if not rows:
        return [Piece("comparison", columns=tuple(cap(n) for n in names), **base)]             if 2 <= len(names) <= MAX_COLUMNS else []
    cells = [v for _, vs in rows for v in vs if v]
    named = [_NAMED_CELL.match(v) for v in cells]
    if all(named) and 2 <= len({m["n"].lower() for m in named}) <= MAX_COLUMNS:
        cols: list[str] = []
        for m in named:
            if m["n"].lower() not in (c.lower() for c in cols):
                cols.append(m["n"])
        merged: dict[str, tuple[str, list[str]]] = {}
        for a, vs in rows:
            row = merged.setdefault(_key(a), (a, [""] * len(cols)))[1]
            for v in filter(None, vs):
                m = _NAMED_CELL.match(v)
                i = [c.lower() for c in cols].index(m["n"].lower())
                row[i] = row[i] or cap(m["v"])
        return [Piece("comparison", columns=tuple(cols), rows=tuple((a or "—", tuple(r)) for a, r in merged.values()),
                      **base)]
    if len(names) < 2 and len(rows) >= 2 and len({_key(a) for a, _ in rows}) == 1             and all(len(vs) == 2 and all(vs) for _, vs in rows) and len({_key(vs[0]) for _, vs in rows}) == len(rows):
        return [Piece("facts", pairs=tuple((cap(vs[0]), vs[1]) for _, vs in rows), term=cap(rows[0][0]), **base)]
    keys = [_key(n) for n in names]
    rows = [(a, vs) for a, vs in rows if not (keys and [_key(v) for v in vs] == keys[:len(vs)])]
    if not rows:
        return []
    width = max(len(vs) for _, vs in rows)
    cols = tuple(cap(n) for n in names) if 2 <= len(names) <= MAX_COLUMNS and width <= len(names) else ()
    n = len(cols) or width
    return [Piece("comparison", columns=cols, rows=tuple((a or "—", tuple((vs + [""] * n)[:n])) for a, vs in rows),
                  **base)]


def pieces_from_act(act: DiscourseAct) -> list[Piece]:
    it = act.items
    base = dict(lines=tuple(act.lines), added=act.added)
    out: list[Piece] = []
    if act.act in NO_CONTENT_ACTS:
        return out  # transitions and questions never put text on the slide
    points = _texts(it.points)
    members = _members(points) or _described_kinds(points) if act.act == "classification" and not it.groups \
        else None
    if members:
        return [Piece("definition", term=term, definition=text, **base) for term, text in members]
    steps = _texts(it.steps)
    if act.act == "process" and not steps and points:
        steps, points = points, ()  # a process given as points is still a process
    term, definition = clean(it.term), clean(it.definition, MAX_DEFINITION_CHARS)
    definition = drop_self_alias(definition, term) if term else definition
    if term and definition.lower().startswith(term.lower() + ":"):  # "Hypothalamus: Hypothalamus: brain region ..."
        definition = cap(definition[len(term) + 1:].strip())
    if term and definition and _NOT_A_DEFINITION.match(definition):
        points, term, definition = (f"{cap(term)} {definition}", *points), "", ""
    elif term and definition and _list_not_definition(definition):
        out.append(Piece("points", texts=_texts(_list_not_definition(definition)), term=cap(term), **base))
        term, definition = "", ""
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
    out += comparison_pieces(it, base)
    events = tuple((clean(e.when), clean(e.what)) for e in it.events if e.what.strip())
    # a timeline holds dated events only; an undated "event" is a statement (F-013 S3, C9)
    points = points + tuple(f"{w}: {x}" if w else x for w, x in events if not _DATED.search(w))
    events = tuple((w, x) for w, x in events if _DATED.search(w))
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
    if not groups and not facts:  # the model gave them as "Label: ..." points
        groups, facts, points = _labelled(points)
        if facts:
            out.append(Piece("facts", pairs=facts, **base))
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
