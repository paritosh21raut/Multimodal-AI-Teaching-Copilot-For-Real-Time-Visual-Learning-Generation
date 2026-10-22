"""The scene contract (F-015, docs/contracts/scene-spec.md): what a live scene is, and the ops that edit it.

The LLM states WHAT is in a scene as SceneOps; the validator checks them; the world engines (scene/worlds/) and the
layout compute HOW it looks and moves: `geom`, `frames`, `stage` and `derived` are engine output, never LLM output.

Truthfulness (carried over from F-014): a number's `source` says where it came from. Only said / teacher / computed
(from known inputs) numbers are printed; a default moves the picture and is never printed. A label prints only the
teacher's words (`Label.source` "said").
"""
from __future__ import annotations

from typing import Any, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field

from copilot.simulation.base import Playback

World = Literal["geometry", "plot", "motion", "rigid", "field", "wave", "optics", "particles", "flow", "graph"]
Source = Literal["said", "teacher", "computed", "default", "mentioned"]
KNOWN: frozenset[str] = frozenset({"said", "teacher", "computed"})

# Drawing kinds are parts, not templates (no topic logic). L1 engines draw these; the rest of F-015's list comes
# with the L2 / L3 worlds (a kind no engine draws yet is refused, never drawn as something else).
GEOMETRY_KINDS = ("square", "rectangle", "circle", "triangle", "polygon", "point", "segment")
PLOT_KINDS = ("curve",)
BODY_KINDS = ("ball", "block", "car", "particle")
KINDS: tuple[str, ...] = GEOMETRY_KINDS + PLOT_KINDS + BODY_KINDS
RELATIONS = ("inscribed_in", "around", "inside", "on", "diagonal_of", "radius_of", "diameter_of", "tangent_to",
             "bisector_of", "midpoint_of", "left_of", "right_of", "above", "below")
BEHAVIORS = ("move", "launch", "fall")
OPS = ("add", "set", "remove", "relate", "behave", "label", "focus")

MAX_ENTITIES = 40
MAX_ANNOTATIONS = 3
MAX_FRAME_POINTS = 400
ID_PATTERN = r"^[a-z][a-z0-9_]{0,15}$"


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Q(_Model):
    """A quantity: value in `unit` (as said; engines convert), and where it came from."""
    value: float
    unit: str = ""
    source: Source = "default"
    said: str = ""  # the words it was heard as ("three metres per second"), for logs and /control


class Label(_Model):
    text: str = ""
    source: Literal["said", "none"] = "none"  # "none": not printed


class Look(_Model):
    role: Literal["main", "second", "third", "accent", "muted"] = "main"


class Geom(_Model):
    """Engine output in stage px (1100 x 740, y down): what the renderer draws for one entity."""
    shape: Literal["rect", "circle", "poly", "seg", "path", "dot", "body"]
    pts: list[tuple[float, float]] = Field(default_factory=list)  # poly / seg corners, rect: [x, y] + [w, h]
    c: Optional[tuple[float, float]] = None   # circle / dot / body centre
    r: float = 0.0
    d: str = ""                               # path data (a sampled curve)
    angle: float = 0.0                        # rect / body rotation (degrees)
    label_at: Optional[tuple[float, float]] = None
    note: str = ""                            # a computed value printed beside the label ("(2, 4)" on a curve)
    dims: list[tuple[float, float, str]] = Field(default_factory=list)  # said sizes printed on the shape ("4 cm")


class Entity(_Model):
    id: str = Field(pattern=ID_PATTERN)
    kind: str
    name: str = ""                            # the teacher's word for it ("" = none said)
    label: Label = Field(default_factory=Label)
    props: dict[str, Q] = Field(default_factory=dict)
    expr: str = ""                            # a curve: y as an expression in x (scene.worlds.plot parses it)
    expr_shown: str = ""                      # the expression as printed ("" = a number in it was not said)
    look: Look = Field(default_factory=Look)
    geom: Optional[Geom] = None               # engine output


class Relation(_Model):
    kind: str
    a: str
    b: str


class Behavior(_Model):
    kind: str
    target: str
    params: dict[str, Q] = Field(default_factory=dict)


class Track(_Model):
    """One moving entity's path, sampled by the motion engine: [t s, x px, y px, angle deg, v m/s, distance m]."""
    id: str
    pts: list[tuple[float, float, float, float, float, float]] = Field(default_factory=list)


class Frames(_Model):
    """Engine output: the motion of one run, looped on the playback clock (run `period` s, then `hold` s at the end)."""
    period: float = 4.0
    hold: float = 1.0
    tracks: list[Track] = Field(default_factory=list)


class Axes(_Model):
    """A plot's axes in stage px, ticks computed by Python ([px, printed value])."""
    x0: float
    x1: float
    y0: float
    y1: float
    origin: tuple[float, float]
    xticks: list[tuple[float, str]] = Field(default_factory=list)
    yticks: list[tuple[float, str]] = Field(default_factory=list)


class Stage(_Model):
    """Engine output besides the entities: plot axes, a motion world's ground line (stage px)."""
    axes: Optional[Axes] = None
    ground: Optional[tuple[float, float, float]] = None  # x0, x1, y
    lanes: list[float] = Field(default_factory=list)
    trails: list[tuple[str, str]] = Field(default_factory=list)  # (entity id, path data): a launch's / fall's whole path


class Derived(_Model):
    """A readout. Static: `text` printed as is. Live (motion): `live` names the track value printed at the clock's
    time with `label` / `unit` (computed from Python's samples)."""
    id: str
    of: str = ""
    label: str = ""
    text: str = ""
    live: Literal["", "v", "x"] = ""
    unit: str = ""


class SceneSpec(_Model):
    template: Literal["scene"] = "scene"
    version: int = 0
    rev: int = 0                              # ops applied so far
    title: str = "Scene"
    world: World = "geometry"
    entities: list[Entity] = Field(default_factory=list, max_length=MAX_ENTITIES)
    relations: list[Relation] = Field(default_factory=list)
    behaviors: list[Behavior] = Field(default_factory=list)
    annotations: list[str] = Field(default_factory=list, max_length=MAX_ANNOTATIONS)
    focus: list[str] = Field(default_factory=list)
    playback: Playback = Field(default_factory=Playback)
    frames: Optional[Frames] = None
    stage: Stage = Field(default_factory=Stage)
    derived: list[Derived] = Field(default_factory=list)
    origin: Literal["cue", "policy", "teacher"] = "cue"

    def get(self, id_: str) -> Optional[Entity]:
        return next((x for x in self.entities if x.id == id_), None)


Num = Union[float, int, list[Any]]  # 3 | [3, "m/s"]


class SceneOp(_Model):
    """One line of the compiler's JSONL. Which fields an op needs is checked by scene.validate."""
    op: str
    id: str = ""
    kind: str = ""
    name: str = ""
    props: dict[str, Num] = Field(default_factory=dict)
    expr: str = ""
    a: str = ""
    b: str = ""
    target: str = ""
    params: dict[str, Num] = Field(default_factory=dict)
    text: str = ""
    ids: list[str] = Field(default_factory=list)
