"""Checks every SceneOp before it touches a scene (F-015 section 3). A bad op is refused with a reason (logged as
scene.rejected by the controller), never repaired by guessing:

- refs: an id must exist (or be new for `add`); kinds, relations and behaviours come from closed lists.
- numbers: each must match a quantity heard in the scene's lines (simulation.values: digits and spoken numbers);
  otherwise it is kept as `default`: drawn, never printed. "double it" of a known value is `computed`.
- units: each prop has a unit family; an unknown unit or an out-of-range value refuses that prop (logged).
- labels: a name or label prints only words the teacher said (in the lines or already in the scene).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Optional

from copilot.scene import safety
from copilot.scene.spec import (
    BEHAVIORS, BODY_KINDS, CANVAS_KINDS, CANVAS_RELATIONS, DIRS, EMITS, GEOMETRY_KINDS, ID_PATTERN, KINDS, KNOWN,
    MAX_ENTITIES, MAX_PARTS, OPS, RELATIONS, RELATIVE_KINDS, SIZES, SOLID_KINDS, Entity, Label, Q, SceneOp, SceneSpec, Source,
)
from copilot.simulation.values import NUM, heard, spoken_number

# family -> unit -> factor to the family's base unit (m, m/s, m/s², degrees, s, kg, plain number)
UNITS: dict[str, dict[str, float]] = {
    "length": {"": 1.0, "m": 1.0, "cm": 0.01, "mm": 0.001, "km": 1000.0, "units": 1.0},
    "speed": {"m/s": 1.0, "km/h": 1 / 3.6, "cm/s": 0.01},
    "acceleration": {"m/s^2": 1.0},
    "angle": {"deg": 1.0, "rad": 180 / math.pi},
    "time": {"s": 1.0, "ms": 0.001, "min": 60.0},
    "mass": {"kg": 1.0, "g": 0.001},
    "count": {"": 1.0},
    "number": {"": 1.0},
}
_ALIASES = {"metre": "m", "metres": "m", "meter": "m", "meters": "m", "centimetres": "cm", "centimeters": "cm",
            "millimetres": "mm", "kilometres": "km", "kilometers": "km", "unit": "units", "u": "units",
            "m/s2": "m/s^2", "m/s²": "m/s^2", "m/s/s": "m/s^2", "ms^-2": "m/s^2", "m s^-2": "m/s^2",
            "kmph": "km/h", "mps": "m/s", "mps2": "m/s^2", "mps^2": "m/s^2", "kph": "km/h", "km/hr": "km/h", "°": "deg", "degree": "deg", "degrees": "deg",
            "sec": "s", "secs": "s", "seconds": "s", "second": "s", "kilogram": "kg", "kilograms": "kg",
            "gram": "g", "grams": "g", "radians": "rad"}
PROPS: dict[str, str] = {
    "side": "length", "width": "length", "height": "length", "radius": "length", "diameter": "length",
    "length": "length", "base": "length", "sides": "count", "x": "number", "y": "number", "xmin": "number",
    "xmax": "number", "speed": "speed", "acceleration": "acceleration", "angle": "angle", "time": "time",
    "mass": "mass", "start": "length", "gap": "length",
}
# base-unit ranges: a number outside is refused (a mishearing or a model slip), never clipped
RANGES: dict[str, tuple[float, float]] = {
    "length": (1e-6, 1e7), "speed": (0.0, 1e4), "acceleration": (-1e3, 1e3), "angle": (0.0, 360.0),
    "time": (1e-3, 3600.0), "mass": (1e-6, 1e6), "count": (3, 12), "number": (-1e6, 1e6),
}
_RELATIVE = ((re.compile(r"\b(?:double|twice|two times)\b", re.I), 2.0),
             (re.compile(r"\b(?:triple|three times|thrice)\b", re.I), 3.0),
             (re.compile(r"\b(?:half|halve[sd]?)\b", re.I), 0.5))
_NUM_RX = re.compile(NUM, re.IGNORECASE)
_EXPR_NUM = re.compile(r"\d+(?:\.\d+)?")
_ID = re.compile(ID_PATTERN)
CLOSED = ("square", "rectangle", "circle", "triangle", "polygon")
BESIDE = ("left_of", "right_of", "above", "below")
MOTION_PROPS = ("speed", "acceleration")  # a body's (a shape or a point given a speed is a model slip: refused)
MOVERS = BODY_KINDS + RELATIVE_KINDS + ("thing",)  # what may have a speed and a direction (a river flows, rain falls)
# what may act (a behaviour's target) and be placed by a canvas relation; a solid too (test32: "inside the cuboid is a
# sphere", "a cone on top of the cylinder": the canvas draws it as a shaded solid)
ACTORS = BODY_KINDS + ("thing",) + SOLID_KINDS
SPATIAL = BODY_KINDS + CANVAS_KINDS + SOLID_KINDS  # what a canvas relation places things by
# a thing's said noun: letters, spaces, hyphens, apostrophes (no markup, no digits)
_NOUN_OK = re.compile(r"^[A-Za-z][A-Za-z '\-]{0,39}$")
_OTHER = ("follow", "chase", "orbit", "move_to", "collide")  # actions that need the other entity (`b`)
# a moving thing said as itself: drawn as a body of this kind with the noun's picture (scene.assets), same physics
KIND_ALIAS = {**{k: "car" for k in ("rocket", "train", "boat", "ship", "bus", "truck", "plane", "aeroplane",
                                    "airplane", "bike", "bicycle", "motorbike", "scooter", "tram", "helicopter",
                                    "submarine", "jet", "vehicle")},
              **{k: "particle" for k in ("person", "man", "woman", "boy", "girl", "child", "swimmer", "runner",
                                         "cyclist", "animal", "dog", "cat", "horse", "bird", "fish", "insect")},
              **{k: "ball" for k in ("stone", "rock", "marble", "bullet", "projectile")},
              **{k: "block" for k in ("box", "crate", "brick", "cart", "trolley")}}
_AXIS = {"east": (1, 0), "right": (1, 0), "west": (-1, 0), "left": (-1, 0), "north": (0, 1), "up": (0, 1),
         "south": (0, -1), "down": (0, -1)}
# the unit words after a said number -> its family ("radius 5 metres" is not a side of 5 cm)
_FAMILY_AFTER = [(f, re.compile(rx, re.IGNORECASE)) for f, rx in (
    # "mps square", "mps2" and a speech recogniser's "mpsw" / "mpsp" (a letter stuck to "mps") are m/s²
    ("acceleration", r"\s*(?:m/s(?:\^?2|²|\s+squared|\s+per\s+second)|m\s?s-2|"
                     r"mps(?:\s*(?:squared?|sq)\b|\^?2|²|[a-z]\b)|(?:metres?|meters?) per second (?:squared|per second))"),
    ("speed", r"\s*(?:m/s|km/h|kmph|kph|km/hr|mps\b|cm/s|"
              r"(?:(?:centi|kilo)?(?:metres?|meters?)|km) (?:per|an?) (?:second|hour))"),
    ("length", r"\s*(?:cm\b|mm\b|km\b|m\b|(?:centi|milli|kilo)?(?:metres?|meters?)\b|units?\b)"),
    ("angle", r"\s*(?:°|degrees?\b|deg\b|radians?\b)"),
    ("mass", r"\s*(?:kg\b|kilo(?:gram)?s?\b|grams?\b|g\b)"),
    ("time", r"\s*(?:s\b|secs?\b|seconds?\b|ms\b|minutes?\b)"),
)]
_HEARD_FAMILY = {"speed": "speed", "length": "length", "angle": "angle", "mass": "mass", "time": "time"}


@dataclass
class Corpus:
    """What the teacher said during this scene (bounded by the controller): the said-number and label checks."""
    lines: list[str] = field(default_factory=list)
    # every number as said (digits or words) with the unit family of the words after it (None: a bare number)
    numbers: list[tuple[float, Optional[str]]] = field(default_factory=list)
    # values.heard in its slot units, with their family (36 km/h -> 10 m/s, speed)
    converted: list[tuple[float, str]] = field(default_factory=list)
    text: str = ""

    @classmethod
    def of(cls, lines: list[str]) -> "Corpus":
        nums: list[tuple[float, Optional[str]]] = []
        conv: list[tuple[float, str]] = []
        for line in lines:
            for m in _NUM_RX.finditer(line):
                if m.start() > 0 and (line[m.start() - 1].isalpha() or line[m.start() - 1] in "/^"):
                    continue  # a unit's exponent ("mps2", "m/s^2") or a name ("C1") is not a said number
                v = spoken_number(m.group("num"))
                if v is not None:
                    fam = next((f for f, rx in _FAMILY_AFTER if rx.match(line, m.end())), None)
                    nums.append((v, fam))
            conv += [(h.value, _HEARD_FAMILY[h.kind]) for h in heard(line) if h.kind in _HEARD_FAMILY]
        return cls(list(lines), nums, conv, " ".join(lines).lower())


@dataclass
class Checked:
    """A valid op, normalised: numbers as Q with their source; name / label only when said."""
    op: SceneOp
    props: dict[str, Q] = field(default_factory=dict)
    params: dict[str, Q] = field(default_factory=dict)
    name: str = ""
    label: Optional[Label] = None
    expr_shown: str = ""   # a curve's expression as printed ("" = a number in it was not said)
    notes: list[str] = field(default_factory=list)  # props refused (the op itself applies)
    noun: str = ""         # a body's noun for its picture (the model's word or the kind it said: "rocket")
    dir: str = ""
    toward: str = ""
    size: str = ""         # F-016 a thing's size word
    text: str = ""         # F-016 a behaviour's text (emit: what; transform_into: the noun it becomes)


def _close(a: float, b: float) -> bool:
    return math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-9)


def said_words(text: str, corpus: Corpus, scene: Optional[SceneSpec] = None) -> bool:
    """Every word of `text` was said (a plural / singular form counts) or is already a name in the scene. A label of
    one or two letters ("A", "AB") must be said as one: "point A", "called AB" (the article "a" is not a label)."""
    t = text.strip()
    if 0 < len(t) <= 2:
        said = " ".join(corpus.lines)
        if re.fullmatch(r"[A-Z][A-Z0-9]", t):  # "C1", "AB": said as a token, as written (not a unit like "m2")
            return bool(re.search(rf"(?<![\w']){re.escape(t)}(?![\w'])", said))
        return bool(re.search(rf"\b(?:point|vertex|corner|side|line|called|named|letter|"
                              rf"(?:label(?:led)?|mark(?:ed)?|call)(?:\s+(?:it|this|that|them))?)\s+"
                              rf"{re.escape(t)}\b", said))
    words = re.findall(r"[a-z0-9']+", text.lower())
    if not words:
        return False
    known = corpus.text + " " + " ".join(e.name.lower() for e in (scene.entities if scene else []))
    return all(re.search(rf"\b{re.escape(w)}(?:e?s)?\b", known) or (w.endswith("s") and re.search(
        rf"\b{re.escape(w[:-1])}\b", known)) for w in words)


def number_source(v: float, corpus: Corpus, current: Optional[Q] = None, fam: Optional[str] = None,
                  base: Optional[float] = None) -> Source:
    """said: the number was heard bare or with a unit of the prop's family (its sign may come from words: "slows
    down at 2"); computed: a heard value of that family in another unit (compared in base units), or "double it" of a
    known value; else default (drawn, never printed)."""
    if any(_close(abs(v), abs(n)) and (f is None or fam is None or f == fam or fam in ("number", "count"))
           for n, f in corpus.numbers):
        return "said"
    b = v if base is None else base
    if any(_close(abs(b), abs(n)) and f == fam for n, f in corpus.converted):
        return "computed"
    if current is not None and current.source in KNOWN:
        last = corpus.lines[-1] if corpus.lines else ""
        for rx, k in _RELATIVE:
            if rx.search(last) and _close(v, current.value * k):
                return "computed"
    return "default"


def _unit(raw: Any) -> str:
    u = str(raw or "").strip()
    return _ALIASES.get(u.lower(), _ALIASES.get(u, u))


def to_q(key: str, raw: Any, corpus: Corpus, current: Optional[Q] = None) -> tuple[Optional[Q], str]:
    """One prop: (Q, "") or (None, why refused)."""
    fam = PROPS.get(key)
    if fam is None:
        return None, f"unknown prop {key!r}"
    if isinstance(raw, list):
        if not raw or len(raw) > 2:
            return None, f"{key}: bad value {raw!r}"
        val, unit = raw[0], _unit(raw[1] if len(raw) > 1 else "")
    else:
        val, unit = raw, ""
    if isinstance(val, bool) or not isinstance(val, (int, float)) or not math.isfinite(float(val)):
        return None, f"{key}: not a number {val!r}"
    if unit not in UNITS[fam]:
        if fam in ("speed", "acceleration", "angle", "time", "mass") and unit == "":
            unit = next(iter(UNITS[fam]))  # "speed 3" in a motion scene: its base unit
        else:
            return None, f"{key}: unit {unit!r} is not a {fam} unit"
    base = float(val) * UNITS[fam][unit]
    lo, hi = RANGES[fam]
    if not lo <= base <= hi or (fam == "count" and base != int(base)):
        return None, f"{key}: {val} {unit} out of range"
    if current is not None and current.unit == unit and _close(current.value, float(val)):
        return current, ""  # restated: keeps its source
    src = number_source(float(val), corpus, current if current is not None and current.unit == unit else None,
                        fam, base)
    return Q(value=float(val), unit=unit, source=src), ""


def expr_numbers_said(expr: str, corpus: Corpus) -> bool:
    """A curve's expression is printed only when each of its numbers was said ("x squared" says the 2)."""
    for m in _EXPR_NUM.finditer(expr):
        v = float(m.group(0))
        if any(_close(v, n) for n, _ in corpus.numbers):
            continue
        if v == 2 and re.search(r"\bsquare[ds]?\b", corpus.text) or v == 3 and re.search(r"\bcube[ds]?\b",
                                                                                          corpus.text):
            continue
        return False
    return True


_PAIRS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {  # relation -> (kinds of a, kinds of b)
    "inscribed_in": (CLOSED, CLOSED), "around": (CLOSED, CLOSED),
    "diagonal_of": (("segment",), ("square", "rectangle", "polygon")),
    "radius_of": (("segment",), ("circle",)), "diameter_of": (("segment",), ("circle",)),
    "tangent_to": (("segment",), ("circle",)), "bisector_of": (("segment",), ("segment",)),
    "midpoint_of": (("point",), ("segment",)),
}


def canvas_solids(kind: str, a: Entity, b: Entity) -> bool:
    """A solid on / inside / under another solid or a thing: a canvas relation (the geometry world only puts solids
    side by side)."""
    return (a.kind in SOLID_KINDS or b.kind in SOLID_KINDS) and kind not in BESIDE and a.kind in ACTORS \
        and b.kind in SPATIAL


def check(op: SceneOp, scene: SceneSpec, corpus: Corpus) -> tuple[Optional[Checked], str]:
    """(Checked, "") or (None, why the op is refused)."""
    if op.op not in OPS:
        return None, f"unknown op {op.op!r}"
    alias = ""
    if op.op == "add" and op.kind in KIND_ALIAS:  # "rocket" is a car body with a rocket's picture
        alias, op = op.kind, op.model_copy(update={"kind": KIND_ALIAS[op.kind]})
    ent = scene.get(op.id) if op.id else None
    if op.op == "unsafe":  # the model refuses the lines: the controller drops this call's ops (nothing drawn)
        return Checked(op), ""
    if op.op == "frame":
        f = scene.get(op.id) if op.id else None
        if op.id and (f is None or f.kind not in BODY_KINDS + ("river",)):
            return None, f"frame: {op.id!r} is not a body or a river"
        return Checked(op), ""
    if op.op == "add":
        if not _ID.match(op.id or ""):
            return None, f"bad id {op.id!r}"
        if op.kind not in KINDS:
            return None, f"kind {op.kind!r} is not drawn (yet)"
        if ent is not None and ent.kind != op.kind:
            return None, f"id {op.id} is already a {ent.kind}"
        if ent is None and len(scene.entities) >= MAX_ENTITIES:
            return None, "the scene is full"
        if op.kind in CANVAS_KINDS:
            noun = (op.name or "").strip()
            if not _NOUN_OK.match(noun):
                return None, f"a {op.kind} needs its said noun as name (letters only), not {op.name!r}"
            if safety.blocked(noun):
                return None, f"blocked noun {noun!r} (scene.safety)"
        if op.kind == "curve":
            from copilot.scene.worlds.plot import parse
            if not op.expr:
                return None, "a curve needs expr"
            try:
                parse(op.expr)
            except ValueError as err:
                return None, f"expr refused: {err}"
    elif op.op in ("set", "remove", "label"):
        if ent is None:
            return None, f"{op.op}: no entity {op.id!r}"
        if op.op == "set" and op.name and ent.kind in CANVAS_KINDS and (not _NOUN_OK.match(op.name.strip())
                                                                        or safety.blocked(op.name)):
            return None, f"set: bad or blocked noun {op.name!r}"
        if op.op == "set" and op.expr:
            from copilot.scene.worlds.plot import parse
            try:
                parse(op.expr)
            except ValueError as err:
                return None, f"expr refused: {err}"
    elif op.op == "relate":
        a, b = scene.get(op.a), scene.get(op.b)
        if op.kind not in RELATIONS:
            return None, f"unknown relation {op.kind!r}"
        if a is None or b is None or a.id == b.id:
            return None, f"relate: bad refs {op.a!r}, {op.b!r}"
        pair = _PAIRS.get(op.kind)
        if op.kind == "inscribed_in" and pair is not None and a.kind in SOLID_KINDS and b.kind in SOLID_KINDS \
                and (a.kind not in pair[0] or b.kind not in pair[1]):
            op = op.model_copy(update={"kind": "inside"})  # C1 live: "a cuboid with a sphere inside it" came as this
            pair = None
        if pair is not None and (a.kind not in pair[0] or b.kind not in pair[1]):
            return None, f"{op.kind}: not for a {a.kind} and a {b.kind}"
        if a.kind in CANVAS_KINDS or b.kind in CANVAS_KINDS or op.kind in CANVAS_RELATIONS or canvas_solids(op.kind, a, b):
            # F-016: things, bodies and the place, never a drawn shape
            if a.kind not in ACTORS or b.kind not in SPATIAL:
                return None, f"{op.kind}: not for a {a.kind} and a {b.kind} (things, bodies and the place)"
            if b.kind == "place" and op.kind not in ("at", "inside", "under", "on", "on_top_of", "above", "below"):
                return None, f"{op.kind}: not for a place (at, inside, under, on, above, below)"
            if op.kind == "part_of":
                if a.kind != "thing" or b.kind != "thing":
                    return None, "part_of: a thing's part is a thing"
                if sum(1 for r in scene.relations if r.kind == "part_of" and r.b == b.id and r.a != a.id) >= MAX_PARTS:
                    return None, f"part_of: {b.id} has {MAX_PARTS} parts already"
            if op.kind == "between":
                c = scene.get(op.c)
                if c is None or c.id in (a.id, b.id) or c.kind not in ACTORS:
                    return None, f"between: needs a second thing c, not {op.c!r}"
        else:
            if (a.kind in SOLID_KINDS or b.kind in SOLID_KINDS) and op.kind not in BESIDE:
                return None, f"{op.kind}: not for a solid (only beside another shape)"
            if op.kind == "on" and a.kind != "point" and not (a.kind in BODY_KINDS and b.kind in BODY_KINDS):
                return None, "on: only a point lies on something"
        chain = {r.a: r.b for r in scene.relations if r.a != a.id}  # a's own relation is replaced by this one
        cur, seen = b.id, set()
        while cur in chain and cur not in seen:
            seen.add(cur)
            cur = chain[cur]
        if cur == a.id:
            return None, f"relate: {a.id} would be placed by itself (a cycle through {b.id})"
    elif op.op == "behave":
        t = scene.get(op.target)
        if op.kind not in BEHAVIORS:
            return None, f"unknown behaviour {op.kind!r}"
        if t is None or t.kind not in ACTORS:
            return None, f"behave: {op.target!r} is not a body or a thing"
        if op.kind in ("cross", "cross_straight") and (t.kind not in BODY_KINDS
                                                       or not any(x.kind == "river" for x in scene.entities)):
            return None, f"{op.kind}: there is no river to cross"
        if op.kind in _OTHER:
            o = scene.get(op.b)
            if o is None or o.id == t.id or o.kind not in ACTORS:
                return None, f"{op.kind}: needs another thing b, not {op.b!r}"
        if op.kind == "emit" and op.text not in EMITS:
            return None, f"emit: {op.text!r} is not one of {' '.join(EMITS)}"
        if op.kind == "transform_into":
            noun = op.text.strip()
            if not _NOUN_OK.match(noun) or safety.blocked(noun):
                return None, f"transform_into: bad or blocked noun {op.text!r}"
    elif op.op == "focus":  # no ids: zoom out (the whole scene)
        if any(scene.get(i) is None for i in op.ids):
            return None, f"focus: bad refs {op.ids!r}"
    out = Checked(op)
    kind = op.kind if op.op == "add" else ent.kind if ent is not None else ""
    for key, raw in op.props.items():
        if key in MOTION_PROPS and kind not in MOVERS or key == "acceleration" and kind in RELATIVE_KINDS:
            out.notes.append(f"{key}: a {kind} does not move (only ball block car particle)")
            continue
        q, why = to_q(key, raw, corpus, ent.props.get(key) if ent is not None else None)
        if q is None:
            out.notes.append(why)
        else:
            out.props[key] = q
    beh = next((x for x in scene.behaviors if x.target == op.target and x.kind == op.kind), None)
    for key, raw in op.params.items():
        q, why = to_q(key, raw, corpus, beh.params.get(key) if beh is not None else None)
        if q is None:
            out.notes.append(why)
        else:
            out.params[key] = q
    if op.dir or op.toward:
        if kind not in MOVERS:
            out.notes.append(f"dir: a {kind} does not move")
        elif op.dir not in DIRS or op.toward and (op.toward not in DIRS or _AXIS[op.toward][0] * _AXIS[op.dir][0]
                                                  + _AXIS[op.toward][1] * _AXIS[op.dir][1] != 0):
            out.notes.append(f"dir {op.dir!r} toward {op.toward!r} refused (closed list; toward is at right angles)")
        else:
            out.dir, out.toward = op.dir, op.toward
    if kind in BODY_KINDS + CANVAS_KINDS and (op.op == "add" or op.name):
        out.noun = (op.name.strip() or alias)[:40]
    if op.size:
        if kind == "thing" and op.size in SIZES:
            out.size = op.size
        else:
            out.notes.append(f"size {op.size!r} refused (a thing's: {' '.join(SIZES)})")
    if op.op == "behave" and op.kind in ("emit", "transform_into"):
        out.text = op.text.strip()[:40]
    if op.name:
        out.name = op.name.strip()[:40] if said_words(op.name, corpus, scene) else ""
        if not out.name:
            out.notes.append(f"name {op.name!r} not said: not printed")
    if op.expr:
        from copilot.scene.worlds.plot import pretty
        out.expr_shown = pretty(op.expr) if expr_numbers_said(op.expr, corpus) else ""
    if op.op == "label":
        if not said_words(op.text, corpus, scene):
            return None, f"label {op.text!r} was not said"
        out.label = Label(text=op.text.strip()[:40], source="said")
    word = alias or op.kind
    if op.op == "add" and (op.kind in GEOMETRY_KINDS + RELATIVE_KINDS + ("curve",) or alias) and not op.name \
            and said_words(word, corpus):
        out.name = word  # "imagine a square": the teacher's word is the kind's
    return out, ""
