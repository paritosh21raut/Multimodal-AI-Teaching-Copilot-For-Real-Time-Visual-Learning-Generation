"""graph -> `diagram.patch` (contract §7): the layout's parts, wires, labels, overlays, tracks and badges, every position
from Python. Tracks are seamless loops (orbits, the pour stream, the stirrer, the flame, the field's flowing dashes)."""
from __future__ import annotations

from typing import Any, Optional

from copilot.diagram import mech
from copilot.diagram import parts as P
from copilot.diagram.solvers import run
from copilot.diagram.graph import Graph
from copilot.diagram.layout import AREA, VIEW, place_labels, solve


def _tint(g: Graph, pid: str) -> Optional[str]:
    c = P.chemical(str(g.parts[pid].attr.get("chem") or "")) if pid in g.parts else None
    return c["tint"] if c else None


def build(g: Graph, rev: int = 1, nogo: Optional[list[list[float]]] = None) -> dict[str, Any]:
    if not g.parts:
        return {"rev": rev, "view": list(VIEW), "parts": [], "wires": [], "labels": [], "overlays": [], "tracks": [],
                "badges": []}
    res = run(g) if mech.wants(g) else None  # F-019: the domain solver (contact mechanics in M1)
    panel = mech.PANEL_W if res is not None and res.values else 0.0
    if panel:  # labels keep off the values panel
        nogo = list(nogo or []) + [[AREA[2] - panel, AREA[1], VIEW[0], AREA[3]]]
    L = solve(g, nogo, panel)
    M = mech.build(g, L, res) if mech.wants(g) else None
    if M is not None and M["forces"]:  # the part labels again, clear of the force arrows and their labels
        L.labels = []
        place_labels(L, list(nogo or []) + mech.boxes(M["forces"]))
    parts = []
    for n in L.nodes.values():
        if n.kind in ("loop",):
            continue
        a = {k: v for k, v in n.attr.items() if k not in ("label_src",)}
        if n.kind in ("liquid", "pourer"):
            a["tint"] = _tint(g, n.id) or "water"
        if n.kind == "liquid" and a.get("cid") in L.nodes:
            c = L.nodes[a["cid"]]
            a["cbox"] = [round(c.cx, 2), round(c.cy, 2), round(c.w, 2), round(c.h, 2)]
        parts.append({"id": n.id, "kind": n.kind, "cx": round(n.cx, 2), "cy": round(n.cy, 2), "w": round(n.w, 2),
                      "h": round(n.h, 2), "rot": round(n.rot, 3), "attr": a})
    order = {"support": 0, "incline": 1, "floor": 1, "burner": 2, "shell": 2, "sun": 3, "liquid": 4, "stirrer": 5,
             "beaker": 6, "flask": 6, "test_tube": 6}
    parts.sort(key=lambda p: order.get(p["kind"], 7))  # paint order: a liquid under its glass, a rod behind it
    for w in L.wires:
        w.pop("tree", None)
        if w["kind"] == "stream":
            w["tint"] = next((p["attr"].get("tint") for p in parts if f"stream_{p['id']}" == w["id"]), "water")
    procs = [{"verb": p["verb"], "target": p["target"], "manner": p.get("manner")} for p in g.processes]
    tracks = list(L.tracks)
    for p in g.processes:
        if p["verb"] == "stir" and p.get("src") in L.nodes:
            stirred = [n.id for n in L.nodes.values() if n.kind == "liquid" and n.attr.get("cid") == p["target"]]
            tracks.append({"id": p["src"], "kind": "swirl", "period": 1.6, "liquids": stirred})
        if p["verb"] == "heat":
            tracks += [{"id": n.id, "kind": "heat", "period": 0.9} for n in L.nodes.values() if n.kind == "burner"]
    for n in L.nodes.values():
        if n.kind == "burner" and not any(t["id"] == n.id for t in tracks):
            tracks.append({"id": n.id, "kind": "heat", "period": 0.9})  # a lit burner's flame flickers
    givens = {k: {"v": v["v"], "u": v["u"], "src": "said", "q": v["q"]} for k, v in g.givens.items()}
    for (_, sym), v in g.qty.items():  # the said values a K1 `given` does not cover (the solver's panel has them all)
        givens.setdefault(sym, {"v": v["v"], "u": v["u"], "src": "said", "q": v["q"]})
    badges = list(L.badges)
    if M is not None:
        tracks += M.pop("tracks")
        if not M["simulated"]:
            badges.append("not simulated")
    return {"rev": rev, "view": list(VIEW), "scale": round(L.scale, 4), "parts": parts, "wires": L.wires,
            "labels": L.labels, "overlays": L.overlays, "tracks": tracks, "badges": badges, "processes": procs,
            "givens": givens, "focus": g.last if g.last in g.parts else None, "mech": M}
