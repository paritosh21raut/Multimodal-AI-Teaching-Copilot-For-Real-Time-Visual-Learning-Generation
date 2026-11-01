"""Motion lines on the open diagram (F-019 M5, 0 tokens): "you throw a ball at 10 m/s at 30 degrees", "a stone is
dropped from a height of 20 m", "a car moving at 50 kmph", "another car at 60 kmph in the opposite direction", "rain
falls at 4 m/s and you walk at 3 m/s", "a boat crosses a 100 m wide river", "a stone whirled in a circle of radius
2 m" -> `process` ops (throw | fall | move | circle | cross) and `qty` ops (v, h, t, a, r, d, theta).

    processes  the verb said with the body (the manner: up | horizontal | angle; opposite; short)
    values     speeds, lengths and times by `simulation.values.heard` ("3mps", "50 kmph", "10 meter per second"), an
               acceleration by its own pattern ("2 metres per second squared"); a length is a height, a radius or a
               distance (a river's width) by the words around it; an angle is the launch angle (no incline there)
    attachment the motion noun in the value's clause, else the line's one new body, else "it" (the last part), else
               the one moving body there; else unattached (logged, never guessed)
"""
from __future__ import annotations

import re
from typing import Any, Callable, Optional

from copilot.diagram.graph import Graph
from copilot.diagram.quantities import _CLAUSE, NUM, Said, clause
from copilot.simulation.values import heard, spoken_number

MOVERS = ("ball", "car", "boat", "man")
KINDS = MOVERS + ("river", "rain")
VERBS = ("throw", "fall", "move", "circle", "cross")
_THROW = re.compile(r"\b(?:throw\w*|threw|thrown|project(?:ed|s|ing)?|launch\w*|kick\w*|fired|toss\w*)\b", re.I)
_FALL = re.compile(r"\b(?:drop\w*|fall\w*|fell|released?|let\s+go)\b", re.I)
_MOVE = re.compile(r"\b(?:mov\w*|travel\w*|driv\w*|drove|runs?|running|ran|walk\w*|going|goes|cross\w*|swim\w*|swam|"
                   r"row\w*|accelerat\w*|sail\w*|speed\w*|starts?|velocity|at\s+(?:a\s+)?(?:speed|rate))\b", re.I)
_CIRCLE = re.compile(r"\bin\s+a\s+(?:horizontal\s+|vertical\s+)?circle\b|\bcircular\b|\bwhirl\w*|\brevolv\w*|"
                     r"\bround\s+and\s+round\b|\baround\s+a\s+circle\b", re.I)
_UP = re.compile(r"\b(?:straight\s+up(?:wards?)?|vertically(?:\s+up\w*)?|upwards?|in(?:to)?\s+the\s+air|up\s+in\s+the\s+air)\b", re.I)
_HORIZ = re.compile(r"(?<!the\s)\bhorizontal(?:ly)?\b", re.I)  # not "30 degrees above the horizontal"
_OPP = re.compile(r"\b(?:opposite\s+(?:directions?|ways?|sides?)|towards?\s+each\s+other|head[- ]on|approaching\s+each\s+other)\b", re.I)
_SAME = re.compile(r"\bsame\s+(?:directions?|ways?)\b", re.I)
_SHORT = re.compile(r"\b(?:shortest\s+(?:path|route|distance|way)|directly\s+opposite|exactly\s+opposite|point\s+opposite|"
                    r"straight\s+across)\b", re.I)
_PERSON = re.compile(r"\b(?:(?:a|the)\s+)?(man|person|boy|girl|woman|walker|cyclist|you)\b", re.I)
_WALK = re.compile(r"\b(?:walk\w*|run\w*|ran|jog\w*|cycl\w*|mov\w*|going|goes|travel\w*|speed)\b", re.I)
_ACC = re.compile(rf"(?P<num>{NUM})\s*(?:m\s*/\s*s\s*(?:\^\s*2|²|2\b|squared)|(?:met(?:re|er)s?|m)\s+per\s+second\s+"
                  rf"(?:squared|square|per\s+second)|mps\s*(?:squared?|sq)\b|m/s2\b)", re.I)
_RADIUS = re.compile(r"\b(?:radius|radii|circle|circular|rope|string)\b", re.I)
_WIDTH = re.compile(r"\b(?:wide|width|breadth|across|river)\b", re.I)
_HEIGHT = re.compile(r"\b(?:height|high|tall|from|cliff|tower|building|roof|above|bridge|top\s+of|deep)\b", re.I)
_ORDINAL = (("first", 0), ("second", 1), ("other", 1), ("another", 1))


def moving(text: str) -> bool:
    """The line says a motion: a motion verb or a speed / acceleration."""
    return bool(_THROW.search(text) or _FALL.search(text) or _CIRCLE.search(text) or _MOVE.search(text)
                or _ACC.search(text) or any(h.kind == "speed" for h in heard(text)))


def context(ms: list[Any], g: Graph) -> bool:
    """A river or a boat here: "in still water" is the river's water, no beaker."""
    return any(m.kind in ("river", "boat") for m in ms) or bool(g.of("river") or g.of("boat"))


_TITLES = {"throw": "Throwing a {w}", "fall": "A falling {w}", "circle": "A {w} moving in a circle",
           "cross": "A {w} crossing a river"}


def title(ops: list[dict], g: Graph) -> str:
    """A motion cue's title from its new parts and the motion said ("Throwing a ball", "Walking in the rain")."""
    parts = {**{p.id: (p.kind, p.label) for p in g.parts.values()},
             **{o["id"]: (o["kind"], o.get("label", "")) for o in ops if o.get("op") == "part"}}
    new = [o["id"] for o in ops if o.get("op") == "part"]
    kinds = [parts[i][0] for i in new]
    if "rain" in kinds and "man" in kinds:
        return "Walking in the rain"
    for o in ops:
        if o.get("op") == "process" and o["verb"] in _TITLES and o["target"] in new:
            k, label = parts[o["target"]]
            return _TITLES[o["verb"]].format(w=(label or k).lower())
        if o.get("op") == "process" and o["verb"] == "move" and o["target"] in new:
            k, label = parts[o["target"]]
            return f"{(label or k).capitalize()} moving"
    return ""


def scene(g: Graph) -> list[str]:
    return [p.id for p in g.parts.values() if p.kind in KINDS]


def people(text: str, ms: list[Any], g: Graph) -> Optional[re.Match]:
    """A person who walks / runs in the rain or crosses with the river ("you walk", "a man running"): the man."""
    if not (any(m.kind in ("rain", "river") for m in ms) or g.of("rain") or g.of("river")):
        return None
    for m in _PERSON.finditer(text):
        if _WALK.search(clause(text, m.start(), m.end())):
            return m
    return None


def draft(text: str, ms: list[Any], ops: list[dict], g: Graph, d: Any, add: Callable[..., str]) -> None:
    """The motion ops of the line (ms: its mentions with their ids; g: the open diagram before the line)."""
    from copilot.diagram.fastpath import Mention
    line = [m for m in ms if m.kind in KINDS and m.ids]
    pm = people(text, ms, g)
    if pm is not None:
        man = next((p.id for p in g.of("man")), None)
        if man is None:
            man = add("man", pm.group(1), "said")
            d.kinds.append("man")
        mm = Mention(pm.start(1), pm.end(1), "man", pm.group(1).lower(), ids=[man])
        line.append(mm)
        line.sort(key=lambda x: x.start)
    if not line and not scene(g):
        return
    _ordinals(text, line, g)
    incline = bool(g.of("incline")) or any(m.kind == "incline" for m in ms)  # review: "a ball down an incline of 30°"
    movers_line = [m for m in line if m.kind in MOVERS]
    have = {**{p.id: p.kind for p in g.parts.values() if p.kind in KINDS},
            **{i: m.kind for m in line for i in m.ids}}
    # "a stone whirled in a circle of radius 2 m": the circle is the path, not a circle part
    circ = _CIRCLE.search(text)
    if circ and any(k in ("ball", "car") for k in have.values()):
        for m in [m for m in ms if m.kind == "circle" and set(m.ids) <= set(d.new)]:
            for i in m.ids:
                ops[:] = [o for o in ops if o.get("id") != i and o.get("a") != i and o.get("b") != i]
                d.new.remove(i)
            if "circle" in d.kinds:
                d.kinds.remove("circle")
            m.ids = []

    def proc(verb: str, target: str, manner: Optional[str] = None) -> None:
        old = next((p for p in g.processes if p["verb"] == verb and p["target"] == target), None)
        if old is not None and (manner is None or old.get("manner") == manner):
            return  # said again: kept (a later line with no way said does not undo "straight up")
        ops.append({"op": "process", "verb": verb, "target": target, **({"manner": manner} if manner else {})})

    targets = [i for m in movers_line for i in m.ids] or [i for i, k in have.items() if k in MOVERS][-1:]
    for t in targets:
        k = have[t]
        moving = {p["verb"] for p in g.processes if p["target"] == t}
        if circ and k in ("ball", "car"):
            proc("circle", t)
        elif k == "ball" and _THROW.search(text):
            ang = any(h.kind == "angle" for h in heard(text)) and not incline
            proc("throw", t, "horizontal" if _HORIZ.search(text) else "up" if _UP.search(text) else
                 "angle" if ang else None)
        elif k == "ball" and _FALL.search(text):
            proc("fall", t)
        elif k == "boat" and (any(x == "river" for x in have.values())):
            if _MOVE.search(text) or _SHORT.search(text) or any(h.kind == "speed" for h in heard(text)):
                proc("cross", t, "short" if _SHORT.search(text) else None)
        elif moving - {"move"}:
            continue  # "with the speed of 3 mps" after "throw a ball in the air": still the throw
        elif k in ("car", "man", "boat", "ball") and (_MOVE.search(text) or any(h.kind == "speed" for h in heard(text))):
            cars = [i for i, kk in have.items() if kk == k]
            opp = bool(_OPP.search(text)) and len(cars) > 1 and t == cars[-1]
            proc("move", t, "opposite" if opp else "same" if _SAME.search(text) and len(cars) > 1 else None)
    _values(text, line, ops, g, d, have, incline)


# ---- values ---------------------------------------------------------------------------------------------------------
def found(text: str, theta: bool) -> list[Said]:
    """The line's motion values in the order said (theta: an angle is a launch angle here)."""
    out: list[Said] = []
    taken: list[tuple[int, int]] = []

    def put(s: Said) -> None:
        if not any(s.start < b and a < s.end for a, b in taken):
            taken.append((s.start, s.end))
            out.append(s)

    for m in _ACC.finditer(text):
        v = spoken_number(m.group("num"))
        if v is not None:
            put(Said("a", v, m.group(0).strip(), m.start(), m.end()))
    for h in heard(text):
        if h.start < 0:
            continue
        i = text.find(h.said, max(0, h.start - 2))
        if i < 0:
            continue
        c = clause(text, i, i + len(h.said))
        if h.kind == "speed":
            kmh = bool(re.search(r"km|kilomet|kph|kmph", h.said, re.I))
            put(Said("v", h.value, h.said, i, i + len(h.said), note="km/h" if kmh else ""))
        elif h.kind == "time":
            put(Said("t", h.value, h.said, i, i + len(h.said)))
        elif h.kind == "length":
            high = _HEIGHT.search(c) and not re.search(r"\bwide|width\b", c, re.I) and (
                theta or re.search(r"\b(?:height|high|tall|cliff|tower|building|roof)\b", c, re.I))
            sym = "r" if _RADIUS.search(c) else "h" if high else "d"
            put(Said(sym, h.value, h.said, i, i + len(h.said)))
        elif h.kind == "angle" and theta:
            put(Said("theta", h.value, h.said, i, i + len(h.said)))
    out.sort(key=lambda s: s.start)
    return out


def _ordinal_rx(kind: str) -> re.Pattern:
    from copilot.diagram import parts as P
    words = [w for w, k in P.words().items() if k == kind] + (["man", "person", "you", "boy", "girl", "walker"]
                                                               if kind == "man" else [])
    return re.compile(r"\b(?:(first|second|other|another)\s+)?(?:" + "|".join(map(re.escape, words)) + r")s?\b", re.I)


def _ordinals(text: str, line: list[Any], g: Graph) -> None:
    """Review: "the second car moves at 30 m/s" is the second car there (the noun alone named the first one)."""
    for kind in ("car", "ball", "boat"):
        olds = [p.id for p in g.of(kind)]
        for m in _ordinal_rx(kind).finditer(text):
            o = (m.group(1) or "").lower()
            idx = dict(_ORDINAL).get(o) if o and o != "another" else None
            if idx is None or idx >= len(olds):
                continue
            for x in line:
                if x.kind == kind and m.start() <= x.start < m.end() and x.ids and x.ids[0] in olds:
                    x.ids = [olds[idx]]


def _names(text: str, g: Graph, line: list[Any]) -> list[tuple[int, str]]:
    """(position, id) of every motion body the text names: this line's mentions, and the open ones by their noun."""
    hits = [(m.start, i) for m in line for i in m.ids[:1]]
    for kind in KINDS:
        olds = [p.id for p in g.of(kind)]
        if not olds:
            continue
        for m in _ordinal_rx(kind).finditer(text):
            if any(abs(m.start() - p) < 4 or m.start() <= p < m.end() for p, _ in hits):
                continue
            o = (m.group(1) or "").lower()
            idx = dict(_ORDINAL).get(o) if o else None
            if idx is not None and idx < len(olds) and o != "another":
                hits.append((m.start(), olds[idx]))
            elif len(olds) == 1 and o != "another":
                hits.append((m.start(), olds[0]))
    return sorted(hits)


def _values(text: str, line: list[Any], ops: list[dict], g: Graph, d: Any, have: dict[str, str],
            incline: bool = False) -> None:
    balls = [i for i, k in have.items() if k == "ball"]
    said = found(text, theta=bool(balls) and not incline)
    if not said:
        return
    if any(s.sym == "theta" for s in said):  # the mechanics reader kept the angle unattached (no incline)
        d.unattached = [u for u in d.unattached if u[0] != "theta"]
    names = _names(text, g, line)
    new = [i for m in line for i in m.ids if i in d.new and have.get(i) in MOVERS]
    pron = [m.start() for m in re.finditer(r"\b(?:it|its)\b", text, re.I)]
    movers = [i for i, k in have.items() if k in MOVERS]
    for s in said:
        on = _target(s, text, names, new, pron, g, have, movers)
        if on is None:
            d.unattached.append((s.sym, s.q))
            continue
        from copilot.diagram.ops import QSYMS
        ops.append({"op": "qty", "on": on, "sym": s.sym, "v": s.v, "u": QSYMS[s.sym], "q": s.q,
                    **({"note": s.note} if s.note else {})})


def _bounds(t: str, start: int, end: int) -> tuple[int, int]:
    """Where `quantities.clause` cuts the value's clause."""
    a = 0
    for m in _CLAUSE.finditer(t, 0, start):
        a = m.end()
    m = _CLAUSE.search(t, end)
    return a, m.start() if m else len(t)


# a speed said with no noun goes by its verb (only to a part that is there)
_V_BY = (("rain", re.compile(r"\b(?:falls?|falling|drops?|vertically)\b", re.I)),
         ("river", re.compile(r"\b(?:flows?|flowing|current)\b", re.I)),
         ("man", re.compile(r"\b(?:walks?|walking|runs?|running|jogs?|jogging)\b", re.I)))


def _target(s: Said, text: str, names: list[tuple[int, str]], new: list[str], pron: list[int], g: Graph,
            have: dict[str, str], movers: list[str]) -> Optional[str]:
    if s.sym == "theta":
        b = [i for i, k in have.items() if k == "ball"]
        return b[0] if len(b) == 1 else None
    if s.sym == "d" and any(k == "river" for k in have.values()) and _WIDTH.search(clause(text, s.start, s.end)):
        return next(i for i, k in have.items() if k == "river")
    c0, c1 = _bounds(text, s.start, s.end)
    near = [(p, i) for p, i in names if c0 <= p < c1]
    before = [i for p, i in near if p < s.start]
    after = [i for p, i in near if p >= s.end]
    if s.sym in ("h", "r", "a", "t") or s.sym == "d" and not any(k == "river" for k in have.values()):
        near_movers = [i for i in before[::-1] + after if have.get(i) in MOVERS]
        if near_movers:
            return near_movers[0]
    elif before or after:
        return (before[-1:] or after[:1])[0]
    if s.sym == "v":  # test49: "the rays (rain) fall vertically at 4 mps" with no noun went onto the walker
        c = text[c0:c1]
        for kind, rx in _V_BY:
            ids = [i for i, k in have.items() if k == kind]
            if len(ids) == 1 and rx.search(c):
                return ids[0]
    if len(new) == 1:
        return new[0]
    if any(c0 <= p < c1 for p in pron) and g.last in have:
        return g.last
    if s.sym == "v" and (len(movers) > 1 or any(k in ("rain", "river") for k in have.values())):
        return None  # more than one thing takes a speed: asked, never guessed
    return movers[0] if len(movers) == 1 else None
