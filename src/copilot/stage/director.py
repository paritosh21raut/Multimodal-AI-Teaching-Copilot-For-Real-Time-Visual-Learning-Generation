"""The 2D director (F-017 §5, §7): where things stand and what the camera sees. Positions are the director's, never
the LLM's: an op names WHAT; the stagers in stage.timeline build each group in its own metres, and the director

- lays the groups out left -> right on the ground line (true relative size inside a group; across groups the gaps
  are the director's, and a group too small to read next to the others is enlarged with a "Not to scale" badge);
- frames the shot: the ground line at 75 % of the height, the entities of the current sentence (or all, establish)
  with 6 % margins over the whole period, outside the slide's no-go boxes; a follow shot keeps a mover in view;
- places labels (said words) by a nudge order clear of the figures and of each other;
- dims what was not named lately (not in an active action or law), and staggers entrances about 100 ms.

Boxes are world metres [x0, y0, x1, y1] unless named screen (px, y down).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from copilot.stage import catalog

VW, VH = 1600, 1000
GROUND = 0.75     # the ground line's height on the stage (fraction from the top)
MARGIN = 0.06     # frame margins
FAR = 0.6         # far-row scale (web/stage/player.js)
GAP = 1.2         # metres between groups
MIN_READ = 0.25   # a group shorter than this fraction of the tallest is enlarged (with the badge)
DIM_AFTER = 3     # lines without a mention -> dimmed
TOP_BAND = 0.25   # a no-go box ending above this fraction of the height is a title band (keeps height, not width)
NUDGE = [(0, 0)] + [d for k in range(1, 9) for d in ((0, -k * 16), (k * 16, 0), (-k * 16, 0), (0, k * 16))]


@dataclass
class Frame:
    cx: float
    cy: float
    s: float
    ease_ms: int = 600

    def d(self) -> dict[str, Any]:
        return {"cx": round(self.cx, 4), "cy": round(self.cy, 4), "s": round(self.s, 2), "ease_ms": self.ease_ms}

    def proj(self, p: tuple[float, float], w: float = VW) -> tuple[float, float]:
        return (w / 2 + (p[0] - self.cx) * self.s, VH / 2 - (p[1] - self.cy) * self.s)

    def screen_box(self, b: list[float], w: float = VW) -> list[float]:
        a, c = self.proj((b[0], b[3]), w), self.proj((b[2], b[1]), w)
        return [a[0], a[1], c[0], c[1]]


def overlaps(a: list[float], b: list[float]) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def union(boxes: list[list[float]]) -> list[float]:
    return [min(b[0] for b in boxes), min(b[1] for b in boxes), max(b[2] for b in boxes), max(b[3] for b in boxes)]


# ---------- where an entity is (Python's estimate of what the browser draws) ----------
def _at(samples: list[list[float]], t: float) -> list[float]:
    if t <= samples[0][0]:
        return samples[0][1:]
    for a, b in zip(samples, samples[1:]):
        if t <= b[0]:
            k = (t - a[0]) / ((b[0] - a[0]) or 1)
            return [p + (q - p) * k for p, q in zip(a[1:], b[1:])]
    return samples[-1][1:]


def size_of(e: dict[str, Any]) -> tuple[float, float]:
    x = e.get("xform") or {}
    if x.get("size"):
        return tuple(x["size"])
    d = e["draw"]
    if d.startswith("cast:"):
        h = catalog.cast()[d[5:]]["height_m"]
        return 0.5 * h, h
    if d.startswith("species:"):
        return tuple(catalog.species(d[8:])["size_m"])
    row = catalog.prop(d)
    return tuple(row["size_m"]) if row else (1.0, 1.0)


class Where:
    """World boxes of a patch's entities at time t: paths, sockets (to the parent's socket point, roughly), the far
    row, rotation (the rotated box's bounds)."""

    def __init__(self, patch: dict[str, Any], regions: Optional[dict[str, Any]] = None):
        self.p = patch
        self.ents = {e["id"]: e for e in patch["entities"]}
        self.paths = {t["id"]: t for t in patch["tracks"] if t["kind"] == "path"}
        self.socks: dict[str, list[dict]] = {}
        for t in patch["tracks"]:
            if t["kind"] == "socket":
                self.socks.setdefault(t["id"], []).append(t)
        self.regions = regions or {}

    def origin(self, i: str, t: float, depth: int = 0) -> tuple[float, float, float]:
        e = self.ents[i]
        x = e.get("xform") or {}
        ox, oy, rot = x.get("x", 0.0), x.get("y", 0.0), x.get("rot", 0.0)
        if i in self.paths:
            v = _at(self.paths[i]["samples"], t)
            ox, oy = v[0], v[1]
            rot = v[2] if len(v) > 2 else rot
        sk = [s for s in self.socks.get(i, []) if t >= s.get("t0", 0)]
        if sk and depth < 4:
            s = sk[-1]
            free = s.get("t1") is not None and t > s["t1"] and i in self.paths and self.paths[i]["samples"][0][0] <= t
            if not free and s["parent"] in self.ents:
                tt = min(t, s["t1"]) if s.get("t1") is not None else t
                px, py, prot = self.origin(s["parent"], tt, depth + 1)
                pw, ph = size_of(self.ents[s["parent"]])
                off = s.get("offset") or [0, 0]
                pd = self.ents[s["parent"]]
                anchor = s["socket"]
                ay = {"top": ph, "seat": ph * 0.45, "floor": 0.02 * ph, "hands": 0.62 * ph, "hand_r": 0.6 * ph,
                      "hand_l": 0.6 * ph}.get(anchor, 0.0)
                if pd["draw"] == "swing_seat":
                    ay = -0.985 * ph
                if pd["draw"] == "seesaw":
                    ay = 0.16 * ph
                c, sn = math.cos(math.radians(prot)), math.sin(math.radians(prot))
                lx, ly = off[0], ay + off[1]
                ox, oy, rot = px + lx * c - ly * sn, py + lx * sn + ly * c, prot
                ch = size_of(e)[1]
                ox, oy = ox, oy - {"lap": 0.3 * ch, "centre": 0.5 * ch}.get(s.get("child_socket"), 0.0)
        if x.get("row") == "far":
            oy += self.regions.get("far_y", 0.9)
        return ox, oy, rot

    def box(self, i: str, t: float) -> list[float]:
        e = self.ents[i]
        x = e.get("xform") or {}
        w, h = size_of(e)
        k = (FAR if x.get("row") == "far" else 1.0) * x.get("scale", 1.0)
        w, h = w * k, h * k
        ox, oy, rot = self.origin(i, t)
        if e["draw"] == "swing_seat":
            pts = [(-w / 2, -h), (w / 2, -h), (-w / 2, 0), (w / 2, 0)]
        elif e["draw"] == "rain":
            return [ox - w / 2, oy, ox + w / 2, oy + h]
        else:
            pts = [(-w / 2, 0), (w / 2, 0), (-w / 2, h), (w / 2, h)]
        c, s = math.cos(math.radians(rot)), math.sin(math.radians(rot))
        q = [(ox + a * c - b * s, oy + a * s + b * c) for a, b in pts]
        return [min(p[0] for p in q), min(p[1] for p in q), max(p[0] for p in q), max(p[1] for p in q)]

    def times(self, n: int = 24) -> list[float]:
        T = self.p.get("period") or 0.0
        return [T * i / n for i in range(n + 1)] if T else [0.0]


# ---------- layout ----------
@dataclass
class Group:
    """One interacting group, built by a stager in its own metres (x = 0 near its middle)."""
    ids: list[str]
    x0: float = 0.0
    x1: float = 0.0
    top: float = 2.0
    dx: float = 0.0
    scale: float = 1.0
    shift: Optional[Callable[[float], None]] = None


def layout(groups: list[Group]) -> tuple[list[Group], bool]:
    """Groups left -> right with GAP between them, the first one where its stager put it. A group much shorter
    than the tallest is enlarged to stay readable: returns (groups, not_to_scale)."""
    if not groups:
        return groups, False
    tallest = max(g.top for g in groups)
    nts = False
    for g in groups:
        if len(groups) > 1 and g.top < MIN_READ * tallest:
            g.scale, nts = MIN_READ * tallest / g.top, True
    x = groups[0].x1 * groups[0].scale
    for g in groups[1:]:
        g.dx = x + GAP - g.x0 * g.scale
        x = g.dx + g.x1 * g.scale
    return groups, nts


# ---------- framing ----------
def usable(nogo: list[list[float]], w: float = VW) -> list[float]:
    """The widest screen strip [x0, y0, x1, y1] beside the slide's no-go boxes (text boxes)."""
    x0, x1 = 0.0, w
    for b in nogo or []:
        left, right = b[0], w - b[2]
        if left >= right:
            x1 = min(x1, b[0])
        else:
            x0 = max(x0, b[2])
    return [x0, 0.0, x1, VH]


def fit(boxes: list[list[float]], nogo: Optional[list[list[float]]] = None, w: float = VW, ground: float = GROUND,
        ease_ms: int = 600, top_room: float = 0.0) -> Frame:
    """The camera that shows every box (world) with margins inside the usable strip, the ground (y = 0) at
    `ground` of the height. `top_room` px are kept free at the top (captions)."""
    b = union(boxes)
    # a no-go box in the top band (a slide title) keeps that height free; the others take a side of the width
    band = [n for n in nogo or [] if n[3] <= VH * TOP_BAND]
    top_room = max([top_room] + [n[3] + 10 for n in band])
    ux0, _, ux1, _ = usable([n for n in nogo or [] if n not in band], w)
    mw = (ux1 - ux0) * (1 - 2 * MARGIN)
    gy = VH * ground
    above = gy - VH * MARGIN - top_room
    below = VH * (1 - MARGIN) - gy
    s = mw / max(0.2, b[2] - b[0])
    if b[3] > 0:
        s = min(s, above / b[3])
    if b[1] < 0:
        s = min(s, below / -b[1])
    s = max(8.0, s)
    # screen x of the usable centre -> world centre of the boxes
    cx = (b[0] + b[2]) / 2 - ((ux0 + ux1) / 2 - w / 2) / s
    cy = (gy - VH / 2) / s
    return Frame(cx, cy, s, ease_ms)


def inside(frame: Frame, box: list[float], w: float = VW, slack: float = 2.0) -> bool:
    sb = frame.screen_box(box, w)
    return sb[0] >= -slack and sb[2] <= w + slack and sb[1] >= -slack and sb[3] <= VH + slack


# ---------- labels ----------
def text_box(x: float, y: float, s: str, size: float, anchor: str = "middle") -> list[float]:
    """The overlays.js estimate of a label's screen box at its baseline."""
    wpx = len(s.replace("_", "")) * size * 0.55 + 8
    x0 = x - wpx / 2 if anchor == "middle" else x - wpx if anchor == "end" else x
    return [x0, y - size * 0.85, x0 + wpx, y + size * 0.25]


def place_labels(labels: list[dict[str, Any]], figures: list[list[list[float]]], others: list[list[float]],
                 size: float = 34) -> list[dict[str, Any]]:
    """labels: [{text, at: [[sx, sy] per sample time]}]; figures: per sample time, the screen boxes of everything
    drawn. Each label takes the first nudge offset whose box is clear of the figures and placed labels at every
    sample time. Returns [{text, dx, dy, boxes}] (dx, dy in px; boxes per sample time)."""
    placed: list[list[list[float]]] = []
    out = []
    for lb in labels:
        best = None
        for dx, dy in NUDGE:
            boxes = [text_box(p[0] + dx, p[1] + dy, lb["text"], size) for p in lb["at"]]
            clear = all(not any(overlaps(bx, f) for f in figures[k] if not _same(f, lb.get("own", [None] * len(boxes))[k]))
                        and not any(overlaps(bx, o) for o in others)
                        and not any(overlaps(bx, pl[k]) for pl in placed) for k, bx in enumerate(boxes))
            if clear:
                best = (dx, dy, boxes)
                break
        if best is None:
            dx, dy = NUDGE[-1]
            best = (dx, dy, [text_box(p[0] + dx, p[1] + dy, lb["text"], size) for p in lb["at"]])
        placed.append(best[2])
        out.append({"text": lb["text"], "dx": best[0], "dy": best[1], "boxes": best[2]})
    return out


def _same(a: Optional[list[float]], b: Optional[list[float]]) -> bool:
    return a is not None and b is not None and all(abs(p - q) < 1e-6 for p, q in zip(a, b))


# ---------- dimming / entrances ----------
def dimmed(g: Any, busy: set[str]) -> set[str]:
    """Ids not named in the last DIM_AFTER lines and not in an active action / law."""
    order = [i for i, _ in g.lines]
    recent = set(order[-DIM_AFTER:])
    return {e.id for e in g.visible() if e.line not in recent and e.id not in busy}


def stagger(new_ids: list[str], step_ms: int = 100) -> dict[str, int]:
    return {i: k * step_ms for k, i in enumerate(new_ids)}
