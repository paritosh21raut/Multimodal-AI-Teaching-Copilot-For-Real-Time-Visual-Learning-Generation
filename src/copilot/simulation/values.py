"""Spoken values -> simulation slots (F-014), deterministic, 0 tokens.

One finished transcript line in, the quantities it states out, by kind (a template maps a kind to its slot,
base.Slot.kind):
    mass    "a block of 5 kg", "five kilograms", "500 grams"
    angle   "30 degrees", "an angle of thirty", "theta equals 30" (not "30 degrees Celsius")
    force   "push it with 20 newtons" - only a push / pull / applied force; a friction, weight, normal or net force
            the teacher states is a result, never an input (S2 compares it with the computed value)
    mu      "mu equals 0.2", "coefficient of friction is zero point two", "μ = 0.2"; "smooth" / "frictionless" = 0
    g       "take g as 10", "g = 9.8 metres per second squared"
plus two qualities: force_dir (the push acts "up" / "down" the slope) and rough (friction exists, value not said).

Precision over recall: a value that is not clearly one of these is left out (the teacher can set it in /control).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_ONES = {"zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
         "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
         "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19}
_TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80,
         "ninety": 90}
_DIGIT = {**{k: v for k, v in _ONES.items() if v < 10}, "oh": 0, "o": 0}
_W1 = "|".join(sorted(_ONES, key=len, reverse=True))
_W10 = "|".join(_TENS)
# a spelled number: "five", "thirty five", "thirty-five", "two hundred", "two hundred and fifty", "zero point two"
_SPELLED = (rf"(?:(?:{_W1}|a)\s+hundred(?:\s+(?:and\s+)?(?:(?:{_W10})(?:[\s-](?:{_W1}))?|{_W1}))?|"
            rf"(?:{_W10})(?:[\s-](?:{_W1}))?|{_W1})"
            rf"(?:\s+point(?:\s+(?:{'|'.join(_DIGIT)}))+)?|point(?:\s+(?:{'|'.join(_DIGIT)}))+")
NUM = rf"(?P<num>-?\d+(?:,\d{{3}})*(?:\.\d+)?|-?\.\d+|{_SPELLED})"


def spoken_number(s: str) -> Optional[float]:
    """"5" / "0.2" / "1,000" / "thirty-five" / "zero point two" / "two hundred and fifty" -> float, else None."""
    s = s.strip().lower().replace(",", "")
    try:
        return float(s)
    except ValueError:
        pass
    whole, _, frac = s.partition("point")
    total = 0.0
    words = whole.replace("-", " ").split()
    seen = False
    for w in words:
        if w == "and":
            continue
        if w == "hundred":
            total = (total or 1.0) * 100
        elif w in _TENS:
            total += _TENS[w]
        elif w in _ONES:
            total += _ONES[w]
        elif w == "a":
            continue
        else:
            return None
        seen = True
    if frac.strip():
        digits = [_DIGIT.get(w) for w in frac.split()]
        if not digits or any(d is None for d in digits):
            return None
        total += float("0." + "".join(str(d) for d in digits))
        seen = True
    return total if seen else None


@dataclass(frozen=True)
class Heard:
    kind: str           # mass | angle | force | mu | g | force_dir | rough
    value: float = 0.0  # in the slot's unit (kg, degrees, N, -, m/s²)
    said: str = ""      # the words as heard ("five kilograms")
    text: str = ""      # for force_dir: "up" / "down"


_MASS = re.compile(rf"{NUM}\s*(?P<u>kg\b|kgs\b|kilo(?:gram)?s?\b|grams?\b|gm\b|tonnes?\b|tons?\b)", re.IGNORECASE)
_MASS_FACTOR = {"g": 0.001, "gr": 0.001, "gm": 0.001, "to": 1000.0}
_ANGLE = re.compile(rf"{NUM}\s*(?:°|degrees?\b|deg\b)(?!\s*(?:celsius|centigrade|fahrenheit|kelvin|c\b|f\b))",
                    re.IGNORECASE)
_ANGLE_NAMED = re.compile(rf"\b(?:angle(?: of (?:inclination|the (?:incline|slope|plane)))?|theta|θ|inclination)\s*"
                          rf"(?:of|is|=|equals|equal to|equal|as|be)\s+{NUM}(?!\s*(?:kg|kilo|newton|n\b|m\b|metre|meter|%))",
                          re.IGNORECASE)
_FORCE = re.compile(rf"{NUM}\s*(?:newtons?\b|(?<=\d)\s*N\b|(?<=\d)N\b)")
_FORCE_SPOKEN_N = re.compile(rf"{NUM}\s+newtons?\b", re.IGNORECASE)
_PUSH = re.compile(r"\b(?:push\w*|pull\w*|appl(?:y|ied|ies|ying)|exert\w*|drag\w*|force of|with a force|"
                   r"external force|effort)\b", re.IGNORECASE)
_RESULT = re.compile(r"\b(?:friction\w*|weight|normal|net|resultant|tension|gravit\w*|reaction|unbalanced|"
                     r"balanced|component)\b", re.IGNORECASE)
_MU = re.compile(rf"(?:\bmu\b|μ|\bmew\b|coefficient of (?:kinetic |static |sliding |limiting )?friction"
                 rf"(?:\s+between(?:\s+\w+){{1,6}}?(?=\s+(?:is|=|equals|be)\b))?)\s*"
                 rf"(?:is|=|equals|equal to|equal|of|as|be|value(?: is)?)?\s*(?:about\s+|around\s+|nearly\s+)?{NUM}",
                 re.IGNORECASE)
_SMOOTH = re.compile(r"\b(?:smooth|frictionless|no friction|without friction|friction ?less|zero friction|"
                     r"neglect(?:ing)? friction|ignore friction)\b", re.IGNORECASE)
_ROUGH = re.compile(r"\brough\b", re.IGNORECASE)
_G = re.compile(rf"(?:\bg\b|acceleration due to gravity)\s*(?:is|=|equals|equal to|equal|as|be)\s*(?:about\s+)?{NUM}",
                re.IGNORECASE)
_UP = re.compile(r"\b(?:up|upwards?|uphill)\s+(?:the|this|along the)?\s*(?:slope|incline|inclined plane|plane|ramp|hill)"
                 r"|\bpush\w*\s+(?:it\s+|the block\s+)?up\b|\bup the (?:slope|incline|plane|ramp)", re.IGNORECASE)
_DOWN = re.compile(r"\b(?:down|downwards?|downhill)\s+(?:the|this|along the)?\s*(?:slope|incline|inclined plane|"
                   r"plane|ramp|hill)|\bpush\w*\s+(?:it\s+|the block\s+)?down\b", re.IGNORECASE)
_PUSH_DIR = re.compile(r"(?<!\bthe )(?<!\ba )\b(?:push|pull|drag)\w*\s+(?:it\s+|the (?:block|box|body)\s+)?(?:up|down)\b", re.IGNORECASE)
CONTEXT_WORDS = 7  # a force value's role is read from the words just before it


def _num(m: re.Match) -> Optional[float]:
    return spoken_number(m.group("num"))


def heard(text: str) -> list[Heard]:
    """Every value the line clearly states (at most one per kind: the first)."""
    t = " ".join(text.replace("’", "'").split())
    out: dict[str, Heard] = {}

    def put(h: Heard) -> None:
        out.setdefault(h.kind, h)

    for m in _MASS.finditer(t):
        v = _num(m)
        if v is not None:
            u = m.group("u").lower()
            put(Heard("mass", v * _MASS_FACTOR.get(u[:2], 1.0) if not u.startswith("k") else v, m.group(0)))
    for rx in (_ANGLE, _ANGLE_NAMED):
        for m in rx.finditer(t):
            v = _num(m)
            if v is not None:
                put(Heard("angle", v, m.group(0)))
    for rx in (_FORCE, _FORCE_SPOKEN_N):
        for m in rx.finditer(t):
            v = _num(m)
            if v is None:
                continue
            before = " ".join(t[:m.start()].split()[-CONTEXT_WORDS:])
            # "a friction of 5 N" / "the weight is 49 N" state a result; "push it with 20 N" is the input
            if _RESULT.search(before) or not (_PUSH.search(before) or _PUSH.search(t[m.end():m.end() + 30])):
                continue
            put(Heard("force", v, m.group(0)))
    for m in _MU.finditer(t):
        v = _num(m)
        if v is not None:
            put(Heard("mu", v, m.group(0)))
    if "mu" not in out:
        m = _SMOOTH.search(t)
        if m:
            put(Heard("mu", 0.0, m.group(0)))
        elif _ROUGH.search(t):
            put(Heard("rough", said="rough"))
    for m in _G.finditer(t):
        v = _num(m)
        if v is not None:
            put(Heard("g", v, m.group(0)))
    # a direction belongs to a push said in the same line ("push it up the slope with 20 newtons") or straight after
    # the push verb ("now push it up"); "balance the pull down the slope" is about the weight, not the push
    if "force" in out or _PUSH_DIR.search(t):
        if _DOWN.search(t):
            put(Heard("force_dir", text="down", said=_DOWN.search(t).group(0)))  # type: ignore[union-attr]
        elif _UP.search(t):
            put(Heard("force_dir", text="up", said=_UP.search(t).group(0)))  # type: ignore[union-attr]
    return list(out.values())
