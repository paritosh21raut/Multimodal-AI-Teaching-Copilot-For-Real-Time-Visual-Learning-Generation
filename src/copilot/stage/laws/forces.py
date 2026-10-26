"""Force laws: sliding_friction, moments, buoyancy, apparent_weight (closed forms, SI)."""
from __future__ import annotations

import math
from typing import Any

from copilot.stage.laws.base import Calc, Result, r, steps

SHOW_S = 4.0


def sliding_friction(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """A body pushed along a rough surface. ctx `phase`: steady (pushed at a constant speed: F = f), hard (pushed
    harder than friction: it speeds up), released (no push: friction stops it), rest (no push yet: f = 0).
    ctx `v0` is the speed at the phase start (the stage's push speed; a said `v` replaces it)."""
    c = Calc(law_id, "sliding_friction", givens, {"m": 30.0, "mu_k": 0.4})
    g = c.const("g_earth", "g")
    m, mu = c.get("m", "kg"), c.get("mu_k", "1")
    N = c.out("N", m * g, "N", ["m", "g"])
    f = c.out("f", mu * N, "N", ["mu_k", "N"])
    phase, T = ctx.get("phase", "steady"), float(ctx.get("T", SHOW_S))
    v0 = c.get("v", "m/s") if c.has("v") else c.stage("v", float(ctx.get("v0", 0.0)), "m/s")
    if c.has("mu_s"):
        mus = c.get("mu_s", "1")
        c.out("f_s_max", mus * N, "N", ["mu_s", "N"])
    if phase in ("steady", "hard") and c.has("F"):
        # a said push decides, whatever the words: F > f speeds it up, F < f slows it (a < 0), F = f keeps v
        F = c.get("F", "N")
        a = c.out("a", (F - f) / m, "m/s^2", ["F", "f", "m"])
    elif phase == "steady":
        a = 0.0
        c.stage("F", f, "N")  # a steady push: the push equals friction (F = f)
    elif phase == "hard":
        F = c.get("F", "N", f + 0.12 * m)  # not said: illustratively a = 0.12 m/s² (a person can keep up)
        a = c.out("a", (F - f) / m, "m/s^2", ["F", "f", "m"])
    elif phase == "released":
        a = -c.out("a_stop", mu * g, "m/s^2", ["mu_k", "g"])  # a = −μk g, whatever the mass
        c.out("t_stop", v0 / (mu * g), "s", ["v", "mu_k", "g"])
        c.out("s_stop", v0 * v0 / (2 * mu * g), "m", ["v", "mu_k", "g"])
    else:
        a, v0 = 0.0, 0.0
    stop = v0 / -a if a < 0 else math.inf
    if phase == "released":
        T = min(T, stop + 1.5)

    def x(t: float) -> float:
        tt = min(t, stop)
        return v0 * tt + a * tt * tt / 2

    c.res.samples["body"] = [[r(t), r(x(t)), 0.0] for t in steps(0, T, 1 / 12)]
    c.res.samples["speed"] = [[r(t), r(max(0.0, v0 + a * min(t, stop)), 4)] for t in steps(0, T, 1 / 12)]
    c.res.events.update(start=0.0, end=r(T))
    if math.isfinite(stop):
        c.res.events["stop"] = r(stop)
    c.res.facts.update(phase=phase, a=a, v0=v0, v_end=max(0.0, v0 + a * min(T, stop)), T=T, f=f, N=N,
                       balanced=abs(a) < 1e-9 and phase == "steady")
    return c.res


def moments(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Two loads on a beam either side of the pivot (load 1 left at d1, load 2 right at d2). W_i said, or m_i said
    (W = m g), else a default from the person (adult 60 kg, child 25 kg). With ctx `balance` (the teacher says it
    balances) and d2 not said, d2 = W1 d1 / W2 is computed: where the second load must sit."""
    c = Calc(law_id, "moments", givens, {"d1": 1.0, "d2": 1.0})
    g = c.const("g_earth", "g")
    W = []
    for i, m_def in enumerate(ctx.get("m_default", [60.0, 25.0]), 1):
        if c.has(f"W{i}"):
            W.append(c.get(f"W{i}", "N"))
        elif c.has(f"m{i}"):
            W.append(c.out(f"W{i}", c.get(f"m{i}", "kg") * g, "N", [f"m{i}", "g"]))
        else:
            W.append(c.get(f"W{i}", "N", m_def * g))
    d1 = c.get("d1", "m", ctx.get("d1"))
    if c.has("d2") or not ctx.get("balance"):
        d2 = c.get("d2", "m", ctx.get("d2"))
    else:
        d2 = c.out("d2", W[0] * d1 / W[1], "m", ["W1", "d1", "W2"])
    M1 = c.out("M1", W[0] * d1, "N m", ["W1", "d1"])
    M2 = c.out("M2", W[1] * d2, "N m", ["W2", "d2"])
    net = M2 - M1  # > 0: the right side goes down
    balanced = abs(net) <= 1e-6 * max(M1, M2)
    max_tilt = math.degrees(math.asin(min(1.0, ctx.get("top", 0.6) / max(0.1, ctx.get("half", 3.0)))))
    tilt = 0.0 if balanced else (-max_tilt if net > 0 else max_tilt)  # degrees, counter-clockwise +
    T = 3.0
    c.res.samples["beam"] = [[r(t), r(tilt * min(1.0, t / 1.0) ** 2 if t < 1.0 else tilt, 3)] for t in steps(0, T, 1 / 24)]
    c.res.facts.update(balanced=balanced, turns="none" if balanced else "right_down" if net > 0 else "left_down",
                       d1=d1, d2=d2, W=W, tilt=tilt)
    return c.res


def buoyancy(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """A body in a fluid: floats when its density m / V is below the fluid's ρ, then submerged by (m / V) / ρ;
    upthrust U = ρ V_sub g, weight W = m g. ρ not said: the fluid's constant (water) when the noun names one."""
    c = Calc(law_id, "buoyancy", givens, {"m": 0.5, "V": 0.001, "rho": 1000.0})
    g = c.const("g_earth", "g")
    rho = c.get("rho", "kg/m^3") if c.has("rho") or not ctx.get("rho_key") else c.const(ctx["rho_key"], "rho")
    m, V = c.get("m", "kg"), c.get("V", "m^3")
    dens = c.out("rho_body", m / V, "kg/m^3", ["m", "V"])
    W = c.out("W", m * g, "N", ["m", "g"])
    floats = dens < rho
    frac = dens / rho if floats else 1.0
    c.out("U", rho * V * frac * g, "N", ["rho", "V", "g"] + (["rho_body"] if floats else []))
    if floats:
        c.out("frac", frac, "1", ["rho_body", "rho"])
    c.res.facts.update(floats=floats, frac=frac, W=W)
    side = V ** (1 / 3)
    end = -side * frac if floats else -float(ctx.get("depth", 1.0))
    c.res.samples["body"] = [[r(t), 0.0, r(end * (1 - math.exp(-3 * t)))] for t in steps(0, 3.0, 1 / 12)]
    return c.res


def apparent_weight(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """A person standing in a lift with acceleration a (ctx `sign`: +1 up, −1 down): the floor pushes N = m (g + a);
    the scale reads N, not m g. Speeding up going up (or slowing going down): N > m g."""
    c = Calc(law_id, "apparent_weight", givens, {"m": 60.0, "a": 1.5})
    g = c.const("g_earth", "g")
    m, a = c.get("m", "kg"), c.get("a", "m/s^2") * float(ctx.get("sign", 1))
    W = c.out("W", m * g, "N", ["m", "g"])
    N = c.out("N", m * (g + a), "N", ["m", "g", "a"])
    c.out("ratio", N / W, "1", ["N", "W"])
    T = float(ctx.get("T", 3.0))
    c.res.samples["lift"] = [[r(t), 0.0, r(a * t * t / 2)] for t in steps(0, T, 1 / 12)]  # from rest in the shot
    c.res.facts.update(N=N, W=W, a=a, heavier=N > W)
    return c.res
