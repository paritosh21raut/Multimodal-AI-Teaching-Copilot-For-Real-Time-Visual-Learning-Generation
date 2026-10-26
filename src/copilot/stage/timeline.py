"""Graph + law results + director + acting -> `stage.patch` (contract §8), and patch diffs.

A stager builds one interacting group in its own metres: a law's roles (sliding_friction: the pusher and the box;
moments: the plank, the pivot, the two sitters) or an action pattern (a tug of war, a carry, a walk with a dog). The
law module owns every number (and its provenance); acting turns the verbs into clips, IK and sockets that agree with
the solver; the director lays the groups out, frames the shot, places labels, dims and staggers. The browser only
draws the patch. Deterministic: the same graph gives the same bytes.

Every overlay that prints a digit carries `value` / `values` (provenance ids in `numbers`) or is the teacher's own
line (`said`); `check_numbers` refuses a patch otherwise.
"""
from __future__ import annotations

import math
import re
from typing import Any, Optional

from copilot.stage import catalog, director
from copilot.stage.acting import ACT, r
from copilot.stage.graph import Action, Ent, Graph, LawRec
from copilot.stage.laws import LAWS, Num, Result, place_key
from copilot.stage.laws.base import PRETTY, steps
from copilot.simulation.base import fmt

VW, VH = director.VW, director.VH
SUB = '<tspan baseline-shift="sub" font-size="0.62em">{}</tspan>'
NAMES = {"v0": "v_0", "theta": "θ", "theta0": "θ_0", "mu_k": "μ_k", "mu_s": "μ_s", "t_apex": "t_top", "h_apex": "h_top",
         "a_stop": "a", "t_stop": "t_stop", "s_stop": "s_stop", "v_rel": "v_rm", "va": "v_r", "vb": "v_m",
         "gap_ratio": "gaps", "W1": "W_1", "W2": "W_2", "m1": "m_1", "m2": "m_2", "d1": "d_1", "d2": "d_2",
         "M1": "M_1", "M2": "M_2", "rho_body": "ρ_body", "rho": "ρ", "f_s_max": "f_s,max"}
WHAT = {"said": "said", "computed": "computed", "constant": "constant"}


def _sub(s: str) -> str:
    """"W_1" -> W with a subscript 1 (SVG tspan), as the cards print equations."""
    return re.sub(r"_(\w+)", lambda m: SUB.format(m.group(1)), s)


class Build:
    def __init__(self, g: Graph, prev: Optional[dict] = None, nogo: Optional[list] = None, rev: int = 1):
        self.g, self.prev, self.nogo, self.rev = g, prev, nogo or [], rev
        self.E: dict[str, dict] = {}
        self.T: list[dict] = []
        self.O: list[dict] = []
        self.N: dict[str, dict] = {}
        self.badges: list[str] = []
        self.groups: list[director.Group] = []
        self.periods: list[float] = []
        self.keys: list[float] = []
        self.cards: list[dict] = []
        self.group_ov: list[list[dict]] = []
        self.ov_mark = 0
        self.done: set[str] = set()
        self.busy: set[str] = set()
        self.backdrop: dict[str, Any] = {"id": "outdoor"}
        self.view = "side"
        self.panes: Optional[list[dict]] = None
        self.illustrative = False
        self.results: dict[str, Result] = {}
        self.frame_ids: Optional[list[str]] = None

    # ---------- helpers ----------
    def ent(self, e: Ent | str, draw: Optional[str] = None, **xf) -> dict:
        eid = e if isinstance(e, str) else e.id
        d = {"id": eid, "draw": draw or (e.draw if isinstance(e, Ent) else draw)}
        xf = {k: (r(v) if isinstance(v, float) else v) for k, v in xf.items() if v is not None}
        if isinstance(e, Ent) and e.row == "far":
            xf["row"] = "far"
        if xf:
            d["xform"] = xf
        self.E[eid] = d
        self.done.add(eid)
        return d

    def track(self, *ts: dict) -> None:
        self.T.extend(ts)

    def over(self, *os: dict) -> None:
        self.O.extend(os)

    def num(self, n: Num, law: str) -> Optional[str]:
        if not n.known:
            return None
        pid = f"{law}.{n.sym}"
        self.N[pid] = n.rec()
        return pid

    def row(self, res: Result, sym: str, name: Optional[str] = None) -> Optional[tuple[list[str], str]]:
        """A card row [symbol, "value unit · source"] and its provenance id, for a printable number."""
        n = res.nums.get(sym)
        if n is None or not n.known:
            return None
        pid = self.num(n, res.law)
        v, u = (n.v, n.u)
        if n.src == "said" and n.shown_u and n.shown_u not in (n.u,):  # shown as said: 36 km/h
            v, u = float(next(g for g in self.g.laws[res.law].givens.values() if g.sym == sym).v), n.shown_u
        u = PRETTY.get(u, u)
        return [name or NAMES.get(sym, sym), f"{fmt(v)}{' ' + u if u else ''}  · {WHAT[n.src]}"], pid

    def card(self, title: str, res: Optional[Result], syms: list[str], lines: Optional[list[str]] = None,
             eq: Optional[str] = None, w: int = 520, names: Optional[dict] = None, **kw) -> Optional[dict]:
        rows, vals = [], []
        for s in syms:
            got = self.row(res, s, (names or {}).get(s)) if res else None
            if got:
                rows.append(got[0])
                vals.append(got[1])
        if not rows and not lines and not eq:
            return None
        c = {"kind": "card", "screen": [0, 0], "w": w, "title": title, "rows": rows, "lines": lines or []}
        if eq:
            c["eq"] = eq
        if vals:
            c["values"] = vals
        c.update(kw)
        self.cards.append(c)
        self.over(c)
        return c

    def law_ents(self, law: LawRec) -> list[str]:
        return [i for v in law.roles.values() for i in (v if isinstance(v, list) else [v])]

    def acts_on(self, obj: str, verbs: tuple[str, ...]) -> list[Action]:
        return sorted((a for a in self.g.actions.values() if a.obj == obj and a.verb in verbs), key=lambda a: a.seq)

    def acts_of(self, agent: str, verbs: Optional[tuple[str, ...]] = None) -> list[Action]:
        return sorted((a for a in self.g.actions.values() if a.agent == agent and (verbs is None or a.verb in verbs)),
                      key=lambda a: a.seq)

    def solve(self, law: LawRec, ctx: dict) -> Result:
        res = LAWS[law.name].solve(law.id, law.givens, ctx)
        self.results[law.id] = res
        self.illustrative |= res.illustrative
        return res

    def group(self, ids: list[str], period: float, keys: list[float]) -> None:
        self.groups.append(director.Group(list(dict.fromkeys(ids))))
        self.group_ov.append(self.O[self.ov_mark:])  # the overlays this stager drew go with its group
        self.ov_mark = len(self.O)
        self.periods.append(period)
        if not self.keys:
            self.keys = [r(k, 3) for k in keys]
        self.busy |= set(ids)

    def dirn(self, a: Optional[Action]) -> int:
        return -1 if a and a.dir == "left" else 1

    # ---------- build ----------
    def run(self) -> dict:
        g = self.g
        place = g.place()
        if place:
            bd = catalog.backdrop(place.w) or catalog.backdrop(place.near or "") or {"id": "outdoor"}
            self.backdrop = {"id": bd["id"]}
        for law in g.laws.values():
            if any(i in self.done for i in self.law_ents(law)) and law.name != "relative_motion":
                continue
            getattr(self, "_" + law.name)(law)
        self._actions()
        self._static()
        return self.finish()

    # ---------- law stagers ----------
    def _sliding_friction(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        body = g.ents[ro["body"]]
        pushes = self.acts_on(body.id, ("push", "pull"))
        pusher_id = ro.get("force_from") or (pushes[-1].agent if pushes else None)
        cur = pushes[-1] if pushes else None
        phase = "rest" if cur is None else ("hard" if cur.manner == "hard" else "steady") if cur.active else "released"
        if g.ents.get(pusher_id) is None or not g.ents[pusher_id].draw.startswith("cast:"):
            pusher_id = None
        man = g.ents[pusher_id] if pusher_id else None
        draw = man.draw if man else "cast:man"
        clip = "Push_Loop"
        v_push = ACT.stride(clip, draw)
        if body.draw.startswith("cast:") or body.draw.startswith("species:"):
            w, bh = body.size
        else:
            w, bh = max(0.95, body.size[0]), min(1.4, ACT.push_box_h(draw))
        lead = 0.0
        if phase == "released":
            was_hard = cur.manner == "hard"
            v0 = v_push
            if was_hard:
                v0 = self.solve(law, {"phase": "hard", "v0": v_push, "T": 3.0}).facts["v_end"]
            lead = 0.6
            res = self.solve(law, {"phase": "released", "v0": v0, "T": 3.0})
        elif phase == "hard":
            res = self.solve(law, {"phase": "hard", "v0": v_push, "T": 3.0})
            v0 = v_push
        elif phase == "steady":
            T = ACT.whole(clip, 2.6 / v_push)
            res = self.solve(law, {"phase": "steady", "v0": v_push, "T": T})
            v0 = v_push
        else:
            res = self.solve(law, {"phase": "rest", "T": 2.0})
            v0 = 0.0
        xs = res.samples["body"]
        speed = res.samples["speed"]
        # lead-in: he pushes at v0 for `lead` s, then lets go (the law's t = 0)
        path = ([[0.0, 0.0, 0.0]] if lead else []) + [[r(t + lead), r(x + v0 * lead), 0.0] for t, x, _ in xs]
        spd = ([[0.0, v0]] if lead else []) + [[r(t + lead), v] for t, v in speed]
        period = path[-1][0] + (0.0 if phase in ("steady", "hard") else 0.4)
        bx0 = -1.2 if phase != "released" else -0.8
        gap = ACT.push_gap(draw, clip)
        self.ent(body, body.draw, size=[r(w), r(bh)] if not body.draw.startswith(("cast:", "species:")) else None)
        self.track({"id": body.id, "kind": "path", "samples": [[t, r(bx0 + w / 2 + x), 0] for t, x, _ in path]})
        ids = [body.id]
        if man:
            self.ent(man)
            t_let = lead if phase == "released" else None
            push_until = [s for s in spd if t_let is None or s[0] <= t_let + 1e-9]
            if phase == "released":
                mx = bx0 - gap + v0 * lead
                self.track({"id": man.id, "kind": "path", "samples": [[0, r(bx0 - gap), 0], [r(lead), r(mx), 0],
                                                                       [r(period), r(mx), 0]]})
                self.track(ACT.clip(man.id, clip, 0, v0 / ACT.stride(clip, draw), True, True),
                           ACT.clip(man.id, "Idle_Loop", lead, 1.0, True, blend=0.4))
                self.track(*ACT.push_ik(man.id, draw, body.id, bh, 0, lead))
            elif phase == "rest":
                self.track({"id": man.id, "kind": "path", "samples": [[0, r(bx0 - gap - 0.4), 0]]},
                           ACT.clip(man.id, "Idle_Loop", 0, 1.0, True))
            else:
                self.track({"id": man.id, "kind": "path", "samples": [[t, r(bx0 - gap + x), 0] for t, x, _ in path]})
                if phase == "steady":
                    self.track(ACT.clip(man.id, clip, 0, 1.0, True, True))
                else:
                    self.track(*ACT.warp(man.id, clip, draw, push_until, 0.25))
                self.track(*ACT.push_ik(man.id, draw, body.id, bh, 0))
            ids.append(man.id)
            self.E = {k: self.E[k] for k in [man.id, body.id] + [k for k in self.E if k not in (man.id, body.id)]}
        # arrows: the push while hands are on, friction while it slides, the velocity scaled by speed
        t_push = lead if phase == "released" else period
        moving = res.events.get("stop", period - lead) + lead if phase == "released" else period
        vmax = max(v for _, v in spd) or 1.0
        k = 150 / max(vmax, v_push)
        if phase != "rest":
            F = {"steady": 150, "hard": 220, "released": 150}[phase]
            self.over({"kind": "arrow", "at": {"entity": body.id, "anchor": "face_l", "dx": 0.03}, "vec": [F, 0],
                       "role": "applied", "label": "F", "t1": r(t_push)},
                      {"kind": "arrow", "at": {"entity": body.id, "anchor": "bottom", "dx": 0.12, "dy": 0.04},
                       "vec": [-150, 0], "role": "friction", "label": "f_r", "t1": r(moving)},
                      {"kind": "arrow", "at": {"entity": body.id, "anchor": "top", "dx": -0.2, "dy": 0.16},
                       "samples": [[t, r(v * k, 1), 0] for t, v in spd], "role": "velocity", "label": "v",
                       "t0": 0.15 if phase == "steady" else None})
        if self.O and self.O[-1].get("t0") is None:
            self.O[-1].pop("t0", None)
        say = {"released": ["no push: friction slows it to a stop"], "rest": ["no push: no friction"]}.get(phase)
        if say is None:  # pushing: the words follow the solver's a, not the verb's manner
            a_ = res.facts["a"]
            say = ["F > f: the box speeds up"] if a_ > 1e-9 else ["F < f: the box slows down"] if a_ < -1e-9 \
                else ["steady push: F = f, so v stays the same"]
        self.card("Friction" if phase != "rest" else "At rest", res,
                  ["m", "mu_k", "F", "N", "f", "a", "a_stop", "t_stop"], say)
        self.backdrop = self.backdrop if self.g.place() else {"id": "room"}
        if ro.get("surface") in g.ents:
            self.done.add(ro["surface"])
        self.group(ids, period, [period * 0.15, period * 0.5, period * 0.85] if phase != "released" else
                   [lead * 0.5, lead + max(0.05, res.events.get("stop", 0.2)) * 0.5, period * 0.9])

    def _projectile(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        body = g.ents[ro["body"]]
        throws = self.acts_on(body.id, ("throw",))
        launcher = g.ents.get(ro.get("launcher", "")) if ro.get("launcher") else None
        thrower = g.ents.get(throws[-1].agent) if throws else (launcher if launcher and launcher.kind == "agent" else None)
        br = body.size[1] / 2
        spin = body.draw in ("book", "phone", "bag")
        if thrower:
            mx = 0.0
            st = ACT.throw(thrower.id, thrower.draw, mx, body.id, br)
            res = self.solve(law, {"h0": st["y"]})
            t0, x0 = st["t_release"], st["x"]
            self.ent(thrower, x=mx)
            self.ent(body)
            self.track(*st["tracks"])
            roll = []
            ids = [thrower.id, body.id]
        else:
            desk = launcher or next((g.ents[rl.b] for rl in g.rels if rl.a == body.id and rl.kind == "on"
                                     and rl.b in g.ents), None)
            top = desk.size[1] if desk else 1.0
            dw = desk.size[0] if desk else 1.0
            ctx = {"h0": top, "theta": 0.0}
            res = self.solve(law, ctx)
            v0 = res.facts["ux"]
            if desk:
                self.ent(desk, x=0.0)
                self.done.add(desk.id)
            self.ent(body)
            xs0, x0 = -dw / 2 + 0.15, dw / 2
            t0 = (x0 - xs0) / v0 if v0 > 0 else 1.0
            roll = [[r(t), r(xs0 + v0 * t), r(top), 0.0] for t in steps(0, t0, 1 / 12)]
            ids = [body.id] + ([desk.id] if desk else [])
        fly = res.samples["body"]
        tf = res.facts["tf"]
        rot0 = roll[-1][3] if roll else 0.0
        wspin = -540.0 if thrower and spin else 0.0  # a thrown book tumbles; a ball (turned about its bottom) does not
        path = roll + [[r(t0 + t), r(x0 + x), r(y), r(rot0 + wspin * t, 2)] for t, x, y in fly]
        land = path[-1]
        period = t0 + tf + 1.2
        path.append([r(period), land[1], land[2], land[3]])
        self.track({"id": body.id, "kind": "path", "samples": path, "events": [{"t": r(t0), "name": "release"}]})
        v0 = math.hypot(res.facts["ux"], res.facts["uy"]) or 1.0
        k = 140 / v0
        vel = [[r(t0 + t), r(vx * k, 1), r(vy * k, 1)] for t, vx, vy in res.samples["v"]]
        self.over({"kind": "path", "of": body.id, "upto": True, "every": 2, "role": "path", "t0": r(t0)},
                  {"kind": "arrow", "at": {"entity": body.id, "anchor": "centre"}, "samples": vel, "role": "velocity",
                   "label": "v", "t0": r(t0), "t1": r(t0 + tf)},
                  {"kind": "arrow", "at": {"entity": body.id, "anchor": "centre"}, "dy": -20, "vec": [0, -100],
                   "role": "weight", "label": "mg", "lx": 12, "ly": 10, "t0": r(t0), "t1": r(t0 + tf)})
        lines = ["a curve: it moves sideways and falls at once"] if thrower else ["it rolls off the edge and falls in a curve"]
        self.card("Projectile", res, ["v0", "theta", "h0", "g", "t_apex", "h_apex", "T", "R"], lines)
        self.group(ids, period, [t0 * 0.5, t0 + tf * 0.45, t0 + tf * 0.95])

    def _free_fall_compare(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        body = g.ents[ro["bodies"][0]]
        places = [place_key(g.ents[p].w) for p in ro["places"]]
        res = self.solve(law, {"places": places})
        v0 = res.facts["v0"]
        pre, post = 0.35, 0.45
        period = pre + max(res.events[f"land_{p}"] for p in places) + post + 0.8
        self.view, self.panes = "split", []
        h = catalog.cast()[body.draw[5:]]["height_m"] if body.draw.startswith("cast:") else 1.7
        for i, p in enumerate(places):
            pid = f"{body.id}{i}" if i else body.id
            air = res.events[f"land_{p}"]
            ground = p if p in ("moon", "mars") else None
            self.panes.append({"backdrop": {"id": "space", "state": {"ground": ground}} if ground else {"id": "outdoor"},
                               "frame": {"cx": 0, "cy": r((880 - VH / 2) / 175), "s": 175, "ease_ms": 0}})
            self.E[pid] = {"id": pid, "draw": body.draw, "pane": i, "xform": {"x": -0.2}}
            ys = [[r(pre + t), -0.2, y] for t, _, y in res.samples[p]]
            self.track({"id": pid, "kind": "path", "samples": [[0, -0.2, 0]] + ys + [[r(period), -0.2, 0]]},
                       *ACT.jump(pid, pre, air, post, pre))
            ink = "#ffffff" if p == "moon" else "#3a1d10"
            apex = res.samples[p][len(res.samples[p]) // 2][2]
            apex = max(y for _, _, y in res.samples[p])
            hn = res.nums.get(f"h_{p}")
            hp = self.num(hn, law.id) if hn else None
            gp = self.num(res.nums[f"g_{p}"], law.id)
            self.over({"kind": "line", "pane": i, "a": [-1.43, h], "b": [1.43, h], "color": ink, "opacity": "0.6"},
                      {"kind": "line", "pane": i, "a": [-1.43, r(apex + h)], "b": [1.43, r(apex + h)], "color": ink, "opacity": "0.6"},
                      {"kind": "dim", "pane": i, "a": [1.14, h], "b": [1.14, r(apex + h)], "arrows": True,
                       "text": f"h = {fmt(hn.v)} m" if hp else "h", "role": "velocity", "lx": 28, "ly": 14,
                       **({"value": hp} if hp else {})},
                      {"kind": "words", "pane": i, "screen": [40, 150], "text": g.ents[ro["places"][i]].w.title(),
                       "size": 40, "weight": 700, "color": ink, "halo": False},
                      {"kind": "words", "pane": i, "screen": [40, 198], "text": f"g = {fmt(res.nums[f'g_{p}'].v)} m/s²  ·  constant",
                       "size": 26, "halo": False, "color": "#D8DCE6" if p == "moon" else "#5a2a14", "value": gp})
        self.done.add(body.id)
        self.done |= set(ro["places"])
        rn = res.nums.get("ratio")
        if rn and rn.known and len(places) == 2:
            a, b = (g.ents[i].w.title() for i in ro["places"])
            self.over({"kind": "card", "pane": "all", "screen": [380, 928], "w": 840, "h": 56, "lines": [],
                       "title": f"same take-off speed:  h on the {a} / h on {b} = {fmt(rn.v)}  (computed)",
                       "title_size": 27, "values": [self.num(rn, law.id)]})
        self.keys = [r(pre * 0.6, 3)] + [r(pre + res.events[f"apex_{p}"], 3) for p in places]
        self.periods.append(period)
        self.busy |= {body.id}

    def _relative_motion(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        a, b = g.ents[ro["a"]], g.ents[ro["b"]]
        rain, man = (a, b) if a.draw == "rain" else (b, a)
        walk = next((x for x in self.acts_of(man.id, ("walk", "jog", "run"))), None)
        clip = ACT.clip_of(walk.verb if walk else "walk")
        stride = ACT.stride(clip, man.draw)
        rain_a = rain.id == a.id  # the givens follow the roles: va is a's speed, whichever a is
        down, fwd = (0.0, -1.0), (1.0, 0.0)
        res = self.solve(law, {"da": down if rain_a else fwd, "db": fwd if rain_a else down,
                               "va": 5.0 if rain_a else stride, "vb": stride if rain_a else 5.0,
                               "observer_is_a": ro["observer"] == ro["a"]})
        vr, vm = (res.facts["va"], res.facts["vb"]) if rain_a else (res.facts["vb"], res.facts["va"])
        if vm > 1e-6:
            rate = vm / stride
            period = ACT.whole(clip, 3.2 / vm, rate)
        else:  # standing still: no walk, a fixed shot
            rate, period, clip = 1.0, 3.0, "Idle_Loop"
        span = vm * period
        self.backdrop = {"id": self.backdrop["id"], "state": {"sky": "overcast"}} if self.backdrop["id"] == "outdoor" \
            else self.backdrop
        self.ent(rain, x=0.2, size=[7.6, 4.2]).update(state={"speed": r(min(vr, 9.0), 2), "drops": 90})
        self.ent(man)
        self.track({"id": man.id, "kind": "path", "samples": [[0, -2.9, 0], [r(period), r(-2.9 + span), 0]]},
                   ACT.clip(man.id, clip, 0, rate, True, vm > 1e-6))
        self.over({"kind": "arrow", "at": {"entity": man.id, "anchor": "head_top", "dx": -0.1, "dy": 0.25},
                   "vec": [150, 0], "role": "velocity", "label": "v_m", "lx": 10, "ly": 14})
        inset = g.view["mode"].startswith("inset_from")
        if inset:
            rel = res.facts["rel"]
            L = 230 / max(abs(rel[0]), abs(rel[1]), vr, vm)
            down, side = vr * L, vm * L
            c = {"kind": "card", "screen": [0, 0], "w": 470, "h": 420, "title": f"SEEN BY THE {man.w.upper()}",
                 "title_size": 19, "title_color": "#5d6672",
                 "vectors": [{"from": [330, 70], "to": [330, r(70 + down)], "role": "weight", "label": "v_r", "lx": 14, "ly": -60},
                             {"from": [330, r(70 + down)], "to": [r(330 - side), r(70 + down)], "role": "velocity",
                              "label": "−v_m", "dashed": True, "lx": -20, "ly": 46},
                             {"from": [330, 70], "to": [r(330 - side), r(70 + down)], "role": "applied", "label": "v_rm",
                              "lx": -120, "ly": -70}],
                 "lines": [], "rows": []}
            foot = {"kind": "words", "text": f"tan θ = v{SUB.format('m')} / v{SUB.format('r')}", "size": 26, "halo": False,
                    "card_dy": 380}
            self.cards.append(c)
            self.over(c, foot)
        self.card("Rain seen by the walker", res, ["va", "vb", "v_rel", "theta"], w=470,
                  names={"va": "v_r" if rain_a else "v_m", "vb": "v_m" if rain_a else "v_r"})
        self.group([man.id, rain.id], period, [period * 0.2, period * 0.5, period * 0.8])

    def _accelerated_motion(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        body = g.ents[ro["body"]]
        strobe = any(d["recipe"] == "strobe" for d in g.diagrams.values())
        res = self.solve(law, {"T": 4.0, "marks": 4})
        w = body.size[0]
        xs = res.samples["body"]
        x0 = -w / 2
        period = xs[-1][0] + 1.0
        path = [[t, r(x0 + x), 0] for t, x, _ in xs] + [[r(period), r(x0 + xs[-1][1]), 0]]
        self.ent(body)
        self.track({"id": body.id, "kind": "path", "samples": path})
        ids = [body.id]
        drv = next((x for x in g.actions.values() if x.obj == body.id and x.verb == "drive"), None)
        if drv and drv.agent in g.ents:
            self.ent(g.ents[drv.agent]).update(shadow=False)
            self.track({"id": drv.agent, "kind": "socket", "parent": body.id, "socket": "seat", "child_socket": "lap", "t0": 0},
                       ACT.clip(drv.agent, "Driving_Loop", 0, 1.0, True))
            ids.append(drv.agent)
        vmax = max(res.facts["v_end"], 1e-6)
        sp = [[t, r(150 * (res.facts["v_end"] * t / xs[-1][0]) / vmax if xs[-1][0] else 0, 1), 0] for t, _, _ in xs]
        self.over({"kind": "arrow", "at": {"entity": body.id, "anchor": "top", "dy": 0.25}, "samples": sp,
                   "role": "velocity", "label": "v", "t0": 0.3, "t1": r(xs[-1][0])})
        lines = []
        if strobe:
            mx = [x0 + w / 2 + x for x in res.facts["mark_x"]]  # the front bumper at equal times
            for i, (t, x) in enumerate(zip(res.facts["mark_t"], mx)):
                self.over({"kind": "line", "a": [r(x), 0.02], "b": [r(x), -0.45], "color": "#1f4e79", "opacity": "1",
                           "w": 5, "t0": r(t)})
            for i, (a, b) in enumerate(zip(mx, mx[1:])):
                self.over({"kind": "dim", "a": [r(a), -0.3], "b": [r(b), -0.3], "text": f"s_{i + 1}",
                           "t0": r(res.facts["mark_t"][i + 1]), "size": 30})
            gr = res.nums.get("gap_ratio")
            if gr and gr.known:
                pid = self.num(gr, law.id)
                ratio = " : ".join(fmt(x) for x in res.facts["gap_ratio"])
                lines = [f"equal times: the gaps go {ratio}  (computed)"]
                un = res.nums.get("u")
                rest = un is not None and un.known and abs(un.v) < 1e-12
                title = "From rest, speeding up" if rest else "Speeding up" if res.facts["v_end"] >= res.facts["u"] else "Slowing down"
                c = self.card(title, res, ["u", "a", "t", "v", "s"], lines)
                c["values"] = (c.get("values") or []) + [pid]
            else:
                self.card("Speeding up", res, ["u", "a", "t", "v", "s"], ["equal times: each gap is longer than the last"])
        else:
            self.card("Speeding up", res, ["u", "a", "t", "v", "s"])
        self.backdrop = self.backdrop if g.place() else {"id": "street"}
        self.group(ids, period, [xs[-1][0] * 0.3, xs[-1][0] * 0.7, xs[-1][0]])

    def _uniform_motion(self, law: LawRec) -> None:
        body = self.g.ents[law.roles["body"]]
        walk = body.draw.startswith("cast:")
        clip = "Walk_Loop"
        res = self.solve(law, {"v": ACT.stride(clip, body.draw) if walk else 1.0, "T": 4.0})
        xs = res.samples["body"]
        self.ent(body)
        self.track({"id": body.id, "kind": "path", "samples": [[t, r(x - xs[-1][1] / 2), 0] for t, x, _ in xs]})
        if walk:
            self.track(ACT.clip(body.id, clip, 0, res.facts["v"] / ACT.stride(clip, body.draw), True, True))
        self.over({"kind": "arrow", "at": {"entity": body.id, "anchor": "top" if not walk else "head_top", "dy": 0.25},
                   "vec": [150, 0], "role": "velocity", "label": "v"})
        self.card("Steady speed", res, ["v", "t", "d"])
        self.group([body.id], xs[-1][0], [0.5, xs[-1][0] / 2, xs[-1][0] - 0.2])

    def _moments(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        plank, piv = g.ents[ro["beam"]], g.ents[ro["pivot"]]
        loads = [g.ents[i] for i in ro["loads"]]
        top = piv.size[1] if piv.draw == "fulcrum" else 0.62
        mdef = [25.0 if l.draw.startswith("cast:") and catalog.cast()[l.draw[5:]]["child"] else 60.0 for l in loads]
        balance = balance_asked([t for _, t in g.lines])
        res = self.solve(law, {"m_default": mdef, "balance": balance, "d1": 0.95, "d2": 2.45, "top": top, "half": 3.0})
        d1, d2 = res.facts["d1"], res.facts["d2"]
        L = max(6.0, 2 * max(d1, d2) + 0.9)
        res = self.solve(law, {"m_default": mdef, "balance": balance, "d1": 0.95, "d2": 2.45, "top": top, "half": L / 2})
        tilt = res.samples["beam"]
        period = 2 * math.pi / 1.2
        self.ent(piv, size=[0.76, r(top)])
        pe = self.ent(plank, "seesaw", y=r(top), size=[r(L), 0.5])
        pe["state"] = {"handles": []}
        self.track({"id": plank.id, "kind": "path", "samples": [[t, 0, r(top), a] for t, a in tilt]
                    + [[r(period), 0, r(top), tilt[-1][1]]]})
        for i, (who, sx, d) in enumerate(((loads[0], -d1, 1), (loads[1], d2, -1))):
            e = self.ent(who, dir=d)
            e["shadow"] = False
            if who.draw.startswith("cast:"):
                gy = 0.17 * ACT.h(who.draw)
                hx = sx + d * 0.85 * ACT.sit_reach(who.draw, gy)
                pe["state"]["handles"].append([r(hx), r(0.08 + gy)])
                self.track(ACT.clip(who.id, "Sitting_Idle_Loop", 0, 1.0, True, t_offset=r(i * 0.7)),
                           {"id": who.id, "kind": "socket", "parent": plank.id, "socket": "top", "offset": [r(sx), 0],
                            "child_socket": "lap", "t0": 0},
                           {"id": who.id, "kind": "ik", "hand": "r", "target": {"entity": plank.id, "anchor": "top", "dx": r(hx), "dy": r(gy)}},
                           {"id": who.id, "kind": "ik", "hand": "l", "target": {"entity": plank.id, "anchor": "top", "dx": r(hx - d * 0.03), "dy": r(gy)}})
            else:
                self.track({"id": who.id, "kind": "socket", "parent": plank.id, "socket": "top", "offset": [r(sx), 0], "t0": 0})
        dy = -0.28
        Wmax = max(res.facts["W"])
        dims = []
        for i, (sx, sym) in enumerate(((-d1, "d1"), (d2, "d2"))):
            n = res.nums[sym]
            pid = self.num(n, law.id)
            o = {"kind": "dim", "a": {"entity": plank.id, "anchor": "top", "dy": dy},
                 "b": {"entity": plank.id, "anchor": "top", "dx": r(sx), "dy": dy},
                 "text": f"d{'₁₂'[i]} = {fmt(n.v)} m" if pid else f"d_{i + 1}"}
            if pid:
                o["value"] = pid
            dims.append(o)
        self.over(*dims)
        for i, (sx, W, side) in enumerate(((-d1, res.facts["W"][0], -1), (d2, res.facts["W"][1], 1))):
            self.over({"kind": "arrow", "at": {"entity": plank.id, "anchor": "top", "dx": r(sx)}, "dx": 40 * side, "dy": 10,
                       "vec": [0, r(-160 * W / Wmax, 1)], "role": "weight", "label": f"W_{i + 1}",
                       "lx": -60 if side < 0 else 14, "ly": 0})
        f = res.facts
        say = ["balanced: the moments are equal"] if f["balanced"] else \
            [f"not balanced: the {'right' if f['turns'] == 'right_down' else 'left'} side goes down"]
        self.card("balanced when the moments are equal:" if f["balanced"] else "moment = force × distance", res,
                  ["W1", "d1", "W2", "d2", "M1", "M2"], say + ["moment = force × distance from the pivot"],
                  eq=f"W{SUB.format(1)} × d{SUB.format(1)} = W{SUB.format(2)} × d{SUB.format(2)}")
        self.group([piv.id, plank.id] + [l.id for l in loads], period, [period * 0.1, period * 0.25, period * 0.75])

    def _pendulum_energy(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        frame_e, bob = g.ents[ro["pivot"]], g.ents[ro["bob"]]
        sitter = bob if bob.draw.startswith("cast:") else next(
            (g.ents[rl.a] for rl in g.rels if rl.kind == "sitting_on" and rl.b == bob.id and rl.a in g.ents), None)
        res = self.solve(law, {"L": 2.3})
        L = res.facts["L"]
        top = L + 0.75
        th0 = math.radians(res.facts["theta0"])
        period = res.facts["T"]
        seat = next((e for e in g.ents.values() if e.draw == "swing_seat"), None)
        sid = seat.id if seat else f"{frame_e.id}_seat"
        self.ent(frame_e, "swing", size=[3.0, r(top)])
        self.E[sid] = {"id": sid, "draw": "swing_seat", "xform": {"y": r(top), "size": [0.6, r(L - 0.05)]}}
        self.done.add(sid)
        self.track({"id": sid, "kind": "path", "samples": [[t, 0, r(top), a] for t, a in res.samples["theta"]]})
        ids = [frame_e.id, sid]
        if sitter:
            self.ent(sitter).update(shadow=False)
            lap_dx = ACT.lap_dx("Sitting_Idle_Loop", 0.4, sitter.draw)
            self.track(ACT.clip(sitter.id, "Sitting_Idle_Loop", 0, 0.0, True, t_offset=0.4),
                       {"id": sitter.id, "kind": "socket", "parent": sid, "socket": "seat", "offset": [r(lap_dx), 0],
                        "child_socket": "lap", "t0": 0},
                       {"id": sitter.id, "kind": "ik", "hand": "r", "target": {"entity": sid, "anchor": "seat", "dx": 0.02, "dy": 0.55}},
                       {"id": sitter.id, "kind": "ik", "hand": "l", "target": {"entity": sid, "anchor": "seat", "dx": 0.0, "dy": 0.62}})
            ids.append(sitter.id)
        yl, yh = top - L, top - L * math.cos(th0)
        arc = [[r(L * math.sin(th0 * k)), r(top - L * math.cos(th0 * k))] for k in [i / 20 - 1 for i in range(41)]]
        k = 70
        vel = []
        for (t, a), (_, sp) in zip(res.samples["theta"], res.samples["speed"]):
            # the velocity is along the arc, toward the swing's motion (sign from dθ/dt)
            nxt = _theta_at(res.samples["theta"], t + 0.01)
            sgn = 1 if nxt > a else -1
            ar = math.radians(a)
            vel.append([t, r(sgn * sp * k * math.cos(ar), 1), r(sgn * sp * k * math.sin(ar), 1)])
        hp = self.row(res, "h")
        self.over({"kind": "path", "pts": arc, "style": "dashed", "role": "path"},
                  {"kind": "line", "a": [1.0, r(yl)], "b": [2.6, r(yl)]},
                  {"kind": "line", "a": [1.2, r(yh)], "b": [2.6, r(yh)]},
                  {"kind": "dim", "a": [2.45, r(yl)], "b": [2.45, r(yh)], "arrows": True, "text": "h", "role": "muted",
                   "lx": 26, "ly": 14},
                  {"kind": "arrow", "at": {"entity": sid, "anchor": "seat"}, "dy": -30, "samples": vel, "role": "velocity",
                   "label": "v", "lx": 10, "ly": -8},
                  {"kind": "words", "at": [r(-L * math.sin(th0) - 1.2), r(yh + 0.25)], "text": "highest: all PE", "size": 24, "weight": 600},
                  {"kind": "words", "at": [-0.6, r(yl - 0.65)], "text": "lowest: all KE", "size": 24, "weight": 600})
        if any(d["recipe"] == "energy_bars" for d in g.diagrams.values()):
            e = {"kind": "energy", "screen": [0, 0], "w": 470, "samples": res.samples["energy"], "title": "energy (no friction)",
                 "note": "PE + KE stays the same", "h": 250}
            self.cards.append(e)
            self.over(e)
        self.card("Swing", res, ["L", "theta0", "T", "h", "v_max"]) if any(
            res.nums.get(s) and res.nums[s].known for s in ("L", "theta0")) else None
        self.group(ids, period, [0.0, period * 0.25, period * 0.4])

    def _apparent_weight(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        person, lift = g.ents[ro["person"]], g.ents[ro["lift"]]
        mv = next((a for a in self.acts_of(lift.id, ("move",)) if a.active), None)
        sign = -1 if mv and mv.dir == "down" else 1
        res = self.solve(law, {"sign": sign, "T": 1.6})
        ys = res.samples["lift"]
        period = ys[-1][0] + 1.0
        self.ent(lift, x=0.0)
        self.track({"id": lift.id, "kind": "path", "samples": [[t, 0, y] for t, _, y in ys] + [[r(period), 0, ys[-1][2]]]})
        scale = next((g.ents[rl.b] for rl in g.rels if rl.a == person.id and rl.kind == "on" and rl.b in g.ents
                      and g.ents[rl.b].draw == "scale"), None)
        ids = [lift.id, person.id]
        if scale:
            self.ent(scale)
            self.track({"id": scale.id, "kind": "socket", "parent": lift.id, "socket": "floor", "offset": [0.1, 0], "t0": 0})
            ids.append(scale.id)
        self.ent(person, dir=-1)
        self.track({"id": person.id, "kind": "socket", "parent": scale.id if scale else lift.id,
                    "socket": "top" if scale else "floor", "offset": [0.0 if scale else 0.1, 0], "t0": 0},
                   ACT.clip(person.id, "Idle_Loop", 0, 1.0, True))
        f = res.facts
        Nmax = max(f["N"], f["W"])
        base = {"entity": scale.id if scale else lift.id, "anchor": "top" if scale else "floor"}
        hp = ACT.h(person.draw)
        self.over({"kind": "arrow", "at": {**base, "dx": 0.42}, "vec": [0, r(170 * f["N"] / Nmax, 1)], "role": "applied",
                   "label": "N", "lx": 10, "ly": 0},
                  {"kind": "arrow", "at": {**base, "dx": -0.42, "dy": r(hp * 0.55)}, "vec": [0, r(-170 * f["W"] / Nmax, 1)],
                   "role": "weight", "label": "mg", "lx": -70, "ly": 30},
                  {"kind": "arrow", "at": {"entity": lift.id, "anchor": "top", "dx": 0.95, "dy": -0.3},
                   "vec": [0, 110 * sign], "role": "velocity", "label": "a", "lx": 10, "ly": 0})
        say = ["N > mg: she feels heavier" if f["heavier"] else "N < mg: she feels lighter"]
        self.card("In a lift speeding up" if sign > 0 else "In a lift", res, ["m", "a", "g", "W", "N"], say)
        self.backdrop = self.backdrop if g.place() else {"id": "room"}
        self.group(ids, period, [0.2, ys[-1][0] * 0.6, ys[-1][0]])

    def _buoyancy(self, law: LawRec) -> None:
        g, ro = self.g, law.roles
        body, fluid = g.ents[ro["body"]], g.ents[ro["fluid"]]
        fw = fluid.w.lower()
        key = "rho_sea_water" if "sea" in fw or "ocean" in fw else "rho_water" if "water" in fw else None
        res = self.solve(law, {"rho_key": key})
        self.backdrop = {"id": "pool"}
        self.ent(body)
        ys = res.samples["body"]
        self.track({"id": body.id, "kind": "path", "samples": [[t, 0, y] for t, _, y in ys]})
        self.done.add(fluid.id)
        self.card("Floats" if res.facts["floats"] else "Sinks", res, ["m", "V", "rho", "rho_body", "W", "U", "frac"],
                  ["it floats: the upthrust equals its weight" if res.facts["floats"] else "it sinks: the upthrust is less than its weight"])
        self.group([body.id], ys[-1][0] + 1.0, [0.2, 1.0, 2.5])

    # ---------- action stagers ----------
    def _actions(self) -> None:
        g = self.g
        pulls = [a for a in g.actions.values() if a.active and a.verb == "pull" and a.agent not in self.done]
        if pulls and len(pulls) >= 2:
            self._tug(pulls)
        for a in sorted(g.actions.values(), key=lambda a: a.seq):
            if a.agent in self.done or a.agent not in g.ents:
                continue
            if a.verb in ("carry", "put_down", "pick_up") and a.obj in g.ents:
                self._carry(a.agent)
            elif a.verb in ("walk", "jog", "run") and a.active:
                self._walk(a)
        for a in sorted(g.actions.values(), key=lambda a: a.seq):  # what is left: stand and act in place
            if a.agent not in self.done and a.agent in g.ents and a.active:
                self._in_place(a)

    def _tug(self, pulls: list[Action]) -> None:
        g = self.g
        rope_id = pulls[0].obj
        rope = g.ents[rope_id]
        ry, lean, clip = 0.95, 30, "Walk_Loop"
        left = [a for a in pulls if a.dir == "left"]
        right = [a for a in pulls if a.dir != "left"]
        hard_l, hard_r = any(a.manner == "hard" for a in left), any(a.manner == "hard" for a in right)
        winner = -1 if (hard_l and not hard_r) or (hard_l == hard_r and len(left) > len(right)) else \
            1 if (hard_r and not hard_l) or (hard_l == hard_r and len(right) > len(left)) else 0
        vr = 0.2 if winner else 0.0
        self.illustrative = True
        period = 7.5
        ts = steps(0, period, 1 / 12)
        c = [(t, winner * vr * t) for t in ts]
        self.E[rope_id] = {"id": rope_id, "draw": "rope", "xform": {"y": r(ry - 0.025), "size": [7.2, 0.05]}, "state": {"marker": True}}
        self.done.add(rope_id)
        self.track({"id": rope_id, "kind": "path", "samples": [[r(t), r(x), r(ry - 0.025)] for t, x in c]})
        ids = [rope_id]
        team = [(a, -1.0 - 0.9 * i) for i, a in enumerate(left)] + [(a, 1.0 + 0.9 * i) for i, a in enumerate(right)]
        dur = ACT.dur(clip)
        for i, (a, off) in enumerate(team):
            who = g.ents[a.agent]
            d = 1 if off < 0 else -1
            self.ent(who, dir=d)
            self.track({"id": who.id, "kind": "path", "samples": [[r(t), r(x + off), 0] for t, x in c]})
            win = (off < 0 and winner < 0) or (off > 0 and winner > 0)
            self.track(ACT.clip(who.id, clip, 0, r(-vr / ACT.stride(clip, who.draw)) if win else 0.0, True, win,
                                lean=lean, t_offset=r(dur * (i * 0.37 % 1) if win else ACT.brace_offset(clip))))
            for hand, kk in (("r", ACT.reach(clip, who.draw, ry, "r", lean=lean)),
                             ("l", ACT.reach(clip, who.draw, ry, "l", frac=0.85, lean=lean))):
                self.track({"id": who.id, "kind": "ik", "hand": hand, "target": {"entity": rope_id, "anchor": "centre", "dx": r(off + d * kk)}})
            ids.append(who.id)
        # the teams' pulls: the winner's arrow longer (no numbers: illustrative)
        fl, fr_ = (240, 150) if winner < 0 else (150, 240) if winner > 0 else (190, 190)
        self.over({"kind": "line", "a": [0, 0.02], "b": [0, -0.4], "color": "#ffffff", "opacity": "1", "w": 5},
                  {"kind": "arrow", "at": {"entity": rope_id, "anchor": "centre", "dy": 1.4}, "dx": -20, "vec": [-fl, 0],
                   "role": "applied", "label": "F_L", "lx": -60, "ly": -14},
                  {"kind": "arrow", "at": {"entity": rope_id, "anchor": "centre", "dy": 1.4}, "dx": 20, "vec": [fr_, 0],
                   "role": "applied", "label": "F_R", "lx": 10, "ly": -14})
        if winner:
            self.over({"kind": "arrow", "at": {"entity": rope_id, "anchor": "centre", "dy": 1.0}, "dx": -10 * -winner,
                       "vec": [100 * winner, 0], "role": "friction", "label": "F_net", "lx": -110 if winner < 0 else 10, "ly": 44})
        say = ["the left team pulls harder: the rope moves left" if winner < 0 else
               "the right team pulls harder: the rope moves right" if winner > 0 else "equal pulls: the rope stays"]
        self.card("Tug of war", None, [], say)
        self.group(ids, period, [1.0, 4.5, 7.4])

    def _carry(self, agent: str) -> None:
        g = self.g
        who = g.ents[agent]
        acts = self.acts_of(agent, ("carry", "put_down", "pick_up"))
        obj = g.ents[acts[-1].obj]
        put = next((a for a in acts if a.verb == "put_down"), None)
        dest = g.rel(obj.id, "on")
        table = g.ents.get(dest.b) if dest and put else None
        walk, putc = "Walk_Carry_Loop", "PickUp_Table"
        bw, bh = min(0.5, obj.size[0]), min(0.4, obj.size[1]) if obj.size[1] > 0.1 else obj.size[1]
        off = (0.12, 0.17)
        self.ent(obj, size=[r(bw), r(bh)])
        v = ACT.stride(walk, who.draw)
        if table:
            x0, stop = -2.6, 0.2
            t_walk = (stop - x0) / v
            tc = ACT.event_t(putc, "contact")
            t_let = t_walk + tc
            pr = ACT.palm(putc, tc, "r", stop, who.draw, loop=False)
            pl = ACT.palm(putc, tc, "l", stop, who.draw, loop=False)
            bxm, bym = (pr[0] + pl[0]) / 2 + off[0], (pr[1] + pl[1]) / 2 + off[1]
            top = bym - bh / 2  # the table top is where the clip's hands put the box down
            period = t_let + 2.2
            self.E = {table.id: {"id": table.id, "draw": table.draw, "xform": {"x": r(bxm - 0.35 + 0.75), "size": [1.5, r(top)]}},
                      **self.E}
            self.done.add(table.id)
            self.ent(who)
            self.E[obj.id] = self.E.pop(obj.id)  # in front of the woman (held between her and her near arm)
            self.track({"id": who.id, "kind": "path", "samples": [[0, x0, 0], [r(t_walk), stop, 0], [r(period), stop, 0]]},
                       ACT.clip(who.id, walk, 0, 1.0, True, True),
                       ACT.clip(who.id, putc, t_walk, 1.0, False, blend=0.25, events=[{"t": r(t_let), "name": "contact"}]),
                       ACT.clip(who.id, "Idle_Loop", t_let, 1.0, True, blend=0.5),
                       {"id": obj.id, "kind": "socket", "parent": who.id, "socket": "hands", "child_socket": "centre",
                        "offset": list(off), "t0": 0, "t1": r(t_let)})
            self.over({"kind": "arrow", "at": {"entity": who.id, "anchor": "head_top", "dx": -0.1, "dy": 0.22}, "vec": [150, 0],
                       "role": "velocity", "label": "v", "t1": r(t_walk)})
            keys = [t_walk * 0.4, t_walk + tc * 0.5, t_let + 1.0]
            ids = [who.id, obj.id, table.id]
        else:
            period = ACT.whole(walk, 3.0 / v)
            self.ent(who)
            self.E[obj.id] = self.E.pop(obj.id)
            self.track({"id": who.id, "kind": "path", "samples": [[0, -1.8, 0], [r(period), r(-1.8 + v * period), 0]]},
                       ACT.clip(who.id, walk, 0, 1.0, True, True),
                       {"id": obj.id, "kind": "socket", "parent": who.id, "socket": "hands", "child_socket": "centre",
                        "offset": list(off), "t0": 0})
            self.over({"kind": "arrow", "at": {"entity": who.id, "anchor": "head_top", "dx": -0.1, "dy": 0.22}, "vec": [150, 0],
                       "role": "velocity", "label": "v"})
            keys = [period * 0.2, period * 0.5, period * 0.8]
            ids = [who.id, obj.id]
        self.backdrop = self.backdrop if g.place() else {"id": "room"}
        self.group(ids, period, keys)

    def _walk(self, a: Action) -> None:
        g = self.g
        who = g.ents[a.agent]
        d = self.dirn(a)
        if who.kind == "animal":
            v, clip = (1.1 if a.verb == "walk" else 3.0), None
        else:
            clip = ACT.clip_of(a.verb)
            v = ACT.stride(clip, who.draw)
        period = ACT.whole(clip, 3.4 / v) if clip else 3.4 / v
        span = v * period
        x0 = -span / 2 - 0.4 if d > 0 else span / 2 + 0.4
        self.ent(who, dir=d if d < 0 else None)
        self.track({"id": who.id, "kind": "path", "samples": [[0, r(x0), 0], [r(period), r(x0 + d * span), 0]]})
        if clip:
            self.track(ACT.clip(who.id, clip, 0, 1.0, True, True))
        ids = [who.id]
        # who goes with it: an animal near / with the walker, or walking too, keeps its pace beside it
        for rl in g.rels:
            if rl.b == who.id and rl.kind in ("near", "attached_to", "in_front_of", "at") and rl.a in g.ents \
                    and rl.a not in self.done:
                f = g.ents[rl.a]
                ahead = 0.95 if f.kind == "animal" else -0.7
                self.ent(f, dir=d if d < 0 else None)
                self.track({"id": f.id, "kind": "path", "samples": [[0, r(x0 + d * ahead), 0],
                                                                     [r(period), r(x0 + d * (ahead + span)), 0]]})
                if f.draw.startswith("cast:"):
                    self.track(ACT.clip(f.id, "Walk_Loop", 0, v / ACT.stride("Walk_Loop", f.draw), True, True))
                ids.append(f.id)
        self.over({"kind": "arrow", "at": {"entity": who.id, "anchor": "head_top" if who.kind == "agent" else "top",
                                           "dx": -0.1 * d, "dy": 0.25}, "vec": [150 * d, 0], "role": "velocity",
                   "label": "v", "lx": 10 if d > 0 else -40, "ly": 14})
        self.group(ids, period, [period * 0.2, period * 0.5, period * 0.8])

    def _in_place(self, a: Action) -> None:
        g = self.g
        who = g.ents[a.agent]
        if who.kind != "agent":
            self.ent(who)
            self.group([who.id], 3.0, [0.5, 1.5, 2.5])
            return
        clip = ACT.clip_of(a.verb)
        seat = g.rel(who.id, "sitting_on")
        self.ent(who)
        if seat and seat.b in g.ents:
            s = g.ents[seat.b]
            self.ent(s, x=0.0)
            self.track({"id": who.id, "kind": "socket", "parent": s.id, "socket": "seat", "child_socket": "lap", "t0": 0},
                       ACT.clip(who.id, "Sitting_Idle_Loop", 0, 1.0, True))
            self.E[who.id] = self.E.pop(who.id)
            self.group([who.id, s.id], 3.0, [0.5, 1.5, 2.5])
            return
        self.track(ACT.clip(who.id, clip, 0, 1.0, None))
        dur = ACT.dur(clip)
        self.group([who.id], max(dur, 2.0), [dur * 0.2, dur * 0.5, dur * 0.8])

    def _static(self) -> None:
        """Entities no stager placed: on / under / near / behind a placed one, else a group of their own."""
        g = self.g
        for e in g.visible():
            if e.id in self.done:
                continue
            rel = g.rel(e.id)
            if rel and rel.b in self.E and rel.kind in ("on", "near", "behind", "left_of", "right_of", "in_front_of", "at"):
                tgt = self.E[rel.b]
                tx = (tgt.get("xform") or {}).get("x", 0.0)
                tw, th = director.size_of(tgt)
                w, h = e.size
                x = {"left_of": tx - tw / 2 - w / 2 - 0.4, "right_of": tx + tw / 2 + w / 2 + 0.4,
                     "near": tx + tw / 2 + w / 2 + 0.3}.get(rel.kind, tx)
                y = th if rel.kind == "on" else None
                self.ent(e, x=r(x), y=r(y) if y else None)
                gi = next((k for k, gr in enumerate(self.groups) if rel.b in gr.ids), None)
                if gi is not None:
                    self.groups[gi].ids.append(e.id)
                continue
            self.ent(e)
            if e.kind == "agent":
                self.track(ACT.clip(e.id, "Idle_Loop", 0, 1.0, True))
            self.groups.append(director.Group([e.id]))
            self.group_ov.append([])
            self.periods.append(3.0)

    # ---------- director ----------
    def finish(self) -> dict:
        g = self.g
        period = max(self.periods) if self.periods else 3.0
        keys = self.keys or [period * 0.2, period * 0.5, period * 0.8]
        line = g.lines[-1][1] if g.lines else ""
        if self.illustrative:
            self.badges.append("Illustrative")
        if self.view == "split":
            patch = {"rev": self.rev, "view": "split", "panes": self.panes}
        else:
            patch = {"rev": self.rev, "view": "side", "backdrop": self.backdrop}
        patch.update(entities=list(self.E.values()), tracks=self.T, overlays=self.O, period=r(period, 4),
                     keyframes=[r(k, 3) for k in keys])
        if self.view != "split":
            self._layout(patch)
            self._frame(patch, line)
            self._labels(patch)
        dim = director.dimmed(g, self.busy)
        for e in patch["entities"]:
            if e["id"] in dim:
                e.setdefault("xform", {})["dim"] = True
        prev_ids = {e["id"] for e in (self.prev or {}).get("entities", [])}
        new = [e["id"] for e in patch["entities"] if e["id"] not in prev_ids]
        for i, ms in director.stagger(new).items():
            next(e for e in patch["entities"] if e["id"] == i)["enter_ms"] = ms
        patch["badges"] = self.badges
        patch["numbers"] = dict(sorted(self.N.items()))
        patch["laws"] = {k: {"name": v.name, "illustrative": v.illustrative, "events": v.events,
                             "facts": _plain(v.facts)} for k, v in self.results.items()}
        check_numbers(patch)
        return patch

    def _layout(self, patch: dict) -> None:
        if len(self.groups) < 2:
            return
        w = director.Where(patch, self._regions())
        for gr in self.groups:
            bs = [w.box(i, 0.0) for i in gr.ids if i in w.ents]
            if not bs:
                continue
            b = director.union(bs)
            gr.x0, gr.x1, gr.top = b[0], b[2], max(0.3, b[3])
        groups, nts = director.layout(self.groups)
        if nts:
            self.badges.append("Not to scale")
        for gr, ov in zip(groups, self.group_ov):
            if gr.dx or gr.scale != 1.0:
                _shift(patch, set(gr.ids), gr.dx, gr.scale, [o for o in ov if o.get("kind") != "card"])

    def _regions(self) -> dict:
        bd = catalog.backdrop(self.backdrop.get("id", "outdoor")) or {}
        return bd.get("regions", {})

    def _frame(self, patch: dict, line: str) -> None:
        g = self.g
        w = director.Where(patch, self._regions())
        times = w.times(24)
        ids = [e["id"] for e in patch["entities"]]
        if g.frame["shot"] == "focus" and g.frame["ids"]:
            ids = [i for i in g.frame["ids"] if i in w.ents] or ids
        boxes = [_room(w.box(i, t)) for i in ids for t in times]
        boxes += [_world_overlay_box(o) for o in patch["overlays"] if _world_overlay_box(o)]
        top_room = 90 if line else 0
        fr = director.fit(boxes, self.nogo, top_room=top_room, ease_ms=600 if self.prev else 0)
        # cards: the top corner clear of every figure at every time, else the scene makes room beside the card
        figs = [[fr.screen_box(_room(w.box(i, t))) for i in w.ents] for t in times]
        y = 120
        for c in self.cards:
            ch = c.get("h") or (30 + (44 if c.get("title") else 0) + len(c.get("rows", [])) * 54
                                + len(c.get("lines", [])) * 40 + (60 if c.get("eq") else 0))
            c["h"] = ch
            spot = None
            for x in (VW - c["w"] - 40, 40):
                cb = [x, y, x + c["w"], y + ch]
                if not any(director.overlaps(cb, f) for fs in figs for f in fs) and not any(
                        director.overlaps(cb, n) for n in self.nogo):
                    spot = cb
                    break
            if spot is None:
                cb = [VW - c["w"] - 40, y, VW - 40, y + ch]
                fr = director.fit(boxes, self.nogo + [[cb[0] - 20, 0, VW, VH]], top_room=top_room, ease_ms=fr.ease_ms)
                figs = [[fr.screen_box(_room(w.box(i, t))) for i in w.ents] for t in times]
                spot = cb
            c["screen"] = [r(spot[0], 1), r(spot[1], 1)]
            y = spot[3] + 24
        for o in patch["overlays"]:
            if "card_dy" in o:
                c = next(c for c in self.cards if c.get("vectors"))
                o["screen"] = [r(c["screen"][0] + 24, 1), r(c["screen"][1] + o.pop("card_dy"), 1)]
        patch["frame"] = fr.d()
        if line:
            patch["overlays"].insert(0, {"kind": "words", "screen": [48, 66], "text": f"“{line}”", "size": 30,
                                         "color": "#5d6672", "weight": 400, "said": g.current_line()})
        self._fr, self._where, self._times = fr, w, times

    def _labels(self, patch: dict) -> None:
        g = self.g
        labs = [e for e in g.visible() if e.label and e.id in self._where.ents]
        if not labs:
            return
        fr, w, times = self._fr, self._where, self._times
        figs = [[fr.screen_box(w.box(i, t)) for i in w.ents] for t in times]
        others = [[c["screen"][0], c["screen"][1], c["screen"][0] + c["w"], c["screen"][1] + c["h"]] for c in self.cards]
        req = []
        for e in labs:
            at = []
            for t in times:
                b = fr.screen_box(w.box(e.id, t))
                at.append([(b[0] + b[2]) / 2, b[1] - 14])
            req.append({"text": e.label, "at": at})
        placed = director.place_labels(req, figs, others)
        for e, p in zip(labs, placed):
            # a person: above the head; anything else: its height above its origin (animals have no `top` socket)
            # (its drawn height: the far row's 0.6 and a layout enlargement included)
            b = w.box(e.id, 0.0)
            at = {"entity": e.id, "anchor": "head_top"} if e.draw.startswith("cast:") else \
                {"entity": e.id, "anchor": "bottom", "dy": r(b[3] - b[1])}
            # the teacher's own words (said_words checked them): `said`, so a digit in them needs no record
            patch["overlays"].append({"kind": "words", "at": at, "dx": p["dx"], "dy": 14 - p["dy"], "text": e.label,
                                      "size": 34, "anchor": "middle", "weight": 600, "said": "label"})
        patch["label_boxes"] = [p["boxes"] for p in placed]


HEADROOM = 0.45  # metres kept above a figure for its arrows and labels (v above a box, a above a lift)


def _room(b: list[float]) -> list[float]:
    return [b[0], b[1], b[2], b[3] + HEADROOM]


_BALANCE = re.compile(r"\bbalanc", re.I)
_NOT_BALANCE = re.compile(r"\bunbalanc|\b(?:not|never|n't|no longer|won't|cannot|can't)\b[^.?!]*\bbalanc", re.I)


def balance_asked(lines: list[str]) -> bool:
    """The latest line about balancing decides: "where must she sit to balance?" yes; "it does not balance" no."""
    for t in reversed(lines):
        if _BALANCE.search(t):
            return not _NOT_BALANCE.search(t)
    return False


def _theta_at(samples: list[list[float]], t: float) -> float:
    T = samples[-1][0]
    t = t % T if T else t
    for a, b in zip(samples, samples[1:]):
        if t <= b[0]:
            k = (t - a[0]) / ((b[0] - a[0]) or 1)
            return a[1] + (b[1] - a[1]) * k
    return samples[-1][1]


def _plain(x: Any) -> Any:
    if isinstance(x, float):
        return r(x, 6)
    if isinstance(x, (list, tuple)):
        return [_plain(v) for v in x]
    if isinstance(x, dict):
        return {k: _plain(v) for k, v in x.items()}
    return x


def _world_overlay_box(o: dict) -> Optional[list[float]]:
    """World points of an overlay (dimension lines, arcs) that the frame must show."""
    pts = []
    for k in ("a", "b", "at"):
        if isinstance(o.get(k), list) and len(o[k]) == 2 and all(isinstance(v, (int, float)) for v in o[k]):
            pts.append(o[k])
    if isinstance(o.get("pts"), list):
        pts += o["pts"]
    if not pts or o.get("pane") is not None:
        return None
    return [min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts)]


def _shift(patch: dict, ids: set[str], dx: float, k: float, overlays: list[dict] = ()) -> None:
    """Move (and scale about x = 0) one group: its entities, their paths, and the group's world-point overlays."""
    sh = lambda p: [r(p[0] * k + dx), r(p[1] * k)]  # noqa: E731
    for o in overlays:
        for key in ("a", "b", "at"):
            if isinstance(o.get(key), list) and len(o[key]) == 2:
                o[key] = sh(o[key])
        if isinstance(o.get("pts"), list):
            o["pts"] = [sh(q) for q in o["pts"]]
    for e in patch["entities"]:
        if e["id"] in ids:
            xf = e.setdefault("xform", {})
            xf["x"] = r(xf.get("x", 0.0) * k + dx)
            if "y" in xf:
                xf["y"] = r(xf["y"] * k)
            if k != 1.0:
                xf["scale"] = r(xf.get("scale", 1.0) * k)
    for t in patch["tracks"]:
        if t["id"] in ids and t["kind"] == "path":
            t["samples"] = [[s[0], r(s[1] * k + dx), r(s[2] * k)] + s[3:] for s in t["samples"]]


_DIGIT = re.compile(r"\d")


def check_numbers(patch: dict) -> None:
    """Contract §2: the stage refuses a number without a provenance record. Every overlay text with a digit must
    carry value / values naming records in patch.numbers, or be the teacher's own line (`said`)."""
    nums = patch.get("numbers", {})
    for o in patch["overlays"]:
        if o.get("said"):
            continue
        texts = [o.get(k) for k in ("text", "label", "title", "eq") if isinstance(o.get(k), str)]
        texts += [x for x in o.get("lines", []) if isinstance(x, str)]
        texts += [" ".join(x) for x in o.get("rows", [])]
        texts = [re.sub(r"<[^>]+>", "", t) for t in texts]  # tspans (subscripts) are not numbers
        texts = [re.sub(r"[A-Za-zθμ]_?\d\b", "", t) for t in texts]  # symbols with a subscript digit (W_1, s_2, d1)
        if any(_DIGIT.search(t) for t in texts):
            ids = ([o["value"]] if o.get("value") else []) + list(o.get("values", []))
            if not ids or any(i not in nums for i in ids):
                raise ValueError(f"overlay prints a number without provenance: {texts}")


def build(g: Graph, prev: Optional[dict] = None, nogo: Optional[list] = None, rev: int = 1) -> dict:
    return Build(g, prev, nogo, rev).run()


def diff(a: Optional[dict], b: dict) -> dict:
    """The patch b as a change on a: entities added / changed / removed by id and their order (the draw order is
    the z order); the tracks of the ids whose tracks changed and the order of track ids; every other top-level key
    that differs (a live stage applies a diff to its last patch)."""
    if a is None:
        return {"rev": b["rev"], "full": b}
    ea, eb = {e["id"]: e for e in a["entities"]}, {e["id"]: e for e in b["entities"]}
    out: dict[str, Any] = {"rev": b["rev"], "base": a["rev"], "order": list(eb)}
    out["add"] = [eb[i] for i in eb if i not in ea]
    out["change"] = [eb[i] for i in eb if i in ea and ea[i] != eb[i]]
    out["remove"] = [i for i in ea if i not in eb]
    ta, tb = _by_id(a["tracks"]), _by_id(b["tracks"])
    out["tracks"] = {i: tb.get(i, []) for i in sorted(set(ta) | set(tb)) if ta.get(i) != tb.get(i)}
    out["track_order"] = list(tb)
    keys = (set(a) | set(b)) - {"rev", "entities", "tracks"}
    out["set"] = {k: b[k] for k in sorted(keys) if k in b and a.get(k) != b[k]}
    out["unset"] = sorted(k for k in keys if k in a and k not in b)
    return out


def _by_id(tracks: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for t in tracks:
        out.setdefault(t["id"], []).append(t)
    return out


def undiff(a: dict, d: dict) -> dict:
    """Apply a diff to its base patch: undiff(a, diff(a, b)) == b."""
    if "full" in d:
        return d["full"]
    ents = {e["id"]: e for e in a["entities"]}
    for i in d["remove"]:
        ents.pop(i, None)
    for e in d["change"] + d["add"]:
        ents[e["id"]] = e
    tracks = _by_id(a["tracks"])
    tracks.update(d["tracks"])
    out = {k: v for k, v in a.items() if k not in d["unset"]}
    out.update(d["set"])
    out.update(rev=d["rev"], entities=[ents[i] for i in d["order"]],
               tracks=[t for i in d["track_order"] for t in tracks.get(i, [])])
    return {k: out[k] for k in list(a) + [k for k in out if k not in a] if k in out}
