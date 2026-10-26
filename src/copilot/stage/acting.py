"""Acting (F-017 §6): a verb becomes clip tracks, IK targets and sockets that agree with the solver's motion.

- verb -> clip row (config/stage_clips.json via stage.motion.VERBS); playback rate = the solver's speed / the clip's
  stride speed (x the person's height), so planted feet do not slide;
- time-warp: a clip event lands on the solver's event (the throw's release frame = the projectile's t0; a push's hands
  touch for the force interval; a jump's apex = the solver's apex). A changing speed is played as short clip
  segments, each at the speed of its moment, the clip phase carried over (no pop);
- IK targets from prop anchors (a push face, a rope, a seesaw handle, a swing rope) at a height the arms reach in
  every frame of the clip (reach());
- sockets: hand_r / hands (holding, carry), on top, the lap on a seat (sitting on);
- mirror: a pull is a push played backwards (E1 tug: a walk turned back about the feet);
- animals: the gait follows the path's speed (web/stage/animals.js).

All lengths in metres in the person's frame (facing +x) unless said; the stage multiplies clip joints by height.
"""
from __future__ import annotations

import math
from functools import cached_property
from typing import Any, Optional

from copilot.stage import catalog
from copilot.stage.motion import VERBS, Motion, clips, load

FPS = 24


def r(x: float, k: int = 4) -> float:
    return round(x + 0.0, k)


class Acting:
    @cached_property
    def m(self) -> Motion:
        return Motion(load())

    @cached_property
    def c(self) -> dict[str, dict[str, Any]]:
        return clips()

    # ---------- people ----------
    def h(self, draw: str) -> float:
        return catalog.cast()[draw[5:]]["height_m"] if draw.startswith("cast:") else 1.7

    def clip_of(self, verb: str) -> str:
        return VERBS.get(verb, ("Idle_Loop",))[0]

    def stride(self, clip: str, draw: str) -> float:
        """The clip's walking speed (m/s) for this person."""
        return self.c[clip]["stride_mps"] * self.h(draw)

    def dur(self, clip: str) -> float:
        return self.c[clip]["dur"]

    def whole(self, clip: str, period: float, rate: float = 1.0) -> float:
        """The period rounded to whole clip cycles (a looping scene restarts in step)."""
        cyc = self.dur(clip) / max(1e-9, abs(rate))
        return max(1, round(period / cyc)) * cyc

    def t_of(self, clip: str, frame: int) -> float:
        return self.m.frame_time(clip, frame)

    def event_t(self, clip: str, name: str) -> float:
        return self.t_of(clip, self.c[clip]["events"][name])

    def palm(self, clip: str, t: float, side: str, x: float, draw: str, d: int = 1,
             loop: Optional[bool] = None) -> tuple[float, float]:
        loop = self.c[clip]["loop"] if loop is None else loop
        q = self.m.palm(self.m.sample(clip, t, loop), side)
        return x + d * q[0] * self.h(draw), q[1] * self.h(draw)

    def lap(self, fr: list, draw: str, mirror: bool = False) -> tuple[float, float]:
        """The socket `lap` in the figure's frame: halfway from hip to knee on the thigh's underside (people.js)."""
        j, h, c = self.m.ji, self.h(draw), catalog.cast()[draw[5:]]
        side = "l" if fr[j["thigh_l"]][1] < fr[j["thigh_r"]][1] else "r"
        hip, knee = fr[j["thigh_" + side]], fr[j["calf_" + side]]
        lw = 1.22 * (c.get("build") or 1) * (0.9 if c["child"] else 1)
        return ((-1 if mirror else 1) * (hip[0] + knee[0]) / 2 * h,
                min(hip[1] * h - 0.044 * lw * h, knee[1] * h - 0.032 * lw * h))

    def lap_dx(self, clip: str, t: float, draw: str) -> float:
        """How far the lap socket sits ahead of the pelvis (a sitter's hips over a swing rope)."""
        fr, j = self.m.sample(clip, t), self.m.ji
        side = "l" if fr[j["thigh_l"]][1] < fr[j["thigh_r"]][1] else "r"
        return ((fr[j["thigh_" + side]][0] + fr[j["calf_" + side]][0]) / 2 - fr[j["pelvis"]][0]) * self.h(draw)

    def leaned(self, fr: list, lean: float) -> list:
        """The frame with the body above the shins turned back by `lean` degrees about the feet (people.js lean)."""
        j = self.m.ji
        fa, fb = fr[j["foot_l"]], fr[j["foot_r"]]
        px, py = (fa[0] + fb[0]) / 2, min(fa[1], fb[1])
        c, s = math.cos(math.radians(lean)), math.sin(math.radians(lean))
        shin = {j[n] for n in ("calf_l", "foot_l", "ball_l", "calf_r", "foot_r", "ball_r")}
        return [q if i in shin else [px + (q[0] - px) * c - (q[1] - py) * s, py + (q[0] - px) * s + (q[1] - py) * c, q[2]]
                for i, q in enumerate(fr)]

    def reach(self, clip: str, draw: str, y: float, side: str = "r", mirror: bool = False, rel=None,
              frac: float = 0.95, lean: float = 0.0) -> float:
        """The furthest forward x a hand reaches at height y in every frame of the clip (from rel(frame)): an IK
        target there is always reachable, so the hand lands on it."""
        h, j = self.h(draw), self.m.ji
        best = math.inf
        for fr in self.m.clips[clip]["frames"]:
            fr = self.leaned(fr, lean) if lean else fr
            ox, oy = rel(fr) if rel else (0.0, 0.0)
            sh, el, pm = fr[j["upperarm_" + side]], fr[j["lowerarm_" + side]], self.m.palm(fr, side)
            arm = (math.dist(sh[:2], el[:2]) + math.dist(el[:2], pm)) * h * frac
            px, py = (-1 if mirror else 1) * sh[0] * h - ox, sh[1] * h - oy
            if abs(y - py) >= arm:
                raise ValueError(f"{draw} cannot reach height {y:.2f} in {clip}")
            best = min(best, px + math.sqrt(arm * arm - (y - py) ** 2))
        return best

    def brace_offset(self, clip: str) -> float:
        """The clip time of the widest stance with both feet planted (a team that digs in)."""
        cont, frames, j = self.c[clip]["contact"], self.m.clips[clip]["frames"], self.m.ji
        i = max((i for i in range(len(frames)) if cont["l"][i] != "0" and cont["r"][i] != "0"),
                key=lambda i: abs(frames[i][j["foot_l"]][0] - frames[i][j["foot_r"]][0]))
        return self.t_of(clip, i)

    # ---------- tracks ----------
    def clip(self, eid: str, clip: str, t0: float = 0.0, rate: float = 1.0, loop: Optional[bool] = None,
             lock: bool = False, **kw) -> dict:
        tr = {"id": eid, "kind": "clip", "clip": clip, "rate": r(rate), "loop": self.c[clip]["loop"] if loop is None
              else loop, "t0": r(t0)}
        if lock:
            tr["lock"] = True
        tr.update({k: v for k, v in kw.items() if v is not None})
        return tr

    def warp(self, eid: str, clip: str, draw: str, speed: list[list[float]], seg: float = 0.25,
             t_offset: float = 0.0, lock: bool = True) -> list[dict]:
        """Clip segments whose rates follow a changing speed (samples [[t, v m/s]]): each segment plays at the speed
        of its middle; the clip phase carries over between segments, so the pose never jumps."""
        st = self.stride(clip, draw)
        t_a, t_b = speed[0][0], speed[-1][0]
        n = max(1, math.ceil((t_b - t_a) / seg - 1e-9))
        out, phase = [], t_offset
        for i in range(n):
            a, b = t_a + (t_b - t_a) * i / n, t_a + (t_b - t_a) * (i + 1) / n
            v = _at(speed, (a + b) / 2)
            rate = v / st if st else 0.0
            out.append(self.clip(eid, clip, a, rate, True, lock, t_offset=r(phase, 5)))
            phase += (b - a) * rate
        return out

    def phase_at(self, tracks: list[dict], t: float) -> float:
        """The clip time the last of `tracks` (warp segments) reaches at stage time t."""
        tr = [x for x in tracks if x["t0"] <= t][-1]
        return tr.get("t_offset", 0.0) + (t - tr["t0"]) * tr["rate"]

    def walk(self, eid: str, draw: str, clip: str, x0: float, t0: float, t1: float, speed: Optional[float] = None,
             d: int = 1) -> tuple[list[dict], float]:
        """A walk from x0 for t0..t1 at `speed` (default: the clip's stride speed); returns (tracks, x at t1)."""
        st = self.stride(clip, draw)
        v = st if speed is None else speed
        x1 = x0 + d * v * (t1 - t0)
        return [{"id": eid, "kind": "path", "samples": [[r(t0), r(x0), 0], [r(t1), r(x1), 0]]},
                self.clip(eid, clip, t0, v / st if st else 1.0, True, True)], x1

    def throw(self, eid: str, draw: str, x: float, obj: str, obj_r: float) -> dict[str, Any]:
        """The overhand throw: the clip starts at 0; the object rides hand_r until the release frame, where the
        projectile's t0 is put (time-warp: release = solver t0). Returns the release time and point (the object's
        bottom centre there: the law's h0)."""
        clip = "OverhandThrow"
        tr = self.event_t(clip, "release")
        hx, hy = self.palm(clip, tr, "r", x, draw, loop=False)
        return {"t_release": tr, "x": hx, "y": hy - obj_r, "tracks": [
            self.clip(eid, clip, 0.0, 1.0, False, events=[{"t": r(tr), "name": "release"}]),
            {"id": obj, "kind": "socket", "parent": eid, "socket": "hand_r", "child_socket": "centre", "t0": 0,
             "t1": r(tr)}]}

    def push_ik(self, eid: str, draw: str, body: str, body_h: float, t0: float = 0.0,
                t1: Optional[float] = None, clip: str = "Push_Loop") -> list[dict]:
        """Both hands on the body's near face (anchor face_l) at the clip's hand heights, for the force interval."""
        out = []
        for hand in ("r", "l"):
            k = {"id": eid, "kind": "ik", "hand": hand, "pad": True, "t0": r(t0),
                 "target": {"entity": body, "anchor": "face_l", "dy": r(self.c[clip]["hands_h"][hand] * self.h(draw) - body_h / 2)}}
            if t1 is not None:
                k["t1"] = r(t1)
            out.append(k)
        return out

    def push_gap(self, draw: str, clip: str = "Push_Loop") -> float:
        """The person's origin -> the pushed face (the hands at full reach touch it)."""
        return self.c[clip]["reach_x"] * self.h(draw) - 0.03

    def push_box_h(self, draw: str, clip: str = "Push_Loop") -> float:
        """A pushed box at least as tall as the hands are high (the hands on its face)."""
        return self.c[clip]["hands_h"]["max"] * self.h(draw) + 0.14

    def sit_reach(self, draw: str, grip_y: float) -> float:
        return self.reach("Sitting_Idle_Loop", draw, grip_y, rel=lambda fr: self.lap(fr, draw))

    def jump(self, eid: str, t_take: float, air: float, land: float = 0.45, pre: float = 0.35) -> list[dict]:
        """A jump time-warped to the solver: the take-off clip squeezed into `pre` s before t_take, the air clip with
        its apex at the solver's apex, the landing clip after the solver's landing."""
        ds, dl = self.dur("Jump_Start"), self.dur("Jump_Land")
        return [self.clip(eid, "Jump_Start", t_take - pre, ds / pre, False),
                self.clip(eid, "Jump_Loop", t_take, 1.0, True, events=[{"t": r(t_take + air / 2), "name": "apex"}]),
                self.clip(eid, "Jump_Land", t_take + air, dl / land, False),
                self.clip(eid, "Idle_Loop", t_take + air + land, 1.0, True, blend=0.3)]


def _at(samples: list[list[float]], t: float) -> float:
    if t <= samples[0][0]:
        return samples[0][1]
    for a, b in zip(samples, samples[1:]):
        if t <= b[0]:
            k = (t - a[0]) / ((b[0] - a[0]) or 1)
            return a[1] + (b[1] - a[1]) * k
    return samples[-1][1]


ACT = Acting()
