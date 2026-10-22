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

from copilot.scene.spec import ACTIONS, CANVAS_RELATIONS, EMITS, KINDS, SIZES, SceneOp, SceneSpec
from copilot.simulation.base import fmt

log = logging.getLogger(__name__)

MAX_LINES = 4
MAX_TOKENS = 1400      # reasoning (low) + the ops; ≤ 3k a new scene with the prompt (F-015 targets)
EST_PROMPT = 2100
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
{{"op":"frame","id":"m1"}}   (show the scene as seen by m1; "id":"" = as seen from the ground)
{{"op":"unsafe"}}   (ONLY this, when the lines ask for sexual, gory, hateful, self-harm or drug content)

kinds: {" ".join(KINDS)}
props, as [number, unit], ONLY numbers the teacher said (leave a prop out if its number was not said):
 side width height radius diameter length base (cm m mm km, or "" for none) | sides (count) | x y xmin xmax (plain)
 speed (m/s km/h) | acceleration (m/s^2; negative when slowing down) | angle (deg) | height for a fall (m)
 gap (m: the distance between two bodies) | length (m: a train's length) | width (m: a river's width)
 solids: cube (side) | cuboid (length width height) | cylinder, cone (radius or diameter, height) | sphere (radius)
speech units: "mps" = m/s; "mps square", "mps2", "m p s squared" (or "mps" plus a stray letter: "mpsw") = m/s^2;
 "kmph", "km per hour" = km/h
curve: "expr" is y in terms of x, e.g. {{"op":"add","id":"f1","kind":"curve","name":"parabola","expr":"x^2-3"}}
relations of shapes (a is placed by b): inscribed_in around inside on diagonal_of radius_of diameter_of tangent_to
 bisector_of midpoint_of left_of right_of above below
 inscribed_in = a fits exactly inside b; around = a encloses b exactly; on = point a lies on b
a textbook motion problem (a ball rolls at 3 m/s, trains, a boat crossing a river, a man in the rain) uses bodies:
 car for a vehicle, particle for a person or an animal, ball for a ball or a stone, block for a box; name = the
 teacher's noun ("rocket", "man"): the picture follows the name
EVERYTHING ELSE the teacher imagines is a "thing": name = the teacher's noun, as said ("laptop", "cat", "you"),
 "size": {" ".join(SIZES)} (its size next to the others; leave it out if unsure). ONE "place" per scene = where it
 happens (ocean, sky, space, street, room, forest, beach ...). Something you put things on (mountain, table, plane)
 is a thing, not a place. Parts the teacher names (a bicycle's wheel): a thing with relate part_of
relations of things: {" ".join(CANVAS_RELATIONS)} inside above below left_of right_of
 (between also takes "c": the second thing; at / inside / under / on / above / below may take the place as b)
actions (behave, target a thing or a body; "b" = the other thing for move_to follow chase orbit collide):
 {" ".join(ACTIONS)} move launch fall
 emit "text": {" ".join(EMITS)}; transform_into "text": the noun it becomes. An unknown verb: the nearest action
 ("zooms" = fly, "drops" = fall, "tosses" = throw, "hits" = collide, "swims" = move). Thrown up: "dir":"up"
focus: "look at / zoom into the X" = {{"op":"focus","ids":["x1"]}}; "zoom out" = {{"op":"focus","ids":[]}}
direction (on add / set of a body, a river or rain, only when the teacher says one): "dir": east west north south up
 down; "at 30 degrees to the vertical towards the east" = "dir":"down","toward":"east" with props angle [30,"deg"]
river: a band of water; its speed is the flow; rain: falls ("dir":"down" unless said otherwise)
two bodies on one line: add first the one on the left (or behind), with the gap between them on it
behaviours of bodies: move launch fall cross cross_straight
 move = straight line (speed, acceleration on the body); launch = thrown at an angle (speed, angle); fall = dropped
 from a height (height); cross = a boat heads straight across the river (shortest time); cross_straight = it heads
 upstream so that it reaches the point straight opposite (shortest path)

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
{{"op":"relate","kind":"on","a":"p1","b":"f1"}}
Lines: Rain falls vertically at 3 m/s. A man walks east at 4 m/s. How does the rain look to him?
{{"op":"add","id":"r1","kind":"rain","name":"rain","props":{{"speed":[3,"m/s"]}},"dir":"down"}}
{{"op":"add","id":"m1","kind":"particle","name":"man","props":{{"speed":[4,"m/s"]}},"dir":"east"}}
{{"op":"behave","kind":"move","target":"m1"}}
{{"op":"frame","id":"m1"}}
Lines: A river 100 m wide flows at 3 m/s. A boat that goes 5 m/s in still water crosses it in the shortest time.
{{"op":"add","id":"r1","kind":"river","name":"river","props":{{"width":[100,"m"],"speed":[3,"m/s"]}}}}
{{"op":"add","id":"b1","kind":"car","name":"boat","props":{{"speed":[5,"m/s"]}}}}
{{"op":"behave","kind":"cross","target":"b1"}}
Lines: Two trains 200 m apart run towards each other at 20 m/s and 30 m/s.
{{"op":"add","id":"t1","kind":"car","name":"train","props":{{"speed":[20,"m/s"],"gap":[200,"m"]}},"dir":"east"}}
{{"op":"add","id":"t2","kind":"car","name":"train","props":{{"speed":[30,"m/s"]}},"dir":"west"}}
{{"op":"behave","kind":"move","target":"t1"}}
{{"op":"behave","kind":"move","target":"t2"}}
Lines: Imagine a cube on a mountain.
{{"op":"add","id":"m1","kind":"thing","name":"mountain","size":"huge"}}
{{"op":"add","id":"c1","kind":"thing","name":"cube","size":"small"}}
{{"op":"relate","kind":"on_top_of","a":"c1","b":"m1"}}
Lines: Picture a bicycle under the ocean.
{{"op":"add","id":"o1","kind":"place","name":"ocean"}}
{{"op":"add","id":"b1","kind":"thing","name":"bicycle"}}
{{"op":"relate","kind":"under","a":"b1","b":"o1"}}
Lines: Imagine a laptop flying on top of an airplane.
{{"op":"add","id":"p1","kind":"thing","name":"airplane","size":"large"}}
{{"op":"add","id":"l1","kind":"thing","name":"laptop","size":"small"}}
{{"op":"relate","kind":"on_top_of","a":"l1","b":"p1"}}
{{"op":"behave","kind":"fly","target":"p1"}}
Lines: Suppose you throw a book up in the air.
{{"op":"add","id":"k1","kind":"thing","name":"book","dir":"up"}}
{{"op":"behave","kind":"throw","target":"k1"}}
Lines: Imagine you're on a bus and it brakes.
{{"op":"add","id":"u1","kind":"thing","name":"bus","size":"large"}}
{{"op":"add","id":"y1","kind":"thing","name":"you","size":"small"}}
{{"op":"relate","kind":"inside","a":"y1","b":"u1"}}
{{"op":"behave","kind":"brake","target":"u1"}}
Scene: u1 thing "bus"; y1 thing "you"; y1 inside u1; u1 brake
Lines: Look at the person inside.
{{"op":"focus","ids":["y1"]}}"""


def context(scene: Optional[SceneSpec]) -> str:
    """The compact scene: one clause per entity (id kind "name" key=value unit), its relations and behaviours."""
    if scene is None or not scene.entities:
        return "(empty)"
    parts = []
    for e in scene.entities:
        props = " ".join(f"{k}={fmt(q.value)}{(' ' + q.unit) if q.unit else ''}" for k, q in list(e.props.items())[:4]
                         if q.source != "default")
        expr = f" expr={e.expr}" if e.expr else ""
        way = f" dir={e.dir}" + (f" toward={e.toward}" if e.toward else "") if e.dir else ""
        name = e.name or e.look.noun  # a thing's noun, said or not (the model refers to it)
        parts.append(f"{e.id} {e.kind}" + (f' "{name}"' if name else "") + (f" {e.size}" if e.size else "")
                     + (f" {props}" if props else "") + expr + way)
    parts += [f"{r.a} {r.kind} {r.b}" + (f" {r.c}" if r.c else "") for r in scene.relations]
    parts += [f"{b.target} {b.kind}" + (f" {b.b}" if b.b else "") + (f" {b.text}" if b.text else "")
              for b in scene.behaviors]
    if scene.frame:
        parts.append(f"seen by {scene.frame}")
    if scene.focus:
        parts.append("focus " + " ".join(scene.focus))
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
