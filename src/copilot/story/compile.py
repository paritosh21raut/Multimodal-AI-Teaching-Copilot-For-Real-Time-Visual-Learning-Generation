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

from copilot.story import world as W
from copilot.story.look import Looks

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / "web" / "story" / "anim" / "assets"
G = 9.81
STAGE_W = 14.0
NOUN_ASSET = {"tree": "tree", "horse": "horse", "pony": "horse", "village": "village", "town": "village",
              "apple": "apple"}
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


def pelvis_y(p: Place) -> float:
    person = assets()["person"]
    return person["pelvis"].get(p.posture, person["pelvis"]["stand"])


class Compiler:
    def __init__(self) -> None:
        self.at: dict[str, Place] = {}
        self.hidden: dict[str, list[int]] = {}   # tree id -> fruit spots already fallen
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
        return p.x, pelvis_y(p) * self.scale(eid)

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
        ents = world.entities
        events = list(world.events)
        start: dict[str, Place] = {k: replace(v) for k, v in self.at.items() if k in ents}
        roles = _roles(world)
        skipped: list[dict[str, str]] = []
        drawn: list[str] = []
        for e in ents.values():
            if asset_for(e) or e.id in roles:
                drawn.append(e.id)
            else:
                skipped.append({"id": e.id, "name": e.name, "why": "no asset, no role"})
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
        for ev in events:
            if ev.op in ("move_to", "enter") and group and group[0] == ev.target:
                end = self._event(ev, world, at, group[1], timeline, fallback, queue=group[2])
                group, t = (group[0], group[1], group[2] + 1), max(t, end)
                continue
            t0 = t
            t = self._event(ev, world, at, t, timeline, fallback)
            group = (ev.target, t0, 1) if ev.op in ("move_to", "enter") and ev.target else None
        _style_hit_reacts(timeline)
        end = max([t] + [e.get("t1", e.get("t0", 0)) for e in timeline]) + 0.8
        for k, v in at.items():
            self.at[k] = v
        for f in fallback:
            log.info("[STORY] fallback %s", f)
        spec = {
            "rev": world.rev, "line": line, "g": G, "stage": {"w": STAGE_W, "sky": "day"},
            "entities": [self._ent(ents[i], start.get(i), at.get(i)) for i in drawn if i in start],
            "events": timeline, "fallback": fallback, "skipped": skipped, "duration": round(end, 3),
        }
        return spec

    def _ent(self, e: W.Entity, s: Optional[Place], f: Optional[Place]) -> dict[str, Any]:
        out: dict[str, Any] = {"id": e.id, "kind": e.kind, "asset": asset_for(e) or "box", "name": e.name,
                               "known": e.known, "start": asdict(s) if s else None, "end": asdict(f) if f else None}
        if e.kind == "person":
            look = dict(self.looks.looks.get(e.id, {}))
            look.pop("kind", None)
            out["look"], out["label"] = look, look.pop("label", "")
        if out["asset"] == "tree":
            out["fruit"] = fruit_of(e)
            out["hidden"] = list(self.hidden.get(e.id, []))
        return out

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
                if not q.carrier and not want.carrier and q.fruit < 0 and abs(want.x - q.x) > 0.3:
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
            at[i] = p
        self._mount_starts(world, at)
        self._walk_starts(world, at, free)
        for ev in world.events:
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
        if ev.actor not in at:
            fallback.append({"op": ev.op, "actor": ev.actor, "why": "not drawn"})
            return t
        p = at[ev.actor]
        if ev.op == "change_posture":
            if p.carrier or p.posture == ev.value:
                return t
            out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": ev.value, "t0": t, "t1": t + 0.9})
            p.posture = ev.value
            return t + 0.9
        if ev.op == "attach" and ev.value in ("ride", "sit_on") and ev.target in at \
                and asset_for(ents[ev.target]) == "horse":
            if p.carrier == ev.target:
                return t             # already on it: a restated ride never slides him across the stage
            h = at[ev.target]
            sx, sy = A["horse"]["saddle"]
            out.append({"op": "mount", "actor": ev.actor, "carrier": ev.target, "from": [p.x, pelvis_y(p)],
                        "to": [h.x + h.facing * sx, sy], "t0": t, "t1": t + 1.0})
            at[ev.actor] = replace(p, carrier=ev.target, anchor="saddle", posture="sit", facing=h.facing)
            return t + 1.1
        if ev.op in ("move_to", "enter") and ev.target in at:
            mover = p.carrier or ev.actor
            x1 = self._arrive_x(ev.target, at[mover], asset_for(ents[mover]), world, at)
            side = -1 if at[mover].x < at[ev.target].x else 1
            x1 += side * 0.85 * queue                    # the k-th to arrive stops behind the others (arrival side)
            p.tree = ""
            return self._walk(mover, x1, world, at, t, out)
        if ev.op == "fall":
            if ents[ev.actor].kind in ("person", "animal", "group"):    # it falls over, where it is
                if p.carrier or p.posture == "lie":
                    fallback.append({"op": "fall", "actor": ev.actor, "verb": ev.verb, "why": "no fall-off motion in P0"})
                    return t
                out.append({"op": "posture", "actor": ev.actor, "from": p.posture, "to": "lie", "t0": t, "t1": t + 0.6})
                p.posture = "lie"
                return t + 0.6
            return self._fall(ev, world, at, t, out, fallback)
        if ev.op == "speak":
            facing = self._face(ev.actor, ev.target, at, both=True)
            text = ev.value or ""
            dur = 0.5 + 0.06 * len(text) + 1.6
            out.append({"op": "speak", "actor": ev.actor, "to": ev.target, "text": text, "t0": t, "t1": t + dur,
                        "type_s": round(0.06 * len(text), 3), "facing": facing})
            return t + dur
        if ev.op == "react":
            out.append({"op": "react", "actor": ev.actor, "value": ev.value, "t0": t, "t1": t + 1.4})
            return t + 1.4
        if ev.op in ("look_at", "point_at") and (ev.target or ev.obj) in at:
            facing = self._face(ev.actor, ev.target or ev.obj, at, both=False)
            out.append({"op": ev.op.replace("_at", ""), "actor": ev.actor, "target": ev.target or ev.obj,
                        "t0": t, "t1": t + 1.2, "facing": facing})
            return t + 1.2
        fallback.append({"op": ev.op, "actor": ev.actor, "verb": ev.verb, "why": "no motion for this op in P0"})
        return t

    def _walk(self, mover: str, x1: float, world: W.World, at: dict[str, Place], t: float, out: list) -> float:
        """A move of `mover` (a person or a carrier) to x1; its riders go with it (their x follows the carrier)."""
        A = assets()
        m, kind = at[mover], asset_for(world.entities[mover])
        if abs(x1 - m.x) < 0.05:
            return t
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


def _roles(world: W.World) -> set[str]:
    """Ids with a physical role in the scene (in a relation, or acted on / moving): drawn even without an asset."""
    ids: set[str] = set()
    for r in world.relations:
        ids |= {r.a, r.b} | ({r.c} if r.c else set())
    for ev in world.events:
        if ev.op in ("fall", "throw", "attach", "move_to", "enter", "exit", "work", "detach"):
            ids |= {ev.actor} | ({ev.target} if ev.target else set()) | ({ev.obj} if ev.obj else set())
        elif ev.op in ("speak", "react", "look_at", "point_at", "change_posture"):
            ids.add(ev.actor)
            if ev.target and world.entities[ev.target].kind in ("person", "animal"):
                ids.add(ev.target)
    for e in world.entities.values():
        if e.kind in ("person", "animal", "group"):
            ids.add(e.id)
    return ids


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
        if e["op"] == "fall" and c.get("on") not in ("", "ground", None) and c["on"] not in said:
            timeline.append({"op": "react", "actor": c["on"], "value": "surprise", "t0": c["t"],
                             "t1": round(c["t"] + 1.6, 4), "style": "hit_reacts", "rub": c.get("part") == "head"})
