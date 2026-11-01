"""F-019 M5: motion and relative velocity on the K1 diagram (0 tokens): the fast path's processes and values (test36
wordings: "3mps", "10 meter per second", "50 kmph"), routing, the kinematics solver against textbook answers (each
fixture's `about`, tests/fixtures/diagram/m5_*.json, g = 9.8) and the patch (tracks and arrows on the slide, every
number said or computed)."""
from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import pytest

from copilot.diagram import fastpath, patch
from copilot.diagram.extract import replay
from copilot.diagram.graph import DiagramLog
from copilot.diagram.layout import VIEW
from copilot.diagram.route import route
from copilot.diagram.solvers import run
from tests.unit.test_diagram_m1 import test_fixture as _m1_fixture

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "diagram"
M5 = sorted(p.stem for p in FIX.glob("m5_*.json"))


def _fx(name):
    return json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))


def _graph(lines):
    log = DiagramLog()
    for k, t in enumerate(lines):
        log.say(f"l{k}", t)
        log.delta(fastpath.draft(t, log.fold()).ops, f"l{k}", "fast", text=t)
    return log.fold()


@pytest.mark.parametrize("name", M5)
def test_motion_fixture(name):
    """Every said and computed value (hand-worked answers in the fixture), symbols when an input is missing."""
    _m1_fixture(name)


@pytest.mark.parametrize("name", M5)
def test_motion_needs_no_llm_call(name):
    lines = [x["say"] for x in _fx(name)["lines"]]
    assert [why for _, why in asyncio.run(replay(lines))] == [""] * len(lines)


@pytest.mark.parametrize("name", M5)
def test_motion_parts(name):
    """Only the said motion parts: no beaker of "still water", no circle part for "whirled in a circle"."""
    fx = _fx(name)
    for k in range(len(fx["lines"])):
        want = fx["lines"][k]["expect"].get("kinds")
        if want:
            g = _graph([x["say"] for x in fx["lines"][:k + 1]])
            assert sorted({p.kind for p in g.parts.values()}) == sorted(want), g.parts


@pytest.mark.parametrize("text", [
    "Imagine you throw a ball in the air.", "Imagine a car moving at a speed of 50 kmph.",
    "Imagine you are running in the rain.", "A man walks in the rain at 3 metres per second.",
    "A boat crosses a river.", "A stone is dropped from a height of 20 metres."])
def test_motion_lines_are_diagrams(text):
    assert route(text) == "diagram"


@pytest.mark.parametrize("text", ["imagine you're pushing a car", "Imagine a man reading a book",
                                  "Imagine a dog chasing a ball"])
def test_other_lines_stay_as_before(text):
    assert route(text) is None


def test_two_cars_and_no_noun_is_unattached():
    """Two cars there and "the speed is 30 m/s" with no car named: asked, not guessed."""
    g = _graph(["Imagine a car moving at 50 kmph.", "Imagine another car moving at 60 kmph."])
    d = fastpath.draft("The speed is 30 metres per second.", g)
    assert not [o for o in d.ops if o["op"] == "qty"] and ("v", "30 metres per second") in d.unattached


def test_kmh_said_is_shown_in_kmh():
    g = _graph(["Imagine a car moving at a speed of 50 kmph.", "Imagine another car moving at a speed of 60 kmph."])
    texts = {v.text() for v in run(g).values}
    assert {"v_1 = 50 km/h", "v_2 = 60 km/h", "v_rel = 10 km/h"} <= texts


def test_a_later_speed_keeps_the_throw_up():
    """test36: "throw a ball in the air", then "with the speed of 3mps": still thrown up (no 'moving' ball)."""
    g = _graph(["Imagine you throw a ball in the air.", "with the speed of 3mps. second."])
    assert [p["verb"] for p in g.processes] == ["throw"] and g.processes[0]["manner"] == "up"


def test_launch_angle_above_the_horizontal_is_no_horizontal_throw():
    g = _graph(["A ball is thrown at 20 metres per second at 30 degrees above the horizontal."])
    assert g.processes[0]["manner"] == "angle"


@pytest.mark.parametrize("name", M5)
def test_patch_tracks_and_arrows_stay_on_the_slide(name):
    """The body's whole run (path samples / orbit), every arrow and its label inside the slide; a moving scene has
    a track; the badge says the sizes are not to scale."""
    g = _graph([x["say"] for x in _fx(name)["lines"]])
    p = patch.build(g)
    parts = {x["id"]: x for x in p["parts"]}
    inside = lambda x, y: -1 <= x <= VIEW[0] + 1 and -1 <= y <= VIEW[1] + 1  # noqa: E731
    moving = [t for t in p["tracks"] if t["kind"] in ("path", "orbit")]
    assert moving, p["tracks"]
    for t in moving:
        b = parts[t["id"]]
        if t["kind"] == "path":
            for _, dx, dy in t["pts"]:
                assert inside(b["cx"] + dx, b["cy"] + dy), (t["id"], dx, dy)
        else:
            assert inside(t["cx"] - t["rx"], t["cy"] - t["ry"]) and inside(t["cx"] + t["rx"], t["cy"] + t["ry"])
    for a in p["mech"]["forces"]:
        assert inside(a["x2"], a["y2"]) and inside(a["lx"], a["ly"]), a
    assert "body sizes not to scale" in p["badges"]


def test_projectile_path_lands_on_the_ground():
    """The sampled path starts at the launch point and ends back on the ground (R to scale with the height)."""
    g = _graph(["Imagine you throw a ball at 20 metres per second at 30 degrees above the horizontal."])
    res = run(g)
    pts = res.paths[0].pts
    R = next(v.v for v in res.values if v.sym == "R")
    assert pts[0][1:] == (0.0, 0.0) and math.isclose(pts[-1][1], R, rel_tol=1e-9) and abs(pts[-1][2]) < 1e-9
    assert math.isclose(max(y for _, _, y in pts), next(v.v for v in res.values if v.sym == "H"), rel_tol=1e-3)


def test_the_later_of_angle_and_straight_up_wins():
    """'at 45 degrees' then 'throw it straight up': a throw up (T = 2v/g); and back to an angle when said again."""
    g = _graph(["Imagine you throw a ball at 20 metres per second at 45 degrees.", "Now throw it straight up."])
    vals = {v.sym: v for v in run(g).values}
    assert math.isclose(vals["T"].v, 40 / 9.8) and "θ" not in {v.sym for v in run(g).values if v.known}
    g = _graph(["Imagine you throw a ball straight up at 20 metres per second.", "Now throw it at 45 degrees."])
    assert math.isclose({v.sym: v for v in run(g).values}["R"].v, 400 / 9.8)


def test_a_stone_cue_after_the_ball_is_no_repeat():
    """Dry run of M5-live: 'imagine a stone dropped …' 50 s after the ball cue was taken as the ball said again."""
    from copilot.presentation.stage import _recount
    g = _graph(["Imagine you throw a ball at 20 metres per second at 30 degrees above the horizontal."])
    assert not _recount(fastpath.draft("Now imagine a stone dropped from a height of 20 metres.", g), g.parts)
    assert _recount(fastpath.draft("Imagine you throw a ball at 20 metres per second at 30 degrees above the "
                                   "horizontal.", _graph([])), g.parts)


# ---- review findings (M5) -------------------------------------------------------------------------------------------
def test_a_throw_said_in_kmh_is_computed_in_si():
    """36 km/h = 10 m/s at 30°: T = 2·10·0.5/9.8 = 1.02 s, R = 100·sin 60°/9.8 = 8.84 m; the arrow shows "36 km/h"."""
    g = _graph(["Imagine a ball thrown at 36 kmph at 30 degrees."])
    res = run(g)
    vals = {v.sym: v for v in res.values}
    assert math.isclose(vals["T"].v, 10 / 9.8) and math.isclose(vals["R"].v, 100 * math.sin(math.radians(60)) / 9.8)
    assert next(v for v in res.vectors if v.id == "v0").value.text() == "v = 36 km/h"


def test_each_car_keeps_the_unit_it_was_said_in():
    g = _graph(["Imagine a car moving at 20 metres per second.",
                "Imagine another car moving at 72 kmph in the opposite direction."])
    texts = {v.text() for v in run(g).values}
    assert {"v_1 = 20 m/s", "v_2 = 72 km/h", "v_rel = 40 m/s"} <= texts


def test_the_second_car_is_the_second_car():
    g = _graph(["Imagine two cars moving in opposite directions.", "The first car moves at 20 metres per second.",
                "The second car moves at 30 metres per second."])
    assert g.qty[("car", "v")]["v"] == 20.0 and g.qty[("car2", "v")]["v"] == 30.0


def test_an_incline_said_in_the_line_takes_the_angle():
    g = _graph(["Imagine a ball rolling down an incline of 30 degrees."])
    assert not any(sym == "theta" and g.parts[on].kind == "ball" for on, sym in g.qty)


def test_a_horizontal_throw_needs_its_height():
    res = run(_graph(["Imagine a ball thrown horizontally at 10 metres per second."]))
    assert not any(v.known and v.sym in ("T", "R", "H") for v in res.values) and any("h" in n for n in res.notes)


def test_from_a_place_is_a_distance_not_a_height():
    g = _graph(["Imagine a car moving at 10 metres per second from the school to a house 200 metres away."])
    assert g.qty[("car", "d")]["v"] == 200.0 and math.isclose({v.sym: v for v in run(g).values}["t"].v, 20.0)


def test_a_zero_width_river_is_refused():
    g = _graph(["Imagine a boat crossing a river 0 metres wide.", "The boat moves at 5 metres per second.",
                "The river flows at 3 metres per second."])
    assert ("river", "d") not in g.qty and run(g) is not None


# ---- live test49 ----------------------------------------------------------------------------------------------------
def test_test49_rain_speed_with_no_noun_goes_by_its_verb():
    """Heard: "The rays fall vertically at 4 mps." / "You walk at 3 mps.": v_r = 4 on the rain, v_m = 3, 5 m/s, 36.9°."""
    rays = fastpath.concept_mishear("The rays fall vertically at 4 mps.")
    assert rays == "The rain fall vertically at 4 mps."
    assert fastpath.concept_mishear("Light rays fall on the mirror at 30 degrees.") is None
    g = _graph(["Imagine you are walking in the rain.", "The rays fall vertically at 4 mps.", "You walk at 3 mps."])
    vals = {v.sym: v for v in run(g).values}
    assert math.isclose(vals["v_rel"].v, 5.0) and math.isclose(vals["θ"].v, math.degrees(math.atan(3 / 4)))


def test_a_bare_speed_in_the_rain_is_not_guessed():
    g = _graph(["Imagine you are walking in the rain.", "The speed is 4 metres per second."])
    assert not any(sym == "v" for _, sym in g.qty)
