"""The stage catalog (contract §9) for Python: which kit row, species or cast row draws a said noun, and its size.

    config/stage_catalog.json   props, backdrops, species (names, size_m, anchors)
    config/stage_cast.json      the 12 people

A person noun picks a cast row by sex / age (the first not yet on the stage, in file order: deterministic). A surface
noun with no prop row (floor, ground, road) is the backdrop's ground line: drawn by the backdrop, not as a prop.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[3]
CATALOG = ROOT / "config" / "stage_catalog.json"
CAST = ROOT / "config" / "stage_cast.json"

# noun -> (sex: m / f / None, child, elder)
PEOPLE: dict[str, tuple[Optional[str], bool, bool]] = {
    **{w: ("m", False, False) for w in ("man", "father", "dad", "husband", "uncle", "brother", "boyfriend", "gentleman",
                                        "he", "him", "sir", "king", "farmer", "driver", "worker", "player")},
    **{w: ("f", False, False) for w in ("woman", "mother", "mom", "mum", "wife", "aunt", "sister", "lady", "she",
                                        "her", "queen", "madam")},
    **{w: ("m", True, False) for w in ("boy", "son", "schoolboy")},
    **{w: ("f", True, False) for w in ("girl", "daughter", "schoolgirl")},
    **{w: (None, True, False) for w in ("child", "kid", "baby", "toddler", "student", "pupil")},
    **{w: ("m", False, True) for w in ("grandfather", "grandpa", "old man")},
    **{w: ("f", False, True) for w in ("grandmother", "grandma", "old woman")},
    **{w: (None, False, False) for w in ("person", "teacher", "people", "someone", "athlete", "runner", "swimmer",
                                         "astronaut", "passenger", "friend", "team")},
}
GROUND = ("floor", "ground", "road", "street", "grass", "ice", "carpet", "earth", "field", "surface", "track", "path",
          "pavement", "concrete", "sand", "mud")
FLUIDS = ("water", "oil", "sea", "river", "pool", "pond", "lake", "liquid", "mercury")


@dataclass(frozen=True)
class Draw:
    draw: str            # kit id | cast:<row> | species:<name> | ground | backdrop:<id> | fluid
    size: tuple[float, float]
    row: dict[str, Any]


@lru_cache(maxsize=1)
def catalog() -> dict[str, Any]:
    return json.loads(CATALOG.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def cast() -> dict[str, dict[str, Any]]:
    return {c["id"]: c for c in json.loads(CAST.read_text(encoding="utf-8"))["cast"]}


def _norm(w: str) -> str:
    return " ".join(w.lower().strip().split())


def _forms(w: str) -> list[str]:
    w = _norm(w)
    out = [w]
    if w.endswith("ies"):
        out.append(w[:-3] + "y")
    if w.endswith("es"):
        out.append(w[:-2])
    if w.endswith("s"):
        out.append(w[:-1])
    if " " in w:
        out += _forms(w.split()[-1])  # "wooden box" -> box
    return out


def _row(kind: str, w: str) -> Optional[dict[str, Any]]:
    for f in _forms(w):
        for r in catalog()[kind]:
            if f == r["id"] or f in r["names"]:
                return r
    return None


def prop(w: str) -> Optional[dict[str, Any]]:
    return _row("props", w)


def species(w: str) -> Optional[dict[str, Any]]:
    return _row("species", w)


def backdrop(w: str) -> Optional[dict[str, Any]]:
    return _row("backdrops", w)


def person(w: str) -> Optional[tuple[Optional[str], bool, bool]]:
    for f in _forms(w):
        if f in PEOPLE:
            return PEOPLE[f]
    return None


def known(w: str) -> bool:
    """A noun the stage can draw (a `near` noun must be one: contract §6)."""
    f = _norm(w)
    return bool(prop(f) or species(f) or backdrop(f) or person(f) or any(g in _forms(f) for g in GROUND + FLUIDS))


def pick_cast(w: str, attr: list[str], used: set[str]) -> Optional[str]:
    """The cast row for a person noun: sex / child / elder from the noun and attrs (child, old); the first free row."""
    p = person(w)
    if p is None:
        return None
    sex, child, elder = p
    a = {x.lower() for x in attr}
    child = child or bool(a & {"child", "young", "little", "small", "kid"})
    elder = elder or bool(a & {"old", "elderly", "aged"})
    sex = sex or ("f" if a & {"female", "woman", "girl"} else "m" if a & {"male", "man", "boy"} else None)
    rows = list(cast().values())

    def fits(c):
        is_elder = c["id"].startswith("elder")
        return (sex is None or c["sex"] == sex) and c["child"] == child and is_elder == elder

    for c in rows:
        if fits(c) and c["id"] not in used:
            return c["id"]
    return next((c["id"] for c in rows if fits(c)), None)


def resolve(kind: str, w: str, near: Optional[str], attr: list[str], used_cast: set[str]) -> Optional[Draw]:
    """What draws an entity: the said noun first, else its `near` stand-in noun; None = nothing can draw it."""
    for noun in [w] + ([near] if near else []):
        if not noun:
            continue
        if kind == "agent":
            cid = pick_cast(noun, attr, used_cast)
            if cid:
                c = cast()[cid]
                return Draw(f"cast:{cid}", (0.45 * c["height_m"] / 1.75, c["height_m"]), c)
            continue
        if kind == "animal":
            r = species(noun)
            if r:
                return Draw(f"species:{r['id']}", tuple(r["size_m"]), r)
            continue
        if kind == "place":
            r = backdrop(noun)
            if r:
                return Draw(f"backdrop:{r['id']}", (0.0, 0.0), r)
            continue
        r = prop(noun)
        if r:
            return Draw(r["id"], tuple(r["size_m"]), r)
        forms = _forms(noun)
        if kind == "surface" and any(g in forms for g in GROUND):
            return Draw("ground", (0.0, 0.0), {})
        if any(f in forms for f in FLUIDS):
            return Draw("fluid", (0.0, 0.0), {})
    return None
