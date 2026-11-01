"""Solver results -> the patch's `mech` block (F-019 §4): force arrows from the bodies (positions from Python), the
values panel on the right (said values with their quote, computed values with their equation) and the motion tracks
(a body slides by x(t) = ½ a t², a mass on a spring oscillates with its true period). The browser only draws."""
from __future__ import annotations

import math
import textwrap
from typing import Any, Optional, Sequence

from copilot.diagram.graph import Graph
from copilot.diagram.layout import AREA, VIEW, Layout
from copilot.diagram.solvers.base import Results, Value

PANEL_W = 400.0
ARROW = (80.0, 190.0)       # shortest, longest arrow (the largest known force gets the longest)
REACH = 170.0               # how far the fastest body slides before the loop restarts (units)
HOLD = 0.8                  # s the bodies rest at the end of a run
AMP = 34.0                  # a spring's oscillation on screen (illustrative)
LABEL_W = 15.0              # an arrow label's width per character (units)
QUOTE_CHARS, NOTE_CHARS = 30, 30  # what fits the panel's width at its font sizes
ROLE = {"weight": "weight", "normal": "normal", "friction": "friction", "applied": "applied", "tension": "pull",
        "spring": "component"}
SAID_SYMS = ("m", "F", "μ", "μs", "μk", "θ", "k")
SHOWN_COMPUTED = ("a", "f", "N", "T", "x", "F_s")


def wants(g: Graph) -> bool:
    """A mechanics scene: a body (block, box, mass) or a said quantity. A beaker on a table or a lamp from the ceiling
    is a K1 diagram, not an unsimulated one."""
    return any(p.kind in ("block", "mass") for p in g.parts.values()) or bool(g.qty)


def build(g: Graph, L: Layout, res: Optional[Results], fbd: str = "") -> dict[str, Any]:
    """fbd: "" the scene, "all" every body's free-body diagram, or one body's id (M2)."""
    if res is None:
        return {"forces": [], "panel": None, "notes": [], "tracks": [], "simulated": False}
    forces = _arrows(L, res, PANEL_W if res.values else 0.0)
    tracks = _tracks(L, res, forces)
    notes = [ln for n in res.notes for ln in textwrap.wrap(n, NOTE_CHARS)]
    out = {"forces": forces, "panel": _fit(_panel(g, res), notes), "notes": notes, "tracks": tracks,
           "marks": _marks(L, res, forces), "simulated": True}
    shown = free_bodies(g, res, fbd)
    if shown:
        out["fbd"] = _fbd(g, L, res, shown, PANEL_W if res.values else 0.0)
        out["tracks"] = []  # a free-body diagram stands still
    return out


def free_bodies(g: Graph, res: Optional[Results], fbd: str) -> list[str]:
    """The bodies a free-body view draws: every body with a force ("all"), or the one named."""
    if not fbd or res is None:
        return []
    bodies = list(dict.fromkeys(f.on for f in res.forces if f.on in g.parts and g.parts[f.on].kind in ("block", "mass")))
    return bodies if fbd == "all" else [b for b in bodies if b == fbd]


def _marks(L: Layout, res: Results, arrows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """A said mass written in its body ("2 kg") as a tag over the arrows, turned with the body, at the first spot no
    arrow label covers; it moves with the body (the player's carry group)."""
    labels = boxes(arrows)[1::2]
    out = []
    for v in res.values:
        if v.sym != "m" or v.src != "said" or not v.known or v.on not in L.nodes:
            continue
        if any(o["on"] == v.on for o in out):
            continue
        n = L.nodes[v.on]
        text = v.text().split(" = ", 1)[-1]
        size = max(16.0, min(26.0, n.h * 0.3, n.w * 0.2))
        w, h = 0.58 * size * len(text) + 12, size + 8
        spots = [n.at(0.5, fy) for fy in (0.28, 0.72, 0.5)]
        x, y = next(((x, y) for x, y in spots if not any(x + w / 2 > b[0] and x - w / 2 < b[2] and y + h / 2 > b[1]
                                                          and y - h / 2 < b[3] for b in labels)), spots[0])
        out.append({"on": v.on, "text": text, "x": round(x, 1), "y": round(y, 1), "rot": round(n.rot, 1),
                    "size": round(size, 1), "w": round(w, 1), "h": round(h, 1)})
    return out


# the player's panel steps (web/diagram/player.js `panel`): top, head, a value row without / with its sub-line, a note
# line, the foot; the panel keeps inside the slide (test41: two bodies made 14 rows and the last ran off the bottom)
P_TOP, P_HEAD, P_ROW, P_SUB, P_NOTE, P_FOOT = 44.0, 50.0, 50.0, 74.0, 32.0, 40.0


def _height(pn: dict[str, Any], notes: list[str]) -> float:
    h = P_TOP + sum(P_HEAD if r["kind"] == "head" else P_SUB if r.get("sub") else P_ROW for r in pn["rows"])
    return h + P_NOTE * len(notes) + (P_FOOT if pn["foot"] else 0.0)


def _fit(pn: dict[str, Any], notes: list[str]) -> dict[str, Any]:
    room = VIEW[1] - pn["y"] - 16
    if _height(pn, notes) > room:  # the equations go first (each computed value keeps its number)
        for r in pn["rows"]:
            if r.get("src") == "computed":
                r["sub"] = ""
    pn["scale"] = round(min(1.0, room / _height(pn, notes)), 3)
    return pn


def _short(q: str) -> str:
    return q if len(q) <= QUOTE_CHARS else "…" + q[-(QUOTE_CHARS - 1):].lstrip()


def _origin(L: Layout, on: str, at: str) -> tuple[float, float]:
    n = L.nodes[on]
    if at == "contact":
        c = n.attr.get("contact")
        return (c[0], c[1]) if c else n.at(0.5, 1.0)
    if at == "top":
        return n.at(0.5, 0.0)
    return n.cx, n.cy


def _room(x: float, y: float, ux: float, uy: float, area: tuple[float, float, float, float]) -> float:
    """How long an arrow from (x, y) along (ux, uy) can be with its tip and label inside the area."""
    pad = 40.0
    t = math.inf
    for p, u, lo, hi in ((x, ux, area[0] + pad, area[2] - pad), (y, uy, area[1] + pad, area[3] - pad)):
        if u > 1e-9:
            t = min(t, (hi - p) / u)
        elif u < -1e-9:
            t = min(t, (lo - p) / u)
    return max(50.0, t)


def _arrows(L: Layout, res: Results, panel: float) -> list[dict[str, Any]]:
    area = (AREA[0], AREA[1], AREA[2] - panel, VIEW[1] - 10)
    known = [abs(f.value.v) for f in res.forces if f.value.known and f.value.v]
    top = max(known) if known else 1.0
    out = []
    for f in res.forces:
        if f.on not in L.nodes or f.pair:
            continue  # a pair force (the top block on the bottom one) is drawn in the free-body view only
        x, y = _origin(L, f.on, f.at)
        v = f.value
        if v.known and abs(v.v) < 1e-9:
            continue  # a zero force is not drawn (its value stays in the panel)
        ln = ARROW[0] + (ARROW[1] - ARROW[0]) * abs(v.v) / top if v.known else (ARROW[0] + ARROW[1]) / 2
        if f.kind == "normal" and v.known:
            ln += L.nodes[f.on].h / 2  # the normal starts at the contact: the part inside the body is not the force
        ux, uy = math.cos(math.radians(f.ang)), math.sin(math.radians(f.ang))
        if f.kind == "friction":
            x, y = x + ux * 6, y + uy * 6
        if f.kind in ("weight", "normal") and L.nodes[f.on].rot == 0 and abs(ux) < 1e-6:
            x += -16 if f.kind == "weight" else 16  # on a floor W and N would share one line through the body
            up, down = _stacked(L, res, f.on)
            if f.kind == "normal" and up is not None:  # M4: past the body on top, not through it (nor on its N line)
                me = L.nodes[f.on].box()
                x = min(up.box()[2] + 14, me[2] - 8)
            if f.kind == "weight" and down is not None:  # M4: the top body's W stops at the body it rests on
                ln = max(44.0, min(ln, down.box()[1] - 6 - y))
        ln = min(ln, _room(x, y, ux, uy, area))  # the tip stays on the slide and off the panel
        x2, y2 = x + ux * ln, y + uy * ln
        # a vertical arrow's label beside its tip (up: left, down: right, so W and N / T read apart); a level one's
        # label above its line (a rope or a table top runs along it)
        side = abs(ux) < 0.35
        lx = x2 + (16 if uy > 0 else -16) if side else x2 + ux * 36
        ly = y2 + 10 - uy * 14 if side else y2 + uy * 30 - (14 if abs(uy) < 0.35 else -12)
        anchor = ("start" if uy > 0 else "end") if side else "start" if ux > 0.35 else "end" if ux < -0.35 else "middle"
        if side and anchor == "start" and (lx + LABEL_W * len(v.text()) > area[2] or _on_body(L, res, f.on, lx, ly,
                                                                                         LABEL_W * len(v.text()))):
            lx, anchor = x2 - 16, "end"  # test40: "W = 9.8 N" ran under the panel (or onto the other Atwood block)
        elif side and anchor == "end" and _on_body(L, res, f.on, lx - LABEL_W * len(v.text()), ly,
                                                   LABEL_W * len(v.text())):
            lx, anchor = x2 + 16, "start"
        out.append({"id": f.id, "on": f.on, "kind": f.kind, "role": ROLE[f.kind], "x1": round(x, 1), "y1": round(y, 1),
                    "x2": round(x2, 1), "y2": round(y2, 1), "text": v.text(), "src": v.src,
                    "q": v.q, "eq": v.eq, "said_dir": f.said_dir, "lx": round(lx, 1), "ly": round(ly, 1),
                    "anchor": anchor})
    bodies = [L.nodes[b].box() for b in {f.on for f in res.forces} if b in L.nodes]
    _unclash(out, bodies, area)
    return out


def _stacked(L: Layout, res: Results, on: str) -> tuple[Any, Any]:
    """(the body resting on this one, the body this one rests on), from the drawn boxes (level bodies only)."""
    me = L.nodes[on].box()
    up = down = None
    for b in {f.on for f in res.forces} - {on}:
        n = L.nodes.get(b)
        if n is None or n.rot != 0:
            continue
        x0, y0, x1, y1 = n.box()
        if x0 < me[2] and x1 > me[0]:
            if abs(y1 - me[1]) < 3:
                up = n
            elif abs(y0 - me[3]) < 3:
                down = n
    return up, down


def _on_body(L: Layout, res: Results, on: str, lx: float, ly: float, w: float) -> bool:
    """A label starting at (lx, ly) would cover another body (its box)."""
    for b in {f.on for f in res.forces} - {on}:
        if b in L.nodes:
            x0, y0, x1, y1 = L.nodes[b].box()
            if lx < x1 and lx + w > x0 and ly - 30 < y1 and ly + 8 > y0:
                return True
    return False


def _label_box(a: dict[str, Any]) -> list[float]:
    w = LABEL_W * len(a["text"])
    x0 = a["lx"] - (w if a["anchor"] == "end" else w / 2 if a["anchor"] == "middle" else 0)
    return [x0, a["ly"] - 30, x0 + w, a["ly"] + 8]


def boxes(arrows: list[dict[str, Any]]) -> list[list[float]]:
    """Each arrow's line and label as boxes (the part labels keep clear of them)."""
    out = []
    for a in arrows:
        out.append([min(a["x1"], a["x2"]) - 6, min(a["y1"], a["y2"]) - 6, max(a["x1"], a["x2"]) + 6,
                    max(a["y1"], a["y2"]) + 6])
        out.append(_label_box(a))
    return out


def _hits(b: list[float], others: Any) -> bool:
    return any(b[0] < o[2] and b[2] > o[0] and b[1] < o[3] and b[3] > o[1] for o in others)


def _spots(a: dict[str, Any]) -> list[tuple[float, float, str]]:
    """Where a label may go: its first choice, the other side of the tip, past the tip, then up / down the slide."""
    x2, y2 = a["x2"], a["y2"]
    ln = math.hypot(x2 - a["x1"], y2 - a["y1"]) or 1.0
    ux, uy = (x2 - a["x1"]) / ln, (y2 - a["y1"]) / ln
    flip = {"start": "end", "end": "start", "middle": "middle"}[a["anchor"]]
    fx = 2 * x2 - a["lx"]
    past = (x2 + ux * 46, y2 + uy * 46 + 10, "start" if ux > 0.35 else "end" if ux < -0.35 else "middle")
    return [(a["lx"], a["ly"], a["anchor"]), (fx, a["ly"], flip), past, (a["lx"], a["ly"] - 40, a["anchor"]),
            (a["lx"], a["ly"] + 42, a["anchor"]), (fx, a["ly"] + 42, flip), (a["lx"], a["ly"] + 84, a["anchor"])]


def _unclash(arrows: list[dict[str, Any]], bodies: Any = (),
             area: Optional[tuple[float, float, float, float]] = None) -> None:
    """Each label at the first of its spots clear of the labels before it, the other arrows' lines, the bodies (the
    first choice may touch its own) and inside the area (M2: the stacked blocks' labels piled up)."""
    taken: list[list[float]] = []
    lines = [[min(a["x1"], a["x2"]) - 4, min(a["y1"], a["y2"]) - 4, max(a["x1"], a["x2"]) + 4,
              max(a["y1"], a["y2"]) + 4] for a in arrows]
    for i, a in enumerate(arrows):
        best = None
        for k, (lx, ly, anc) in enumerate(_spots(a)):
            b = _label_box({**a, "lx": lx, "ly": ly, "anchor": anc})
            inside = area is None or (b[0] >= area[0] - 20 and b[2] <= area[2] + 10 and b[1] >= area[1] - 10
                                      and b[3] <= area[3] + 10)
            clear = not _hits(b, taken) and not _hits(b, [ln for j, ln in enumerate(lines) if j != i])
            if inside and clear and (k == 0 or not _hits(b, bodies)):
                best = (lx, ly, anc)
                break
        if best is None:  # nothing clear: below the last label it would cover (the M1 rule)
            lx, ly, anc = a["lx"], a["ly"], a["anchor"]
            while _hits(_label_box({**a, "lx": lx, "ly": ly, "anchor": anc}), taken) and ly < VIEW[1]:
                ly += 42
            best = (lx, ly, anc)
        a["lx"], a["ly"], a["anchor"] = round(best[0], 1), round(best[1], 1), best[2]
        taken.append(_label_box(a))


# the free-body view (M2): each body alone, every force from its centre dot, the pair forces too
FBD_BOX = (190.0, 130.0)


def _fbd(g: Graph, L: Layout, res: Results, shown: list[str], panel: float) -> dict[str, Any]:
    area = (AREA[0], AREA[1] + 50, AREA[2] - panel, VIEW[1] - 20)
    cw = (area[2] - area[0]) / len(shown)
    fs = [f for f in res.forces if f.on in shown]
    known = [abs(f.value.v) for f in fs if f.value.known and f.value.v]
    top = max(known) if known else 1.0
    cy = (area[1] + area[3]) / 2
    bodies, arrows = [], []
    for k, b in enumerate(shown):
        cx = area[0] + cw * (k + 0.5)
        n = L.nodes.get(b)
        rot = n.rot if n is not None else 0.0
        w = min(FBD_BOX[0], cw * 0.24)  # narrow cells: a smaller box, room for the level arrows' labels
        h = min(FBD_BOX[1], w * 0.7)
        name = _name(g, b, res) or (g.parts[b].label or g.parts[b].kind)
        m = next((v for v in res.values if v.on == b and v.sym == "m" and v.known), None)
        bodies.append({"id": b, "kind": g.parts[b].kind, "cx": round(cx, 1), "cy": round(cy, 1), "w": round(w, 1),
                       "h": round(h, 1), "rot": round(rot, 1), "name": name,
                       "mass": "" if m is None or m.text().split(" = ", 1)[-1] in name else m.text().split(" = ", 1)[-1]})
        cell = (cx - cw / 2 + 10, area[1], cx + cw / 2 - 10, area[3])
        wide = (cell[0] - 30, cell[1], cell[2] + 30, cell[3])  # a level arrow may use the room pad
        seen: list[float] = []
        for f in fs:
            if f.on != b or f.value.known and abs(f.value.v) < 1e-9:
                continue
            same = sum(1 for a in seen if abs((a - f.ang + 180) % 360 - 180) < 12)
            seen.append(f.ang)
            ux, uy = math.cos(math.radians(f.ang)), math.sin(math.radians(f.ang))
            off = 26.0 * ((same + 1) // 2) * (1 if same % 2 else -1)  # forces on one line (W and N′ down) sit apart
            x, y = cx - uy * off, cy + ux * off
            v = f.value
            ln = ARROW[0] + (ARROW[1] - ARROW[0]) * abs(v.v) / top if v.known else (ARROW[0] + ARROW[1]) / 2
            edge = abs(ux) * w / 2 + abs(uy) * h / 2
            side = abs(ux) < 0.35
            # well past the box's edge; a level arrow far enough for its label over the shaft outside the box
            ln = max(ln, edge + 50, 0.0 if side else edge + LABEL_W * len(v.text()) + 14)
            ln = min(ln, _room(x, y, ux, uy, cell if side else wide))
            x2, y2 = x + ux * ln, y + uy * ln
            # a vertical arrow's label beside its tip; a level / slanted one's above its shaft, ending at the tip (it
            # stays in the body's cell: a label past the tip ran under the panel)
            lx = x2 + (16 if uy > 0 else -16) if side else x2
            ly = y2 + 10 - uy * 14 if side else y2 - 16 + max(0.0, uy) * 30
            anchor = ("start" if uy > 0 else "end") if side else "end" if ux > 0 else "start"
            arrows.append({"id": "fbd-" + f.id, "on": b, "kind": f.kind, "role": ROLE[f.kind], "x1": round(x, 1),
                           "y1": round(y, 1), "x2": round(x2, 1), "y2": round(y2, 1), "text": v.text(),
                           "src": v.src, "said_dir": f.said_dir, "pair": f.pair, "lx": round(lx, 1),
                           "ly": round(ly, 1), "anchor": anchor})
    rects = [[c["cx"] - c["w"] / 2, c["cy"] - c["h"] / 2, c["cx"] + c["w"] / 2, c["cy"] + c["h"] / 2] for c in bodies]
    _unclash(arrows, rects, area)
    return {"bodies": bodies, "forces": arrows, "name_y": round(area[1] - 6, 1)}


def _name(g: Graph, on: str, res: Results) -> str:
    bodies = [p for p in g.parts.values() if p.kind in ("block", "mass")]
    if len(bodies) <= 1 or not on or on not in g.parts:
        return ""
    from copilot.diagram.solvers.contact import _name as body_name
    return body_name(g, on)[4:]  # "top block"


def _panel(g: Graph, res: Results) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    groups: dict[str, list[Value]] = {}
    for v in res.values:
        if v.src == "constant" or not v.known:
            continue  # a symbol stays on its arrow; the note says what is missing
        if v.src == "said" and v.sym not in SAID_SYMS or v.src == "computed" and v.sym not in SHOWN_COMPUTED:
            continue
        if g.parts.get(v.on) is not None and g.parts[v.on].kind not in ("block", "mass"):
            key = ""
        else:
            key = v.on
        groups.setdefault(key, [])
        if not any(x.sym == v.sym and x.src == v.src for x in groups[key]):
            groups[key].append(v)
    order = [k for k in groups if k] + ([""] if "" in groups else [])
    for k in order:
        head = _name(g, k, res)
        if head:
            rows.append({"kind": "head", "text": head})
        for v in sorted(groups[k], key=lambda v: (v.src != "said", v.src == "symbol")):
            sub = ""
            if v.src == "said":
                sub = f"said: “{_short(v.q)}”" + (" (weight)" if v.note == "weight" else "")
            elif v.src == "computed":
                sub = v.eq
            rows.append({"kind": "value", "text": v.text(), "src": v.src, "sub": sub, "on": v.on})
    g_row = next((v for v in res.values if v.src == "constant" and v.sym == "g"), None)
    return {"x": AREA[2] - PANEL_W + 10, "y": AREA[1] + 6, "w": PANEL_W - 10, "rows": rows,
            "foot": f"{g_row.text()} (constant)" if g_row else ""}


def _tracks(L: Layout, res: Results, forces: Sequence[dict[str, Any]] = ()) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    moving = [m for m in res.motions if m.state == "slides" and m.a and m.on in L.nodes]
    if moving:
        a_max = max(m.a for m in moving)
        top = REACH
        for m in moving:  # every body stays on the slide (and a hanging one below its pulley) for the whole run
            top = min(top, min(_space(L, m.on, m.ang), _carried(L, m.on, m.ang, forces)) * a_max / m.a)
        T = min(4.0, max(1.0, math.sqrt(2 * top / (a_max * 100.0))))  # 100 units / m, kept between 1 s and 4 s
        for m in moving:
            reach = top * m.a / a_max
            out.append({"id": m.on, "kind": "slide", "ux": round(math.cos(math.radians(m.ang)), 4),
                        "uy": round(math.sin(math.radians(m.ang)), 4), "acc": round(2 * reach / T ** 2, 3),
                        "run": round(T, 3), "hold": HOLD, "ropes": _ropes(L, m.on)})
    for m in res.motions:
        if m.state == "oscillates" and m.period and m.on in L.nodes:
            sp = L.nodes.get(m.spring)
            out.append({"id": m.on, "kind": "shm", "period": round(m.period, 4), "amp": AMP, "spring": m.spring,
                        "top": round(sp.box()[1], 1) if sp else None})
    return out


def _space(L: Layout, on: str, ang: float) -> float:
    """How far the body can move along `ang` with its box inside the slide and, hanging, its rope longer than 20."""
    n = L.nodes[on]
    x0, y0, x1, y1 = n.box()
    ux, uy = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    room = _room((x0 + x1) / 2, (y0 + y1) / 2, ux, uy, (AREA[0] + (x1 - x0) / 2 - 40, AREA[1] + (y1 - y0) / 2 - 40,
                                                          AREA[2] - (x1 - x0) / 2 + 40, VIEW[1] - (y1 - y0) / 2 + 30))
    for w in L.wires:
        if w.get("body") == on and w.get("end") == 1 and uy < 0:
            room = min(room, (w["pts"][1][1] - w["pts"][0][1] - 20) / -uy)
    return max(10.0, room)


def _carried(L: Layout, on: str, ang: float, forces: Sequence[dict[str, Any]]) -> float:
    """M4 (sheet: the 6 kg Atwood side ran its W arrow off the slide, the 4 kg side's T label into the ceiling): how
    far a body moving up or down can go with the arrows it carries (tips and labels) between the bottom of what it
    hangs from and the slide's bottom. A level motion is not limited here."""
    uy = math.sin(math.radians(ang))
    if abs(uy) < 0.5:
        return math.inf
    mine = [a for a in forces if a["on"] == on]
    if not mine:
        return math.inf
    if uy > 0:
        low = max(max(a["y2"], a["ly"] + 8) for a in mine)
        return max(10.0, (VIEW[1] - 10 - low) / uy)
    hung = [n.box()[3] for n in L.nodes.values() if n.kind in ("support", "pulley")]
    ceiling = min(hung) + 10 if hung else AREA[1]
    high = min(min(a["y2"], a["ly"] - 30) for a in mine)
    return max(10.0, (high - ceiling) / -uy)


def _ropes(L: Layout, body: str) -> list[dict[str, Any]]:
    return [{"id": w["id"], "end": w["end"]} for w in L.wires if w.get("body") == body]
