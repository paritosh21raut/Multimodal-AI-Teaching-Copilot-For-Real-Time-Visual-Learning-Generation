"""A thin lens: the image of an object, the three principal rays (F-014 S4). Renderer: web/sims/thin_lens.js.

An object of height h stands at distance u in front of a thin lens of focal length f (convex: converging; concave:
diverging). Distances as sizes (no sign convention is imposed on the class; the side is said in words):

    1/v = 1/f' − 1/u   with f' = +f (convex), −f (concave):  v > 0 the image is on the other side (real),
                       v < 0 on the object's side (virtual);  u = f (convex): the rays leave parallel (at infinity)
    m = −v / u  (m < 0 inverted, |m| > 1 magnified),  image height h' = |m| h,  power P = 1 / f' (f in metres, D)

    convex f 10 cm, u 30 cm: v 15 cm other side (real), m −0.5 (inverted, smaller);  u 15 cm: v 30 cm, m −2;
    u 5 cm: v 10 cm on the object's side (virtual), m 2 (upright, magnified);  concave f 10 cm, u 30 cm: v 7.5 cm
    object's side (virtual), m 0.25 (upright, smaller)

Truthfulness: f, u and h print only when said; the image distance and the magnification only with f and u said, the
image height with h too; the lens kind is drawn convex until said ("a concave lens"), and named only when said. The
picture is to scale along the axis; the heights are drawn on their own scale (the object a fixed height).
"""
from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import Field

from copilot.simulation.base import Derived, Element, SimBase, SimLabel, Slot, Solution, Template, _Model, fmt
from copilot.simulation.values import spoken_number

SLOTS = (
    Slot("f_m", "Focal length", "f", "m", 0.01, 5.0, 0.01, 0.1, "length"),
    Slot("u_m", "Object distance", "u", "m", 0.01, 10.0, 0.01, 0.3, "length"),
    Slot("h_m", "Object height", "h", "m", 0.001, 2.0, 0.001, 0.02, "length"),
)
ELEMENTS = (
    Element("lens", "Lens"), Element("object", "Object"), Element("rays", "Rays"), Element("image", "Image"),
    Element("foci", "Focal points"), Element("readout", "Values"),
)
HALF_PX = 470      # the axis from the lens to either side, in stage px
AT_INF = 1e-9
FAR = 1000.0       # an image farther than this many times f or u counts as at infinity


class ThinLensParams(_Model):
    f_m: float = Field(default=0.1, ge=0.01, le=5.0)
    u_m: float = Field(default=0.3, ge=0.01, le=10.0)
    h_m: float = Field(default=0.02, ge=0.001, le=2.0)
    lens: Literal["convex", "concave"] = "convex"


class ThinLensSim(SimBase):
    template: Literal["thin_lens"] = "thin_lens"
    params: ThinLensParams = Field(default_factory=ThinLensParams)
    ELEMENTS = tuple(e.id for e in ELEMENTS)
    LABELS = ("lens", "f", "u", "h", "v", "note")


def image(f: float, u: float, convex: bool) -> tuple[Optional[float], Optional[float]]:
    """(v, m); v None when the image is at infinity (object at the focus of a convex lens)."""
    fs = f if convex else -f
    inv = 1 / fs - 1 / u
    if abs(inv) < AT_INF * max(1 / f, 1 / u) or abs(1 / inv) > FAR * max(f, u):
        return None, None  # at the focus, or so near it that the image is beyond any printed distance
    v = 1 / inv
    return v, -v / u


def cm(x: float) -> str:
    """A length as a teacher says it: cm below a metre ("15 cm", "7.5 cm"), else m."""
    return f"{fmt(x * 100)} cm" if abs(x) < 1 else f"{fmt(x)} m"


def signed(x: float) -> str:
    """A Cartesian distance: "+15 cm", "−30 cm" (light travels left to right, distances from the lens)."""
    return ("+" if x > 0 else "−") + cm(abs(x))


def solve(p: ThinLensParams, src: dict[str, str]) -> Solution:
    said = lambda n: src.get(n, "default") in ("said", "teacher", "computed")  # noqa: E731
    convex = p.lens == "convex"
    v, m = image(p.f_m, p.u_m, convex)
    kind_said = said("lens")
    ok = said("f_m") and said("u_m") and kind_said  # the default kind (convex) is drawn, never worked from
    labels = {
        "lens": SimLabel(symbol=f"{p.lens} lens" if kind_said else ""),
        "f": SimLabel(symbol="f", text=signed(p.f_m if convex else -p.f_m) if kind_said else cm(p.f_m),
                      source=src["f_m"]) if said("f_m") else SimLabel(symbol="f"),  # type: ignore[arg-type]
        "u": SimLabel(symbol="u", text=signed(-p.u_m), source=src["u_m"]) if said("u_m") else SimLabel(symbol="u"),  # type: ignore[arg-type]
        "h": SimLabel(symbol="h", text=cm(p.h_m), source=src["h_m"]) if said("h_m") else SimLabel(symbol="h"),  # type: ignore[arg-type]
        "v": SimLabel(symbol="v", text=signed(v), source="computed") if ok and v is not None else SimLabel(symbol="v"),
        "note": SimLabel(symbol=""),
    }
    derived: list[Derived] = []
    if ok and v is None:
        derived.append(Derived(id="v", label="Image", symbol="image", value=-1.0,
                               text="at infinity (the rays leave parallel)"))
    elif ok and v is not None and m is not None:
        side = "other side (real)" if v > 0 else "object's side (virtual)"
        derived.append(Derived(id="v", label="Image distance", symbol="v", value=abs(v), unit="m",
                               text=f"{signed(v)}, {side}"))
        same = fmt(abs(m)) == "1"  # as printed: 1.0000001 is "same size", not "magnified"
        how = ("inverted" if m < 0 else "upright") + ", " + \
            ("same size" if same else "magnified" if abs(m) > 1 else "smaller")
        derived.append(Derived(id="m", label="Magnification", symbol="m", value=m,
                               text=f"{fmt(m).replace('-', '−')} ({how})"))
        if said("h_m"):
            derived.append(Derived(id="h2", label="Image height", symbol="h′", value=abs(m) * p.h_m, unit="m",
                                   text=cm(abs(m) * p.h_m)))
    if said("f_m") and kind_said:
        pw = (1 if convex else -1) / p.f_m
        derived.append(Derived(id="power", label="Power", symbol="P", value=pw, unit="D",
                               text=f"{fmt(pw).replace('-', '−')} D"))
    # the axis to scale: the object, the image (when near enough) and both foci fit on their side
    far = max(p.u_m, 2 * p.f_m, abs(v) if v is not None and abs(v) < 4 * max(p.u_m, p.f_m) else 0.0) * 1.1
    drive = {"px_m": HALF_PX / far, "f": p.f_m, "u": p.u_m, "v": v if v is not None else 0.0,
             "inf": 1.0 if v is None else 0.0, "m": m if m is not None else 0.0, "convex": 1.0 if convex else 0.0,
             "still_t": 1.6}
    return Solution(drive=drive, labels=labels, derived=derived)


def default_shown(p: ThinLensParams, src: dict[str, str]) -> list[str]:
    return ["lens", "object", "rays", "image", "foci", "readout"]


# ---- speech: the lens kind, f / u / h by their words, a power in dioptres, notices -----------------------------------
_KIND = re.compile(r"\b(?P<k>convex|converging|concave|diverging|biconvex|bi-convex|biconcave|bi-concave|plano-?convex|"
                   r"plano-?concave)\s+lens\b", re.IGNORECASE)
_F = re.compile(r"\b(?:focal length|f)\s*(?:of|is|=|equal to|equals)?\s*(?:the lens\s*(?:is\s*)?)?(?:about\s+)?$", re.I)
_H = re.compile(r"\b(?:height|tall|high|size)\b[^.;,]{0,20}$|\bobject of height\s*$", re.IGNORECASE)
_H_AFTER = re.compile(r"^\s*(?:tall|high)\b", re.IGNORECASE)
_U = re.compile(r"(?:\b(?:placed|kept|put|held|stands?|at|object distance|distance of|u is|object|bring|brought|"
                r"(?:mov|shift)\w*(?:\s+\w+){0,3}\s+to)\b|\bu\s*=)[^.;,]{0,25}$", re.IGNORECASE)
_U_STRONG = re.compile(r"\b(?:placed|kept|put|(?<!of the )object|object distance|u is)\b|\bu\s*=", re.IGNORECASE)
_SHIFT = re.compile(r"^\s*(?:closer|further|farther|nearer|towards|toward|back|away from|more|less)\b", re.IGNORECASE)
_U_AFTER = re.compile(r"^\s*(?:away\b|(?:away\s+)?(?:from|in front of)\s+(?:the|a|an)\s+(?:\w+\s+)?lens\b)",
                      re.IGNORECASE)
_IMAGE = re.compile(r"(?:\b(?:image|screen|v is)\b|\bv\s*=)[^.;,]{0,25}$", re.IGNORECASE)  # a result, or where it forms  # "the image forms at 15 cm": a result
_POWER = re.compile(r"(?P<neg>minus |negative |-|−)?(?P<v>\d+(?:\.\d+)?|one|two|three|four|five|ten)\s*"
                    r"(?:dioptres?|diopters?|D\b)", re.IGNORECASE)
_NOT_DRAWN = (
    (re.compile(r"\bmirrors?\b", re.I), "Mirrors are not drawn: this is a lens"),
    (re.compile(r"\blens ?maker'?s?\b|\bradius of curvature\b|\bradii of curvature\b", re.I),
     "The lens maker's formula is not drawn: the lens is set by its focal length"),
    (re.compile(r"\b(?:combination of (?:two )?lenses|two lenses|lenses in contact|microscope|telescope)\b", re.I),
     "One lens is drawn: combinations are not"),
)


def parse(line: str, items: list[Any], state: Optional[dict] = None) -> list[tuple[str, Any, str, int]]:
    out: list[tuple[str, Any, str, int]] = []
    if (k := _KIND.search(line)) is not None:
        word = k.group("k").lower()
        out.append(("lens", "concave" if ("conca" in word or "diverg" in word) else "convex", k.group(0), k.start()))
    for h in items:
        if h.start < 0:
            continue
        if h.kind != "length":
            out.append(("~", None, h.said, h.start))  # not a length: not this simulation's
            continue
        # its words: since the sentence began and since the number before it ("2 cm tall and placed 30 cm")
        prev = max((x.start + len(x.said) for x in items if 0 <= x.start < h.start), default=0)
        before = line[max(prev, line.rfind(".", 0, h.start) + 1):h.start]
        before = _H_AFTER.sub("", before) if prev else before  # "tall" there was the number before's
        after = line[h.start + len(h.said):]
        sign = re.search(r"(?:minus|negative|plus|positive|-|−|\+)\s*$", before, re.IGNORECASE)
        neg = h.value < 0 or bool(sign and sign.group(0).strip().lower() in ("minus", "negative", "-", "−"))
        size = abs(h.value)
        before = re.sub(r"\s*(?:minus|negative|plus|positive|-|−|\+)\s*$", " ", before, flags=re.IGNORECASE)
        mi, mu = _IMAGE.search(before), _U.search(before)
        strong = [x.start() for x in _U_STRONG.finditer(before)]
        if re.search(r"\bscreen\b[^.;,]{0,25}$", before, re.IGNORECASE):  # where the image is caught: not u
            out.append(("~", None, h.said, h.start))
        elif mi and not (strong and strong[-1] > mi.start()):  # "for a real image place the object at 30 cm": u
            out.append(("~", None, h.said, h.start))
        elif _F.search(before):
            # Cartesian: "f = -20 cm" / "minus 20 cm" is a concave lens of 20 cm, "f = +10 cm" a convex one
            out += [("f_m", size, h.said, -1), ("~", None, h.said, h.start)]
            if neg or sign:
                out.append(("lens", "concave" if neg else "convex", h.said, h.start))
        elif _H.search(before) or _H_AFTER.match(after):
            out += [("h_m", size, h.said, -1), ("~", None, h.said, h.start)]
        elif _SHIFT.match(after):  # "moved 5 cm closer": a shift, not where it is
            out.append(("~", None, h.said, h.start))
        elif mu or _U_AFTER.match(after):  # Cartesian "u = -30 cm": the object 30 cm in front of the lens
            out += [("u_m", size, h.said, -1), ("~", None, h.said, h.start)]
        else:
            out.append(("~", None, h.said, h.start))  # a length said with nothing naming it: not guessed
    if (pm := _POWER.search(line)) is not None and (pv := spoken_number(pm.group("v"))):
        out.append(("f_m", 1 / pv, pm.group(0), pm.start()))
        out.append(("lens", "concave" if pm.group("neg") else "convex", pm.group(0), pm.start()))
    for rx, msg in _NOT_DRAWN:
        if (m := rx.search(line)) is not None:
            out.append(("!", msg, m.group(0), m.start()))
    return out


TEMPLATE = Template(
    id="thin_lens", name="A thin lens: ray diagram", subject="optics",
    sim=ThinLensSim, params=ThinLensParams, slots=SLOTS, elements=ELEMENTS,
    solve=solve, default_shown=default_shown,  # type: ignore[arg-type]
    setup=re.compile(r"\b(?:convex|concave|converging|diverging|thin|biconvex|biconcave|plano-?convex|plano-?concave) "
                     r"lens(?:es)?\b|\blens formula\b|\bray diagrams?\b[^.;]{0,40}\blens\b|\bimage formed by (?:a |the )?"
                     r"(?:\w+ )?lens\b|\bmagnification (?:of|by) (?:a |the )?(?:\w+ )?lens\b", re.IGNORECASE),
    lexicon=re.compile(r"\b(?:lens|focal|focus|foci|image|object|ray|rays|real|virtual|inverted|erect|upright|"
                       r"magnif\w*|diminished|principal axis|optical cent(?:re|er)|dioptres?|diopters?|power)\b",
                       re.IGNORECASE),
    guard=re.compile(r"\bcontact lens(?:es)?\b|\bcamera lens(?:es)?\b|\b(?:through|from) (?:the|a) lens of\b|"
                     r"\blens of (?:history|economics|culture|policy)\b|\beye\b|\bspectacles\b|\bmyopia\b", re.IGNORECASE),
    aliases=("lens", "convex lens", "concave lens", "lens formula", "ray diagram", "thin lens"),
    parse=parse, listens=r"\b(?:convex|concave|converging|diverging) lens\b|\bdioptres?\b|\bdiopters?\b|\bmirrors?\b",
    results=re.compile(r"\b(?:image|magnification|v ?=|power)\b", re.IGNORECASE),
)
