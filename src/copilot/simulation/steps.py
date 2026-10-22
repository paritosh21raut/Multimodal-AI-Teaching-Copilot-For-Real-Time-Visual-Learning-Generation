"""Process steps (F-014 S3): discrete steps that follow the teacher's speech, deterministic, 0 tokens.

A process template (water cycle, heart, photosynthesis, Bohr atom, neutralisation) lists its steps in order, each with
the words that name it, and its named parts (a chamber, a valve, a gas). This module reads them from a line and moves
the simulation's current step:

    speech   the teacher names a step ("then the water vapour condenses"): it becomes the current one and its name
             prints from now on; a line naming several ("the four stages are evaporation, condensation, ...") names
             them all and the first becomes the current one (an overview, not a walk; user 2026-10-19)
    teacher  Next / Prev in the sim bar: the next / previous drawn step, named (the teacher chose it, like a value set in
             Values)
    auto     after AUTO_AFTER_S without a step word (and only while it plays): the drawn steps in turn, every
             `every_s` simulation seconds, round and round; a step nobody said stays unnamed; a step said or Next / Prev
             ends it

Truthfulness as for values: a step not said is drawn (its arrow, its number) but not named; an optional step
(transpiration, runoff) is not drawn until said. Speech wins over the auto-cycle; nothing names a step ahead of
the teacher.
"""
from __future__ import annotations

import math
import re
from functools import lru_cache
from typing import Optional

from copilot.simulation.base import Cycle, SimBase, Step, StepDef, Template

AUTO_AFTER_S = 20.0  # lecture seconds without a step word before the steps cycle by themselves (user 2026-10-19)


@lru_cache(maxsize=None)
def _rx(words: str) -> "re.Pattern[str]":
    return re.compile(rf"(?:{words})", re.IGNORECASE)


def defs(t: Template, sim: Optional[SimBase] = None) -> tuple[StepDef, ...]:
    """The template's steps; S4: worked out from the values when the template's steps depend on them (routing)."""
    if t.step_defs is not None and sim is not None:
        return t.step_defs(sim.params, sim.param_source)  # type: ignore[attr-defined]
    return t.steps


def heard_steps(t: Template, line: str, sim: Optional[SimBase] = None) -> list[str]:
    """The template's steps this line names, in the order said (each once); the weak words only when none else."""
    for weak in (False, True):
        hits = []
        for d in defs(t, sim):
            words = d.weak if weak else d.words
            m = _rx(words).search(line) if words else None
            if m is not None:
                hits.append((m.start(), d.id))
        if hits:
            return [sid for _, sid in sorted(hits)]
    return []


def heard_parts(t: Template, line: str) -> list[str]:
    return [p.id for p in t.parts if _rx(p.words).search(line)]


def initial(t: Template, sim: Optional[SimBase] = None) -> list[Step]:
    return [Step(id=d.id, optional=d.optional) for d in defs(t, sim)]


def drawn(sim: SimBase) -> list[int]:
    """Indices of the steps drawn now: every step but an optional one not yet said."""
    return [i for i, s in enumerate(sim.steps) if not s.optional or s.source is not None]


def current(sim: SimBase, t_now: float) -> int:
    """The step shown at simulation time t_now (the auto-cycle's, else the one set)."""
    c = sim.cycle
    if sim.step_by != "auto" or c is None:
        return sim.step
    order = drawn(sim)
    if not order:
        return sim.step
    k0 = order.index(c.first) if c.first in order else 0
    return order[(k0 + int(math.floor(max(0.0, t_now - c.t0) / c.every_s))) % len(order)]


def numbered(t: Template, steps: list[Step], sim: Optional[SimBase] = None) -> list[Step]:
    """Numbers (1, 2, ... among the drawn steps), printed tags and names (only of steps said / the teacher's), from
    the template's steps (S4: the ones the values give now; a step keeps its source by its id). Tags: a main step
    keeps its number for good; an optional step said later is the main step before it plus a letter ("1b"), so the
    numbers on the stage never shift (S3 review 15)."""
    old = {s.id: s for s in steps}
    out, n, main, extra = [], 0, 0, 0
    for d in defs(t, sim):
        s = old.get(d.id) or Step(id=d.id, optional=d.optional)
        shown = not d.optional or s.source is not None
        n += 1 if shown else 0
        if not d.optional:
            main, extra = main + 1, 0
            tag = str(main)
        elif shown:
            extra += 1
            tag = f"{main}{chr(ord('a') + extra)}" if main else str(n)
        else:
            tag = ""
        out.append(s.model_copy(update={"n": n if shown else 0, "optional": d.optional, "tag": tag,
                                        "label": d.label if s.source is not None else ""}))
    return out


_NOT_NOW = re.compile(r"\b(?:not|never|yet|before|instead|should|could|would|might|if)\b|n't\b|\?", re.IGNORECASE)


def _in_order(sim: SimBase, ids: list[str], line: str) -> list[str]:
    """An ordered template's steps a line may move to: none when negated or asked ("we don't visit E yet", "should
    we visit D?", "from A we could go to B"), else those up to one past the furthest reached; the path step any time."""
    if _NOT_NOW.search(line):
        return []
    index = {s.id: i for i, s in enumerate(sim.steps)}
    reached = max((i for i, s in enumerate(sim.steps) if s.source is not None), default=-1)
    reached = max(reached, sim.step)
    return [x for x in ids if x == "path" or index.get(x, 99) <= reached + 1]


def said(sim: SimBase, t: Template, line: str) -> Optional[dict]:
    """The update a line makes to the steps and named parts ({} keys of SimBase), None when it names none."""
    ids = heard_steps(t, line, sim)
    parts = [p for p in heard_parts(t, line) if p not in sim.named]
    if not ids and not parts:
        return None
    upd: dict = {}
    if parts:
        upd["named"] = [*sim.named, *parts]
    if ids and t.ordered:
        ids = _in_order(sim, ids, line)
        if not ids and not parts:
            return None
    if ids:
        index = {s.id: i for i, s in enumerate(sim.steps)}
        steps = [s.model_copy(update={"source": s.source or "said"}) if s.id in ids else s for s in sim.steps]
        upd.update(steps=numbered(t, steps, sim), step=index[ids[0]], step_by="speech", cycle=None)
    return upd


def moved(sim: SimBase, t: Template, delta: int, t_now: float) -> dict:
    """The teacher's Next (+1) / Prev (-1): the next drawn step from the one shown now, named as the teacher's."""
    order = drawn(sim)
    if not order:
        return {}
    cur = current(sim, t_now)
    if cur in order:
        k = order.index(cur) + delta
    else:
        k = 0 if delta > 0 else len(order) - 1
    k = max(0, min(len(order) - 1, k))
    i = order[k]
    steps = [s.model_copy(update={"source": s.source or "teacher"}) if j == i else s for j, s in enumerate(sim.steps)]
    return {"steps": numbered(t, steps, sim), "step": i, "step_by": "teacher", "cycle": None}


def cycling(sim: SimBase, t: Template, t_now: float) -> dict:
    """Start the auto-cycle at simulation time t_now from the step shown now (the first drawn when none)."""
    order = drawn(sim)
    if not order:
        return {}
    first = sim.step if sim.step in order else order[0]
    return {"step": first, "step_by": "auto", "cycle": Cycle(t0=t_now, first=first, every_s=t.every_s)}


def frozen(sim: SimBase, t_now: float) -> dict:
    """Leave the auto-cycle where it is now (the step it shows stays the current one, unnamed if nobody said it)."""
    if sim.step_by != "auto":
        return {}
    return {"step": current(sim, t_now), "step_by": "", "cycle": None}
