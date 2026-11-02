"""Story scene compiler (ADR-0015 §4, docs/v3/P0-animation-proof.md part 2): the world + this line's events ->
a StorySceneSpec the browser plays (web/story/anim/). Deterministic, 0 tokens.

    places     metres on a 14 m stage, ground y = 0; the asset sidecars (web/story/anim/assets/*.json) give the
               anchors (canopy span, trunk, fruit, saddle, entrance), the same files the renderer draws from
    relations  -> placements: under a tree = on the ground inside the shade span, clear of the trunk; ride = the
               rider's pelvis on the saddle, the rider carried by the horse (one transform, never a gap); next_to,
               towards, in
    events     -> a timeline: posture change, mount, move (the carrier moves, its rider with it), fall (Python gives
               the start, the contact point and the contact time from g; the browser only evaluates the curve),
               speak (the two face each other, bubble at the speaker), react
    style      named embellishments only, marked "style" (hit_reacts: a hit on the head = a surprised reaction);
               never a story fact
    fallback   an op the engine has no motion for: the actor stays, the op is listed in "fallback" (logged), never a
               guessed gesture; a thing with no asset and no role is not drawn (an abstract word like "time")
    registry   story/ops.py gives each op's duration and sorts every event first (executable / unsupported / invalid /
               missing_asset, in spec["checks"]); an invalid event (ride a tree) never animates

Positions persist across lines (the Compiler keeps each entity's end place), so B starts where A ended.
"""
from __future__ import annotations

import json
import logging
import math
from dataclasses import asdict, dataclass, replace
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from copilot.story import ops as O
from copilot.story import world as W
from copilot.story.look import Looks

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "web" / "story" / "anim" / "assets"
G = 9.81
STAGE_W = 14.0
NOUN_ASSET = {"tree": "tree", "horse": "horse", "pony": "horse", "village": "village", "town": "village",
              "apple": "apple",
              # P1b fix round 1 (user: "just a white box"): the first drawn props, pulled from P2 Tier-1
              "stone": "stone", "stones": "stone", "rock": "stone", "pebble": "stone", "ball": "ball", "balls": "ball",
              "stick": "stick", "staff": "stick", "cane": "stick", "basket": "basket", "pot": "pot", "pots": "pot",
              "bucket": "pot", "buckets": "pot", "jar": "pot", "pail": "pot", "boat": "boat", "book": "book",
              "books": "book", "scroll": "book", "scrolls": "book", "cart": "cart", "wagon": "cart", "trolley": "cart"}
PROPS = ("stone", "ball", "stick", "basket", "pot", "boat", "book", "cart")
FRUIT = ("apple", "mango", "orange", "pear", "lemon", "cherry")
PLACE_SLOTS = (7.0, 3.0, 11.0)
T_START = 0.3


@lru_cache(maxsize=1)
def assets() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(ASSETS.glob("*.json"))}


def asset_for(e: W.Entity) -> str:
    if e.kind == "person":
        return "person"
    for w in W.words(f"{e.noun} {e.name}"):
        if w in NOUN_ASSET:
            return NOUN_ASSET[w]
    return ""


def fruit_of(e: W.Entity) -> str:
    """"an apple tree" -> apple (the tree's own name says the fruit)."""
    ws = W.words(e.name)
    return next((w for w in ws if w in FRUIT), "") if "tree" in ws else ""


@dataclass
class Place:
    x: float
    y: float = 0.0
    posture: str = "stand"
    facing: int = 1
    carrier: str = ""        # the id this one rides / sits on (its transform follows the carrier)
    anchor: str = ""         # the carrier's anchor ("saddle")
    fruit: int = -1          # a fruit spot of a tree this one hangs at (before it falls)
    tree: str = ""
    holder: str = ""         # P1b: the person holding this thing (it rides that person's hand)
    hand: int = 0            # which hand (0 = the near / right one, 1 = the other)
    gone: bool = False       # P1b: walked off the stage (not drawn until it comes back)
    comeback: bool = False   # this line it walks back in from the edge (enter with no place: to a free spot)
    on: str = ""             # what its feet stand / sit on above the ground (a branch, a box): jumping off leaves it
    # a person's y = the height its feet stand at (0 = the ground; a branch, a box top, mid-jump)


def pelvis_y(p: Place) -> float:
    person = assets()["person"]
    return person["pelvis"].get(p.posture, person["pelvis"]["stand"])


class Compiler:
    def __init__(self) -> None:
        self.at: dict[str, Place] = {}
        self.hidden: dict[str, list[int]] = {}   # tree id -> fruit spots already fallen
        self.parts: dict[str, set[str]] = {}     # id -> its optional parts a line said (a tree's branch); they stay
        self.looks = Looks()                      # per person: shirt, hair, size, name tag (look.py)

    def scale(self, eid: str) -> float:
        return self.looks.looks.get(eid, {}).get("scale", 1.0)

    # ---- geometry -----------------------------------------------------------------------------------------------
    def abs_pelvis(self, eid: str, at: dict[str, Place]) -> tuple[float, float]:
        p = at[eid]
        if p.carrier and p.carrier in at:
            c = at[p.carrier]
            sx, sy = assets()["horse"][p.anchor or "saddle"]
            return c.x + c.facing * sx, sy
        return p.x, pelvis_y(p) * self.scale(eid) + p.y

    def hand_at(self, eid: str, at: dict[str, Place], k: int = 0) -> tuple[float, float]:
        """Where a held thing sits: the carry anchor off the pelvis (person.json "carry"; rig.js uses the same)."""
        cx, cy = assets()["person"]["carry"][k]
        x, y = self.abs_pelvis(eid, at)
        p = at[eid]
        f = at[p.carrier].facing if p.carrier in at else p.facing
        s = self.scale(eid)
        return x + f * cx * s, y + cy * s

    def _sync_held(self, at: dict[str, Place]) -> None:
        for p in at.values():
            if p.holder and p.holder in at:
                p.x, p.y = self.hand_at(p.holder, at, p.hand)
                p.gone = at[p.holder].gone

    def head_top(self, eid: str, at: dict[str, Place]) -> tuple[float, float]:
        """The top of the head as the rig draws it: the torso and head lean by the posture's lean (person.json)."""
        person = assets()["person"]
        x, py = self.abs_pelvis(eid, at)
        p = at[eid]
        posture = "ride" if p.carrier else p.posture
        f = at[p.carrier].facing if p.carrier in at else p.facing
        k = self.scale(eid)
        lean = person["lean"][posture] + (self.looks.looks.get(eid, {}).get("stoop", 0.0) if posture == "stand" else 0)
        x += f * person["pelvis_dx"].get(posture, 0.0) * k
        reach = (person["torso"] + person["neck"] + person["head_r"]) * k
        return x + f * math.sin(lean) * reach, py + math.cos(lean) * reach + person["head_r"] * k

    # ---- compile ------------------------------------------------------------------------------------------------
    def compile(self, world: W.World, line: str) -> dict[str, Any]:
        world, part_of = self._said_parts(world, line)   # "sat on a branch": the tree's branch, not a box
        ents = world.entities
        events = list(world.events)
        # back on the stage (review): the one who comes back, its carrier / riders and what it holds walk in from the
        # nearer edge; whatever stays gone is left out of this line (not drawn, not a target) but kept in self.at
        back = {ev.actor for ev in events if ev.op in ("enter", "move_to", "follow_path")}
        for _ in range(2):
            back |= {k for k, v in self.at.items() if v.carrier in back or v.holder in back}
            back |= {v.carrier for k, v in self.at.items() if k in back and v.carrier}
        start: dict[str, Place] = {}
        for k, v in self.at.items():
            if k not in ents or (v.gone and k not in back):
                continue
            start[k] = replace(v)
            if v.gone:
                start[k].gone = False
                start[k].x = -0.9 if v.x < STAGE_W / 2 else STAGE_W + 0.9
                start[k].y = 0.0
                start[k].comeback = True
        roles = _roles(world)
        skipped: list[dict[str, str]] = []
        drawn: list[str] = []
        for e in ents.values():
            old = self.at.get(e.id)
            if old is not None and old.gone and e.id not in back:
                skipped.append({"id": e.id, "name": e.name, "why": "gone (left the stage)"})
            elif asset_for(e) or e.id in roles or e.id in self.at:   # once on the stage, it stays
                drawn.append(e.id)
            else:
                skipped.append({"id": e.id, "name": e.name, "why": "no asset, no role"})
        skipped += [{"id": k, "name": n, "why": f"part of {v}"} for k, (v, n) in part_of.items()]
        self.looks.update(world)

        self._place_places(world, start, drawn)
        moves = self._place_actors(world, start, drawn)
        at = {k: replace(v) for k, v in start.items()}      # the running state the events move
        timeline: list[dict[str, Any]] = []
        fallback: list[dict[str, str]] = []
        t = T_START
        for i, (x1, tree) in moves.items():                  # it walks to the place the line says first
            t = self._walk(i, x1, world, at, t, timeline)
            at[i].tree = tree
        group: Optional[tuple[str, float, int]] = None      # people going to one place go together, queued
        checks = []
        for ev in events:
            cls, why = O.classify(ev, world, asset_for, assets())
            checks.append({"op": ev.op, "actor": ev.actor, "target": ev.target or ev.obj, "class": cls, "why": why})
            if cls == "invalid":                             # never animates; the actor stays
                fallback.append({"op": ev.op, "actor": ev.actor, "verb": ev.verb, "why": why})
                checks[-1]["fallback"] = why
                continue
            n0 = len(fallback)
            if ev.op in ("move_to", "enter") and group and group[0] == ev.target:
                end = self._event(ev, world, at, group[1], timeline, fallback, queue=group[2])
                group, t = (group[0], group[1], group[2] + 1), max(t, end)
            elif _together(ev, world) and group and group[0] == _together(ev, world):
                end = self._event(ev, world, at, group[1], timeline, fallback)   # at once: both boats, both balls
                t = max(t, end)
            else:
                t0 = t
                t = self._event(ev, world, at, t, timeline, fallback)
                key = _together(ev, world)
                group = (ev.target, t0, 1) if ev.op in ("move_to", "enter") and ev.target else (key, t0, 1) if key else None
            self._sync_held(at)
            checks[-1]["fallback"] = fallback[-1]["why"] if len(fallback) > n0 else ""
        _style_hit_reacts(timeline)
        end = max([t] + [e.get("t1", e.get("t0", 0)) for e in timeline]) + 0.8
        self._sync_held(at)
        for k, v in at.items():
            v.comeback = False
            self.at[k] = v
        for f in fallback:
            log.info("[STORY] fallback %s", f)
        spec = {
            "rev": world.rev, "line": line, "g": G, "stage": {"w": STAGE_W, "sky": "day"},
            "entities": [self._ent(ents[i], start.get(i), at.get(i)) for i in drawn if i in start],
            "events": timeline, "fallback": fallback, "skipped": skipped, "checks": checks,
            "duration": round(end, 3),
        }
        return spec

    def _ent(self, e: W.Entity, s: Optional[Place], f: Optional[Place]) -> dict[str, Any]:
        out: dict[str, Any] = {"id": e.id, "kind": e.kind, "asset": asset_for(e) or "box", "name": e.name,
                               "known": e.known, "start": asdict(s) if s else None, "end": asdict(f) if f else None}
        if e.kind == "person":
            look = dict(self.looks.looks.get(e.id, {}))
            look.pop("kind", None)
            out["look"], out["label"] = look, look.pop("label", "")
        out["parts"] = sorted(self.parts.get(e.id, ()))
        if out["asset"] == "tree":
            out["fruit"] = fruit_of(e)
            out["hidden"] = list(self.hidden.get(e.id, []))
        return out

    def _said_parts(self, world: W.World, line: str) -> tuple[W.World, dict[str, tuple[str, str]]]:
        """Optional parts (sidecar "parts": a tree's branch) are drawn only once a line says them (user, P1b close):
        the said word shows the part on the thing this line acts on (else the latest such thing on the stage). An
        entity that names a part ("a high branch") is that part: events and relations on it go to its thing."""
        A = assets()
        said = set(W.words(line))
        part_of: dict[str, tuple[str, str]] = {}
        acted = [i for ev in world.events for i in (ev.target, ev.obj) if i]
        for asset, a in A.items():
            for part, d in a.get("parts", {}).items():
                ws = set(d["words"])
                named = [e for e in world.entities.values() if e.kind != "person" and not asset_for(e)
                         and ({e.noun} | set(W.words(e.name))) & ws]
                if not (said & ws or named):
                    continue
                things = [i for i, e in world.entities.items() if asset_for(e) == asset
                          and not (i in self.at and self.at[i].gone)]
                rel = [r.b for r in world.relations for e in named if r.a == e.id and r.b in things]
                pick = next((i for i in acted + rel if i in things), None) or (things[-1] if things else None)
                if pick is None:
                    continue
                self.parts.setdefault(pick, set()).add(part)
                part_of.update({e.id: (pick, e.name) for e in named})
        if not part_of:
            return world, part_of
        m = lambda i: part_of[i][0] if i in part_of else i
        rels = [W.Relation(m(r.a), r.rel, m(r.b), m(r.c) if r.c else "") for r in world.relations]
        view = W.World({k: v for k, v in world.entities.items() if k not in part_of},
                       [r for r in rels if r.a != r.b], world.rev,
                       [replace(ev, actor=m(ev.actor), target=m(ev.target) if ev.target else "",
                                obj=m(ev.obj) if ev.obj else "") for ev in world.events])
        return view, part_of

    def _place_places(self, world: W.World, at: dict[str, Place], drawn: list[str]) -> None:
        dest = {ev.target for ev in world.events if ev.op in ("move_to", "enter")}
        dest |= {r.b for r in world.relations if r.rel == "towards"}
        taken = {round(p.x, 1) for i, p in at.items() if _is_place(world.entities[i])}
        for i in drawn:
            e = world.entities[i]
            if i in at or not _is_place(e):
                continue
            want = [11.0, *PLACE_SLOTS] if i in dest else list(PLACE_SLOTS)
            x = next((s for s in want if round(s, 1) not in taken), 1.5 + (2.2 * len(taken)) % 11)
            at[i] = Place(x)
            taken.add(round(x, 1))

    def _place_actors(self, world: W.World, at: dict[str, Place], drawn: list[str]) -> dict[str, tuple[float, str]]:
        """New actors get a place from their relations. An actor from an earlier line whose place does not meet its
        locating relation (review: "sat under the tree" after "stood in the field") keeps its start place and walks
        there first: returned as {id: (x to walk to, the tree it ends under)}."""
        ents = world.entities
        moves: dict[str, tuple[float, str]] = {}
        free: set[str] = set()
        for i in sorted(drawn, key=lambda i: ents[i].kind == "prop"):   # people first: a falling prop aims at them
            e = ents[i]
            if _is_place(e):
                continue
            if i in at:
                q = at[i]
                want = self._relate(world, i, replace(q, tree=""), at)
                if not q.carrier and not want.carrier and q.fruit < 0 and not q.holder and q.y < 0.05                         and abs(want.x - q.x) > 0.3:
                    moves[i] = (want.x, want.tree)
                continue
            p = Place(-1.0, posture=e.posture)
            if any(ev.op == "change_posture" and ev.actor == i for ev in world.events):
                p.posture = "stand"          # it stands first, then the line's change plays
            p = self._relate(world, i, p, at)
            if p.x < 0 and not p.carrier:    # no relation placed it: the nearest free spot to the middle
                p.x = self._free_x(STAGE_W / 2, i, world, at)
                free.add(i)
            elif p.x == p.x and not p.carrier and any(r.a == i and r.rel == "in" for r in world.relations):
                p.x = self._free_x(p.x, i, world, at)
            if e.kind == "prop" and asset_for(e) == "apple":
                p = self._bind_fruit(world, i, at) or p
            if e.kind in ("prop", "animal") and p.fruit < 0:
                p = self._held_start(world, i, p, at)
            at[i] = p
        self._mount_starts(world, at)
        self._walk_starts(world, at, free)
        for ev in world.events:
            if ev.op == "throw" and ev.target in at and ev.target not in self.at and ev.actor in at                     and world.entities[ev.target].kind in ("person", "animal"):
                a, b = at[ev.actor], at[ev.target]       # a new catcher stands a throw away, not shoulder to shoulder
                if abs(b.x - a.x) < 2.5:
                    x = a.x + (3.0 if a.x < STAGE_W / 2 else -3.0)
                    b.x, b.facing = x, (1 if a.x > x else -1)
                continue
            if ev.op != "speak" or not ev.target:
                continue
            a, b = at.get(ev.actor), at.get(ev.target)
            if a is None or b is None or a.carrier or b.carrier or abs(a.x - b.x) < 1e-6:
                continue
            if ev.target not in self.at and ev.actor not in self.at and abs(b.x - a.x) < 1.3:
                b.x = a.x + (1.4 if b.x >= a.x else -1.4)   # a talking distance, not shoulder to shoulder
            if ev.actor not in self.at:      # new to the scene: they already face each other (no turn plays)
                a.facing = 1 if b.x > a.x else -1
            if ev.target not in self.at:
                b.facing = 1 if a.x > b.x else -1
        return moves

    def _free_x(self, near: float, me: str, world: W.World, at: dict[str, Place]) -> float:
        """The spot nearest `near` where no one else stands (people 0.8 m apart, a horse its length)."""
        half = {"horse": assets()["horse"]["length"] / 2}
        others = [(o.x, half.get(asset_for(world.entities[k]), 0.4)) for k, o in at.items()
                  if k != me and not o.carrier and o.x >= 0 and world.entities[k].kind in ("person", "animal")]
        for step in range(0, 30):
            x = near + (step + 1) // 2 * 0.9 * (1 if step % 2 else -1) if step else near
            if 0.6 <= x <= STAGE_W - 0.6 and all(abs(x - ox) >= 0.4 + h for ox, h in others):
                return x
        return near

    def _relate(self, world: W.World, i: str, p: Place, at: dict[str, Place]) -> Place:
        """The place the world's relations give actor i (p unchanged where no relation applies)."""
        A = assets()
        ents = world.entities
        for r in world.relations:
            if r.a != i or r.b not in at:
                continue
            b, bp = ents[r.b], at[r.b]
            ba = asset_for(b)
            if r.rel == "under" and ba == "tree":
                tr = A["tree"]
                n = sum(1 for k, o in at.items() if k != i and o.tree == r.b and o.fruit < 0)
                p.x = bp.x + tr["trunk"]["w"] / 2 + tr["under"]["clear"] + 0.7 * n
                p.facing, p.tree = 1, r.b
            elif r.rel in ("ride", "sit_on") and ba == "horse":
                p = replace(p, carrier=r.b, anchor="saddle", posture="sit", facing=bp.facing)
            elif r.rel == "next_to":
                side = 1 if bp.x <= STAGE_W / 2 else -1
                p.x = bp.x + side * (_width(b) / 2 + 0.5)
            elif r.rel == "in" and _is_place(b) and abs(p.x - bp.x) > _width(b) / 2:
                p.x = bp.x
        return p

    def _walk_starts(self, world: W.World, at: dict[str, Place], free: set[str]) -> None:
        """New people with no place of their own who go to a place this line start in a line on the far side of the
        stage, the first said in front, so they walk there together."""
        go = [ev for ev in world.events if ev.op in ("move_to", "enter") and ev.actor in free and ev.target in at
              and _is_place(world.entities[ev.target])]
        for dest in dict.fromkeys(ev.target for ev in go):
            walkers = [ev.actor for ev in go if ev.target == dest]
            right = at[dest].x > STAGE_W / 2
            for k, i in enumerate(walkers):
                back = k * 0.85
                at[i].x = 1.0 + (len(walkers) - 1) * 0.85 - back if right else STAGE_W - 1.0 - (len(walkers) - 1) * 0.85 + back
                at[i].facing = 1 if right else -1

    def _mount_starts(self, world: W.World, at: dict[str, Place]) -> None:
        """A new rider starts standing beside the horse (the line's mount plays); a new horse that rides off to a
        place starts on the far side of the stage."""
        ents = world.entities
        new = {i for i in at if i not in self.at}
        for ev in world.events:
            if ev.op != "attach" or ev.value not in ("ride", "sit_on") or ev.actor not in new or ev.target not in at \
                    or asset_for(ents[ev.target]) != "horse":
                continue
            h = at[ev.target]
            dest = next((m.target for m in world.events if m.op == "move_to" and m.actor in (ev.actor, ev.target)
                         and m.target in at), "")
            if ev.target in new and dest:
                h.x, h.facing = (2.4, 1) if at[dest].x > STAGE_W / 2 else (STAGE_W - 2.4, -1)
            at[ev.actor] = replace(at[ev.actor], carrier="", anchor="", posture="stand", x=h.x - h.facing * 0.75,
                                   facing=h.facing)

    def _bind_fruit(self, world: W.World, i: str, at: dict[str, Place]) -> Optional[Place]:
        """A said fruit that falls on someone under a tree of that fruit = one of that tree's own fruit (the one
        nearest above the head), not a new apple out of the air."""
        A = assets()
        e = world.entities[i]
        fall = next((ev for ev in world.events if ev.op == "fall" and ev.actor == i), None)
        trees = [t for t, p in at.items() if asset_for(world.entities[t]) == "tree"
                 and fruit_of(world.entities[t]) in W.words(e.name)]
        if not trees:
            return None
        tree = trees[0]
        if fall and fall.target in at and world.entities[fall.target].kind in ("person", "animal"):
            if at[fall.target].tree not in trees:
                return None          # not under that tree: no fruit thrown sideways across the stage
            tree = at[fall.target].tree
        tp = at[tree]
        free = [k for k in range(len(A["tree"]["fruit"])) if k not in self.hidden.get(tree, [])]
        if not free:
            return None
        hx = self.head_top(fall.target, at)[0] if fall and fall.target in at and world.entities[fall.target].kind \
            == "person" else tp.x
        k = min(free, key=lambda k: (abs(tp.x + A["tree"]["fruit"][k][0] - hx), A["tree"]["fruit"][k][1]))
        fx, fy = A["tree"]["fruit"][k]
        self.hidden.setdefault(tree, []).append(k)
        return Place(tp.x + fx, fy, fruit=k, tree=tree)

    # ---- events -------------------------------------------------------------------------------------------------
    def _event(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list, fallback: list,
               queue: int = 0) -> float:
        A = assets()
        ents = world.entities
        if ev.op == "push" and ents[ev.actor].kind == "agent" and ev.target in at:   # the wind pushes the boat
            return self._slide(ev.target, 2.0 * (1 if ev.value != "pull" else -1), t, O.OPS["push"].dur, world, at, out)
        if ev.actor not in at:
            fallback.append({"op": ev.op, "actor": ev.actor, "why": "not drawn"})
            return t
        if ev.op in O.RIG_OPS + ("detach",) or (ev.op == "attach" and ev.value == "hold"):
            if ev.op != "detach" and asset_for(ents[ev.actor]) != "person":
                fallback.append({"op": ev.op, "actor": ev.actor, "verb": ev.verb, "why": f"no rig for a {ents[ev.actor].kind}"})
                return t
            return self._hand_op(ev, world, at, t, out, fallback)
        if ev.op == "exit":
            return self._exit(ev, world, at, t, out)
        if ev.op == "follow_path":
            p = at[ev.actor]
            mover = p.carrier or ev.actor
            m = at[mover]
            x1 = m.x + m.facing * 3.0
            if not 0.8 <= x1 <= STAGE_W - 0.8:
                x1 = m.x - m.facing * 3.0
            return self._walk(mover, x1, world, at, t, out)
        p = at[ev.actor]
        if ev.op == "change_posture":
            if p.carrier or p.posture == ev.value:
                return t
            if p.posture == "climb" and ev.value == "sit" and p.on in at and "branch" in self.parts.get(p.on, ()):
                tr, bp = assets()["tree"], at[p.on]        # clinging, then "sat on a branch": over onto the limb
                side = 1 if p.x >= bp.x else -1
                x1, y1 = bp.x + side * tr["branch"]["x"], tr["branch"]["y"]
                dur = max(y1 - p.y, 0.3) / assets()["person"]["climb_speed"] + 0.6
                out.append({"op": "climb", "actor": ev.actor, "from": [p.x, p.y], "to": [x1, y1], "end": "sit",
                            "t0": t, "t1": t + dur, "facing": -side})
                p.x, p.y, p.posture = x1, y1, "sit"
                return t + dur
            d = O.OPS["change_posture"].dur
            out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": ev.value, "t0": t, "t1": t + d})
            p.posture = ev.value
            return t + d
        if ev.op == "attach" and ev.value in ("ride", "sit_on") and ev.target in at \
                and asset_for(ents[ev.target]) == "horse":
            if p.carrier == ev.target:
                return t             # already on it: a restated ride never slides him across the stage
            if p.y > 0.05:           # review: down from the branch / box first, never mounted from mid-air
                t = self._jump(W.Event("jump", ev.actor, p.on, value="off"), world, at, t, out)
                p = at[ev.actor]
            h = at[ev.target]
            sx, sy = A["horse"]["saddle"]
            out.append({"op": "mount", "actor": ev.actor, "carrier": ev.target, "from": [p.x, pelvis_y(p)],
                        "to": [h.x + h.facing * sx, sy], "t0": t, "t1": t + 1.0})
            at[ev.actor] = replace(p, carrier=ev.target, anchor="saddle", posture="sit", facing=h.facing)
            return t + O.OPS["attach"].dur
        if ev.op == "enter" and ev.target not in at and at[p.carrier or ev.actor].comeback:
            mover = p.carrier or ev.actor
            return self._walk(mover, self._free_x(STAGE_W / 2, mover, world, at), world, at, t, out)
        if ev.op in ("move_to", "enter") and ev.target in at:
            mover = p.carrier or ev.actor
            x1 = self._arrive_x(ev.target, at[mover], asset_for(ents[mover]), world, at)
            side = -1 if at[mover].x < at[ev.target].x else 1
            x1 += side * 0.85 * queue                    # the k-th to arrive stops behind the others (arrival side)
            p.tree = ""
            return self._walk(mover, x1, world, at, t, out)
        if ev.op == "fall":
            if ents[ev.actor].kind in ("person", "animal", "group"):    # it falls over, where it is
                if p.y > 0.05 and not p.carrier:            # off the branch first: lands, then lies there
                    t = self._jump(W.Event("jump", ev.actor, p.on, value="off"), world, at, t, out)
                if p.carrier or p.posture == "lie":
                    fallback.append({"op": "fall", "actor": ev.actor, "verb": ev.verb, "why": "no fall-off motion in P0"})
                    return t
                d = O.OPS["fall"].dur
                out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": "lie", "t0": t, "t1": t + d})
                p.posture = "lie"
                return t + d
            return self._fall(ev, world, at, t, out, fallback)
        if ev.op == "speak":
            facing = self._face(ev.actor, ev.target, at, both=True)
            text = ev.value or ""
            sp = O.OPS["speak"]
            dur = sp.dur + sp.per_char * len(text) + sp.tail
            out.append({"op": "speak", "actor": ev.actor, "to": ev.target, "text": text, "t0": t, "t1": t + dur,
                        "type_s": round(sp.per_char * len(text), 3), "facing": facing})
            return t + dur
        if ev.op == "react":
            d = O.OPS["react"].dur
            out.append({"op": "react", "actor": ev.actor, "value": ev.value, "t0": t, "t1": t + d})
            return t + d
        if ev.op in ("look_at", "point_at") and (ev.target or ev.obj) in at:
            facing = self._face(ev.actor, ev.target or ev.obj, at, both=False)
            out.append({"op": ev.op.replace("_at", ""), "actor": ev.actor, "target": ev.target or ev.obj,
                        "t0": t, "t1": t + O.OPS[ev.op].dur, "facing": facing})
            return t + O.OPS[ev.op].dur
        fallback.append({"op": ev.op, "actor": ev.actor, "verb": ev.verb, "why": "no motion for this op in P0"})
        return t

    # ---- P1b: hand ops, jump, climb, push, exit (docs/v3/P1b-semantic-actions.md) -------------------------------
    def _held_start(self, world: W.World, i: str, p: Place, at: dict[str, Place]) -> Place:
        """A new thing someone holds on this line: in the hand from the start ("with a stick in his hand"), or, said
        picked up / caught, on the ground in front of the person (the grip plays)."""
        ents = world.entities
        who = next((r.a for r in world.relations if r.rel == "hold" and r.b == i and r.a in at
                    and asset_for(ents[r.a]) == "person"), "")
        ev = next((e for e in world.events if e.obj == i or e.target == i), None)
        if ev is not None and ev.op in ("put", "give", "throw") and ev.actor in at \
                and asset_for(ents[ev.actor]) == "person":
            who = ev.actor               # put / given / thrown, never said picked up: it was in that hand
        if not who:
            return p
        if ev is not None and ev.op == "attach" and set(W.words(ev.verb)) & _PICK:
            h = at[who]
            return Place(h.x + h.facing * 0.38, _rest_y(ents[i]))
        n = sum(1 for o in at.values() if o.holder == who)
        q = Place(0.0, 0.0, holder=who, hand=min(n, 1))
        q.x, q.y = self.hand_at(who, at, q.hand)
        return q

    def _hand_op(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list, fallback: list) -> float:
        A = assets()
        ents = world.entities
        p = at[ev.actor]
        thing = ev.obj or (ev.target if ev.op in ("attach", "detach") else "")
        held = [k for k, q in at.items() if q.holder == ev.actor]
        fb = lambda why: (fallback.append({"op": ev.op, "actor": ev.actor, "verb": ev.verb, "why": why}), t)[1]
        if ev.op == "attach":                                    # hold / carry / pick up / catch / lift
            if thing not in at or ents[thing].kind in ("person", "place"):
                return fb("no carry motion for that")
            q = at[thing]
            if q.holder == ev.actor:                             # already in the hand: held up
                out.append({"op": "raise", "actor": ev.actor, "hand": q.hand, "t0": t, "t1": t + 1.4})
                return t + 1.4
            if q.carrier or q.fruit >= 0:
                return fb("it hangs / rides elsewhere")
            if not q.holder and abs(q.x - p.x) > 0.7 and not p.carrier:   # held by another: taken from that hand
                t = self._walk(ev.actor, q.x - (1 if q.x > p.x else -1) * 0.38, world, at, t, out)
            facing = self._face(ev.actor, thing, at, both=False)
            low = q.y < 0.5 and not p.carrier and p.posture == "stand"
            if low:
                out.append({"op": "posture", "actor": ev.actor, "from": "stand", "to": "reach_down", "t0": t, "t1": t + 0.5})
                p.posture, t = "reach_down", t + 0.5
            hand = min(len(held), 1)
            d = O.OPS["attach"].dur
            out.append({"op": "grip", "actor": thing, "by": ev.actor, "hand": hand, "from": [q.x, q.y],
                        "t0": t, "t1": t + d * 0.6, "facing": facing})
            q.holder, q.hand = ev.actor, hand
            t += d * 0.6
            if low:
                out.append({"op": "posture", "actor": ev.actor, "from": "reach_down", "to": "stand", "t0": t, "t1": t + 0.5})
                p.posture, t = "stand", t + 0.5
            return t
        if ev.op == "detach":
            if p.carrier and (not thing or thing == p.carrier):  # off the horse: beside it, standing
                h = at[p.carrier]
                to = [h.x - h.facing * 0.75, 0.0]
                out.append({"op": "dismount", "actor": ev.actor, "carrier": p.carrier, "to": to, "t0": t, "t1": t + 1.0})
                at[ev.actor] = replace(p, carrier="", anchor="", posture="stand", x=to[0], y=0.0)
                return t + 1.0
            mine = [k for k in held if not thing or k == thing]
            if not mine:
                if p.posture == "sit" and not thing:
                    return self._event(W.Event("change_posture", ev.actor, value="stand"), world, at, t, out, fallback)
                return fb("nothing held to let go")
            for k in mine:                                       # it drops from the hand to the ground under g
                self._drop_from_hand(k, world, at, t, out)
            return t + O.OPS["detach"].dur
        if ev.op in ("put", "give", "throw"):
            if not thing or thing not in at:
                return fb("nothing to " + ev.op)
            q = at[thing]
            if q.holder != ev.actor:                             # not held yet (said earlier on the ground): pick up
                t = self._hand_op(W.Event("attach", ev.actor, thing, "", "hold"), world, at, t, out, fallback)
                if at[thing].holder != ev.actor:
                    return t
            if ev.op == "put":
                return self._put(ev, thing, world, at, t, out)
            if ev.op == "give":
                return self._give(ev, thing, world, at, t, out, fallback)
            return self._throw(ev, thing, world, at, t, out)
        if ev.op == "jump":
            return self._jump(ev, world, at, t, out)
        if ev.op == "climb":
            return self._climb(ev, world, at, t, out, fallback)
        if ev.op == "push":
            if ev.target not in at or ents[ev.target].kind == "place":
                return fb("nothing to push")
            b = at[ev.target]
            side = 1 if b.x > p.x else -1
            t = self._walk(ev.actor, b.x - side * (_width(ents[ev.target]) / 2 + 0.4), world, at, t, out)
            d = (1.2 if ev.value != "pull" else -1.2) * side
            dur = O.OPS["push"].dur
            out.append({"op": "push", "actor": ev.actor, "value": ev.value or "push", "t0": t, "t1": t + dur,
                        "facing": self._face(ev.actor, ev.target, at, both=False)})
            x0 = b.x
            end = self._slide(ev.target, d, t, dur, world, at, out, me=ev.actor)
            moved = b.x - x0                                     # the pusher steps as far as the thing went
            if abs(moved) > 0.05:
                out.append({"op": "move", "actor": ev.actor, "from": p.x, "to": p.x + moved, "t0": t, "t1": t + dur,
                            "gait": "walk", "speed": abs(moved) / dur, "facing": side, "carries": []})
                p.x += moved
            return max(end, t + dur)
        return fb("no motion")

    def _slide(self, i: str, d: float, t: float, dur: float, world: W.World, at: dict[str, Place], out: list,
               me: str = "") -> float:
        q = at[i]
        x1 = min(max(q.x + d, 0.6), STAGE_W - 0.6)
        half = _width(world.entities[i]) / 2 + 0.35
        for k, o in at.items():                                  # it stops short of anyone standing in its way
            if k not in (i, me) and not o.carrier and not o.holder and world.entities[k].kind in ("person", "animal") \
                    and min(q.x, x1) - half < o.x < max(q.x, x1) + half and abs(o.x - q.x) > half:
                x1 = o.x - math.copysign(half, d)
        if abs(x1 - q.x) < 0.05:
            return t
        out.append({"op": "slide", "actor": i, "from": q.x, "to": x1, "t0": t, "t1": t + dur})
        q.x = x1
        return t + dur

    def _drop_from_hand(self, k: str, world: W.World, at: dict[str, Place], t: float, out: list) -> None:
        q = at[k]
        x0, y0 = self.hand_at(q.holder, at, q.hand)
        r = _rest_y(world.entities[k]) or 0.0
        h = max(y0 - r, 0.02)
        tc = math.sqrt(2 * h / G)
        out.append({"op": "fall", "actor": k, "from": [x0, y0], "v": [0.0, 0.0], "shake": 0.0, "t0": t,
                    "t1": round(t + tc, 4), "contact": {"t": round(t + tc, 4), "at": [x0, r], "on": "ground",
                                                        "part": "ground"}, "r": r, "rest": [x0, r]})
        at[k] = Place(x0, r)

    def _put(self, ev: W.Event, k: str, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        ents = world.entities
        p = at[ev.actor]
        r = _rest_y(ents[k])
        tgt = ev.target if ev.target in at else ""
        if tgt:
            b, bp = ents[tgt], at[tgt]
            side = 1 if bp.x > p.x else -1
            if ev.value == "under" and asset_for(b) == "tree":   # in the shade, on his side of the trunk (user: a toss
                tr = assets()["tree"]                            # to the trunk centre read as a throw)
                spot = bp.x - side * (tr["trunk"]["w"] / 2 + 0.55)
                if not p.carrier and abs(p.x - spot) > 0.45:
                    t = self._walk(ev.actor, spot - side * 0.38, world, at, t, out)
                facing = self._face(ev.actor, tgt, at, both=False)
                return self._set_down(ev, k, [spot, r], world, at, t, out, facing)
            if abs(bp.x - p.x) > _width(b) / 2 + 0.9 and not p.carrier:
                t = self._walk(ev.actor, bp.x - side * (_width(b) / 2 + 0.45), world, at, t, out)
            facing = self._face(ev.actor, tgt, at, both=False)
            top = _top(b)
            if bp.holder or bp.carrier:                          # into a held basket: it goes with the basket
                d = O.OPS["put"].dur
                q = at[k]
                out.append({"op": "place", "actor": k, "by": ev.actor, "hand": q.hand, "to": [bp.x, bp.y + r],
                            "t0": t, "t1": t + d, "facing": facing})
                q.holder, q.hand = bp.holder or q.holder, bp.hand
                if not bp.holder:
                    q.holder = ""
                    q.x, q.y = bp.x, bp.y + r
                return t + d
            rest = {"on": [bp.x, bp.y + top + r], "in": [bp.x, bp.y + max(top * 0.5, r)], "under": [bp.x, r],
                    "next_to": [bp.x - side * (_width(b) / 2 + 0.3), r]}[ev.value or "on"]
        else:                                                    # put down: on the ground in front
            rest, facing = [p.x + p.facing * 0.38, r], {}
        return self._set_down(ev, k, rest, world, at, t, out, facing)

    def _set_down(self, ev: W.Event, k: str, rest: list, world: W.World, at: dict[str, Place], t: float, out: list,
                  facing: dict) -> float:
        """The hand carries the thing down to the spot and lets go there (bending down for a low spot); no arc."""
        p = at[ev.actor]
        low = rest[1] < 0.5 and p.posture == "stand" and not p.carrier
        if low:
            out.append({"op": "posture", "actor": ev.actor, "from": "stand", "to": "reach_down", "t0": t, "t1": t + 0.5})
            p.posture, t = "reach_down", t + 0.5
        d = O.OPS["put"].dur
        q = at[k]
        out.append({"op": "place", "actor": k, "by": ev.actor, "hand": q.hand, "to": rest, "t0": t, "t1": t + d,
                    "facing": facing})
        at[k] = Place(rest[0], rest[1])
        t += d
        if low:
            out.append({"op": "posture", "actor": ev.actor, "from": "reach_down", "to": "stand", "t0": t, "t1": t + 0.5})
            p.posture, t = "stand", t + 0.5
        return t

    def _give(self, ev: W.Event, k: str, world: W.World, at: dict[str, Place], t: float, out: list,
              fallback: list) -> float:
        p, tgt = at[ev.actor], ev.target
        if tgt not in at or asset_for(world.entities[tgt]) != "person":
            fallback.append({"op": "give", "actor": ev.actor, "verb": ev.verb, "why": "no hands to take it"})
            return t
        b = at[tgt]
        if abs(b.x - p.x) > 1.0 and not p.carrier:               # the giver walks up to a hand-over distance
            t = self._walk(ev.actor, b.x - (1 if b.x > p.x else -1) * 0.9, world, at, t, out)
        facing = self._face(ev.actor, tgt, at, both=True)
        hand = min(sum(1 for o in at.values() if o.holder == tgt), 1)
        d = O.OPS["give"].dur
        out.append({"op": "handover", "actor": k, "by": ev.actor, "to": tgt, "hand": at[k].hand, "to_hand": hand,
                    "t0": t, "t1": t + d, "facing": facing})
        at[k].holder, at[k].hand = tgt, hand
        return t + d

    def shoulder_at(self, eid: str, at: dict[str, Place]) -> tuple[float, float]:
        """The right shoulder of a standing person (rig.js: neck - 0.05 along the torso, 0.025 forward)."""
        P = assets()["person"]
        p, s = at[eid], self.scale(eid)
        return p.x + p.facing * 0.025 * s, p.y + (P["pelvis"]["stand"] + P["torso"] - 0.05) * s

    def _throw(self, ev: W.Event, k: str, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        """Overarm throw (user round 1): a step forward with the wind-up behind the head, the release at the forward
        hand point (person.json "release", the rig uses the same), a 35 degree arc whose speed Python picks so it
        ends in the catcher's raised hands (a person target catches and holds it) or on the ground at the target."""
        P = assets()["person"]
        ents = world.entities
        p = at[ev.actor]
        tgt = ev.target if ev.target in at and ev.target != k else ""
        catcher = tgt if tgt and asset_for(ents[tgt]) == "person" and not at[tgt].carrier else ""
        facing = self._face(ev.actor, tgt, at, both=bool(catcher)) if tgt else {}
        D, k_rel = 0.9, 0.75                                     # throw_arm length, the release point of it
        step = 0.3 if not p.carrier and p.y < 0.05 else 0.0
        if step:
            out.append({"op": "move", "actor": ev.actor, "from": p.x, "to": p.x + p.facing * step, "t0": t,
                        "t1": t + D * k_rel, "gait": "walk", "speed": step / (D * k_rel), "facing": p.facing,
                        "carries": []})
            p.x += p.facing * step
        out.append({"op": "throw_arm", "actor": ev.actor, "t0": t, "t1": t + D, "release": k_rel, "facing": facing})
        sx, sy = self.shoulder_at(ev.actor, at)
        s = self.scale(ev.actor)
        x0, y0 = sx + p.facing * P["release"][0] * s, sy + P["release"][1] * s
        r = _rest_y(ents[k])
        if catcher:
            cx, cy = self.shoulder_at(catcher, at)
            cs = self.scale(catcher)
            x1, y1 = cx + at[catcher].facing * P["catch"][0] * cs, cy + P["catch"][1] * cs
        else:
            x1 = at[tgt].x if tgt else x0 + p.facing * 4.0
            y1 = r
        x1 = min(max(x1, 0.4), STAGE_W - 0.4)
        R, dy = abs(x1 - x0), y1 - y0
        th = math.radians(35)
        v = math.sqrt(G * R * R / (2 * math.cos(th) ** 2 * max(R * math.tan(th) - dy, 0.05))) if R >= 0.3 else 0.0
        vx, vy = (math.copysign(v * math.cos(th), x1 - x0), v * math.sin(th)) if v else (0.0, 0.0)
        tc = R / abs(vx) if vx else math.sqrt(2 * max(y0 - y1, 0.02) / G)
        t_rel = t + D * k_rel
        tcon = round(t_rel + tc, 4)
        if catcher:                                              # hands up before it arrives, closed on it after
            out.append({"op": "ready", "actor": catcher, "t0": max(t, t_rel - 0.3), "t1": tcon + 0.25})
        out.append({"op": "fall", "actor": k, "from": [x0, y0], "v": [vx, vy], "shake": 0.0, "t0": t_rel, "t1": tcon,
                    "contact": {"t": tcon, "at": [x1, y1], "on": catcher or "ground", "part": "hands" if catcher
                                else "ground", "caught": bool(catcher)}, "r": r, "rest": [x1, y1]})
        if catcher:
            hand = min(sum(1 for o in at.values() if o.holder == catcher), 1)
            out.append({"op": "grip", "actor": k, "by": catcher, "hand": hand, "from": [x1, y1], "t0": tcon,
                        "t1": tcon + 0.3})
            at[k] = Place(x1, y1, holder=catcher, hand=hand)
            return tcon + 0.4
        at[k] = Place(x1, y1)
        return tcon + 0.1

    def _jump(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        """Crouch, hop, land: v0 from the hop height and g (person.json jump_h); onto a target = its top, off = down
        beside where it stood."""
        A = assets()
        ents = world.entities
        p = at[ev.actor]
        tgt = ev.target if ev.target in at else ""
        if p.carrier:                                            # off the horse = the dismount (review)
            if ev.value == "off" or tgt == p.carrier:
                return self._hand_op(W.Event("detach", ev.actor, p.carrier), world, at, t, out, [])
            return t
        if ev.value == "onto" and tgt and asset_for(ents[tgt]) == "horse":
            return self._event(W.Event("attach", ev.actor, tgt, value="ride"), world, at, t, out, [])
        if p.posture != "stand":
            out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": "stand", "t0": t, "t1": t + 0.6})
            p.posture, t = "stand", t + 0.6
        x0, y0 = p.x, p.y
        if ev.value == "onto" and tgt:
            x1, y1 = at[tgt].x, _top(ents[tgt]) + at[tgt].y
            p.facing = 1 if x1 >= x0 else -1
        elif ev.value == "off" or (y0 > 0.05 and not tgt):
            off = tgt or p.on                                    # away from what it leaves (never into the trunk)
            if off in at and abs(x0 - at[off].x) > 0.05:
                p.facing = 1 if x0 > at[off].x else -1
            x1, y1 = x0 + p.facing * 0.9, 0.0
        else:
            x1, y1 = x0, y0                                      # in place, as high as it can
        hop = A["person"]["jump_h"]
        v0 = math.sqrt(2 * G * (max(y1 - y0, 0.0) + hop))
        tf = (v0 + math.sqrt(max(v0 * v0 - 2 * G * (y1 - y0), 0.0))) / G
        crouch = 0.3
        out.append({"op": "jump", "actor": ev.actor, "from": [x0, y0], "to": [x1, y1], "v0": round(v0, 4),
                    "t0": t, "t_up": t + crouch, "t_land": round(t + crouch + tf, 4), "t1": round(t + 2 * crouch + tf, 4),
                    "facing": p.facing})
        p.x, p.y = x1, y1
        p.on = tgt if ev.value == "onto" and y1 > 0.05 else ""
        return t + 2 * crouch + tf

    def _climb(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list, fallback: list) -> float:
        """Up the target hand over hand to its anchor: a tree's branch (sits there), a box's top (stands on it)."""
        A = assets()
        ents = world.entities
        p = at[ev.actor]
        if ev.target not in at or p.carrier:
            fallback.append({"op": "climb", "actor": ev.actor, "verb": ev.verb, "why": "nothing to climb"})
            return t
        b, bp = ents[ev.target], at[ev.target]
        side = -1 if p.x < bp.x else 1                          # the side it climbs from
        if asset_for(b) == "tree":
            tr = A["tree"]
            foot = bp.x + side * (tr["trunk"]["w"] / 2 + 0.28)
            if "branch" in self.parts.get(ev.target, ()):
                top_x, top_y, end = bp.x + side * tr["branch"]["x"], tr["branch"]["y"], "sit"   # on the limb, legs hang
            else:                                   # no branch said: no limb drawn; he clings to the trunk
                top_x, top_y, end = foot, tr["cling"]["y"], "climb"
        else:
            foot = bp.x + side * (_width(b) / 2 + 0.25)
            top_x, top_y, end = bp.x, _top(b), "stand"
        t = self._walk(ev.actor, foot, world, at, t, out)
        p.facing = -side
        if p.posture != "stand":
            out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": "stand", "t0": t, "t1": t + 0.6})
            t += 0.6
        dur = max(top_y, 0.3) / A["person"]["climb_speed"] + 0.6
        out.append({"op": "climb", "actor": ev.actor, "from": [foot, p.y], "to": [top_x, top_y], "end": end,
                    "t0": t, "t1": t + dur, "facing": -side})
        p.x, p.y, p.posture, p.on = top_x, top_y, end, ev.target
        return t + dur

    def _exit(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        """Walks off at the nearer edge; gone until it comes back. Leaving a said place walks away from it instead."""
        p = at[ev.actor]
        mover = p.carrier or ev.actor
        m = at[mover]
        if ev.target in at and _is_place(world.entities[ev.target]):   # "left his ashram": walks away, stays on
            away = 1 if m.x >= at[ev.target].x else -1
            x1 = at[ev.target].x + away * (_width(world.entities[ev.target]) / 2 + 3.0)
            if not 0.8 <= x1 <= STAGE_W - 0.8:
                x1 = min(max(x1, 0.8), STAGE_W - 0.8)
            return self._walk(mover, x1, world, at, t, out)
        right = m.x >= STAGE_W / 2
        t = self._walk(mover, STAGE_W + 0.9 if right else -0.9, world, at, t, out)
        if out and out[-1]["op"] == "move" and out[-1]["actor"] == mover:
            out[-1]["exit"] = True
        for k, q in at.items():
            if k == mover or q.carrier == mover:
                q.gone = True
        return t

    def _walk(self, mover: str, x1: float, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        """A move of `mover` (a person or a carrier) to x1; its riders go with it (their x follows the carrier)."""
        A = assets()
        m, kind = at[mover], asset_for(world.entities[mover])
        if abs(x1 - m.x) < 0.05:
            return t
        if kind == "person" and m.y > 0.05 and not m.carrier:     # review: never walk in the air (branch, box top)
            t = self._jump(W.Event("jump", mover, m.on, value="off"), world, at, t, out)
        speed = A.get(kind, A["person"]).get("walk_speed", A["person"]["walk_speed"])
        dur = abs(x1 - m.x) / speed
        m.facing = 1 if x1 > m.x else -1
        if kind == "person" and m.posture != "stand":
            out.append({"op": "posture", "actor": mover, "from": m.posture, "to": "stand", "t0": t, "t1": t + 0.6})
            m.posture, t = "stand", t + 0.6
        riders = [k for k, q in at.items() if q.carrier == mover]
        out.append({"op": "move", "actor": mover, "from": m.x, "to": x1, "t0": t, "t1": t + dur,
                    "gait": "walk", "speed": speed, "facing": m.facing, "carries": riders})
        m.x = x1
        for k in riders:
            at[k].x, at[k].facing = x1, m.facing
        return t + dur

    def _face(self, a: str, b: str, at: dict[str, Place], both: bool) -> dict[str, int]:
        """a turns to b (and b to a when both); a rider keeps the horse's facing. Returns the new facings: the event
        carries them so the browser turns the same way."""
        out: dict[str, int] = {}
        if a not in at or b not in at or abs(at[b].x - at[a].x) < 1e-6:
            return out
        pa, pb = at[a], at[b]
        if not pa.carrier:
            pa.facing = out[a] = 1 if pb.x > pa.x else -1
        if both and not pb.carrier:
            pb.facing = out[b] = 1 if pa.x > pb.x else -1
        return out

    def _arrive_x(self, target: str, m: Place, kind: str, world: W.World, at: dict[str, Place]) -> float:
        A = assets()
        b, bp = world.entities[target], at[target]
        ba = asset_for(b)
        if ba == "village":
            side = -1 if m.x < bp.x else 1
            half = A["horse"]["length"] / 2 if kind == "horse" else 0.4
            return bp.x + side * (abs(A["village"]["entrance"]) + half)
        side = -1 if m.x < bp.x else 1
        return bp.x + side * (_width(b) / 2 + 0.6)

    def _fall(self, ev: W.Event, world: W.World, at: dict[str, Place], t: float, out: list, fallback: list) -> float:
        """A thing drops (props only): from where it hangs, or, said to hit someone, from above that person. Python
        gives the start, the contact point and time (free fall under G), the bounce and where it rests."""
        A = assets()
        p = at[ev.actor]
        r = A["apple"]["r"] if asset_for(world.entities[ev.actor]) == "apple" else 0.15
        tgt = ev.target if ev.target in at and world.entities[ev.target].kind == "person" else ""
        x0, y0 = p.x, p.y
        hx, cy = x0, r
        if tgt:
            hx, hy = self.head_top(tgt, at)
            cy = hy + r
        if y0 <= r + 0.05:
            if not tgt:
                fallback.append({"op": "fall", "actor": ev.actor, "verb": ev.verb, "why": "already on the ground"})
                return t
            x0, y0 = hx, cy + 2.2           # nothing it hung from: it drops from above the person
        h = max(y0 - cy, 0.05)
        tc = math.sqrt(2 * h / G)
        vx = (hx - x0) / tc
        contact = {"t": round(t + 0.4 + tc, 4), "at": [hx, cy], "on": tgt or "ground", "part": ev.value or "ground"}
        e = {"op": "fall", "actor": ev.actor, "from": [x0, y0], "v": [vx, 0.0], "shake": 0.4,
             "t0": t + 0.4, "t1": contact["t"], "contact": contact, "r": r}
        land_x = hx
        if tgt:
            vy = A["apple"]["restitution"] * math.sqrt(2 * G * h)
            side = at[tgt].facing or 1
            vbx = 0.9 * side
            tl = (vy + math.sqrt(vy * vy + 2 * G * (cy - r))) / G
            land_x = hx + vbx * tl
            e["bounce"] = {"v": [vbx, vy], "t_ground": round(contact["t"] + tl, 4), "roll": 0.25 * side}
            land_x += 0.25 * side
            e["t1"] = round(contact["t"] + tl + 0.5, 4)
        e["rest"] = [land_x, r]
        out.append(e)
        at[ev.actor] = Place(land_x, r)
        return contact["t"] + 0.1


def _together(ev: W.Event, world: W.World) -> str:
    """Events of one line that play at the same time: everyone walking on (follow_path), the wind's pushes ("pushed
    both boats"), one person letting go of held things ("let go of both balls"). "" = in turn (review: a person's two
    pushes each walk up first; a dismount plays before a drop)."""
    if ev.op == "follow_path":
        return "follow_path"
    if ev.op == "push" and world.entities[ev.actor].kind == "agent":
        return f"push:{ev.actor}"
    tgt = world.entities.get(ev.target)
    if ev.op == "detach" and tgt is not None and tgt.kind == "prop" and asset_for(tgt) != "horse":
        return f"detach:{ev.actor}"
    return ""


def _roles(world: W.World) -> set[str]:
    """Ids with a physical role in the scene (in a relation, or acted on / moving): drawn even without an asset."""
    ids: set[str] = set()
    for r in world.relations:
        ids |= {r.a, r.b} | ({r.c} if r.c else set())
    for ev in world.events:
        if ev.op == "push" and world.entities[ev.actor].kind == "agent":   # the wind is not drawn, what it moves is
            ids |= {x for x in (ev.target, ev.obj) if x}
        elif ev.op in ("fall", "throw", "attach", "move_to", "enter", "exit", "work", "detach", "put", "give", "climb",
                     "push", "follow_path", "jump"):
            ids |= {ev.actor} | ({ev.target} if ev.target else set()) | ({ev.obj} if ev.obj else set())
        elif ev.op in ("speak", "react", "look_at", "point_at", "change_posture"):
            ids.add(ev.actor)
            if ev.target and world.entities[ev.target].kind in ("person", "animal"):
                ids.add(ev.target)
    for e in world.entities.values():
        if e.kind in ("person", "animal", "group"):
            ids.add(e.id)
    return ids


_PICK = {"picked", "pick", "picks", "grabbed", "grab", "took", "take", "takes", "lifted", "lift", "caught", "catch",
         "catches", "collected", "gathered"}
BOX_H = 0.45          # the fallback box (props.js box()): a thing with no asset is a labelled box this tall


def _rest_y(e: W.Entity) -> float:
    """A free thing's y: the apple's centre (its radius), a box's bottom (0)."""
    return assets()["apple"]["r"] if asset_for(e) == "apple" else 0.0


def _top(e: W.Entity) -> float:
    """The height a thing put / jumped / climbed onto ends at."""
    a = asset_for(e)
    A = assets()
    if a in PROPS:
        return A[a]["height"]
    return {"apple": 2 * A["apple"]["r"], "tree": A["tree"]["trunk"]["top"], "horse": A["horse"]["saddle"][1],
            "village": 0.0, "person": 1.0}.get(a, BOX_H)


def _is_place(e: W.Entity) -> bool:
    return e.kind == "place" or asset_for(e) in ("tree", "village")


def _width(e: W.Entity) -> float:
    a = asset_for(e)
    return assets().get(a, {}).get("width", 0.8) if a else 0.8


def _style_hit_reacts(timeline: list[dict[str, Any]]) -> None:
    """Style rule hit_reacts (ADR-0015 §3: embellishment only as a named rule): a fall that hits a person's head =
    a surprised reaction at the contact time, unless the line already says how the person reacts."""
    said = {e["actor"] for e in timeline if e["op"] == "react"}
    for e in list(timeline):
        c = e.get("contact") or {}
        if e["op"] == "fall" and c.get("on") not in ("", "ground", None) and c["on"] not in said and not c.get("caught"):
            timeline.append({"op": "react", "actor": c["on"], "value": "surprise", "t0": c["t"],
                             "t1": round(c["t"] + 1.6, 4), "style": "hit_reacts", "rub": c.get("part") == "head"})
