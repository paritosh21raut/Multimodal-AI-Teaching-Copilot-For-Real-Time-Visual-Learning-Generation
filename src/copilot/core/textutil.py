"""Small text helpers shared across packages."""
from __future__ import annotations

import math
import re

_SENT_END = re.compile(r"[.!?][\"')\]]*$")


def approx_tokens(text: str) -> int:
    """Conservative token estimate for budget enforcement (no model tokenizer needed).

    max(chars / 4, words * 1.35) over-estimates typical BPE counts for English, so a prompt
    within the estimated budget is within the real one.
    """
    if not text:
        return 0
    return math.ceil(max(len(text) / 4.0, len(text.split()) * 1.35))


def ends_sentence(text: str) -> bool:
    return bool(_SENT_END.search(text.strip()))


def word_count(text: str) -> int:
    return len(text.split())


# ---- spoken quantities (F-013 S3): "10 to the power minus 8 centimeter" and "~10⁻⁸ cm" are the same item
_SUPERSCRIPT = {c: d for c, d in zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺", "0123456789-+")}
_UNITS = [(r"centimet(?:er|re)s?", "cm"), (r"millimet(?:er|re)s?", "mm"), (r"kilomet(?:er|re)s?", "km"),
          (r"nanomet(?:er|re)s?", "nm"), (r"met(?:er|re)s?", "m"), (r"kilograms?", "kg"), (r"milligrams?", "mg"),
          (r"grams?", "g"), (r"degrees? (?:celsius|centigrade)", "°c"), (r"degrees? kelvin|kelvins?", "k"),
          (r"per ?cent", "%"), (r"coulombs?", "c"), (r"seconds?", "s"), (r"hertz", "hz"), (r"volts?", "v"),
          (r"amperes?|amps?", "a"), (r"ohms?", "ω"), (r"joules?", "j"), (r"watts?", "w"), (r"newtons?", "n"),
          (r"litres?|liters?", "l"), (r"miles?", "mi")]


def normalise_spoken(text: str) -> str:
    """Lower-case text with quantities written one way: spoken powers and superscripts as "10^-8", "minus 55" as
    "-55", "9.58 into 10" as "9.58x10", unit words as symbols ("centimeter" -> "cm", "degrees Celsius" -> "°c").
    For comparing items, never for display (test4: "~10⁻⁸ cm" and "10 to the power minus 8 centimeter" were shown
    together; test5: "55 °C" and "minus 55 degrees Celsius")."""
    t = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻⁺]+", lambda m: "^" + "".join(_SUPERSCRIPT[c] for c in m.group()), text)
    t = t.replace("−", "-").replace("×", " x ").replace("~", " ").replace("≈", " ").lower()
    t = re.sub(r"\b(?:minus|negative)\s+(?=\d)", "-", t)
    t = re.sub(r"\s*\bto the power (?:of )?", "^", t)
    t = re.sub(r"\^\s+(?=-?\d)", "^", t)
    t = re.sub(r"(?<=\d)\s*(?:into|x|times|\*)\s*(?=\d)", "x", t)
    t = re.sub(r"(?<=\d)\s*%", " %", t)
    for word, sym in _UNITS:
        # only as a unit: after a number or "per" ("second law", "a metre stick" stay words)
        t = re.sub(rf"(?:(?<=\d)|(?<=\d )|(?<=\bper )){word}\b", sym, t)
    t = re.sub(r"(?<=\d)\s*°\s*c\b", " °c", t)
    return " ".join(t.split())


def stem(word: str) -> str:
    """A light English stemmer for comparing words ("masses" ~ "mass", "rioting" ~ "riots", "wars" ~ "war"): not
    linguistics, only enough that one statement said two ways shares its words."""
    w = word.lower()
    if len(w) <= 3 or not w.isalpha():
        return w
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ches", "ch"), ("shes", "sh"), ("xes", "x"), ("ing", ""),
                     ("ed", ""), ("ly", ""), ("es", "e"), ("s", "")):
        if w.endswith(suf) and len(w) - len(suf) >= 3 and not (suf == "s" and w.endswith(("ss", "us", "is"))):
            w = w[: len(w) - len(suf)] + rep
            break
    if len(w) > 4 and w[-1] == w[-2] and w[-1] not in "lsz":  # "stopp(ing)" -> "stop"
        w = w[:-1]
    return w.rstrip("e") if len(w) > 4 else w
