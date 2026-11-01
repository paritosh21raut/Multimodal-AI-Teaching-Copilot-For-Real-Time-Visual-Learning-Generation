"""The story world (ADR-0015, docs/v3/P0-animation-proof.md): what is in the story now, kept across lines. The LLM
states a DELTA against it (scene_llm.py); Python validates the delta whole or not at all and applies it; the
compiler (P0 part 2) turns the world + the delta's events into placements and timed motion.

    entities   person / animal / prop / place / group / agent; the said name; a known person ("newton") only when
               said; posture; gender only from said words (ST2 rule)
    relations  (a, rel, b[, c]) from a closed set; the previous line's relations stay until changed
    events     this line's ops (closed set); the said verb kept as metadata; an unmapped verb = op "none" (the actor
               stays, the line is a caption), never a guessed gesture
    revision   +1 per applied delta; a delta made against an older revision is stale and dropped
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional

KINDS = ("person", "animal", "prop", "place", "group", "agent")
POSTURES = ("stand", "sit", "lie", "kneel", "crouch")
MODES = ("hold", "ride", "sit_on", "in")
FEELINGS = ("surprise", "happy", "sad", "angry", "scared", "think")
SPATIAL = ("on", "under", "in", "next_to", "above", "behind", "in_front", "between", "towards", "away_from")
ATTACH = ("hold", "ride", "sit_on")  # attachments live in the relation list too: "in" is both
RELATIONS = SPATIAL + ATTACH
OPS = ("enter", "exit", "move_to", "follow_path", "change_posture", "attach", "detach", "fall", "throw", "look_at",
       "point_at", "speak", "react", "work", "none")
KNOWN = ("newton", "einstein", "curie", "napoleon", "gandhi", "galileo", "darwin", "tesla", "edison", "archimedes",
         "shakespeare", "columbus")
PARTS = ("head", "hand", "back", "feet", "ground")
_TARGET_OPS = ("move_to", "fall", "throw", "look_at", "point_at", "speak", "work", "attach", "enter", "exit")
_LOCATING = ("on", "under", "in", "next_to", "above", "behind", "in_front", "between", "sit_on", "ride")


def words(s: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", s.lower())


def said(part: str, line: str) -> bool:
    """`part` is a run of whole words of the line (case and punctuation aside)."""
    want, have = words(part), words(line)
    return bool(want) and any(have[i:i + len(want)] == want for i in range(len(have) - len(want) + 1))


@dataclass
class Entity:
    id: str
    kind: str
    name: str                # as said: "an apple tree", "his friend"
    noun: str = ""           # its head noun ("tree", "friend")
    known: str = ""          # a famous person, only when said ("newton")
    gender: str = ""         # "he" / "she" only from said words
    posture: str = "stand"

    def summary(self) -> str:
        extra = f" known={self.known}" if self.known else ""
        return f"{self.id} {self.kind} \"{self.name}\" ({self.posture}){extra}"


@dataclass(frozen=True)
class Relation:
    a: str
    rel: str
    b: str
    c: str = ""              # "between" only

    def summary(self) -> str:
        return f"{self.a} {self.rel} {self.b}" + (f" {self.c}" if self.c else "")


@dataclass
class Event:
    op: str
    actor: str
    target: str = ""         # an entity id
    obj: str = ""            # throw / attach / work: the thing acted with or on
    value: str = ""          # posture / mode / feeling / body part / the spoken words
    verb: str = ""           # the said verb (metadata)


@dataclass
class Delta:
    rev: int
    new: list[Entity] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    relations: list[Relation] = field(default_factory=list)
    end: list[Relation] = field(default_factory=list)


@dataclass
class World:
    entities: dict[str, Entity] = field(default_factory=dict)
    relations: list[Relation] = field(default_factory=list)
    rev: int = 0
    events: list[Event] = field(default_factory=list)   # the last applied line's events

    def summary(self) -> str:
        """The bounded world text the prompt carries (never the transcript)."""
        ents = "\n".join(e.summary() for e in self.entities.values()) or "(empty)"
        rels = "; ".join(r.summary() for r in self.relations) or "(none)"
        return f"rev {self.rev}\nentities:\n{ents}\nrelations: {rels}"

    def next_id(self, taken: set[str]) -> str:
        n = len(self.entities) + 1
        while f"e{n}" in self.entities or f"e{n}" in taken:
            n += 1
        return f"e{n}"

    # ---- apply ---------------------------------------------------------------------------------------------------
    def apply(self, d: Delta) -> bool:
        """Apply a validated delta. False = stale (made against an older revision): nothing changes."""
        if d.rev != self.rev:
            return False
        for e in d.new:
            self.entities[e.id] = e
        for r in d.end:
            self._drop(lambda x, r=r: x.a == r.a and x.rel == r.rel and x.b == r.b)
        for ev in d.events:
            self._event(ev)
        # one place at a time: a new location replaces the old one (riding moves him off the bench); the line's own
        # relations all stay ("sat on the bench under the tree" = two): drop first for every actor, then add
        placed = {r.a for r in d.relations if r.rel in _LOCATING}
        heading = {r.a for r in d.relations if r.rel in ("towards", "away_from")}
        self._drop(lambda x: (x.a in placed and x.rel in _LOCATING)
                   or (x.a in heading and x.rel in ("towards", "away_from")))
        for r in d.relations:
            if r not in self.relations:
                self.relations.append(r)
        self.events = list(d.events)
        self.rev += 1
        return True

    def _drop(self, pred) -> None:
        self.relations = [x for x in self.relations if not pred(x)]

    def _event(self, ev: Event) -> None:
        a = self.entities[ev.actor]
        if ev.op == "change_posture":
            a.posture = ev.value
        elif ev.op in ("move_to", "exit", "enter", "follow_path"):
            self._drop(lambda x: x.a == ev.actor and x.rel in _LOCATING + ("towards", "away_from"))
        elif ev.op == "detach":
            self._drop(lambda x: x.a == ev.actor and (x.rel in ATTACH if not ev.target  # review: not his room
                                                      else x.rel in ATTACH + ("in", "on") and x.b == ev.target))
        elif ev.op == "fall":  # it leaves where it hung / was held; it lands on the target
            self._drop(lambda x: (x.a == ev.actor and x.rel in _LOCATING) or (x.rel == "hold" and x.b == ev.actor))
        elif ev.op == "throw" and ev.obj:
            self._drop(lambda x: x.rel == "hold" and x.b == ev.obj)
        elif ev.op == "attach" and ev.target:
            rel = {"hold": "hold", "ride": "ride", "sit_on": "sit_on", "in": "in"}[ev.value]
            a_, b_ = (ev.actor, ev.target)
            self._drop(lambda x: x.a == a_ and x.rel in _LOCATING and rel != "hold")
            r = Relation(a_, rel, b_)
            if r not in self.relations:
                self.relations.append(r)
            if rel in ("ride", "sit_on"):
                a.posture = "sit"


# ---- validate ------------------------------------------------------------------------------------------------------
def validate(ans: Any, world: World, line: str) -> tuple[Optional[Delta], str]:
    """The model's JSON -> a Delta, whole or not at all (reason on refusal). Ids exist (or are new), ops / relations /
    postures / modes / feelings closed, names and spoken words are spans of THIS line, a known person said."""
    if not isinstance(ans, dict):
        return None, "not an object"
    rev = ans.get("rev", world.rev)
    if type(rev) is not int:
        return None, "rev"
    for k in ("new", "events", "relations", "end"):
        if not isinstance(ans.get(k) or [], list):
            return None, f"{k}: not a list"
    new: list[Entity] = []
    ids = set(world.entities)
    for raw in ans.get("new") or []:
        if not isinstance(raw, dict):
            return None, "new: not an object"
        eid, kind, name = str(raw.get("id", "")), str(raw.get("kind", "")), str(raw.get("name", "")).strip()
        if not eid or eid in ids:
            return None, f"new id {eid!r} taken"
        if kind not in KINDS:
            return None, f"kind {kind!r}"
        if not said(name, line):
            return None, f"name {name!r} not said"
        noun = str(raw.get("noun", "") or (words(name)[-1] if words(name) else ""))
        if not said(noun, line):
            noun = words(name)[-1]
        known = str(raw.get("known", "") or "").lower()
        if known and (known not in KNOWN or known not in words(line)):
            known = ""  # a famous head only when the line names the person
        gender = str(raw.get("gender", "") or "")
        if gender not in ("he", "she") or not _gender_said(gender, name):
            gender = ""
        posture = str(raw.get("posture", "") or "stand")
        if posture not in POSTURES:
            return None, f"posture {posture!r}"
        new.append(Entity(eid, kind, name, noun, known, gender, posture))
        ids.add(eid)
    events: list[Event] = []
    for raw in ans.get("events") or []:
        ev, why = _event(raw, ids, line)
        if ev is None:
            return None, why
        events.append(ev)
    rels: list[Relation] = []
    for key in ("relations", "end"):
        out: list[Relation] = []
        for raw in ans.get(key) or []:
            r, why = _relation(raw, ids)
            if r is None:
                return None, f"{key}: {why}"
            out.append(r)
        rels.append(out)  # type: ignore[arg-type]
    if not new and not events and not rels[0] and not rels[1]:
        return None, "empty"
    return Delta(rev, new, events, rels[0], rels[1]), ""


_HE_NOUNS = {"man", "boy", "king", "father", "brother", "husband", "grandpa", "son", "uncle", "prince", "knight"}
_SHE_NOUNS = {"woman", "girl", "queen", "mother", "sister", "wife", "grandma", "daughter", "aunt", "princess"}


def _gender_said(g: str, name: str) -> bool:
    """Only its own name says it ("the old man"; review: "The man gave her a book" never makes the man a she). A
    pronoun naming an earlier person is the cast's job (ST2 rules), wired in P1."""
    return bool(set(words(name)) & (_HE_NOUNS if g == "he" else _SHE_NOUNS))


def _event(raw: Any, ids: set[str], line: str) -> tuple[Optional[Event], str]:
    if not isinstance(raw, dict):
        return None, "event: not an object"
    op = str(raw.get("op", ""))
    if op not in OPS:
        return None, f"op {op!r}"
    actor = str(raw.get("actor", ""))
    if actor not in ids:
        return None, f"{op}: actor {actor!r} unknown"
    target, obj = str(raw.get("target", "") or ""), str(raw.get("obj", "") or "")
    for x in (target, obj):
        if x and x not in ids:
            return None, f"{op}: id {x!r} unknown"
    value = str(raw.get("value", "") or "")
    verb = str(raw.get("verb", "") or "")
    if verb and not said(verb, line):
        verb = ""
    allowed = {"change_posture": POSTURES, "attach": MODES, "react": FEELINGS}.get(op)
    if allowed is not None and value not in allowed:
        return None, f"{op}: value {value!r}"
    if op == "fall" and value and value not in PARTS:
        return None, f"fall: part {value!r}"
    if op == "speak" and value and not said(value, line):
        return None, "speak: words not said"
    if op in ("attach", "throw", "look_at", "point_at") and not (target or obj):
        return None, f"{op}: no target"
    if op == "attach" and not target:
        target = obj
    return Event(op, actor, target, obj, value, verb), ""


def _relation(raw: Any, ids: set[str]) -> tuple[Optional[Relation], str]:
    if not isinstance(raw, dict):
        return None, "not an object"
    a, rel, b, c = (str(raw.get(k, "") or "") for k in ("a", "rel", "b", "c"))
    if rel not in RELATIONS:
        return None, f"rel {rel!r}"
    if a not in ids or b not in ids or (c and c not in ids) or a == b:
        return None, f"ids {a!r} {b!r} {c!r}"
    if rel == "between" and (not c or c in (a, b)):
        return None, "between needs two others"
    return Relation(a, rel, b, c if rel == "between" else ""), ""
