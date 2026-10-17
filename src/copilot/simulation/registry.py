"""The template registry and the SimulationSpec union (docs/contracts/simulation-spec.md).

`SimulationSpec` is a discriminated union on `template`, built from the template list: a new template plugs in by
being listed in simulation.templates.ALL; nothing in core, audio, STT or understanding changes (RULES #6).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Annotated, Any, Iterable, Optional, Union

from pydantic import Field, TypeAdapter

from copilot.simulation.base import Origin, SimBase, Template
from copilot.simulation.templates import ALL

TEMPLATES: dict[str, Template] = {t.id: t for t in ALL}
ORDER: tuple[str, ...] = tuple(t.id for t in ALL)  # detection priority

SimulationSpec = Annotated[Union[tuple(t.sim for t in ALL)], Field(discriminator="template")]  # type: ignore[misc]
_ADAPTER: TypeAdapter = TypeAdapter(SimulationSpec)


def validate(data: Any) -> SimBase:
    """A SimulationSpec from a dict (raises pydantic.ValidationError on an unknown template, slot or element)."""
    return _ADAPTER.validate_python(data)


def get(template_id: str) -> Optional[Template]:
    return TEMPLATES.get(template_id)


def template_of(sim: SimBase) -> Template:
    return TEMPLATES[sim.template]


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.lower())
    return re.sub(r"[^a-z0-9 =]+", " ", "".join(c for c in s if not unicodedata.combining(c)))


def search(q: str, limit: int = 10) -> list[Template]:
    """/control template search: every word of the query in the name, subject or aliases (all when empty)."""
    words = _fold(q).split()
    out = []
    for t in ALL:
        hay = _fold(" ".join((t.name, t.subject, t.id.replace("_", " "), *t.aliases)))
        if all(w in hay for w in words):
            out.append(t)
    return out[:limit]


def describe(t: Template) -> dict[str, Any]:
    """The template for /control (Values popover ranges, element toggles)."""
    return {"id": t.id, "name": t.name, "subject": t.subject,
            "slots": [{"name": s.name, "label": s.label, "symbol": s.symbol, "unit": s.unit, "min": s.lo,
                       "max": s.hi, "step": s.step} for s in t.slots],
            "elements": [{"id": e.id, "label": e.label} for e in t.elements]}


def solved(sim: SimBase, toggled: Optional[dict[str, bool]] = None, bump: bool = False) -> SimBase:
    """The spec with labels, derived values, drive numbers and shown elements recomputed from its params (Python is
    the single source of truth for every printed number). toggled: the teacher's element choices, which win over the
    template's defaults. bump: a new motion (rev + 1, from t = 0)."""
    t = template_of(sim)
    sol = t.solve(sim.params, sim.param_source)  # type: ignore[attr-defined]
    default = set(t.default_shown(sim.params, sim.param_source))  # type: ignore[attr-defined]
    toggled = toggled or {}
    shown = [e.id for e in t.elements if toggled.get(e.id, e.id in default)]
    data = sim.model_dump()
    data.update(labels={k: v.model_dump() for k, v in sol.labels.items()},
                derived=[d.model_dump() for d in sol.derived], drive=sol.drive, shown=shown,
                version=sim.version + 1)
    if bump:
        data["playback"] = {**data["playback"], "t": 0.0, "rev": data["playback"]["rev"] + 1}
    return validate(data)


def build(template_id: str, values: Iterable[tuple[str, float, str]] = (), origin: Origin = "cue",
          speed: float = 1.0) -> SimBase:
    """A new simulation: template defaults, then the given values (slot, value, source), solved. A value outside its
    slot's range raises ValueError (the caller reports it as "heard ... - not used")."""
    t = TEMPLATES[template_id]
    params: dict[str, Any] = {}
    sources: dict[str, str] = {}
    for slot, value, source in values:
        params[slot] = value
        sources[slot] = source
    sim = t.sim(params=t.params(**params), param_source=sources, title=t.name, origin=origin,
                playback={"speed": speed})
    return solved(sim)


def with_values(sim: SimBase, values: Iterable[tuple[str, float, str]], toggled: Optional[dict[str, bool]] = None
                ) -> SimBase:
    """Set slots (raises ValueError / ValidationError when a value is out of range); the motion keeps its clock."""
    params = sim.params.model_dump()  # type: ignore[attr-defined]
    sources = dict(sim.param_source)
    for slot, value, source in values:
        params[slot] = value
        sources[slot] = source
    t = template_of(sim)
    old = sim.params.model_dump()  # type: ignore[attr-defined]
    new = sim.model_copy(update={"params": t.params(**params), "param_source": sources})
    return solved(new, toggled, bump=any(params[s] != old[s] for s in t.restart_on))


def switched(sim: SimBase, template_id: str, origin: Origin) -> SimBase:
    """Another template for the same situation (the teacher tilts the surface): the slots both share and the new
    template carries (mass, μ, g) keep their values and sources; the motion starts again (rev + 1)."""
    t = TEMPLATES[template_id]
    old = sim.params.model_dump()  # type: ignore[attr-defined]
    same = template_of(sim).kin == t.kin  # a pendulum's bob mass is not the next block's mass
    keep = [(s, old[s], sim.param_source[s]) for s in t.carry if same and s in old and s in sim.param_source]
    new = build(template_id, keep, origin=origin, speed=sim.playback.speed)
    pb = new.playback.model_copy(update={"rev": sim.playback.rev + 1})
    return new.model_copy(update={"playback": pb, "version": sim.version + 1})
