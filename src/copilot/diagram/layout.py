"""Diagram layout (contract §3): Python decides every position. Relations are solved first, each tree in its own frame
with its root at (0, 0); the trees then go in a row (the grid), scaled as one to fill the slide under the title; labels
are placed last, each box clear of every part, wire and other label.

    on          a's bottom on b's surface; on an incline along the slope, turned by θ (contact, no gap)
    in          a liquid fills b's inner box to its level; a rod stands in it, leaning on the rim
    hang_from   a's top anchor at b's end (a spring's end, a pulley's rim — left then right, a support's underside)
    orbit       a on an ellipse round b (ring order = table / said order); a track moves it
    above       a pourer tilted over b, its stream ends on b's liquid
Composites drawn from tables: an atom (nucleus, shells 2-8-8-2, electrons), a bar magnet's field (lines traced from
its two poles, N -> S outside the bar), a circuit loop (series items on the top side, a parallel group as a ladder).
Units: the slide frame is 1600 x 1000, y down.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from copilot.diagram import parts as P
from copilot.diagram.graph import Graph

VIEW = (1600, 1000)
AREA = (60.0, 150.0, 1540.0, 965.0)   # x0, y0, x1, y1: the slide under the title
GAP = 130.0                            # between free trees
MAX_SCALE = 1.6
LABEL_PX = 34
DEFAULT_THETA = 30.0                   # an incline with no said angle (illustrative, badge)
FILL = 0.55                            # a liquid's level in its container's inner box (illustrative)
ROPE = (150.0, 260.0)                  # hanging from a pulley: left, right (two lengths, so the sides read apart)
SECONDS_PER_MERCURY = 8.0
PHASES = (200, 20, 290, 110, 340, 160, 250, 65)  # t = 0 angles: neighbouring rings on opposite sides (labels apart)              # orbit period of Mercury on screen; the others at true ratios


@dataclass
class Node:
    id: str
    kind: str
    w: float
    h: float
    cx: float = 0.0
    cy: float = 0.0
    rot: float = 0.0                    # degrees, clockwise on screen, about the centre
    attr: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    label_src: str = ""
    tree: str = ""
    sub: bool = False                   # drawn by a composite (an atom's electron), not a graph part

    def corners(self) -> list[tuple[float, float]]:
        c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
        out = []
        for dx, dy in ((-self.w / 2, -self.h / 2), (self.w / 2, -self.h / 2), (self.w / 2, self.h / 2),
                       (-self.w / 2, self.h / 2)):
            out.append((self.cx + dx * c - dy * s, self.cy + dx * s + dy * c))
        return out

    def box(self) -> tuple[float, float, float, float]:
        xs, ys = zip(*self.corners())
        return min(xs), min(ys), max(xs), max(ys)

    def at(self, fx: float, fy: float) -> tuple[float, float]:
        """A point given as fractions of the part box, on screen (rotation applied)."""
        dx, dy = (fx - 0.5) * self.w, (fy - 0.5) * self.h
        c, s = math.cos(math.radians(self.rot)), math.sin(math.radians(self.rot))
        return self.cx + dx * c - dy * s, self.cy + dx * s + dy * c

    def anchor(self, name: str) -> tuple[float, float]:
        a = (P.kind(self.kind) or {}).get("anchors", {}).get(name, (0.5, 0.5))
        return self.at(*a)


@dataclass
class Layout:
    nodes: dict[str, Node] = field(default_factory=dict)
    wires: list[dict[str, Any]] = field(default_factory=list)
    overlays: list[dict[str, Any]] = field(default_factory=list)
    tracks: list[dict[str, Any]] = field(default_factory=list)
    labels: list[dict[str, Any]] = field(default_factory=list)
    badges: list[str] = field(default_factory=list)
    scale: float = 1.0


# ---- sizes ----------------------------------------------------------------------------------------------------------
def theta(g: Graph, inc: str) -> tuple[float, bool]:
    gv = g.givens.get("theta")
    if gv and (gv.get("on") in (None, inc)) and 3 <= gv["v"] <= 75:
        return float(gv["v"]), True
    return DEFAULT_THETA, False


def _node(g: Graph, pid: str) -> Node:
    p = g.parts[pid]
    row = P.kind(p.kind)
    n = Node(pid, p.kind, float(row["w"]), float(row["h"]), attr=dict(p.attr), label=p.label, label_src=p.label_src)
    if p.kind == "incline":
        th, said = theta(g, pid)
        base, h = 900.0, 900.0 * math.tan(math.radians(th))
        if h > 480:
            base, h = 480 / math.tan(math.radians(th)), 480.0
        n.w, n.h = base, h
        n.attr.update(theta=th, theta_said=said)
    elif p.kind == "planet":
        row_p = P.planet(p.attr.get("name", "")) or {"r": 1.0}
        d = 26 + 13 * math.sqrt(row_p["r"])
        n.w = n.h = round(d, 1)
        n.attr["tint"] = row_p.get("tint", "rock")
        if row_p.get("rings"):
            n.attr["rings"] = True
    elif p.kind == "atom":
        z, name, sym, said = _element(p.attr)
        sh = P.shells(z)
        r = 100 + (len(sh) - 1) * 78 + 22
        n.w = n.h = 2 * r
        n.attr.update(z=z, element=name, symbol=sym, shells=sh, element_said=said)
    elif p.kind == "switch":
        n.attr.setdefault("state", "closed")
    return n


def _element(attr: dict[str, Any]) -> tuple[int, str, str, bool]:
    el = P.element(str(attr.get("element") or ""))
    if el:
        return el[0], el[1], el[2], True
    z, name, sym = P.element(P.table("illustrative_atom"))  # type: ignore[misc]
    return z, name, sym, False


# ---- relations ------------------------------------------------------------------------------------------------------
def _children(g: Graph, b: str) -> list[str]:
    return sorted(g.children(b), key=lambda a: g.parts[a].seq if a in g.parts else 0)


def _place_tree(g: Graph, L: Layout, root: str) -> None:
    """Every part under `root`, by relation, in the root's frame."""
    todo = [root]
    while todo:
        b = todo.pop(0)
        nb = L.nodes[b]
        kids = [a for a in _children(g, b) if a in L.nodes]
        hang_i, on_i, orbit_i = 0, 0, 0
        orbits = [a for a in kids if g.rels[a][0] == "orbit"]
        on_kids = [a for a in kids if g.rels[a][0] == "on"]
        for a in kids:
            rel = g.rels[a][0]
            na = L.nodes[a]
            na.tree = root
            if rel == "on":
                _on(na, nb, on_i, len(on_kids))
                on_i += 1
            elif rel == "in":
                _in(na, nb, L)
            elif rel in ("hang_from", "attached_to"):
                _hang(na, nb, hang_i, L)
                hang_i += 1
            elif rel == "orbit":
                _orbit(na, nb, orbit_i, len(orbits), L)
                orbit_i += 1
            elif rel == "above":
                _above(na, nb, g, L)
            elif rel == "inside":
                _inside(na, nb)
            else:  # beside: next to it on the same floor line
                na.cx = nb.box()[2] + GAP / 2 + na.w / 2
                na.cy = nb.box()[3] - na.h / 2
            todo.append(a)


def _on(a: Node, b: Node, i: int, n: int) -> None:
    if b.kind == "incline":
        th = math.radians(b.attr["theta"])
        x0, y0, x1, y1 = b.cx - b.w / 2, b.cy - b.h / 2, b.cx + b.w / 2, b.cy + b.h / 2
        top, low = (x0, y0), (x1, y1)               # the slope rises to the left; θ is at the bottom right
        s = 0.5 if n == 1 else 0.3 + 0.4 * i / max(1, n - 1)
        px, py = low[0] + s * (top[0] - low[0]), low[1] + s * (top[1] - low[1])
        nx, ny = math.sin(th), -math.cos(th)        # the slope's outward normal (up and to the right)
        a.cx, a.cy, a.rot = px + nx * a.h / 2, py + ny * a.h / 2, math.degrees(th)
        a.attr["contact"] = [round(px, 2), round(py, 2)]
        return
    sx, sy = b.anchor("top") if b.kind in ("burner",) else (b.cx, b.box()[1])
    span = b.w * 0.6
    x = sx if n == 1 else sx - span / 2 + span * i / (n - 1)
    a.cx, a.cy, a.rot = x, sy - a.h / 2, 0.0


def _in(a: Node, b: Node, L: Layout) -> None:
    ix0, iy0, ix1, iy1 = (P.kind(b.kind) or {}).get("inner", (0.1, 0.1, 0.9, 0.95))
    bx0, by0 = b.cx - b.w / 2, b.cy - b.h / 2
    floor = by0 + iy1 * b.h
    if a.kind == "liquid":
        level = floor - (iy1 - iy0) * b.h * float(a.attr.get("fill", FILL))
        a.cx, a.cy, a.w, a.h, a.rot = b.cx, (level + floor) / 2, (ix1 - ix0) * b.w, floor - level, 0.0
        a.attr.update(container=b.kind, level=round(level, 2), floor=round(floor, 2), cid=b.id)
        b.attr["liquid"] = a.id
        return
    if a.kind == "stirrer":  # leaning on the rim, its tip on the inner floor
        tilt = 14.0
        tip = (b.cx + 0.12 * b.w, floor - 6)
        a.rot = tilt
        a.cx = tip[0] + math.sin(math.radians(tilt)) * a.h / 2
        a.cy = tip[1] - math.cos(math.radians(tilt)) * a.h / 2
        return
    a.cx, a.cy, a.rot = b.cx, floor - a.h / 2, 0.0


def _inside(a: Node, b: Node) -> None:
    """A shape inside a shape (M0, "a square inside C3"): centred on b's centre anchor, scaled to fit (≤ 0.7 of b; a
    square stays clear inside a circle at 0.6; inside a triangle, its incircle)."""
    room = 0.6 if b.kind == "circle" else 0.42 if b.kind == "triangle" else 0.7
    s = min(1.0, room * b.w / a.w, room * b.h / a.h)
    a.w, a.h, a.rot = a.w * s, a.h * s, 0.0
    a.cx, a.cy = b.anchor("centre")


def _hang(a: Node, b: Node, i: int, L: Layout) -> None:
    anchors = (P.kind(b.kind) or {})["anchors"]
    if b.kind == "pulley":
        k = min(1.0, 0.85 * b.w / a.w)  # the two sides must not touch: a hung body no wider than the pulley
        a.w, a.h = a.w * k, a.h * k
        side = "left_end" if i % 2 == 0 else "right_end"
        ex, ey = b.anchor(side)
        top = ey + ROPE[i % 2]
        L.wires.append({"id": f"rope_{a.id}", "kind": "rope", "pts": [[ex, ey], [ex, top]]})
        a.cx, a.cy = ex, top + a.h / 2
        return
    if b.kind == "support":
        ex, ey = b.anchor("end") if i == 0 else b.at(0.5 + (0.3 if i % 2 else -0.3), 1.0)
    else:
        ex, ey = b.anchor("end" if "end" in anchors else "bottom")
    if a.kind == "pulley":  # a pulley's strap from the support to its centre
        a.cx, a.cy = ex, ey + 70 + a.h / 2
        L.wires.append({"id": f"strap_{a.id}", "kind": "rope", "pts": [[ex, ey], [a.cx, a.cy]]})
        return
    top = (P.kind(a.kind) or {})["anchors"].get("top", (0.5, 0))
    a.cx, a.cy, a.rot = ex - (top[0] - 0.5) * a.w, ey + a.h / 2 - top[1] * a.h, 0.0
    a.attr["hung_at"] = [round(ex, 2), round(ey, 2)]


def _orbit(a: Node, b: Node, i: int, n: int, L: Layout) -> None:
    r0 = b.w / 2 + 48
    step = 88.0 if n > 1 else 0.0
    rx = r0 + 20 + i * step
    ry = rx * 0.42
    phase = math.radians(PHASES[i % len(PHASES)])
    a.cx, a.cy = b.cx + rx * math.cos(phase), b.cy + ry * math.sin(phase)
    L.wires.append({"id": f"orbit_{a.id}", "kind": "orbit", "ellipse": [b.cx, b.cy, rx, ry]})
    row = P.planet(a.attr.get("name", "")) if a.kind == "planet" else None
    if row:
        period = SECONDS_PER_MERCURY * row["period_y"] / P.table("planets")[0]["period_y"]
        L.tracks.append({"id": a.id, "kind": "orbit", "cx": b.cx, "cy": b.cy, "rx": rx, "ry": ry,
                         "period": round(period, 3), "phase": round(phase, 4), "dir": -1})


def _above(a: Node, b: Node, g: Graph, L: Layout) -> None:
    """A pourer over the container: tilted, its spout over the mouth, the stream to the liquid (or the floor)."""
    a.rot = 40.0
    sx, sy = b.cx - 0.2 * b.w, b.cy - b.h / 2 - 150
    fx, fy = (P.kind("pourer") or {})["anchors"]["spout"]
    c, s = math.cos(math.radians(a.rot)), math.sin(math.radians(a.rot))
    dx, dy = (fx - 0.5) * a.w, (fy - 0.5) * a.h
    a.cx, a.cy = sx - (dx * c - dy * s), sy - (dx * s + dy * c)
    a.attr["spout"] = [round(sx, 2), round(sy, 2)]
    a.attr["into"] = b.id


def _streams(g: Graph, L: Layout) -> None:
    """After the liquids are placed: each pour's stream from the spout to the liquid surface (else the inner floor)."""
    for p in g.processes:
        if p["verb"] != "pour" or p.get("src") not in L.nodes or p["target"] not in L.nodes:
            continue
        a, b = L.nodes[p["src"]], L.nodes[p["target"]]
        sx, sy = a.attr["spout"]
        liq = L.nodes.get(b.attr.get("liquid", ""))
        iy1 = (P.kind(b.kind) or {}).get("inner", (0, 0, 1, 0.95))[3]
        end = liq.attr["level"] if liq else b.cy - b.h / 2 + iy1 * b.h
        pts = [[sx, sy], [sx + 6, sy + 30], [sx + 8, end]]
        L.wires.append({"id": f"stream_{a.id}", "kind": "stream", "pts": pts, "tint": a.attr.get("tint", "water")})
        L.tracks.append({"id": f"stream_{a.id}", "kind": "pour", "speed": 0.5 if p.get("manner") == "slow" else 1.0})
        if p.get("manner") == "slow":
            a.attr["slow"] = True


# ---- composites -----------------------------------------------------------------------------------------------------
def _atom(n: Node, L: Layout) -> None:
    sh = n.attr["shells"]
    L.nodes[f"{n.id}_nucleus"] = Node(f"{n.id}_nucleus", "nucleus", 90, 90, n.cx, n.cy, attr={
        "symbol": n.attr["symbol"]}, label="nucleus", label_src="table", tree=n.tree, sub=True)
    for k, count in enumerate(sh):
        r = 100 + k * 78
        sid = f"{n.id}_shell{k + 1}"
        L.nodes[sid] = Node(sid, "shell", 2 * r, 2 * r, n.cx, n.cy, label="shell" if k == len(sh) - 1 else "",
                            label_src="table", tree=n.tree, sub=True)
        period = 12.0 + 6.0 * k
        for j in range(count):
            ph = 2 * math.pi * j / count + 0.35 * k
            eid = f"{n.id}_e{k + 1}_{j + 1}"
            L.nodes[eid] = Node(eid, "electron", 26, 26, n.cx + r * math.cos(ph), n.cy + r * math.sin(ph),
                                label="electron" if (k == len(sh) - 1 and j == 0) else "", label_src="table",
                                tree=n.tree, sub=True)
            L.tracks.append({"id": eid, "kind": "orbit", "cx": n.cx, "cy": n.cy, "rx": r, "ry": r,
                             "period": period, "phase": round(ph, 4), "dir": 1})
    if not n.attr["element_said"]:
        L.badges.append(f"Illustrative atom ({n.attr['element']})")


def field_lines(n: Node, k: int = 14) -> list[list[list[float]]]:
    """Field lines of a bar magnet (N on the right), traced from two poles; only the parts outside the bar, N -> S.
    Lines leave N (traced along B); the ones that never reach S are matched by lines traced back from S (against B,
    then reversed), so the picture is symmetric."""
    pole = n.w / 2 - 34
    N, S = (n.cx + pole, n.cy), (n.cx - pole, n.cy)
    x0, y0, x1, y1 = n.cx - 700, n.cy - 330, n.cx + 700, n.cy + 330
    inside = lambda x, y: abs(x - n.cx) <= n.w / 2 + 4 and abs(y - n.cy) <= n.h / 2 + 4  # noqa: E731

    def trace(start: tuple[float, float], sign: float, ang: float, goal: tuple[float, float]) -> tuple[list, bool]:
        x, y = start[0] + 16 * math.cos(ang), start[1] + 16 * math.sin(ang)
        pts: list[list[float]] = []
        for _ in range(2400):
            ex = ey = 0.0
            for (px, py), q in ((N, 1.0), (S, -1.0)):
                dx, dy = x - px, y - py
                r3 = max(1e-6, (dx * dx + dy * dy) ** 1.5)
                ex, ey = ex + q * dx / r3, ey + q * dy / r3
            m = math.hypot(ex, ey)
            if m == 0:
                break
            x, y = x + sign * 5 * ex / m, y + sign * 5 * ey / m
            if not inside(x, y):
                pts.append([round(x, 1), round(y, 1)])
            elif pts:
                return pts, True  # back into the bar at the other pole
            if math.hypot(x - goal[0], y - goal[1]) < 14:
                return pts, True
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                return pts, False  # out of the picture
        return pts, False

    out = []
    for i in range(k):
        ang = 2 * math.pi * (i + 0.5) / k
        pts, closed = trace(N, 1.0, ang, S)
        if len(pts) > 8:
            out.append(pts)
        if not closed:  # its mirror at S: traced back from S, drawn N -> S (arriving)
            back, shut = trace(S, -1.0, math.pi - ang, N)
            if len(back) > 8 and not shut:
                out.append(back[::-1])
    return [p[::3] + ([p[-1]] if (len(p) - 1) % 3 else []) for p in out]


def _field(n: Node, L: Layout) -> None:
    for i, pts in enumerate(field_lines(n)):
        L.wires.append({"id": f"field_{n.id}_{i}", "kind": "field", "pts": pts, "arrow": 0.5})
    L.tracks.append({"id": f"field_{n.id}", "kind": "flow", "speed": 1.0})


def _compass(L: Layout) -> None:
    mags = [n for n in L.nodes.values() if n.kind == "bar_magnet"]
    for c in [n for n in L.nodes.values() if n.kind == "compass"]:
        if not mags:
            continue
        m = mags[0]
        pole = m.w / 2 - 34
        ex = ey = 0.0
        for (px, py), q in (((m.cx + pole, m.cy), 1.0), ((m.cx - pole, m.cy), -1.0)):
            dx, dy = c.cx - px, c.cy - py
            r3 = max(1e-6, (dx * dx + dy * dy) ** 1.5)
            ex, ey = ex + q * dx / r3, ey + q * dy / r3
        c.attr["needle"] = round(math.degrees(math.atan2(ey, ex)), 1)  # the needle's N end points along B


def _circuit(g: Graph, L: Layout) -> Optional[str]:
    """K1: one series loop. Its items go along the top side, a parallel group as a ladder, the cell on the bottom side.
    Returns the loop's root id (a node standing for the whole loop)."""
    loop = next((gid for gid, (m, _) in g.groups.items() if m == "series"), None)
    if loop is None:
        return None
    items = g.groups[loop][1]
    cells = [i for i in items if i in g.parts and g.parts[i].kind == "cell"]
    top = [i for i in items if i not in cells]
    widths = []
    for i in top:
        if i in g.groups:
            widths.append(max(L.nodes[x].w for x in g.groups[i][1] if x in L.nodes) + 120)
        else:
            widths.append(L.nodes[i].w)
    W = max(760.0, sum(widths) + 110 * (len(top) + 1))
    nbr = max([len(g.groups[i][1]) for i in top if i in g.groups] or [1])
    H = max(380.0, 150 + 120 * nbr)
    x0, y0, x1, y1 = -W / 2, -H / 2, W / 2, H / 2
    gap = (W - sum(widths)) / (len(top) + 1)
    x, segs, prev = x0, [], (x0, y0)
    for i, w in zip(top, widths):
        x += gap
        if i in g.groups:
            br = [b for b in g.groups[i][1] if b in L.nodes]
            ra, rb = x, x + w
            ys = [y0 + 120 * k for k in range(len(br))]
            for b, y in zip(br, ys):
                nb = L.nodes[b]
                nb.cx, nb.cy, nb.tree = (ra + rb) / 2, y, loop
                segs += [[[ra, y], [nb.cx - nb.w / 2, y]], [[nb.cx + nb.w / 2, y], [rb, y]]]
            segs += [[[ra, ys[0]], [ra, ys[-1]]], [[rb, ys[0]], [rb, ys[-1]]]]
            for y in ys[1:]:
                L.overlays.append({"kind": "node", "tree": loop, "x": ra, "y": y})
                L.overlays.append({"kind": "node", "tree": loop, "x": rb, "y": y})
            segs.append([list(prev), [ra, y0]])
            prev = (rb, y0)
        else:
            nb = L.nodes[i]
            nb.cx, nb.cy, nb.tree = x + w / 2, y0 - (nb.h * 0.3 if nb.kind == "switch" else 0), loop
            ly = nb.anchor("left")[1]
            segs.append([list(prev), [x, ly]] if abs(ly - prev[1]) < 1 else [list(prev), [x, prev[1]], [x, ly]])
            prev = nb.anchor("right")
        x += w
    if not cells:  # no source said: the parts between two terminals, not a closed loop (no current is implied)
        segs.append([list(prev), [x1, y0]])
        L.overlays += [{"kind": "node", "tree": loop, "x": x0, "y": y0}, {"kind": "node", "tree": loop, "x": x1, "y": y0}]
    else:
        segs.append([list(prev), [x1, y0], [x1, y1]])
    if cells:
        cw = sum(L.nodes[c].w for c in cells) + 40 * (len(cells) - 1)
        cx = -cw / 2
        p2 = (x1, y1)
        for c in reversed(cells):
            nc = L.nodes[c]
            nc.cx, nc.cy, nc.tree = cx + cw - nc.w / 2, y1, loop
            segs.append([list(p2), list(nc.anchor("right"))])
            p2 = nc.anchor("left")
            cw -= nc.w + 40
        segs.append([list(p2), [x0, y1], [x0, y0]])
    for k, s in enumerate(segs):
        L.wires.append({"id": f"wire_{loop}_{k}", "kind": "wire", "pts": [[round(a, 1), round(b, 1)] for a, b in s]})
    L.nodes[loop] = Node(loop, "loop", W, H, 0, 0, tree=loop, sub=True)
    return loop


# ---- the whole diagram ----------------------------------------------------------------------------------------------
def solve(g: Graph, nogo: Optional[list[list[float]]] = None) -> Layout:
    L = Layout()
    for pid in g.parts:
        L.nodes[pid] = _node(g, pid)
    loop = _circuit(g, L)
    in_loop = {n.id for n in L.nodes.values() if n.tree == loop} if loop else set()
    roots = [pid for pid in g.parts if pid not in g.rels and pid not in in_loop]
    if loop:
        roots.insert(0, loop)
    for r in roots:
        L.nodes[r].tree = r
        if r != loop:
            _place_tree(g, L, r)
    for n in list(L.nodes.values()):
        if n.kind == "atom":
            _atom(n, L)
            n.label = ""
    _streams(g, L)
    for what, on in g.shows:
        if what == "field" and on in L.nodes and L.nodes[on].kind == "bar_magnet":
            _field(L.nodes[on], L)
    for n in L.nodes.values():
        if n.kind == "incline":
            _angle(n, L)
    _arrange(L, roots)
    _compass(L)  # on the final positions (each tree has its own frame until it is arranged)
    _focus(g, L)
    place_labels(L, nogo or [])
    if any(n.kind == "planet" for n in L.nodes.values()):
        L.badges.append("Sizes and distances not to scale · periods to scale")
    return L


def _angle(n: Node, L: Layout) -> None:
    th = n.attr["theta"]
    x, y = n.cx + n.w / 2, n.cy + n.h / 2
    L.overlays.append({"kind": "angle", "tree": n.tree, "x": x, "y": y, "r": min(110.0, n.w * 0.16), "a0": 180.0, "a1": 180.0 + th,
                       "text": f"θ = {th:g}°" if n.attr["theta_said"] else "θ",
                       "src": "said" if n.attr["theta_said"] else "symbol"})
    if not n.attr["theta_said"]:
        L.badges.append("Illustrative angle")


def tree_box(L: Layout, root: str) -> tuple[float, float, float, float]:
    xs0, ys0, xs1, ys1 = [], [], [], []
    for n in L.nodes.values():
        if n.tree == root:
            b = n.box()
            if n.kind == "planet" and n.attr.get("rings"):
                b = (n.cx - n.w * 0.95, b[1], n.cx + n.w * 0.95, b[3])
            xs0.append(b[0]), ys0.append(b[1]), xs1.append(b[2]), ys1.append(b[3])
    for w in L.wires:
        if w.get("tree", _wire_tree(L, w)) == root:
            for x, y in _wire_pts(w):
                xs0.append(x), ys0.append(y), xs1.append(x), ys1.append(y)
    return min(xs0), min(ys0), max(xs1), max(ys1)


def _wire_tree(L: Layout, w: dict[str, Any]) -> str:
    owner = w["id"].split("_", 1)[1] if "_" in w["id"] else ""
    if w["kind"] == "field":
        owner = w["id"][len("field_"):].rsplit("_", 1)[0]
    if w["kind"] == "wire":
        owner = w["id"][len("wire_"):].rsplit("_", 1)[0]
    n = L.nodes.get(owner)
    w["tree"] = n.tree if n else ""
    return w["tree"]


def _wire_pts(w: dict[str, Any]) -> list[tuple[float, float]]:
    if "ellipse" in w:
        cx, cy, rx, ry = w["ellipse"]
        return [(cx - rx, cy - ry), (cx + rx, cy + ry)]
    return [(p[0], p[1]) for p in w["pts"]]


def _arrange(L: Layout, roots: list[str]) -> None:
    """The trees in a row (bottoms on one line for apparatus, centres for the rest), scaled as one to fill the slide."""
    boxes = [tree_box(L, r) for r in roots]
    margin = 70.0  # room for the labels round the edge
    widths = [b[2] - b[0] for b in boxes]
    total = sum(widths) + GAP * (len(roots) - 1)
    tall = max(b[3] - b[1] for b in boxes)
    aw, ah = AREA[2] - AREA[0] - 2 * margin, AREA[3] - AREA[1] - 2 * margin
    s = min(MAX_SCALE, aw / max(total, 1.0), ah / max(tall, 1.0))
    bottoms = all((P.kind(L.nodes[r].kind) or {}).get("domain") in ("mech", "lab") for r in roots) and len(roots) > 1
    x = (AREA[0] + AREA[2]) / 2 - s * total / 2
    cy = (AREA[1] + AREA[3]) / 2
    base = cy + s * tall / 2
    shifts = {}
    for r, b, w in zip(roots, boxes, widths):
        dy = (base - s * b[3]) if bottoms else (cy - s * (b[1] + b[3]) / 2)
        shifts[r] = (x - s * b[0], dy)
        x += s * w + s * GAP
    L.scale = s

    def tf(root: str, px: float, py: float) -> tuple[float, float]:
        dx, dy = shifts.get(root, (0.0, 0.0))
        return round(px * s + dx, 2), round(py * s + dy, 2)

    for n in L.nodes.values():
        n.cx, n.cy = tf(n.tree, n.cx, n.cy)
        n.w, n.h = round(n.w * s, 2), round(n.h * s, 2)
        for k in ("contact", "hung_at", "spout"):
            if k in n.attr:
                n.attr[k] = list(tf(n.tree, *n.attr[k]))
        for k in ("level", "floor"):
            if k in n.attr:
                n.attr[k] = tf(n.tree, 0, n.attr[k])[1]
    for w in L.wires:
        t = w.get("tree") or _wire_tree(L, w)
        if "ellipse" in w:
            cx, cy, rx, ry = w["ellipse"]
            w["ellipse"] = [*tf(t, cx, cy), round(rx * s, 2), round(ry * s, 2)]
        else:
            w["pts"] = [list(tf(t, *p)) for p in w["pts"]]
    for tr in L.tracks:
        if "cx" in tr:
            owner = L.nodes.get(tr["id"])
            tr["cx"], tr["cy"] = tf(owner.tree if owner else "", tr["cx"], tr["cy"])
            tr["rx"], tr["ry"] = round(tr["rx"] * s, 2), round(tr["ry"] * s, 2)
    for o in L.overlays:
        o["x"], o["y"] = tf(o.pop("tree", ""), o["x"], o["y"])
        if "r" in o:
            o["r"] = round(o["r"] * s, 2)


def _focus(g: Graph, L: Layout) -> None:
    if g.last in L.nodes:
        L.nodes[g.last].attr["focus"] = True


# ---- labels ---------------------------------------------------------------------------------------------------------
def label_size(text: str) -> tuple[float, float]:
    return 0.56 * LABEL_PX * max(1, len(text)) + 14, LABEL_PX * 1.3


def _hits(b: tuple[float, float, float, float], c: tuple[float, float, float, float], pad: float = 4.0) -> bool:
    return b[0] < c[2] + pad and c[0] < b[2] + pad and b[1] < c[3] + pad and c[1] < b[3] + pad


def obstacles(L: Layout, skip: set[str]) -> list[tuple[float, float, float, float]]:
    out = []
    for n in L.nodes.values():
        if n.id in skip or n.kind in ("loop", "shell", "atom"):
            continue
        out.append(n.box())
    for w in L.wires:
        if w["kind"] in ("wire", "rope", "stream"):
            for (ax, ay), (bx, by) in zip(w["pts"], w["pts"][1:]):
                out.append((min(ax, bx) - 3, min(ay, by) - 3, max(ax, bx) + 3, max(ay, by) + 3))
    return out


def crosses_ring(b: tuple[float, float, float, float], cx: float, cy: float, r: float, pad: float = 4.0) -> bool:
    """A label box over a ring's line (a shell): its nearest and farthest points straddle the radius."""
    nx, ny = min(max(cx, b[0]), b[2]), min(max(cy, b[1]), b[3])
    near = math.hypot(nx - cx, ny - cy)
    far = max(math.hypot(x - cx, y - cy) for x in (b[0], b[2]) for y in (b[1], b[3]))
    return near - pad <= r <= far + pad


def _ancestors(L: Layout, n: Node) -> set[str]:
    out = {n.id}
    if n.kind == "liquid" and n.attr.get("cid"):
        out.add(n.attr["cid"])
    if n.kind == "nucleus":
        out.add(n.id.rsplit("_", 1)[0])
    return out


def place_labels(L: Layout, nogo: list[list[float]]) -> None:
    """Each label at its part's preferred side, else the next free spot on a ring round the part, clear of every part
    box, wire, earlier label, the title and the slide edge; a label far from its part gets a leader line."""
    placed: list[tuple[float, float, float, float]] = [tuple(b) for b in nogo]  # type: ignore[misc]
    order = sorted([n for n in L.nodes.values() if n.label], key=lambda n: (n.sub, n.kind == "planet", n.id))
    for n in order:
        lw, lh = label_size(n.label)
        pref = (P.kind(n.kind) or {}).get("label", "right")
        x0, y0, x1, y1 = n.box()
        cands: list[tuple[float, float]] = []
        if pref == "inside" and n.kind in ("circle", "square", "triangle", "rectangle", "pentagon", "hexagon", "unknown", "liquid"):
            cands.append((n.cx, n.cy + (n.h * 0.12 if n.kind == "triangle" else 0)))
        sides = {"right": (x1 + 14 + lw / 2, n.cy), "left": (x0 - 14 - lw / 2, n.cy), "below": (n.cx, y1 + 12 + lh / 2),
                 "above": (n.cx, y0 - 12 - lh / 2)}
        for k in [pref] + [s for s in ("right", "below", "left", "above") if s != pref]:
            if k in sides:
                cands.append(sides[k])
        for ring in (1, 2, 3, 4):
            r = max(n.w, n.h) / 2 + 30 + ring * 46
            for a in range(0, 360, 30):
                cands.append((n.cx + (r + lw / 2) * math.cos(math.radians(a)), n.cy + r * math.sin(math.radians(a))))
        inner = len(cands) and pref == "inside" and n.kind in ("circle", "square", "triangle", "rectangle", "pentagon", "hexagon", "unknown",
                                                              "liquid")
        obs_in = obstacles(L, _ancestors(L, n))   # inside its own part (and a liquid inside its container)
        obs = obstacles(L, {n.id})
        rings = [r for r in L.nodes.values() if r.kind == "shell"]
        chosen = None
        for k, (cx, cy) in enumerate(cands):
            b = (cx - lw / 2, cy - lh / 2, cx + lw / 2, cy + lh / 2)
            if b[0] < 8 or b[2] > VIEW[0] - 8 or b[1] < 8 or b[3] > VIEW[1] - 8:
                continue
            if any(_hits(b, o, 6) for o in placed):
                continue
            if any(crosses_ring(b, r.cx, r.cy, r.w / 2) for r in rings):
                continue
            if k == 0 and inner:
                if any(_hits(b, o) for o in obs_in):
                    continue
            elif any(_hits(b, o) for o in obs) or _hits(b, n.box(), 2):
                continue
            chosen = (cx, cy, b)
            break
        if chosen is None:
            continue  # no free spot: no label rather than one over a part (logged by the caller's tests)
        cx, cy, b = chosen
        placed.append(b)
        lab = {"id": f"lbl_{n.id}", "for": n.id, "text": n.label, "src": n.label_src or "said",
               "x": round(cx, 1), "y": round(cy, 1), "w": round(lw, 1), "h": round(lh, 1)}
        dist = math.hypot(cx - n.cx, cy - n.cy) - max(n.w, n.h) / 2 - max(lw, lh) / 2
        if dist > 40 or n.kind in ("electron", "nucleus", "shell"):
            ex, ey = _edge_point(n, cx, cy)
            lab["leader"] = [[round(ex, 1), round(ey, 1)], [round(_toward(b, ex, ey)[0], 1), round(_toward(b, ex, ey)[1], 1)]]
        if any(t["id"] == n.id and t["kind"] == "orbit" for t in L.tracks):
            lab["follow"] = n.id  # a moving part carries its label
        L.labels.append(lab)


def _edge_point(n: Node, x: float, y: float) -> tuple[float, float]:
    a = math.atan2(y - n.cy, x - n.cx)
    if n.kind == "shell":
        r = n.w / 2
        return n.cx + r * math.cos(a), n.cy + r * math.sin(a)
    r = min(n.w, n.h) / 2
    return n.cx + r * math.cos(a), n.cy + r * math.sin(a)


def _toward(b: tuple[float, float, float, float], x: float, y: float) -> tuple[float, float]:
    """The point of a label box nearest to (x, y)."""
    return min(max(x, b[0]), b[2]), min(max(y, b[1]), b[3])
