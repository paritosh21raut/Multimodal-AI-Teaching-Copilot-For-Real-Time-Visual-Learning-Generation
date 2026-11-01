"""Diagram ops (contract §1): what the fast path or the LLM may say about a diagram. Never coordinates, sizes, times
or a number without its quote."""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

MAX_OPS = 16
MAX_PARTS = 40
RELS = ("on", "in", "hang_from", "orbit", "above", "attached_to", "beside", "inside", "at_edge")
VERBS = ("stir", "heat", "cool", "dissolve", "pour", "close", "open", "rotate", "orbit", "flow",
         "throw", "fall", "move", "circle", "cross")  # M5: motion
SHOWS = ("field", "current", "voltage", "forces", "labels", "shells")
SYMS = {"theta": "deg", "m": "kg", "k": "N/m", "V": "V", "R": "ohm"}  # K1: the givens a part can show
# F-019 §2: the quantities a `qty` op may attach (sym -> SI unit; "" = a pure number)
QSYMS = {"m": "kg", "F": "N", "mu": "", "mu_s": "", "mu_k": "", "theta": "deg", "k": "N/m",
         "v": "m/s", "h": "m", "t": "s", "a": "m/s^2", "r": "m", "d": "m"}  # M5: motion
DIRS = ("left", "right", "up", "down", "up_slope", "down_slope", "")


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Part(_Op):
    op: Literal["part"]
    id: str
    kind: str
    label: Optional[str] = None
    attr: dict[str, Any] = Field(default_factory=dict)


class Group(_Op):
    op: Literal["group"]
    id: str
    mode: Literal["series", "parallel"]
    items: list[str]


class Wire(_Op):
    op: Literal["wire"]
    a: str
    b: str


class Contain(_Op):
    op: Literal["contain"]
    a: str
    b: str


class Solution(_Op):
    op: Literal["solution"]
    id: str
    solute: str
    conc: Optional[str] = None


class Place(_Op):
    op: Literal["place"]
    a: str
    rel: str
    b: str


class Process(_Op):
    op: Literal["process"]
    verb: str
    target: str
    src: Optional[str] = None
    manner: Optional[str] = None


class Given(_Op):
    op: Literal["given"]
    sym: str
    v: float
    u: str = ""
    q: str
    on: Optional[str] = None


class Qty(_Op):
    """A said quantity on a part (F-019 §2): `v` in the SI unit `u`, converted by Python from the quote `q`."""
    op: Literal["qty"]
    on: str
    sym: str
    v: float
    u: str = ""
    q: str
    dir: str = ""
    note: str = ""          # "weight": the word the teacher used for a mass ("the weight of the box is 5 kg")


class Show(_Op):
    op: Literal["show"]
    what: str
    on: Optional[str] = None


class Mode(_Op):
    op: Literal["mode"]
    to: Literal["diagram", "scene"]


Op = Union[Part, Group, Wire, Contain, Solution, Place, Process, Given, Qty, Show, Mode]
_ADAPTER: TypeAdapter = TypeAdapter(Op)


def parse(raw: dict) -> Op:
    if not isinstance(raw, dict) or "op" not in raw:
        raise ValueError("not an op")
    return _ADAPTER.validate_python(raw)
