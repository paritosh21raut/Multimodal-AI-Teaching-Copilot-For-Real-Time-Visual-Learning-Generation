"""The motion pack (F-017 §4): 87 CC0 clips (Quaternius UAL1+2) baked to 2D joints, and the clip table derived from them.

    web/stage/data/motion.json   {joints, fps, clips {name: {dur, frames [frame][joint] = [x, y, z]}}}: a person 1 m
                                 tall, facing +x, feet on the ground; z > 0 = the near (right) side
    config/stage_clips.json      per clip: loop, verbs, stride speed, events, seat / hand heights, foot contacts and
                                 the foot lock (clip_table below)

Everything is per metre of body height: the stage multiplies by the person's height. The browser samples clips the
same way (`web/stage/motion.js`), so a socket Python computes here (a palm) is where the stage draws it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
MOTION = ROOT / "web" / "stage" / "data" / "motion.json"
CLIPS = ROOT / "config" / "stage_clips.json"

FEET = ("foot_l", "ball_l", "foot_r", "ball_r")  # ankle (heel contact) and ball of each foot
PLANT_EPS = 0.004  # a foot point within 4 mm (per m of height) of its lowest is on the ground
LOCK_RELEASE = 4  # frames over which a lifted foot's lock shift eases back to the clip's pose

# verb (contract §3) -> clips; a verb with no clip is acted by IK on a stand clip (E2)
VERBS: dict[str, tuple[str, ...]] = {
    "walk": ("Walk_Loop", "Walk_Formal_Loop"), "jog": ("Jog_Fwd_Loop",), "run": ("Sprint_Loop",),
    "stand": ("Idle_Loop",), "talk": ("Idle_Talking_Loop", "Sitting_Talking_Loop"), "phone": ("Idle_TalkingPhone_Loop",),
    "fold_arms": ("Idle_FoldArms_Loop",), "nod": ("Yes",), "shake_head": ("Idle_No_Loop",), "call": ("Idle_Rail_Call",),
    "push": ("Push_Loop",), "pull": ("Push_Loop",), "throw": ("OverhandThrow",), "carry": ("Walk_Carry_Loop",),
    "pick_up": ("PickUp_Table",), "put_down": ("PickUp_Table",), "hold": ("Idle_Loop",), "point": ("Idle_Loop",),
    "sit": ("Sitting_Idle_Loop", "Sitting_Talking_Loop", "Sitting_Enter", "Sitting_Exit"),
    "jump": ("Jump_Start", "Jump_Loop", "Jump_Land", "NinjaJump_Start", "NinjaJump_Idle_Loop", "NinjaJump_Land"),
    "swim": ("Swim_Fwd_Loop",), "float": ("Swim_Idle_Loop",), "drive": ("Driving_Loop",), "climb": ("ClimbUp_1m_RM",),
    "crouch": ("Crouch_Idle_Loop", "Crouch_Fwd_Loop"), "kneel": ("Fixing_Kneeling",), "roll": ("Roll", "Roll_RM"),
    "slide": ("Slide_Start", "Slide_Loop", "Slide_Exit"), "water": ("Farm_Watering",), "plant": ("Farm_PlantSeed",),
    "harvest": ("Farm_Harvest",), "chop": ("TreeChopping_Loop",), "eat": ("Consume",), "drink": ("Consume",),
    "dance": ("Dance_Loop",), "wave": ("Interact",), "catch": ("Idle_Loop",), "look_at": ("Idle_Loop",),
}
SIT = ("Sitting_Idle_Loop", "Sitting_Talking_Loop", "Driving_Loop")


def load(path: Path = MOTION) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


class Motion:
    """Clip sampling, the same arithmetic as web/stage/motion.js."""

    def __init__(self, data: dict[str, Any]):
        self.data = data
        self.fps = data["fps"]
        self.ji = {j: i for i, j in enumerate(data["joints"])}
        self.clips = data["clips"]

    def sample(self, name: str, t: float, loop: bool = True) -> list[list[float]]:
        c = self.clips[name]
        n, dur = len(c["frames"]), c["dur"]
        tt = ((t % dur) + dur) % dur if loop else max(0.0, min(t, dur * 0.999))
        u = (tt / dur) * (n if loop else n - 1)
        i = int(u)
        k = u - i
        a = c["frames"][i % n]
        b = c["frames"][(i + 1) % n if loop else min(i + 1, n - 1)]
        return [[p[0] + (q[0] - p[0]) * k, p[1] + (q[1] - p[1]) * k, p[2] + (q[2] - p[2]) * k] for p, q in zip(a, b)]

    def joint(self, fr: list[list[float]], name: str) -> list[float]:
        return fr[self.ji[name]]

    def palm(self, fr: list[list[float]], side: str) -> tuple[float, float]:
        """The palm centre (socket hand_r / hand_l): halfway from the wrist to the middle finger's base."""
        a, b = self.joint(fr, "hand_" + side), self.joint(fr, "middle_01_" + side)
        return (a[0] + b[0]) / 2, (a[1] + b[1]) / 2

    def frame_time(self, name: str, i: int) -> float:
        """Clip time of frame i (a loop clip has n frames over dur; a one-shot spreads n - 1 steps over dur)."""
        c = self.clips[name]
        n = len(c["frames"])
        return c["dur"] * i / (n if is_loop(name) else max(1, n - 1))


def is_loop(name: str) -> bool:
    return name.endswith("_Loop")


def _r(x: float, k: int = 4) -> float:
    return round(x, k)


def contacts(m: Motion, name: str) -> dict[str, list[int]]:
    """Per foot, per frame: 0 in the air, 1 heel (ankle at its lowest), 2 ball, 3 both."""
    f = m.clips[name]["frames"]
    lows = {p: min(fr[m.ji[p]][1] for fr in f) for p in FEET}
    floor = min(lows.values())
    out = {}
    for s in ("l", "r"):
        codes = []
        for fr in f:
            heel = fr[m.ji["foot_" + s]][1] - lows["foot_" + s] < PLANT_EPS and lows["foot_" + s] < floor + 0.06
            ball = fr[m.ji["ball_" + s]][1] - lows["ball_" + s] < PLANT_EPS
            codes.append((1 if heel else 0) + (2 if ball else 0))
        out[s] = codes
    return out


def _point(m: Motion, fr, s: str, code: int) -> float:
    """The x of a foot's contact point: the ball when it is down, else the heel."""
    return fr[m.ji[("ball_" if code & 2 else "foot_") + s]][0]


def stride(m: Motion, name: str, con: dict[str, list[int]]) -> float:
    """The speed (m/s per m of height) the clip walks at: the mean backward speed of the planted contact points.
    Played at it, the planted feet stay put (the reference's lower-foot estimate under-read the jog by half)."""
    c = m.clips[name]
    f, n = c["frames"], len(c["frames"])
    vel: list[float | None] = []
    for i in range(n):
        j = (i + 1) % n
        d = [_point(m, f[i], s, con[s][i]) - _point(m, f[j], s, con[s][i]) for s in ("l", "r")
             if con[s][i] and con[s][j] and (con[s][i] & 2) == (con[s][j] & 2)]
        vel.append(sum(d) / len(d) if d else None)
    known = [v for v in vel if v is not None]
    if not known:
        return 0.0
    # in the air (a run's flight): the speed carries on
    mean = sum(known) / len(known)
    total = sum(v if v is not None else mean for v in vel)
    return max(0.0, total / c["dur"])


def lock(m: Motion, name: str, con: dict[str, list[int]], v: float) -> dict[str, list[float]]:
    """Per foot, per frame: the x shift (per m of height) that keeps a planted foot's contact point still on the ground
    when the clip plays at its stride speed. The stage adds it to the foot and bends the knee to reach (leg IK)."""
    c = m.clips[name]
    f, n = c["frames"], len(c["frames"])
    step = v * c["dur"] / n
    out = {}
    for s in ("l", "r"):
        code = con[s]
        shift = [0.0] * n
        if all(code) or not any(code):
            out[s] = shift
            continue
        start = code.index(0)
        cur, target, seg, since = 0.0, None, None, LOCK_RELEASE
        lifted_at = 0.0
        for k in range(1, 2 * n + 1):  # two cycles: the second starts settled
            i = (start + k) % n
            world = _point(m, f[i], s, code[i]) + step * (start + k) if code[i] else 0.0
            kind = code[i] & 2 if code[i] else None
            if code[i]:
                if seg != kind:  # a new contact (strike, or heel -> ball): keep the shift continuous
                    target = world + cur
                    seg = kind
                cur = target - world
                since = 0
            else:
                if seg is not None:
                    lifted_at, seg = cur, None
                since += 1
                cur = lifted_at * max(0.0, 1 - since / LOCK_RELEASE)
            if k > n:
                shift[i] = cur
        out[s] = [_r(x) for x in shift]
    return out


def events(m: Motion, name: str, con: dict[str, list[int]]) -> dict[str, Any]:
    f = m.clips[name]["frames"]
    n = len(f)
    ev: dict[str, Any] = {}
    strikes = [[i, s] for i in range(n) for s in ("l", "r") if con[s][i] and not con[s][(i - 1) % n]]
    if strikes and is_loop(name):
        ev["footstrike"] = sorted(strikes)
    if name == "OverhandThrow":  # the reference's release: the hand highest and furthest forward
        ev["release"] = max(range(n), key=lambda i: m.palm(f[i], "r")[1] + 0.6 * m.palm(f[i], "r")[0])
    if name in ("Push_Loop", "Interact"):  # the hands furthest forward
        ev["contact"] = max(range(n), key=lambda i: max(m.palm(f[i], "l")[0], m.palm(f[i], "r")[0]))
    if name == "PickUp_Table":  # the hands lowest: on the table
        ev["contact"] = min(range(n), key=lambda i: m.palm(f[i], "l")[1] + m.palm(f[i], "r")[1])
    if "Jump" in name:
        ev["apex"] = max(range(n), key=lambda i: f[i][m.ji["pelvis"]][1])
    return ev


def clip_row(m: Motion, name: str) -> dict[str, Any]:
    c = m.clips[name]
    f, n = c["frames"], len(c["frames"])
    con = contacts(m, name)
    loop = is_loop(name)
    moves = loop and any(name.startswith(p) for p in ("Walk", "Jog", "Sprint", "Push", "Crouch_Fwd", "Zombie_Walk"))
    v = stride(m, name, con) if moves else 0.0
    palms = [(m.palm(fr, "l"), m.palm(fr, "r")) for fr in f]
    row: dict[str, Any] = {
        "name": name, "verb": sorted(k for k, cs in VERBS.items() if name in cs), "loop": loop,
        "dur": c["dur"], "frames": n, "stride_mps": _r(v), "events": events(m, name, con),
        "seat_h": None, "hands_h": {"l": _r(sum(p[0][1] for p in palms) / n), "r": _r(sum(p[1][1] for p in palms) / n),
                                    "max": _r(max(max(p[0][1], p[1][1]) for p in palms))},
        "reach_x": _r(max(max(p[0][0], p[1][0]) for p in palms)),
    }
    if name in SIT:  # the hip joints' height: the stage puts the thighs' underside on the seat (socket `lap`)
        row["seat_h"] = _r(sum(min(fr[m.ji["thigh_l"]][1], fr[m.ji["thigh_r"]][1]) for fr in f) / n)
        row["pelvis_x"] = _r(sum(fr[m.ji["pelvis"]][0] for fr in f) / n)
    if moves:
        row["contact"] = {s: "".join(map(str, con[s])) for s in ("l", "r")}
        row["lock"] = lock(m, name, con, v)
    return row


def clip_table(data: dict[str, Any]) -> dict[str, Any]:
    m = Motion(data)
    return {"units": "per metre of body height; frame indices at fps", "fps": m.fps,
            "clips": [clip_row(m, n) for n in sorted(m.clips)]}


def clips(path: Path = CLIPS) -> dict[str, dict[str, Any]]:
    return {r["name"]: r for r in json.loads(Path(path).read_text(encoding="utf-8"))["clips"]}
