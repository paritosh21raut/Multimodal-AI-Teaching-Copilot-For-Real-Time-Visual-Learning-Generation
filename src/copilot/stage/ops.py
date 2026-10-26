"""Stage ops (contract stage-spec §1): what the LLM and the fast path may say about a scene, and the closed lists (§3–5).

An op says WHAT is in the scene (entities, relations, actions, laws, stated numbers with their quote); never where
(no coordinates, sizes, times or unquoted numbers): the director, acting and the law modules compute HOW. Every op is
checked by stage.validate before the event log takes it.
"""
from __future__ import annotations

import re
from typing import Annotated, Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator

MAX_OPS = 16        # per delta
MAX_ENTITIES = 12   # visible at once
ID = re.compile(r"^[a-z][a-z0-9_]{0,23}$")

KINDS = ("agent", "animal", "prop", "surface", "place", "field", "diagram")
RELATIONS = ("on", "under", "in", "above", "behind", "in_front_of", "left_of", "right_of", "near", "holding",
             "attached_to", "sitting_on", "at")
STATES = ("on", "off", "full", "empty", "open", "closed")
AGENT_VERBS = tuple("""walk jog run stand sit jump push pull throw catch carry pick_up put_down hold point talk call
phone fold_arms nod shake_head wave drive swim float climb crouch kneel roll slide water plant harvest chop eat
drink dance look_at""".split())
OBJECT_VERBS = tuple("""move fall roll bounce slide_down orbit swing rotate float sink grow shrink appear vanish
transform_into emit flow""".split())
ANIMAL_VERBS = ("walk", "run", "sit", "stand", "fly", "swim")
NEEDS_OBJ = ("push", "pull", "throw", "catch", "carry", "pick_up", "put_down", "hold", "water", "chop", "eat", "drink")
MANNERS = ("slow", "fast", "hard", "gently")
PLAIN_DIRS = ("left", "right", "up", "down")
LAWS = ("uniform_motion", "accelerated_motion", "projectile", "sliding_friction", "relative_motion", "free_fall_compare",
        "moments", "pendulum_energy", "buoyancy", "apparent_weight", "collision_1d", "orbit", "wave_string", "echo",
        "rays", "refraction", "static_field")
RECIPES = ("axes_curve", "riemann_strips", "vector_add", "free_body", "field_lines", "particles", "wavefronts", "rays",
           "atom", "circuit", "number_line", "unit_circle", "cycle", "moon_phases", "strobe", "energy_bars")
VIEWS = ("side", "top", "cutaway", "split")
SHOTS = ("establish", "focus", "follow")


class _Op(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _list(v: Any) -> Any:
    return [v] if isinstance(v, str) else v


class Add(_Op):
    op: Literal["add"]
    id: str
    kind: str
    w: str
    near: Optional[str] = None
    attr: list[str] = Field(default_factory=list)
    _attr = field_validator("attr", mode="before")(_list)


class Set(_Op):
    op: Literal["set"]
    id: str
    w: Optional[str] = None
    attr: Optional[list[str]] = None
    state: Optional[str] = None
    _attr = field_validator("attr", mode="before")(_list)


class Remove(_Op):
    op: Literal["remove"]
    id: str


class Relate(_Op):
    op: Literal["relate"]
    a: str
    kind: str
    b: str


class Act(_Op):
    op: Literal["act"]
    id: str
    verb: str
    agent: str
    obj: Optional[str] = None
    dir: Optional[str] = None
    manner: Optional[str] = None


class End(_Op):
    op: Literal["end"]
    id: str


class Law(_Op):
    op: Literal["law"]
    id: str
    name: str
    roles: dict[str, Union[str, list[str]]]


class Given(_Op):
    op: Literal["given"]
    law: str
    sym: str
    v: float
    u: str = ""
    q: str


class View(_Op):
    op: Literal["view"]
    mode: str
    ids: list[str] = Field(default_factory=list)


class Frame(_Op):
    op: Literal["frame"]
    shot: str
    ids: list[str] = Field(default_factory=list)


class Diagram(_Op):
    op: Literal["diagram"]
    id: str
    recipe: str
    params: dict[str, Any] = Field(default_factory=dict)


class Label(_Op):
    op: Literal["label"]
    id: str
    text: str


class Unsafe(_Op):
    op: Literal["unsafe"]


class Undo(_Op):
    """A compensating event (contract §7): the teacher's "undo" of an earlier event; never sent by the LLM."""
    op: Literal["undo"]
    seq: int


StageOp = Annotated[Union[Add, Set, Remove, Relate, Act, End, Law, Given, View, Frame, Diagram, Label, Unsafe, Undo],
                    Field(discriminator="op")]
_ADAPTER: TypeAdapter = TypeAdapter(StageOp)


def parse(raw: dict) -> StageOp:
    """One op from its JSON object (raises pydantic.ValidationError on a schema error)."""
    return _ADAPTER.validate_python(raw)


def dump(op: Any) -> dict:
    return op.model_dump(exclude_none=True, exclude_defaults=True) | {"op": op.op}
