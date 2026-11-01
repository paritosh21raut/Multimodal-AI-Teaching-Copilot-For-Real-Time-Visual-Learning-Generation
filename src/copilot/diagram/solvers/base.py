"""The solver framework (F-019 §3): a domain solver reads the scene graph (parts, relations, said quantities) and
returns `Results`: values (said with the quote, computed with the equation and its inputs, or a bare symbol when an
input is missing), force arrows and motions. Pure Python, deterministic; the LLM never computes (RULES)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional, Protocol

from copilot.diagram.graph import Graph
from copilot.simulation.base import fmt

UNIT_TEXT = {"m/s^2": "m/s²", "deg": "°", "N/m": "N/m"}


@dataclass
class Value:
    sym: str
    v: Optional[float]           # None: a symbol (an input is missing)
    u: str
    on: str = ""                 # the part (body) it belongs to; "" = the scene
    src: str = "computed"        # said | computed | constant | symbol
    frm: list[str] = field(default_factory=list)  # computed: the symbols it comes from
    eq: str = ""                 # computed: the equation, as printed ("a = (F − f)/m")
    q: str = ""                  # said: the teacher's words
    note: str = ""               # said: the word used ("weight" for a mass)

    @property
    def known(self) -> bool:
        return self.v is not None and math.isfinite(self.v)

    def text(self) -> str:
        if not self.known:
            return self.sym
        u = UNIT_TEXT.get(self.u, self.u)
        return f"{self.sym} = {fmt(self.v)}{'' if u in ('', '°') else ' '}{u}"


@dataclass
class Force:
    id: str
    on: str                      # the body it acts on
    kind: str                    # weight | normal | friction | applied | tension | spring
    value: Value                 # its magnitude (a symbol when unknown)
    ang: float                   # screen degrees: 0 = right, 90 = down (y down)
    at: str = "centre"           # centre | contact | top: where the arrow starts
    said_dir: bool = True        # False: a push with no way said (drawn, decides nothing)
    pair: bool = False           # Newton III: put on this body by the body on it (free-body view only)


@dataclass
class Motion:
    on: str
    state: str                   # slides | sticks | at rest | oscillates | not computed
    a: Optional[float] = None    # m/s², the magnitude along `ang`
    ang: float = 0.0             # screen degrees of the motion
    period: Optional[float] = None
    spring: str = ""             # oscillates: the spring that stretches


@dataclass
class Results:
    domain: str
    values: list[Value] = field(default_factory=list)
    forces: list[Force] = field(default_factory=list)
    motions: list[Motion] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)   # "slides", "sticks", what is missing (shown as words)
    paths: list = field(default_factory=list)        # M5 motion: kinematics.Path (sampled world positions)
    vectors: list = field(default_factory=list)      # M5 motion: kinematics.Vec (velocity arrows)
    extra: dict = field(default_factory=dict)        # M5 motion: display facts (the umbrella tilt, a river's width)


class Solver(Protocol):
    name: str

    def applies(self, g: Graph) -> bool: ...

    def solve(self, g: Graph) -> Results: ...


def registry() -> list[Solver]:
    from copilot.diagram.solvers.contact import Contact
    from copilot.diagram.solvers.kinematics import Kinematics
    return [Contact(), Kinematics()]


def run(g: Graph) -> Optional[Results]:
    """The first solver that applies, or None ("not simulated")."""
    for s in registry():
        if s.applies(g):
            return s.solve(g)
    return None
