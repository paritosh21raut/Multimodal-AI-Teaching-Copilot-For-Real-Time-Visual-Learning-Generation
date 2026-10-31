"""Numbers are sacred (F-019 M0, test36: the said "5 kg" became "5 kN" on the recap).

The understanding LLM may reword what the teacher said, but never a number: every number in its content must be one
the teacher said (in the request's lines or already on the slide). Deterministic, after parsing:
    - a quantity whose number was said with another unit ("5 kN", said "5kg") is put back as said
    - an item with a number nobody said is dropped (a list item, a pair, a row; a single field is emptied)
    - a factual concern that would change a said number or unit is dropped: the slide keeps what was said
Formulas are left alone (a relation's own constants: "½mv²", "E = mc^2"), so are digits inside names (H2O, C3).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Optional, Sequence

from copilot.core.interpretation import ContentItems, Interpretation

log = logging.getLogger(__name__)

_WORDS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen twenty".split())}
_WORDS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
               "hundred": 100, "thousand": 1000, "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
               "half": 0.5, "quarter": 0.25})
# a number not inside a name ("H2O", "C3", "x2"): no letter or digit right before it
_NUM = re.compile(r"(?<![A-Za-z0-9_.])(-?\d+(?:,\d{3})*(?:\.\d+)?|-?\.\d+)(?:st|nd|rd|th)?(?![\d])\s*"
                  r"(%|°\s*[CF]?|[A-Za-zµμΩ]+(?:\s*/\s*[A-Za-z]+|\s+per\s+[A-Za-z]+)?(?:[²³]|\^\s*[23]|(?<=[A-Za-z])[23]\b|"
                  r"\s+(?:squared|cubed)\b)?)?")
# "Step 1:", "1." / "2)" at the start of an item: the model's own list numbering, not a value
_NUMBERING = re.compile(r"^\s*(?:step\s+)?\d+\s*[.:)]\s", re.IGNORECASE)
_UNIT = {
    "kg": "kg", "kgs": "kg", "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
    "g": "g", "gram": "g", "grams": "g", "n": "n", "newton": "n", "newtons": "n", "kn": "kn",
    "m": "m", "metre": "m", "metres": "m", "meter": "m", "meters": "m", "cm": "cm", "centimetre": "cm",
    "centimetres": "cm", "centimeter": "cm", "centimeters": "cm", "mm": "mm", "km": "km", "kilometre": "km",
    "kilometres": "km", "kilometer": "km", "kilometers": "km", "s": "s", "sec": "s", "second": "s", "seconds": "s",
    "%": "%", "percent": "%", "per cent": "%", "°": "deg", "deg": "deg", "degree": "deg", "degrees": "deg",
    "°c": "degc", "celsius": "degc", "v": "v", "volt": "v", "volts": "v", "a": "a", "amp": "a", "amps": "a",
    "ampere": "a", "amperes": "a", "ohm": "ohm", "ohms": "ohm", "ω": "ohm", "j": "j", "joule": "j", "joules": "j",
    "w": "w", "watt": "w", "watts": "w", "l": "l", "litre": "l", "litres": "l", "liter": "l", "liters": "l",
    "ml": "ml", "m/s": "m/s", "mps": "m/s", "km/h": "km/h", "kmph": "km/h", "kph": "km/h", "m/s²": "m/s2",
    "m/s2": "m/s2", "n/m": "n/m", "hz": "hz", "hertz": "hz", "k": "k", "kelvin": "k",
}
_PER = re.compile(r"\s+per\s+")


def _unit(u: str) -> str:
    """The unit's normal form; "" = none (a plain number, or a word that is no unit: "5 boxes")."""
    if u.strip() == "a":
        return ""  # "5 a block": the article, not amperes ("5 A" stays)
    u = " ".join(u.lower().split())
    if not u:
        return ""
    sq = re.search(r"(?:²|\^\s*2|(?<=[a-z])2|\s+squared)$", u)
    cu = re.search(r"(?:³|\^\s*3|(?<=[a-z])3|\s+cubed)$", u)
    u = u[:(sq or cu).start()] if (sq or cu) else u
    u = _PER.sub("/", u).replace(" ", "")
    u = {"meter/second": "m/s", "metre/second": "m/s", "meters/second": "m/s", "metres/second": "m/s",
         "kilometre/hour": "km/h", "kilometer/hour": "km/h", "kilometres/hour": "km/h", "kilometers/hour": "km/h",
         "newton/metre": "n/m", "newton/meter": "n/m", "newtons/metre": "n/m", "newtons/meter": "n/m"}.get(u, u)
    base = _UNIT.get(u, _UNIT.get(u.split("/")[0], "") if "/" in u else "")
    return base + ("2" if sq else "3" if cu else "") if base else ""  # "m/s²" = "m/s^2" = "metres per second squared"


def _value(s: str) -> Optional[float]:
    try:
        return float(s.replace(",", ""))
    except ValueError:
        return None


def quantities(text: str) -> list[tuple[float, str, int, int]]:
    """(value, normal unit or "", start, end of the whole quantity) for every number in the text."""
    out = []
    for m in _NUM.finditer(text or ""):
        v = _value(m.group(1))
        if v is None:
            continue
        u = _unit(m.group(2) or "")
        end = m.end(2) if u and m.group(2) else m.end(1)
        out.append((v, u, m.start(1), end))
    return out


def spoken_values(line: str) -> set[float]:
    """Every number said in words, each word alone and each run added up ("twenty five" -> 20, 5, 25; "a hundred and
    fifty" -> 100, 50, 150)."""
    out: set[float] = set()
    total, cur, run = 0.0, 0.0, False
    for w in re.findall(r"[a-z]+", line.lower()) + ["."]:
        x = _WORDS.get(w)
        if x is not None:
            out.add(float(x))
            if w in ("hundred", "thousand"):
                cur = (cur or 1) * x
                if w == "thousand":
                    total, cur = total + cur, 0.0
            else:
                cur += x
            run = True
        elif run and w in ("and", "a"):
            continue
        else:
            if run:
                out.add(total + cur)
            total, cur, run = 0.0, 0.0, False
    return out


class Said:
    """The numbers the teacher said: values (digits and number words) and the quantities with their units."""

    def __init__(self, lines: Sequence[str]) -> None:
        self.values: set[float] = set()
        self.pairs: set[tuple[float, str]] = set()
        self.forms: dict[float, dict[str, str]] = {}  # value -> unit -> the text as said ("5kg", "5K")
        for line in lines:
            for v, u, s, e in quantities(line):
                self.values.add(v)
                self.pairs.add((v, u))
                if u:
                    self.forms.setdefault(v, {}).setdefault(u, line[s:e])
            self.values |= spoken_values(line or "")

    def ok(self, v: float, u: str) -> bool:
        if v not in self.values:
            return False
        return not u or (v, u) in self.pairs or not any(p[0] == v and p[1] for p in self.pairs)


def fix(text: str, said: Said) -> Optional[str]:
    """The text with every number as said; None when it holds a number nobody said."""
    out, changed = text, False
    skip = _NUMBERING.match(text)
    for v, u, s, e in reversed(quantities(text)):
        if skip and s < skip.end():
            continue
        if said.ok(v, u):
            continue
        forms = said.forms.get(v, {})
        if u and len(forms) == 1:  # the unit changed: back to the one said form ("5 kN" -> "5kg"); two said: unsure
            out = out[:s] + next(iter(forms.values())) + out[e:]
            changed = True
            continue
        return None
    return out if changed else text


def _walk(v: Any, said: Said, notes: list[str], aligned: bool = False) -> Any:
    """A JSON value with its numbers checked: None = drop it (the caller drops a list item / empties a field).
    aligned: a list whose positions mean something (a row's values, `compare`): an item is emptied, not dropped."""
    if isinstance(v, str):
        f = fix(v, said)
        if f != v:
            notes.append(f"{v!r} -> {f!r}" if f is not None else f"{v!r} dropped")
        return f
    if isinstance(v, list):
        got = [_walk(x, said, notes) for x in v]
        if aligned:
            return [("" if isinstance(x, str) else x) if y is None else y for x, y in zip(v, got)]
        return [x for x in got if x is not None]
    if isinstance(v, dict):
        out = {}
        for k, x in v.items():
            y = _walk(x, said, notes, aligned=True)
            if y is None:
                return None  # a pair / row / fact with an unsaid number goes as a whole
            out[k] = y
        return out
    return v


def _items(it: ContentItems, said: Said, notes: list[str]) -> ContentItems:
    data = it.model_dump()
    formula = data.pop("formula", None)
    out: dict[str, Any] = {}
    for k, v in data.items():
        y = _walk(v, said, notes, aligned=k == "compare")
        out[k] =("" if isinstance(v, str) else []) if y is None else y
    out["formula"] = formula
    return ContentItems.model_validate(out)


def _changes_a_number(c: Any, said: Said) -> bool:
    """The concern's correction has a number (or unit) the teacher did not say where the claim has one they did."""
    before = [q for q in quantities(f"{c.claim} {c.wrong}") if said.ok(q[0], q[1])]
    after = [q for q in quantities(f"{c.suggested_correction} {c.right}") if not said.ok(q[0], q[1])]
    return bool(before and after)


def guard_numbers(it: Interpretation, lines: Sequence[str]) -> tuple[Interpretation, list[str]]:
    """The interpretation with only said numbers; the changes made (for the log)."""
    said = Said(lines)
    notes: list[str] = []
    acts = [a.model_copy(update={"items": _items(a.items, said, notes)}) for a in it.acts]
    concerns = []
    for c in it.concerns:
        if c.kind == "factual" and _changes_a_number(c, said):
            log.info("[CONCERN] number kept: %r stays as said (not %r)", c.claim, c.suggested_correction)
            notes.append(f"concern {c.claim!r} -> {c.suggested_correction!r} dropped")
            continue
        concerns.append(c)
    if not notes:
        return it, []
    return it.model_copy(update={"acts": acts, "concerns": concerns}), notes
