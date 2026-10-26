"""relative_motion: the velocity of a seen from b (v_a − v_b), as in the F-015 relative world (rain on a walker)."""
from __future__ import annotations

import math
from typing import Any

from copilot.stage.laws.base import Calc, Result, r


def relative_motion(law_id: str, givens: dict[str, Any], ctx: dict[str, Any]) -> Result:
    """Roles a and b with speeds va, vb (the givens follow the roles). ctx `da`, `db`: their unit directions on the
    stage (rain falls (0, −1), a man walks (1, 0)); ctx `va`, `vb`: defaults (a walker's: its stage speed).
    v_rel = v_a − v_b (a seen from b; b − a when the observer is a: same size, opposite way); θ = the angle of v_rel
    from the vertical (rain–man: tan θ = v_m / v_r)."""
    c = Calc(law_id, "relative_motion", givens, {"va": float(ctx.get("va", 5.0)), "vb": float(ctx.get("vb", 1.0))})
    va, vb = c.get("va", "m/s"), c.get("vb", "m/s")
    da, db = ctx.get("da", (0.0, -1.0)), ctx.get("db", (1.0, 0.0))
    rel = (va * da[0] - vb * db[0], va * da[1] - vb * db[1])
    if ctx.get("observer_is_a"):
        rel = (-rel[0], -rel[1])
    c.out("v_rel", math.hypot(*rel), "m/s", ["va", "vb"])
    th = math.degrees(math.atan2(abs(rel[0]), abs(rel[1]))) if rel[1] else 90.0
    c.out("theta", th, "deg", ["va", "vb"])
    c.res.facts.update(rel=(r(rel[0], 4), r(rel[1], 4)), va=va, vb=vb, theta=th)
    return c.res
