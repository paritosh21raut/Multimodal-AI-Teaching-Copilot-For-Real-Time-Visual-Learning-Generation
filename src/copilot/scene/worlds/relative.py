"""The relative world (F-015 L2a): velocities as vectors, seen from the ground or from a body (`scene.frame`).

    river   a boat crosses a river: heading straight across (`cross`: shortest time, it drifts downstream) or upstream
            so that it lands straight opposite (`cross_straight`: shortest path, sin a = u / v); or a said heading.
            Ground velocity = boat (in the water) + river; crossing time = width / the part across; drift = the part
            along the river x that time.
    rain    rain seen by a walker: v rain - v walker; the umbrella tilts from the vertical by atan(|across| / |down|),
            into the rain (rain falling straight down, a man walking: tan a = v man / v rain).
    free    bodies with velocities: two trains (relative speed, time to meet / catch up / pass) on lanes, or any
            bodies in a top view (relative velocity of the first two).

Velocities in SI: speed + `dir` (east / west / north / south, up / down) + `angle` toward `toward` (scene.spec DIRS).
Python computes every number; a value is printed only when every input of it is known (said / teacher / computed). A
direction not said is drawn, never printed (the readouts say "upstream", "forward", never a compass word).
Frames are in display seconds: a long crossing plays in at most MAX_RUN s (the readouts are static, computed)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Optional

from copilot.scene.spec import (
    BODY_KINDS, KNOWN, MAX_FRAME_POINTS, Behavior, Derived, Entity, Frames, Geom, Q, SceneSpec, Stage, Track, Vec,
)
from copilot.scene.validate import UNITS
from copilot.simulation.base import fmt

W, H, MARGIN = 1100, 740, 70
BODY_R = 30.0
MIN_RUN, MAX_RUN, RUN_S = 2.5, 6.0, 4.0   # display seconds of one run
DEFAULTS = {"body": 2.0, "boat": 4.0, "river": 2.0, "rain": 5.0, "width": 60.0, "gap": 100.0}  # drawn, never printed
AXIS = {"east": (1.0, 0.0), "right": (1.0, 0.0), "west": (-1.0, 0.0), "left": (-1.0, 0.0), "north": (0.0, 1.0),
        "up": (0.0, 1.0), "south": (0.0, -1.0), "down": (0.0, -1.0)}
VEC_PX = 170.0                              # the longest arrow of a velocity triangle (px)

V = tuple[float, float]


def _add(a: V, b: V) -> V:
    return a[0] + b[0], a[1] + b[1]


def _sub(a: V, b: V) -> V:
    return a[0] - b[0], a[1] - b[1]


def _mul(a: V, k: float) -> V:
    return a[0] * k, a[1] * k


def _len(a: V) -> float:
    return math.hypot(a[0], a[1])


def _known(*qs: Optional[Q]) -> bool:
    return all(q is not None and q.source in KNOWN for q in qs)


def _si(q: Optional[Q], fam: str) -> Optional[float]:
    return None if q is None else q.value * UNITS[fam].get(q.unit, 1.0)


@dataclass
class Vel:
    v: V
    known: bool                 # its speed (and angle) said / computed
    speed: float
    dir_said: bool = False      # its direction was said (else the default is drawn: a number resting on it is not
    tilt_ok: bool = True        # printed); tilt_ok: an angle has its `toward` said (or there is no angle)


HORIZONTAL = ("east", "west", "left", "right")


def velocity(e: Entity, default_dir: str, default_speed: float, b: Optional[Behavior] = None,
             horizontal: bool = False) -> Vel:
    """speed along dir, tilted by `angle` toward `toward` (a said angle with no `toward`: tilted to the default side,
    drawn only). horizontal: a side view's walker or a river drawn as a horizontal band: a vertical `dir` is not
    drawable there, so the default is drawn and the direction counts as not said."""
    qv = b.params.get("speed") if b is not None and "speed" in b.params else e.props.get("speed")
    qa = b.params.get("angle") if b is not None and "angle" in b.params else e.props.get("angle")
    s = _si(qv, "speed")
    s = default_speed if s is None else s
    said = bool(e.dir) and e.dir in AXIS and (not horizontal or e.dir in HORIZONTAL)
    u = AXIS[e.dir] if said else AXIS[default_dir]
    if qa is not None:
        t = AXIS.get(e.toward) if e.toward else (u[1], -u[0]) if u[0] == 0 else (0.0, 1.0)
        th = math.radians(_si(qa, "angle") or 0.0)
        u = (math.cos(th) * u[0] + math.sin(th) * t[0], math.cos(th) * u[1] + math.sin(th) * t[1])  # type: ignore
    return Vel(_mul(u, s), _known(qv) and (qa is None or _known(qa)), s, said, qa is None or bool(e.toward))


@dataclass
class Plan:
    """The world in metres (y up) before it is fitted to the stage."""
    case: str                                          # river | rain | free1d | free2d
    T: float                                           # physical run time (s)
    vel: dict[str, V] = field(default_factory=dict)    # ground velocities of the moving entities
    start: dict[str, V] = field(default_factory=dict)  # body start positions
    lane: dict[str, int] = field(default_factory=dict)
    derived: list[tuple[str, str, str]] = field(default_factory=list)  # (id, of, label: text) rows
    triangle: list[tuple[V, str, str]] = field(default_factory=list)  # (velocity, words, role) head to tail
    width: float = 0.0                                 # river
    flow: V = (0.0, 0.0)
    rain: V = (0.0, 0.0)
    umbrella: Optional[tuple[str, float]] = None       # walker id, tilt from the vertical (deg, + = toward +x)


def case_of(scene: SceneSpec) -> str:
    kinds = {e.kind for e in scene.entities}
    if "river" in kinds:
        return "river"
    if "rain" in kinds:
        return "rain"
    bodies = [e for e in scene.entities if e.kind in BODY_KINDS]
    return "free1d" if all(AXIS.get(e.dir or "east", (1, 0))[1] == 0 and "angle" not in e.props for e in bodies) \
        else "free2d"


def _w(e: Entity) -> str:
    """An entity's printed word: its said name, else ""."""
    return e.label.text if e.label.source == "said" and e.label.text else ""


def _speed_words(e: Entity, v: float, known: bool) -> str:
    w = _w(e)
    return (w + (" " if w else "") + f"{fmt(v)} m/s").strip() if known else w


def plan(scene: SceneSpec) -> Plan:
    case = case_of(scene)
    beh = {b.target: b for b in scene.behaviors}
    bodies = [e for e in scene.entities if e.kind in BODY_KINDS]
    if case == "river":
        river = next(e for e in scene.entities if e.kind == "river")
        rv = velocity(river, "east", DEFAULTS["river"], horizontal=True)  # the band is drawn horizontal
        qw = river.props.get("width")
        w = _si(qw, "length") or DEFAULTS["width"]
        uhat = _mul(rv.v, 1 / rv.speed) if rv.speed > 0 else AXIS[river.dir or "east"]
        n = (-uhat[1], uhat[0]) if uhat[1] != 0 or uhat[0] >= 0 else (uhat[1], -uhat[0])  # across: toward +y
        if n[1] < 0:
            n = (-n[0], -n[1])
        p = Plan("river", 0.0, width=w, flow=rv.v)
        p.vel[river.id] = rv.v
        times = []
        for i, e in enumerate(bodies):
            b = beh.get(e.id)
            kind = b.kind if b is not None and b.kind in ("cross", "cross_straight") else "cross" if not e.dir else ""
            bv = velocity(e, "north", DEFAULTS["boat"], b)
            u = rv.speed
            heading = bv.v
            can = True
            if kind == "cross":
                heading = _mul(n, bv.speed)
            elif kind == "cross_straight":
                if bv.speed > u and bv.speed > 0:
                    a = math.asin(u / bv.speed)
                    heading = _add(_mul(uhat, -bv.speed * math.sin(a)), _mul(n, bv.speed * math.cos(a)))
                else:
                    can, heading = False, _mul(n, bv.speed)
            g = _add(heading, rv.v)
            across = g[0] * n[0] + g[1] * n[1]
            along = g[0] * uhat[0] + g[1] * uhat[1]
            p.vel[e.id] = g
            p.start[e.id] = (0.0, 0.0)
            # cross / cross_straight need no direction; a boat's own heading needs its and the river's
            known = bv.known and rv.known and (kind != "" or bv.dir_said and bv.tilt_ok and rv.dir_said)
            T = w / across if across > 1e-9 else RUN_S
            times.append(T)
            if i > 0:
                continue  # the readouts and the triangle are for the first boat
            if known:
                p.derived.append((f"{e.id}_vg", e.id, f"Resultant speed: {fmt(_len(g))} m/s"))
            if kind == "cross_straight" and not can:
                p.derived.append((f"{e.id}_no", e.id, "Straight across: not possible ("
                                  + ("the boat has no speed)" if bv.speed <= 0 else "river too fast)")))
            elif kind == "cross_straight" and known:
                p.derived.append((f"{e.id}_head", e.id,
                                  f"Heading: {fmt(math.degrees(math.asin(u / bv.speed)))}° upstream"))
            if across > 1e-9 and known and _known(qw):
                p.derived.append((f"{e.id}_t", e.id, f"Crossing time: {fmt(T)} s"))
                if abs(along) > 1e-9:
                    p.derived.append((f"{e.id}_drift", e.id, f"Drift: {fmt(abs(along) * T)} m "
                                                             f"{'downstream' if along > 0 else 'upstream'}"))
            elif across <= 1e-9:
                p.derived.append((f"{e.id}_never", e.id, "Crossing: never (no speed across)"))
            p.triangle = [(heading, _speed_words(e, bv.speed, bv.known) or "heading", "main"),
                          (rv.v, _speed_words(river, rv.speed, rv.known) or "flow", "second"),
                          (g, "resultant" + (f" {fmt(_len(g))} m/s" if known else ""), "accent")]
        p.T = min(times) if times else RUN_S
        return p
    if case == "rain":
        rain = next(e for e in scene.entities if e.kind == "rain")
        rr = velocity(rain, "down", DEFAULTS["rain"])
        p = Plan("rain", RUN_S, rain=rr.v)
        p.vel[rain.id] = rr.v
        for i, e in enumerate(bodies):
            mv = velocity(e, "east", DEFAULTS["body"], beh.get(e.id), horizontal=True)  # a side view
            p.vel[e.id] = mv.v
            p.start[e.id] = (0.0, 0.0)
            p.lane[e.id] = i
            if i > 0:
                continue
            a = _sub(rr.v, mv.v)                             # the rain as seen by the walker
            tilt = math.degrees(math.atan2(-a[0], -a[1])) if _len(a) > 0 else 0.0  # into the rain
            p.umbrella = (e.id, tilt)
            # rain falls down unless told otherwise; a tilted rain needs its `toward` and the walker's direction
            tilted = abs(rr.v[0]) > 1e-9
            known = rr.known and mv.known and rr.tilt_ok and (not tilted or mv.dir_said)
            if known:
                seen = f"Rain seen by the {_w(e)}" if _w(e) else "Rain seen by the walker"
                p.derived.append((f"{e.id}_rain", e.id, f"{seen}: {fmt(_len(a))} m/s"))
                side = "" if abs(tilt) < 1e-9 or abs(mv.v[0]) < 1e-9 else " forward" if tilt * mv.v[0] > 0 \
                    else " backward"
                p.derived.append((f"{e.id}_umb", e.id, f"Umbrella tilt: {fmt(abs(tilt))}°{side}"))
            p.triangle = [(rr.v, _speed_words(rain, rr.speed, rr.known) or "rain", "second"),
                          (_mul(mv.v, -1), ("minus " + _speed_words(e, mv.speed, mv.known)).strip(), "main"),
                          (a, "seen by the " + (_w(e) or "walker"), "accent")]
        return p
    # free: bodies with velocities
    vels = {e.id: velocity(e, "east", DEFAULTS["body"], beh.get(e.id)) for e in bodies}
    p = Plan(case, RUN_S)
    for i, e in enumerate(bodies):
        p.vel[e.id] = vels[e.id].v
        p.lane[e.id] = i
        p.start[e.id] = (0.0, 0.0)
    if len(bodies) < 2:
        return p
    a, b = bodies[0], bodies[1]
    va, vb = vels[a.id], vels[b.id]
    rel = _sub(va.v, vb.v)
    known = va.known and vb.known and va.dir_said and vb.dir_said and va.tilt_ok and vb.tilt_ok
    if known:
        p.derived.append((f"{a.id}_rel", a.id, f"Relative speed: {fmt(_len(rel))} m/s"))
    qgap = next((e.props["gap"] for e in (a, b) if "gap" in e.props), None)
    gap = _si(qgap, "length") or DEFAULTS["gap"]
    if case == "free1d":
        ax, bx = va.v[0], vb.v[0]
        # the first said starts on the left, the second `gap` to its right (the compiler adds the left / rear one
        # first); a time to meet / catch up only when they close in (never assumed for bodies moving apart)
        p.start[b.id] = (gap, 0.0)
        closing = ax - bx
        if closing > 1e-9 and qgap is not None:
            meet = gap / closing
            word = "Time to meet" if ax * bx < 0 else "Time to catch up"
            if known and _known(qgap):
                p.derived.append((f"{a.id}_meet", a.id, f"{word}: {fmt(meet)} s"))
            p.T = max(RUN_S, meet * 1.3)
        la, lb = a.props.get("length"), b.props.get("length")
        rel1 = abs(ax - bx)
        if rel1 > 1e-9 and la is not None and lb is not None and known and _known(la, lb):
            total = (_si(la, "length") or 0.0) + (_si(lb, "length") or 0.0)
            p.derived.append((f"{a.id}_pass", a.id, f"Time to pass: {fmt(total / rel1)} s"))
    else:
        p.triangle = [(va.v, _speed_words(a, va.speed, va.known) or "first", "main"),
                      (_mul(vb.v, -1), ("minus " + _speed_words(b, vb.speed, vb.known)).strip(), "second"),
                      (rel, "seen by the " + (_w(b) or "second"), "accent")]
    return p


def _samples(T: float, n: int) -> list[float]:
    n = max(2, min(120, n))
    return [T * i / (n - 1) for i in range(n)]


def solve(scene: SceneSpec, band: Callable[[int], float]) -> SceneSpec:
    """The scene with its relative-world output: geoms, stage (river / rain / vectors / umbrella), frames, derived."""
    from copilot.scene.layout import MAX_DERIVED

    p = plan(scene)
    rows = p.derived[:MAX_DERIVED]
    derived = [Derived(id=i, of=of, label=t.split(": ", 1)[0], text=t.split(": ", 1)[1]) for i, of, t in rows]
    top = band(len(derived))
    bodies = [e for e in scene.entities if e.kind in BODY_KINDS]
    obs = p.vel.get(scene.frame, (0.0, 0.0))            # seen from this entity: its velocity is taken away
    T = max(p.T, 0.2)
    Td = min(MAX_RUN, max(MIN_RUN, T)) if p.case in ("river", "free1d") else RUN_S
    n = max(2, MAX_FRAME_POINTS // max(1, len(bodies)))
    ts = _samples(T, n)
    pos = {e.id: [_add(p.start.get(e.id, (0.0, 0.0)), _mul(_sub(p.vel.get(e.id, (0.0, 0.0)), obs), t)) for t in ts]
           for e in bodies}
    ground = H - MARGIN - 20
    stage = Stage()
    # the picture's box in stage px: under the readout card, the triangle on the right (river, rain, free2d)
    tri = bool(p.triangle)
    L, R = MARGIN, W - MARGIN - (VEC_PX + 120 if tri else 0)
    if p.case == "river":
        xs = [q[0] for ps in pos.values() for q in ps] + [0.0]
        x0, x1 = min(xs) - p.width * 0.3, max(xs) + p.width * 0.3
        y0, y1 = -p.width * 0.12, p.width * 1.12
        Y0, Y1 = top + 10, ground
    elif p.case == "rain":
        xs = [q[0] for ps in pos.values() for q in ps] + [0.0]
        x0, x1 = min(xs) - 1.0, max(xs) + 1.0
        y0, y1 = 0.0, 1.0
        Y0, Y1 = top + 10, ground
    elif p.case == "free1d":
        xs = [q[0] for ps in pos.values() for q in ps] + [0.0]
        x0, x1 = min(xs), max(xs) if max(xs) > min(xs) else min(xs) + 1.0
        y0, y1 = 0.0, 1.0
        Y0, Y1 = top + 10, ground
    else:
        xs = [q[0] for ps in pos.values() for q in ps] + [0.0]
        ys = [q[1] for ps in pos.values() for q in ps] + [0.0]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        Y0, Y1 = top + 50, H - MARGIN - 30
    bw, bh = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    pad = BODY_R * 2
    if p.case in ("river", "free2d"):
        k = min((R - L - 2 * pad) / bw, (Y1 - Y0 - 2 * pad) / bh) if p.case == "free2d" else min(
            (R - L) / bw, (Y1 - Y0) / bh)
    else:
        k = (R - L - 2 * pad) / bw
    ox = L + ((R - L) - bw * k) / 2 - x0 * k
    oy = Y0 + ((Y1 - Y0) - bh * k) / 2 + y1 * k if p.case in ("river", "free2d") else ground - BODY_R

    def px(q: V, lane: int = 0, gap: float = 0.0) -> tuple[float, float]:
        if p.case in ("rain", "free1d"):
            return round(ox + q[0] * k, 1), round(oy - lane * gap, 1)
        return round(ox + q[0] * k, 1), round(oy - q[1] * k, 1)

    lanes = max(1, len(bodies))
    gap = min(110.0, (ground - top - 2 * BODY_R - 20) / max(1, lanes - 1)) if lanes > 1 else 0.0
    r = BODY_R if gap == 0 or gap >= 2.4 * BODY_R else max(12.0, gap * 0.4)
    if p.case == "river":
        # the band of water spans the picture's width (a river is long); the flow arrow near its right end
        _, by0 = px((x0, p.width))
        _, by1 = px((x1, 0.0))
        stage.river = (float(L), float(R), by0, by1)
        f = p.flow
        fl = _len(f)
        if fl > 0:
            fx = f[0] / fl * 70
            mid = (by0 + by1) / 2
            cx = R - 110
            stage.flow = (round(cx - fx, 1), round(mid, 1), round(cx + fx, 1), round(mid, 1))
    else:
        stage.ground = (MARGIN, W - MARGIN, ground) if p.case in ("rain", "free1d") else None
        stage.lanes = [round(ground - BODY_R - i * gap + gap / 2, 1) for i in range(1, lanes)] if p.case == "free1d" \
            else []
    if p.case == "rain":
        a = _sub(p.rain, obs)
        stage.rain = (round(math.degrees(math.atan2(a[0], -a[1])), 2), round(min(900.0, 120 + _len(a) * 40), 1))
        if p.umbrella is not None:
            # into the rain as it is seen from the frame's body (the walker: the apparent rain)
            stage.umbrella = p.umbrella
    tracks: list[Track] = []
    out: list[Entity] = []
    for e in scene.entities:
        if e.kind not in BODY_KINDS:
            out.append(e.model_copy(update={"geom": None}))
            continue
        lane = p.lane.get(e.id, 0)
        pts = []
        for t, q in zip(ts, pos[e.id]):
            X, Y = px(q, lane, gap)
            v = _len(_sub(p.vel.get(e.id, (0.0, 0.0)), obs))
            pts.append((round(t * Td / T, 3), X, Y, 0.0, round(v, 3), round(_len(_sub(q, pos[e.id][0])), 3)))
        tracks.append(Track(id=e.id, pts=pts))
        X, Y = pts[0][1], pts[0][2]
        vx = _sub(p.vel.get(e.id, (0.0, 0.0)), obs)[0]
        out.append(e.model_copy(update={"geom": Geom(shape="body", c=(X, Y), r=r, flip=vx < -1e-9,
                                                     label_at=(X, Y - r - 16))}))
    if p.triangle:
        big = max(_len(v) for v, _, _ in p.triangle) or 1.0
        s = VEC_PX / big
        # head to tail: the first from a corner, the second from its tip, the resultant from the corner to the end;
        # the triangle centred in the column right of the picture
        a1 = (p.triangle[0][0][0] * s, -p.triangle[0][0][1] * s)
        a2 = (a1[0] + p.triangle[1][0][0] * s, a1[1] - p.triangle[1][0][1] * s)
        xs, ys = (0.0, a1[0], a2[0]), (0.0, a1[1], a2[1])
        cx, cy = W - MARGIN - 50 - VEC_PX / 2, top + 40 + VEC_PX / 2
        dx, dy = cx - (min(xs) + max(xs)) / 2, cy - (min(ys) + max(ys)) / 2
        corners = [(0.0, 0.0), a1, a2]
        pairs = ((0, 1), (1, 2), (0, 2))
        # each arrow's words outside the triangle: from its centre, away from the triangle's centroid
        gx, gy = sum(xs) / 3, sum(ys) / 3
        vecs = []
        for (i, j), (_, words, role) in zip(pairs, p.triangle):
            mx, my = (corners[i][0] + corners[j][0]) / 2, (corners[i][1] + corners[j][1]) / 2
            ox_, oy_ = mx - gx, my - gy
            d = math.hypot(ox_, oy_) or 1.0
            ox_, oy_ = ox_ / d, oy_ / d
            vecs.append(Vec(x0=round(corners[i][0] + dx, 1), y0=round(corners[i][1] + dy, 1),
                            x1=round(corners[j][0] + dx, 1), y1=round(corners[j][1] + dy, 1), text=words,
                            role=role,  # type: ignore[arg-type]
                            at=(round(mx + dx + ox_ * 22, 1), round(my + dy + oy_ * 22 + 8, 1)),
                            anchor="start" if ox_ > 0.35 else "end" if ox_ < -0.35 else "middle"))
        stage.vectors = vecs
    return scene.model_copy(update={"entities": out, "derived": derived, "stage": stage,
                                    "frames": Frames(period=round(Td, 3), hold=1.0, tracks=tracks)})
