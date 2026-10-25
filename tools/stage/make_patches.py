"""The 8 reference scenes as `stage.patch` fixtures (contract §8): tests/fixtures/stage/patches/<name>.json.

    .venv/Scripts/python tools/stage/make_patches.py

HAND-MADE: positions come from the reference samples' closed forms (tools/stage/reference/), with the same numbers;
E2 makes patches from ops. Clip facts (stride speed, release / contact frames, hand and seat heights) come from the
clip table, so a walk plays at its stride speed (feet do not slide) and a throw lets go at the clip's release frame.
Deterministic: the same inputs give the same bytes.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from copilot.stage.motion import Motion, clips, load  # noqa: E402

OUT = ROOT / "tests" / "fixtures" / "stage" / "patches"
VW, VH = 1600, 1000
SOURCE = "hand-made (E1, reference closed forms); E2 makes patches from ops"
G = 9.8


def r(x: float, k: int = 4) -> float:
    return round(x + 0.0, k)


def cast() -> dict:
    return {c["id"]: c for c in json.loads((ROOT / "config" / "stage_cast.json").read_text(encoding="utf-8"))["cast"]}


def ground_frame(x0: float, x1: float, top: float, w: float = VW) -> dict:
    """Ground at 75 % of the height (director rule), x0..x1 across, `top` metres visible above the ground."""
    s = min(w * 0.94 / (x1 - x0), VH * 0.68 / top)
    return {"cx": r((x0 + x1) / 2), "cy": r((VH * 0.75 - VH / 2) / s), "s": r(s, 2), "ease_ms": 0}


def view(s: float, cx: float, gy: float) -> dict:
    """The reference's view(s, cx, gy): ground at screen y gy."""
    return {"cx": r(cx), "cy": r((gy - VH / 2) / s), "s": s, "ease_ms": 0}


def caption(text: str) -> dict:
    return {"kind": "words", "screen": [48, 66], "text": f"“{text}”", "size": 30, "color": "#5d6672", "weight": 400}


def steps(t0: float, t1: float, dt: float = 1 / 24):
    n = max(1, math.ceil((t1 - t0) / dt - 1e-9))
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


class Scenes:
    def __init__(self):
        self.m = Motion(load())
        self.c = clips()
        self.cast = cast()

    def h(self, who: str) -> float:
        return self.cast[who]["height_m"]

    def stride(self, clip: str, who: str) -> float:
        return self.c[clip]["stride_mps"] * self.h(who)

    def whole(self, clip: str, period: float, rate: float = 1.0) -> float:
        """The period rounded to a whole number of clip cycles, so a looping scene restarts in step."""
        cyc = self.c[clip]["dur"] / rate
        return max(1, round(period / cyc)) * cyc

    def t_of(self, clip: str, frame: int) -> float:
        return self.m.frame_time(clip, frame)

    def palm(self, clip: str, t: float, side: str, x: float, who: str, d: int = 1, loop: bool | None = None):
        loop = self.c[clip]["loop"] if loop is None else loop
        q = self.m.palm(self.m.sample(clip, t, loop), side)
        return x + d * q[0] * self.h(who), q[1] * self.h(who)

    def lap(self, fr, who: str, mirror: bool = False):
        """The socket `lap` in the figure's frame (metres): the thighs' underside halfway from hip to knee; the thigh
        half-width as web/stage/people.js draws it (0.044 x limb scale x height)."""
        j, h, c = self.m.ji, self.h(who), self.cast[who]
        side = "l" if fr[j["thigh_l"]][1] < fr[j["thigh_r"]][1] else "r"
        hip, knee = fr[j["thigh_" + side]], fr[j["calf_" + side]]
        lw = 1.22 * c.get("build", 1) * (0.9 if c["child"] else 1)
        return (-1 if mirror else 1) * (hip[0] + knee[0]) / 2 * h, min(hip[1], knee[1]) * h - 0.044 * lw * h

    def reach(self, clip: str, who: str, y: float, side: str = "r", mirror: bool = False, rel=None, frac: float = 0.95) -> float:
        """The furthest forward x (metres, the figure facing +x) a hand reaches at height y in every frame of the clip,
        measured from rel(frame) (default the origin): an IK target there is always reachable (the hand lands on it)."""
        h, j = self.h(who), self.m.ji
        best = math.inf
        for fr in self.m.clips[clip]["frames"]:
            ox, oy = rel(fr) if rel else (0.0, 0.0)
            sh, el, pm = fr[j["upperarm_" + side]], fr[j["lowerarm_" + side]], self.m.palm(fr, side)
            arm = (math.dist(sh[:2], el[:2]) + math.dist(el[:2], pm)) * h * frac
            px, py = (-1 if mirror else 1) * sh[0] * h - ox, sh[1] * h - oy
            if abs(y - py) >= arm:
                raise ValueError(f"{who} cannot reach height {y} in {clip}")
            best = min(best, px + math.sqrt(arm * arm - (y - py) ** 2))
        return best

    # ---------- 1 push ----------
    def push(self):
        who, clip, h = "man", "Push_Loop", self.h("man")
        v, span, w = self.stride(clip, who), 2.6, 0.95
        box_h = min(1.4, self.c[clip]["hands_h"]["max"] * h + 0.14)
        period = self.whole(clip, span / v)
        span = v * period
        bx0 = -1.2  # the box's near face
        gap = self.c[clip]["reach_x"] * h - 0.03  # person origin -> near face
        tracks = [
            {"id": "box", "kind": "path", "samples": [[0, r(bx0 + w / 2), 0], [r(period), r(bx0 + span + w / 2), 0]]},
            {"id": "man", "kind": "path", "samples": [[0, r(bx0 - gap), 0], [r(period), r(bx0 + span - gap), 0]]},
            {"id": "man", "kind": "clip", "clip": clip, "rate": 1, "loop": True, "lock": True, "t0": 0},
        ]
        for hand in ("r", "l"):
            tracks.append({"id": "man", "kind": "ik", "hand": hand, "pad": True,
                           "target": {"entity": "box", "anchor": "face_l", "dy": r(self.c[clip]["hands_h"][hand] * h - box_h / 2)}})
        return {
            "caption": "A man pushes a heavy box across a rough floor.", "backdrop": {"id": "room"}, "period": r(period),
            "entities": [{"id": "man", "draw": "cast:man"}, {"id": "box", "draw": "crate", "xform": {"size": [w, r(box_h)]}}],
            "tracks": tracks,
            "overlays": [
                {"kind": "arrow", "at": {"entity": "box", "anchor": "face_l", "dx": 0.03}, "vec": [150, 0], "role": "applied", "label": "F"},
                {"kind": "arrow", "at": {"entity": "box", "anchor": "bottom", "dx": 0.12, "dy": 0.04}, "vec": [-125, 0], "role": "friction", "label": "f"},
                {"kind": "arrow", "at": {"entity": "box", "anchor": "top", "dx": -0.2, "dy": 0.16}, "vec": [150, 0], "role": "velocity", "label": "v"},
            ],
            "frame": view(250, 0.2, 820), "keyframes": [r(period * 0.15), r(period * 0.5), r(period * 0.85)],
        }

    # ---------- 2 throw ----------
    def throw(self):
        who, clip, mx = "man", "OverhandThrow", -3.9
        rel = self.c[clip]["events"]["release"]
        tr = self.t_of(clip, rel)
        hx, hy = self.palm(clip, tr, "r", mx, who, loop=False)
        v0, br = (4.6, 4.4), 0.11
        tf = (v0[1] + math.sqrt(v0[1] ** 2 + 2 * G * (hy - br))) / G
        period = tr + tf + 1.2
        fly = steps(0, tf, 0.03)
        path = [[r(tr + u), r(hx + v0[0] * u), r(hy - br + v0[1] * u - 0.5 * G * u * u)] for u in fly]  # the ball's origin: bottom centre
        vel = [[r(tr + u), r(v0[0] * 24, 2), r((v0[1] - G * u) * 24, 2)] for u in fly]
        return {
            "caption": "He throws a ball; it flies in a curve and falls.", "backdrop": {"id": "outdoor"}, "period": r(period),
            "entities": [{"id": "man", "draw": "cast:man", "xform": {"x": mx}}, {"id": "ball", "draw": "ball"}],
            "tracks": [
                {"id": "man", "kind": "clip", "clip": clip, "rate": 1, "loop": False, "t0": 0, "events": [{"t": r(tr), "name": "release"}]},
                {"id": "ball", "kind": "socket", "parent": "man", "socket": "hand_r", "child_socket": "centre", "t0": 0, "t1": r(tr)},
                {"id": "ball", "kind": "path", "samples": path, "events": [{"t": r(tr), "name": "release"}]},
            ],
            "overlays": [
                {"kind": "path", "of": "ball", "upto": True, "every": 2, "role": "path", "t0": r(tr)},
                {"kind": "arrow", "at": {"entity": "ball", "anchor": "centre"}, "samples": vel, "role": "velocity", "label": "v", "t0": r(tr), "t1": r(tr + tf)},
                {"kind": "arrow", "at": {"entity": "ball", "anchor": "centre"}, "dy": -20, "vec": [0, -100], "role": "weight", "label": "mg", "lx": 12, "ly": 10, "t0": r(tr), "t1": r(tr + tf)},
            ],
            "badges": ["Illustrative"], "frame": view(160, 0.3, 860),
            "keyframes": [r(tr * 0.5), r(tr + tf * 0.45), r(tr + tf * 0.95)],
        }

    # ---------- 3 carry onto a table ----------
    def carry(self):
        who, walk, put, h = "woman", "Walk_Carry_Loop", "PickUp_Table", self.h("woman")
        v, x0, stop = self.stride(walk, who), -2.6, 0.2
        t_walk = (stop - x0) / v
        tc = self.t_of(put, self.c[put]["events"]["contact"])
        t_let = t_walk + tc
        bw, bh, off = 0.5, 0.4, (0.1, 0.02)
        pr, pl = self.palm(put, tc, "r", stop, who, loop=False), self.palm(put, tc, "l", stop, who, loop=False)
        bxm, bym = (pr[0] + pl[0]) / 2 + off[0], (pr[1] + pl[1]) / 2 + off[1]
        top = bym - bh / 2  # the table top is where the clip's hands put the box down
        tx0 = bxm - 0.35
        period = t_let + 2.2
        return {
            "caption": "She carries a box to the table and puts it down.", "backdrop": {"id": "room"}, "period": r(period),
            "entities": [{"id": "table", "draw": "table", "xform": {"x": r(tx0 + 0.75), "size": [1.5, r(top)]}},
                         {"id": "woman", "draw": "cast:woman"}, {"id": "box", "draw": "crate", "xform": {"size": [bw, bh]}}],
            "tracks": [
                {"id": "woman", "kind": "path", "samples": [[0, x0, 0], [r(t_walk), stop, 0], [r(period), stop, 0]]},
                {"id": "woman", "kind": "clip", "clip": walk, "rate": 1, "loop": True, "lock": True, "t0": 0},
                {"id": "woman", "kind": "clip", "clip": put, "rate": 1, "loop": False, "t0": r(t_walk), "blend": 0.25,
                 "events": [{"t": r(t_let), "name": "contact"}]},
                {"id": "woman", "kind": "clip", "clip": "Idle_Loop", "rate": 1, "loop": True, "t0": r(t_let), "blend": 0.5},
                {"id": "box", "kind": "socket", "parent": "woman", "socket": "hands", "child_socket": "centre", "offset": list(off), "t0": 0, "t1": r(t_let)},
            ],
            "overlays": [{"kind": "arrow", "at": {"entity": "woman", "anchor": "head_top", "dx": -0.1, "dy": 0.22}, "vec": [150, 0],
                          "role": "velocity", "label": "v", "t1": r(t_walk)}],
            "frame": view(250, 0.3, 830), "keyframes": [r(t_walk * 0.4), r(t_walk + tc * 0.5), r(t_let + 1.0)],
        }

    # ---------- 4 tug of war ----------
    def tug(self):
        # the rope drifts left at a steady speed; the winning (left) team steps back with it, feet locked; the losing
        # team digs in (the same clip, unlocked) and is dragged: its feet skid, as a losing team's do
        ry, rate = 1.0, 0.35
        team = [("man", -1.0), ("man3", -1.9), ("woman3", -2.8), ("man2", 1.0), ("woman", 1.9), ("woman2", 2.8)]
        period = self.whole("Push_Loop", 9.0, rate)
        v = {w: self.stride("Push_Loop", w) * rate for w, _ in team}
        vr = min(v[w] for w, off in team if off < 0)  # the rope (and the left team) at the slowest winner's step
        ts = steps(0, period, 1 / 12)
        c = [(t, -vr * t) for t in ts]
        ents = [{"id": "rope", "draw": "rope", "xform": {"y": r(ry - 0.025), "size": [7.2, 0.05]}, "state": {"marker": True}}]
        tracks = [{"id": "rope", "kind": "path", "samples": [[r(t), r(x), r(ry - 0.025)] for t, x in c]}]
        for i, (who, off) in enumerate(team):
            d = 1 if off < 0 else -1
            pid = f"p{i}"
            ents.append({"id": pid, "draw": f"cast:{who}", "xform": {"dir": d}})
            tracks.append({"id": pid, "kind": "path", "samples": [[r(t), r(x + off), 0] for t, x in c]})
            win = off < 0
            tracks.append({"id": pid, "kind": "clip", "clip": "Push_Loop", "mirror": True, "loop": True, "t0": 0,
                           "rate": r(rate * vr / v[who] if win else rate), "lock": win, "t_offset": r(i * 0.6)})
            # the grips: as far forward as the leaning-back (mirrored push) arms reach in every frame (the reference's
            # fixed 0.62 / 0.48 m were out of reach, so its hands fell short of the rope)
            for hand, k in (("r", self.reach("Push_Loop", who, ry, "r", True)), ("l", self.reach("Push_Loop", who, ry, "l", True, frac=0.85))):
                tracks.append({"id": pid, "kind": "ik", "hand": hand, "target": {"entity": "rope", "anchor": "centre", "dx": r(off + d * k)}})
        return {
            "caption": "Tug of war: the left team pulls harder, so the rope moves left.", "backdrop": {"id": "outdoor"}, "period": period,
            "entities": ents, "tracks": tracks,
            "overlays": [
                {"kind": "line", "a": [0, 0.02], "b": [0, -0.4], "color": "#ffffff", "opacity": "1", "w": 5},
                {"kind": "arrow", "at": {"entity": "rope", "anchor": "centre", "dy": 1.4}, "dx": -20, "vec": [-240, 0], "role": "applied", "label": "F_L", "lx": -60, "ly": -14},
                {"kind": "arrow", "at": {"entity": "rope", "anchor": "centre", "dy": 1.4}, "dx": 20, "vec": [150, 0], "role": "applied", "label": "F_R", "lx": 10, "ly": -14},
                {"kind": "arrow", "at": {"entity": "rope", "anchor": "centre", "dy": 1.0}, "dx": -10, "vec": [-100, 0], "role": "friction", "label": "F_net", "lx": -110, "ly": 44},
            ],
            "badges": ["Illustrative"], "frame": view(150, 0, 860), "keyframes": [1.0, 4.5, 7.5],
        }

    # ---------- 5 seesaw ----------
    def seesaw(self):
        top, d1, d2 = 0.62, 0.95, 2.45
        period = 2 * math.pi / 1.2
        rot = [[r(t), 0, top, r(1.6 * math.sin(t * 1.2), 3)] for t in steps(0, period)]
        plank = {"id": "plank", "draw": "seesaw", "xform": {"y": top, "size": [6.0, 0.5]}, "state": {"handles": []}}
        ents = [{"id": "fulcrum", "draw": "fulcrum", "xform": {"size": [0.76, top]}}, plank]
        tracks = [{"id": "plank", "kind": "path", "samples": rot}]
        for i, (who, sx, d) in enumerate((("man", -d1, 1), ("girl", d2, -1))):
            ents.append({"id": who, "draw": f"cast:{who}", "xform": {"dir": d}, "shadow": False})
            # the handle: a grip 0.17 x height above the plank, where the sitting arms reach in every frame
            gy = 0.17 * self.h(who)
            hx = sx + d * 0.85 * self.reach("Sitting_Idle_Loop", who, gy, rel=lambda fr, w=who: self.lap(fr, w))
            plank["state"]["handles"].append([r(hx), r(0.08 + gy)])
            tracks += [
                {"id": who, "kind": "clip", "clip": "Sitting_Idle_Loop", "rate": 1, "loop": True, "t_offset": r(i * 0.7), "t0": 0},
                {"id": who, "kind": "socket", "parent": "plank", "socket": "top", "offset": [r(sx), 0], "child_socket": "lap", "t0": 0},
                {"id": who, "kind": "ik", "hand": "r", "target": {"entity": "plank", "anchor": "top", "dx": r(hx), "dy": r(gy)}},
                {"id": who, "kind": "ik", "hand": "l", "target": {"entity": "plank", "anchor": "top", "dx": r(hx - d * 0.03), "dy": r(gy)}},
            ]
        dy = -0.28
        return {
            "caption": "A father and daughter balance a seesaw: the heavier one sits nearer the pivot.", "backdrop": {"id": "outdoor"},
            "period": r(period), "entities": ents, "tracks": tracks,
            "overlays": [
                {"kind": "dim", "a": {"entity": "plank", "anchor": "top", "dy": dy}, "b": {"entity": "plank", "anchor": "top", "dx": -d1, "dy": dy}, "text": "d_1"},
                {"kind": "dim", "a": {"entity": "plank", "anchor": "top", "dy": dy}, "b": {"entity": "plank", "anchor": "top", "dx": d2, "dy": dy}, "text": "d_2"},
                {"kind": "arrow", "at": {"entity": "plank", "anchor": "top", "dx": -d1}, "dx": -40, "dy": 10, "vec": [0, -150], "role": "weight", "label": "W_1", "lx": -60, "ly": 0},
                {"kind": "arrow", "at": {"entity": "plank", "anchor": "top", "dx": d2}, "dx": 40, "dy": 10, "vec": [0, r(-160 * d1 / d2, 1)], "role": "weight", "label": "W_2", "lx": 14, "ly": 0},
                {"kind": "card", "screen": [1060, 120], "w": 500, "title": "balanced when the moments are equal:",
                 "eq": "W<tspan baseline-shift=\"sub\" font-size=\"0.62em\">1</tspan> × d<tspan baseline-shift=\"sub\" font-size=\"0.62em\">1</tspan> = W<tspan baseline-shift=\"sub\" font-size=\"0.62em\">2</tspan> × d<tspan baseline-shift=\"sub\" font-size=\"0.62em\">2</tspan>",
                 "lines": ["moment = force × distance from the pivot"]},
            ],
            "badges": ["Illustrative"], "frame": view(175, 0, 850), "keyframes": [r(period * 0.1), r(period * 0.25), r(period * 0.75)],
        }

    # ---------- 6 swing ----------
    def swing(self):
        L, top, th0 = 2.3, 3.05, 0.62
        w = math.sqrt(9.81 / L)
        period = 2 * math.pi / w
        ts = steps(0, period)
        th = [th0 * math.cos(w * t) for t in ts]
        thd = [-th0 * w * math.sin(w * t) for t in ts]
        # the girl's hips over the rope: the lap socket (mid-thigh) sits that far ahead of the pelvis
        fr = self.m.sample("Sitting_Idle_Loop", 0.4)
        j = self.m.ji
        side = "l" if fr[j["thigh_l"]][1] < fr[j["thigh_r"]][1] else "r"
        hg = self.h("girl")
        lap_dx = ((fr[j["thigh_" + side]][0] + fr[j["calf_" + side]][0]) / 2 - fr[j["pelvis"]][0]) * hg
        yl, yh = top - L, top - L * math.cos(th0)
        arc = [[r(L * math.sin(th0 * k)), r(top - L * math.cos(th0 * k))] for k in [i / 20 - 1 for i in range(41)]]
        vel = [[r(t), r(L * td * 70 * math.cos(a), 1), r(L * td * 70 * math.sin(a), 1)] for t, a, td in zip(ts, th, thd)]
        energy = [[r(t), r((1 - math.cos(a)) / (1 - math.cos(th0)), 3), r(1 - (1 - math.cos(a)) / (1 - math.cos(th0)), 3)] for t, a in zip(ts, th)]
        return {
            "caption": "On a swing, energy keeps changing between height (PE) and speed (KE).", "backdrop": {"id": "outdoor"},
            "period": r(period),
            "entities": [{"id": "frame", "draw": "swing", "xform": {"size": [3.0, top]}},
                         {"id": "seat", "draw": "swing_seat", "xform": {"y": top, "size": [0.6, L - 0.05]}},
                         {"id": "girl", "draw": "cast:girl", "shadow": False}],
            "tracks": [
                {"id": "seat", "kind": "path", "samples": [[r(t), 0, top, r(a * 180 / math.pi, 3)] for t, a in zip(ts, th)]},
                {"id": "girl", "kind": "clip", "clip": "Sitting_Idle_Loop", "rate": 0, "t_offset": 0.4, "t0": 0},
                {"id": "girl", "kind": "socket", "parent": "seat", "socket": "seat", "offset": [r(lap_dx), 0], "child_socket": "lap", "t0": 0},
                {"id": "girl", "kind": "ik", "hand": "r", "target": {"entity": "seat", "anchor": "seat", "dx": 0.02, "dy": 0.55}},
                {"id": "girl", "kind": "ik", "hand": "l", "target": {"entity": "seat", "anchor": "seat", "dx": 0.0, "dy": 0.62}},
            ],
            "overlays": [
                {"kind": "path", "pts": arc, "style": "dashed", "role": "path"},
                {"kind": "line", "a": [1.0, r(yl)], "b": [2.6, r(yl)]},
                {"kind": "line", "a": [1.2, r(yh)], "b": [2.6, r(yh)]},
                {"kind": "dim", "a": [2.45, r(yl)], "b": [2.45, r(yh)], "arrows": True, "text": "h", "role": "muted", "lx": 26, "ly": 14},
                {"kind": "arrow", "at": {"entity": "seat", "anchor": "seat"}, "dy": -30, "samples": vel, "role": "velocity", "label": "v", "lx": 10, "ly": -8},
                {"kind": "energy", "screen": [1080, 330], "w": 470, "samples": energy, "title": "energy (no friction)", "note": "PE + KE stays the same"},
                {"kind": "words", "at": [r(-L * math.sin(th0) - 1.2), r(yh + 0.25)], "text": "highest: all PE", "size": 24, "weight": 600},
                {"kind": "words", "at": [-0.6, r(yl - 0.65)], "text": "lowest: all KE", "size": 24, "weight": 600},
            ],
            "badges": ["Illustrative"], "frame": view(150, -0.6, 870), "keyframes": [0.0, r(period * 0.25), r(period * 0.4)],
        }

    # ---------- 7 rain on a walking man ----------
    def rain(self):
        who, clip, h = "man", "Walk_Loop", self.h("man")
        v = self.stride(clip, who)
        period = self.whole(clip, 3.2 / v)
        walk = v * period
        return {
            "caption": "Rain falls straight down on a man walking; to him it comes at an angle.",
            "backdrop": {"id": "outdoor", "state": {"sky": "overcast"}}, "period": r(period),
            "entities": [{"id": "rain", "draw": "rain", "xform": {"x": 0.2, "size": [7.6, 4.2]}, "state": {"speed": 7.0, "drops": 90}},
                         {"id": "man", "draw": "cast:man"}],
            "tracks": [
                {"id": "man", "kind": "path", "samples": [[0, -2.9, 0], [r(period), r(-2.9 + walk), 0]]},
                {"id": "man", "kind": "clip", "clip": clip, "rate": 1, "loop": True, "lock": True, "t0": 0},
            ],
            "overlays": [
                {"kind": "arrow", "at": {"entity": "man", "anchor": "head_top", "dx": -0.1, "dy": 0.25}, "vec": [150, 0], "role": "velocity", "label": "v_m", "lx": 10, "ly": 14},
                {"kind": "card", "screen": [1080, 120], "w": 470, "h": 400, "title": "SEEN BY THE MAN", "title_size": 19, "title_color": "#5d6672",
                 "vectors": [{"from": [330, 70], "to": [330, 300], "role": "weight", "label": "v_r", "lx": 14, "ly": -60},
                             {"from": [330, 300], "to": [180, 300], "role": "velocity", "label": "−v_m", "dashed": True, "lx": -20, "ly": 46},
                             {"from": [330, 70], "to": [180, 300], "role": "applied", "label": "v_rm", "lx": -120, "ly": -70}]},
                {"kind": "words", "screen": [1104, 496], "text": "tan θ = v<tspan baseline-shift=\"sub\" font-size=\"0.62em\">m</tspan> / v<tspan baseline-shift=\"sub\" font-size=\"0.62em\">r</tspan>", "size": 26, "halo": False},
                {"kind": "words", "screen": [1362, 310], "text": "θ", "size": 34, "anchor": "middle", "halo": False},
            ],
            "badges": ["Illustrative"], "frame": view(230, 0.0, 850), "keyframes": [r(period * 0.2), r(period * 0.5), r(period * 0.8)],
        }

    # ---------- 8 the same jump on the Moon and on Mars ----------
    def moonmars(self):
        who, v0, h = "man", 2.4, self.h("man")
        pre, post = 0.35, 0.45
        panes, ents, tracks, overlays = [], [], [], []
        gs = (("Moon", 1.62, "moon"), ("Mars", 3.71, "mars"))
        period = pre + 2 * v0 / gs[0][1] + post + 0.8
        for i, (name, g, ground) in enumerate(gs):
            air = 2 * v0 / g
            apex = v0 * v0 / (2 * g)
            pid = f"man{i}"
            panes.append({"backdrop": {"id": "space", "state": {"ground": ground}}, "frame": {"cx": 0, "cy": r((880 - VH / 2) / 175), "s": 175, "ease_ms": 0}})
            ents.append({"id": pid, "draw": "cast:man", "pane": i, "xform": {"x": -0.2}})
            ys = [[r(pre + u), -0.2, r(v0 * u - 0.5 * g * u * u)] for u in steps(0, air)]
            tracks += [
                {"id": pid, "kind": "path", "samples": [[0, -0.2, 0]] + ys + [[r(period), -0.2, 0]]},
                {"id": pid, "kind": "clip", "clip": "Jump_Start", "rate": r(self.m.clips["Jump_Start"]["dur"] / pre), "loop": False, "t0": 0},
                {"id": pid, "kind": "clip", "clip": "Jump_Loop", "rate": 1, "loop": True, "t0": pre, "events": [{"t": r(pre + air / 2), "name": "apex"}]},
                {"id": pid, "kind": "clip", "clip": "Jump_Land", "rate": r(self.m.clips["Jump_Land"]["dur"] / post), "loop": False, "t0": r(pre + air)},
                {"id": pid, "kind": "clip", "clip": "Idle_Loop", "rate": 1, "loop": True, "t0": r(pre + air + post), "blend": 0.3},
            ]
            ink = "#ffffff" if ground == "moon" else "#3a1d10"
            overlays += [
                {"kind": "line", "pane": i, "a": [-1.43, h], "b": [1.43, h], "color": ink, "opacity": "0.6"},
                {"kind": "line", "pane": i, "a": [-1.43, r(apex + h)], "b": [1.43, r(apex + h)], "color": ink, "opacity": "0.6"},
                {"kind": "dim", "pane": i, "a": [1.14, h], "b": [1.14, r(apex + h)], "arrows": True, "text": "h", "role": "velocity", "lx": 28, "ly": 14},
                {"kind": "words", "pane": i, "screen": [40, 150], "text": name, "size": 40, "weight": 700, "color": ink, "halo": False},
                {"kind": "words", "pane": i, "screen": [40, 198], "text": f"g = {g} m/s²  ·  constant", "size": 26, "halo": False,
                 "color": "#D8DCE6" if ground == "moon" else "#5a2a14"},
            ]
        ratio = gs[1][1] / gs[0][1]  # h = v0^2 / 2g: the same v0, so h_moon / h_mars = g_mars / g_moon
        overlays.append({"kind": "card", "pane": "all", "screen": [380, 928], "w": 840, "h": 56,
                         "lines": [], "title": f"same take-off speed:  h on the Moon / h on Mars = {ratio:.2f}  (computed)", "title_size": 27})
        return {
            "caption": "The same jump on the Moon and on Mars.", "view": "split", "panes": panes, "period": r(period),
            "entities": ents, "tracks": tracks, "overlays": overlays, "badges": ["Illustrative"],
            "keyframes": [r(pre * 0.6), r(pre + 2 * v0 / 3.71 / 2), r(pre + 2 * v0 / 1.62 / 2)],
        }


NAMES = ["push", "throw", "carry", "tug", "seesaw", "swing", "rain", "moonmars"]


def build() -> dict[str, dict]:
    sc = Scenes()
    out = {}
    for n in NAMES:
        p = getattr(sc, n)()
        cap = p.pop("caption")
        p["overlays"] = [caption(cap)] + p["overlays"] if p.get("view") != "split" else p["overlays"]
        p = {"rev": 1, "source": SOURCE, "name": n, "caption": cap, "view": p.pop("view", "side"), **p}
        out[n] = p
    return out


def dump(p: dict) -> str:
    """Indented JSON with each list of numbers on one line (samples stay readable)."""
    s = json.dumps(p, indent=1, ensure_ascii=False)
    return re.sub(r"\[\s*(-?[\d.e-]+(?:,\s*-?[\d.e-]+)*)\s*\]", lambda m: "[" + re.sub(r",\s*", ", ", m.group(1)) + "]", s) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for n, p in build().items():
        (OUT / f"{n}.json").write_text(dump(p), encoding="utf-8")
        print(n, len(p["entities"]), "entities,", len(p["tracks"]), "tracks, period", p.get("period"))


if __name__ == "__main__":
    main()
