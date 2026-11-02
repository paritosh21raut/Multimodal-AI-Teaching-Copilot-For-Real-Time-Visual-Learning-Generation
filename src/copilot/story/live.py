"""The live story animation of one open story (V3 P1c, docs/v3/P1c-live-wiring.md): one World, one Compiler and the
last two lines. A heard line -> one scene call (scene_llm.step: the LLM states WHAT changes, world.validate takes it
whole or not at all) -> the compiler (Python computes every position, time and curve) -> the shot the display plays.

A refused line changes nothing: the last shot stays on screen and the reason is kept (never a made-up motion).
Gender: a person the model left without one gets the cast's (ST2, from said words) when the names match.
"""
from __future__ import annotations

import difflib
import json
import logging
import time
from dataclasses import dataclass, field, replace
from typing import Any, Optional

from copilot.story import world as W
from copilot.story.compile import Compiler
from copilot.story.scene_llm import messages

log = logging.getLogger(__name__)
SAME_NAME = 0.75     # "Rabi" ~ "Ravi" (0.75), same first letter (the fast path's cast: presentation/story.py)


@dataclass
class Shot:
    spec: Optional[dict[str, Any]] = None   # the compiled spec (None: refused, nothing changes)
    why: str = ""                           # the refusal reason
    tokens: int = 0
    secs: float = 0.0                       # the scene call + the compile
    same: bool = False                      # taken, but nothing changed (no event, entity or relation): no new shot


@dataclass
class StoryAnim:
    reader: Any                             # scene_llm.SceneReader / ReplaySceneReader
    world: W.World = field(default_factory=W.World)
    comp: Compiler = field(default_factory=Compiler)
    before: list[str] = field(default_factory=list)
    n: int = 0                              # shots made

    async def read(self, line: str, genders: Optional[dict[str, str]] = None) -> Shot:
        t0 = time.perf_counter()
        was = (set(self.world.entities), list(self.world.relations))
        try:
            res, why = await self._step(line)
        finally:
            self.before = (self.before + [line])[-2:]
        shot = Shot(why=why, tokens=res.tokens)
        if why == "empty" or (not why and not self.world.events
                              and was == (set(self.world.entities), list(self.world.relations))):
            shot.same, shot.why = True, ""   # the model read nothing to change: not a refusal, the shot plays on
        elif not why:
            self._genders(genders or {})
            try:
                spec = self.comp.compile(self.world, line)
            except Exception:   # review: the world moved on, the placements did not: place them again from the world
                log.exception("[STORY] compile failed for %r: the stage is placed again from the world", line[:60])
                self.comp = Compiler()
                spec = self.comp.compile(self.world, line)
            self.n += 1
            shot.spec = {**spec, "n": self.n}
        shot.secs = time.perf_counter() - t0
        return shot

    async def _step(self, line: str):
        """scene_llm.step + one rule: a new named person whose name is near a named person of the world is that
        person (STT "Rabi" then "Ravi"; the fast path's cast does the same)."""
        rev = self.world.rev
        res = await self.reader.read(messages(self.world, self.before, line), line)
        if res.answer is None:
            return res, "no JSON"
        log.info("[STORY] anim answer %r: %s", line[:60], json.dumps(res.answer, separators=(",", ":"))[:1500])  # replay
        delta, why = W.validate(res.answer, self.world, line, rev=rev)
        if delta is None:
            return res, why
        self._same_names(delta)
        if self.world.rev != rev or not self.world.apply(delta):
            return res, "stale"
        return res, ""

    def _same_names(self, d: W.Delta) -> None:
        named = [e for e in self.world.entities.values() if e.kind == "person" and e.name[:1].isupper()]
        alias: dict[str, str] = {}
        for e in d.new:
            if e.kind != "person" or not e.name[:1].isupper() or len(e.name.split()) > 2:
                continue
            for o in named:
                a, b = e.name.lower(), o.name.lower()
                if a[:1] == b[:1] and (a == b or difflib.SequenceMatcher(None, a, b).ratio() >= SAME_NAME):
                    alias[e.id] = o.id
                    log.info("[STORY] anim: %r is %r (a name like it), %s -> %s", e.name, o.name, e.id, o.id)
                    break
        if not alias:
            return
        f = lambda i: alias.get(i, i)  # noqa: E731
        d.new = [e for e in d.new if e.id not in alias]
        d.events = [replace(ev, actor=f(ev.actor), target=f(ev.target), obj=f(ev.obj)) for ev in d.events]
        d.relations = [replace(r, a=f(r.a), b=f(r.b), c=f(r.c)) for r in d.relations]
        d.end = [replace(r, a=f(r.a), b=f(r.b), c=f(r.c)) for r in d.end]

    def _genders(self, genders: dict[str, str]) -> None:
        """The cast's gender (said pronouns / nouns) for a person the model gave none; only on an exact name."""
        low = {k.lower(): g for k, g in genders.items() if g in ("he", "she")}
        for e in self.world.entities.values():
            if e.kind != "person" or e.gender:
                continue
            for said in (e.name, e.noun):
                g = low.get(said.lower().strip()) if said else None
                if g:
                    e.gender = g
                    break
