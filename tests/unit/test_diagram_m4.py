"""F-019 M4: the live mechanics lecture (incline -> floor -> stack -> Atwood -> table -> spring) on the fast path
(0 tokens), the M3 leftovers (Atwood W room, stack arrows, recap restating the cue, the Scene switch keeping the LLM's
fixes, "half a kilogram") and the lecture-script misses (static + kinetic in one line, "a 2 kg block on top of a 4 kg
block", "increase the force to", "a rough horizontal floor"). Values: tests/fixtures/diagram/m4_*.json."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from copilot.core.events import Command, CommandReceived
from copilot.diagram import layout, mech
from copilot.diagram.extract import replay
from copilot.diagram.solvers.contact import Contact
from copilot.presentation.recap import restates
from copilot.simulation.values import heard
from tests.unit.test_diagram_m1 import test_fixture as _m1_fixture

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "diagram"
M4 = sorted(p.stem for p in FIX.glob("m4_*.json"))


def _lines(name):
    return [x["say"] for x in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["lines"]]


@pytest.mark.parametrize("name", M4)
def test_lecture_fixture(name):
    """Every value of the lecture script, said or computed (the M1 fixture checks, hand-computed expectations)."""
    _m1_fixture(name)


@pytest.mark.parametrize("name", M4)
def test_lecture_needs_no_llm_call(name):
    """The scripted lecture runs on the fast path: value -> re-solved well inside 1 s, 0 tokens."""
    assert [why for _, why in asyncio.run(replay(_lines(name)))] == [""] * len(_lines(name))


def test_half_a_kilogram_is_read():
    assert [(h.kind, h.value) for h in heard("The block is half a kilogram.")] == [("mass", 0.5)]
    g = asyncio.run(replay(["Imagine a block of half a kilogram on the floor."]))[-1][0]
    assert g.rels == {"block": ("on", "floor")} and g.qty[("block", "m")]["v"] == 0.5


def test_a_surface_adjective_is_no_part():
    g = asyncio.run(replay(["Imagine a box on a smooth level floor."]))[-1][0]
    assert {p.kind for p in g.parts.values()} == {"block", "floor"} and g.rels["box"] == ("on", "floor")


def _arrows(lines):
    g = asyncio.run(replay(lines))[-1][0]
    res = Contact().solve(g)
    L = layout.solve(g, panel=mech.PANEL_W)
    return L, {(a["on"], a["kind"]): a for a in mech.build(g, L, res)["forces"]}


def test_atwood_weight_arrow_and_label_stay_on_the_slide():
    """test47: the heavier side hangs low; its W arrow has its full length and its label inside the slide."""
    L, arr = _arrows(_lines("m4_atwood"))
    w = arr[("mass2", "weight")]
    assert w["y2"] - w["y1"] >= mech.ARROW[1] - 1 and w["ly"] + 8 <= layout.AREA[3]


def test_stack_arrows_keep_clear_of_the_other_block():
    """The top block's W stops at the bottom block; the bottom block's N runs beside the top block, off its N line."""
    L, arr = _arrows(_lines("m4_stack")[:3])
    top, low = L.nodes["block"].box(), L.nodes["block2"].box()
    assert arr[("block", "weight")]["y2"] <= low[1]
    n = arr[("block2", "normal")]
    assert n["x1"] > top[2] and n["x1"] < low[2] and n["x1"] != arr[("block", "normal")]["x1"]


def test_recap_bullet_restating_the_cue_is_dropped():
    cue = ["Imagine two masses connected by a string over a pulley."]
    assert restates("Two masses are linked by a string over a pulley", cue)
    assert not restates("Tension in the string is the same on both sides of the pulley", cue)
    assert not restates("The heavier mass moves down", cue)
    assert not restates("The block slides down the incline", ["Imagine a block on an incline."])


def test_scene_switch_and_back_keeps_the_llm_fix():
    """M3 leftover: Diagram -> Scene -> Diagram drew the fast draft again and lost the LLM's values (0 tokens now)."""
    from tests.unit.test_diagram_m3 import _engine
    from tests.unit.test_diagram_routing import block, stage_slides
    from tests.unit.test_presentation_engine import send

    lines = ["Imagine two masses connected by a string over a pulley.", "The masses are 2 kg and 3 kg."]
    answers = json.loads((FIX / "m3_llm_answers.json").read_text(encoding="utf-8"))

    async def run():
        eng, _ = await _engine(lines, answers)
        sid = eng._stage.open.slide_id
        bus = eng.bus
        for to in ("scene", "diagram"):
            await send(bus, CommandReceived(command=Command(kind="stage_mode", args={"slide_id": sid, "to": to})))
        return eng, block(next(s for s in stage_slides(eng.deck) if s.id == sid)).diagram

    eng, dia = asyncio.run(run())
    rows = " ".join(r["text"] for r in dia["mech"]["panel"]["rows"])
    assert "2 kg" in rows and "3 kg" in rows and eng._stage.stats.calls == 1


# ---- review findings ------------------------------------------------------------------------------------------------
def test_review_a_force_said_on_another_body_never_replaces_the_push():
    g = asyncio.run(replay(["Imagine a 2 kg block on top of a 4 kg block.",
                            "The top block is pushed with a force of 10 newtons.",
                            "A force of 6 newtons acts on the 4 kg block."]))[-1][0]
    assert g.qty[("block", "F")]["v"] == 10.0 and ("block2", "F") not in g.qty or g.qty[("block2", "F")]["v"] == 6.0


def test_review_a_block_placed_on_the_block_is_a_second_block():
    g = asyncio.run(replay(["Imagine a 5 kg block on the floor.", "A 3 kg block is placed on top of the block."]))[-1][0]
    assert g.rels == {"block": ("on", "floor"), "block2": ("on", "block")}
    assert g.qty[("block", "m")]["v"] == 5.0 and g.qty[("block2", "m")]["v"] == 3.0


def test_review_restates_keeps_a_point_about_what_acts():
    assert not restates("The floor pushes the block up", ["Imagine a block on a rough floor pushed with 10 newtons"])
    assert restates("Masses hang over a pulley", ["Imagine two masses connected by a string over a pulley."])
