"""Solver results -> the patch's `mech` block (F-019 §4): force arrows from the bodies (positions from Python), the
values panel on the right (said values with their quote, computed values with their equation) and the motion tracks
(a body slides by x(t) = ½ a t², a mass on a spring oscillates with its true period). The browser only draws."""
from __future__ import annotations

import math
import textwrap
from typing import Any, Optional

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


def build(g: Graph, L: Layout, res: Optional[Results]) -> dict[str, Any]:
    if res is None:
        return {"forces": [], "panel": None, "notes": [], "tracks": [], "simulated": False}
    forces = _arrows(L, res, PANEL_W if res.values else 0.0)
    tracks = _tracks(L, res)
    notes = [ln for n in res.notes for ln in textwrap.wrap(n, NOTE_CHARS)]
    return {"forces": forces, "panel": _fit(_panel(g, res), notes), "notes": notes, "tracks": tracks,
            "marks": _marks(L, res, forces), "simulated": True}


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
        if f.on not in L.nodes:
            continue
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
    _unclash(out)
    return out


def _on_body(L: Layout, res: Results, on: str, lx: float, ly: float, w: float) -> bool:
    """A label starting at (lx, ly) would cover another body (its box)."""
    for b in {f.on for f in res.forces} - {on}:
        if b in L.nodes:
            x0, y0, x1, y1 = L.nodes[b].box()
            if lx < x1 and lx + w > x0 and ly - 30 < y1 and ly + 8 > y0:
                return True
    return False


def boxes(arrows: list[dict[str, Any]]) -> list[list[float]]:
    """Each arrow's line and label as boxes (the part labels keep clear of them)."""
    out = []
    for a in arrows:
        out.append([min(a["x1"], a["x2"]) - 6, min(a["y1"], a["y2"]) - 6, max(a["x1"], a["x2"]) + 6,
                    max(a["y1"], a["y2"]) + 6])
        w = LABEL_W * len(a["text"])
        x0 = a["lx"] - (w if a["anchor"] == "end" else w / 2 if a["anchor"] == "middle" else 0)
        out.append([x0, a["ly"] - 30, x0 + w, a["ly"] + 8])
    return out


def _unclash(arrows: list[dict[str, Any]]) -> None:
    """Labels of arrows ending near each other move apart (down the slide)."""
    for i, a in enumerate(arrows):
        for b in arrows[:i]:
            if abs(a["lx"] - b["lx"]) < 150 and abs(a["ly"] - b["ly"]) < 40:
                a["ly"] = round(b["ly"] + 42, 1)


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


def _tracks(L: Layout, res: Results) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    moving = [m for m in res.motions if m.state == "slides" and m.a and m.on in L.nodes]
    if moving:
        a_max = max(m.a for m in moving)
        top = REACH
        for m in moving:  # every body stays on the slide (and a hanging one below its pulley) for the whole run
            top = min(top, _space(L, m.on, m.ang) * a_max / m.a)
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


def _ropes(L: Layout, body: str) -> list[dict[str, Any]]:
    return [{"id": w["id"], "end": w["end"]} for w in L.wires if w.get("body") == body]
