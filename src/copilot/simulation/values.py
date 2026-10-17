"""Spoken values -> simulation slots (F-014), deterministic, 0 tokens.

Two steps:
1. `heard(line)`: every quantity the line states with a unit, by kind (unit first: N -> force, ° -> angle, kg ->
   mass, V -> voltage, ...), plus μ / g said by name, "smooth" (μ = 0), "rough" and the push direction. Needs no
   template, so the detector can log what it heard.
       mass "5 kg", "five kilograms", "500 grams" · angle "30 degrees" (not "30 degrees Celsius") · force "20 newtons":
       a friction / weight / normal / net force is a result, never an input; a force with no push word is `loose`
       (the push only while a simulation is open) · speed "20 m/s" · length "2 m", "50 cm" · voltage "12 V" ·
       resistance "10 ohms" · current "2 A" · frequency "5 Hz" · time "2 seconds" · mu "mu is 0.2" · g "take g as 10"
2. `resolve(template, line, last, ...)`: those quantities -> the open simulation's slots, and what the units cannot
   say: a value named without a unit ("the pushing force is 50"), a bare number ("make it 30", a line "0.3") for the
   slot changed or mentioned last, relative phrases ("double it", "halve the mass", "increase the angle to 40",
   "reduce it by 5"), a slot only mentioned ("if the coefficient of friction of this surface is ...") becomes the
   last one. Whisper spellings ("co-efficient", "coefficient of fiction", "mew", "2000 Nm" for N) are read only where
   the open simulation makes them unambiguous.

Precision over recall: a value that is not clearly one of these is left out (the teacher can set it in /control).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from copilot.simulation.base import Template

_ONES = {"zero": 0, "nought": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
         "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}
_DIGIT = {**{k: v for k, v in _ONES.items() if v < 10}, "oh": 0, "o": 0}
_W1 = "|".join(sorted(_ONES, key=len, reverse=True))
_W10 = "|".join(_TENS)
_UNDER100 = rf"(?:(?:{_W10})(?:[\s-](?:{_W1}))?|{_W1})"
_UNDER1000 = rf"(?:(?:{_W1}|a)\s+hundred(?:\s+(?:and\s+)?{_UNDER100})?|{_UNDER100})"
# a spelled number: "five", "thirty-five", "two hundred and fifty", "two thousand", "zero point two", "point five"
_SPELLED = (rf"(?:(?:{_UNDER1000}|a)\s+thousand(?:\s+(?:and\s+)?{_UNDER1000})?|{_UNDER1000})"
            rf"(?:\s+point(?:\s+(?:{'|'.join(_DIGIT)}))+)?|point(?:\s+(?:{'|'.join(_DIGIT)}))+")
NUM = rf"(?P<num>-?\d+(?:,\d{{3}})*(?:\.\d+)?(?!\.?\d)|-?\.\d+|\b(?:{_SPELLED})\b)"


def spoken_number(s: str) -> Optional[float]:
    """"5" / "0.2" / "1,000" / "thirty-five" / "zero point two" / "two thousand five hundred" -> float, else None."""
    s = s.strip().lower().replace(",", "")
    try:
        return float(s)
    except ValueError:
        pass
    whole, _, frac = s.partition("point")
    total, part = 0.0, 0.0
    seen = False
    for w in whole.replace("-", " ").split():
        if w in ("and", "a"):
            continue
        if w == "hundred":
            part = (part or 1.0) * 100
        elif w == "thousand":
            total += (part or 1.0) * 1000
            part = 0.0
        elif w in _TENS:
            part += _TENS[w]
        elif w in _ONES:
            part += _ONES[w]
        else:
            return None
        seen = True
    total += part
    if frac.strip():
        digits = [_DIGIT.get(w) for w in frac.split()]
        if not digits or any(d is None for d in digits):
            return None
        total += float("0." + "".join(str(d) for d in digits))
        seen = True
    return total if seen else None


@dataclass(frozen=True)
class Heard:
    kind: str           # mass | angle | force | speed | length | voltage | resistance | current | frequency | time |
    #                     mu | g | force_dir | force_mode | rough
    value: float = 0.0  # in the slot's unit (kg, degrees, N, m/s, m, V, Ω, A, Hz, s, -, m/s²)
    said: str = ""      # the words as heard ("five kilograms")
    text: str = ""      # for force_dir: "up" / "down"
    start: int = -1     # where in the line (resolve: the slot named just before it)
    loose: bool = False  # force with no push word ("if it is of 100 N"): the push only with a simulation open
    odd_unit: bool = False  # "Nm" / "Nf" (Whisper's N): a force only with a force context


_AFTER_DIGIT = r"(?<=\d)\s?"
# kind, unit pattern (after the number), factor per unit prefix (lower-cased first letters), "odd" units
_UNIT_SPECS: tuple[tuple[str, str], ...] = (
    ("mass", r"kg\b|kgs\b|kilo(?:gram)?s?\b(?![- ]?(?:ohm|newton|watt|volt|metre|meter|hertz|joule))|grams?\b|gm\b|"
             r"tonnes?\b|tons?\b"),
    ("angle", r"°|degrees?\b|deg\b"),
    ("force", r"(?i:kilo ?newtons?\b|newtons?\b)|(?<=\d)\s?kN\b|(?<=\d)\s?N(?:m|f|F)?\b|(?<=\d)\s?N\.? ?m\b"),
    ("speed", r"m/s\b(?!\s*(?:squared|square|²|2\b))|(?:metres?|meters?) per second\b(?!\s*(?:squared|square|²|per))|"
              r"km/h\b|kmph\b|kilomet(?:re|er)s? per hour\b"),
    ("length", r"(?i:(?:centi|milli|kilo)?(?:metres?|meters?)\b(?!\s*(?:per|/)))|(?<=\d)\s?(?:cm|mm|km)\b(?!\s*/)|"
               r"(?<=\d)\s?m\b(?!\s*/)"),
    ("voltage", r"(?i:(?:kilo)?volts?\b)|(?<=\d)\s?k?V\b"),
    ("resistance", r"(?:kilo[- ]?)?ohms?\b|k?Ω|(?<=\d)\s?k(?=\s*ohm)"),
    ("current", r"(?i:(?:milli)?amp(?:ere)?s?\b)|(?<=\d)\s?m?A\b"),
    ("frequency", r"(?:kilo)?hertz\b|(?<=\d)\s?k?Hz\b"),
    ("time", r"(?i:seconds?\b|secs?\b|milliseconds?\b)|(?<=\d)\s?s\b|(?<=\d)\s?ms\b"),
)
_UNIT_RX = [(k, re.compile(rf"{NUM}\s*(?P<u>{u})", re.IGNORECASE if k not in ("force", "voltage", "current",
                                                                                     "length", "time") else 0))
            for k, u in _UNIT_SPECS]
# case-sensitive kinds still accept their spelled-out unit in any case ("Newtons", "Volts")
_ANY_UNIT = re.compile(r"\s*(?:" + "|".join(u for _, u in _UNIT_SPECS) + r"|percent|%)", re.IGNORECASE)
_NOT_ANGLE = re.compile(r"\s*(?:celsius|centigrade|fahrenheit|kelvin|c\b|f\b)", re.IGNORECASE)
_PUSH = re.compile(r"\b(?:push\w*|pull\w*|appl(?:y|ied|ies|ying)|exert\w*|drag\w*|force of|with a force|"
                   r"external force|effort|force)\b", re.IGNORECASE)
_RESULT = re.compile(r"\b(?:friction\w*|weight|normal|net|resultant|tension|gravit\w*|reaction|unbalanced|"
                     r"balanced|component|frictional)\b", re.IGNORECASE)
MU_NAMES = (r"mu(?:\s+(?:sub\s+)?[ks])?|μ(?:\s?[ks])?|mew|myu|"
            r"(?:co-?\s?efficient|coefficient)\s+of\s+(?:kinetic\s+|static\s+|sliding\s+|limiting\s+)?f(?:r)?ictions?|"
            r"f(?:r)?iction(?:al)?\s+co-?\s?efficients?|fictional\s+co-?\s?efficients?")
CONN = (r"(?:is|are|it|its|it's|of|be|=|equals?|equal\s+to|to|as|now|about|around|approximately|roughly|nearly|"
        r"becomes?|will\s+be|would\s+be|was|value(?:\s+of)?|let|taken\s+as|say|at|has|with|,|:)")
_FILLER_WORDS = r"(?:\s+[a-z']+){0,6}?"  # "coefficient of friction [of the object of this surface] is"
_MU = re.compile(rf"\b(?:{MU_NAMES})(?:\s+between(?:\s+\w+){{1,6}}?|{_FILLER_WORDS})?\s*(?:{CONN}\s*){{1,3}}"
                 rf"{NUM}(?!\s*(?:kg|kilo|newtons?|N\b|degrees?|°|m\b|metres?|meters?|%))", re.IGNORECASE)
_SMOOTH = re.compile(r"\b(?:smooth|frictionless|no friction|without friction|friction ?less|zero friction|"
                     r"neglect(?:ing)? friction|ignore friction|remove (?:the )?friction)\b", re.IGNORECASE)
_ROUGH = re.compile(r"\brough\b", re.IGNORECASE)
_G = re.compile(rf"(?:\bg\b|acceleration due to gravity|\bgravity)\s*(?:{CONN}\s*){{1,3}}(?:about\s+)?{NUM}"
                rf"(?!\s*(?:kg|N\b|newtons?|degrees?))", re.IGNORECASE)
_UP = re.compile(r"\b(?:up|upwards?|uphill)\s+(?:the|this|along the)?\s*(?:slope|incline|inclined plane|plane|ramp|hill)"
                 r"|\bpush\w*\s+(?:it\s+|the block\s+)?up\b|\bup the (?:slope|incline|plane|ramp)", re.IGNORECASE)
_DOWN = re.compile(r"\b(?:down|downwards?|downhill)\s+(?:the|this|along the)?\s*(?:slope|incline|inclined plane|"
                   r"plane|ramp|hill)|\bpush\w*\s+(?:it\s+|the block\s+)?down\b", re.IGNORECASE)
# the verb, said by someone ("we push it up", "now pull the block down"), not the noun ("a larger pull down the slope")
_PUSH_DIR = re.compile(r"(?:^|\b(?:we|you|i|let's|let us|now|then|and|to|will|can|must|if)\s+|,\s*)(?:push|pull|drag)\w*\s+"
                       r"(?:it\s+|the (?:block|box|body)\s+)?(?:up|down)\b", re.IGNORECASE)
_MODE = re.compile(r"\b(?:push\w*|pull\w*|rope|string)\b", re.IGNORECASE)
CONTEXT_WORDS = 7  # a force value's role is read from the words just before it


def _factor(kind: str, unit: str) -> float:
    u = unit.lower().replace(" ", "").replace("-", "")
    if kind == "mass":
        return 1.0 if u.startswith("k") else 1000.0 if u.startswith("to") else 0.001
    if kind == "force":
        return 1000.0 if u.startswith("k") else 1.0
    if kind == "speed":
        return 1 / 3.6 if ("km" in u or "hour" in u) else 1.0
    if kind == "length":
        return 0.01 if u.startswith(("c", "centi")) else 0.001 if u.startswith(("mm", "milli")) else \
            1000.0 if u.startswith(("k", "kilo")) else 1.0
    if kind in ("voltage", "resistance", "frequency"):
        return 1000.0 if u.startswith("k") else 1.0
    if kind == "current":
        return 0.001 if u.startswith("m") else 1.0
    if kind == "time":
        return 0.001 if u.startswith("m") else 1.0
    return 1.0


def _clean(text: str) -> str:
    return " ".join(text.replace("’", "'").split())


def heard(text: str) -> list[Heard]:
    """Every value the line clearly states, in the order said (a kind may come more than once: "10 and 20 ohms")."""
    t = _clean(text)
    out: list[Heard] = []
    taken: list[tuple[int, int]] = []

    def put(h: Heard, span: tuple[int, int]) -> None:
        if any(span[0] < b and a < span[1] for a, b in taken):
            return  # one stretch of words states one value ("20 m/s" is a speed, not a length)
        taken.append(span)
        out.append(h)

    for kind, rx in _UNIT_RX:
        for m in rx.finditer(t):
            v = spoken_number(m.group("num"))
            if v is None:
                continue
            unit = m.group("u")
            if kind == "angle" and _NOT_ANGLE.match(t, m.end()):
                continue
            if kind == "force":
                if unit == "Newton" and 1500 <= v <= 2100 and v == int(v):
                    continue  # "in 1687 Newton published ...": a year and the name
                before = " ".join(t[:m.start()].split()[-CONTEXT_WORDS:])
                # "a friction of 5 N" / "the weight is 49 N" state a result; "push it with 20 N" is the input
                if _RESULT.search(before):
                    continue
                pushed = bool(_PUSH.search(before) or _PUSH.search(t[m.end():m.end() + 30]))
                odd = bool(re.search(r"N\.? ?m|N[fF]$", unit))
                put(Heard("force", v * _factor(kind, unit), m.group(0), start=m.start(), loose=not pushed,
                          odd_unit=odd), m.span())
                continue
            put(Heard(kind, v * _factor(kind, unit), m.group(0), start=m.start()), m.span())
    for m in _MU.finditer(t):
        v = spoken_number(m.group("num"))
        if v is not None:
            put(Heard("mu", v, m.group(0), start=m.start()), m.span("num"))
    if not any(h.kind == "mu" for h in out):
        m = _SMOOTH.search(t)
        if m:
            put(Heard("mu", 0.0, m.group(0), start=m.start()), m.span())
        elif _ROUGH.search(t):
            out.append(Heard("rough", said="rough"))
    for m in _G.finditer(t):
        v = spoken_number(m.group("num"))
        if v is not None:
            put(Heard("g", v, m.group(0), start=m.start()), m.span("num"))
    # a direction belongs to a push said in the same line ("push it up the slope with 20 newtons") or straight after
    # the push verb ("now push it up"); "balance the pull down the slope" is about the weight, not the push
    if any(h.kind == "force" for h in out) or _PUSH_DIR.search(t):
        if _DOWN.search(t):
            out.append(Heard("force_dir", text="down", said=_DOWN.search(t).group(0)))  # type: ignore[union-attr]
        elif _UP.search(t):
            out.append(Heard("force_dir", text="up", said=_UP.search(t).group(0)))  # type: ignore[union-attr]
    # a force at an angle pushes the block into the floor or pulls it up from it: said with the force or the angle
    if any(h.kind in ("force", "angle") for h in out):
        m = _MODE.search(t)
        if m:
            out.append(Heard("force_mode", text="pull" if m.group(0).lower().startswith(("pull", "rope", "string"))
                             else "push", said=m.group(0)))
    return sorted(out, key=lambda h: (h.start < 0, h.start))


# ---- step 2: the open simulation's slots ------------------------------------------------------------------------
_SET_IT = re.compile(rf"\b(?:make it|make that|change it to|change that to|set it to|set it at|let it be|now it'?s|"
                     rf"now it is|put it at|try|what about|how about|instead of \w+ (?:take|use)|take it as|"
                     rf"what if it (?:was|is|were|becomes)|(?:and )?if it (?:was|were|becomes)|suppose it'?s|"
                     rf"(?:increase|raise|reduce|decrease|lower|bring) it (?:up |down )?to)\s+{NUM}", re.IGNORECASE)
_BARE_LINE = re.compile(rf"^(?:(?:so|and|now|okay|ok|if|it|it's|its|is|of|let's|let|say|make|try|then|what|about|"
                        rf"how|um|uh|the|value|becomes|equals?|to|be|or|maybe|again)\s+)*{NUM}\s*$", re.IGNORECASE)
_RELATIVE = re.compile(r"\b(?P<op>double|doubles|doubled|doubling|triple|tripled|quadruple|halve|halved|halving|half)\b"
                       r"\s+(?:of\s+)?(?P<tgt>it|that|this|the\s+(?:[a-z-]+\s+){0,3}[a-z-]+)", re.IGNORECASE)
_TWICE = re.compile(r"\b(?P<op>twice|two times|three times|half)\s+(?:as\s+(?:much|heavy|big|large|steep)|"
                    r"the\s+(?P<tgt>(?:[a-z-]+\s+){0,2}?[a-z-]+))", re.IGNORECASE)
_STEP = re.compile(rf"\b(?P<verb>increase[sd]?|raise[sd]?|reduce[sd]?|decrease[sd]?|lower(?:s|ed)?|change[sd]?|set|"
                   rf"bring|put|make|take|adjust)\s+(?P<tgt>it|that|this|the\s+(?:[a-z-]+\s+){{0,3}}?[a-z-]+)\s+"
                   rf"(?P<prep>to|by|as|at)\s+{NUM}", re.IGNORECASE)
_FACTORS = {"double": 2.0, "doubles": 2.0, "doubled": 2.0, "doubling": 2.0, "twice": 2.0, "two times": 2.0,
            "triple": 3.0, "tripled": 3.0, "three times": 3.0, "quadruple": 4.0,
            "halve": 0.5, "halved": 0.5, "halving": 0.5, "half": 0.5}
_NO_PUSH = re.compile(r"\b(?:remove (?:the )?(?:push|force)|no push|stop pushing|without (?:the |any )?push|"
                      r"take away the (?:push|force)|let go)\b", re.IGNORECASE)
_TORQUE = re.compile(r"\b(?:torque|moment|work|energy|joules?)\b", re.IGNORECASE)
_NEW_MU = re.compile(rf"\bnew\s+(?:{CONN}\s*){{1,2}}{NUM}", re.IGNORECASE)  # Whisper's "mu" ("new equal to 0.2")


def _steps(t: "Template", line: str, last: Optional[str], items: list[Heard], params: dict[str, float]
           ) -> list[tuple[str, float, str, int, str]]:
    """"increase the angle to 40", "reduce it by 10 degrees", "change it to 45 degree": (slot, value, said, position
    of the number, why). With a unit the unit names the slot ("it" may be another one); "by" needs the current value."""
    out = []
    for m in _STEP.finditer(line):
        tgt = m.group("tgt").lower()
        v = spoken_number(m.group("num"))
        if v is None:
            continue
        unit_h = next((h for h in items if h.start == m.start("num") and h.kind not in ("force_dir", "force_mode")),
                      None)
        slot = _named(t, tgt) if tgt not in ("it", "that", "this") else None
        if unit_h is not None:
            v = unit_h.value
            slot = slot or _slot_for_kind(t, unit_h.kind, "")
        slot = slot or (last if tgt in ("it", "that", "this") else None)
        if slot is None or slot not in t.slot_map:
            continue
        verb = m.group("verb").lower()
        if m.group("prep").lower() == "by":
            cur = params.get(slot)
            if cur is None:
                continue
            if verb.startswith(("increase", "raise", "adjust")):
                v = cur + v
            elif verb.startswith(("reduce", "decrease", "lower")):
                v = cur - v
            else:
                continue
        out.append((slot, v, m.group(0), m.start("num"), "relative (to / by)"))
    return out


@dataclass
class Resolved:
    values: list[tuple[str, float, str]] = field(default_factory=list)  # (slot, value, the words as heard)
    last: Optional[str] = None      # the slot changed or mentioned last in this line (the next bare number's slot)
    rough: bool = False
    direction: str = ""             # "up" / "down" said with a push
    mode: str = ""                  # "push" / "pull" said with a force or an angle
    choices: dict[str, str] = field(default_factory=dict)  # a choice said in words ("in parallel": arrangement)
    mentioned: list[tuple[str, float]] = field(default_factory=list)  # there, number unsaid: (slot, stand-in)
    why: list[str] = field(default_factory=list)  # how each value was read (logs, tests)


_NEGATIVE = re.compile(r"(?:\bminus|\bnegative|−|-)\s*$", re.IGNORECASE)
_PI = re.compile(r"\s*(?:pi\b|π)", re.IGNORECASE)
_PI_BY = re.compile(r"(?:\bpi|π)\s*(?:by|over|/)\s*$", re.IGNORECASE)


def _named(t: "Template", words: str) -> Optional[str]:
    """The slot these words name ("the pushing force" -> applied_n), the last one named when several are."""
    best: tuple[int, Optional[str]] = (-1, None)
    for s in t.slots:
        if not s.names:
            continue
        for m in re.finditer(rf"\b(?:{s.names})\b", words, re.IGNORECASE):
            if s.kind == "force" and _RESULT.search(" ".join(words[:m.start()].split()[-3:]) + " " + m.group(0)):
                continue  # "the friction force" names a result, not the push
            if m.start() > best[0]:
                best = (m.start(), s.name)
    return best[1]


def _slot_for_kind(t: "Template", kind: str, before: str, after: str = "") -> Optional[str]:
    """Unit first: the slot of this kind; with several, the one named just before the value, else the one named in the
    three words after it ("a 2 cm high wave": the amplitude), else the first."""
    slots = [s for s in t.slots if s.kind == kind]
    if not slots:
        return None
    if len(slots) > 1:
        named = _named(t, before)
        if named in {s.name for s in slots}:
            return named
        named = _named(t, " ".join(after.split()[:3]))  # "42164 km from the centre"
        if named in {s.name for s in slots}:
            return named
    return slots[0].name


def resolve(t: "Template", text: str, last: Optional[str] = None, *, friction_context: bool = False,
            params: Optional[dict[str, float]] = None, items: Optional[list[Heard]] = None) -> Resolved:
    """The open simulation's slot values in one line. last: the slot changed or mentioned before (a bare number or
    "double it" goes there); friction_context: friction is on the stage or was just named ("new equal to 0.2" is μ);
    params: the current values (relative phrases)."""
    line = _clean(text)
    items = heard(line) if items is None else items
    slots = t.slot_map
    params = params or {}
    r = Resolved()
    got: dict[str, int] = {}  # slot -> position said
    force_slot = next((s.name for s in t.slots if s.kind == "force"), None)
    force_words = bool(_PUSH.search(line)) or last == force_slot

    def take(slot: Optional[str], value: float, said: str, pos: int, why: str) -> None:
        if slot is None or slot in got:
            return
        if pos >= 0 and (_NEGATIVE.search(line[:pos]) or _PI.match(line[pos + len(said):])
                         or _PI_BY.search(line[:pos])):
            # "minus 30 degrees" is not 30, "3 pi by 2" is not 3°: refused, never misread (unit circle review)
            r.why.append(f"{said}: negative or in terms of pi, not used")
            return
        got[slot] = pos
        r.values.append((slot, value, said))
        r.why.append(f"{slot}: {why}")

    steps = _steps(t, line, last, items, params)
    for slot, v, said, pos, why in steps:
        take(slot, v, said, pos, why)
    stepped = {pos for *_, pos, _ in steps}
    for h in items:
        if h.start in stepped:
            continue  # the number of a step ("increase it to 40 degrees") is that step's value
        if h.kind == "rough":
            r.rough = True
            continue
        if h.kind == "force_dir":
            r.direction = h.text
            continue
        if h.kind == "force_mode":
            r.mode = h.text
            continue
        if h.kind == "force" and h.odd_unit and (not force_words or _TORQUE.search(line)):
            continue  # "20 Nm" with nothing about a force: maybe a torque, not the push
        clause = line[max(0, line.rfind(",", 0, h.start), line.rfind(" and ", 0, h.start)):h.start] if h.start >= 0 else ""
        if t.results is not None and h.start >= 0 and t.results.search(" ".join(line[:h.start].split()[-5:])):
            r.why.append(f"{h.said}: a result of the scene, not an input")
            continue
        after = line[h.start + len(h.said):] if h.start >= 0 else ""
        slot = _slot_for_kind(t, h.kind, clause or line[:max(h.start, 0)], after)
        if slot in got:  # a second value of this kind: the next slot of the kind ("a 4 ohm and a 6 ohm resistor")
            slot = next((s.name for s in t.slots if s.kind == h.kind and s.name not in got), slot)
        take(slot, h.value, h.said, max(h.start, 0), f"unit ({h.kind})")
    said_as = []  # earliest first: "a satellite orbiting the Moon, which itself orbits the Earth" is about the Moon
    for rx, slot, value in t.said_as:  # "thrown horizontally" (θ = 0), "straight up" (θ = 90°), "in parallel"
        m = re.search(rx, line, re.IGNORECASE)
        if m is not None:
            said_as.append((m.start(), m, slot, value))
    for _, m, slot, value in sorted(said_as, key=lambda x: x[0]):
        if isinstance(value, str):  # a choice, not a number slot
            r.choices.setdefault(slot, value)
        elif slot not in got:
            take(slot, value, m.group(0), m.start(), "said as words")
    used = {h.start for h in items if h.start >= 0}
    # a value named without a unit: "the pushing force is 50", "the angle of inclination is of 30", "mass is 10"
    for s in t.slots:
        if not s.names or s.name in got:
            continue
        rx = re.compile(rf"\b(?:{s.names})\b{_FILLER_WORDS}\s*(?:{CONN}\s*){{1,3}}{NUM}(?!{_ANY_UNIT.pattern})",
                        re.IGNORECASE)
        for m in rx.finditer(line):
            if m.start("num") in used:
                continue  # that number has a unit and went to its own slot ("a force at an angle of 30 degrees")
            if s.kind == "force" and _RESULT.search(" ".join(line[:m.start()].split()[-3:]) + " " +
                                                    line[m.start():m.start("num")]):
                continue
            if t.results is not None and t.results.search(" ".join(line[:m.start("num")].split()[-5:])):
                continue
            v = spoken_number(m.group("num"))
            if v is None or (s.kind == "angle" and v < 1):  # "30 N at an angle of 0.5": a mishearing, not 0.5°
                continue
            take(s.name, v, m.group(0), m.start(), "named")
            break
    if "mu" in slots and "mu" not in got and friction_context:
        m = _NEW_MU.search(line)
        if m and (v := spoken_number(m.group("num"))) is not None and v <= slots["mu"].hi:
            take("mu", v, m.group(0), m.start(), "'new' heard for mu")
    if force_slot and force_slot not in got and _NO_PUSH.search(line):
        take(force_slot, 0.0, _NO_PUSH.search(line).group(0), 0, "no push")  # type: ignore[union-attr]
    # relative: "double it", "halve the mass", "twice the force"
    for rx in (_RELATIVE, _TWICE):
        for m in rx.finditer(line):
            tgt = (m.group("tgt") or "it")
            slot = last if tgt.lower() in ("it", "that", "this") else _named(t, tgt)
            if slot is None or slot in got or params.get(slot) is None:
                continue
            take(slot, params[slot] * _FACTORS[m.group("op").lower()], m.group(0), m.start(), "relative (factor)")
    for s in t.slots:  # "thrown from a cliff" with no height: a cliff is drawn, nothing from h is printed
        if s.present and s.name not in got and re.search(s.present, line, re.IGNORECASE):
            r.mentioned.append((s.name, s.present_value))
    # a bare number: "make it 30", or the whole line "0.3": the slot changed or mentioned last
    if last in slots and last not in got and not r.values:
        m = _SET_IT.search(line) or _BARE_LINE.match(line.rstrip(".?!, "))
        if m and not _ANY_UNIT.match(line, m.end("num")):
            v = spoken_number(m.group("num"))
            if v is not None:
                take(last, v, m.group(0), m.start(), "bare number -> the last slot")
    if r.values:
        r.last = max(got, key=lambda s: got[s])
    else:
        r.last = _named(t, line)  # only mentioned: "if the coefficient of friction of this surface is ..."
    return r
