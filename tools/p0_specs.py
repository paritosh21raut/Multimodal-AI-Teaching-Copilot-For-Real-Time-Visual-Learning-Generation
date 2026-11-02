"""P0 part 2 (docs/v3/P0-animation-proof.md): the recorded gpt-oss-20b deltas (p0_llm_answers.json, 0 tokens) ->
world -> compiler -> web/story/anim/p0_specs.json, the specs the dev page plays (A -> B on one world, C, D).

    .venv/Scripts/python tools/p0_specs.py
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.story import world as W  # noqa: E402
from copilot.story.compile import Compiler  # noqa: E402
from copilot.story.scene_llm import ReplaySceneReader, step  # noqa: E402

ANSWERS = ROOT / "tests" / "fixtures" / "story" / "p0_llm_answers.json"
OUT = ROOT / "web" / "story" / "anim" / "p0_specs.json"
MODEL = "gpt-oss-20b"
TESTS = {  # ADR-0015 gate: A then B on one world; C, D each on a fresh world
    "AB": ["Newton was sitting under an apple tree.", "An apple fell on his head."],
    "C": ["The boy rode his horse to the village."],
    "D": ["Einstein said to his friend, time is relative."],
}


def recorded() -> dict[str, str]:
    return json.loads(ANSWERS.read_text(encoding="utf-8"))[MODEL]["answers"]


async def story_specs(lines: list[str], answers: dict[str, str]) -> list[dict]:
    """One spec per line; the world and the compiler persist across the lines (positions, fallen fruit)."""
    world, comp, before, out = W.World(), Compiler(), [], []
    for ln in lines:
        key = " | ".join(before + [ln])
        res, why = await step(ReplaySceneReader({ln: answers.get(key, "")}), world, before, ln)
        if why:
            raise SystemExit(f"{ln!r}: {why}")
        out.append(comp.compile(world, ln))
        before.append(ln)
    return out


async def build() -> dict[str, dict]:
    answers = recorded()
    specs: dict[str, dict] = {}
    for name, lines in TESTS.items():
        got = await story_specs(lines, answers)
        for letter, spec in zip(name, got):
            specs[letter] = spec
    return specs


# Look demo (user look round 2026-11-02): HAND-WRITTEN deltas, not LLM answers. Name tags, main vs supporting
# looks, walking together. The genders are what the cast (ST2) gives from the said words: "her" -> Geeta, "brother"
# -> Arun; in P1 the cast supplies them live.
LOOK_DEMO = [
    ("Geeta and her brother Arun walked to the village with two boys.", W.Delta(0, new=[
        W.Entity("e1", "person", "Geeta", "Geeta", gender="she"),
        W.Entity("e2", "person", "her brother Arun", "Arun", gender="he"),
        W.Entity("e3", "person", "two boys", "boys", gender="he"),
        W.Entity("e4", "person", "two boys", "boys", gender="he"),
        W.Entity("e5", "place", "the village", "village")],
        events=[W.Event("move_to", a, "e5", verb="walked") for a in ("e1", "e2", "e3", "e4")])),
    ("Geeta asked Arun, are you tired?", W.Delta(1, events=[
        W.Event("speak", "e1", "e2", value="are you tired", verb="asked")])),
]


def look_demo() -> list[dict]:
    world, comp, out = W.World(), Compiler(), []
    for line, delta in LOOK_DEMO:
        assert world.apply(delta)
        out.append(comp.compile(world, line))
    return out


# P1b motions (docs/v3/P1b-semantic-actions.md): HAND-WRITTEN deltas on one world, one scene per line (G..M):
# pick up + carry, put + climb, jump off, give, throw, pick up + push, drop + walk off.
E = W.Entity
P1B_DEMO = [
    ("Ravi picked up an apple and walked to the tree.", W.Delta(0, new=[
        E("e1", "person", "Ravi", "Ravi"), E("e2", "prop", "an apple", "apple"), E("e3", "prop", "the tree", "tree")],
        events=[W.Event("attach", "e1", "e2", value="hold", verb="picked"), W.Event("move_to", "e1", "e3", verb="walked")],
        relations=[W.Relation("e1", "hold", "e2")])),
    ("He put the apple under the tree, climbed it and sat on a branch.", W.Delta(1, events=[
        W.Event("put", "e1", "e3", "e2", "under", "put"), W.Event("climb", "e1", "e3", verb="climbed")])),
    ("Then he jumped off the tree.", W.Delta(2, events=[W.Event("jump", "e1", "e3", value="off", verb="jumped")])),
    ("Meena came, and Ravi gave her the apple.", W.Delta(3, new=[E("e4", "person", "Meena", "Meena")], events=[
        W.Event("give", "e1", "e4", "e2", verb="gave")])),
    ("Meena threw the apple to the boy.", W.Delta(4, new=[E("e5", "person", "the boy", "boy", gender="he")], events=[
        W.Event("throw", "e4", "e5", "e2", verb="threw")])),
    ("The boy picked up a stone and pushed a cart.", W.Delta(5, new=[
        E("e6", "prop", "a stone", "stone"), E("e7", "prop", "a cart", "cart")], events=[
        W.Event("attach", "e5", "e6", value="hold", verb="picked"), W.Event("push", "e5", "e7", value="push", verb="pushed")],
        relations=[W.Relation("e5", "hold", "e6")])),
    ("He dropped the stone and walked away.", W.Delta(6, events=[
        W.Event("detach", "e5", "e6", verb="dropped"), W.Event("exit", "e5", verb="walked")])),
]


def p1b_demo() -> list[dict]:
    world, comp, out = W.World(), Compiler(), []
    for line, delta in P1B_DEMO:
        assert world.apply(delta), line
        out.append(comp.compile(world, line))
    return out


def main() -> None:
    specs = asyncio.run(build())
    specs["E"], specs["F"] = look_demo()
    for letter, spec in zip("GHIJKLM", p1b_demo()):
        specs[letter] = spec
    OUT.write_text(json.dumps(specs, indent=1), encoding="utf-8")
    for k, s in specs.items():
        print(k, f"{s['duration']:.1f}s", [e["op"] for e in s["events"]], "fallback:", s["fallback"],
              "skipped:", [x["name"] for x in s["skipped"]])


if __name__ == "__main__":
    main()
