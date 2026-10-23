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

World = Literal["geometry", "plot", "motion", "relative", "canvas", "rigid", "field", "wave", "optics", "particles", "flow", "graph"]
Source = Literal["said", "teacher", "computed", "default", "mentioned"]
KNOWN: frozenset[str] = frozenset({"said", "teacher", "computed"})

# Drawing kinds are parts, not templates (no topic logic). L1 engines draw these; the rest of F-015's list comes
# with the L2 / L3 worlds (a kind no engine draws yet is refused, never drawn as something else).
SOLID_KINDS = ("cube", "cuboid", "cylinder", "cone", "sphere")  # drawn as a textbook projection (hidden edges dashed)
GEOMETRY_KINDS = ("square", "rectangle", "circle", "triangle", "polygon", "point", "segment") + SOLID_KINDS
PLOT_KINDS = ("curve",)
BODY_KINDS = ("ball", "block", "car", "particle")
RELATIVE_KINDS = ("river", "rain")  # a flowing band of water, falling rain: they move things, they are not bodies
# F-016: any noun the teacher said (a picture of it) and the one place a scene happens in (its backdrop)
CANVAS_KINDS = ("thing", "place")
KINDS: tuple[str, ...] = GEOMETRY_KINDS + PLOT_KINDS + BODY_KINDS + RELATIVE_KINDS + CANVAS_KINDS
SIZES = ("tiny", "small", "medium", "large", "huge")  # a thing's size as the model senses it (drawn, never printed)
# directions a velocity is said in (screen: east / right +x, north / up +y); "toward" tilts it by its `angle`
DIRS = ("east", "west", "north", "south", "up", "down", "left", "right")
RELATIONS = ("inscribed_in", "around", "inside", "on", "diagonal_of", "radius_of", "diameter_of", "tangent_to",
             "bisector_of", "midpoint_of", "left_of", "right_of", "above", "below")
# F-016 relation primitives of the canvas (things and places): a is placed by b ("between" also takes c)
CANVAS_RELATIONS = ("on_top_of", "under", "in_front_of", "behind", "near", "between", "holding", "attached_to",
                    "part_of", "at")
RELATIONS = RELATIONS + CANVAS_RELATIONS
# cross: a boat heads straight across the river (shortest time); cross_straight: it heads upstream so that it lands
# straight opposite (shortest path)
BEHAVIORS = ("move", "launch", "fall", "cross", "cross_straight")
# F-016 action primitives (scene.worlds.canvas): an unknown verb is mapped by the model onto the nearest one.
# throw = launch; fall / throw / move / brake are motion.py's kinematics, the rest are drawn motions (no numbers)
ACTIONS = ("appear", "vanish", "move_to", "fly", "drive", "walk", "throw", "bounce", "sink", "float", "slide", "roll",
           "rotate", "spin", "grow", "shrink", "follow", "chase", "orbit", "shake", "carry", "push", "pull", "stop",
           "brake", "transform_into", "emit", "collide")
BEHAVIORS = BEHAVIORS + ACTIONS
EMITS = ("bubbles", "rings", "rays", "smoke", "waves", "sparks")  # what `emit` gives off (drawn effects)
# unsafe: the model's flag for content it must not draw (the call's ops are dropped, nothing is drawn, logged)
OPS = ("add", "set", "remove", "relate", "behave", "label", "focus", "frame", "unsafe")
MAX_PARTS = 4         # part_of things per thing

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
    """How an entity is drawn. A body's picture (scene.assets) for its said noun: an icon of the offline set, an LLM
    glyph (cleaned path data) or the teacher's image; none of them: the kind's own drawing. The picture never changes
    the physics. pick "teacher": chosen in /control, kept across edits."""
    role: Literal["main", "second", "third", "accent", "muted"] = "main"
    noun: str = ""                            # the word the picture is for ("rocket")
    icon: str = ""                            # an icon name of web/vendor/icons/scene-icons.js
    glyph: str = ""                           # path data on the 24 x 24 grid (scene.assets.clean)
    image: str = ""                           # the teacher's image (/media/<id>.jpg)
    emoji: str = ""                           # F-016: a Fluent 3D picture, cached (/scene-pic/<slug>.png)
    photo: str = ""                           # F-016 C1b: a photo cutout (background removed), cached (/scene-pic/)
    form: str = ""                            # F-016: a shape noun drawn as a shaded solid (cube, sphere, ...)
    to_noun: str = ""                         # transform_into: the noun it becomes and that noun's picture
    to_icon: str = ""
    to_emoji: str = ""
    pick: Literal["auto", "teacher"] = "auto"


class Geom(_Model):
    """Engine output in stage px (1100 x 740, y down; a canvas: Stage.size): what the renderer draws for one entity."""
    shape: Literal["rect", "circle", "poly", "seg", "path", "dot", "body", "solid", "thing"]
    pts: list[tuple[float, float]] = Field(default_factory=list)  # poly / seg corners, rect: [x, y] + [w, h]
    c: Optional[tuple[float, float]] = None   # circle / dot / body centre
    r: float = 0.0
    d: str = ""                               # path data (a sampled curve; a solid's visible edges)
    d2: str = ""                              # a solid's hidden edges (drawn dashed)
    angle: float = 0.0                        # rect / body rotation (degrees)
    flip: bool = False                        # a body's picture faces left (it moves west)
    label_at: Optional[tuple[float, float]] = None
    note: str = ""                            # a computed value printed beside the label ("(2, 4)" on a curve)
    dims: list[tuple[float, float, str]] = Field(default_factory=list)  # said sizes printed on the shape ("4 cm")
    wh: Optional[tuple[float, float]] = None  # a thing's picture box (w, h) centred on c
    z: int = 0                                # drawing order (behind < 0 < in front)
    hidden: bool = False                      # a part: not drawn on the stage (a focused part: the magnifier)
    glass: bool = False                       # a shape with something inside it: drawn see-through
    ground: Optional[float] = None            # y of the ground under it (its shadow), None: no shadow


class Entity(_Model):
    id: str = Field(pattern=ID_PATTERN)
    kind: str
    name: str = ""                            # the teacher's word for it ("" = none said)
    label: Label = Field(default_factory=Label)
    props: dict[str, Q] = Field(default_factory=dict)
    expr: str = ""                            # a curve: y as an expression in x (scene.worlds.plot parses it)
    expr_shown: str = ""                      # the expression as printed ("" = a number in it was not said)
    look: Look = Field(default_factory=Look)
    dir: str = ""                             # a velocity's direction as said (DIRS; "" = the world's default)
    toward: str = ""                          # tilted from `dir` toward this direction by the `angle` prop
    size: str = ""                            # F-016 a thing's SIZES word ("" = medium)
    geom: Optional[Geom] = None               # engine output


class Relation(_Model):
    kind: str
    a: str
    b: str
    c: str = ""                               # between: the second one


class Behavior(_Model):
    kind: str
    target: str
    params: dict[str, Q] = Field(default_factory=dict)
    b: str = ""                               # follow / chase / orbit / move_to / collide: the other entity
    text: str = ""                            # emit: what (EMITS); transform_into: the said noun it becomes


class Track(_Model):
    """One moving entity's path, sampled by the motion engine: [t s, x px, y px, angle deg, v m/s, distance m]."""
    id: str
    pts: list[tuple[float, float, float, float, float, float]] = Field(default_factory=list)
    sa: list[tuple[float, float, float]] = Field(default_factory=list)  # F-016 per sample: scale x, scale y, opacity


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


class Vec(_Model):
    """A velocity drawn as an arrow (stage px), its words: whose velocity, and its speed when it is known."""
    x0: float
    y0: float
    x1: float
    y1: float
    text: str = ""
    role: Literal["main", "second", "third", "accent", "muted"] = "main"
    at: Optional[tuple[float, float]] = None   # where its words stand (outside the triangle)
    anchor: Literal["start", "middle", "end"] = "middle"


class Stage(_Model):
    """Engine output besides the entities: plot axes, a motion world's ground line (stage px)."""
    axes: Optional[Axes] = None
    ground: Optional[tuple[float, float, float]] = None  # x0, x1, y
    lanes: list[float] = Field(default_factory=list)
    trails: list[tuple[str, str]] = Field(default_factory=list)  # (entity id, path data): a launch's / fall's whole path
    vectors: list[Vec] = Field(default_factory=list)  # the relative world's velocity triangle
    river: Optional[tuple[float, float, float, float]] = None  # x0, x1, y top, y bottom: the band of water
    flow: Optional[tuple[float, float, float, float]] = None   # the river's flow arrow (x0, y0, x1, y1)
    rain: Optional[tuple[float, float]] = None  # the streaks' angle from the vertical (deg, + leans right) and px/s
    umbrella: Optional[tuple[str, float]] = None  # (entity id, tilt from the vertical in deg): held above that body
    backdrop: Optional["Backdrop"] = None     # F-016 the place
    camera: Optional[tuple[float, float, float, float]] = None  # F-016 focus: the view box (x, y, w, h), None = all
    effects: list["Effect"] = Field(default_factory=list)
    size: Optional[tuple[float, float]] = None  # F-016 the stage's own size (a canvas fills the slide), None: 1100 x 740
    magnifier: Optional["Magnifier"] = None   # F-016 a focused part, shown enlarged in an inset


class Backdrop(_Model):
    """F-016: the place drawn behind a canvas scene (an illustrated backdrop by its type)."""
    type: Literal["plain", "sky", "space", "water", "mountain", "street", "nature", "indoors", "beach", "desert", "snow",
                  "moon", "mars"]
    name: str = ""                            # the said place ("" = not printed)
    photo: str = ""                           # C1b: a landscape photo of the place (/media/<id>.jpg), drawn dimmed
    ground: Optional[float] = None            # y of the ground / sea floor (None: no ground, e.g. sky, space)
    surface: Optional[float] = None           # y of the water's surface (water)


class Magnifier(_Model):
    """F-016: a focused part (part_of) in an inset circle, a leader line from where it is on its whole."""
    of: str                                   # the part's id
    at: tuple[float, float]                   # where the part is on its whole (stage px)
    c: tuple[float, float]                    # the inset's centre
    r: float                                  # the inset's radius


class Effect(_Model):
    """F-016: a drawn effect that follows an entity: emit (bubbles, rings ...), a push / pull arrow."""
    of: str
    kind: Literal["bubbles", "rings", "rays", "smoke", "waves", "sparks", "push", "pull"]
    dir: float = 0.0                          # push / pull: the arrow's direction (deg, 0 = +x, screen)


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
    frame: str = ""                           # the relative world: seen from this entity ("" = the ground)

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
    dir: str = ""
    toward: str = ""
    size: str = ""
    c: str = ""


Stage.model_rebuild()
