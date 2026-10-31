"""F-019 M2: the free-body view (each body alone, the pair forces of Newton III), labels that never overlap, the
recap's bare-number pairs. 0 tokens."""
import json
import math
from pathlib import Path

import pytest

from copilot.diagram import mech, patch
from copilot.diagram.solvers import run
from copilot.presentation.content import Piece
from copilot.presentation.recap import recap_pieces
from tests.unit.test_diagram_m1 import FIX, M1
from tests.unit.test_diagram_m1 import _final as _fd


def _final(lines):
    return _fd(lines)[0]


def _lines(name):
    return [ln["say"] for ln in json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["lines"]]


def _overlap(a, b):
    return a[0] < b[2] - 1 and a[2] > b[0] + 1 and a[1] < b[3] - 1 and a[3] > b[1] + 1


def test_pair_forces_are_newton_three():
    """Two blocks, 50 N on the bottom (3 kg), top 2 kg, μ 0.4 between, frictionless floor (m1_two_blocks_slip):
    the top block's N = m_top g = 19.6 N up and f = μ N = 7.84 N forward (right); on the bottom block the pair
    N′ = 19.6 N down and f′ = 7.84 N backward (left). The pair forces are not in the scene view."""
    g = _final(_lines("m1_two_blocks_slip"))
    res = run(g)
    by = {f.id: f for f in res.forces}
    top, bot = "block2", "block"
    assert by[f"N'_{top}"].on == bot and by[f"N'_{top}"].pair
    assert math.isclose(by[f"N'_{top}"].value.v, by[f"N_{top}"].value.v) and math.isclose(by[f"N_{top}"].value.v, 19.6)
    assert (by[f"N'_{top}"].ang - by[f"N_{top}"].ang) % 360 == 180
    assert math.isclose(by[f"f'_{top}"].value.v, 7.84) and (by[f"f'_{top}"].ang - by[f"f_{top}"].ang) % 360 == 180
    assert by[f"N'_{top}"].value.sym == "N′"
    p = patch.build(g)
    assert not [a for a in p["mech"]["forces"] if "'" in a["id"]]
    assert p["mech"]["bodies"] == [bot, top] or sorted(p["mech"]["bodies"]) == sorted([bot, top])


@pytest.mark.parametrize("name", M1)
def test_scene_labels_never_overlap(name):
    p = patch.build(_final(_lines(name)))
    labels = [mech._label_box(a) for a in p["mech"]["forces"]]
    for i, a in enumerate(labels):
        for b in labels[:i]:
            assert not _overlap(a, b), (name, a, b)


@pytest.mark.parametrize("name", ["m1_two_blocks_slip", "m1_incline_full", "m1_atwood", "m1_table_hanging",
                                  "m1_spring", "m1_two_blocks_missing"])
def test_free_body_view(name):
    g = _final(_lines(name))
    res = run(g)
    p = patch.build(g, fbd="all")
    fb = p["mech"]["fbd"]
    assert p["mech"]["fbd_on"] == "all" and not [t for t in p["tracks"] if t["kind"] in ("slide", "shm")]
    shown = {b["id"] for b in fb["bodies"]}
    want = {f.id for f in res.forces if f.on in shown and not (f.value.known and abs(f.value.v) < 1e-9)}
    assert {a["id"][4:] for a in fb["forces"]} == want  # every force on every body, pair forces too
    labels = [mech._label_box(a) for a in fb["forces"]]
    for i, a in enumerate(labels):
        assert 0 <= a[0] and a[2] <= 1600 - mech.PANEL_W + 20 and a[1] >= 150 and a[3] <= 1000, (name, a)
        for b in labels[:i]:
            assert not _overlap(a, b), (name, a, b)
    for a in fb["forces"]:  # each arrow ends outside its box; no label lies on a box
        b = next(x for x in fb["bodies"] if x["id"] == a["on"])
        assert math.hypot(a["x2"] - b["cx"], a["y2"] - b["cy"]) > max(b["w"], b["h"]) / 2
    if name != "m1_incline_full":  # (a tilted box's corners reach past its axis-aligned extent)
        rects = [[b["cx"] - b["w"] / 2, b["cy"] - b["h"] / 2, b["cx"] + b["w"] / 2, b["cy"] + b["h"] / 2]
                 for b in fb["bodies"]]
        for lb in labels:
            assert not any(_overlap(lb, r) for r in rects), (name, lb)
    if name == "m1_two_blocks_slip":
        ids = {a["id"] for a in fb["forces"]}
        assert {"fbd-N'_block2", "fbd-f'_block2"} <= ids
        assert [b["name"] for b in fb["bodies"]] and all(b["mass"] for b in fb["bodies"])
    if name == "m1_atwood":  # "2 kg block", not "2 kg block · 2 kg"
        assert all(not b["mass"] for b in fb["bodies"])


def test_free_body_one_body_and_off():
    g = _final(_lines("m1_two_blocks_slip"))
    one = patch.build(g, fbd="block")["mech"]
    assert [b["id"] for b in one["fbd"]["bodies"]] == ["block"] and one["fbd_on"] == "block"
    assert {a["on"] for a in one["fbd"]["forces"]} == {"block"}
    off = patch.build(g, fbd="gone")["mech"]  # a body no longer there: the scene
    assert "fbd" not in off and off["fbd_on"] == ""


def test_recap_drops_bare_number_pairs():
    p = Piece(kind="facts", pairs=(("Coefficient of friction (blocks)", "0.4"), ("Mass of the top block", "2 kg"),
                                  ("Friction", "always opposes relative motion")))
    kept, dropped = recap_pieces([p])
    assert dropped == 2 and kept[0].pairs == (("Friction", "always opposes relative motion"),)


async def test_voice_and_button_turn_the_free_body_view():
    """Through the real engine (0 tokens): the two-block lines, then "draw the free body diagram of the top block"
    (that body), the button's command (all), "back to the picture" (off). No new slide on the way."""
    from copilot.core.events import Command, CommandReceived
    from copilot.scene.detector import SceneDetector
    from copilot.simulation.detector import SimulationDetector
    from tests.unit.test_diagram_routing import block, stage_slides
    from tests.unit.test_presentation_engine import act, make, ready, send
    from tests.unit.test_simulation import Lines

    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    await send(bus, ready("Science", "Science", [act("explanation", points=["Friction"])], relation="new_topic"))
    talk = Lines(bus)
    for line in _lines("m1_two_blocks_slip"):
        await talk.say(line)
        await bus.drain()
    n = len(stage_slides(deck))
    sid = stage_slides(deck)[-1].id

    def mech_now():
        return block(next(x for x in deck.slides if x.id == sid)).diagram["mech"]

    assert mech_now()["fbd_on"] == ""
    await talk.say("Now let's draw the free body diagram of the top block.")
    await bus.drain()
    assert mech_now()["fbd_on"] == "block2" and [b["id"] for b in mech_now()["fbd"]["bodies"]] == ["block2"]
    await send(bus, CommandReceived(command=Command(kind="stage_fbd", args={"slide_id": sid, "on": "all"})))
    assert mech_now()["fbd_on"] == "all" and len(mech_now()["fbd"]["bodies"]) == 2
    await talk.say("Okay, back to the picture.")
    await bus.drain()
    assert mech_now()["fbd_on"] == "" and "fbd" not in mech_now()
    assert len(stage_slides(deck)) == n


def test_recap_keeps_facts_that_are_numbers():
    """Review: only a scene parameter's bare number is parameter talk; "pH of pure water: 7" is a fact."""
    p = Piece(kind="facts", pairs=(("pH of pure water", "7"), ("Protons in carbon", "6"), ("Mass of the box", "5 kg")))
    kept, dropped = recap_pieces([p])
    assert dropped == 1 and kept[0].pairs == (("pH of pure water", "7"), ("Protons in carbon", "6"))


async def _engine(lines):
    from copilot.scene.detector import SceneDetector
    from copilot.simulation.detector import SimulationDetector
    from tests.unit.test_diagram_routing import block, stage_slides
    from tests.unit.test_presentation_engine import act, make, ready, send
    from tests.unit.test_simulation import Lines

    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    await send(bus, ready("Science", "Science", [act("explanation", points=["Friction"])], relation="new_topic"))
    talk = Lines(bus)
    for line in lines:
        await talk.say(line)
        await bus.drain()
    return block(stage_slides(deck)[-1]).diagram


def test_lettered_block_named_as_a_whole_word():
    """Review: "free body diagram of block B" is block B ("a" is in "diagram", "b" in "body": not a name)."""
    from types import SimpleNamespace

    from copilot.presentation.stage import StageController

    g = _final(_lines("m1_two_blocks_slip"))
    g.parts["block"].label, g.parts["block2"].label = "B", "A"  # block A on block B
    o = SimpleNamespace(dlog=SimpleNamespace(fold=lambda: g), fbd="")
    assert StageController._fbd_line(None, o, "Draw the free body diagram of block B.") and o.fbd == "block"
    assert StageController._fbd_line(None, o, "Now the free body diagram of block A.") and o.fbd == "block2"
    assert StageController._fbd_line(None, o, "Draw the free body diagram.") and o.fbd == "all"
    assert StageController._fbd_line(None, o, "Okay, back to the picture.") and o.fbd == ""


async def test_a_value_in_the_free_body_line_still_lands_and_no_body_opens_no_slide():
    """Review: the value said with the request re-solves (top 2 kg → 4 kg); with no mechanics diagram the line
    opens nothing (it once opened a stage slide "Body")."""
    d = await _engine(_lines("m1_two_blocks_slip") + ["Draw the free body diagram, and the top block is 4 kg."])
    assert d["mech"]["fbd_on"] == "block2"  # the line names the top block
    assert any(r["text"] == "m = 4 kg" for r in d["mech"]["panel"]["rows"] if r["kind"] == "value")
    d = await _engine(["Imagine an atom.", "Draw the free body diagram."])
    assert d.get("mech") is None or "fbd" not in d["mech"]


TEST42 = ["Imagine two blocks on top of the other on the floor.",
          "Imagine two blocks, one on top of the other on the floor.",
          "The top block is 2kg and the bottom block is 3kg.",
          "Perf friction between the blocks is 0.4 and the floor is frictionless.",
          "Let's draw the free body diagram of the bottom block.",
          "N equals 19.6 down and F dash equals 7.84 left.",
          "Now the freeboard diagram of both blocks.",
          "Now the free body diagram of both blocks.",
          "Change the mass of the top block to 4 kg."]


async def test_test42_no_extra_blocks_and_freeboard_is_free_body():
    """test42 (live words): the cut cue said again whole redraws it (the stack, not two more blocks); "freeboard
    diagram of both blocks" is the free-body view of the two drawn blocks (it drew two more each time: 8 blocks)."""
    d = await _engine(TEST42)
    assert sorted(p["id"] for p in d["parts"]) == ["block", "block2", "floor"]
    m = d["mech"]
    assert m["fbd_on"] == "all" and len(m["fbd"]["bodies"]) == 2
    vals = [r["text"] for r in m["panel"]["rows"] if r["kind"] == "value"]
    assert "m = 4 kg" in vals and "m = 3 kg" in vals and "N = 39.2 N" in vals


async def test_cue_said_twice_later_adds_nothing_but_another_still_adds():
    d = await _engine(["Imagine two circles, C1 and C2.", "Imagine two circles."])
    assert sum(p["kind"] == "circle" for p in d["parts"]) == 2
    d = await _engine(["Imagine two circles, C1 and C2.", "Another circle C3."])
    assert sum(p["kind"] == "circle" for p in d["parts"]) == 3


def test_test42_recap_lines_are_dropped():
    from copilot.presentation.recap import chatter, only_picture

    p = Piece(kind="facts", pairs=(("Normal force N", "19.6 N down"), ("Friction force F'", "7.84 N left")))
    assert recap_pieces([p])[0] == []
    assert chatter("Angle increased to 60°")
    assert only_picture("Two blocks stacked on the floor", {"block", "floor"})
    assert only_picture("Free‑body diagram of the box on the incline", {"box", "incline"})
    assert not chatter("Friction increases with the normal force")  # a rule stays
