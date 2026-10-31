"""The stage's LLM delta (F-017 §3, E3): one call per teacher line turns it into stage ops (contract stage-spec §1),
streamed as JSONL, correcting the fast path's draft. The validator checks every op; the delta replaces the line's
draft in the event log (stage.log).

Prompt order (Groq caches a byte-identical prefix): PREFIX first, never changed per call (rules, op grammar, the
closed verb / relation / law / recipe / view lists, six short examples); then the entity table (≤ MAX_ROWS rows),
the last two lines, this line and the draft. Never the transcript (RULES). The model states WHAT and WHO; it never
gives coordinates, sizes or numbers the teacher did not say (a `given` carries the verbatim quote).

Models: the router given (the app builds it with `openai/gpt-oss-20b` first, then `gpt-oss-120b`); every model
failing -> the fast path's draft stays (no fake fallback).
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from copilot.scene.compiler import JsonlStream
from copilot.stage import ops
from copilot.stage.graph import Graph
from copilot.stage.laws import LAWS

log = logging.getLogger(__name__)

MAX_ROWS = 25
MAX_TOKENS = 700       # reasoning (low) + the ops
EST_PROMPT = 1300
TIMEOUT_S = 6.0
RESET: dict = {}       # queued when a retry restarts the stream (compared by identity)


def _laws() -> str:
    out = []
    for s in LAWS.values():
        roles = ", ".join(list(s.roles) + [f"{r}?" for r in s.optional])
        out.append(f" {s.name}({roles}) givens {' '.join(s.syms)}")
    return "\n".join(out)


PREFIX = f"""You turn one line of a teacher's lecture into ops for a live 2D explainer scene. Output ONLY JSONL (one JSON
object per line), no prose. Say WHAT is there and WHO does what; never coordinates, sizes, times or a number the teacher
did not say. The engine places, animates and computes.

Ops:
{{"op":"add","id":"box","kind":"prop","w":"box","attr":["heavy"]}} kind: {" ".join(ops.KINDS)}; w = the noun as said;
  people (and "you") = agent, animals = animal, things and vehicles = prop, floor/road/water = surface, where = place;
  "near": a common stand-in noun when w is rare ("sofa" near "bench")
{{"op":"set","id":"box","w":"crate"}} a correction, or "state": {" ".join(ops.STATES)}
{{"op":"remove","id":"box"}}
{{"op":"relate","a":"box","kind":"on","b":"floor"}} kind: {" ".join(ops.RELATIONS)}
{{"op":"act","id":"push1","verb":"push","agent":"man","obj":"box","dir":"right","manner":"hard"}}
  agent verbs (a person; an animal only walk run sit stand fly swim): {" ".join(ops.AGENT_VERBS)}
  object verbs (agent = the thing): {" ".join(ops.OBJECT_VERBS)}
  dir: left right up down toward:<id> away:<id>; manner: {" ".join(ops.MANNERS)}; another verb: the nearest listed
{{"op":"end","id":"push1"}} an action stops
{{"op":"law","id":"fr","name":"sliding_friction","roles":{{"body":"box","surface":"floor","force_from":"man"}}}}
{_laws()}
{{"op":"given","law":"fr","sym":"F","v":50,"u":"N","q":"with 50 newtons"}} ONLY a number said; q = the exact words
  of the line holding it; u: m/s m/s^2 m s kg N deg km/h
{{"op":"view","mode":"split","ids":["moon","mars"]}} mode: {" ".join(ops.VIEWS)} inset_from:<id>
{{"op":"frame","shot":"focus","ids":["box"]}} shot: {" ".join(ops.SHOTS)}
{{"op":"label","id":"dog","text":"his dog"}} only the teacher's words
{{"op":"unsafe"}} ONLY this, for sexual, gory, hateful, self-harm or drug content

Rules:
- The draft (a fast parser's guess) is already drawn. Output only what it gets wrong or misses: an op with a draft id
  replaces that op; remove a draft id that is wrong. Reuse the scene's ids; he / she / it = who / what was named last.
- A driver or rider: relate agent in (car, bus, boat) or sitting_on (bicycle, horse) the vehicle, act drive.
- A law only when the line is about that physics; a given only with its quote. Rain on a walker: relative_motion.
- Nothing to draw: output nothing.

Examples:
Line: A man pushes a heavy box across a rough floor.
Draft: add man agent, add box prop heavy, add floor surface rough, box on floor, push1 man push box
{{"op":"law","id":"fr","name":"sliding_friction","roles":{{"body":"box","surface":"floor","force_from":"man"}}}}
Line: She throws the ball at 10 metres per second at 30 degrees.
Scene: girl agent girl | ball prop ball | throw1 girl throw ball
{{"op":"law","id":"pr","name":"projectile","roles":{{"body":"ball","launcher":"girl"}}}}
{{"op":"given","law":"pr","sym":"v0","v":10,"u":"m/s","q":"at 10 metres per second"}}
{{"op":"given","law":"pr","sym":"theta","v":30,"u":"deg","q":"at 30 degrees"}}
Line: Think of an elephant sitting on a sofa.
Draft: add elephant animal, add sofa prop
{{"op":"add","id":"sofa","kind":"prop","w":"sofa","near":"bench"}}
{{"op":"relate","a":"elephant","kind":"sitting_on","b":"sofa"}}
{{"op":"act","id":"sit1","verb":"sit","agent":"elephant"}}
Line: A man walks in the rain at 5 m/s and the rain falls at 2 m/s.
Draft: add man agent, add rain prop, walk1 man walk
{{"op":"law","id":"rel","name":"relative_motion","roles":{{"a":"rain","b":"man","observer":"man"}}}}
{{"op":"given","law":"rel","sym":"vb","v":5,"u":"m/s","q":"at 5 m/s"}}
{{"op":"given","law":"rel","sym":"va","v":2,"u":"m/s","q":"falls at 2 m/s"}}
Line: So that is why friction matters.
"""


def table(g: Graph) -> str:
    """The scene as short rows (≤ MAX_ROWS): entities with their placement, active actions, laws with the givens
    already said."""
    rows: list[str] = []
    for e in list(g.ents.values())[-MAX_ROWS:]:
        r = f"{e.id} {e.kind} {e.w}"
        if e.attr:
            r += " (" + ", ".join(e.attr) + ")"
        rel = g.rel(e.id)
        if rel:
            r += f" {rel.kind} {rel.b}"
        rows.append(r)
    for a in g.active():
        rows.append(f"{a.id} {a.agent} {a.verb}" + (f" {a.obj}" if a.obj else ""))
    for law in g.laws.values():
        r = f"{law.id} {law.name}"
        if law.givens:
            r += " " + " ".join(f"{s}={x.v:g}{x.u}" for s, x in law.givens.items())
        rows.append(r)
    return " | ".join(rows[-MAX_ROWS:]) or "(empty)"


def _short(o: dict) -> str:
    """A draft op as the prompt's short form ("add box prop heavy", "box on floor", "push1 man push box")."""
    k = o.get("op")
    if k == "add":
        w = o.get("w", "")
        return " ".join(["add", o.get("id", "")] + ([f"={w}"] if w and w != o.get("id") else []) + [o.get("kind", "")]
                        + list(o.get("attr") or []))
    if k == "relate":
        return f"{o.get('a')} {o.get('kind')} {o.get('b')}"
    if k == "act":
        return " ".join(str(x) for x in (o.get("id"), o.get("agent"), o.get("verb"), o.get("obj"), o.get("dir"),
                                          o.get("manner")) if x)
    if k == "end":
        return f"end {o.get('id')}"
    return json.dumps(o, separators=(",", ":"))


def messages(g: Graph, before: list[str], line: str, draft: list[dict]) -> list[dict[str, str]]:
    tail = [f"Scene: {table(g)}"]
    if before:
        tail.append("Before: " + " / ".join(before[-2:]))
    tail.append(f"Line: {line}")
    tail.append("Draft: " + (", ".join(_short(o) for o in draft) or "(none)"))
    return [{"role": "system", "content": PREFIX}, {"role": "user", "content": "\n".join(tail)}]


@dataclass
class DeltaResult:
    ops: list[dict[str, Any]] = field(default_factory=list)
    tokens: int = 0
    prompt_tokens: int = 0
    cached_tokens: int = 0
    first_op_s: Optional[float] = None
    total_s: float = 0.0
    entry: str = ""

    @property
    def counted(self) -> int:
        """Tokens that count (the cached prefix does not, on Groq)."""
        return self.tokens - self.cached_tokens


class StageDirector:
    """One call per line; on_op is awaited for each op as it streams in (the caller may show progress)."""

    def __init__(self, router: Any) -> None:
        self.router = router

    async def delta(self, g: Graph, before: list[str], line: str, draft: list[dict],
                    on_op: Optional[Callable[[dict], Awaitable[None]]] = None) -> DeltaResult:
        res = DeltaResult()
        parser = JsonlStream()
        t0 = time.monotonic()
        queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()

        def on_text(piece: Optional[str]) -> None:
            if piece is None:  # a retry streams again from the start: ops still queued go too
                parser.reset()
                queue.put_nowait(RESET)
                return
            for obj in parser.feed(piece):
                queue.put_nowait(obj)

        async def consume() -> None:
            while True:
                obj = await queue.get()
                if obj is None:
                    return
                if obj is RESET:
                    res.ops.clear()
                    continue
                if res.first_op_s is None:
                    res.first_op_s = time.monotonic() - t0
                res.ops.append(obj)
                if on_op is not None:
                    await on_op(obj)

        worker = asyncio.create_task(consume())
        try:
            r = await self.router.complete(messages(g, before, line, draft), est_tokens=EST_PROMPT,
                                           max_tokens=MAX_TOKENS, deadline=time.monotonic() + TIMEOUT_S + 2,
                                           timeout_s=TIMEOUT_S, on_text=on_text)
            for obj in parser.finish():
                queue.put_nowait(obj)
            res.prompt_tokens = r.response.prompt_tokens
            res.cached_tokens = r.response.cached_tokens
            res.tokens = r.response.prompt_tokens + r.response.completion_tokens
            res.entry = r.entry
        finally:
            queue.put_nowait(None)
            await worker
        res.total_s = time.monotonic() - t0
        return res


class ReplayDirector:
    """Recorded answers instead of a call (0 tokens): tests and fixture replays. answers: line -> JSONL text (a line
    not recorded -> no ops); `delay_s` imitates the network."""

    def __init__(self, answers: dict[str, str], delay_s: float = 0.0) -> None:
        self.answers = answers
        self.delay_s = delay_s
        self.calls: list[list[dict[str, str]]] = []

    async def delta(self, g: Graph, before: list[str], line: str, draft: list[dict],
                    on_op: Optional[Callable[[dict], Awaitable[None]]] = None) -> DeltaResult:
        self.calls.append(messages(g, before, line, draft))
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        res = DeltaResult(entry="replay")
        parser = JsonlStream()
        for obj in parser.feed(self.answers.get(line.strip(), "")) + parser.finish():
            res.ops.append(obj)
            if on_op is not None:
                await on_op(obj)
        return res
