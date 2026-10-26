"""Law modules (contract §4): roles + givens -> motion samples, event times and quantities with provenance (§2).

Every number a law returns is a `Num`: `said` (a given, with its quote), `constant` (a row of config/constants.toml),
`computed` (from said / constant / computed inputs only) or `symbol` (no value: shown as a letter). A missing given is
replaced by an illustrative default so the motion can still play; the default is never printed, anything computed
from it is a symbol, and the result is `illustrative` (the stage shows the badge). SI throughout.
"""
from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any, Callable, Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib

from copilot.simulation.base import fmt

ROOT = Path(__file__).resolve().parents[4]
CONSTANTS = ROOT / "config" / "constants.toml"
KNOWN = ("said", "computed", "constant")


@lru_cache(maxsize=1)
def constants() -> dict[str, dict[str, Any]]:
    return tomllib.loads(CONSTANTS.read_text(encoding="utf-8"))


@dataclass
class Num:
    sym: str
    v: Optional[float]
    u: str
    src: str                      # said | computed | constant | symbol
    q: str = ""                   # said: the verbatim quote
    law: str = ""                 # computed: the law id
    inputs: list[str] = field(default_factory=list)
    const: str = ""               # constant: the constants.toml row
    shown_u: str = ""             # said: the unit as said (km/h), v then in that unit

    @property
    def known(self) -> bool:
        return self.src in KNOWN and self.v is not None

    def rec(self) -> dict[str, Any]:
        r: dict[str, Any] = {"sym": self.sym, "v": self.v, "u": self.u, "src": self.src}
        for k in ("q", "law", "const"):
            if getattr(self, k):
                r[k] = getattr(self, k)
        if self.inputs:
            r["inputs"] = list(self.inputs)
        return r

    def text(self, sig: int = 3) -> str:
        """As printed: "v = 10 m/s"; a symbol prints its letter only."""
        if not self.known:
            return self.sym
        u = PRETTY.get(self.u, self.u)
        return f"{self.sym} = {fmt(self.v, sig)}{' ' + u if u else ''}"


PRETTY = {"m/s^2": "m/s²", "deg": "°", "kg/m^3": "kg/m³", "m^3": "m³", "1": ""}


@dataclass
class Result:
    law: str                                   # law id
    name: str
    nums: dict[str, Num] = field(default_factory=dict)
    samples: dict[str, list[list[float]]] = field(default_factory=dict)  # [[t, x, y(, rot)]] in law coordinates
    events: dict[str, float] = field(default_factory=dict)              # contact, release, apex, impact, stop
    illustrative: bool = False
    facts: dict[str, Any] = field(default_factory=dict)                  # law-specific outcome (floats, balanced ...)

    def printable(self) -> dict[str, Num]:
        return {k: n for k, n in self.nums.items() if n.known}


class Calc:
    """One law run: givens in SI by symbol; `get` falls back to a default (illustrative), `out` records a result."""

    def __init__(self, law_id: str, name: str, givens: dict[str, Any], defaults: dict[str, float]):
        self.res = Result(law_id, name)
        self.g, self.defaults = givens, defaults

    def has(self, sym: str) -> bool:
        return sym in self.g

    def get(self, sym: str, unit: str, default: Optional[float] = None) -> float:
        if sym in self.g:
            gv = self.g[sym]
            self.res.nums[sym] = Num(sym, gv.si, gv.si_u, "said", q=gv.q, shown_u=gv.u)
            return gv.si
        v = self.defaults.get(sym) if default is None else default
        if v is None:
            raise KeyError(f"{self.res.name}: no default for {sym}")
        self.res.illustrative = True
        self.res.nums.setdefault(sym, Num(sym, None, unit, "symbol"))
        return v

    def stage(self, sym: str, v: float, unit: str) -> float:
        """A value the drawing fixes (the hand's height, a desk top, a roll-off's θ = 0): used for the motion, shown
        as a symbol; not a guessed physics input (no illustrative flag). Anything computed from it is a symbol."""
        self.res.nums.setdefault(sym, Num(sym, None, unit, "symbol"))
        return v

    def const(self, key: str, sym: str) -> float:
        row = constants()[key]
        self.res.nums[sym] = Num(sym, float(row["v"]), row["u"], "constant", const=key)
        return float(row["v"])

    def out(self, sym: str, v: float, unit: str, deps: list[str]) -> float:
        ok = all(d in self.res.nums and self.res.nums[d].known for d in deps) and math.isfinite(v)
        self.res.nums[sym] = Num(sym, v if ok else None, unit, "computed" if ok else "symbol", law=self.res.law,
                                 inputs=list(deps) if ok else [])
        return v

    def known(self, *syms: str) -> bool:
        return all(s in self.res.nums and self.res.nums[s].known for s in syms)


@dataclass(frozen=True)
class LawSpec:
    name: str
    roles: tuple[str, ...]                     # required
    optional: tuple[str, ...]
    syms: dict[str, str]                       # given symbol -> pint dimensionality ("[length] / [time]", "" = none)
    solve: Callable[..., Result]
    lists: tuple[str, ...] = ()                # roles that take a list of ids
    pre: Optional[Callable[[Any, dict[str, Any]], str]] = None  # (graph, roles) -> "" or why not


def steps(t0: float, t1: float, dt: float = 1 / 24) -> list[float]:
    n = max(1, math.ceil((t1 - t0) / dt - 1e-9))
    return [t0 + (t1 - t0) * i / n for i in range(n + 1)]


def r(x: float, k: int = 4) -> float:
    return round(x + 0.0, k)
