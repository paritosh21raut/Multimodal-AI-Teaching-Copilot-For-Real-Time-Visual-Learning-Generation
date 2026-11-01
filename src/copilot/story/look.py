"""Character looks and name tags (ADR-0015 §7; user look round 2026-11-02). Deterministic, kept across lines.

    name tag   only a named person ("Arun", "Geeta", "Newton"): the capitalised words of the said name that are not
               articles or common nouns; never "the boy", "his friend", a horse, a tree or a house
    main       a named person, or one person who acts (actor / target of an event): each main gets a distinct look:
               shirt colour by order of appearance, hair style by order among mains of the same kind, and a cap or
               glasses from the third look-alike on
    supporting the rest ("two boys", "the villagers"): one plain shared look, so the mains stand out
    age        a child noun (boy, girl, child) = shorter; "old" / grandpa = grey hair and a slight stoop
    gender     only from said words (ST2 rule): long hair or a dress only for a "she"; unknown = neutral short hair
"""
from __future__ import annotations

import re
from typing import Any

from copilot.story import world as W

CHILD = {"boy", "girl", "child", "kid", "baby", "boys", "girls", "children", "kids"}
OLD = {"old", "grandpa", "grandma", "grandfather", "grandmother", "elderly"}
COMMON = W._HE_NOUNS | W._SHE_NOUNS | {
    "friend", "friends", "teacher", "farmer", "people", "child", "children", "boys", "girls", "men", "women", "person",
    "student", "students", "doctor", "soldier", "soldiers", "merchant", "villager", "villagers", "stranger", "lady",
    "ladies", "kid", "kids", "baby", "scientist", "sage", "monk", "thief", "hunter", "fisherman", "shopkeeper"}
FILLER = {"the", "a", "an", "his", "her", "their", "my", "our", "your", "its", "this", "that", "these", "those",
          "old", "young", "little", "two", "three", "four", "five", "some", "many", "other", "few", "several", "both",
          "all", "one", "mr", "mrs", "ms", "dr", "sir", "madam", "and", "of", "with"}
PLURAL = {"two", "three", "four", "five", "six", "some", "many", "other", "others", "few", "several", "both", "all"}
SHIRTS = ("#2c6fb5", "#d1495b", "#2a9d8f", "#8e5bd6", "#e07a1f", "#3d8b37")
EXTRA_SHIRT = "#8a929c"
HAIR = {"he": ("short", "spiky", "side", "curly"), "she": ("ponytail", "bun", "long", "braid"),
        "": ("short", "side", "curly", "spiky")}
ACCESSORY = ("", "", "cap", "glasses")
CHILD_SCALE, STOOP = 0.74, 0.16


def label(e: W.Entity) -> str:
    """The name tag: a famous person's name, or the capitalised name words of the said name ("her brother Arun" ->
    "Arun"); "" for everyone else and for anything that is not a person."""
    if e.kind != "person":
        return ""
    if e.known:
        return e.known.title()
    toks = re.findall(r"[A-Za-z][A-Za-z'-]*", e.name)
    return " ".join(w for w in toks if w[0].isupper() and w.lower() not in FILLER | COMMON)


def plural(e: W.Entity) -> bool:
    ws = set(W.words(e.name))
    noun = e.noun.lower()
    return bool(ws & PLURAL) or (noun in COMMON and noun.endswith("s") and not noun.endswith("ss"))


class Looks:
    def __init__(self) -> None:
        self.looks: dict[str, dict[str, Any]] = {}
        self.main: list[str] = []          # in order of becoming main (shirt colour index)

    def update(self, world: W.World) -> dict[str, dict[str, Any]]:
        acting = {x for ev in world.events for x in (ev.actor, ev.target) if x}
        for e in world.entities.values():
            if e.kind != "person":
                continue
            main = bool(label(e)) or (e.id in acting and not plural(e)) or e.id in self.main
            if main and e.id not in self.main:
                self.main.append(e.id)
                self.looks.pop(e.id, None)   # an extra who now acts gets a main look
            if e.id not in self.looks:
                self.looks[e.id] = self._make(e, main, world)
        return self.looks

    def _make(self, e: W.Entity, main: bool, world: W.World) -> dict[str, Any]:
        ws = set(W.words(e.name)) | {e.noun.lower()}
        child, old, g = bool(ws & CHILD), bool(ws & OLD), e.gender
        look = {"main": main, "label": label(e), "shirt": EXTRA_SHIRT, "hair": HAIR[g][0] if g != "she" else "bun",
                "hair_col": "grey" if old else "dark", "dress": g == "she", "acc": "",
                "scale": CHILD_SCALE if child else 1.0, "stoop": STOOP if old else 0.0}
        if not main:
            return look
        kind = (g, child)
        same = [i for i in self.main if i in self.looks and i != e.id and self.looks[i]["kind"] == list(kind)]
        n = sum(1 for i in self.main if i in self.looks and self.looks[i]["main"])
        look.update(shirt=SHIRTS[n % len(SHIRTS)], hair=HAIR[g][len(same) % 4], acc=ACCESSORY[len(same) % 4])
        if old and g == "he" and not look["acc"]:
            look["acc"] = "beard"
        look["kind"] = list(kind)
        return look
