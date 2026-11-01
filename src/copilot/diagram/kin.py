"""Motion results -> the patch's `mech` block (F-019 M5): the scene laid out from the solver's world positions
(metres, y up) on the slide (diagram units, y down), the velocity arrows, the values panel and the tracks.

    a throw / a fall   a ground; the body at its launch point; the dotted path (trail); launch v and its components
    one body / 2 cars  a road per lane; the body moves by its x(t) (the run fits the slide); its v arrow rides with it
    rain and man       the man walks; the rain falls slanted by the computed θ (as the man sees it); his umbrella
                       tilts by θ; the velocity triangle v_r, −v_m, v_rel beside the scene
    boat and river     the river band (its width to the same scale as the drift); the boat's v_b, the flow, the
                       resultant; the boat crosses by the solver's path
    circular           the circle path, the body on it (orbit track), v along the path and a_c to the centre turn
                       with the body
Body sizes are not to scale (badge); positions and times are the solver's, scaled. The browser only draws.
"""
from __future__ import annotations

import math
import textwrap
from typing import Any, Optional

from copilot.diagram import mech
from copilot.diagram import parts as P
from copilot.diagram.graph import Graph
from copilot.diagram.layout import AREA, VIEW, Layout, Node, label_size
from copilot.diagram.solvers.base import Results, Value
from copilot.diagram.solvers.kinematics import KINDS, Path, Vec

RUN_MAX = 6.0       # s: a longer motion is shown faster (positions are the solver's)
TRAIL_PTS = 60
ARROW = (70.0, 190.0)
BADGE = "body sizes not to scale"


def wants(g: Graph) -> bool:
    """A motion scene: a motion part and no block / mass (those are the contact solver's)."""
    return any(p.kind in KINDS for p in g.parts.values()) and not any(
        p.kind in ("block", "mass") for p in g.parts.values())


def build(g: Graph, L: Layout, res: Optional[Results]) -> dict[str, Any]:
    if res is None or res.domain != "motion":
        return {"forces": [], "panel": None, "notes": [], "tracks": [], "simulated": False}
    area = (AREA[0] + 20, AREA[1] + 30, AREA[2] - (mech.PANEL_W if res.values else 0) - 30, AREA[3] - 10)
    S = _Scene(g, L, res, area)
    paths = {p.on: p for p in res.paths}
    if any(p.orbit for p in res.paths):
        S.circle(next(p for p in res.paths if p.orbit))
    elif g.of("rain") and g.of("man"):
        S.rain(paths)
    elif g.of("river") and g.of("boat"):
        S.river(paths)
    elif any(g.parts[p.on].kind == "ball" for p in res.paths if p.on in g.parts) and any(
            m.state in ("flies", "falls") or g.parts[m.on].kind == "ball" for m in res.motions if m.on in g.parts):
        S.flight(res.paths[0])
    else:
        S.lanes(res.paths)
    notes = [ln for n in res.notes for ln in textwrap.wrap(n, mech.NOTE_CHARS)]
    out = {"forces": S.arrows, "panel": mech._fit(_panel(g, res), notes) if res.values else None, "notes": notes,
           "tracks": S.tracks, "marks": [], "simulated": True, "badge": BADGE if res.paths else ""}
    return out


class _Scene:
    def __init__(self, g: Graph, L: Layout, res: Results, area: tuple[float, float, float, float]) -> None:
        self.g, self.L, self.res, self.area = g, L, res, area
        self.arrows: list[dict[str, Any]] = []
        self.tracks: list[dict[str, Any]] = []
        vs = [math.hypot(v.vx, v.vy) for v in res.vectors if v.value.known]
        self.vmax = max(vs) if vs else 1.0
        L.scale = 1.0
        for n in L.nodes.values():  # the library's sizes (the K1 layout scales a lone part up)
            row = P.kind(n.kind) or {}
            if n.kind in KINDS and row:
                n.w, n.h = float(row["w"]), float(row["h"])

    # ---- pieces ---------------------------------------------------------------------------------------------------
    def _len(self, v: Vec) -> float:
        if not v.value.known:
            return (ARROW[0] + ARROW[1]) / 2
        k = math.hypot(v.vx, v.vy) / self.vmax if self.vmax else 1.0
        return ARROW[0] + (ARROW[1] - ARROW[0]) * k

    def arrow(self, v: Vec, x: float, y: float, length: Optional[float] = None) -> tuple[float, float]:
        n = math.hypot(v.vx, v.vy) or 1.0
        ln = self._len(v) if length is None else length
        x2, y2 = x + v.vx / n * ln, y - v.vy / n * ln  # world y up -> screen y down
        text = v.value.text()
        ang = math.atan2(y2 - y, x2 - x)
        lx, ly = x2 + 14 * math.cos(ang), y2 + 14 * math.sin(ang) + 10
        anchor = "start" if math.cos(ang) > 0.3 else "end" if math.cos(ang) < -0.3 else "middle"
        if anchor == "middle":
            ly += 22 if math.sin(ang) > 0 else -14
        self.arrows.append({"id": v.id, "on": v.on, "kind": "velocity", "role": v.role, "x1": round(x, 1),
                            "y1": round(y, 1), "x2": round(x2, 1), "y2": round(y2, 1), "text": text,
                            "src": v.value.src, "lx": round(lx, 1), "ly": round(ly, 1), "anchor": anchor,
                            "said_dir": not v.dashed})
        return x2, y2

    def ground(self, gid: str, y: float, x0: Optional[float] = None, x1: Optional[float] = None) -> None:
        a = self.area
        x0, x1 = a[0] if x0 is None else x0, a[2] if x1 is None else x1
        self.L.nodes[gid] = Node(gid, "floor", x1 - x0, 26.0, (x0 + x1) / 2, y + 13.0)

    def dim(self, lid: str, on: str, text: str, x: float, y: float) -> None:
        """A said height / width / radius written beside its line, starting at x."""
        w, _ = label_size(text)
        self.L.labels.append({"id": lid, "for": lid, "text": text, "src": "said", "x": round(x + w / 2, 1),
                              "y": round(y, 1), "anchor": "middle"})

    def put(self, pid: str, x: float, y: float, rot: float = 0.0, **attr: Any) -> Node:
        n = self.L.nodes[pid]
        n.cx, n.cy, n.rot = x, y, rot
        n.attr.update(attr)
        return n

    def path_track(self, pid: str, pts: list[tuple[float, float, float]], to_screen: Any, T: float) -> None:
        n = self.L.nodes[pid]
        k = min(1.0, RUN_MAX / T) if T > 0 else 1.0
        step = max(1, len(pts) // 90)
        sp = [[round(t * k, 3), round(to_screen(x, y)[0] - n.cx, 1), round(to_screen(x, y)[1] - n.cy, 1)]
              for t, x, y in pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])]
        if len(sp) < 2:
            return
        self.tracks.append({"id": pid, "kind": "path", "pts": sp, "run": sp[-1][0], "hold": mech.HOLD})

    def trail(self, pid: str, pts: list[tuple[float, float, float]], to_screen: Any) -> None:
        step = max(1, len(pts) // TRAIL_PTS)
        sel = pts[::step] + ([pts[-1]] if (len(pts) - 1) % step else [])
        self.L.wires.append({"id": f"trail_{pid}", "kind": "trail",
                             "pts": [[round(c, 1) for c in to_screen(x, y)] for _, x, y in sel]})

    # ---- scenes ---------------------------------------------------------------------------------------------------
    def flight(self, p: Path) -> None:
        a = self.area
        n = self.L.nodes[p.on]
        gy = a[3] - 40
        self.ground("kin_ground", gy)
        xs, ys = [q[1] for q in p.pts], [q[2] for q in p.pts]
        xspan, yspan = max(xs) - min(xs), max(ys) - min(ys) if len(ys) > 1 else max(ys)
        top = max(max(ys), 0.0)
        room_w, room_h = a[2] - a[0] - 260, gy - n.h / 2 - a[1] - 120
        s = min(room_w / xspan if xspan > 1e-6 else math.inf, room_h / top if top > 1e-6 else math.inf)
        s = 40.0 if not math.isfinite(s) else s
        x0 = a[0] + (150 if xspan > 1e-6 else (a[2] - a[0]) * 0.35)
        to = lambda x, y: (x0 + x * s, gy - n.h / 2 - y * s)  # noqa: E731
        sx, sy = to(p.pts[0][1], p.pts[0][2])
        self.put(p.on, sx, sy)
        if p.pts[0][2] > 1e-6 and xspan < 1e-6 and not any(v.at == "launch" for v in self.res.vectors):
            self.dim("dim_h", p.on, _text(self.res, p.on, "h"), sx + 60, (sy + gy) / 2)
        if len(p.pts) > 1:
            self.trail(p.on, p.pts, to)
            self.path_track(p.on, p.pts, to, p.pts[-1][0])
        for v in self.res.vectors:
            if v.at == "launch":
                if v.role == "component":
                    full = next((u for u in self.res.vectors if u.id == "v0"), v)
                    ln = self._len(full) * math.hypot(v.vx, v.vy) / (math.hypot(full.vx, full.vy) or 1.0)
                    self.arrow(v, sx, sy, ln)
                else:
                    self.arrow(v, sx, sy)

    def lanes(self, paths: list[Path]) -> None:
        a = self.area
        lanes = sorted({p.lane for p in paths})
        gap = min(230.0, (a[3] - a[1] - 200) / max(1, len(lanes)))
        xs = [q[1] for p in paths for q in p.pts]
        span = (max(xs) - min(xs)) if xs else 0.0
        bodies = [self.L.nodes[p.on] for p in paths if p.on in self.L.nodes]
        bw = max((b.w for b in bodies), default=100.0)
        room = a[2] - a[0] - bw - 120
        s = room / span if span > 1e-6 else 1.0
        xmin = min(xs) if xs else 0.0
        for p in paths:
            if p.on not in self.L.nodes:
                continue
            n = self.L.nodes[p.on]
            gy = a[3] - 50 - lanes.index(p.lane) * gap
            gid = "kin_ground" if p.lane == lanes[0] else f"kin_ground{p.lane}"
            if gid not in self.L.nodes:
                self.ground(gid, gy)
            to = lambda x, y, gy=gy, n=n: (a[0] + 60 + bw / 2 + (x - xmin) * s, gy - n.h / 2)  # noqa: E731
            sx, sy = to(p.pts[0][1], 0.0)
            back = len(p.pts) > 1 and p.pts[-1][1] < p.pts[0][1]
            self.put(p.on, sx, sy, flip=1 if back else 0)
            if len(p.pts) > 1:
                self.path_track(p.on, p.pts, to, p.pts[-1][0])
            for v in self.res.vectors:
                if v.on == p.on:
                    self.arrow(v, sx + (-1 if back else 1) * 10, sy - n.h / 2 - 34)
        if len(bodies) == 2:
            for i, b in enumerate(sorted(bodies, key=lambda b: b.id), 1):
                b.label, b.label_src = f"{b.label or b.kind} {i}", "auto"

    def rain(self, paths: dict[str, Path]) -> None:
        a = self.area
        rain, man = self.g.of("rain")[0].id, self.g.of("man")[0].id
        tilt = float(self.res.extra.get("tilt") or 0.0)
        gy = a[3] - 40
        tri_w = 300.0
        self.ground("kin_ground", gy, a[0], a[2] - tri_w)
        m = self.L.nodes[man]
        p = paths.get(man)
        walk = (a[2] - tri_w - a[0]) * 0.45
        span = p.pts[-1][1] if p and len(p.pts) > 1 else 0.0
        s = walk / span if span > 1e-6 else 1.0
        x0 = a[0] + 120
        to = lambda x, y: (x0 + x * s, gy - m.h / 2)  # noqa: E731
        self.put(man, x0, gy - m.h / 2, umbrella=round(tilt, 2))
        if p and len(p.pts) > 1:
            self.path_track(man, p.pts, to, p.pts[-1][0])
        r = self.L.nodes[rain]
        r.w, r.h = a[2] - tri_w - a[0] - 40, gy - a[1] - 20
        self.put(rain, a[0] + 20 + r.w / 2, a[1] + 10 + r.h / 2, slant=round(tilt, 2))
        self.tracks.append({"id": rain, "kind": "flow", "speed": 2.0})
        for v in self.res.vectors:
            if v.on == man:
                self.arrow(v, x0 + 30, gy - m.h - 30)
        tx, ty = a[2] - tri_w + 200, a[1] + 60
        vr = next(v for v in self.res.vectors if v.id == "vr")
        vm = next(v for v in self.res.vectors if v.id == "vm")
        rel = next(v for v in self.res.vectors if v.id == "vrel")
        L1 = 260.0 / max(abs(vr.vy), abs(vm.vx), 1e-9) if rel.value.known else 0.0
        if L1:
            ex, ey = self.arrow(vr, tx, ty, abs(vr.vy) * L1)
            mx, _ = self.arrow(vm, ex, ey, abs(vm.vx) * L1)
            self.arrows[-1].update(lx=round((ex + mx) / 2, 1), ly=round(ey + 40, 1), anchor="middle")  # under it:
            self.arrow(rel, tx, ty, math.hypot(rel.vx, rel.vy) * L1)  # its tip is v_rel's tip
        else:
            self.arrow(vr, tx, ty, 200.0)

    def river(self, paths: dict[str, Path]) -> None:
        a = self.area
        boat, river = self.g.of("boat")[0].id, self.g.of("river")[0].id
        p = paths[boat]
        W = float(self.res.extra.get("width") or 100.0)
        drift = max(abs(q[1]) for q in p.pts)
        band = min(420.0, a[3] - a[1] - 300)
        s = min(band / W, (a[2] - a[0] - 420) / drift if drift > 1e-6 else math.inf)
        h = W * s
        rv = self.L.nodes[river]
        rv.w, rv.h = a[2] - a[0], h
        cy = (a[1] + a[3]) / 2 + 40
        self.put(river, (a[0] + a[2]) / 2, cy)
        bottom = cy + h / 2
        b = self.L.nodes[boat]
        x0 = a[0] + 260
        to = lambda x, y: (x0 + x * s, bottom - b.h / 2 - 6 - y * s * (h - b.h - 12) / h)  # noqa: E731
        hv = next(v for v in self.res.vectors if v.id == "vb")
        rot = math.degrees(math.atan2(-hv.vy, hv.vx))
        sx, sy = to(0.0, 0.0)
        self.put(boat, sx, sy, rot)
        if len(p.pts) > 1:
            self.path_track(boat, p.pts, to, p.pts[-1][0])
            self.trail(boat, p.pts, to)
        for v in self.res.vectors:
            if v.on == boat:
                self.arrow(v, sx, sy)
            elif v.on == river:
                self.arrow(v, a[0] + 30, cy + h / 2 - 40)
        if self.g.value(river, "d"):
            self.dim("dim_d", river, _text(self.res, river, "d"), a[0] + 10, cy - h / 2 - 34)  # above the far bank

    def circle(self, p: Path) -> None:
        a = self.area
        cx0, cy0, R, T = p.orbit  # type: ignore[misc]
        cx, cy = (a[0] + a[2]) / 2, (a[1] + a[3]) / 2 + 20
        rad = min(a[2] - a[0], a[3] - a[1]) * 0.33
        self.put(p.on, cx, cy - rad)
        self.L.wires.append({"id": f"trail_{p.on}", "kind": "trail", "pts": [
            [round(cx + rad * math.cos(2 * math.pi * k / 72), 1), round(cy + rad * math.sin(2 * math.pi * k / 72), 1)]
            for k in range(73)]})
        self.L.overlays.append({"kind": "node", "x": round(cx, 1), "y": round(cy, 1)})
        self.L.wires.append({"id": f"radius_{p.on}", "kind": "trail", "pts": [[cx, cy], [cx, cy - rad]], "turn": p.on})
        r_txt = _text(self.res, p.on, "r")
        if r_txt != "r":
            self.dim("dim_r", p.on, r_txt, cx + 16, cy - rad / 2)
        for v in self.res.vectors:
            if v.on == p.on:
                self.arrow(v, cx, cy - rad, min(self._len(v), rad * 0.8) if v.id == "a_c" else None)
        self.tracks.append({"id": p.on, "kind": "orbit", "cx": round(cx, 1), "cy": round(cy, 1), "rx": round(rad, 1),
                            "ry": round(rad, 1), "period": round(min(max(T, 1.5), 8.0), 3), "phase": -math.pi / 2,
                            "dir": 1, "carry": True})


def _text(res: Results, on: str, sym: str) -> str:
    v = next((v for v in res.values if v.on == on and v.sym == sym), None)
    return v.text() if v is not None else sym


_HEAD = {"": "relative motion"}


def _panel(g: Graph, res: Results) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[Value]] = {}
    for v in res.values:
        if v.src in ("constant", "symbol") or not v.known:
            continue
        groups.setdefault(v.on, [])
        if not any(x.sym == v.sym and x.src == v.src for x in groups[v.on]):
            groups[v.on].append(v)
    heads = len(groups) > 1
    cars = [p.id for p in g.of("car")]
    for k in [k for k in groups if k] + ([""] if "" in groups else []):
        if heads:
            p = g.parts.get(k)
            name = _HEAD.get(k) or (p.label or p.kind if p else k)
            if p is not None and p.kind == "car" and len(cars) == 2:
                name = f"{p.label or 'car'} {cars.index(k) + 1}"
            rows.append({"kind": "head", "text": name})
        for v in sorted(groups[k], key=lambda v: v.src != "said"):
            sub = f"said: “{mech._short(v.q)}”" if v.src == "said" else v.eq
            rows.append({"kind": "value", "text": v.text(), "src": v.src, "sub": sub, "on": v.on})
    g_row = next((v for v in res.values if v.src == "constant" and v.sym == "g"), None)
    return {"x": AREA[2] - mech.PANEL_W + 10, "y": AREA[1] + 6, "w": mech.PANEL_W - 10, "rows": rows,
            "foot": f"{g_row.text()} (constant)" if g_row else ""}


__all__ = ["build", "wants", "VIEW"]
