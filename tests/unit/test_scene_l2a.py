"""F-015 L2a: pictures for the said noun (icons, glyphs, the teacher's pick) and the relative world (rain and a
walker, a river and a boat, two trains, frames of reference) against the textbook formulas; truthfulness of what is
printed."""
import asyncio
import json
import math
import re

import pytest

from copilot.core.events import Command, CommandReceived
from copilot.scene import assets, layout
from copilot.scene.compiler import context
from copilot.scene.detector import cue
from copilot.scene.ops import apply
from copilot.scene.spec import SceneOp, SceneSpec
from copilot.scene.validate import Corpus, check
from tests.unit.test_presentation_engine import send
from tests.unit.test_scene import ANSWERS, build, said, scene_lecture, scene_on


def rows(s):
    return {d.label: d.text for d in s.derived}


def num(text):
    return float(re.match(r"[-\d.]+", text).group(0))


# ---- relative world: analytic checks ---------------------------------------------------------------------------
@pytest.mark.parametrize("vr,vm", [(3, 4), (5, 2), (10, 10)])
def test_rain_and_a_walker_umbrella_angle_is_atan_of_v_man_over_v_rain(vr, vm):
    s, refused = build([f"Rain falls vertically at {vr} m/s and a man walks at {vm} m/s."], [
        {"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [vr, "m/s"]}, "dir": "down"},
        {"op": "add", "id": "m1", "kind": "man", "props": {"speed": [vm, "m/s"]}},
        {"op": "behave", "kind": "move", "target": "m1"}])
    assert refused == [] and s.world == "relative"
    r = rows(s)
    assert num(r["Umbrella tilt"]) == pytest.approx(math.degrees(math.atan(vm / vr)), rel=5e-3)
    assert r["Umbrella tilt"].endswith("forward")
    assert num(r["Rain seen by the man"]) == pytest.approx(math.hypot(vr, vm), rel=5e-3)
    assert s.stage.umbrella[0] == "m1" and s.stage.umbrella[1] == pytest.approx(math.degrees(math.atan(vm / vr)))
    # the triangle: rain, minus the man, the resultant from the first tail to the last tip
    v = s.stage.vectors
    assert len(v) == 3 and (v[2].x0, v[2].y0) == (v[0].x0, v[0].y0) and (v[2].x1, v[2].y1) == (v[1].x1, v[1].y1)


@pytest.mark.parametrize("w,u,vb", [(100, 3, 5), (60, 2, 4), (200, 1.5, 2.5)])
def test_river_crossing_straight_across_drifts_u_d_over_v(w, u, vb):
    s, _ = build([f"A river {w} m wide flows at {u} m/s; a boat at {vb} m/s heads straight across."], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"width": [w, "m"], "speed": [u, "m/s"]}},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [vb, "m/s"]}},
        {"op": "behave", "kind": "cross", "target": "b1"}])
    r = rows(s)
    assert num(r["Crossing time"]) == pytest.approx(w / vb, rel=5e-3)
    assert num(r["Drift"]) == pytest.approx(u * w / vb, rel=5e-3) and r["Drift"].endswith("downstream")
    assert num(r["Resultant speed"]) == pytest.approx(math.hypot(u, vb), rel=5e-3)
    tr = s.frames.tracks[0].pts
    river = s.stage.river
    assert tr[0][2] == pytest.approx(river[3], abs=1) and tr[-1][2] == pytest.approx(river[2], abs=1)  # bank to bank


def test_river_crossing_shortest_path_heads_upstream_and_lands_opposite():
    s, _ = build(["A river 100 m wide flows at 3 m/s. A boat at 5 m/s goes to the point straight opposite."], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"width": [100, "m"], "speed": [3, "m/s"]}},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [5, "m/s"]}},
        {"op": "behave", "kind": "cross_straight", "target": "b1"}])
    r = rows(s)
    assert num(r["Heading"]) == pytest.approx(math.degrees(math.asin(3 / 5)), rel=5e-3)
    assert num(r["Crossing time"]) == pytest.approx(100 / 4, rel=5e-3) and "Drift" not in r
    tr = s.frames.tracks[0].pts
    assert tr[-1][1] == pytest.approx(tr[0][1], abs=0.5)  # straight opposite


def test_a_boat_slower_than_the_river_cannot_land_opposite():
    s, _ = build(["The river flows at 5 m/s and the boat goes 3 m/s; can it reach the point straight opposite?"], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"speed": [5, "m/s"]}},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [3, "m/s"]}},
        {"op": "behave", "kind": "cross_straight", "target": "b1"}])
    assert rows(s)["Straight across"].startswith("not possible")


@pytest.mark.parametrize("v1,v2,gap", [(20, 30, 200), (15, 10, 500)])
def test_two_trains_towards_each_other_meet_after_gap_over_closing_speed(v1, v2, gap):
    s, _ = build([f"Two trains {gap} m apart run towards each other at {v1} m/s and {v2} m/s."], [
        {"op": "add", "id": "t1", "kind": "train", "props": {"speed": [v1, "m/s"], "gap": [gap, "m"]}, "dir": "east"},
        {"op": "add", "id": "t2", "kind": "train", "props": {"speed": [v2, "m/s"]}, "dir": "west"},
        {"op": "behave", "kind": "move", "target": "t1"}, {"op": "behave", "kind": "move", "target": "t2"}])
    r = rows(s)
    assert s.world == "relative" and num(r["Relative speed"]) == pytest.approx(v1 + v2)
    assert num(r["Time to meet"]) == pytest.approx(gap / (v1 + v2), rel=5e-3)
    a, b = s.frames.tracks
    assert a.pts[0][1] < b.pts[0][1] and s.get("t2").geom.flip and not s.get("t1").geom.flip


def test_trains_same_way_relative_speed_and_time_to_pass_by_their_lengths():
    s, _ = build(["Two trains 100 m and 150 m long run the same way at 25 m/s and 15 m/s."], [
        {"op": "add", "id": "t1", "kind": "train", "props": {"speed": [25, "m/s"], "length": [100, "m"]}, "dir": "east"},
        {"op": "add", "id": "t2", "kind": "train", "props": {"speed": [15, "m/s"], "length": [150, "m"]}, "dir": "east"},
        {"op": "behave", "kind": "move", "target": "t1"}, {"op": "behave", "kind": "move", "target": "t2"}])
    r = rows(s)
    assert num(r["Relative speed"]) == pytest.approx(10) and num(r["Time to pass"]) == pytest.approx(25)


def test_seen_from_a_body_it_stands_still_and_the_rain_slants():
    ops = [{"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [3, "m/s"]}},
           {"op": "add", "id": "m1", "kind": "man", "props": {"speed": [4, "m/s"]}},
           {"op": "behave", "kind": "move", "target": "m1"}]
    lines = ["Rain falls at 3 m/s and a man walks at 4 m/s."]
    ground, _ = build(lines, ops)
    seen, _ = build(lines, ops + [{"op": "frame", "id": "m1"}])
    assert ground.stage.rain[0] == pytest.approx(0) and seen.stage.rain[0] == pytest.approx(-53.13, abs=0.01)
    pts = seen.frames.tracks[0].pts
    assert pts[0][1] == pts[-1][1] and ground.frames.tracks[0].pts[-1][1] > ground.frames.tracks[0].pts[0][1]
    assert rows(seen) == rows(ground)  # the numbers do not depend on where it is seen from


# ---- truthfulness ------------------------------------------------------------------------------------------------
def test_a_river_speed_not_said_draws_the_drift_but_prints_no_time():
    s, _ = build(["A boat crosses a river 100 m wide at 5 m/s."], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"width": [100, "m"], "speed": [2, "m/s"]}},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [5, "m/s"]}},
        {"op": "behave", "kind": "cross", "target": "b1"}])
    assert s.get("r1").props["speed"].source == "default" and s.derived == []
    assert "river" in [v.text for v in s.stage.vectors]  # its arrow is drawn, its speed not printed
    assert s.frames.tracks[0].pts[-1][1] > s.frames.tracks[0].pts[0][1] + 10  # the drift is drawn


def test_no_compass_word_is_ever_printed():
    s, _ = build(["Rain falls at 30 degrees to the vertical at 6 m/s; a boy runs at 2 m/s."], [
        {"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [6, "m/s"], "angle": [30, "deg"]}, "dir": "down",
         "toward": "east"},
        {"op": "add", "id": "m1", "kind": "boy", "props": {"speed": [2, "m/s"]}, "dir": "west"},
        {"op": "behave", "kind": "move", "target": "m1"}])
    printed = " ".join([d.label + " " + d.text for d in s.derived] + [v.text for v in s.stage.vectors]).lower()
    assert not re.search(r"\b(east|west|north|south)\b", printed)
    # rain (3, -5.196) minus the boy (-2, 0): apparent (5, -5.196), from where he runs: tilted forward
    r = rows(s)
    assert num(r["Rain seen by the boy"]) == pytest.approx(math.hypot(5, 6 * math.cos(math.radians(30))), rel=5e-3)
    assert num(r["Umbrella tilt"]) == pytest.approx(math.degrees(math.atan2(5, 5.196)), rel=5e-3)
    assert r["Umbrella tilt"].endswith("forward")  # it runs into the rain


@pytest.mark.parametrize("op,note", [
    ({"op": "add", "id": "m1", "kind": "man", "dir": "sideways"}, "dir 'sideways'"),
    ({"op": "add", "id": "m1", "kind": "man", "dir": "east", "toward": "west"}, "toward 'west'"),
    ({"op": "add", "id": "s1", "kind": "square", "dir": "east"}, "dir: a square does not move"),
])
def test_a_bad_direction_is_refused_and_logged(op, note):
    _, refused = build(["A man and a square."], [op])
    assert any(note in r for r in refused)


def test_cross_needs_a_river_and_frame_needs_a_body():
    s, refused = build(["A boat."], [{"op": "add", "id": "b1", "kind": "boat"},
                                     {"op": "behave", "kind": "cross", "target": "b1"},
                                     {"op": "add", "id": "s1", "kind": "square"}, {"op": "frame", "id": "s1"}])
    assert "cross: there is no river to cross" in refused and "frame: 's1' is not a body or a river" in refused


def test_the_context_names_directions_and_the_frame():
    s, _ = build(["A man walks east in the rain."], [
        {"op": "add", "id": "m1", "kind": "man", "dir": "east"}, {"op": "frame", "id": "m1"}])
    assert "m1 particle \"man\" dir=east" in context(s) and context(s).endswith("seen by m1")


# ---- pictures ----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("noun,icon", [("rocket", "rocket"), ("train", "train"), ("boat", "sailboat"),
                                       ("boy", "walk"), ("plane", "plane"), ("two buses", "bus"), ("bus", "bus")])
def test_each_noun_gets_its_own_icon_never_the_car(noun, icon):
    assert assets.Pictures().match(noun) == icon


def test_a_said_kind_becomes_a_body_with_its_picture_and_its_own_physics():
    s, refused = build(["Imagine a rocket moving at 50 m/s."], [
        {"op": "add", "id": "r1", "kind": "rocket", "props": {"speed": [50, "m/s"]}},
        {"op": "behave", "kind": "move", "target": "r1"}])
    s = assets.Pictures().resolve(s)
    e = s.get("r1")
    assert refused == [] and e.kind == "car" and e.name == "rocket" and e.look.icon == "rocket"
    assert s.world == "motion"  # a picture never changes the physics


def test_a_noun_its_kind_draws_gets_no_icon():
    p = assets.Pictures()
    assert p.match("ball") == p.match("stone") == p.match("block") == p.match("car") == ""


@pytest.mark.parametrize("bad", ["<script>alert(1)</script>", "M1 1 L2 2\" onload=\"x", "javascript:alert(1)",
                                 "M1 1 L 2 2 url(#x)", "M" + " 1 1" * 2000, "M100 100 L200 200", 42, "L1 1 2 2"])
def test_a_glyph_is_path_data_only(bad):
    assert assets.clean(bad) == ""


def test_a_clean_glyph_passes():
    d = "M4 13 L20 13 M6 13 C6 9 18 9 18 13 Z"
    assert assets.clean(d) == d


class _Router:
    def __init__(self, text):
        self.text, self.calls = text, 0

    async def complete(self, msgs, **kw):
        from copilot.llm.providers import LLMResponse

        self.calls += 1

        class R:
            pass

        r = R()
        r.response, r.entry = LLMResponse(text=self.text, prompt_tokens=200, completion_tokens=80), "fake"
        return r


ROCKET = ("Imagine a rocket moving at 50 m/s.", '{"op":"add","id":"r1","kind":"car","name":"rocket","props":'
          '{"speed":[50,"m/s"]}}\n{"op":"behave","kind":"move","target":"r1"}')
YAK = ("Imagine a yak, a body moving at 2 m/s.", '{"op":"add","id":"y1","kind":"particle","name":"yak","props":'
       '{"speed":[2,"m/s"]}}\n{"op":"behave","kind":"move","target":"y1"}')
FASTER = ("Now make it faster, 80 m/s.", '{"op":"set","id":"r1","props":{"speed":[80,"m/s"]}}')


async def test_a_noun_with_no_icon_gets_one_cached_glyph_call(tmp_path):
    ANSWERS.update(dict([YAK]))
    bus, deck, eng, clock, talk, replay = await scene_lecture()
    replay.router = _Router('{"d": "M4 14 C6 8 18 8 20 14 L20 18 M6 14 L6 18"}')
    eng._scenes.glyph_dir = tmp_path
    await said(bus, eng, talk, YAK[0])
    await asyncio.sleep(0.01)
    await bus.drain()
    e = scene_on(deck).get("y1")
    assert e.look.glyph.startswith("M4 14") and replay.router.calls == 1
    assert json.loads((tmp_path / "yak.json").read_text())["d"] == e.look.glyph
    assert assets.cached_glyph("yak", tmp_path) == e.look.glyph  # the next scene reads it from disk: 0 tokens


async def test_the_teachers_picture_survives_an_edit():
    ANSWERS.update(dict([ROCKET, FASTER]))
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    await said(bus, eng, talk, ROCKET[0])
    assert scene_on(deck).get("r1").look.icon == "rocket"
    await send(bus, CommandReceived(command=Command(kind="scene_look", args={
        "slide_id": deck.live.id, "id": "r1", "icon": "plane"})))
    await said(bus, eng, talk, FASTER[0])
    e = scene_on(deck).get("r1")
    assert e.look.icon == "plane" and e.look.pick == "teacher" and e.props["speed"].value == 80
    await send(bus, CommandReceived(command=Command(kind="scene_look", args={
        "slide_id": deck.live.id, "id": "r1", "image": "javascript:alert(1)"})))
    assert scene_on(deck).get("r1").look.icon == "plane"  # a bad image is refused
    await send(bus, CommandReceived(command=Command(kind="scene_look", args={
        "slide_id": deck.live.id, "id": "r1", "own": True})))
    assert scene_on(deck).get("r1").look.icon == "" and scene_on(deck).get("r1").look.pick == "teacher"


async def test_seen_from_switches_the_frame_by_command():
    ANSWERS.update({"Imagine rain falling at 3 m/s and a man walking at 4 m/s.":
                    '{"op":"add","id":"r1","kind":"rain","props":{"speed":[3,"m/s"]}}\n'
                    '{"op":"add","id":"m1","kind":"man","props":{"speed":[4,"m/s"]}}\n'
                    '{"op":"behave","kind":"move","target":"m1"}'})
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    await said(bus, eng, talk, "Imagine rain falling at 3 m/s and a man walking at 4 m/s.")
    assert scene_on(deck).world == "relative" and scene_on(deck).get("m1").look.icon == "walk"
    await send(bus, CommandReceived(command=Command(kind="scene_frame", args={"slide_id": deck.live.id, "id": "m1"})))
    assert scene_on(deck).frame == "m1" and scene_on(deck).stage.rain[0] < 0
    await send(bus, CommandReceived(command=Command(kind="scene_frame", args={"slide_id": deck.live.id, "id": "zz"})))
    assert scene_on(deck).frame == "m1"


@pytest.mark.parametrize("line", ["Imagine rain falling vertically at 3 m/s.", "Suppose a river 100 m wide flows.",
                                  "Imagine a man walks in the rain."])
def test_rain_and_river_are_motion_cues(line):
    assert cue(line) == "motion"


def test_a_rainbow_is_not_a_cue():
    assert cue("Look at the rainbow over the hills.") is None


def test_check_and_apply_keep_the_noun_for_the_picture():
    s = SceneSpec()
    c, _ = check(SceneOp(op="add", id="b1", kind="car", name="hovercraft"), s, Corpus.of(["a fast vehicle"]))
    s = apply(s, c)
    assert s.get("b1").name == "" and s.get("b1").look.noun == "hovercraft"  # not said: not printed, still pictured
    assert layout.solve(s).get("b1").geom.shape == "body"


async def test_a_scene_that_ends_before_its_call_draws_leaves_no_empty_slide():
    # live run 2026-10-22: the provider timed out, then "let's get back to the slides" cancelled the call
    bus, deck, eng, clock, talk, replay = await scene_lecture()
    gate = asyncio.Event()

    async def stuck(lines, scene, topic, on_op):
        await gate.wait()

    replay.compile = stuck
    await talk.say("Imagine a rocket moving at a speed of 100 metres per second.")
    await bus.drain()
    assert scene_on(deck) is not None and any(b.type == "scene" for s in deck.slides for b in s.blocks)
    await talk.say("Let's get back to the slides.")
    await bus.drain()
    await eng._scenes.tick()
    await bus.drain()
    assert all(b.type != "scene" for s in deck.slides for b in s.blocks)


# ---- review of L2a: a direction not said never feeds a printed number --------------------------------------------
def _trains(d1, d2, extra=()):
    return build(["Two trains 200 m apart at 20 m/s and 30 m/s."], [
        {"op": "add", "id": "t1", "kind": "train", "props": {"speed": [20, "m/s"], "gap": [200, "m"]},
         **({"dir": d1} if d1 else {})},
        {"op": "add", "id": "t2", "kind": "train", "props": {"speed": [30, "m/s"]}, **({"dir": d2} if d2 else {})},
        {"op": "behave", "kind": "move", "target": "t1"}, {"op": "behave", "kind": "move", "target": "t2"},
        *extra])[0]


def test_trains_with_no_directions_said_print_nothing():
    assert rows(_trains("", "", [{"op": "frame", "id": "t1"}])) == {}


def test_trains_moving_apart_never_get_a_time_to_meet():
    r = rows(_trains("west", "east"))
    assert num(r["Relative speed"]) == 50 and "Time to meet" not in r and "Time to catch up" not in r


def test_tilted_rain_needs_its_toward_and_the_walkers_direction():
    base = [{"op": "add", "id": "m1", "kind": "man", "props": {"speed": [4, "m/s"]}},
            {"op": "behave", "kind": "move", "target": "m1"}]
    rain = {"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [5, "m/s"], "angle": [30, "deg"]}, "dir": "down"}
    lines = ["Rain at 5 m/s at 30 degrees to the vertical; a man walks at 4 m/s."]
    assert rows(build(lines, [rain] + base)[0]) == {}                       # no toward
    assert rows(build(lines, [{**rain, "toward": "east"}] + base)[0]) == {}  # the man's way not said
    r = rows(build(lines, [{**rain, "toward": "east"}, {**base[0], "dir": "east"}, base[1]])[0])
    # rain (2.5, -4.33) minus the man (4, 0) = (-1.5, -4.33): 4.58 m/s, 19.1° forward
    assert num(r["Rain seen by the man"]) == pytest.approx(4.58, abs=0.01) and r["Umbrella tilt"].startswith("19.1")


def test_a_walker_said_to_go_north_in_a_side_view_still_gets_the_right_vertical_rain_answer():
    s, _ = build(["Rain falls vertically at 3 m/s; a man walks north at 4 m/s."], [
        {"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [3, "m/s"]}},
        {"op": "add", "id": "m1", "kind": "man", "props": {"speed": [4, "m/s"]}, "dir": "north"},
        {"op": "behave", "kind": "move", "target": "m1"}])
    r = rows(s)
    assert num(r["Rain seen by the man"]) == 5 and num(r["Umbrella tilt"]) == pytest.approx(53.1)
    assert s.frames.tracks[0].pts[-1][1] > s.frames.tracks[0].pts[0][1]  # it walks across the stage


def test_a_river_said_to_flow_north_is_drawn_as_a_band_and_the_boat_reaches_the_far_bank():
    s, _ = build(["A river 100 m wide flows north at 3 m/s; a boat at 5 m/s crosses straight across."], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"width": [100, "m"], "speed": [3, "m/s"]}, "dir": "north"},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [5, "m/s"]}},
        {"op": "behave", "kind": "cross", "target": "b1"}])
    assert num(rows(s)["Crossing time"]) == 20
    assert s.frames.tracks[0].pts[-1][2] == pytest.approx(s.stage.river[2], abs=1)


def test_a_standing_walker_gets_no_side_word_and_a_still_boat_no_river_blame():
    s, _ = build(["Rain at 5 m/s at 30 degrees towards the east; the man stands, 0 m/s."], [
        {"op": "add", "id": "r1", "kind": "rain", "props": {"speed": [5, "m/s"], "angle": [30, "deg"]}, "dir": "down",
         "toward": "east"},
        {"op": "add", "id": "m1", "kind": "man", "props": {"speed": [0, "m/s"]}, "dir": "east"},
        {"op": "behave", "kind": "move", "target": "m1"}])
    assert rows(s)["Umbrella tilt"] == "30°"
    s, _ = build(["The river flows at 0 m/s and the boat at 0 m/s."], [
        {"op": "add", "id": "r1", "kind": "river", "props": {"speed": [0, "m/s"]}},
        {"op": "add", "id": "b1", "kind": "boat", "props": {"speed": [0, "m/s"]}},
        {"op": "behave", "kind": "cross_straight", "target": "b1"}])
    assert rows(s)["Straight across"] == "not possible (the boat has no speed)"
