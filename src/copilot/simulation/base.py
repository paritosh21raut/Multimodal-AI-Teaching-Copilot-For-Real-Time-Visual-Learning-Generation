"""The simulation contract's shared parts (docs/contracts/simulation-spec.md).

Python is the single source of truth for every number on the projector: a solver turns the parameters into
`labels` (values printed beside an element), `derived` (computed readouts) and `drive` (numbers that only move the
picture and are never printed). The renderer (web/sims/) prints `labels` / `derived` text as it is and never
formats a number of its own.

Truthfulness: a parameter's `source` says where its value came from. Only said / teacher values are printed; a
computed value is printed (marked computed) only when every input it depends on is known (said, teacher or a
standard constant such as g). A default moves the picture and is never printed.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

# mentioned: the thing is there but its number was not said ("from a cliff", "pushed at an angle"): the picture
# shows Slot.present_value, nothing that depends on it is printed
ParamSource = Literal["said", "teacher", "computed", "default", "standard", "mentioned"]
# inputs a printed computed value may rest on; computed (S2): worked out from a value said in another form ("the
# period is 0.2 s" -> f = 5 Hz), printed marked computed
KNOWN: frozenset[str] = frozenset({"said", "teacher", "standard", "computed"})
LabelSource = Literal["said", "teacher", "computed"]
Origin = Literal["cue", "policy", "llm", "teacher"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SimLabel(_Model):
    """What is printed beside an element: its symbol, and its value only when known ("F" / "F = 20 N")."""
    symbol: str = ""
    text: str = ""                    # "20 N"; "" = the symbol alone (the value is a default or not yet known)
    source: Optional[LabelSource] = None  # None when text is ""


class Derived(_Model):
    """A computed readout ("Acceleration", a = 2.04 m/s²), printed and marked computed."""
    id: str
    label: str
    symbol: str
    value: float
    unit: str = ""
    text: str                         # value + unit as printed ("2.04 m/s²", "3.21 m/s² down the slope")


MAX_POINTS = 400  # points in one graph (all its lines): enough for a smooth curve on the projector, small to patch


class Tick(_Model):
    """A number on a graph axis, as printed (Python formats it; the client never does)."""
    value: float
    text: str


class Line(_Model):
    """One curve of a graph. A time graph's curve is drawn up to the clock's time, a cursor on it."""
    id: str
    label: str = ""                   # its name when a graph has several ("R₁"); "" = the graph's only curve
    role: str = "ink"                 # colour role (tokens.css --sim-*), as the arrows'
    xs: list[float]
    ys: list[float]
    mark: Optional[tuple[float, float]] = None  # a point marked on it (the circuit's working point: I, V)

    @model_validator(mode="after")
    def _same_length(self) -> "Line":
        if len(self.xs) != len(self.ys) or len(self.xs) < 2:
            raise ValueError("a line needs xs and ys of one length (at least 2 points)")
        return self


class Series(_Model):
    """A graph beside the motion (F-014 S2): x-t, v-t, θ-t, V-I. The solver samples it; the client only draws it. Its
    axis numbers (ticks) are there only when every input the curve rests on is known: else the shape alone."""
    id: str                           # "x_t", "v_t", "theta_t", "V_I"
    title: str                        # "Position–time"
    x_symbol: str
    x_unit: str = ""
    y_symbol: str
    y_unit: str = ""
    time: bool = True                 # x is the time: drawn up to the scene's clock (web/sims scene.graphTime)
    x_scale: float = 1.0              # a time graph's x units per second (1000 when it is in ms)
    x_range: tuple[float, float]
    y_range: tuple[float, float]
    x_ticks: list[Tick] = Field(default_factory=list)
    y_ticks: list[Tick] = Field(default_factory=list)
    lines: list[Line] = Field(min_length=1, max_length=3)

    @model_validator(mode="after")
    def _bounded(self) -> "Series":
        if sum(len(ln.xs) for ln in self.lines) > MAX_POINTS:
            raise ValueError(f"a graph holds at most {MAX_POINTS} points")
        nums = [*self.x_range, *self.y_range] + [v for ln in self.lines for v in (*ln.xs, *ln.ys)]
        if any(not math.isfinite(v) for v in nums):
            raise ValueError("graph values must be finite")
        if not (self.x_range[1] > self.x_range[0] and self.y_range[1] > self.y_range[0]):
            raise ValueError("an empty graph range")
        return self


class Annotation(_Model):
    target: str                       # an element id
    text: str
    source: Literal["said", "added"] = "said"  # an added note renders subtle (V1 rule)


class Playback(_Model):
    """Server-authoritative clock state. Every client anchors its own clock at `t` when `rev` changes and runs on
    from there while playing, so a patch that changes only values never restarts the motion."""
    state: Literal["playing", "paused"] = "playing"
    speed: float = Field(default=1.0, ge=0.25, le=2.0)
    t: float = Field(default=0.0, ge=0.0)   # simulation seconds at the last change of state
    rev: int = Field(default=0, ge=0)       # bumped by play / pause / step / reset / a new motion (switch)


class SimBase(_Model):
    """Fields every template's spec has; a template subclasses it with `template: Literal[id]` and `params`."""
    template: str
    version: int = Field(default=0, ge=0)
    title: str = ""
    language: str = "en"
    param_source: dict[str, ParamSource] = Field(default_factory=dict)
    shown: list[str] = Field(default_factory=list)          # elements drawn (progressive reveal, teacher toggles)
    labels: dict[str, SimLabel] = Field(default_factory=dict)
    derived: list[Derived] = Field(default_factory=list)
    drive: dict[str, float] = Field(default_factory=dict)   # never printed
    series: list[Series] = Field(default_factory=list, max_length=2)  # the graph element's curves (S2)
    annotations: list[Annotation] = Field(default_factory=list, max_length=3)
    playback: Playback = Field(default_factory=Playback)
    origin: Origin = "cue"

    ELEMENTS: ClassVar[tuple[str, ...]] = ()
    LABELS: ClassVar[tuple[str, ...]] = ()  # label keys beyond the elements (parts of one element: "w_par", "w_perp")

    @model_validator(mode="after")
    def _known_names(self) -> "SimBase":
        params = getattr(self, "params", None)
        slots = set(type(params).model_fields) if params is not None else set()
        bad = [s for s in self.param_source if s not in slots]
        if bad:
            raise ValueError(f"unknown slot(s) in param_source: {bad}")
        elements = set(self.ELEMENTS)
        for what, names, ok in (("shown", self.shown, elements),
                                 ("labels", list(self.labels), elements | set(self.LABELS)),
                                 ("annotation targets", [a.target for a in self.annotations], elements)):
            bad = [n for n in names if n not in ok]
            if bad:
                raise ValueError(f"unknown element(s) in {what}: {bad}")
        if len(set(self.shown)) != len(self.shown):
            raise ValueError("shown has duplicates")
        if any(not math.isfinite(v) for v in self.drive.values()):
            raise ValueError("drive values must be finite")
        return self


@dataclass(frozen=True)
class Slot:
    """One parameter of a template: its range (the params model enforces the same, tests check they agree), how a
    spoken value reaches it (`kind`, see simulation.values) and its default."""
    name: str            # params field ("mass_kg")
    label: str           # "Mass"
    symbol: str          # "m"
    unit: str            # "kg" ("" = none)
    lo: float
    hi: float
    step: float
    default: float
    kind: str            # mass | angle | force | mu | g (simulation.values)
    standard: bool = False  # a textbook constant (g): its default counts as known, never printed unless said
    absent: bool = False    # the default means "there is none" (no push: F = 0): known while it stays at the default
    present: str = ""       # regex: the thing is there, its number unsaid ("cliff": a height) -> source mentioned
    present_value: float = 0.0  # the picture's stand-in then (never printed)
    names: str = ""         # regex of the words that name it ("push(?:ing)? force|applied force"): a value said
    #                         without a unit, a slot only mentioned, "double the mass" (simulation.values.resolve)
    follows: str = ""       # an angle of one force (S2: the push's or the pull's): an angle said goes to the angle of
    #                         the force said nearest before it in the line, else of the force changed last


@dataclass(frozen=True)
class Element:
    id: str
    label: str           # /control toggles ("Friction")


@dataclass
class Solution:
    drive: dict[str, float]
    labels: dict[str, SimLabel] = field(default_factory=dict)
    derived: list[Derived] = field(default_factory=list)
    series: list[Series] = field(default_factory=list)


def fmt(x: float, sig: int = 3) -> str:
    """A value as printed: `sig` significant figures, no exponent in the classroom range, no trailing zeros; whole
    numbers are never rounded to tens (49.05 -> "49.1", 2.038 -> "2.04", 20.0 -> "20", 0.2 -> "0.2", 1234.5 -> "1235")."""
    if not math.isfinite(x):
        return "?"
    ax = abs(x)
    if ax < 5e-4:  # never "5e-05" on a projector: a rounding error at a limit, or a value too small to read
        return "0" if ax < 1e-9 else "≈ 0"
    if ax >= 1e6:
        return f"{x:.{sig}g}"
    digits = max(0, sig - 1 - math.floor(math.log10(ax)))
    s = f"{x + math.copysign(1e-12, x):.{digits}f}"  # 49.05 is 49.04999... in binary: round half up as on paper
    return s.rstrip("0").rstrip(".") if "." in s else s


def nice_ticks(lo: float, hi: float, n: int = 4) -> list[Tick]:
    """Round numbers along [lo, hi] (about n of them, 0 included when inside), printed by fmt."""
    span = hi - lo
    if not (span > 0 and math.isfinite(span)):
        return []
    raw = span / n
    mag = 10 ** math.floor(math.log10(raw))
    step = next(k * mag for k in (1, 2, 2.5, 5, 10) if k * mag >= raw)
    first = math.ceil(lo / step - 1e-9) * step
    out, v = [], first
    while v <= hi + step * 1e-9:
        x = 0.0 if abs(v) < step * 1e-9 else v
        out.append(Tick(value=x, text=fmt(x)))
        v += step
    return out


def graph(id: str, title: str, x: tuple[str, str], y: tuple[str, str], lines: list[Line], printable: bool,
          time: bool = True, y_floor: Optional[float] = None) -> Series:
    """A Series around its lines: ranges with a little room above and below, ticks only when printable. x / y:
    (symbol, unit)."""
    xs = [v for ln in lines for v in ln.xs]
    ys = [v for ln in lines for v in ln.ys] + [ln.mark[1] for ln in lines if ln.mark]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys), max(ys)
    if y_floor is not None:
        y0 = min(y0, y_floor)
    if y1 - y0 < 1e-12:  # a flat line (at rest): a band around it
        pad = max(1.0, abs(y0)) * 0.5
        y0, y1 = y0 - pad, y1 + pad
    else:
        pad = (y1 - y0) * 0.08
        y0, y1 = (y0 - pad if y0 < -1e-12 else y0), y1 + pad
    if x1 - x0 < 1e-12:
        x1 = x0 + 1.0
    return Series(id=id, title=title, x_symbol=x[0], x_unit=x[1], y_symbol=y[0], y_unit=y[1], time=time,
                  x_range=(x0, x1), y_range=(y0, y1),
                  x_ticks=nice_ticks(x0, x1) if printable else [], y_ticks=nice_ticks(y0, y1) if printable else [],
                  lines=lines)


def time_axis(t1: float) -> tuple[str, float]:
    """The unit of a time axis ending at t1 s and its scale: s, ms or µs (a fast wave is never "≈ 0 s")."""
    return ("s", 1.0) if t1 >= 0.1 else ("ms", 1e3) if t1 >= 1e-4 else ("µs", 1e6)


def time_graph(id: str, title: str, y: tuple[str, str], ts: list[float], ys: list[float], printable: bool,
               role: str = "ink") -> Series:
    """A curve against the time from 0 (s, ms or µs), drawn up to the clock with a cursor."""
    unit, k = time_axis(ts[-1])
    s = graph(id, title, ("t", unit), y, [Line(id=id, role=role, xs=[t * k for t in ts], ys=ys)], printable)
    return s.model_copy(update={"x_scale": k})


def run_graphs(a: float, moving: bool, track_m: float, printable: bool) -> list[Series]:
    """Distance-time and velocity-time of one run of a block along its track from rest, as the stage plays it
    (web/sims/runtime.js makeTrack: from rest at constant a over track_m, then again). At rest: both stay 0."""
    t1 = math.sqrt(2 * track_m / a) if moving and a > 1e-9 else 3.0
    ts, ss = sampled(lambda t: 0.5 * a * t * t if moving else 0.0, 0.0, t1)
    _, vs = sampled(lambda t: a * t if moving else 0.0, 0.0, t1)
    return [time_graph("s_t", "Distance–time", ("s", "m"), ts, ss, printable),
            time_graph("v_t", "Velocity–time", ("v", "m/s"), ts, vs, printable, role="applied")]


def sampled(fn: Callable[[float], float], t0: float, t1: float, n: int = 160) -> tuple[list[float], list[float]]:
    """fn at n + 1 evenly spaced times over [t0, t1]."""
    ts = [t0 + (t1 - t0) * i / n for i in range(n + 1)]
    return ts, [fn(t) for t in ts]


def known(sources: dict[str, str], slots: dict[str, Slot], *names: str) -> bool:
    """Is every named input said, set by the teacher or a standard constant left at its standard value?"""
    for n in names:
        src = sources.get(n, "default")
        if src in KNOWN or (src == "default" and (slots[n].standard or slots[n].absent)):
            continue
        return False
    return True


def value_label(symbol: str, value: float, unit: str, source: str, printable: bool) -> SimLabel:
    """A label with the value when printable ("F = 20 N"), else the symbol alone."""
    if not printable:
        return SimLabel(symbol=symbol)
    text = f"{fmt(value)}{unit if unit in ('°',) else (' ' + unit if unit else '')}"
    return SimLabel(symbol=symbol, text=text, source="computed" if source not in ("said", "teacher") else source)


Solver = Callable[[BaseModel, dict[str, str]], Solution]


@dataclass(frozen=True)
class Read:
    """S2: a value of this kind said in another form, by the words around it (simulation.values.resolve). slot: the
    slot it sets, as value * factor (or 1 / value when inverse); "" = not an input ("the string is 3 m long" is not
    the wavelength). A value changed on the way (inverse or factor != 1) is computed."""
    kind: str                 # the heard kind (time, length, ...)
    before: str               # regex on the words before the value, in its clause (end-anchored as needed)
    slot: str = ""
    factor: float = 1.0
    inverse: bool = False
    after: str = ""           # regex the words after it must match ("" = anything)

    @property
    def computed(self) -> bool:
        return self.inverse or self.factor != 1.0


@dataclass(frozen=True)
class Template:
    """One registry entry (simulation.registry). Adding a template = one of these + web/sims/<id>.js + the fixed test
    checklist (solver vs textbook values, detector positives / negatives, browser render in both themes, screenshot).

    Detection (simulation.detector), all on one transcript line:
      setup     names this scenario ("an inclined plane", "a block ... on a rough surface"); with a spoken cue
                ("consider", "let me show you") it shows the simulation
      lexicon   its quantities and verbs ("friction", "slides", "push"): keeps an open simulation listening
      guard     vetoes the line (traps: "block diagram", "block of code", "human body")
    """
    id: str
    name: str                                   # "Block on an incline" (/control, the stage caption)
    subject: str                                # "mechanics"
    sim: type[SimBase]
    params: type[BaseModel]
    slots: tuple[Slot, ...]
    elements: tuple[Element, ...]
    solve: Solver
    default_shown: Callable[[BaseModel, dict[str, str]], list[str]]
    setup: "re.Pattern[str]"
    lexicon: "re.Pattern[str]"
    guard: Optional["re.Pattern[str]"] = None
    aliases: tuple[str, ...] = ()               # search words for /control
    carry: tuple[str, ...] = ()                 # slots taken over when the teacher switches to this template
    # slots whose change starts the motion again from its start (rev + 1, t = 0) on every page: a pendulum whose
    # length changes mid-swing would jump (its period changes), so it is released again
    restart_on: tuple[str, ...] = ()
    # words before a quantity that make it this scene's result, not an input ("the range is 40 m", "the maximum
    # height is 5 m"): such a value sets nothing
    results: Optional["re.Pattern[str]"] = None
    # words that state a value without a number: (regex, slot, value) ("thrown horizontally": θ = 0)
    said_as: tuple[tuple[str, str, Any], ...] = ()  # a str value: a choice field ("in parallel" -> arrangement)
    family: str = ""                            # templates of one situation (block on a floor / on an incline):
                                                # only these carry values when one switches to another
    # S2: each force's direction choice: (role push | pull, params field, spoken word -> value); spoken words are
    # up | down (the slope) and with | against (the motion), simulation.values
    force_dirs: tuple[tuple[str, str, dict[str, str]], ...] = ()
    reads: tuple[Read, ...] = ()                # S2: values said in another form (Read), tried first

    @property
    def kin(self) -> str:
        return self.family or self.id

    def slot(self, name: str) -> Slot:
        return next(s for s in self.slots if s.name == name)

    @property
    def slot_map(self) -> dict[str, Slot]:
        return {s.name: s for s in self.slots}
