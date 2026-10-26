"""The law registry (contract §4): name -> roles, givens (symbol -> dimension), solver, precondition.

E2 builds ten laws; the other names of the closed list are refused by the validator until they are built (E4).
"""
from __future__ import annotations

from typing import Any

from copilot.stage.laws.base import LawSpec, Num, Result
from copilot.stage.laws.energy import pendulum_energy
from copilot.stage.laws.forces import apparent_weight, buoyancy, moments, sliding_friction
from copilot.stage.laws.motion import G_OF, accelerated_motion, free_fall_compare, projectile, uniform_motion
from copilot.stage.laws.relative import relative_motion

SPEED, ACC, LEN, TIME = "[length] / [time]", "[length] / [time] ** 2", "[length]", "[time]"
MASS, FORCE, DENS, VOL = "[mass]", "[mass] * [length] / [time] ** 2", "[mass] / [length] ** 3", "[length] ** 3"
ANGLE, PURE = "angle", ""  # an angle: degrees or radians; a pure number: no unit


def _on(g: Any, body: str, surface: str) -> str:
    rel = g.rel(body)
    return "" if rel and rel.kind == "on" and rel.b == surface else f"{body} is not on {surface}"


def _in(g: Any, x: str, container: str) -> str:
    rel = g.rel(x)
    if rel and rel.kind in ("in", "on", "at") and (rel.b == container or (g.rel(rel.b) and g.rel(rel.b).b == container)):
        return ""
    return f"{x} is not in {container}"


def _pre_friction(g: Any, roles: dict[str, Any]) -> str:
    return _on(g, roles["body"], roles["surface"])


def _pre_moments(g: Any, roles: dict[str, Any]) -> str:
    return "" if len(roles["loads"]) == 2 else "moments needs two loads (one each side)"


def _pre_compare(g: Any, roles: dict[str, Any]) -> str:
    bad = [p for p in roles["places"] if place_key(g.ents[p].w) is None]
    return f"no gravity constant for {', '.join(g.ents[p].w for p in bad)}" if bad else ""


def _pre_relative(g: Any, roles: dict[str, Any]) -> str:
    return "" if roles["observer"] in (roles["a"], roles["b"]) else "the observer must be a or b"


def place_key(w: str) -> str | None:
    t = w.lower()
    return next((k for k in G_OF if k in t), None)


LAWS: dict[str, LawSpec] = {s.name: s for s in (
    LawSpec("uniform_motion", ("body",), (), {"v": SPEED, "t": TIME, "d": LEN}, uniform_motion),
    LawSpec("accelerated_motion", ("body",), (), {"u": SPEED, "a": ACC, "t": TIME, "s": LEN}, accelerated_motion),
    LawSpec("projectile", ("body",), ("launcher",), {"v0": SPEED, "theta": ANGLE, "h0": LEN, "g": ACC}, projectile),
    LawSpec("sliding_friction", ("body", "surface"), ("force_from",),
            {"m": MASS, "F": FORCE, "mu_k": PURE, "mu_s": PURE, "v": SPEED}, sliding_friction, pre=_pre_friction),
    LawSpec("relative_motion", ("a", "b", "observer"), (), {"va": SPEED, "vb": SPEED}, relative_motion,
            pre=_pre_relative),
    LawSpec("free_fall_compare", ("bodies", "places"), (), {"v0": SPEED}, free_fall_compare,
            lists=("bodies", "places"), pre=_pre_compare),
    LawSpec("moments", ("beam", "pivot", "loads"), (),
            {"W1": FORCE, "W2": FORCE, "m1": MASS, "m2": MASS, "d1": LEN, "d2": LEN}, moments, lists=("loads",),
            pre=_pre_moments),
    LawSpec("pendulum_energy", ("bob", "pivot"), (), {"L": LEN, "theta0": ANGLE}, pendulum_energy),
    LawSpec("buoyancy", ("body", "fluid"), (), {"rho": DENS, "V": VOL, "m": MASS}, buoyancy,
            pre=lambda g, ro: _in(g, ro["body"], ro["fluid"])),
    LawSpec("apparent_weight", ("person", "lift"), (), {"m": MASS, "a": ACC}, apparent_weight,
            pre=lambda g, ro: _in(g, ro["person"], ro["lift"])),
)}

__all__ = ["LAWS", "LawSpec", "Num", "Result", "place_key", "ANGLE", "PURE"]
