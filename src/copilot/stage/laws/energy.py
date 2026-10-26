"""pendulum_energy: a swing / pendulum released from rest at θ0 (the S-template's exact period and RK4 swing)."""
from __future__ import annotations

import math
from typing import Any

from copilot.simulation.templates.pendulum import period, swing_curve
from copilot.stage.laws.base import Calc, Result, r


def pendulum_energy(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """θ(t) over one period; PE share = (1 − cos θ) / (1 − cos θ0), KE share = 1 − PE (no friction). The height
    drop h = L (1 − cos θ0) and the speed at the bottom √(2 g h)."""
    c = Calc(law_id, "pendulum_energy", givens, {"L": 2.3, "theta0": 35.0})
    g = c.const("g_earth", "g")
    L = c.get("L", "m", ctx.get("L"))
    th0 = c.get("theta0", "deg")
    T = c.out("T", period(L, th0, g), "s", ["L", "theta0", "g"])
    h = c.out("h", L * (1 - math.cos(math.radians(th0))), "m", ["L", "theta0"])
    c.out("v_max", math.sqrt(2 * g * h), "m/s", ["g", "h"])
    n = max(48, int(T * 24))
    ts, th = swing_curve(L, th0, g, T, n)
    k0 = 1 - math.cos(math.radians(th0))
    pe = [(1 - math.cos(math.radians(a))) / k0 for a in th]
    c.res.samples["theta"] = [[r(t), r(a, 3)] for t, a in zip(ts, th)]
    c.res.samples["energy"] = [[r(t), r(p, 3), r(1 - p, 3)] for t, p in zip(ts, pe)]
    # the bob's speed (tangential, m/s) from energy: v = √(2 g L (cos θ − cos θ0))
    c.res.samples["speed"] = [[r(t), r(math.sqrt(max(0.0, 2 * g * L * (math.cos(math.radians(a)) - math.cos(math.radians(th0))))), 4)]
                              for t, a in zip(ts, th)]
    c.res.events.update(high=0.0, low=r(T / 4), high_2=r(T / 2))
    c.res.facts.update(T=T, L=L, theta0=th0, h=h)
    return c.res
