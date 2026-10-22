"""The motion world (F-015 L1): textbook kinematics in closed form, sampled by Python into frames.

    move   x = v0 t + a t² / 2 along a lane (a < 0 slows it to a stop and it stays there)
    launch x = v cos θ t, y = v sin θ t − g t² / 2 until it lands
    fall   from a height h (with a horizontal speed, if one was said) until it lands

Values in SI. A default (speed, angle or height not said) moves the picture; a readout is printed only when every
input of the motion is known (scene.layout)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from copilot.scene.spec import KNOWN, Behavior, Entity, Q, SceneSpec
from copilot.scene.validate import UNITS

G_EARTH = 9.8
RUN_S = 4.0         # a straight-line motion is shown for this long, then it starts again
MAX_PTS = 120       # samples per track (≤ 400 in all: spec MAX_FRAME_POINTS)
DEFAULTS = {"speed": 2.0, "launch_speed": 15.0, "angle": 45.0, "height": 10.0}


@dataclass
class Path:
    id: str
    kind: str                                   # move | launch | fall | rest
    T: float                                    # run time (s)
    pts: list[tuple[float, float, float, float]] = field(default_factory=list)  # t, x m, y m, v m/s
    known: bool = False                         # every input known: readouts may be printed
    lane: int = 0


def _si(q: Optional[Q], fam: str) -> Optional[float]:
    return None if q is None else q.value * UNITS[fam].get(q.unit, 1.0)


def _get(e: Entity, b: Optional[Behavior], key: str) -> Optional[Q]:
    """A behaviour's param, else the body's prop of that name."""
    if b is not None and key in b.params:
        return b.params[key]
    return e.props.get(key)


def _ok(*qs: Optional[Q]) -> bool:
    return all(q is not None and q.source in KNOWN for q in qs)


GRID = (0.05, 0.1, 0.2, 0.25)  # sample spacing (s): a multiple of it is a Step (0.25 s), so a paused Step shows a sample


def _samples(T: float, n: int) -> list[float]:
    """Times on the finest grid that fits in n samples (the end time added when it is off the grid)."""
    n = max(2, min(MAX_PTS, n))
    for dt in GRID:
        k = int(T / dt + 1e-9)
        if k + 2 <= n:
            ts = [round(i * dt, 6) for i in range(k + 1)]
            return ts if abs(ts[-1] - T) < 1e-9 else ts + [T]
    return [T * i / (n - 1) for i in range(n)]


def path(e: Entity, b: Optional[Behavior], n: int) -> Path:
    if b is None:
        return Path(e.id, "rest", RUN_S, [(0.0, 0.0, 0.0, 0.0), (RUN_S, 0.0, 0.0, 0.0)], True)
    if b.kind == "move":
        qv, qa = _get(e, b, "speed"), _get(e, b, "acceleration")
        v0 = _si(qv, "speed")
        a = _si(qa, "acceleration") or 0.0
        v0 = DEFAULTS["speed"] if v0 is None else v0
        T = RUN_S
        stop = v0 / -a if a < 0 else math.inf
        pts = []
        for t in _samples(T, n):
            tt = min(t, stop)
            pts.append((t, v0 * tt + a * tt * tt / 2, 0.0, max(0.0, v0 + a * tt)))
        return Path(e.id, "move", T, pts, _ok(qv) and (qa is None or _ok(qa)))
    if b.kind == "launch":
        qv, qth = _get(e, b, "speed"), _get(e, b, "angle")
        v = _si(qv, "speed")
        v = DEFAULTS["launch_speed"] if v is None else v
        th = math.radians(_si(qth, "angle") if qth is not None else DEFAULTS["angle"])
        vx, vy = v * math.cos(th), v * math.sin(th)
        T = max(2 * vy / G_EARTH, 0.2)
        pts = [(t, vx * t, max(0.0, vy * t - G_EARTH * t * t / 2), math.hypot(vx, vy - G_EARTH * t))
               for t in _samples(T, n)]
        return Path(e.id, "launch", T, pts, _ok(qv, qth))
    qh, qv = _get(e, b, "height"), _get(e, b, "speed")  # fall
    h = _si(qh, "length")
    h = DEFAULTS["height"] if h is None or h <= 0 else h
    vx = _si(qv, "speed")
    vx = 0.0 if vx is None else vx
    T = math.sqrt(2 * h / G_EARTH)
    pts = [(t, vx * t, max(0.0, h - G_EARTH * t * t / 2), math.hypot(vx, G_EARTH * t)) for t in _samples(T, n)]
    return Path(e.id, "fall", T, pts, _ok(qh) and (qv is None or _ok(qv)))


def solve(scene: SceneSpec, bodies: list[Entity]) -> list[Path]:
    """One path per body; bodies moving in a straight line get a lane each."""
    behaviors = {b.target: b for b in scene.behaviors}
    n = max(2, min(MAX_PTS, 400 // max(1, len(bodies))))
    out = [path(e, behaviors.get(e.id), n) for e in bodies]
    lane = 0
    for p in out:
        if p.kind in ("move", "rest"):
            p.lane = lane
            lane += 1
    return out
