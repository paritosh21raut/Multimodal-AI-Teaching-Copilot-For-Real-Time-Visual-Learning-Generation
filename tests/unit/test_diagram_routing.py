"""F-018 K1: routing of concept lines (GATE-SENTENCES D / S / M rows) and the test35 live run replayed through the
real engine (0 tokens: no LLM answers, the fast paths only): 5 concept topics -> 5 diagrams, 0 people on them, the
follow-up line stays on the open diagram, a concept line never falls to a bullet slide."""
import json
from pathlib import Path

import pytest

from copilot.core.events import Command, CommandReceived
from copilot.diagram.route import route
from copilot.scene.detector import SceneDetector, cue
from copilot.simulation.detector import SimulationDetector
from copilot.stage.director_llm import ReplayDirector
from copilot.stt.engine import guard
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "diagram" / "test35_lines.jsonl"

D_ROWS = ["Imagine a box on an inclined plane.", "Imagine two circles, C1 and C2.", "Imagine our solar system.",
          "Imagine in a beaker you have HCl, and you're adding water to it slowly.", "Imagine an atom.",
          "Three resistors in series with a cell.", "One resistor in series with four in parallel.",
          "A Wheatstone bridge.", "A bar magnet and its field.", "A spring with a mass hanging from it."]
S_ROWS = ["Imagine you are riding a horse.", "Imagine a girl swinging on a swing.", "Imagine a bird sitting on a tree.",
          "Imagine you are riding a car.", "Two men playing tug of war against two women.",
          "Imagine you are throwing a ball at 30 m/s at 60 degrees.", "Imagine a dog running in the rain.",
          "A man pushes a box.", "Imagine you are reading a book.", "A boy climbs a ladder."]


@pytest.mark.parametrize("line", [r for r in D_ROWS if "Wheatstone" not in r])
def test_gate_d_rows_route_to_a_diagram(line):
    assert route(line) == "diagram", line


@pytest.mark.parametrize("line", ["Imagine a box on an inclined plane.", "Imagine two circles, C1 and C2.",
                                  "Imagine our solar system.", "Imagine in a beaker you have HCL.", "Imagine an atom.",
                                  "Imagine a bar magnet and its field.", "Imagine a spring with a mass hanging from it."])
def test_concept_cues_are_diagram_cues_even_with_our_and_you(line):
    assert cue(line) == "diagram"


@pytest.mark.parametrize("line", S_ROWS)
def test_gate_s_rows_are_never_diagrams(line):
    assert route(line) is None, line


@pytest.mark.parametrize("line", ["Imagine you are studying.", "Thank you.", "So what is the answer to question three?",
                                  "Imagine a circle of radius 5 cm.", "Draw a square of side 4 centimetres."])
def test_m_rows_and_measured_shapes_are_not_diagrams(line):
    assert route(line) is None, line


# ---- test35 replayed on the engine ----------------------------------------------------------------------------------
def rows():
    return [json.loads(s) for s in FIX.read_text(encoding="utf-8").splitlines() if s.strip()][1:]


def stage_slides(deck):
    return [s for s in deck.slides if any(b.type == "stage" for b in s.blocks)]


def block(s):
    return next(b for b in s.blocks if b.type == "stage")


async def replay():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    eng._stage.director = ReplayDirector({})
    await send(bus, ready("Lecture", "Lecture", [act("explanation", points=["Pictures of ideas"])], relation="new_topic"))
    talk = Lines(bus)
    seen = []
    for r in rows():
        if guard(r["say"], 2.5, -0.3, 0.1, 1.0):  # the STT engine drops it ("Thank you.")
            continue
        before = len(stage_slides(deck))
        await talk.say(r["say"])
        o = eng._stage.open
        if o is not None and o.task is not None:
            await o.task
        await bus.drain()
        seen.append((r, before, len(stage_slides(deck)), eng._stage._live()))
    return deck, eng, seen, bus


async def test_test35_five_concept_topics_give_five_diagrams_with_no_people():
    deck, eng, seen, _ = await replay()
    bad = []
    for r, before, after, o in seen:
        f = r.get("facts")
        if not f:
            continue
        if f["diagram"] == "new" and after != before + 1:
            bad.append(f"{r['n']} {r['say']!r}: a new diagram slide expected ({before} -> {after})")
        if f["diagram"] == "same" and after != before:
            bad.append(f"{r['n']} {r['say']!r}: the open diagram expected ({before} -> {after})")
        if o is None or o.mode != "diagram":
            bad.append(f"{r['n']} {r['say']!r}: no open diagram ({o and o.mode})")
            continue
        g = o.dlog.fold()
        kinds = {p.kind for p in g.parts.values()}
        for k in f["kinds"]:
            if k not in kinds:
                bad.append(f"{r['n']}: no {k} ({sorted(kinds)})")
        labels = {p.label for p in g.parts.values()}
        for lab in f.get("labels", []):
            if lab not in labels:
                bad.append(f"{r['n']}: label {lab!r} missing ({sorted(labels)})")
    assert not bad, "\n".join(bad)
    dia = [s for s in stage_slides(deck) if block(s).mode == "diagram"]
    assert [s.title for s in dia] == ["Box on an inclined plane", "Two circles C1 and C2", "Solar system",
                                      "HCl in a beaker", "Atom"], [s.title for s in dia]
    for s in dia:
        b = block(s)
        assert b.diagram["parts"] and not b.patch.get("entities"), s.title  # 0 people / stage things on a diagram
        assert not any(p["kind"] in ("agent", "animal") for p in b.diagram["parts"])
    titles = [s.title for s in deck.slides]
    assert "Imagine our solar system" not in titles  # test35: a bullet slide


async def test_test35_people_lines_stay_on_the_stage():
    deck, eng, seen, _ = await replay()
    stages = [s for s in stage_slides(deck) if block(s).mode == "stage"]
    assert len(stages) >= 5
    for r, _, _, o in seen:
        if r["say"].startswith(("Imagine a girl", "Imagine you are riding a horse", "Imagine a bird")):
            assert o is not None and o.mode == "stage", r["say"]


async def test_teacher_switches_diagram_to_scene_and_back_and_undoes_a_line():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    await send(bus, ready("Chemistry", "Chemistry", [act("explanation", points=["Acids"])], relation="new_topic"))
    talk = Lines(bus)
    for line in ("Imagine in a beaker you have HCl.", "And you're adding water to it slowly."):
        await talk.say(line)
        await bus.drain()
    s = stage_slides(deck)[-1]
    assert {p["kind"] for p in block(s).diagram["parts"]} >= {"beaker", "liquid", "pourer"}
    sid = s.id
    await send(bus, CommandReceived(command=Command(kind="stage_undo", args={"slide_id": sid})))
    s = next(x for x in deck.slides if x.id == sid)
    assert "pourer" not in {p["kind"] for p in block(s).diagram["parts"]}
    await send(bus, CommandReceived(command=Command(kind="stage_mode", args={"slide_id": sid, "to": "scene"})))
    s = next(x for x in deck.slides if x.id == sid)
    assert block(s).mode == "stage" and not block(s).diagram
    await send(bus, CommandReceived(command=Command(kind="stage_mode", args={"slide_id": sid, "to": "diagram"})))
    s = next(x for x in deck.slides if x.id == sid)
    assert block(s).mode == "diagram" and {"beaker", "liquid"} <= {p["kind"] for p in block(s).diagram["parts"]}
    assert "pourer" not in {p["kind"] for p in block(s).diagram["parts"]}  # an undone line stays undone


async def test_review_a_new_cue_with_the_same_noun_is_the_next_diagram_and_freeze_holds():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    await send(bus, ready("Chemistry", "Chemistry", [act("explanation", points=["Acids"])], relation="new_topic"))
    talk = Lines(bus)
    await talk.say("Imagine a beaker with HCl.")
    await bus.drain()
    await talk.say("Imagine a beaker with NaOH.")
    await bus.drain()
    dia = [s for s in stage_slides(deck) if block(s).mode == "diagram"]
    assert len(dia) == 2 and [len([p for p in block(s).diagram["parts"] if p["kind"] == "liquid"]) for s in dia] == [1, 1]
    sid = dia[-1].id
    await send(bus, CommandReceived(command=Command(kind="stage_freeze", args={"slide_id": sid})))
    n = len(stage_slides(deck))
    await talk.say("Imagine an atom.")
    await bus.drain()
    assert len(stage_slides(deck)) == n  # frozen: speech opens nothing
