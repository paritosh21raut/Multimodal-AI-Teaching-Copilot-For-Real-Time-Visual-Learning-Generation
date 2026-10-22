"""Scene layout (F-015 L1): picks the world, runs its engine and fits the result to the 1100 x 740 stage (y down).

Writes the engine output of a SceneSpec: each entity's `geom`, `stage` (axes, ground, lanes), `frames` (motion) and
`derived` (readouts). Every printed number is made here by Python (simulation.base.fmt), from known inputs only."""
from __future__ import annotations

import math
from typing import Any, Optional

from copilot.scene.spec import (
    BODY_KINDS, KNOWN, RELATIVE_KINDS, MAX_FRAME_POINTS, SOLID_KINDS, Axes, Derived, Entity, Frames, Geom, SceneSpec, Stage, Track, World,
)
from copilot.scene.worlds import geometry, motion, plot, relative
from copilot.simulation.base import fmt

W, H = 1100, 740
MARGIN = 70
ROW_H = 52            # one readout row (web/sims/draw.js Readout)
MAX_DERIVED = 4
BODY_R = 30.0         # a body's radius on the stage (px)
LANE_GAP = 120.0       # between the lanes of bodies moving in a straight line (px)
GUTTER = 320.0        # the names' column (at most) when there are more than two lanes (px)
MIN_GAP = 48.0        # lanes closer than this first cost readout rows


def world_of(scene: SceneSpec) -> World:
    """relative: a river or rain, a frame of reference, or two bodies with said directions (two trains); else a body
    moves in the motion world."""
    bodies = [e for e in scene.entities if e.kind in BODY_KINDS]
    if any(e.kind in RELATIVE_KINDS for e in scene.entities) or scene.frame or sum(1 for e in bodies if e.dir) >= 2:
        return "relative"
    if bodies:
        return "motion"
    if any(e.kind == "curve" for e in scene.entities):
        return "plot"
    return "geometry"


def _band(n_derived: int) -> float:
    """Where the picture may start: under the readout card when there is one."""
    return MARGIN + (34 + n_derived * ROW_H + 24 if n_derived else 0)


def _card(derived: list[Derived]) -> tuple[float, float]:
    """The readout card's size on the stage (web/sims/draw.js Readout: its width and height formulas)."""
    if not derived:
        return 0.0, 0.0
    w = max(430.0, 60.0 + max((len(d.label) + len(d.text or "00.0 m/s") + 3) * 18 for d in derived))
    return w, 34.0 + len(derived) * ROW_H


def _named(e: Entity, what: str) -> str:
    return f"{what} of the {e.label.text}" if e.label.source == "said" and e.label.text else what


# ---- geometry ---------------------------------------------------------------------------------------------------
def _geometry(scene: SceneSpec) -> SceneSpec:
    gs, unit, _ = geometry.solve(scene)
    ents = {e.id: e for e in scene.entities}
    derived: list[Derived] = []
    order = [i for i in scene.focus if i in gs] + [e.id for e in reversed(scene.entities) if e.id not in scene.focus]
    sq = f" {unit}²" if unit else ""
    ln = f" {unit}" if unit else ""
    for i in order:
        g, e = gs.get(i), ents[i]
        if g is None or not g.known or len(derived) >= MAX_DERIVED:
            continue
        if g.kind in ("square", "rectangle", "circle", "triangle", "polygon"):
            a = geometry.area(g)
            if a is not None:
                derived.append(Derived(id=f"{i}_area", of=i, label=_named(e, "Area"), text=fmt(a) + sq))
            if g.kind == "circle" and g.sized_by and geometry.own_q(e, "radius") is None:
                derived.append(Derived(id=f"{i}_r", of=i, label=_named(e, "Radius"), text=fmt(g.r) + ln))
        elif g.kind == "segment" and g.sized_by:
            derived.append(Derived(id=f"{i}_len", of=i, label=_named(e, "Length"), text=fmt(g.length()) + ln))
        elif g.kind in SOLID_KINDS:
            v, s = geometry.volume(g), geometry.surface(g)
            if v is not None and s is not None:
                derived.append(Derived(id=f"{i}_vol", of=i, label=_named(e, "Volume"),
                                       text=fmt(v) + (f" {unit}³" if unit else "")))
                derived.append(Derived(id=f"{i}_sa", of=i, label=_named(e, "Surface area"), text=fmt(s) + sq))
    derived = derived[:MAX_DERIVED]
    if not gs:
        return scene.model_copy(update={"derived": derived, "stage": Stage()})
    x0 = min(g.bbox()[0] for g in gs.values())
    y0 = min(g.bbox()[1] for g in gs.values())
    x1 = max(g.bbox()[2] for g in gs.values())
    y1 = max(g.bbox()[3] for g in gs.values())
    bw, bh = max(x1 - x0, 1e-9), max(y1 - y0, 1e-9)
    # the picture goes where it is largest: under the readout card or beside it (labels need ~50 px around)
    cw, ch = _card(derived)
    # a solid's said height is printed to its right: keep room for it inside the stage
    R = W - MARGIN - (130 if any(e.kind in SOLID_KINDS and _said(e, "height") for e in scene.entities) else 0)
    boxes = [(MARGIN, R, MARGIN + 30, H - 60)] if not derived else [
        (MARGIN, R, 30 + ch + 50, H - 60), (34 + cw + 60, R, MARGIN + 30, H - 60)]
    bx0, bx1, by0, by1 = max(boxes, key=lambda b: min((b[1] - b[0]) / bw, (b[3] - b[2]) / bh))
    k = min((bx1 - bx0) / bw, (by1 - by0) / bh)
    ox = bx0 + (bx1 - bx0 - bw * k) / 2 - x0 * k
    oy = by0 + (by1 - by0 - bh * k) / 2 + y1 * k

    def px(p: tuple[float, float]) -> tuple[float, float]:
        return round(ox + p[0] * k, 1), round(oy - p[1] * k, 1)

    out = []
    for e in scene.entities:
        g = gs.get(e.id)
        if g is None:
            out.append(e.model_copy(update={"geom": None}))
            continue
        bx0, by0, bx1, by1 = g.bbox()
        top_c = px(((bx0 + bx1) / 2, by1))
        if g.kind == "circle":
            geom = Geom(shape="circle", c=px(g.c), r=round(g.r * k, 1), label_at=(top_c[0], top_c[1] - 14))
        elif g.kind == "point":
            geom = Geom(shape="dot", c=px(g.c), label_at=(px(g.c)[0] + 14, px(g.c)[1] - 14))
        elif g.kind == "segment":
            a, b = px(g.pts[0]), px(g.pts[-1])
            geom = Geom(shape="seg", pts=[a, b], label_at=((a[0] + b[0]) / 2 + 12, (a[1] + b[1]) / 2 - 12))
        elif g.kind in SOLID_KINDS:
            def path(lines: list[list[tuple[float, float]]]) -> str:
                return " ".join("M" + " L".join("%s,%s" % px(p) for p in ln) for ln in lines)
            geom = Geom(shape="solid", pts=[px(p) for p in g.pts], d=path(g.edges), d2=path(g.hidden),
                        label_at=(top_c[0], top_c[1] - 14))
            geom.dims = _solid_dims(e, g, px)
            out.append(e.model_copy(update={"geom": geom}))
            continue
        else:
            geom = Geom(shape="poly", pts=[px(p) for p in g.pts], label_at=(top_c[0], top_c[1] - 14))
        geom.dims = _dims(e, g, geom) if not g.sized_by else []
        out.append(e.model_copy(update={"geom": geom}))
    return scene.model_copy(update={"entities": out, "derived": derived, "stage": Stage(), "frames": None})


def _said(e: Entity, key: str) -> str:
    q = e.props.get(key)
    return f"{fmt(q.value)} {q.unit}".strip() if q is not None and q.source in ("said", "teacher") else ""


def _solid_dims(e: Entity, g: geometry.G, px: Any) -> list[tuple[float, float, str]]:
    """A solid's said sizes beside the edge they measure ("r = 3 cm" on the radius, "h = 5 cm" by the side)."""
    out: list[tuple[float, float, str]] = []
    up = 44 if e.kind == "cylinder" else -12  # a cylinder's radius under its top rim, the others' over the line
    for key, (dx, dy, fmt_) in {"side": (0, 34, "{}"), "length": (0, 34, "{}"), "width": (50, 26, "{}"),
                                "height": (1, 10, "h = {}"), "radius": (0, up, "r = {}"),
                                "diameter": (0, up, "d = {}")}.items():
        text = _said(e, key)
        if not text or key not in g.dim_at or (key == "diameter" and _said(e, "radius")):
            continue
        x, y = px(g.dim_at[key])
        words = fmt_.format(text)
        if dx == 1:  # the height to the right of the edge it measures: half the words' width (~17 px a letter) + 16
            dx = 16 + 8.5 * len(words)
        out.append((round(x + dx, 1), round(y + dy, 1), words))
    return out


def _dims(e: Entity, g: geometry.G, geom: Geom) -> list[tuple[float, float, str]]:
    """The sizes the teacher said, printed on the shape: a side under its bottom edge, a radius at the centre."""
    out: list[tuple[float, float, str]] = []
    if geom.shape == "poly" and len(geom.pts) >= 3:
        (ax, ay), (bx, by) = geom.pts[0], geom.pts[1]
        bottom = _said(e, "side") or _said(e, "width") or _said(e, "length") or _said(e, "base")
        if bottom:
            out.append((round((ax + bx) / 2, 1), round(max(ay, by) + 34, 1), bottom))
        h = _said(e, "height") if e.kind == "rectangle" else ""
        if h and len(geom.pts) >= 3:
            (cx, cy) = geom.pts[2]
            out.append((round(bx + 16, 1), round((by + cy) / 2 + 10, 1), h))
    elif geom.shape == "circle" and geom.c is not None:
        r = _said(e, "radius")
        d = _said(e, "diameter")
        if r or d:
            out.append((geom.c[0], round(geom.c[1] + 12, 1), f"r = {r}" if r else f"d = {d}"))
    elif geom.shape == "seg" and len(geom.pts) == 2:
        L = _said(e, "length")
        if L:
            (ax, ay), (bx, by) = geom.pts
            out.append((round((ax + bx) / 2, 1), round((ay + by) / 2 + 34, 1), L))
    return out


# ---- plot ---------------------------------------------------------------------------------------------------------
def _plot(scene: SceneSpec) -> SceneSpec:
    curves = [e for e in scene.entities if e.kind == "curve"]
    lo = [e.props["xmin"].value for e in curves if "xmin" in e.props]
    hi = [e.props["xmax"].value for e in curves if "xmax" in e.props]
    x0, x1 = (min(lo) if lo else -5.0), (max(hi) if hi else 5.0)
    if x1 <= x0:
        x0, x1 = -5.0, 5.0
    sampled = {e.id: plot.sample(e.expr, x0, x1) for e in curves}
    y0, y1 = plot.y_range(list(sampled.values()))
    L, R, T, B = 110.0, W - MARGIN, MARGIN + 20, H - MARGIN
    sx, sy = (R - L) / (x1 - x0), (B - T) / (y1 - y0)

    def px(x: float, y: float) -> tuple[float, float]:
        return round(L + (x - x0) * sx, 1), round(B - (y - y0) * sy, 1)

    org = px(min(max(0.0, x0), x1), min(max(0.0, y0), y1))
    xs, ys = plot.nice_step(x1 - x0), plot.nice_step(y1 - y0, 6)
    xticks = [(px(v, 0)[0], fmt(v)) for v in _ticks(x0, x1, xs) if abs(v) > 1e-12]
    yticks = [(px(0, v)[1], fmt(v)) for v in _ticks(y0, y1, ys) if abs(v) > 1e-12]
    axes = Axes(x0=L, x1=R, y0=B, y1=T, origin=org, xticks=xticks, yticks=yticks)
    fns = {e.id: plot.evaluator(e.expr) for e in curves}
    on = {r.a: r.b for r in scene.relations if r.kind == "on"}
    out = []
    for e in scene.entities:
        if e.kind == "curve":
            s = sampled[e.id]
            d, pen = [], False
            for x, y in zip(s.xs, s.ys):
                if y is None or not y0 - (y1 - y0) <= y <= y1 + (y1 - y0):
                    pen = False
                    continue
                p = px(x, min(max(y, y0 - 0.05 * (y1 - y0)), y1 + 0.05 * (y1 - y0)))
                d.append(f"{'L' if pen else 'M'}{p[0]},{p[1]}")
                pen = True
            last = next(((x, y) for x, y in zip(reversed(s.xs), reversed(s.ys)) if y is not None and y0 <= y <= y1),
                        None)
            at = px(*last) if last else (R, T)
            out.append(e.model_copy(update={"geom": Geom(shape="path", d=" ".join(d), label_at=(at[0] - 8, at[1] - 16))}))
        elif e.kind == "point":
            qx, qy = e.props.get("x"), e.props.get("y")
            f = fns.get(on.get(e.id, ""))
            x = qx.value if qx is not None else 1.0
            y = f(x) if f is not None else (qy.value if qy is not None else 0.0)
            if y is None:
                out.append(e.model_copy(update={"geom": None}))
                continue
            c = px(x, min(max(y, y0), y1))
            curve = next((c for c in curves if c.id == on.get(e.id)), None)
            # on a curve: its y rests on the expression, printed only when every number in it was said
            known = qx is not None and qx.source in KNOWN and (
                (f is not None and curve is not None and bool(curve.expr_shown))
                or (f is None and qy is not None and qy.source in KNOWN))
            out.append(e.model_copy(update={"geom": Geom(shape="dot", c=c, label_at=(c[0] + 14, c[1] - 14),
                                                         note=f"({fmt(x)}, {fmt(y)})" if known else "")}))
        else:
            out.append(e.model_copy(update={"geom": None}))
    return scene.model_copy(update={"entities": out, "derived": [], "stage": Stage(axes=axes), "frames": None})


def _ticks(lo: float, hi: float, step: float) -> list[float]:
    k0, k1 = math.ceil(lo / step - 1e-9), math.floor(hi / step + 1e-9)
    return [k * step for k in range(k0, k1 + 1)][:25]


# ---- motion -------------------------------------------------------------------------------------------------------
def _motion(scene: SceneSpec) -> SceneSpec:
    bodies = [e for e in scene.entities if e.kind in BODY_KINDS]
    paths = motion.solve(scene, bodies)
    # bodies with the same said name ("car", "another car") are told apart by their said speed, printed beside the name
    names = [e.label.text.lower() for e in bodies if e.label.source == "said" and e.label.text]
    tag = {e.id: _said(e, "speed") for e in bodies
           if e.label.source == "said" and names.count(e.label.text.lower()) > 1}

    def named(e: Entity, what: str) -> str:
        return _named(e, what) + (f" ({tag[e.id]})" if tag.get(e.id) else "")

    shown = [p for p in paths if p.known and p.kind != "rest" and scene.get(p.id) is not None]
    derived: list[Derived] = []
    for p in shown if len(shown) <= MAX_DERIVED // 2 else shown[-MAX_DERIVED:]:
        e = scene.get(p.id)
        assert e is not None
        accel = p.kind == "move" and any(abs(q[3] - p.pts[0][3]) > 1e-9 for q in p.pts)
        if len(shown) <= MAX_DERIVED // 2 or p.kind != "move" or accel:
            derived.append(Derived(id=f"{p.id}_v", of=p.id, label=named(e, "Speed"), live="v", unit="m/s"))
        if p.kind == "move" and (len(shown) <= MAX_DERIVED // 2 or not accel):
            # many bodies: one row each (a steady speed was said: its distance; a changing one: its speed)
            derived.append(Derived(id=f"{p.id}_x", of=p.id, label=named(e, "Distance"), live="x", unit="m"))
    lanes = sum(1 for p in paths if p.kind in ("move", "rest"))
    ground = H - MARGIN - 20
    # many lanes: fewer readout rows (the oldest go first) before the lanes get closer than MIN_GAP
    while derived and lanes > 1 and (ground - _band(len(derived)) - 2 * BODY_R - 10) / (lanes - 1) < MIN_GAP:
        derived.pop(0)
    top = _band(len(derived))
    xmax = max([max(q[1] for q in p.pts) for p in paths] + [1.0])
    ymax = max([max(q[2] for q in p.pts) for p in paths] + [0.0])
    # lanes fit between the readout card and the ground: closer together (and smaller bodies) when there are many
    gap = LANE_GAP if lanes < 2 else max(24.0, min(LANE_GAP, (ground - top - 2 * BODY_R - 10) / (lanes - 1)))
    r = BODY_R if gap >= LANE_GAP else round(max(10.0, min(BODY_R, gap * 0.4)), 1)
    span_y = ground - top - 40 - max(0, lanes - 1) * gap
    # many lanes: the names stand in a column on the left (as wide as the longest name, ~17 px a letter), not over the
    # lane above; a car reaches 1.8 r behind its centre
    in_lane = {p.id for p in paths if p.kind in ("move", "rest")}
    words = [len(e.label.text) + (len(tag[e.id]) + 1 if tag.get(e.id) else 0) for e in bodies
             if e.id in in_lane and e.label.source == "said"]
    gutter = min(GUTTER, max(words, default=0) * 17.0 + 30) if lanes > 2 else 0.0
    back = 1.8 * r if any(e.kind == "car" for e in bodies) else r
    k = (W - 2 * MARGIN - gutter - back - r) / xmax
    if ymax > 0:
        k = min(k, max(span_y, 60) / ymax)
    x0 = MARGIN + gutter + back
    lane_y = [ground - r - i * gap for i in range(lanes)]
    tracks = []
    for p in paths:
        base = lane_y[p.lane] if p.kind in ("move", "rest") and lane_y else ground - r
        pts = []
        for t, x, y, v in p.pts:
            X, Y = x0 + x * k, base - y * k
            pts.append((round(t, 3), round(X, 1), round(Y, 1), round(-math.degrees(x * k / r) % 360, 1),
                        round(v, 3), round(abs(x - p.pts[0][1]), 3)))
        tracks.append(Track(id=p.id, pts=pts))
    assert sum(len(t.pts) for t in tracks) <= MAX_FRAME_POINTS
    period = max([p.T for p in paths] + [motion.RUN_S if not paths else 0.2])
    out = []
    for e in scene.entities:
        tr = next((t for t in tracks if t.id == e.id), None)
        if tr is None:
            out.append(e.model_copy(update={"geom": None}))
            continue
        _, X, Y, _, _, _ = tr.pts[0]
        out.append(e.model_copy(update={"geom": Geom(shape="body", c=(X, Y), r=r, note=tag.get(e.id, ""),
                                                     label_at=(MARGIN, Y + 9) if gutter and e.id in in_lane
                                                     else (X, Y - r - 16))}))
    trails = [(t.id, " ".join(f"{'L' if i else 'M'}{q[1]},{q[2]}" for i, q in enumerate(t.pts)))
              for t, p in zip(tracks, paths) if p.kind in ("launch", "fall")]
    stage = Stage(ground=(MARGIN, W - MARGIN, ground), lanes=[round(y + gap / 2, 1) for y in lane_y[1:]], trails=trails)
    return scene.model_copy(update={"entities": out, "derived": derived, "stage": stage,
                                    "frames": Frames(period=round(period, 3), hold=1.0, tracks=tracks)})


def solve(scene: SceneSpec) -> SceneSpec:
    """The scene with its engine output recomputed (geom, stage, frames, derived), roles and labels settled."""
    world = world_of(scene)
    scene = scene.model_copy(update={"world": world})
    if world == "motion":
        return _motion(scene)
    if world == "relative":
        return relative.solve(scene, _band)
    if world == "plot":
        return _plot(scene)
    return _geometry(scene)


def title_of(scene: SceneSpec) -> Optional[str]:
    """A title from the teacher's names ("Square and circle"), None when nothing was named."""
    names: list[str] = []
    for e in scene.entities:
        if e.label.source == "said" and e.name and e.name.lower() not in (n.lower() for n in names):
            names.append(e.name)
    if not names:
        return None
    t = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return t[:1].upper() + t[1:]
