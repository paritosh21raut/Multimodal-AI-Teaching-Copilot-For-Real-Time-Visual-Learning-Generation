"""Kinematics laws: uniform_motion, accelerated_motion, projectile, free_fall_compare (closed forms, SI).

Law coordinates: x along the motion from the start, y the height above the ground; t = 0 is the law's own start (a
throw's release, a car's start). The timeline shifts them onto the stage clock and into the stage frame.
"""
from __future__ import annotations

import math
from typing import Any

from copilot.simulation.templates.projectile import flight
from copilot.stage.laws.base import Calc, Result, r, steps

SPEED, ACC, LEN, TIME, ANGLE, MASS = "[length] / [time]", "[length] / [time] ** 2", "[length]", "[time]", "", "[mass]"
SHOW_S = 4.0  # display seconds of a motion with no said time


def uniform_motion(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    c = Calc(law_id, "uniform_motion", givens, {"v": ctx.get("v", 1.0)})
    if c.has("v") or not (c.has("d") and c.has("t")):
        v = c.get("v", "m/s")
        if c.has("t"):
            T = c.get("t", "s")
            c.out("d", v * T, "m", ["v", "t"])
        elif c.has("d"):
            d = c.get("d", "m")
            T = c.out("t", d / v, "s", ["d", "v"]) if v > 0 else SHOW_S
        else:
            T = ctx.get("T", SHOW_S)
    else:
        d, T = c.get("d", "m"), c.get("t", "s")
        v = c.out("v", d / T, "m/s", ["d", "t"])
    c.res.samples["body"] = [[r(t), r(v * t), 0.0] for t in steps(0, T, 1 / 12)]
    c.res.events.update(start=0.0, end=r(T))
    c.res.facts.update(v=v, T=T)
    return c.res


def accelerated_motion(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    c = Calc(law_id, "accelerated_motion", givens, {"u": 0.0, "a": 1.5})
    u, a = c.get("u", "m/s"), c.get("a", "m/s^2")
    stop = u / -a if a < 0 else math.inf
    reached = True
    if c.has("t"):
        T = c.get("t", "s")
    elif c.has("s"):
        s = c.get("s", "m")
        disc = u * u + 2 * a * s
        if a == 0:
            reached = u > 0
            T = s / u if reached else SHOW_S
        else:
            reached = disc >= 0 and (-u + math.sqrt(disc)) / a >= 0
            T = (-u + math.sqrt(disc)) / a if reached else min(stop, SHOW_S) + 1.0
        if reached:
            c.out("t", T, "s", ["u", "a", "s"])
        else:  # it stops (or never moves) before s: no time to print, the stop distance is the answer
            c.res.facts["stops_before"] = True
            if math.isfinite(stop):
                c.out("s_stop", u * u / (2 * -a), "m", ["u", "a"])
    else:
        T = ctx.get("T", SHOW_S)

    def x(t: float) -> float:
        tt = min(t, stop)
        return u * tt + a * tt * tt / 2

    if (c.has("t") or c.has("s")) and reached:
        c.out("v", max(0.0, u + a * min(T, stop)), "m/s", ["u", "a", "t" if c.has("t") else "s"])
        if c.has("t"):
            c.out("s", x(T), "m", ["u", "a", "t"])
    c.res.samples["body"] = [[r(t), r(x(t)), 0.0] for t in steps(0, T, 1 / 12)]
    # equal-time marks (a strobe): where the body is at n equal steps of time
    n = int(ctx.get("marks", 4))
    ts = [T * k / n for k in range(n + 1)]
    xs = [x(t) for t in ts]
    gaps = [b - q for q, b in zip(xs, xs[1:])]
    c.res.facts.update(u=u, mark_t=[r(t) for t in ts], mark_x=[r(v) for v in xs], gaps=[r(g, 6) for g in gaps], T=T,
                       v_end=max(0.0, u + a * min(T, stop)))
    if gaps and gaps[0] > 1e-9:
        # from rest the gaps go 1 : 3 : 5 ... whatever a is: computed from the said u = 0 alone
        c.out("gap_ratio", gaps[1] / gaps[0], "1", ["u"] if c.known("u") and abs(u) < 1e-12 else ["u", "a"])
        c.res.facts["gap_ratio"] = [r(g / gaps[0], 3) for g in gaps]
    c.res.events.update(start=0.0, end=r(T))
    if math.isfinite(stop) and stop <= T:
        c.res.events["stop"] = r(stop)
    return c.res


def projectile(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """A throw / a ball rolling off a desk: v0 at θ above the horizontal from height h0 (above the ground the body
    lands on). h0 not said is the drawing's launch height (the hand, the desk top): used, never printed."""
    c = Calc(law_id, "projectile", givens, {"v0": 5.0, "theta": 45.0})
    g = c.get("g", "m/s^2") if c.has("g") else c.const(ctx.get("g_key", "g_earth"), "g")  # "take g as 10"
    v0 = c.get("v0", "m/s")
    # rolling off a desk: horizontal (θ = 0) by the scene itself; else a default angle
    th = c.stage("theta", float(ctx["theta"]), "deg") if "theta" in ctx and not c.has("theta") else c.get("theta", "deg")
    h0 = c.get("h0", "m") if c.has("h0") else c.stage("h0", float(ctx.get("h0", 0.0)), "m")
    tf, rng, hmax = flight(v0, th, h0, g)  # the S-template's closed form
    ux, uy = v0 * math.cos(math.radians(th)), v0 * math.sin(math.radians(th))
    c.out("t_apex", max(0.0, uy) / g, "s", ["v0", "theta", "g"])
    c.out("h_apex", max(0.0, uy) ** 2 / (2 * g), "m", ["v0", "theta", "g"])  # above the launch point
    c.out("T", tf, "s", ["v0", "theta", "h0", "g"])
    c.out("R", rng, "m", ["v0", "theta", "h0", "g"])
    c.res.samples["body"] = [[r(t), r(ux * t), r(h0 + uy * t - g * t * t / 2)] for t in steps(0, tf, 1 / 30)]
    c.res.samples["v"] = [[r(t), r(ux, 3), r(uy - g * t, 3)] for t in steps(0, tf, 1 / 30)]
    c.res.events.update(release=0.0, impact=r(tf))
    if uy > 0:
        c.res.events["apex"] = r(uy / g)
    c.res.facts.update(tf=tf, range=rng, hmax=hmax, h0=h0, ux=ux, uy=uy, g=g)
    return c.res


G_OF = {"moon": "g_moon", "mars": "g_mars", "earth": "g_earth", "jupiter": "g_jupiter"}


def free_fall_compare(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """The same take-off speed v0 on each place: h = v0² / 2g, time in the air 2 v0 / g. The ratio of the heights is
    g2 / g1, which needs no v0 (computed from the constants)."""
    c = Calc(law_id, "free_fall_compare", givens, {"v0": 2.4})
    v0 = c.get("v0", "m/s")
    places = ctx["places"]
    gs = []
    for i, p in enumerate(places, 1):
        g = c.const(G_OF[p], f"g_{p}")
        gs.append(g)
        air = 2 * v0 / g
        c.out(f"h_{p}", v0 * v0 / (2 * g), "m", ["v0", f"g_{p}"])
        c.out(f"t_{p}", air, "s", ["v0", f"g_{p}"])
        c.res.samples[p] = [[r(t), 0.0, r(max(0.0, v0 * t - g * t * t / 2))] for t in steps(0, air, 1 / 24)]
        c.res.events[f"apex_{p}"], c.res.events[f"land_{p}"] = r(air / 2), r(air)
    if len(places) == 2:
        a, b = places
        c.out("ratio", gs[1] / gs[0], "1", [f"g_{a}", f"g_{b}"])  # h_a / h_b = g_b / g_a
    c.res.facts.update(v0=v0, g=gs)
    return c.res
