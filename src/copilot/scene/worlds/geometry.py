"""The geometry world (F-015 L1): shapes and constructions in world units (y up), solved by Python.

Sizes come from the props (said / teacher / computed) or a default (drawn, never printed). A construction sets its
shape from the other one ("a circle inscribed in the square": r = side / 2) and the result is known only when what it
rests on is known. Areas and lengths are printed (scene.layout) only for known sizes."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from copilot.scene.spec import GEOMETRY_KINDS, KNOWN, SOLID_KINDS, Entity, Q, SceneSpec
from copilot.scene.validate import UNITS

P = tuple[float, float]
DEFAULT = {"side": 4.0, "width": 6.0, "height": 4.0, "radius": 2.0, "length": 4.0, "sides": 6.0}
ROOT3 = math.sqrt(3)


@dataclass
class G:
    """One entity in world units: a polygon's corners (counter-clockwise from the bottom left), a circle's centre and
    radius, a segment's ends or a point."""
    id: str
    kind: str
    pts: list[P] = field(default_factory=list)
    c: P = (0.0, 0.0)
    r: float = 0.0
    known: bool = False       # its size rests on known numbers only
    placed: bool = False      # positioned by a relation (else laid out in a row)
    sized_by: str = ""        # the relation that set its size ("" = its own props)
    # a solid (oblique projection): pts is its outline; visible and hidden edges as polylines; where each said size
    # is printed; its sizes (s | l w h | r h) for the volume and surface area
    edges: list[list[P]] = field(default_factory=list)
    hidden: list[list[P]] = field(default_factory=list)
    dim_at: dict[str, P] = field(default_factory=dict)
    size: dict[str, float] = field(default_factory=dict)

    def bbox(self) -> tuple[float, float, float, float]:
        if self.kind == "circle":
            return self.c[0] - self.r, self.c[1] - self.r, self.c[0] + self.r, self.c[1] + self.r
        ps = self.pts or [self.c]
        xs, ys = [p[0] for p in ps], [p[1] for p in ps]
        return min(xs), min(ys), max(xs), max(ys)

    def centre(self) -> P:
        if self.kind == "circle" or not self.pts:
            return self.c
        x0, y0, x1, y1 = self.bbox()
        return (x0 + x1) / 2, (y0 + y1) / 2

    def move(self, dx: float, dy: float) -> None:
        self.c = (self.c[0] + dx, self.c[1] + dy)
        self.pts = [(x + dx, y + dy) for x, y in self.pts]
        self.edges = [[(x + dx, y + dy) for x, y in ln] for ln in self.edges]
        self.hidden = [[(x + dx, y + dy) for x, y in ln] for ln in self.hidden]
        self.dim_at = {k: (x + dx, y + dy) for k, (x, y) in self.dim_at.items()}

    def length(self) -> float:
        (x0, y0), (x1, y1) = self.pts[0], self.pts[-1]
        return math.hypot(x1 - x0, y1 - y0)


def _val(e: Entity, key: str, unit_m: float) -> tuple[Optional[float], bool]:
    """A length prop in the scene's base unit, and whether it is known."""
    q = e.props.get(key)
    if q is None:
        return None, False
    if key == "sides" or not q.unit:  # a length said without a unit is in the scene's unit ("radius 2" by "4 cm")
        return q.value, q.source in KNOWN
    return q.value * UNITS["length"].get(q.unit, 1.0) / unit_m, q.source in KNOWN


def base_unit(scene: SceneSpec) -> tuple[str, float]:
    """The unit printed for lengths: the first known length's (cm), "" when none was said with a unit."""
    for e in scene.entities:
        for k, q in e.props.items():
            if k in ("side", "width", "height", "radius", "diameter", "length", "base") and q.source in KNOWN:
                return q.unit, UNITS["length"].get(q.unit, 1.0) or 1.0
    return "", 1.0


def _regular(n: int, side: float, c: P = (0.0, 0.0), rot: float = 0.0) -> list[P]:
    """A regular n-gon with a flat bottom side (rot degrees more, counter-clockwise)."""
    R = side / (2 * math.sin(math.pi / n))
    a0 = -math.pi / 2 - math.pi / n + math.radians(rot)
    return [(c[0] + R * math.cos(a0 + 2 * math.pi * k / n), c[1] + R * math.sin(a0 + 2 * math.pi * k / n))
            for k in range(n)]


def _rect(w: float, h: float, c: P = (0.0, 0.0)) -> list[P]:
    return [(c[0] - w / 2, c[1] - h / 2), (c[0] + w / 2, c[1] - h / 2), (c[0] + w / 2, c[1] + h / 2),
            (c[0] - w / 2, c[1] + h / 2)]


def _own(e: Entity, u: float) -> G:
    """An entity from its own props, at the origin."""
    g = G(e.id, e.kind)
    if e.kind == "square":
        s, k = _val(e, "side", u)
        g.pts, g.known = _rect(s or DEFAULT["side"], s or DEFAULT["side"]), k
    elif e.kind == "rectangle":
        w, kw = _val(e, "width", u)
        if w is None:
            w, kw = _val(e, "length", u)
        h, kh = _val(e, "height", u)
        if h is None:
            h, kh = _val(e, "base", u)
        g.pts, g.known = _rect(w or DEFAULT["width"], h or DEFAULT["height"]), kw and kh
    elif e.kind == "circle":
        r, k = _val(e, "radius", u)
        if r is None:
            d, k = _val(e, "diameter", u)
            r = d / 2 if d is not None else None
        g.r, g.known = r or DEFAULT["radius"], k
    elif e.kind == "triangle":
        b, kb = _val(e, "base", u)
        h, kh = _val(e, "height", u)
        if b is not None and h is not None:  # base and height: isosceles
            g.pts, g.known = [(-b / 2, -h / 3), (b / 2, -h / 3), (0.0, 2 * h / 3)], kb and kh
        else:
            s, k = _val(e, "side", u)
            g.pts, g.known = _regular(3, s or DEFAULT["side"]), k
            cy = sum(p[1] for p in g.pts) / 3
            g.move(0.0, -cy)
    elif e.kind == "polygon":
        n_q = e.props.get("sides")
        n = int(n_q.value) if n_q is not None else int(DEFAULT["sides"])
        s, k = _val(e, "side", u)
        g.pts, g.known = _regular(n, s or 3.0), k
    elif e.kind == "segment":
        L, k = _val(e, "length", u)
        L = L or DEFAULT["length"]
        g.pts, g.known = [(-L / 2, 0.0), (L / 2, 0.0)], k
    elif e.kind == "point":
        g.known = True
    elif e.kind in SOLID_KINDS:
        _solid(g, e, u)
    return g


# ---- solids: a textbook oblique drawing (depth at 45°, half length), hidden edges dashed -----------------------
DEPTH = 0.5 * math.cos(math.pi / 4)   # a depth of d is drawn d * DEPTH right and up
FLAT = 0.3                             # an ellipse seen from the side: its height / width


def _arc(c: P, r: float, a0: float, a1: float, n: int = 24) -> list[P]:
    """Part of the flattened circle (radius r, height FLAT * r) from angle a0 to a1."""
    return [(c[0] + r * math.cos(a0 + (a1 - a0) * i / n), c[1] + FLAT * r * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def _radius_of(e: Entity, u: float) -> tuple[Optional[float], bool]:
    r, k = _val(e, "radius", u)
    if r is None:
        d, k = _val(e, "diameter", u)
        r = d / 2 if d is not None else None
    return r, k


def _solid(g: G, e: Entity, u: float) -> None:
    """A solid's outline, edges and size labels in world units (its base on y = 0)."""
    if e.kind in ("cube", "cuboid"):
        front_width = False
        if e.kind == "cube":
            s, k = _val(e, "side", u)
            if s is None:
                s, k = _val(e, "length", u)
            l = h = d = s or DEFAULT["side"]
            g.size, g.known = {"s": l}, k
        else:
            l, kl = _val(e, "length", u)
            w, kw = _val(e, "width", u)
            h, kh = _val(e, "height", u)
            front_width = l is None
            if front_width:  # "width 4 and height 3" without a length: the width runs across the front
                l, kl, w, kw = w, kw, None, False
            l, d, h = l or 6.0, w or 3.0, h or DEFAULT["height"]
            g.size, g.known = {"l": l, "w": d, "h": h}, kl and kw and kh
        o = (d * DEPTH, d * DEPTH)
        f = [(0.0, 0.0), (l, 0.0), (l, h), (0.0, h)]
        b = [(x + o[0], y + o[1]) for x, y in f]
        g.pts = [f[0], f[1], b[1], b[2], b[3], f[3]]
        g.edges = [f + [f[0]], [f[3], b[3], b[2], b[1], f[1]], [f[2], b[2]]]
        g.hidden = [[f[0], b[0]], [b[0], b[1]], [b[0], b[3]]]
        g.dim_at = {"side": (l / 2, 0.0), "length": (l / 2, 0.0), "height": (l + o[0], h / 2 + o[1]),
                    "width": (l / 2, 0.0) if e.kind == "cuboid" and front_width else (l + o[0] / 2, o[1] / 2)}
        return
    r, kr = _radius_of(e, u)
    r = r or DEFAULT["radius"]
    if e.kind == "sphere":
        circle = [(r * math.cos(2 * math.pi * i / 48), r + r * math.sin(2 * math.pi * i / 48)) for i in range(48)]
        g.pts, g.size, g.known = circle, {"r": r}, kr
        g.edges = [_arc((0.0, r), r, math.pi, 2 * math.pi), [(0.0, r), (r, r)]]
        g.hidden = [_arc((0.0, r), r, 0.0, math.pi)]
        g.dim_at = {"radius": (r / 2, r), "diameter": (r / 2, r)}
        return
    h, kh = _val(e, "height", u)
    h = h or DEFAULT["height"]
    g.size, g.known = {"r": r, "h": h}, kr and kh
    front = _arc((0.0, 0.0), r, math.pi, 2 * math.pi)       # the near half of the base (drawn)
    back = _arc((0.0, 0.0), r, 0.0, math.pi)                # the far half (hidden)
    if e.kind == "cylinder":
        top = _arc((0.0, h), r, 0.0, 2 * math.pi, 48)
        g.pts = front + [(r, h)] + _arc((0.0, h), r, 0.0, math.pi)[1:]
        g.edges = [front, top, [(-r, 0.0), (-r, h)], [(r, 0.0), (r, h)], [(0.0, h), (r, h)]]
        g.hidden = [back]
        g.dim_at = {"radius": (0.0, h - FLAT * r), "diameter": (0.0, h - FLAT * r), "height": (r, h / 2)}
    else:  # cone: the apex over the centre of the base
        g.pts = front + [(0.0, h)]
        g.edges = [front, [(-r, 0.0), (0.0, h), (r, 0.0)]]
        g.hidden = [back, [(0.0, 0.0), (r, 0.0)], [(0.0, 0.0), (0.0, h)]]
        g.dim_at = {"radius": (r / 2, 0.0), "diameter": (r / 2, 0.0), "height": (r / 2, h / 2)}


def volume(g: G) -> Optional[float]:
    s = g.size
    if g.kind == "cube":
        return s["s"] ** 3
    if g.kind == "cuboid":
        return s["l"] * s["w"] * s["h"]
    if g.kind == "cylinder":
        return math.pi * s["r"] ** 2 * s["h"]
    if g.kind == "cone":
        return math.pi * s["r"] ** 2 * s["h"] / 3
    if g.kind == "sphere":
        return 4 / 3 * math.pi * s["r"] ** 3
    return None


def surface(g: G) -> Optional[float]:
    """The total surface area (a cone's and a cylinder's include the base / both ends)."""
    s = g.size
    if g.kind == "cube":
        return 6 * s["s"] ** 2
    if g.kind == "cuboid":
        return 2 * (s["l"] * s["w"] + s["w"] * s["h"] + s["h"] * s["l"])
    if g.kind == "cylinder":
        return 2 * math.pi * s["r"] * (s["r"] + s["h"])
    if g.kind == "cone":
        return math.pi * s["r"] * (s["r"] + math.hypot(s["r"], s["h"]))
    if g.kind == "sphere":
        return 4 * math.pi * s["r"] ** 2
    return None


def _inradius(g: G) -> tuple[P, float]:
    """The largest circle inside a closed shape: (centre, radius)."""
    if g.kind == "circle":
        return g.c, g.r
    ps = g.pts
    if len(ps) == 3:  # a triangle's incircle
        (ax, ay), (bx, by), (cx, cy) = ps
        a, b, c = math.dist(ps[1], ps[2]), math.dist(ps[0], ps[2]), math.dist(ps[0], ps[1])
        s = a + b + c
        centre = ((a * ax + b * bx + c * cx) / s, (a * ay + b * by + c * cy) / s)
        area = abs((bx - ax) * (cy - ay) - (cx - ax) * (by - ay)) / 2
        return centre, 2 * area / s
    c = g.centre()
    n = len(ps)
    if n == 4:  # a square / rectangle: half its shorter side
        w, h = math.dist(ps[0], ps[1]), math.dist(ps[1], ps[2])
        return c, min(w, h) / 2
    side = math.dist(ps[0], ps[1])
    return c, side / (2 * math.tan(math.pi / n))


def _circumradius(g: G) -> tuple[P, float]:
    """The smallest circle through a closed shape's corners: (centre, radius)."""
    if g.kind == "circle":
        return g.c, g.r
    if len(g.pts) == 3:
        (ax, ay), (bx, by), (cx, cy) = g.pts
        d = 2 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
        ux = ((ax ** 2 + ay ** 2) * (by - cy) + (bx ** 2 + by ** 2) * (cy - ay) + (cx ** 2 + cy ** 2) * (ay - by)) / d
        uy = ((ax ** 2 + ay ** 2) * (cx - bx) + (bx ** 2 + by ** 2) * (ax - cx) + (cx ** 2 + cy ** 2) * (bx - ax)) / d
        return (ux, uy), math.dist((ux, uy), g.pts[0])
    c = g.centre()
    return c, max(math.dist(c, p) for p in g.pts)


def _inscribe(a: G, e: Entity, b: G) -> None:
    """a inside b, touching it (an inscribed circle, a square in a circle, ...)."""
    if a.kind == "circle":
        a.c, a.r = _inradius(b)
        return
    centre, R = _inradius(b) if b.kind != "circle" else (b.c, b.r)
    if b.kind == "square" and a.kind == "square":  # the square on the midpoints of the sides: side / √2, turned 45°
        s = math.dist(b.pts[0], b.pts[1])
        a.pts = _regular(4, s / math.sqrt(2), b.centre(), rot=45.0)
        return
    if b.kind == "circle":
        if a.kind == "square":
            a.pts = _rect(R * math.sqrt(2), R * math.sqrt(2), centre)
        elif a.kind == "rectangle":
            w, h = math.dist(a.pts[0], a.pts[1]), math.dist(a.pts[1], a.pts[2])
            k = 2 * R / math.hypot(w, h)
            a.pts = _rect(w * k, h * k, centre)
        elif a.kind in ("triangle", "polygon"):
            n = len(a.pts)
            a.pts = _regular(n, 2 * R * math.sin(math.pi / n), centre)
        return
    # a polygon in a polygon other than square-in-square: inside the incircle (the honest general case)
    n = len(a.pts)
    if a.kind == "square":
        a.pts = _rect(R * math.sqrt(2), R * math.sqrt(2), centre)
    elif a.kind == "rectangle":
        w, h = math.dist(a.pts[0], a.pts[1]), math.dist(a.pts[1], a.pts[2])
        k = 2 * R / math.hypot(w, h)
        a.pts = _rect(w * k, h * k, centre)
    else:
        a.pts = _regular(n, 2 * R * math.sin(math.pi / n), centre)


def _around(a: G, b: G) -> None:
    """a around b, through its corners (a circumscribed circle) or touching it (a square around a circle)."""
    if a.kind == "circle":
        a.c, a.r = _circumradius(b)
        return
    centre, R = _circumradius(b) if b.kind != "circle" else (b.c, b.r)
    if b.kind == "circle":
        if a.kind == "square":
            a.pts = _rect(2 * R, 2 * R, centre)
        elif a.kind in ("triangle", "polygon"):
            n = len(a.pts)
            a.pts = _regular(n, 2 * R * math.tan(math.pi / n), centre)
            c0 = sum(p[0] for p in a.pts) / n, sum(p[1] for p in a.pts) / n
            a.move(centre[0] - c0[0], centre[1] - c0[1])
        else:
            w, h = math.dist(a.pts[0], a.pts[1]), math.dist(a.pts[1], a.pts[2])
            k = 2 * R / min(w, h)
            a.pts = _rect(w * k, h * k, centre)
        return
    x0, y0, x1, y1 = b.bbox()  # around a polygon: the square / rectangle that holds it
    pad = 0.0
    a.pts = _rect(x1 - x0 + pad, y1 - y0 + pad, b.centre()) if a.kind != "square" else _rect(
        max(x1 - x0, y1 - y0), max(x1 - x0, y1 - y0), b.centre())


def _beside(a: G, b: G, kind: str, gap: float) -> None:
    ax0, ay0, ax1, ay1 = a.bbox()
    bx0, by0, bx1, by1 = b.bbox()
    bc, ac = b.centre(), a.centre()
    if kind == "left_of":
        a.move(bx0 - gap - ax1, bc[1] - ac[1])
    elif kind == "right_of":
        a.move(bx1 + gap - ax0, bc[1] - ac[1])
    elif kind == "above":
        a.move(bc[0] - ac[0], by1 + gap - ay0)
    else:
        a.move(bc[0] - ac[0], by0 - gap - ay1)


def _construct(kind: str, a: G, e: Entity, b: G, gap: float) -> None:
    if kind == "inscribed_in":
        _inscribe(a, e, b)
        a.known, a.sized_by = b.known, kind
    elif kind == "around":
        _around(a, b)
        a.known, a.sized_by = b.known and (a.kind == "circle" or b.kind == "circle"), kind
    elif kind == "inside":
        own = any(k in e.props and e.props[k].source != "default" for k in
                  ("side", "width", "height", "radius", "diameter", "base", "length"))
        if not own:  # no size said: half of what holds it
            _, R = _inradius(b) if b.kind != "point" and b.kind != "segment" else (b.c, 1.0)
            ax0, ay0, ax1, ay1 = a.bbox()
            k = R / max(ax1 - ax0, ay1 - ay0, 1e-9)
            c = a.centre()
            a.pts = [(c[0] + (x - c[0]) * k, c[1] + (y - c[1]) * k) for x, y in a.pts]
            a.r *= k
            a.known = False
        bc, ac = b.centre(), a.centre()
        a.move(bc[0] - ac[0], bc[1] - ac[1])
    elif kind == "diagonal_of":
        n = len(b.pts)
        a.pts = [b.pts[0], b.pts[n // 2]]
        a.known, a.sized_by = b.known, kind
    elif kind == "radius_of":
        a.pts = [b.c, (b.c[0] + b.r * math.cos(math.pi / 6), b.c[1] + b.r * math.sin(math.pi / 6))]
        a.known, a.sized_by = b.known, kind
    elif kind == "diameter_of":
        a.pts = [(b.c[0] - b.r, b.c[1]), (b.c[0] + b.r, b.c[1])]
        a.known, a.sized_by = b.known, kind
    elif kind == "tangent_to":  # touching the top of the circle; its length is not a quantity
        a.pts = [(b.c[0] - 1.3 * b.r, b.c[1] + b.r), (b.c[0] + 1.3 * b.r, b.c[1] + b.r)]
        a.known, a.sized_by = False, kind
    elif kind == "bisector_of":  # the perpendicular bisector, as long as the segment
        (x0, y0), (x1, y1) = b.pts[0], b.pts[-1]
        mx, my, L = (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0)
        ux, uy = -(y1 - y0) / max(L, 1e-9), (x1 - x0) / max(L, 1e-9)
        a.pts = [(mx - ux * L / 2, my - uy * L / 2), (mx + ux * L / 2, my + uy * L / 2)]
        a.known, a.sized_by = False, kind
    elif kind == "midpoint_of":
        (x0, y0), (x1, y1) = b.pts[0], b.pts[-1]
        a.c, a.pts = ((x0 + x1) / 2, (y0 + y1) / 2), []
    elif kind == "on":
        if b.kind == "circle":
            a.c = (b.c[0] + b.r * math.cos(math.pi / 4), b.c[1] + b.r * math.sin(math.pi / 4))
        elif b.kind == "segment":
            (x0, y0), (x1, y1) = b.pts[0], b.pts[-1]
            a.c = (x0 + (x1 - x0) / 3, y0 + (y1 - y0) / 3)
        elif b.pts:  # the middle of the top side
            top = sorted(b.pts, key=lambda p: -p[1])[:2]
            a.c = ((top[0][0] + top[1][0]) / 2, (top[0][1] + top[1][1]) / 2)
        else:
            a.c = b.c
    else:
        _beside(a, b, kind, gap)
    a.placed = True


def solve(scene: SceneSpec) -> tuple[dict[str, G], str, float]:
    """Every geometric entity in world units (in the scene's base length unit), and that unit."""
    unit, u = base_unit(scene)
    gs = {e.id: _own(e, u) for e in scene.entities if e.kind in GEOMETRY_KINDS}
    ents = {e.id: e for e in scene.entities}
    rel = {r.a: r for r in scene.relations if r.a in gs and r.b in gs}
    size = max((max(g.bbox()[2] - g.bbox()[0], g.bbox()[3] - g.bbox()[1]) for g in gs.values()), default=4.0)
    gap = (1.0 if any(g.kind in SOLID_KINDS for g in gs.values()) else 0.35) * size  # solids: room for "h = 4 cm"
    # free shapes first, in a row; then each relation once what it rests on is solved (a cycle stays unsolved)
    roots = [i for i in gs if i not in rel]
    x = 0.0
    for i in roots:
        g = gs[i]
        x0, _, x1, _ = g.bbox()
        c = g.centre()
        g.move(x - x0 if x > 0 else -c[0], -c[1])
        x = g.bbox()[2] + gap
    done = set(roots)
    for _ in range(len(rel) + 1):
        for a, r in rel.items():
            if a in done or r.b not in done:
                continue
            _construct(r.kind, gs[a], ents[a], gs[r.b], gap)
            done.add(a)
    return {i: g for i, g in gs.items() if i in done}, unit, u


def area(g: G) -> Optional[float]:
    if g.kind == "circle":
        return math.pi * g.r ** 2
    if len(g.pts) >= 3:
        ps = g.pts
        return abs(sum(ps[i][0] * ps[i - 1][1] - ps[i - 1][0] * ps[i][1] for i in range(len(ps)))) / 2
    return None


def own_q(e: Entity, key: str) -> Optional[Q]:
    q = e.props.get(key)
    return q if q is not None and q.source in KNOWN else None
