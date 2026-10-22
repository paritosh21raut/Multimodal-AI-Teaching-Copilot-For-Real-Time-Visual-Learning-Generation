"""Refraction at a flat boundary: Snell's law, total internal reflection (F-014 S4). Renderer: web/sims/refraction.js.

A ray in medium 1 (above) meets a flat boundary with medium 2 (below) at the angle of incidence θ₁ to the normal:

    n₁ sin θ₁ = n₂ sin θ₂                    (the refracted ray, θ₂ to the normal on the other side)
    n₁ > n₂: θ_c = asin(n₂ / n₁); θ₁ > θ_c: no refracted ray, all of it reflected (total internal reflection)
    the reflected ray leaves at θ₁ (drawn faint while there is a refracted ray); speed in a medium v = c / n

    air → glass (1.5), 30°: θ₂ = asin(sin 30° / 1.5) = 19.5°;  glass (1.5) → air: θ_c = asin(1 / 1.5) = 41.8°;
    glass → air at 50°: total internal reflection;  water (1.33) → air at 30°: θ₂ = asin(1.33 · 0.5) = 41.7°

Truthfulness: a medium named without its index ("from air into glass") is drawn with a textbook index and named, but
its index and every angle worked out from it are not printed; air (and vacuum) count as n = 1 (a standard value, like
g). An index printed was said ("the refractive index of glass is 1.5", "n2 = 1.33"); the refracted angle and the
critical angle need both indices known, the refracted angle the angle of incidence said too.
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import (
    Derived, Element, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt, value_label,
)
from copilot.simulation.values import spoken_number

# medium -> (name printed, the index it is drawn with when its index is not said)
MEDIA = {"air": ("air", 1.0), "vacuum": ("vacuum", 1.0), "water": ("water", 1.33), "glass": ("glass", 1.5),
         "diamond": ("diamond", 2.42), "oil": ("oil", 1.47), "ice": ("ice", 1.31), "perspex": ("perspex", 1.49)}
STANDARD = ("air", "vacuum")  # n = 1: known without being said
_WORDS = {"air": r"air", "vacuum": r"vacuum", "water": r"water", "glass": r"(?:crown |flint )?glass",
          "diamond": r"diamond", "oil": r"oil", "ice": r"ice", "perspex": r"perspex|acrylic|plexiglass?"}

SLOTS = (
    Slot("n1", "Refractive index (medium 1)", "n₁", "", 1.0, 3.0, 0.01, 1.0, "index"),
    Slot("n2", "Refractive index (medium 2)", "n₂", "", 1.0, 3.0, 0.01, 1.5, "index"),
    Slot("angle_deg", "Angle of incidence", "θ₁", "°", 0.0, 89.0, 1.0, 30.0, "angle",
         names=r"angle of incidence|incident angle|incidence|\bi\b|theta ?1"),
)
ELEMENTS = (
    Element("media", "Media"), Element("normal", "Normal"), Element("rays", "Rays"), Element("angles", "Angles"),
    Element("readout", "Values"),
)


class RefractionParams(_Model):
    n1: float = Field(default=1.0, ge=1.0, le=3.0)
    n2: float = Field(default=1.5, ge=1.0, le=3.0)
    angle_deg: float = Field(default=30.0, ge=0.0, le=89.0)
    medium1: Literal["air", "vacuum", "water", "glass", "diamond", "oil", "ice", "perspex"] = "air"
    medium2: Literal["air", "vacuum", "water", "glass", "diamond", "oil", "ice", "perspex"] = "glass"
    # the medium each said index belongs to: it follows its medium when the direction changes ("now from glass into air")
    n1_of: Literal["", "air", "vacuum", "water", "glass", "diamond", "oil", "ice", "perspex"] = ""
    n2_of: Literal["", "air", "vacuum", "water", "glass", "diamond", "oil", "ice", "perspex"] = ""


class RefractionSim(SimBase):
    template: Literal["refraction"] = "refraction"
    params: RefractionParams = Field(default_factory=RefractionParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("m1", "m2", "n1", "n2", "t1", "t2", "tc", "tir")


def snell(n1: float, n2: float, t1_deg: float) -> Optional[float]:
    """θ₂ in degrees, None past the critical angle (total internal reflection)."""
    s = n1 * math.sin(math.radians(t1_deg)) / n2
    return None if s > 1 + 1e-12 else math.degrees(math.asin(min(1.0, s)))


def critical(n1: float, n2: float) -> Optional[float]:
    return math.degrees(math.asin(n2 / n1)) if n1 > n2 else None


def solve(p: RefractionParams, src: dict[str, str]) -> Solution:
    med = {1: p.medium1, 2: p.medium2}
    of = {"n1": p.n1_of, "n2": p.n2_of}
    # an index said counts while its side is still the medium it was said for (the teacher's own from /control: always)
    said = lambda name: src.get(name, "default") in ("teacher", "computed") or (  # noqa: E731
        src.get(name, "default") == "said" and (not name.startswith("n") or of[name] in ("", med[int(name[1])])))
    named = lambda k: src.get(f"medium{k}", "default") in ("said", "teacher")  # noqa: E731
    n = {1: p.n1 if said("n1") else MEDIA[med[1]][1], 2: p.n2 if said("n2") else MEDIA[med[2]][1]}
    # an index is known when said, or for air / vacuum named (or medium 1 left as air: the textbook ray comes from air)
    n_ok = {k: said(f"n{k}") or (med[k] in STANDARD and (named(k) or k == 1)) for k in (1, 2)}
    t2 = snell(n[1], n[2], p.angle_deg)
    tc = critical(n[1], n[2])
    both = n_ok[1] and n_ok[2]
    t1_ok = said("angle_deg")
    labels = {
        "m1": SimLabel(symbol=MEDIA[med[1]][0] if named(1) else ""),
        "m2": SimLabel(symbol=MEDIA[med[2]][0] if named(2) else ""),
        "n1": SimLabel(symbol="n₁", text=fmt(n[1]), source=src["n1"]) if said("n1")  # type: ignore[arg-type]
        else SimLabel(symbol="n₁", text="1", source="computed") if n_ok[1] and named(1) else SimLabel(symbol="n₁"),
        "n2": SimLabel(symbol="n₂", text=fmt(n[2]), source=src["n2"]) if said("n2")  # type: ignore[arg-type]
        else SimLabel(symbol="n₂", text="1", source="computed") if n_ok[2] and named(2) else SimLabel(symbol="n₂"),
        "t1": value_label("θ₁", p.angle_deg, "°", src.get("angle_deg", "default"), t1_ok),
        "t2": value_label("θ₂", t2 if t2 is not None else 0.0, "°", "computed", both and t1_ok and t2 is not None),
        "tc": value_label("θc", tc if tc is not None else 0.0, "°", "computed", both and tc is not None),
        "tir": SimLabel(symbol=""),
    }
    derived: list[Derived] = []
    if both and t1_ok:
        if t2 is None:
            derived.append(Derived(id="t2", label="Refracted ray", symbol="θ₂", value=-1.0,
                                   text="none"))
            labels["tir"] = SimLabel(symbol="total internal reflection")
        else:
            derived.append(Derived(id="t2", label="Angle of refraction", symbol="θ₂", value=t2, unit="°",
                                   text=f"{fmt(t2)}°"))
    if both and tc is not None:
        derived.append(Derived(id="tc", label="Critical angle", symbol="θc", value=tc, unit="°", text=f"{fmt(tc)}°"))
    if both and abs(n[1] - n[2]) > 1e-9:
        r = n[1] / n[2]  # v₂ / v₁ = n₁ / n₂
        derived.append(Derived(id="speed", label="Speed ratio", symbol="v₂ / v₁", value=r, text=fmt(r)))
    drive = {"n1": n[1], "n2": n[2], "t1": p.angle_deg, "t2": t2 if t2 is not None else -1.0,
             "tir": 1.0 if t2 is None else 0.0, "tc": tc if tc is not None else -1.0, "still_t": 2.0}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: RefractionParams, src: dict[str, str]) -> list[str]:
    return ["media", "normal", "rays", "angles", "readout"]


# ---- speech: the media in order, their indices, notices -------------------------------------------------------------
_MED = "|".join(f"(?P<{k}>{w})" for k, w in _WORDS.items())
_MED_RX = re.compile(rf"\b(?:{_MED})\b", re.IGNORECASE)
_NUM = r"\d+(?:\.\d+)?|one point \w+(?: \w+)?|two point \w+(?: \w+)?|one|two|three"
_FROM_TO = re.compile(rf"\bfrom (?:the )?(?P<a>{'|'.join(_WORDS.values())})\b[^.;]{{0,30}}?\b(?:in)?to (?:the )?"
                      rf"(?:a |an )?(?:denser |rarer |dense |rare )?(?:\w+ )?(?P<b>{'|'.join(_WORDS.values())})\b",
                      re.IGNORECASE)
_INTO = re.compile(rf"\b(?:enters?|entering|into|passes into|goes into|travels into|in) (?:the |a |an )?(?:\w+ )?"
                   rf"(?:slab |block |piece |surface )?(?:of )?(?P<b>{'|'.join(_WORDS.values())})\b", re.IGNORECASE)
_INDEX = re.compile(rf"\b(?:refractive index|index of refraction|absolute refractive index|\bmu\b|\bμ\b)"
                    rf"(?: of (?:the )?(?:(?P<m>{'|'.join(_WORDS.values())})|(?P<s>first|second|incident|"
                    rf"other|second) medium))?(?: with respect to (?:the )?\w+| relative to (?:the )?\w+)?"
                    rf"(?: is equal to| is| =| equal to| equals| of| as)?\s+"
                    rf"(?:about |nearly |approximately )?(?P<v>{_NUM})\b", re.IGNORECASE)
_MED_INDEX = re.compile(rf"\b(?P<m>{'|'.join(_WORDS.values())})(?: has| with)? (?:a |an )?(?:(?:refractive )?index|"
                        rf"n|mu|μ)(?: of| equal to| equals| =)?(?: is)?\s+(?P<v>{_NUM})\b", re.IGNORECASE)
_AND_MED = re.compile(rf",? and (?:that of |for )?(?:the )?(?P<m>{'|'.join(_WORDS.values())})(?: is| has)?\s+"
                      rf"(?P<v>{_NUM})\b", re.IGNORECASE)  # "... index of 1.5 and water 1.33"
_N_BARE = re.compile(rf"(?<![\w₁₂])(?:n|μ)\s*(?:=|is equal to|equals|equal to)\s*(?P<v>{_NUM})\b")
_N_SYM = re.compile(rf"\b(?:n|mu)\s?(?P<k>1|2|one|two)\s?(?:=|is|equals)\s?(?P<v>{_NUM})\b", re.IGNORECASE)
_NOT_DRAWN = (
    (re.compile(r"\bprisms?\b|\bdispersion\b|\bspectrum\b|\brainbows?\b", re.I),
     "Dispersion is not drawn: one colour, one index per medium"),
    (re.compile(r"\blens(?:es)?\b", re.I), "A lens is its own simulation: this one is a flat boundary"),
    (re.compile(r"\boptical fib(?:re|er)s?\b", re.I), "Not drawn: an optical fibre (the boundary shows the reflection)"),
    (re.compile(r"\bapparent depth\b|\breal depth\b", re.I), "Apparent depth is not drawn"),
)


def _medium_of(text: str) -> Optional[str]:
    m = _MED_RX.search(text)
    return next(k for k, v in m.groupdict().items() if v) if m else None


def _val(s: str) -> Optional[float]:
    v = spoken_number(s)
    return v if v is not None and 1.0 <= v <= 3.0 else None


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    out: list[tuple[str, Any, str, int]] = []
    st = state or {}
    sides = {1: st.get("medium1", "air"), 2: st.get("medium2", "glass")}
    src = st.get("_src", {}) or {}
    known = {st.get(f"n{k}_of") or sides[k]: st.get(f"n{k}") for k in (1, 2)  # medium -> its index said
             if src.get(f"n{k}") == "said" and st.get(f"n{k}") is not None}
    m = _FROM_TO.search(line)
    if m:
        a, b = _medium_of(m.group("a")), _medium_of(m.group("b"))
        if a and b and a != b:
            out += [("medium1", a, m.group("a"), m.start("a")), ("medium2", b, m.group("b"), m.start("b"))]
            sides = {1: a, 2: b}
            for k, med in sides.items():  # an index said before goes with its medium to its new side
                if med in known and med not in STANDARD:
                    out += [(f"n{k}", float(known[med]), m.group(0), -1), (f"n{k}_of", med, m.group(0), m.start())]
    elif (m := _INTO.search(line)) is not None and (b := _medium_of(m.group("b"))) not in (None, "air", "vacuum"):
        out.append(("medium2", b, m.group("b"), m.start("b")))
        sides[2] = b
    spans: list[tuple[int, int]] = []
    hits = []  # (match, medium group text, side said) in the order: a medium named first, then the bare index
    for rx in (_MED_INDEX, _INDEX, _N_BARE):
        for m in rx.finditer(line):
            if any(a < m.end() and m.start() < b for a, b in spans):  # the same words, read already with their medium
                continue
            spans.append((m.start(), m.end()))
            gd = m.groupdict()
            hits.append((m, gd.get("m"), gd.get("s")))
            if rx is _MED_INDEX or (rx is _INDEX and gd.get("m")):
                pos = m.end()
                while (a := _AND_MED.match(line, pos)) is not None:  # "... and water 1.33"
                    hits.append((a, a.group("m"), None))
                    spans.append((a.start(), a.end()))
                    pos = a.end()
    for m, mtext, side in hits:
        if True:
            v = _val(m.group("v"))
            if v is None:
                continue
            who = _medium_of(mtext) if mtext else None
            if side:
                k = 1 if side.lower() in ("first", "incident") else 2
            else:
                k = 2 if who is None and v > 1 else next((s for s in (1, 2) if sides[s] == who), None)
            if who is not None and k is None:  # a medium not on the stage: its index is not this one's
                out.append(("!", f"Heard the index of {who}, not one of the two media drawn", m.group(0), m.start()))
                continue
            out += [(f"n{k}", v, m.group("v"), m.start("v")), (f"n{k}_of", sides[k], m.group("v"), m.start("v"))]
    for m in _N_SYM.finditer(line):
        v = _val(m.group("v"))
        if v is not None:
            k = 1 if m.group("k").lower() in ("1", "one") else 2
            out += [(f"n{k}", v, m.group("v"), m.start("v")), (f"n{k}_of", sides[k], m.group("v"), m.start("v"))]
    for rx, msg in _NOT_DRAWN:
        if (m := rx.search(line)) is not None:
            out.append(("!", msg, m.group(0), m.start()))
    return out


TEMPLATE = Template(
    id="refraction", name="Refraction: Snell's law", subject="optics",
    sim=RefractionSim, params=RefractionParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\brefraction of light\b|\bsnell'?s law\b|\blaws? of refraction\b|\btotal internal reflection\b|"
                     r"\b(?:light|a ray|the ray|a beam)\b[^.;]{0,40}\bfrom (?:air|water|glass|vacuum)\b[^.;]{0,20}"
                     r"\b(?:in)?to (?:the )?(?:air|water|glass|vacuum|oil|diamond)\b|"
                     r"\b(?:rectangular )?glass (?:slab|block)\b|"
                     r"\bcritical angle\b|\b(?:light|a ray|the ray|a beam)\b[^.;]{0,50}\b(?:refract\w*|bends?)\b|"
                     r"\brefract\w*\b[^.;]{0,50}\b(?:glass|water|boundary|interface|surface)\b", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:refract\w*|refractive|snell|normal|incidence|incident|ray|light|glass|water|denser|"
                       r"rarer|critical angle|total internal|bends?|boundary|interface|medium|media)\b", re.IGNORECASE),
    guard=re.compile(r"\brefractory\b|\brefraction of (?:sound|waves? in|water waves)\b|\brefractive (?:surgery|error)\b|"
                     r"\bcritical angle (?:of attack|for (?:landslides|slopes|stall)|of repose)\b|\bangle of attack\b|"
                     r"\bwater waves\b|\bseismic waves?\b|\bsound waves?\b|"
                     r"\b(?:eye|vision|spectacles|myopia)\b|\bseismic\b", re.IGNORECASE),
    aliases=("refraction", "snell", "snell's law", "total internal reflection", "critical angle", "refractive index"),
    parse=parse, listens=r"\brefractive index\b|\bindex of refraction\b|\bn ?[12] ?=|\bfrom \w+ (?:in)?to\b|"
                         r"\bprisms?\b|\bdispersion\b|\blens(?:es)?\b|\boptical fib(?:re|er)s?\b|\bapparent depth\b",
    results=re.compile(r"\b(?:angle of refraction|refracted angle|refracted ray|critical angle|angle of reflection|"
                       r"reflected|theta ?2|r\b|deviation)\b", re.IGNORECASE),
)
