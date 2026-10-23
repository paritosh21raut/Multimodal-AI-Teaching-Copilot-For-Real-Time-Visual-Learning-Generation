"""The canvas world (F-016 C1): any thing the teacher imagines, where it is and what it does. No topic logic: a scene
graph of things, one place, relation primitives and action primitives, composed freely.

    place      -> stage.backdrop (illustrated by type: water, sky, space, mountain, street, nature, indoors ...)
    relations  -> positions: on / on_top_of rest on b's top; under / below; inside a place's medium (under the ocean)
                  or a thing; above (airborne); behind / in_front_of (z, scale); left_of / right_of / near / between;
                  holding / attached_to / part_of and things resting on or inside b move with b
    sizes      -> F-016 §4 + test32: the canvas is the whole slide (1920 x 1080 stage px, the title floats on it). Each
                  thing's typical size (scene.sizes: a boy > a book), compressed (^GAMMA, the smallest >= MIN_RATIO of the
                  biggest) so both stay readable; then everything is scaled up to fill the stage (one thing alone:
                  FILL of its height; something that moves leaves room to move); nothing < 8 %
    solids     -> a cube, cuboid, sphere ... in a canvas scene is a thing drawn as a shaded solid (look.form); a thing
                  inside a solid sits in its middle and the solid is drawn see-through
    parts      -> a part (part_of) is not drawn on the stage; focused, it is shown enlarged in a magnifier inset with a
                  leader line from where it is on its whole (feet at the bottom, a head at the top ...)
    actions    -> frames: fall / throw / move (fly, drive, walk, slide, roll, carry, push, pull) / brake are motion.py's
                  kinematics (real arcs, real stopping), scaled to the stage; the others are drawn motions (bob, spin,
                  grow, orbit ...). Brake: loose riders (on / inside the braking thing) lean and slide forward (inertia)
    focus      -> stage.camera, a view box around the focused things (<= 3x); a focused part: stage.magnifier

A number is printed only when every input of its motion is known (said or computed), as in the motion world."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from copilot.scene import pictures, sizes
from copilot.scene.spec import (
    BODY_KINDS, KNOWN, SOLID_KINDS, Backdrop, Behavior, Derived, Effect, Entity, Frames, Geom, Look, Magnifier, Q,
    SceneSpec, Stage, Track,
)
from copilot.scene.worlds import motion

W, H = 1920.0, 1080.0      # the whole slide (the stage is drawn 1:1 on the 1920 x 1080 slide)
MARGIN = 48.0
TOP = 150.0                # the title floats over the top left: things start below it
MIN_H, CHILD_MAX = 0.08, 0.75
GAMMA = 0.55               # typical sizes compressed: a book next to a boy is ~0.4 of him, not 0.16
MIN_RATIO = 0.2            # the smallest thing next to the biggest
FILL = 0.84                # one thing alone: this share of the room's height
MOVING_FILL = 0.6          # ... when something moves along (it needs room to move across)
FLYING_FILL = 0.42         # ... when something is thrown, falls or circles (room above and around it)
GROUND = H - 100.0
SURFACE, FLOOR = 210.0, H - 70.0
GAP = 70.0
HAND = (0.13, 0.12)        # a standing person's right hand, from the middle of their picture (share of its w, h)
ON_TOP = 0.1               # a thing on another sinks this far into its box (pictures have a margin at the top)
SPAN = 0.6 * W             # a move-like run's length at most (px)
RUN_S = motion.RUN_S
BRAKE_AT = 1.0            # a braking thing cruises this long first (s)
LEAN_MAX = 22.0           # a loose rider's lean (deg) at the strongest braking
MAX_ZOOM = 3.0
MAX_DERIVED = 4
# relations that carry a with b (a moves with b)
CARRIED = ("on", "on_top_of", "holding", "attached_to", "part_of", "inside")
LOOSE = ("on", "on_top_of", "inside")    # carried but not fixed: a rider leans / slides when b brakes
AIRBORNE = ("fly", "orbit")
ALONG = ("move", "fly", "drive", "walk", "slide", "roll", "carry", "push", "pull", "brake", "stop")
GROUNDED = ("plain", "mountain", "street", "nature", "indoors", "beach", "desert", "snow")


@dataclass
class Box:
    cx: float
    cy: float
    w: float
    h: float
    z: int = 0
    air: bool = False          # airborne (no resting on the ground)

    @property
    def top(self) -> float:
        return self.cy - self.h / 2

    @property
    def bottom(self) -> float:
        return self.cy + self.h / 2


# a sample: dx, dy (px, from the laid-out box), angle (deg), sx, sy, alpha, v (m/s), distance (m)
Sample = tuple[float, float, float, float, float, float, float, float]


@dataclass
class Act:
    f: Callable[[float], Sample]
    T: float = RUN_S
    known: bool = False
    physics: str = ""          # "move" | "launch" | "fall" | "brake": motion readouts may be printed
    brake: Optional[tuple[float, float, float]] = None  # (t brake starts, deceleration m/s², px per m): riders lean
    sign: float = 1.0          # +1 east / right, -1 west / left


@dataclass
class Plan:
    boxes: dict[str, Box] = field(default_factory=dict)
    acts: dict[str, Act] = field(default_factory=dict)


def _still(t: float) -> Sample:
    return (0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0)


def backdrop(scene: SceneSpec) -> Optional[Backdrop]:
    place = next((e for e in scene.entities if e.kind == "place"), None)
    typ = pictures.place_type(place.look.noun or place.name) if place is not None else "plain"
    name = place.label.text if place is not None and place.label.source == "said" else ""
    photo = place.look.photo if place is not None else ""
    if typ == "water":
        return Backdrop(type="water", name=name, ground=FLOOR, surface=SURFACE, photo=photo)
    if typ in ("sky", "space"):
        return Backdrop(type=typ, name=name, photo=photo)  # type: ignore[arg-type]
    return Backdrop(type=typ, name=name, ground=GROUND, photo=photo)  # type: ignore[arg-type]


def _sign(e: Entity) -> float:
    return -1.0 if e.dir in ("west", "left") else 1.0


def _q(v: float, src: str = "default") -> Q:
    return Q(value=v, unit="deg", source=src)  # type: ignore[arg-type]


# ---- actions ------------------------------------------------------------------------------------------------------
def _motion_act(e: Entity, b: Behavior, box: Box, ground: Optional[float], top: float) -> Act:
    """fall / throw / move-like / brake: motion.py's kinematics in metres, scaled to px on the stage."""
    sign = _sign(e)
    kind = "launch" if b.kind in ("throw", "launch") else "fall" if b.kind in ("fall", "bounce") else "move"
    beh = b
    if kind == "launch" and "angle" not in b.params and "angle" not in e.props:
        up = e.dir == "up"  # "straight up": the direction words say 90°; else a drawn 45° (never printed)
        beh = b.model_copy(update={"params": {**b.params, "angle": Q(value=90.0 if up else 45.0, unit="deg",
                                                                        source="said" if up else "default",
                                                                        said="up" if up else "")}})
    if kind == "move" and b.kind in ("brake", "stop"):
        return _brake_act(e, b, box, sign)
    p = motion.path(e, beh.model_copy(update={"kind": kind}), motion.MAX_PTS)
    pts = p.pts
    rest = (ground - box.h / 2) if ground is not None else H - MARGIN - box.h / 2
    if kind == "fall":
        h_m = max(pts[0][2], 1e-6)
        y0 = min(box.cy, top + box.h / 2) if not box.air else box.cy
        k = (rest - y0) / h_m
        x_m = max(pts[-1][1], 1e-6)
        if x_m > 1e-6:
            k = min(k, (W - MARGIN - box.w / 2 - box.cx) / x_m)
        dy0 = y0 - box.cy
        bounce = b.kind == "bounce"
        x_land = pts[-1][1] * k * sign

        def f(t: float) -> Sample:
            if bounce and t > p.T:  # after landing: bounces (restitution 0.6: drawn only)
                s = _bounce(t - p.T, p.T, h_m * k, rest - box.cy)
                return (x_land,) + s[1:]
            q = _at(pts, t)
            return (q[1] * k * sign, dy0 + (h_m - q[2]) * k, 0.0, 1.0, 1.0, 1.0, q[3], abs(q[1]))
        return Act(f, p.T * (2.2 if bounce else 1.0), p.known, "fall", sign=sign)
    if kind == "launch":
        apex = max(q[2] for q in pts)
        rng = max(pts[-1][1], 0.0)
        x0 = box.cx if rng < 1e-6 else MARGIN + box.w / 2 + 30
        k = (box.cy - top - box.h / 2) / max(apex, 1e-6)
        if rng > 1e-6:
            k = min(k, (W - MARGIN - box.w / 2 - x0) / rng)
        dx0 = (x0 - box.cx) if sign > 0 else (W - x0 - box.cx)
        spin = 360.0 / max(p.T, 0.2)

        def f(t: float) -> Sample:
            q = _at(pts, t)
            return (dx0 + q[1] * k * sign, -q[2] * k, (spin * min(t, p.T)) % 360 * sign, 1.0, 1.0, 1.0, q[3],
                    abs(q[1]))
        return Act(f, p.T, p.known, "launch", sign=sign)
    # move-like: along the ground (or the air), real speed / acceleration, the run fits the stage
    x_end = max(abs(pts[-1][1]), 1e-6)
    span = max(min(W - 2 * MARGIN - box.w, SPAN), 120.0)
    k = span / x_end
    start = -span / 2
    verb = b.kind

    def f(t: float) -> Sample:
        q = _at(pts, t)
        dx = (start + q[1] * k) * sign
        dy = ang = 0.0
        if verb in ("walk", "carry"):    # a step's bob
            dy = -6 * abs(math.sin(2 * math.pi * t * 1.6))
        elif verb == "fly":
            dy = 8 * math.sin(2 * math.pi * t / 1.8)
        elif verb == "roll":             # it turns through its own size
            ang = math.degrees(q[1] * k / max(box.h / 2, 1)) * sign
        return (dx, dy, ang, 1.0, 1.0, 1.0, q[3], abs(q[1]))
    return Act(f, p.T, p.known, "move", sign=sign)


def _bounce(t: float, T0: float, drop_px: float, floor_dy: float) -> Sample:
    """Bounces after a fall (restitution 0.6, drawn only): heights 0.36, 0.13 ... of the drop; a squash on landing."""
    e, h, tt = 0.6, drop_px, t
    for _ in range(4):
        h *= e * e
        half = T0 * math.sqrt(h / max(drop_px, 1e-6))
        if tt <= 2 * half:
            u = tt / max(2 * half, 1e-6)
            y = floor_dy - 4 * h * u * (1 - u)
            sq = 1.0 - 0.18 * max(0.0, 1 - min(u, 1 - u) * 12)
            return (0.0, y, 0.0, 2 - sq, sq, 1.0, 0.0, 0.0)
        tt -= 2 * half
    return (0.0, floor_dy, 0.0, 1.0, 1.0, 1.0, 0.0, 0.0)


def _brake_act(e: Entity, b: Behavior, box: Box, sign: float) -> Act:
    """Cruise BRAKE_AT s at v0, then decelerate to a stop (v0, a said or drawn defaults): x = v0 t + a t²/2."""
    qv = b.params.get("speed") or e.props.get("speed")
    qa = b.params.get("acceleration") or e.props.get("acceleration")
    v0 = motion._si(qv, "speed")
    v0 = 10.0 if v0 is None or v0 <= 0 else v0
    a = motion._si(qa, "acceleration")
    a = -v0 / (0.5 * RUN_S) if a is None or a == 0 else -abs(a)
    t_stop = BRAKE_AT + v0 / -a
    T = max(RUN_S, t_stop + 0.8)
    x_end = v0 * BRAKE_AT + v0 * v0 / (2 * -a)
    span = max(min(W - 2 * MARGIN - box.w, SPAN), 120.0)
    k = span / x_end

    def x_at(t: float) -> tuple[float, float]:
        if t <= BRAKE_AT:
            return v0 * t, v0
        tt = min(t - BRAKE_AT, v0 / -a)
        return v0 * BRAKE_AT + v0 * tt + a * tt * tt / 2, max(0.0, v0 + a * tt)

    def f(t: float) -> Sample:
        x, v = x_at(t)
        return ((-span / 2 + x * k) * sign, 0.0, 0.0, 1.0, 1.0, 1.0, v, x)
    known = motion._ok(qv) and motion._ok(qa)  # a drawn deceleration: no stopping distance printed
    return Act(f, T, known, "brake", brake=(BRAKE_AT, -a, k), sign=sign)


def _at(pts: list[tuple[float, float, float, float]], t: float) -> tuple[float, float, float, float]:
    """motion.Path samples at time t (linear between samples, the last held)."""
    if t <= pts[0][0]:
        return pts[0]
    for i in range(1, len(pts)):
        if pts[i][0] >= t:
            a, b = pts[i - 1], pts[i]
            k = (t - a[0]) / max(b[0] - a[0], 1e-9)
            return (t, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k, a[3] + (b[3] - a[3]) * k)
    return pts[-1]


def _drawn_act(e: Entity, b: Behavior, box: Box, plan: Plan, bd: Optional[Backdrop]) -> Act:
    """The motions with no physics to compute: drawn, never measured (no readout)."""
    k, T, sign = b.kind, RUN_S, _sign(e)
    if k == "appear":
        return Act(lambda t: (0, 0, 0, 0.6 + 0.4 * min(1, t / 0.6), 0.6 + 0.4 * min(1, t / 0.6), min(1.0, t / 0.6),
                              0, 0), T)
    if k == "vanish":
        return Act(lambda t: (0, 0, 0, 1, 1, max(0.0, 1 - t / 1.2), 0, 0), T)
    if k in ("rotate", "spin"):
        return Act(lambda t: (0, 0, (360.0 * t / (1.5 if k == "spin" else T)) % 360 * sign, 1, 1, 1, 0, 0), T)
    if k in ("grow", "shrink"):
        end = 1.6 if k == "grow" else 0.5
        return Act(lambda t: (0, 0, 0, 1 + (end - 1) * min(1, t / 2.5), 1 + (end - 1) * min(1, t / 2.5), 1, 0, 0), T)
    if k == "shake":
        return Act(lambda t: (10 * math.sin(2 * math.pi * 6 * t), 0, 4 * math.sin(2 * math.pi * 6 * t + 1), 1, 1, 1,
                              0, 0), T)
    if k == "sink":
        floor = (bd.ground if bd is not None and bd.ground is not None else H - MARGIN) - box.h / 2
        start = (bd.surface + box.h / 2 if bd is not None and bd.surface is not None else box.cy - 160)
        return Act(lambda t: (8 * math.sin(2 * math.pi * t / 1.6), start - box.cy + (floor - start) * min(1, t / 3.2),
                              6 * math.sin(2 * math.pi * t / 1.6), 1, 1, 1, 0, 0), T)
    if k == "float":
        dy = (bd.surface - box.cy if bd is not None and bd.surface is not None else 0.0)
        return Act(lambda t: (0, dy + 10 * math.sin(2 * math.pi * t / 2), 4 * math.sin(2 * math.pi * t / 2), 1, 1, 1,
                              0, 0), T)
    if k == "transform_into":
        return Act(lambda t: (0, 0, 0, 1, 1, 1 - min(1, max(0, (t - 1.0) / 1.5)), 0, 0), T)
    other = plan.boxes.get(b.b)
    if k == "orbit" and other is not None:
        R = 0.5 * max(other.w, other.h) + 0.5 * box.h + 20
        return Act(lambda t: (other.cx + R * math.cos(2 * math.pi * t / T) - box.cx,
                              other.cy + R * 0.55 * math.sin(2 * math.pi * t / T) - box.cy, 0, 1, 1, 1, 0, 0), T)
    if k in ("move_to", "collide") and other is not None:
        gap = (other.w + box.w) / 2 if k == "collide" else (other.w + box.w) / 2 + 20
        tx = other.cx - gap if other.cx >= box.cx else other.cx + gap
        dx = tx - box.cx

        def f(t: float) -> Sample:
            u = min(1.0, t / (T * 0.7))
            u = u * u if k == "collide" else 1 - (1 - u) ** 2   # collide: speeds up into it; move_to: eases in
            return (dx * u, 0, 0, 1, 1, 1, 0, 0)
        return Act(f, T, sign=1.0 if dx >= 0 else -1.0)
    return Act(_still, T)


def _follow_act(e: Entity, b: Behavior, box: Box, plan: Plan) -> Act:
    """follow / chase: b's path, lagging (follow) or closing in (chase), from a's own place."""
    lead = plan.acts.get(b.b)
    other = plan.boxes.get(b.b)
    if lead is None or other is None:
        return Act(_still, RUN_S)
    lag = 0.5 if b.kind == "follow" else 0.8
    off = box.cx - other.cx  # where a stands from b; a chase closes 70 % of that gap

    def f(t: float) -> Sample:
        s = lead.f(min(max(0.0, t - lag), lead.T))
        closing = 0.7 * min(1.0, t / lead.T) if b.kind == "chase" else 0.0
        return (s[0] - off * closing, s[1], 0, 1, 1, 1, 0, 0)
    return Act(f, lead.T, sign=lead.sign)


# ---- layout -------------------------------------------------------------------------------------------------------
def _relations(scene: SceneSpec) -> dict[str, tuple[str, str, str]]:
    return {r.a: (r.kind, r.b, r.c) for r in scene.relations}


def _ratios(things: list[Entity], rel: dict[str, tuple[str, str, str]]) -> dict[str, float]:
    """Each thing's height next to the biggest (1.0): typical sizes compressed; a thing on / held by / inside another
    at most CHILD_MAX of it (a rider smaller than its carrier)."""
    ids = {e.id for e in things}
    m = {e.id: max(sizes.typical(e.look.noun or e.name, e.size), 1e-3) for e in things}
    big = max(m.values(), default=1.0)
    own = {i: max(MIN_RATIO, (v / big) ** GAMMA) for i, v in m.items()}
    out: dict[str, float] = {}

    def r(i: str, depth: int = 0) -> float:
        if i in out:
            return out[i]
        v = own[i]
        kind, b, _ = rel.get(i, ("", "", ""))
        if b in ids and kind in CARRIED + ("under",) and depth < 40:
            v = min(v, CHILD_MAX * r(b, depth + 1))
        out[i] = v
        return v
    for e in things:
        r(e.id)
    return out


def _layout(scene: SceneSpec, things: list[Entity], bd: Optional[Backdrop], top: float) -> dict[str, Box]:
    """Typical sizes, then one scale for all that fills the stage (a few passes: the stacks and rows are measured)."""
    rel = _relations(scene)
    ratios = _ratios(things, rel)
    floor = bd.ground if bd is not None and bd.ground is not None else H - MARGIN
    room_h = max(floor - top - 50, 200.0)        # 50: a name above the tallest
    kinds = {b.kind for b in scene.behaviors}
    flying = bool(kinds & {"throw", "launch", "fall", "bounce", "orbit"})
    moving = bool(kinds & set(ALONG + ("follow", "chase")))
    cap = (FLYING_FILL if flying else MOVING_FILL if moving else FILL) * room_h
    scale = cap
    boxes: dict[str, Box] = {}
    for _ in range(6):
        boxes = _arrange(scene, things, bd, top, {i: v * scale for i, v in ratios.items()}, rel)
        shown = [b for i, b in boxes.items() if rel.get(i, ("", "", ""))[0] != "part_of"]  # a part: the magnifier
        if not shown:
            break
        x0 = min(b.cx - b.w / 2 for b in shown)
        x1 = max(b.cx + b.w / 2 for b in shown)
        y0 = min(b.top for b in shown)
        y1 = max(b.bottom for b in shown)
        k = min((W - 2 * MARGIN) / max(x1 - x0, 1.0), (floor - top - 40) / max(y1 - y0, 1.0))
        new = min(cap, scale * min(k, 1.5))
        if abs(new - scale) < 0.02 * scale:
            break
        scale = new
    return boxes


def _arrange(scene: SceneSpec, things: list[Entity], bd: Optional[Backdrop], top: float, hs: dict[str, float],
             rel: dict[str, tuple[str, str, str]]) -> dict[str, Box]:
    ids = {e.id for e in things}
    hs = {i: max(v, MIN_H * H) for i, v in hs.items()}
    acts = {b.target: b.kind for b in scene.behaviors if b.kind != "emit"}
    ground = bd.ground if bd is not None else None
    water = bd is not None and bd.type == "water"
    forms = {e.id for e in things if e.look.form}
    people = {e.id for e in things if pictures.person(e.look.noun or e.name)}
    roots = [e for e in things if rel.get(e.id, ("", "", ""))[1] not in ids]
    # roots side by side, as wide as they are tall (pictures are square)
    total = sum(hs[e.id] for e in roots) + GAP * max(0, len(roots) - 1)
    boxes: dict[str, Box] = {}
    x = (W - total) / 2
    for e in roots:
        h = hs[e.id]
        kind = rel.get(e.id, ("", "", ""))[0]
        air = (acts.get(e.id) in AIRBORNE or kind == "above" or bd is not None and bd.type in ("sky", "space")
               or ground is None)
        if water and acts.get(e.id) == "float":
            cy = SURFACE
        elif water and kind in ("", "inside", "under", "at", "on"):
            cy = FLOOR - h / 2                   # under the ocean: in the water, resting on the sea floor
        elif air and ground is not None:         # in the air above the ground, under the title band
            cy = max(top + h / 2 + 50, min(H * 0.45, ground - h / 2 - 80))
        elif air:                                # sky, space: in the middle of the room
            cy = top + (H - MARGIN - top) / 2
        else:
            cy = ground - h / 2                  # type: ignore[operator]
        boxes[e.id] = Box(x + h / 2, cy, h, h, 0, air)
        x += h + GAP
    # the others, placed by their relation to a placed thing (a chain: its b first)
    pending = [e for e in things if e.id not in boxes]
    for _ in range(len(pending) + 1):
        left = []
        for e in pending:
            kind, b, c = rel[e.id]
            if b not in boxes or (kind == "between" and c not in boxes):
                left.append(e)
                continue
            boxes[e.id] = _place(kind, hs[e.id], boxes[b], boxes.get(c), ground, b in forms, b in people)
        if len(left) == len(pending):
            break
        pending = left
    for e in pending:  # unreachable (cycles are refused): beside the stage's middle
        boxes[e.id] = Box(W / 2, H / 2, hs[e.id], hs[e.id])
    # a stack that rises above the top band comes down (an airborne root)
    for e in roots:
        tree = [i for i in boxes if _root_of(i, rel, ids) == e.id]
        hi = min(boxes[i].top for i in tree)
        if hi < top + 40:
            d = top + 40 - hi
            for i in tree:
                boxes[i].cy += d
    return boxes


def _root_of(i: str, rel: dict[str, tuple[str, str, str]], ids: set[str]) -> str:
    seen: set[str] = set()
    while rel.get(i, ("", "", ""))[1] in ids and i not in seen:
        seen.add(i)
        i = rel[i][1]
    return i


def _place(kind: str, h: float, b: Box, c: Optional[Box], ground: Optional[float], in_form: bool = False,
           person: bool = False) -> Box:
    w = h
    if kind in ("on", "on_top_of"):
        return Box(b.cx, b.top - h / 2 + ON_TOP * b.h, w, h, b.z + 1, b.air)
    if kind == "above":
        return Box(b.cx, b.top - h / 2 - GAP, w, h, b.z, True)
    if kind in ("under", "below"):
        if kind == "under" and not b.air and ground is not None:
            # under a tree / a table: on the ground beneath it, a person a little off its middle, in front
            return Box(b.cx + (0.18 * b.w if h > 0.5 * b.h else 0.0), b.bottom - h / 2, w, h, b.z + 1)
        cy = b.bottom + h / 2 + (GAP if kind == "below" else 10)
        if ground is not None:
            cy = min(cy, ground - h / 2)
        return Box(b.cx, cy, w, h, b.z, b.air)
    if kind == "inside":
        if in_form:  # inside a cube / a sphere: in its middle, the solid drawn see-through
            h = min(h, 0.5 * b.h)
            return Box(b.cx, b.cy, h, h, b.z + 1, b.air)
        # in a vehicle / a box: in its upper middle (a window), smaller than it
        h = min(h, 0.45 * b.h)
        return Box(b.cx + 0.08 * b.w, b.cy - 0.12 * b.h, h, h, b.z + 1, b.air)
    if kind == "holding" and person:  # in a person's hand: their body is ~a third of the picture's square
        return Box(b.cx + HAND[0] * b.w + 0.3 * h, b.cy + HAND[1] * b.h, w, h, b.z + 1, b.air)
    if kind in ("holding", "attached_to"):  # in the hand: at its side, a little below the middle
        return Box(b.cx + 0.25 * b.w + 0.3 * h, b.cy + 0.08 * b.h, w, h, b.z + 1, b.air)
    if kind == "part_of":
        return Box(b.cx, b.cy, w, h, b.z + 1, b.air)
    if kind == "in_front_of":
        return Box(b.cx + 0.3 * b.w, b.bottom - h / 2 + 24, w, h, b.z + 1, b.air)
    if kind == "behind":
        s = 0.85
        return Box(b.cx - 0.3 * b.w, b.bottom - h * s / 2 - 30, w * s, h * s, b.z - 1, b.air)
    if kind == "between" and c is not None:
        return Box((b.cx + c.cx) / 2, (b.bottom + c.bottom) / 2 - h / 2, w, h, b.z, b.air and c.air)
    if kind == "around":
        return Box(b.cx + 0.5 * b.w + w / 2 + 10, b.cy, w, h, b.z + 1, b.air)
    side = -1 if kind == "left_of" else 1
    gap = 20.0 if kind == "near" else GAP
    return Box(b.cx + side * (b.w / 2 + gap + w / 2), b.bottom - h / 2, w, h, b.z, b.air)


# where a part is on its whole (fractions of the whole's width and height from its centre); else its middle
_PART_AT: dict[tuple[float, float], tuple[str, ...]] = {
    (0.0, 0.42): ("foot", "feet", "leg", "legs", "wheel", "wheels", "tyre", "tire", "paw", "paws", "hoof", "hooves",
                  "root", "roots", "base", "shoe", "shoes", "claw", "claws", "toe", "toes"),
    (0.0, -0.38): ("head", "hair", "hat", "roof", "cap", "ear", "ears", "eye", "eyes", "nose", "mouth", "beak", "face",
                   "horn", "horns", "crown", "leaf", "leaves", "top", "antenna", "chimney", "lid", "tip"),
    (-0.4, 0.0): ("tail",),
    (0.38, 0.05): ("hand", "hands", "arm", "arms", "finger", "fingers", "handle"),
    (0.1, -0.08): ("wing", "wings", "fin", "fins", "window", "windows", "door", "engine", "heart", "chest", "body"),
}
PART_AT = {w: at for at, ws in _PART_AT.items() for w in ws}


def _magnifier(scene: SceneSpec, boxes: dict[str, Box], rel: dict[str, tuple[str, str, str]], top: float,
               flips: dict[str, bool]) -> Optional[Magnifier]:
    """The first focused part: an inset on the side away from its whole, a leader line from where it is on it."""
    part = next((i for i in scene.focus if rel.get(i, ("", "", ""))[0] == "part_of" and rel[i][1] in boxes), None)
    if part is None:
        return None
    e = scene.get(part)
    whole = boxes[rel[part][1]]
    noun = (e.look.noun or e.name) if e is not None else ""
    fx, fy = PART_AT.get(noun.lower(), PART_AT.get(pictures.assets.head(noun), (0.0, 0.0)))
    if flips.get(rel[part][1]):
        fx = -fx
    at = (round(whole.cx + fx * whole.w, 1), round(whole.cy + fy * whole.h, 1))
    r = round(0.24 * H, 1)
    cx = W - MARGIN - r if whole.cx < W / 2 else MARGIN + r
    return Magnifier(of=part, at=at, c=(round(cx, 1), round(top + r + 10, 1)), r=r)


# ---- solve --------------------------------------------------------------------------------------------------------
def _named(e: Entity, what: str) -> str:
    return f"{what} of the {e.label.text}" if e.label.source == "said" and e.label.text else what


def _as_things(scene: SceneSpec) -> SceneSpec:
    """A solid in a canvas scene ("a sphere inside the cuboid", "a cone on the cylinder") is a thing drawn as a shaded
    solid: placed by the canvas relations like any other thing."""
    ents = [e.model_copy(update={"look": e.look.model_copy(update={"form": e.kind, "noun": e.look.noun or e.kind})})
            if e.kind in SOLID_KINDS and e.look.form != e.kind and e.look.pick != "teacher" else e for e in scene.entities]
    return scene.model_copy(update={"entities": ents})


def band(n_derived: int) -> float:
    """Where things may start: under the title, and under the readout card when there is one."""
    return TOP + (34 + n_derived * 52 + 24 if n_derived else 0)


def solve(scene: SceneSpec, _band: Optional[Callable[[int], float]] = None) -> SceneSpec:
    scene = _as_things(scene)
    things = [e for e in scene.entities if e.kind == "thing" or e.kind in BODY_KINDS or e.kind in SOLID_KINDS]
    bd = backdrop(scene)
    beh = {b.target: b for b in scene.behaviors if b.kind != "emit"}
    rel = _relations(scene)
    # readouts first (they take the top band): the kinematics with every input known
    physics = {i: b for i, b in beh.items() if b.kind in ("fall", "throw", "launch", "bounce") + ALONG}
    plan = Plan()
    ground = bd.ground if bd is not None else None
    top = band(0)
    boxes = _layout(scene, things, bd, top)
    plan.boxes = boxes
    ents = {e.id: e for e in things}
    for i, b in physics.items():
        if i in boxes:
            plan.acts[i] = _motion_act(ents[i], b, boxes[i], ground, top)
    derived: list[Derived] = []
    for i, a in plan.acts.items():
        e = ents[i]
        if not a.known or beh[i].kind == "bounce":  # bounces are drawn (restitution not said): no readout
            continue
        derived.append(Derived(id=f"{i}_v", of=i, label=_named(e, "Speed"), live="v", unit="m/s"))
        if a.physics in ("move", "brake"):
            derived.append(Derived(id=f"{i}_x", of=i, label=_named(e, "Distance"), live="x", unit="m"))
    derived = derived[:MAX_DERIVED]
    if derived:  # the readout card takes the top band: lay out again below it
        top = band(len(derived))
        boxes = _layout(scene, things, bd, top)
        plan = Plan(boxes)
        for i, b in physics.items():
            if i in boxes:
                plan.acts[i] = _motion_act(ents[i], b, boxes[i], ground, top)
    for i, b in beh.items():
        if i in boxes and i not in plan.acts and b.kind not in ("follow", "chase"):
            plan.acts[i] = _drawn_act(ents[i], b, boxes[i], plan, bd)
    for i, b in beh.items():
        if i in boxes and b.kind in ("follow", "chase"):
            plan.acts[i] = _follow_act(ents[i], b, boxes[i], plan)
    frames = _frames(scene, things, plan, rel)
    hidden = {r.a for r in scene.relations if r.kind == "part_of"}  # a focused part: the magnifier
    glass = {r.b for r in scene.relations if r.kind == "inside" and r.b in ents and ents[r.b].look.form}
    # a thing with another resting on / above / held by it has its name at its side (the one on top has the top)
    topped = {r.b for r in scene.relations if r.kind in ("on", "on_top_of", "above", "holding", "attached_to", "inside")
              and r.a in boxes}
    out: list[Entity] = []
    for e in scene.entities:
        bx = boxes.get(e.id)
        if bx is None:
            out.append(e.model_copy(update={"geom": None}))
            continue
        a = plan.acts.get(e.id)
        flip = a is not None and a.sign < 0
        shadow = ground if ground is not None and not (bd is not None and bd.type == "water"
                                                        and bx.cy < (bd.surface or 0) + bx.h) else None
        out.append(e.model_copy(update={"geom": Geom(
            shape="thing", c=(round(bx.cx, 1), round(bx.cy, 1)), r=round(bx.h / 2, 1),
            wh=(round(bx.w, 1), round(bx.h, 1)), z=bx.z, hidden=e.id in hidden, glass=e.id in glass, flip=flip,
            ground=shadow,
            label_at=(round(bx.cx - bx.w / 2 - 14, 1), round(bx.cy + 12, 1)) if e.id in topped
            else (round(bx.cx, 1), round(bx.top - 16, 1)))}))
    effects = [Effect(of=b.target, kind=b.text) for b in scene.behaviors  # type: ignore[arg-type]
               if b.kind == "emit" and b.target in boxes]
    effects += [Effect(of=b.target, kind=b.kind, dir=0.0 if _sign(ents[b.target]) > 0 else 180.0)  # type: ignore[arg-type]
                for b in scene.behaviors if b.kind in ("push", "pull") and b.target in boxes]
    flips = {e.id: bool(e.geom and e.geom.flip) for e in out}
    stage = Stage(backdrop=bd, effects=effects, camera=camera(scene, boxes, frames, rel), size=(W, H),
                  magnifier=_magnifier(scene, boxes, rel, top, flips))
    return scene.model_copy(update={"entities": out, "derived": derived, "stage": stage, "frames": frames})


def _frames(scene: SceneSpec, things: list[Entity], plan: Plan, rel: dict[str, tuple[str, str, str]]
            ) -> Optional[Frames]:
    """One track per thing that moves (its own action and its carriers'), on one time grid."""
    ids = {e.id for e in things}

    def carriers(i: str) -> list[tuple[str, str]]:
        out, seen = [], set()
        while rel.get(i, ("", "", ""))[0] in CARRIED and rel[i][1] in ids and i not in seen:
            seen.add(i)
            out.append((rel[i][0], rel[i][1]))
            i = rel[i][1]
        return out
    moving = [e.id for e in things if e.id in plan.acts or any(c in plan.acts for _, c in carriers(e.id))]
    if not moving:
        return None
    period = max(plan.acts[i].T for i in plan.acts)
    n = max(2, min(motion.MAX_PTS, 400 // len(moving)))
    ts = motion._samples(period, n)
    tracks = []
    for i in moving:
        bx = plan.boxes[i]
        own = plan.acts.get(i)
        chain = carriers(i)
        pts, sa = [], []
        for t in ts:
            s = own.f(min(t, own.T)) if own is not None else _still(t)
            dx, dy, ang = s[0], s[1], s[2]
            for k, (kind, c) in enumerate(chain):
                ca = plan.acts.get(c)
                if ca is None:
                    continue
                cs = ca.f(min(t, ca.T))
                dx, dy = dx + cs[0], dy + cs[1]
                if k == 0 and kind in LOOSE and ca.brake is not None:  # a loose rider: inertia when b brakes
                    lean, slide = _rider(t, ca, plan.boxes[c].w)
                    ang += lean * ca.sign
                    dx += slide * ca.sign
            pts.append((round(t, 3), round(bx.cx + dx, 1), round(bx.cy + dy, 1), round(ang, 1), round(s[6], 3),
                        round(s[7], 3)))
            sa.append((round(s[3], 3), round(s[4], 3), round(s[5], 3)))
        tracks.append(Track(id=i, pts=pts, sa=sa if any(q != (1.0, 1.0, 1.0) for q in sa) else []))
    return Frames(period=round(period, 3), hold=1.0, tracks=tracks)


def _rider(t: float, ca: Act, carrier_w: float) -> tuple[float, float]:
    """A loose rider when its carrier brakes (deceleration a): it keeps moving (slides forward relative to the
    carrier by a t²/2, at most a fifth of the carrier) and leans forward; after the stop it straightens up."""
    assert ca.brake is not None
    t0, a, k = ca.brake
    if t <= t0:
        return 0.0, 0.0
    v0 = ca.f(t0)[6]
    t_stop = t0 + v0 / a if a > 0 else t0
    tb = min(t, t_stop) - t0
    slide = min(0.2 * carrier_w, 0.5 * a * tb * tb * k)
    lean_full = min(LEAN_MAX, 2.2 * a)
    if t <= t_stop:
        lean = lean_full * min(1.0, (t - t0) / 0.25)
    else:
        lean = lean_full * max(0.0, 1 - (t - t_stop) / 0.6)
    return lean, slide


def camera(scene: SceneSpec, boxes: dict[str, Box], frames: Optional[Frames],
           rel: Optional[dict[str, tuple[str, str, str]]] = None) -> Optional[tuple[float, float, float, float]]:
    """The focused things' view box at their laid-out place, padded, at most MAX_ZOOM, the stage's aspect; None: all.
    One focused thing that moves: the renderer keeps the box centred on it (the camera follows). A focused part is
    shown by the magnifier, not the camera."""
    rel = rel or {}
    ids = [i for i in scene.focus if i in boxes and rel.get(i, ("", "", ""))[0] != "part_of"]
    if not ids:
        return None
    xs0, ys0, xs1, ys1 = [], [], [], []
    for i in ids:
        b = boxes[i]
        xs0.append(b.cx - b.w / 2)
        xs1.append(b.cx + b.w / 2)
        ys0.append(b.top - 50)  # its name above it
        ys1.append(b.bottom)
    x0, x1, y0, y1 = min(xs0), max(xs1), min(ys0), max(ys1)
    w, h = (x1 - x0) * 1.35, (y1 - y0) * 1.35
    w, h = max(w, W / MAX_ZOOM), max(h, H / MAX_ZOOM)
    if w / h > W / H:
        h = w * H / W
    else:
        w = h * W / H
    if w >= W or h >= H:
        return None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    x = min(max(cx - w / 2, 0.0), W - w)
    y = min(max(cy - h / 2, 0.0), H - h)
    return (round(x, 1), round(y, 1), round(w, 1), round(h, 1))
