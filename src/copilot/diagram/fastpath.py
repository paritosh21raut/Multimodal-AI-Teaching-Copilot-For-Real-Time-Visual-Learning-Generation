"""The diagram fast path (F-018 §3, 0 tokens): a concept line -> a deterministic draft of diagram ops at once.

    nouns      part words (config/diagram_parts.json, longest phrase first, plurals), chemicals (the table), "solar
               system" (sun + the 8 planets in true order, each orbiting the sun), "<element> atom", an unknown noun in
               a diagram line ("next to a centrifuge" -> a labelled box)
    counts     "two circles" -> exactly 2; names said after the noun ("C1 and C2") label them in order; counted
               circuit parts get auto names R1, R2 …
    relations  a chemical with a container is IN it; "X on Y" -> on; "hanging from / attached to / with … hanging"
               -> hang_from (the part with an end is the hanger); a hanging spring or pulley gets its support
    processes  "adding / pouring water (in)to it" -> a pourer labelled with the chemical over the container; "stir"
               -> a glass rod in it; "heat" / a burner -> the flame; "and its field" -> the magnet's field lines
    numbers    only with their quote ("at 30 degrees" -> given theta, the validator checks it again); F-019: every
               quantity said (mass, force + its way, μ, k, θ) -> a `qty` op on its part (`quantities.attach`)
    mechanics  "two blocks, one on top of the other, on the floor" -> stacked; "a block on a table connected by a rope
               over a pulley to a hanging mass" -> the pulley at the table's edge, the rope, the mass hanging from it

With the open diagram's graph, a noun the diagram already has ("the beaker", "it", the same label) refers to it, and
the draft says which ids are old and which are new (continuity: a follow-up line stays on the open diagram).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any, Optional

from copilot.diagram import parts as P
from copilot.diagram.graph import Graph

COUNT = {"a": 1, "an": 1, "one": 1, "single": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "both": 2, "pair of": 2}
_DEF = ("the", "this", "that", "its", "same")
_HANG = re.compile(r"\b(?:hang\w*|hung|suspended|attached|tied)\b", re.IGNORECASE)
_ON = re.compile(r"^\s*(?:(?:which|that)\s+(?:is|are)\s+)?(?:(?:is|are|was|were)\s+)?(?:(?:lying|resting|placed|kept|"
                 r"sitting|sits|rests|lies|put|stacked)\s+)?(?:on|on top of|upon|over|above)(?:\s+(?:plane|flat|smooth|rough))?\s*$",
                 re.IGNORECASE)
_IN = re.compile(r"^\s*(?:(?:is|are|was|were)\s+)?(?:(?:placed|kept|put|drawn)\s+)?(?:in|inside|into|within)\s*$",
                 re.IGNORECASE)
# M0 (test36): "another circle", "one more", "a third": a part added to the open diagram, never the one there
# (one adjective may sit between, never an article: "after a second the box", "we added the box" name the open one)
_ANOTHER = re.compile(r"\b(?:another|one more|a second|a third|a fourth|a new|added|add|adding)\s+"
                      r"(?:(?!(?:the|this|that|its|a|an)\b)\w+\s+)?$", re.IGNORECASE)
# "If a square was inside C3": a shape inside the open part labelled C3
# (a garbled label keeps its letter + digits: "C1C" -> C1, test37)
_SHAPE_W = r"(?:circle|square|triangle|rectangle|pentagon|hexagon)\s+"
# (a stray capital in front is Whisper's too: "SC3" -> C3, test38)
_INSIDE_LABEL = re.compile(rf"\b(inside|within|in|outside|beside|next to),?\s+(?:the\s+)?(?:{_SHAPE_W})?"
                           r"[A-Z]?([A-Z][0-9]{1,2})[A-Z]?\b")
# test37: "C1 has a pentagon inside it" (the host first)
_HAS_INSIDE = re.compile(r"\b[A-Z]?([A-Z][0-9]{1,2})[A-Z]?\s+(?:has|have|contains?|holds?)\s+(?:a|an|the)?\s*(\w+)\s+"
                         r"(?:inside|in it|within)\b")
# a statement about a kind: "<noun> has / is / are / means ..." with no place word in the line
_PROPERTY = re.compile(r"\w+(?:e?s)?\s+(?:has|have|is|are|means|contains)\s+(?!(?:inside|outside|on|in|beside|placed|"
                       r"kept|added|drawn|put|next|above|below|under)\b)", re.IGNORECASE)
_PLACE_WORD = re.compile(r"\b(?:inside|outside|within|on top|beside|next to|above|below|under|placed|kept|added|drawn|"
                         r"put|hang\w*|hung|attached|poured|in it|into)\b", re.IGNORECASE)
# test37: "a box on an ink-like plane" (Whisper) -> an inclined plane: a word that sounds like "inclined" before "plane"
_PLANE = re.compile(r"\b([a-z]+(?:-[a-z]+)?)\s+plane\b", re.IGNORECASE)
# "a laptop of sodium" (test36, a mishear of "an atom of sodium"): an unknown noun + "of" + an element
_OF_ELEMENT = re.compile(r"\b(?:a|an)\s+([a-z]+)\s+of\s+([A-Za-z]+)\b")
_OF_OK = {"piece", "lump", "bit", "chunk", "sample", "block", "bar", "rod", "strip", "sheet", "wire", "mole", "moles",
          "gram", "grams", "pinch", "spoon", "spoonful", "jar", "bottle", "solution", "compound", "salt", "ion", "isotope",
          "nucleus", "electron", "proton", "neutron", "shell", "property", "properties", "number", "mass", "weight",
          "balloon", "tank", "cylinder", "kind", "form", "type", "layer", "coin", "can", "container", "cup", "glass",
          "gas", "foil", "ring", "nugget", "cloud", "source", "supply", "atmosphere", "flask", "beaker", "tube"}
_AROUND = re.compile(r"\b(?:around|orbiting|revolving|orbits?)\b", re.IGNORECASE)
_POUR = re.compile(r"\b(?:add|adding|added|adds|pour|pouring|poured|pours)\b", re.IGNORECASE)
_STIR = re.compile(r"\bstir(?:s|red|ring)?\b", re.IGNORECASE)
_HEAT = re.compile(r"\bheat(?:s|ed|ing)?\b", re.IGNORECASE)
_SLOW = re.compile(r"\b(?:slowly|gently|drop by drop|dropwise)\b", re.IGNORECASE)
_FIELD = re.compile(r"\b(?:field|field lines|lines of force)\b", re.IGNORECASE)
_SERIES = re.compile(r"\bin\s+series\b", re.IGNORECASE)
_PARALLEL = re.compile(r"\bin\s+parallel\b", re.IGNORECASE)
_SWITCH = re.compile(r"\b(open|closed|close|off|on)\b", re.IGNORECASE)
_PASSIVE = re.compile(r"\b(?:is|are|being|was|were|gets?)\s+(?:\w+ly\s+)?(?:added|poured)\b", re.IGNORECASE)
_PRONOUN = re.compile(r"\b(?:it|them|its)\b", re.IGNORECASE)
_ANGLE = re.compile(r"(?:(?:an?\s+)?angle\s+(?:of\s+)?)?(\d+(?:\.\d+)?|[a-z]+(?:[- ][a-z]+)?)\s*(?:degrees?|°)",
                    re.IGNORECASE)
_NAMES = re.compile(r"^\s*,?\s*(?:(?:called|named|labelled|labeled|of)\s+)?([A-Z][0-9]{0,2}(?:\s*(?:,|and|&)\s*"
                    r"[A-Z][0-9]{0,2})*)\b(?![a-z])")
_UNKNOWN = re.compile(r"\b(?:a|an|the)\s+([a-z]{4,})\b", re.IGNORECASE)
_STOP = {"time", "moment", "second", "minute", "example", "case", "situation", "scenario", "question", "answer",
         "lecture", "class", "topic", "concept", "idea", "diagram", "picture", "system", "model", "very", "little",
         "small", "large", "big", "long", "short", "simple", "certain", "given", "particular", "same", "other",
         "angle", "slowly", "while", "number", "value", "amount", "point", "drop", "solution", "liquid", "thing",
         "object", "body", "bunch", "couple", "lot", "few", "bit", "kind", "type", "sort", "glass", "reaction",
         "precipitate", "stiffness", "force", "energy", "process", "result", "change", "product", "first", "second",
         "third", "fourth", "fifth", "sixth", "next", "last", "whole", "half", "quarter", "speed", "velocity",
         "temperature", "pressure", "level", "colour", "color", "rate", "mixture", "effect", "reason", "experiment"}
_CUEW = re.compile(r"\b(?:imagine|picture|consider|suppose|visuali[sz]e|think of|draw|sketch)\b", re.IGNORECASE)
_NEXT_TO = re.compile(r"\b(?:next to|beside|near|and|with|on|in|inside|above|below|under|behind)\s+(?:a|an|the)\s+$",
                      re.IGNORECASE)
WORD_LABEL = {"block", "mass", "incline", "floor", "spring", "pulley", "beaker", "flask", "test_tube", "stirrer",
              "burner", "bar_magnet", "compass", "cell", "bulb", "switch"}  # a single one is labelled with the teacher's word
UNITS = {"kg", "g", "gram", "grams", "kilogram", "kilograms", "ohm", "ohms", "v", "volt", "volts", "cm", "m", "mm",
         "metre", "metres", "meter", "meters", "degree", "degrees", "n", "newton", "newtons", "ml", "litre", "litres",
         "amp", "amps", "ampere", "a", "s", "second", "seconds"} - {"a"}
# words that are also everyday words ("a spring morning", "the cell membrane", "a switch from coal"): a concept part only
# with "of" not following and, when nothing else in the line is a part, a physics / lab context word
AMBIGUOUS = {"spring", "cell", "switch", "mass", "block", "shell", "flask", "weight", "bob", "surface", "table",
             "floor", "ground", "lamp", "key", "battery", "slope", "ramp", "stand", "wedge", "compass", "flame", "sun"}
CONTEXT = re.compile(r"\b(?:hang\w*|hung|attached|suspended|stretch\w*|compress\w*|circuit|battery|series|parallel|"
                     r"current|volt\w*|resist\w*|bulb|wire|incline\w*|slope|pulley|friction\w*|smooth|oscillat\w*|beaker|"
                     r"spring constant|gravity|planet\w*|orbit\w*|magnet\w*|on (?:a|an|the) \w+)\b", re.IGNORECASE)
SYSTEM = re.compile(r"\bsolar\s+system\b", re.IGNORECASE)


@dataclass
class Mention:
    start: int
    end: int
    kind: str           # a part kind, "chem", "system", "unknown"
    word: str
    n: int = 1
    names: list[str] = field(default_factory=list)
    definite: bool = False
    ids: list[str] = field(default_factory=list)
    attr: dict[str, Any] = field(default_factory=dict)


@dataclass
class Draft:
    ops: list[dict] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)   # diagram kinds said
    old: list[str] = field(default_factory=list)     # ids of the open diagram the line names
    new: list[str] = field(default_factory=list)     # ids the line adds
    refers: bool = False                             # "it" / "the beaker": the line is about the open diagram
    named: list[str] = field(default_factory=list)   # ids of the open diagram the line names by label ("C1, C2")
    more: bool = False                               # "another / one more X" of a kind the open diagram has
    unknown: list[str] = field(default_factory=list)
    title: str = ""
    unattached: list[tuple[str, str]] = field(default_factory=list)  # (sym, quote): a value with no part to go on


@lru_cache(maxsize=1)
def _noun_rx() -> re.Pattern:
    alts = [re.escape(w) for w in P.words()] + [re.escape(w) for w in P.chemicals()]
    alts.sort(key=len, reverse=True)
    return re.compile(r"\b(solar\s+system|" + "|".join(alts) + r")(?:es|s)?\b", re.IGNORECASE)


def _count_before(text: str, start: int) -> tuple[int, bool]:
    """The count said right before a noun ("two circles", "three small blocks"); a number with a unit is a measure,
    not a count ("a 5 kg block" is one block, "a 10 ohm resistor" one resistor)."""
    toks = re.findall(r"[a-z0-9]+", text[max(0, start - 40):start].lower())[-2:]
    definite = bool(toks) and (toks[-1] in _DEF or "both" in toks)  # test42: "both blocks" are the ones drawn
    if not toks or toks[-1] in UNITS:
        return 1, definite

    def count(t: str) -> Optional[int]:
        if t.isdigit() and 0 < int(t) <= 30:
            return int(t)
        return COUNT.get(t)
    n = count(toks[-1])
    if n is None and len(toks) == 2 and not toks[-1].isdigit():  # one adjective between ("two small circles")
        n = count(toks[0])
    return n or 1, definite


def mentions(text: str) -> list[Mention]:
    out: list[Mention] = []
    for m in _noun_rx().finditer(text):
        w = m.group(1).lower()
        w = " ".join(w.split())
        if w == "solar system":
            out.append(Mention(m.start(), m.end(), "system", w))
            continue
        chem = P.chemicals().get(w)
        kind = P.words().get(w)
        if chem and (kind is None or kind == "liquid"):
            out.append(Mention(m.start(), m.end(), "chem", w, attr={"chem": chem}))
            continue
        if kind is None:
            continue
        if w in AMBIGUOUS and (re.match(r"\s+of\s+(?!(?:mass|weight)\b)(?!\d)(?!(?:one|two|three|four|five|six|seven|"
                                        r"eight|nine|ten|twenty|fifty|hundred|half)\b)\w", text[m.end():])
                               or re.search(r"\bof\s+$", text[max(0, m.start() - 4):m.start()])):
            continue  # "a mass of air", "a block of ice", "a block of mass 2 kg": not a part (the quantity is a given)
        n, definite = _count_before(text, m.start())
        mm = Mention(m.start(), m.end(), kind, w, n, definite=definite)
        nm = _NAMES.match(text[m.end():])
        if nm and kind not in ("planet", "atom"):
            mm.names = re.split(r"\s*(?:,|and|&)\s*", nm.group(1).strip())
            if mm.n == 1 and len(mm.names) > 1:
                mm.names = mm.names[:1]
        if kind == "planet" and P.planet(w):  # "a planet" (no name): a plain planet
            mm.attr["name"] = P.planet(w)["name"]
        if kind == "atom":
            el = _element_near(text, m.start(), m.end())
            if el:
                mm.attr["element"] = el
        out.append(mm)
    out.sort(key=lambda x: x.start)
    return out


def _element_near(text: str, s: int, e: int) -> Optional[str]:
    before = re.findall(r"[A-Za-z]+", text[max(0, s - 20):s])
    after = re.match(r"\s+of\s+([A-Za-z]+)", text[e:])
    for w in ([before[-1]] if before else []) + ([after.group(1)] if after else []):
        el = P.element(w) or (P.element(w.lower()) if w.islower() else None)
        if el:
            return el[1]
    return None


def unknown_nouns(text: str, known: list[Mention]) -> list[tuple[int, str]]:
    """Nouns after an article that no table knows (a diagram line's unknown part, drawn as a labelled box)."""
    from copilot.stage.fastpath import index
    spans = [(m.start, m.end) for m in known]
    out = []
    if not _CUEW.search(text):
        return []  # an explanation line ("… gives a precipitate") never adds a box
    for m in _UNKNOWN.finditer(text):
        w = m.group(1).lower()
        if not _NEXT_TO.search(text[max(0, m.start() - 20):m.start(1)]):
            continue
        if any(s <= m.start(1) < e for s, e in spans) or w in _STOP or w in index() or w.rstrip("s") in index():
            continue
        if P.words().get(w) or P.chemicals().get(w) or P.element(w):
            continue
        nxt = text[m.end(1):m.end(1) + 12].lower()
        if re.match(r"\s+(?:of|atom|system|plane|surface|table|floor|ground)\b", nxt):  # "a plane surface" (test36)
            continue
        out.append((m.start(1), w))
    return out


def said_counts(text: str) -> dict[str, int]:
    """The counts said with a part noun ("two circles" -> {circle: 2}); 1s are left out."""
    out: dict[str, int] = {}
    for m in mentions(text):
        if m.kind not in ("chem", "system", "unknown") and m.n > 1:
            out[m.kind] = out.get(m.kind, 0) + m.n
    return out


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "x"


class _Ids:
    def __init__(self, g: Graph) -> None:
        self.used = set(g.parts) | set(g.groups)

    def new(self, base: str) -> str:
        base = _slug(base)
        i, k = base, 2
        while i in self.used:
            i, k = f"{base}{k}", k + 1
        self.used.add(i)
        return i


def _container(ms: list[Mention], g: Graph, upto: int = 10 ** 9) -> Optional[str]:
    """The container the line or the open diagram names last."""
    for m in reversed([m for m in ms if m.start < upto]):
        if m.ids and _row(m.kind).get("container"):
            return m.ids[0]
    for m in reversed(ms):
        if m.ids and _row(m.kind).get("container"):
            return m.ids[0]
    return next((p.id for p in reversed(list(g.parts.values())) if P.kind(p.kind).get("container")), None)


def draft(text: str, g: Optional[Graph] = None) -> Draft:
    g = g or Graph()
    d = Draft()
    ids = _Ids(g)
    ms = mentions(text)
    ops: list[dict] = []
    pron = _PRONOUN.search(text)

    def add(kind: str, label: str = "", src: str = "", **attr: Any) -> str:
        i = ids.new(label if label and src != "table" else kind)
        a = dict(attr)
        if label:
            a["label_src"] = src or "said"
        ops.append({"op": "part", "id": i, "kind": kind, **({"label": label} if label else {}), **({"attr": a} if a else {})})
        d.new.append(i)
        return i

    # 1. the things: old ones referred to, new ones added (counts exact, names in order)
    for m in ms:
        if m.kind == "system":
            sun = next((p.id for p in g.of("sun")), None)
            if sun is None:
                sun = add("sun", "Sun", "table")
            else:
                d.old.append(sun)
            for row in P.table("planets"):
                old = next((p.id for p in g.of("planet") if p.attr.get("name") == row["name"]), None)
                if old:
                    d.old.append(old)
                    continue
                pid = add("planet", row["name"], "table", name=row["name"])
                ops.append({"op": "place", "a": pid, "rel": "orbit", "b": sun})
            m.ids = [sun]
            d.kinds += ["sun", "planet"]
            continue
        if m.kind == "chem":
            cid = m.attr["chem"]
            row = P.chemical(cid)
            old = next((p.id for p in g.of("liquid") if p.attr.get("chem") == cid), None)
            if old:
                m.ids = [old]
                d.old.append(old)
            d.kinds.append("liquid")
            continue
        d.kinds.append(m.kind)
        more = bool(_ANOTHER.search(text[max(0, m.start - 30):m.start]))
        d.more = d.more or (more and bool(g.of(m.kind)))
        same = [p for p in g.of(m.kind) if (m.names and p.label in m.names) or (not m.names and m.attr.get("name")
                and p.attr.get("name") == m.attr["name"])]
        if not same and not m.names and m.n == 1 and not more:  # the same cue said again (Whisper repeats)
            # "a box" = the box; "an atom (of)" = the atom with no other element said (shapes are drawn many times)
            same = [p for p in g.of(m.kind) if p.label_src == "said" and p.label.lower() == m.word
                    or not p.label and _row(m.kind).get("domain") != "shape"
                    and all(p.attr.get(k) == v for k, v in m.attr.items())][:1]
            kin = g.of(m.kind)
            if not same and len(kin) == 1 and kin[0].label_src == "said" and _head(kin[0].label) == _head(m.word):
                same = kin  # test40: "a spring with a hanging mass" said again = the mass there ("mass")
        if same:
            m.ids = [p.id for p in same]
            d.old += m.ids
            if m.names:
                d.named += m.ids
                have = {p.label for p in same}
                # "three circles C1, C2 and C3" with C1 and C2 open: the count includes them, only C3 is added
                m.ids += [add(m.kind, nm, "said", **m.attr) for nm in m.names if nm not in have]
            continue
        olds = g.of(m.kind)
        loose = [p for p in olds if p.id not in g.rels and _row(m.kind).get("domain") == "shape"]
        if loose and not m.names and m.n == 1 and not more:  # test37: "a pentagon ... inside C1" said again and
            olds = loose                                       # again: the one not placed yet, not a 2nd and 3rd
        if olds and not m.names and m.n == 1 and not more and (m.definite or not _fresh(text, m) or olds is loose):
            m.ids = [olds[-1].id]
            d.old.append(olds[-1].id)
            d.refers = d.refers or m.kind != "floor"  # M1: "imagine a block on the floor" is a new picture
            continue
        if g.parts and not m.names and _PROPERTY.match(text[m.start:]) and not _PLACE_WORD.search(text) \
                and not _CUEW.search(text):
            continue  # test38: "A square has 4 equal sides" is a fact about squares, not a new square
        n = max(m.n, len(m.names))
        auto = _row(m.kind).get("two_port") and m.kind != "cell" and n > 1
        for k in range(n):
            if k < len(m.names):
                m.ids.append(add(m.kind, m.names[k], "said", **m.attr))
            elif auto:
                m.ids.append(add(m.kind, f"{m.kind[0].upper()}{k + 1}", "auto", **m.attr))
            elif m.kind == "planet":
                m.ids.append(add("planet", m.attr["name"], "table", **m.attr))
            elif m.kind in WORD_LABEL and n == 1:
                m.ids.append(add(m.kind, m.word, "said", **m.attr))
            else:
                m.ids.append(add(m.kind, **m.attr))

    # "it" names the open diagram only before the line's own new things ("a spring with a mass hanging from it": the
    # spring; "and you're adding water to it": the beaker)
    first_new = min((m.start for m in ms if set(m.ids) & set(d.new)), default=len(text))
    d.refers = d.refers or bool(pron and g.parts and pron.start() < first_new)

    # 2. unknown nouns in a line that also names diagram parts: a labelled box with the said word
    if [m for m in ms if m.kind != "chem"] or [m for m in ms if m.kind == "chem"]:
        for pos, w in unknown_nouns(text, ms):
            old = next((p.id for p in g.of("unknown") if p.label.lower() == w), None)
            if old:
                d.old.append(old)
                continue
            mm = Mention(pos, pos + len(w), "unknown", w)
            mm.ids = [add("unknown", w, "said")]
            ms.append(mm)
            d.unknown.append(w)
        ms.sort(key=lambda x: x.start)

    # 3. chemicals: a liquid in its container; an added chemical pours in from a pourer
    pour = _POUR.search(text)
    passive = bool(pour and _PASSIVE.search(text[max(0, pour.start() - 30):pour.end()]))
    for m in [m for m in ms if m.kind == "chem"]:
        cid = m.attr["chem"]
        row = P.chemical(cid)
        poured = pour and (m.start < pour.start() if passive else m.start > pour.start())
        if poured and (_container(ms, g) or g.of("liquid") or len([x for x in ms if x.kind == "chem"]) > 1):
            tgt = _container(ms, g)
            if tgt is None:
                tgt = add("beaker")
                d.kinds.append("beaker")
                ms.append(Mention(len(text), len(text), "beaker", "beaker", ids=[tgt]))
            src = add("pourer", _chem_label(row, m.word, text), "said", chem=cid)
            ops.append({"op": "place", "a": src, "rel": "above", "b": tgt})
            ops.append({"op": "process", "verb": "pour", "target": tgt, "src": src,
                        **({"manner": "slow"} if _SLOW.search(text) else {})})
            m.ids = [src]
            continue
        if m.ids:
            continue
        lid = add("liquid", _chem_label(row, m.word, text), "said", chem=cid)
        m.ids = [lid]
        tgt = _container(ms, g)
        if tgt is None:
            tgt = add("beaker")
            d.kinds.append("beaker")
        ops.append({"op": "contain", "a": tgt, "b": lid})

    # 4. relations between neighbouring things
    things = [m for m in ms if m.ids and m.kind not in ("system",)]
    for a, b in zip(things, things[1:]):
        between = _gap(_QUANT.sub(" ", text[a.end:b.start], count=1))  # "a block of 10 kg on the floor": on
        if a.kind == "chem" or b.kind == "chem":
            continue
        rel = None
        if _HANG.search(between) or _HANG.search(text[b.end:b.end + 30]) and re.search(r"\bwith\b", between):
            rel = _hang(a, b, between)
        elif _ON.match(between):
            rel = ("on", a, b)
        elif _IN.match(between) and _row(b.kind).get("container"):
            rel = ("in", a, b)
        elif _IN.match(between) and _row(a.kind).get("domain") == _row(b.kind).get("domain") == "shape":
            rel = ("inside", a, b)  # "a square inside a circle"
        elif _AROUND.search(between) and b.kind in ("sun", "planet", "nucleus"):
            rel = ("orbit", a, b)
        if rel and rel[0] == "hang_from" and rel[2].kind == "support" and rel[1].kind not in ("spring", "pulley"):
            hanger = next((m for m in things if m.kind in ("spring", "pulley")), None)
            if hanger is not None:
                rel = ("hang_from", rel[1], hanger)
        if rel:
            r, x, y = rel
            for i in x.ids:
                if g.rels.get(i) != (r, y.ids[0]):
                    ops.append({"op": "place", "a": i, "rel": r, "b": y.ids[0]})
    _inside_label(text, things, ops, g)
    _mechanics(text, things, ops, g)
    _supports(ops, ms, g, add)

    # 5. processes and shows
    if _STIR.search(text) and (tgt := _container(ms, g)):
        rod = next((p.id for p in g.of("stirrer")), None) or add("stirrer")
        ops.append({"op": "place", "a": rod, "rel": "in", "b": tgt})
        ops.append({"op": "process", "verb": "stir", "target": tgt, "src": rod})
    if (_HEAT.search(text) or any(m.kind == "burner" for m in ms if m.ids and m.ids[0] in d.new)):
        tgt = _container(ms, g)
        if tgt:
            if not g.of("burner") and not any(m.kind == "burner" for m in ms):
                b = add("burner")
                ops.append({"op": "place", "a": tgt, "rel": "on", "b": b})
            ops.append({"op": "process", "verb": "heat", "target": tgt})
    if _FIELD.search(text):
        mag = next((m.ids[0] for m in ms if m.kind == "bar_magnet" and m.ids), None) or next(
            (p.id for p in g.of("bar_magnet")), None)
        if mag:
            ops.append({"op": "show", "what": "field", "on": mag})
    for m in ms:
        if m.kind == "switch" and m.ids:
            st = _SWITCH.search(text[m.end:m.end + 20]) or _SWITCH.search(text[max(0, m.start - 12):m.start])
            if st:
                for i in m.ids:
                    for o in ops:
                        if o.get("id") == i:
                            o.setdefault("attr", {})["state"] = "closed" if st.group(1).lower() in ("closed", "close", "on") else "open"
    _circuit(text, ms, ops, ids, g)
    _givens(text, ms, ops, g)
    _quantities(text, ops, g, d)
    d.ops = ops
    d.title = title_for(text, ms)
    return d


def _row(kind: str) -> dict:
    return P.kind(kind) or {}


def _inside_label(text: str, things: list[Mention], ops: list[dict], g: Graph) -> None:
    """"If a square was inside C3": the shape said before goes inside the shape labelled C3 (open or in this line)."""
    labels = {p.label: p.id for p in g.parts.values() if _row(p.kind).get("domain") == "shape" and p.label}
    labels.update({o["label"]: o["id"] for o in ops if o.get("op") == "part" and o.get("label")
                   and _row(o["kind"]).get("domain") == "shape"})
    found = [(m.start(), "beside" if m.group(1).lower() in ("outside", "beside", "next to") else "inside",
              labels.get(m.group(2)), None) for m in _INSIDE_LABEL.finditer(text)]
    for m in _HAS_INSIDE.finditer(text):  # "C1 has a pentagon inside it": the guest is the shape after the label
        guest = next((t for t in things if t.start >= m.start(2) and t.ids
                      and _row(t.kind).get("domain") == "shape"), None)
        found.append((m.start(), "inside", labels.get(m.group(1)), guest))
    for pos, rel, host, guest in found:
        guest = guest or next((t for t in reversed(things) if t.start < pos and t.ids
                               and _row(t.kind).get("domain") == "shape" and host not in t.ids), None)
        if host is None or guest is None or host in guest.ids:
            continue
        for i in guest.ids:
            if g.rels.get(i) != (rel, host) and not any(o.get("op") == "place" and o.get("a") == i for o in ops):
                ops.append({"op": "place", "a": i, "rel": rel, "b": host})


def concept_mishear(text: str) -> Optional[str]:
    """"Imagine a laptop of sodium" -> "Imagine an atom of sodium" (test36): an unknown noun before "of <element>"
    is a mishear of "atom" (the element is the concept said); "a box on an ink-like plane" -> "... an inclined
    plane" (test37); None when the line has no such word."""
    p = _PLANE.search(text)
    if p and p.group(1).lower() not in ("inclined", "the", "a", "an", "flat", "plane", "smooth", "rough", "horizontal",
                                        "vertical", "same", "this", "that", "air", "x", "y", "xy", "cartesian") \
            and SequenceMatcher(None, p.group(1).lower().replace("-", ""), "inclined").ratio() >= 0.6:
        text = text[:p.start()] + "inclined plane" + text[p.end():]
        text = re.sub(r"\ba(\s+inclined plane)", r"an\1", text)
        return concept_mishear(text) or text
    m = _OF_ELEMENT.search(text)
    if m is None:
        return None
    noun, el = m.group(1).lower(), m.group(2)
    if noun in _OF_OK or noun == "atom" or P.words().get(noun) or P.words().get(noun.rstrip("s")):
        return None
    if SequenceMatcher(None, noun, "atom").ratio() < 0.55:  # must sound like "atom" ("laptop" 0.6, "tank" 0.25)
        return None
    if not (P.element(el) or P.element(el.lower())):
        return None
    return text[:m.start()] + f"an atom of {el}" + text[m.end():]


def _chem_label(row: dict, word: str, text: str) -> str:
    """The table's formula when the teacher said it ("HCL" -> HCl), else the said words."""
    return row["show"] if row["show"].lower() in text.lower() else word


def _head(word: str) -> str:
    """The noun without its describing words ("hanging mass" -> "mass")."""
    return word.lower().split()[-1] if word.strip() else ""


def _fresh(text: str, m: Mention) -> bool:
    """A cue naming a thing anew ("imagine a beaker") rather than the one there ("in the beaker")."""
    head = text[max(0, m.start - 30):m.start].lower()
    return bool(re.search(r"\b(?:a|an|another|new|second)\s+(?:\w+\s+)?$", head))


def _hang(a: Mention, b: Mention, between: str) -> Optional[tuple[str, Mention, Mention]]:
    ea, eb = "end" in _row(a.kind).get("anchors", {}), "end" in _row(b.kind).get("anchors", {})
    if eb and not ea:
        return ("hang_from", a, b)
    if ea and not eb:
        return ("hang_from", b, a)
    if ea and eb:  # a spring from a support / a pulley: the lower one hangs ("a spring hanging from the ceiling")
        return ("hang_from", a, b) if re.search(r"\bfrom\b|\bto\b", between) else ("hang_from", b, a)
    return None


def _supports(ops: list[dict], ms: list[Mention], g: Graph, add: Any) -> None:
    """A spring or a pulley something hangs from needs a support (drawn, never labelled)."""
    hung = {o["b"] for o in ops if o.get("op") == "place" and o["rel"] == "hang_from"} | {
        b for a, (r, b) in g.rels.items() if r == "hang_from"}
    placed = {o["a"] for o in ops if o.get("op") == "place"} | set(g.rels)
    sup = next((p.id for p in g.of("support")), None) or next(
        (o["id"] for o in ops if o.get("op") == "part" and o["kind"] == "support"), None)
    for m in ms:
        for i in m.ids:
            if m.kind in ("spring", "pulley") and i not in placed and (i in hung or m.kind == "pulley"):
                sup = sup or add("support", implied=True)
                ops.append({"op": "place", "a": i, "rel": "hang_from", "b": sup})


def _circuit(text: str, ms: list[Mention], ops: list[dict], ids: _Ids, g: Graph) -> None:
    """K1: one loop. "N resistors in parallel" -> a parallel group (also with no cell: drawn between two terminals);
    the rest in series with it around the cell. New parts said later join the open diagram's loop ("now add two
    resistors in parallel")."""
    new = {o["id"] for o in ops if o.get("op") == "part"}
    two = [m for m in ms if m.ids and _row(m.kind).get("two_port") and set(m.ids) <= new]
    if not two:
        return
    items: list[str] = []
    par = _PARALLEL.search(text)
    for m in two:
        if par and m.kind != "cell" and len(m.ids) > 1 and m.start < par.start():
            gid = ids.new("par")
            ops.append({"op": "group", "id": gid, "mode": "parallel", "items": list(m.ids)})
            items.append(gid)
        else:
            items += m.ids
    loop = next((gid for gid, (mode, _) in g.groups.items() if mode == "series"), None)
    if loop is not None:  # the open loop grows (the group op with the same id replaces its items)
        ops.append({"op": "group", "id": loop, "mode": "series", "items": g.groups[loop][1] + items})
    elif len(items) >= 2 or any(m.kind == "cell" for m in two) or items and items[0].startswith("par"):
        ops.append({"op": "group", "id": ids.new("loop"), "mode": "series", "items": items})


def _givens(text: str, ms: list[Mention], ops: list[dict], g: Graph) -> None:
    from copilot.stage.validate import quoted_numbers
    inc = next((m.ids[0] for m in ms if m.kind == "incline" and m.ids), None) or next((p.id for p in g.of("incline")), None)
    for m in _ANGLE.finditer(text):
        nums = quoted_numbers(m.group(0))
        if nums and inc:
            ops.append({"op": "given", "sym": "theta", "v": nums[0][0], "u": "deg", "q": m.group(0).strip(), "on": inc})
            break  # a body's mass is a `qty` now (F-019 §2, `_quantities`)


_STACK = re.compile(r"\bone\s+(?:on\s+top\s+of|above|over|upon)\s+(?:the\s+other|another)\b|\bon\s+top\s+of\s+"
                    r"(?:each\s+other|one\s+another)\b|\bstacked\b|\bplaced\s+on\s+(?:each\s+other|one\s+another)\b",
                    re.IGNORECASE)
_QUANT = re.compile(r"^\s*,?\s*(?:of|with\s+(?:a\s+)?mass\s+of|weighing|of\s+mass)\s+[\w.]+(?:\s+point\s+\w+)?\s*"
                    r"(?:kg|kilograms?|kilos?|grams?|g)\b\s*,?", re.IGNORECASE)
_ROPE = re.compile(r"\b(?:rope|string|thread|cord)s?\b|\bconnected\b|\btied\b|\bover\s+(?:a|the)\s+pulley\b",
                   re.IGNORECASE)


def _mechanics(text: str, things: list[Mention], ops: list[dict], g: Graph) -> None:
    """F-019 M1: stacks and ropes over a pulley, which the neighbour relations above do not see."""
    placed = lambda i: [o for o in ops if o.get("op") == "place" and o["a"] == i]  # noqa: E731
    bodies = [i for m in things if m.kind in ("block", "mass") for i in m.ids]
    grounds = [m for m in things if m.kind in ("floor", "incline")]
    st = _STACK.search(text)
    if st and len(bodies) >= 2:
        lo, hi = bodies[0], bodies[1]  # "two blocks, one on top of the other": the second one on the first
        said = next((o for o in ops if o.get("op") == "place" and o["rel"] == "on" and {o["a"], o["b"]} == {lo, hi}),
                    None)
        if said:  # "a small block stacked on a big block": the said order stands
            hi, lo = said["a"], said["b"]
        elif re.search(r"\bstacked\s+(?:on|upon|over)\b", text, re.IGNORECASE):
            hi, lo = bodies[0], bodies[1]
        for o in placed(lo) + placed(hi):
            ops.remove(o)
        ops.append({"op": "place", "a": hi, "rel": "on", "b": lo})
        gr = next((m for m in grounds if re.search(r"\bon\s+(?:a|an|the)?\s*(?:\w+\s+)?$", text[:m.start])), None)
        if gr:
            ops.append({"op": "place", "a": lo, "rel": "on", "b": gr.ids[0]})
    pulley = next((m for m in things if m.kind == "pulley"), None)
    if not (pulley and pulley.ids and _ROPE.search(text)):
        return
    pid = pulley.ids[0]
    on_table = [i for m in things if m.kind in ("block", "mass") for i in m.ids  # either word order
                if any(o["rel"] == "on" and next((t for t in things if o["b"] in t.ids and t.kind == "floor"), None)
                       for o in placed(i))]
    rest = [i for m in things if m.kind in ("block", "mass") for i in m.ids if i not in on_table]
    table = next((m.ids[0] for m in things if m.kind == "floor" and m.ids), None)
    if on_table and table and not placed(pid) and pid not in g.rels:
        ops.append({"op": "place", "a": pid, "rel": "at_edge", "b": table})
        ops.append({"op": "wire", "a": on_table[0], "b": pid})
        for i in rest[:1]:
            for o in placed(i):
                ops.remove(o)
            ops.append({"op": "place", "a": i, "rel": "hang_from", "b": pid})
    elif not on_table:
        for i in [i for i in rest if not placed(i) and i not in g.rels][:2]:  # two masses tied over a pulley (Atwood)
            ops.append({"op": "place", "a": i, "rel": "hang_from", "b": pid})


def _quantities(text: str, ops: list[dict], g: Graph, d: Draft) -> None:
    """The line's quantities on the parts (the open diagram's and this line's): `qty` ops, or unattached."""
    from copilot.diagram import ops as O
    from copilot.diagram.graph import apply
    from copilot.diagram.quantities import attach
    work = g.copy()
    for raw in ops:
        try:
            apply(work, O.parse(raw), "", 0)
        except Exception:  # noqa: BLE001 - the validator reports a bad op; the quantities only need the good ones
            continue
    q, d.unattached = attach(text, work)
    ops += q


def title_for(text: str, ms: list[Mention]) -> str:
    """The diagram's title from what the line names ("Box on an inclined plane", "HCl in a beaker", "Solar system")."""
    if any(m.kind == "system" for m in ms):
        return "Solar system"
    things = [m for m in ms if m.kind != "unknown" or m.ids]
    if not things:
        return ""
    chem = next((m for m in things if m.kind == "chem" and not _POUR.search(text[:m.start])), None)
    box = next((m for m in things if _row(m.kind).get("container")), None) if any(
        m.kind != "chem" for m in things) else None
    if chem and box:
        row = P.chemical(chem.attr["chem"])
        return f"{row['show']} in {_a(box.word)}"
    a = things[0]
    if a.kind == "atom":
        return f"{a.attr['element'].capitalize()} atom" if a.attr.get("element") else "Atom"
    w = a.word if a.n == 1 else f"{_num(a.n)} {a.word}{'' if a.word.endswith('s') else 's'}"
    if a.names:
        w += " " + " and ".join(a.names) if len(a.names) <= 2 else " " + ", ".join(a.names)
    grouped = _PARALLEL.search(text) or _SERIES.search(text)
    if grouped and grouped.start() > a.start:
        w += " " + " ".join(grouped.group(0).lower().split())
    if len(things) > 1:
        b = things[1]
        between = _gap(text[a.end:b.start])
        if _ON.match(between):
            w += f" on {_a(b.word)}"
        elif _HANG.search(text):
            w += f" with {_some(b)}"
        elif re.search(r"\bwith\b", between):
            w += f" with {_some(b)}"
        else:  # a list ("a cell, a bulb and a switch", "a beaker next to a centrifuge")
            names = [_some(m) if m.n > 1 else m.word for m in things[1:4]]
            w += (", " + ", ".join(names[:-1]) if len(names) > 1 else "") + f" and {names[-1]}"
    if _FIELD.search(text) and a.kind == "bar_magnet":
        w += " and its field"
    w = w.strip()
    return (w[:1].upper() + w[1:])[:48]


def _gap(s: str) -> str:
    """The words between two nouns without articles, counts, commas and a said quantity (" on an " -> " on ",
    " of mass 2 kg on a " -> " on ")."""
    s = re.sub(r"\bof\s+(?:mass|weight)\b", " ", s, flags=re.IGNORECASE)
    words = [w for w in re.findall(r"[A-Za-z']+", s) if w.lower() not in COUNT and w.lower() not in _DEF
             and w.lower() not in UNITS and w.lower() != "another"]  # "on top of another box" (test36)
    return " " + " ".join(words) + " "


def _some(m: Mention) -> str:
    return _a(m.word) if m.n == 1 else f"{_num(m.n)} {m.word}{'' if m.word.endswith('s') else 's'}"


def _a(w: str) -> str:
    return ("an " if w[:1].lower() in "aeiou" else "a ") + w


def _num(n: int) -> str:
    return {v: k for k, v in COUNT.items() if k not in ("a", "an", "single", "both", "pair of")}.get(n, str(n))
