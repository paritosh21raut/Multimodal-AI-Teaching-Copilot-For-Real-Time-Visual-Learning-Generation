"""SceneCompiler (F-015 L1): one LLM call turns the teacher's lines into SceneOps, streamed as JSONL so the first
shapes appear while the model is still writing.

Context is bounded (RULES): the compact scene (ids, kinds, names, key props), ≤ MAX_LINES lines and the topic; never
the transcript. The model states WHAT is in the scene; it never computes a number (the engines do)."""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

from pydantic import ValidationError

from copilot.scene.spec import BEHAVIORS, KINDS, RELATIONS, SceneOp, SceneSpec
from copilot.simulation.base import fmt

log = logging.getLogger(__name__)

MAX_LINES = 4
MAX_TOKENS = 1400      # reasoning (low) + the ops; ≤ 3k a new scene with the prompt (F-015 targets)
EST_PROMPT = 1000
TIMEOUT_S = 12.0

SYSTEM = f"""You turn a teacher's spoken words into drawing operations for a live classroom diagram.
Output ONLY JSON objects, one per line (JSONL). No prose, no code fences. State WHAT is in the scene; never compute
a number: the engine computes sizes, positions, motion and results.

Ops (fields exactly as shown):
{{"op":"add","id":"s1","kind":"square","name":"square","props":{{"side":[4,"cm"]}}}}
{{"op":"set","id":"b1","props":{{"acceleration":[2,"m/s^2"]}}}}
{{"op":"remove","id":"c1"}}
{{"op":"relate","kind":"inscribed_in","a":"c1","b":"s1"}}
{{"op":"behave","kind":"move","target":"b1"}}
{{"op":"label","id":"s1","text":"ABCD"}}
{{"op":"focus","ids":["c1"]}}

kinds: {" ".join(KINDS)}
props, as [number, unit], ONLY numbers the teacher said (leave a prop out if its number was not said):
 side width height radius diameter length base (cm m mm km, or "" for none) | sides (count) | x y xmin xmax (plain)
 speed (m/s km/h) | acceleration (m/s^2; negative when slowing down) | angle (deg) | height for a fall (m)
 solids: cube (side) | cuboid (length width height) | cylinder, cone (radius or diameter, height) | sphere (radius)
speech units: "mps" = m/s; "mps square", "mps2", "m p s squared" (or "mps" plus a stray letter: "mpsw") = m/s^2;
 "kmph", "km per hour" = km/h
curve: "expr" is y in terms of x, e.g. {{"op":"add","id":"f1","kind":"curve","name":"parabola","expr":"x^2-3"}}
relations (a is placed by b): {" ".join(RELATIONS)}
 inscribed_in = a fits exactly inside b; around = a encloses b exactly; on = point a lies on b
anything that moves is a body: car for a vehicle (car, train, bus, boat, rocket, plane), particle for a person or an
 animal, ball for a ball or a stone, block for a box; never a point or a shape
behaviours (of ball block car particle): {" ".join(BEHAVIORS)}
 move = straight line (speed, acceleration on the body); launch = thrown at an angle (speed, angle); fall = dropped
 from a height (height)

Rules:
- New things get new short ids; change existing things by their id from the scene. "it" = the thing named last.
- name = the teacher's own word for the thing ("ball", "diagonal"); never invent names.
- Only what the lines ask for. Nothing to draw or change: output nothing.

Examples:
Lines: Imagine a square. Now a circle inside it.
{{"op":"add","id":"s1","kind":"square","name":"square"}}
{{"op":"add","id":"c1","kind":"circle","name":"circle"}}
{{"op":"relate","kind":"inscribed_in","a":"c1","b":"s1"}}
Scene: s1 square "square"; c1 circle "circle"
Lines: Now draw its diagonal.
{{"op":"add","id":"d1","kind":"segment","name":"diagonal"}}
{{"op":"relate","kind":"diagonal_of","a":"d1","b":"s1"}}
Lines: Imagine a ball rolling at 3 metres per second.
{{"op":"add","id":"b1","kind":"ball","name":"ball","props":{{"speed":[3,"m/s"]}}}}
{{"op":"behave","kind":"move","target":"b1"}}
Scene: b1 ball "ball" speed=3 m/s; b1 move
Lines: Now it slows down at 0.5 metres per second squared.
{{"op":"set","id":"b1","props":{{"acceleration":[-0.5,"m/s^2"]}}}}
Lines: Imagine a cylinder of radius 3 cm and height 5 cm.
{{"op":"add","id":"y1","kind":"cylinder","name":"cylinder","props":{{"radius":[3,"cm"],"height":[5,"cm"]}}}}
Lines: Consider the graph of y equals x squared, and mark the point where x is 2.
{{"op":"add","id":"f1","kind":"curve","name":"graph","expr":"x^2"}}
{{"op":"add","id":"p1","kind":"point","props":{{"x":[2,""]}}}}
{{"op":"relate","kind":"on","a":"p1","b":"f1"}}"""


def context(scene: Optional[SceneSpec]) -> str:
    """The compact scene: one clause per entity (id kind "name" key=value unit), its relations and behaviours."""
    if scene is None or not scene.entities:
        return "(empty)"
    parts = []
    for e in scene.entities:
        props = " ".join(f"{k}={fmt(q.value)}{(' ' + q.unit) if q.unit else ''}" for k, q in list(e.props.items())[:4]
                         if q.source != "default")
        expr = f" expr={e.expr}" if e.expr else ""
        parts.append(f"{e.id} {e.kind}" + (f' "{e.name}"' if e.name else "") + (f" {props}" if props else "") + expr)
    parts += [f"{r.a} {r.kind} {r.b}" for r in scene.relations]
    parts += [f"{b.target} {b.kind}" for b in scene.behaviors]
    return "; ".join(parts)


def messages(lines: list[str], scene: Optional[SceneSpec], topic: str) -> list[dict[str, str]]:
    said = " ".join(x.strip() for x in lines[-MAX_LINES:] if x.strip())
    user = f"Topic: {topic or '-'}\nScene: {context(scene)}\nLines: {said}"
    return [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]


class JsonlStream:
    """Splits streamed text into JSON objects as soon as each is complete: one per line, also several on one line
    ("}{") or one spread over lines; code fences and prose are skipped. reset(): a retry streams from the start."""

    def __init__(self) -> None:
        self.buf = ""
        self.seen: list[str] = []  # objects already returned (a retried stream does not return them twice)
        self._dec = json.JSONDecoder()

    def reset(self) -> None:
        self.buf = ""

    def feed(self, text: str) -> list[dict[str, Any]]:
        self.buf += text
        out: list[dict[str, Any]] = []
        while True:
            i = self.buf.find("{")
            if i < 0:
                self.buf = ""
                return out
            try:
                obj, end = self._dec.raw_decode(self.buf, i)
            except ValueError:
                nl = self.buf.find("\n", i)
                if nl >= 0 and "{" in self.buf[nl:] and _broken(self.buf[i:nl]):
                    self.buf = self.buf[nl + 1:]  # a broken line: skip it, the next one may be fine
                    continue
                self.buf = self.buf[i:]
                return out
            self.buf = self.buf[end:]
            key = json.dumps(obj, sort_keys=True)
            if isinstance(obj, dict) and key not in self.seen:
                self.seen.append(key)
                out.append(obj)

    def finish(self) -> list[dict[str, Any]]:
        return self.feed("\n")


def _broken(line: str) -> bool:
    """A line that opens and closes its braces but is still not JSON."""
    return line.count("{") > 0 and line.count("{") == line.count("}")


@dataclass
class CompileResult:
    ops: int = 0                      # ops parsed
    bad: list[str] = field(default_factory=list)  # lines that were not a valid op
    tokens: int = 0
    first_op_s: Optional[float] = None
    total_s: float = 0.0
    entry: str = ""


class SceneCompiler:
    """One call per cue / debounced edit. on_op is awaited for each op as it streams in (in order)."""

    def __init__(self, router: Any) -> None:
        self.router = router

    async def compile(self, lines: list[str], scene: Optional[SceneSpec], topic: str,
                      on_op: Callable[[SceneOp], Awaitable[None]]) -> CompileResult:
        import asyncio

        res = CompileResult()
        parser = JsonlStream()
        queue: asyncio.Queue[Optional[dict]] = asyncio.Queue()
        t0 = time.monotonic()

        def on_text(piece: Optional[str]) -> None:
            if piece is None:  # an attempt (re)starts: drop a partial object; ops already applied stay applied
                parser.reset()
                return
            for obj in parser.feed(piece):
                queue.put_nowait(obj)

        async def consume() -> None:
            while True:
                obj = await queue.get()
                if obj is None:
                    return
                try:
                    op = SceneOp.model_validate(obj)
                except ValidationError as err:
                    res.bad.append(f"{json.dumps(obj)[:120]}: {err.errors()[0]['msg']}")
                    continue
                res.ops += 1
                if res.first_op_s is None:
                    res.first_op_s = time.monotonic() - t0
                await on_op(op)

        worker = asyncio.create_task(consume())
        try:
            r = await self.router.complete(messages(lines, scene, topic), est_tokens=EST_PROMPT,
                                           max_tokens=MAX_TOKENS, deadline=time.monotonic() + TIMEOUT_S + 2,
                                           timeout_s=TIMEOUT_S, on_text=on_text)
            for obj in parser.finish():
                queue.put_nowait(obj)
            res.tokens = r.response.prompt_tokens + r.response.completion_tokens
            res.entry = r.entry
        finally:
            queue.put_nowait(None)
            await worker
        res.total_s = time.monotonic() - t0
        return res


class ReplayCompiler:
    """A recorded answer per line instead of an LLM call (0 tokens): screenshots, tests, fixture replays. The text is
    streamed through the same JsonlStream in small pieces, so the parse and the op-by-op path are the live ones.
    answers: the line (the last of the call's lines) -> the model's JSONL text; a line not recorded -> no ops."""

    def __init__(self, answers: dict[str, str], piece: int = 23) -> None:
        self.answers = answers
        self.piece = piece
        self.calls: list[list[str]] = []

    async def compile(self, lines: list[str], scene: Optional[SceneSpec], topic: str,
                      on_op: Callable[[SceneOp], Awaitable[None]]) -> CompileResult:
        self.calls.append(list(lines))
        res = CompileResult(entry="replay")
        text = self.answers.get(lines[-1].strip(), "") if lines else ""
        parser = JsonlStream()
        t0 = time.monotonic()
        objs: list[dict] = []
        for i in range(0, len(text), self.piece):
            objs += parser.feed(text[i:i + self.piece])
        objs += parser.finish()
        for obj in objs:
            try:
                op = SceneOp.model_validate(obj)
            except ValidationError as err:
                res.bad.append(f"{json.dumps(obj)[:120]}: {err.errors()[0]['msg']}")
                continue
            res.ops += 1
            if res.first_op_s is None:
                res.first_op_s = time.monotonic() - t0
            await on_op(op)
        res.total_s = time.monotonic() - t0
        return res
