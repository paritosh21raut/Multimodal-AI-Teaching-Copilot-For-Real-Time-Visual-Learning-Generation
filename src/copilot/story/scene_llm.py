"""One story line -> a world delta (ADR-0015 §9, P0 part 1). The LLM states WHAT changes (new entities, events,
relations) against the world it is shown; world.validate() takes the answer whole or not at all; Python applies it.

    prompt   PREFIX first, never changed per call (Groq caches a byte-identical prefix); then the world summary (ids,
             relations, revision), the last two lines and the line. Never the transcript (RULES). The example in the
             prefix is not one of the P0 test sentences (tests/fixtures/story/p0_relations.json).
    output   one JSON object (JSON mode): {"new", "events", "relations", "end"}; the revision it was made against is
             stamped by the caller (P1b: the model's echoed rev was 15 of 21 refusals)
"""
from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Optional

from copilot.story import world as W

MAX_TOKENS = 500        # gpt-oss reasons (low) before the object (ST3: 260 cut it off)
EST_PROMPT = 1100
TIMEOUT_S = 5.0

PREFIX = f"""You turn one line of a story a teacher tells into a change of the story's world, for a live animation.
The line comes from speech-to-text. Answer with ONE JSON object and nothing else:
{{"new": [{{"id": "eN", "kind": "<kind>", "name": "<the line's own words for it>", "noun": "<its head noun>",
          "known": "<famous person or empty>", "gender": "he|she|", "posture": "<posture>"}}],
 "events": [{{"op": "<op>", "actor": "<id>", "target": "<id or empty>", "obj": "<id or empty>",
             "value": "<see ops>", "verb": "<the line's verb>"}}],
 "relations": [{{"a": "<id>", "rel": "<relation>", "b": "<id>", "c": "<id, only for between>"}}],
 "end": [<relations from the world that this line ends>]}}

Closed sets (use nothing else):
kind: {", ".join(W.KINDS)}
posture: {", ".join(W.POSTURES)}
ops: enter, exit, move_to (target = where), follow_path, change_posture (value = posture), attach (value = {"|".join(W.MODES)},
  target = the thing), detach (target = what is let go / got off), fall (target = what it lands on, value = body part
  {"|".join(W.PARTS)} if it hits a person), throw (obj = the thing, target = whom / where), look_at, point_at,
  speak (target = listener, value = the spoken words exactly as in the line), react (value = {"|".join(W.FEELINGS)}),
  work (target = what is worked on), put (obj = the thing, target = where, value = {"|".join(W.PUT)}; put down: no
  target), give (obj = the thing, target = who gets it), jump (value = |onto|off, target = what it jumps onto / out
  of), climb (target = what is climbed), push (target = the thing, value = {"|".join(W.PUSH)}),
  none (a verb none of these fits: the actor just stays)
relation: {", ".join(W.RELATIONS)}   (a rel b: "a is under b"; hold = a holds b; ride = a rides b; sit_on = a sits on b)
known: {", ".join(W.KNOWN)} (only when the line says the name)

Rules:
- Reuse the ids of the world for things already in it (he / she / his / her / it / the same noun = the same id). Make
  a new entity only for something not in the world; new ids continue after the last id.
- Every name, noun, verb and spoken word must be words of THIS line. Never invent things the line does not say.
- State the posture with change_posture (or "posture" of a new entity) when the line says sitting, lying, kneeling.
- Put the places and contacts the line says into "relations": "sitting under a tree" = a under tree; "rode his horse"
  = attach ride + relation ride. Moving to a place = move_to (and towards if still on the way).
- If the line ends a relation of the world (got off, dropped, left), list it in "end".
- Places the line names (village, kitchen, forest) are kind place.

Example (world rev 0, empty) line "The girl carried a basket to the river.":
{{"new": [{{"id": "e1", "kind": "person", "name": "The girl", "noun": "girl", "known": "", "gender": "she",
"posture": "stand"}}, {{"id": "e2", "kind": "prop", "name": "a basket", "noun": "basket", "known": "", "gender": "",
"posture": "stand"}}, {{"id": "e3", "kind": "place", "name": "the river", "noun": "river", "known": "", "gender": "",
"posture": "stand"}}], "events": [{{"op": "attach", "actor": "e1", "target": "e2", "obj": "", "value": "hold",
"verb": "carried"}}, {{"op": "move_to", "actor": "e1", "target": "e3", "obj": "", "value": "", "verb": "carried"}}],
"relations": [{{"a": "e1", "rel": "hold", "b": "e2"}}, {{"a": "e1", "rel": "towards", "b": "e3"}}], "end": []}}
"""


def messages(world: W.World, before: list[str], line: str) -> list[dict[str, str]]:
    ctx = "\n".join(f"- {x}" for x in before[-2:]) or "(none)"
    user = f"World:\n{world.summary()}\n\nThe last lines:\n{ctx}\n\nThe line: {line}"
    return [{"role": "system", "content": PREFIX}, {"role": "user", "content": user}]


def parse(text: str) -> Optional[dict]:
    text = (text or "").strip()
    i, j = text.find("{"), text.rfind("}")
    if i < 0 or j <= i:
        return None
    try:
        obj = json.loads(text[i:j + 1])
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else None


@dataclass
class SceneResult:
    answer: Optional[dict] = None
    text: str = ""
    tokens: int = 0
    cached_tokens: int = 0
    total_s: float = 0.0
    entry: str = ""


class SceneReader:
    """The live call (Groq through the router: JSON mode, one attempt chain)."""

    def __init__(self, router: Any) -> None:
        self.router = router

    async def read(self, msgs: list[dict[str, str]], line: str) -> SceneResult:
        t0 = time.monotonic()
        r = await self.router.complete(msgs, est_tokens=EST_PROMPT, max_tokens=MAX_TOKENS,
                                       deadline=time.monotonic() + TIMEOUT_S + 1, timeout_s=TIMEOUT_S)
        res = SceneResult(answer=parse(r.response.text), text=r.response.text, entry=r.entry,
                          total_s=time.monotonic() - t0)
        res.tokens = r.response.prompt_tokens + r.response.completion_tokens
        res.cached_tokens = r.response.cached_tokens
        return res


class ReplaySceneReader:
    """Recorded answers instead of a call (0 tokens). answers: line -> JSON text."""

    def __init__(self, answers: dict[str, str], delay_s: float = 0.0) -> None:
        self.answers = answers
        self.delay_s = delay_s
        self.calls: list[list[dict[str, str]]] = []

    async def read(self, msgs: list[dict[str, str]], line: str) -> SceneResult:
        self.calls.append(msgs)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        text = self.answers.get(line.strip(), "")
        return SceneResult(answer=parse(text), text=text, entry="replay")


async def step(reader: Any, world: W.World, before: list[str], line: str) -> tuple[SceneResult, str]:
    """Read one line and apply it to the world. Returns the result and "" (applied) or the refusal reason."""
    rev = world.rev
    res = await reader.read(messages(world, before, line), line)
    if res.answer is None:
        return res, "no JSON"
    delta, why = W.validate(res.answer, world, line, rev=rev)
    if delta is None:
        return res, why
    if world.rev != rev or not world.apply(delta):
        return res, "stale"
    return res, ""
