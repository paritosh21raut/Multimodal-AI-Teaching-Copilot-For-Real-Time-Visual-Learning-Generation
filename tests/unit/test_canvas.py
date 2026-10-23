"""F-016 C1 open canvas: things, places, relation / action primitives, sizes, pictures, safety, Imagine Mode."""
from __future__ import annotations

import io
import math

import pytest

from copilot.core.events import Command, CommandReceived
from copilot.scene import pictures, safety
from copilot.scene.compiler import ReplayCompiler
from copilot.scene.spec import SceneOp
from copilot.scene.worlds import canvas, motion
from tests.unit.test_presentation_engine import act, ready, send
from tests.unit.test_scene import build, said, scene_lecture, scene_on

H = canvas.H


def thing(id_, name, size="", **kw):
    return {"op": "add", "id": id_, "kind": "thing", "name": name, **({"size": size} if size else {}), **kw}


def rel(kind, a, b, **kw):
    return {"op": "relate", "kind": kind, "a": a, "b": b, **kw}


def beh(kind, target, **kw):
    return {"op": "behave", "kind": kind, "target": target, **kw}


def box(s, i):
    g = s.get(i).geom
    return g.c[0], g.c[1], g.wh[0], g.wh[1]


# ---- the goal sentences ------------------------------------------------------------------------------------------------
def test_a_cube_rests_on_the_mountain_top_and_both_are_readable():
    s, refused = build(["Imagine a cube on a mountain."], [thing("m1", "mountain", "huge"), thing("c1", "cube", "small"),
                                                           rel("on_top_of", "c1", "m1")])
    assert s.world == "canvas" and not refused
    mx, my, mw, mh = box(s, "m1")
    cx, cy, cw, ch = box(s, "c1")
    assert mh >= 0.35 * H and ch >= 0.08 * H and ch <= 0.6 * mh       # main >= 35 %, nothing < 8 %
    assert cx == mx and math.isclose(cy + ch / 2, my - mh / 2 + canvas.ON_TOP * mh, abs_tol=0.2)  # resting on its top
    assert s.get("c1").look.form == "cube" and s.get("c1").geom.z > s.get("m1").geom.z


def test_a_bicycle_under_the_ocean_is_in_the_water_on_the_sea_floor():
    s, _ = build(["Picture a bicycle under the ocean."], [{"op": "add", "id": "o1", "kind": "place", "name": "ocean"},
                                                          thing("b1", "bicycle"), rel("under", "b1", "o1")])
    bd = s.stage.backdrop
    x, y, w, h = box(s, "b1")
    assert bd.type == "water" and bd.name == "ocean" and y - h / 2 > bd.surface and math.isclose(y + h / 2, bd.ground)
    assert h >= 0.35 * H and s.get("o1").geom is None


def test_a_laptop_on_a_flying_airplane_sits_on_its_top_and_moves_with_it():
    s, _ = build(["Imagine a laptop flying on top of an airplane."],
                 [thing("p1", "airplane", "large"), thing("l1", "laptop", "small"), rel("on_top_of", "l1", "p1"),
                  beh("fly", "p1")])
    px, py, pw, ph = box(s, "p1")
    lx, ly, lw, lh = box(s, "l1")
    assert ly + lh / 2 <= py - ph / 2 + canvas.ON_TOP * ph + 0.2
    tr = {t.id: t for t in s.frames.tracks}
    for a, b in zip(tr["p1"].pts, tr["l1"].pts):  # carried: the same displacement at every sample
        assert math.isclose(a[1] - px, b[1] - lx, abs_tol=0.11) and math.isclose(a[2] - py, b[2] - ly, abs_tol=0.11)
    assert tr["p1"].pts[-1][1] > tr["p1"].pts[0][1] + 300  # it flies across


def test_a_book_thrown_up_follows_the_launch_kinematics():
    s, _ = build(["Imagine you throw a book up in the air."], [thing("k1", "book", dir="up"), beh("throw", "k1")])
    tr = s.frames.tracks[0]
    T = 2 * motion.DEFAULTS["launch_speed"] / motion.G_EARTH   # straight up: v sin 90° / g, twice
    assert math.isclose(tr.pts[-1][0], T, rel_tol=1e-3)
    top = min(tr.pts, key=lambda q: q[2])
    assert math.isclose(top[0], T / 2, abs_tol=0.06) and all(math.isclose(q[1], tr.pts[0][1]) for q in tr.pts)
    assert s.derived == []  # the speed was not said: drawn, never printed


def test_a_bus_that_brakes_slows_to_a_stop_and_its_rider_leans_forward():
    s, _ = build(["Imagine you're on a bus and it brakes."],
                 [thing("u1", "bus", "large"), thing("y1", "you", "small"), rel("inside", "y1", "u1"),
                  beh("brake", "u1")])
    tr = {t.id: t for t in s.frames.tracks}
    bus, you = tr["u1"].pts, tr["y1"].pts
    vs = [q[4] for q in bus]
    assert vs[0] > 0 and vs[-1] == 0 and all(b <= a + 1e-9 for a, b in zip(vs, vs[1:]))
    braking = [i for i, q in enumerate(bus) if canvas.BRAKE_AT < q[0] and q[4] > 0]
    assert braking and all(you[i][3] > 0 for i in braking)            # leans forward (inertia)
    assert all(you[i][3] == 0 for i, q in enumerate(bus) if q[0] <= canvas.BRAKE_AT)
    assert you[-1][1] - you[0][1] > bus[-1][1] - bus[0][1]               # slid forward in the bus
    assert s.derived == []


def test_a_said_speed_and_deceleration_print_live_readouts():
    s, _ = build(["The bus moves at 20 m/s and brakes at 5 m/s squared."],
                 [thing("u1", "bus", props={"speed": [20, "m/s"], "acceleration": [-5, "m/s^2"]}),
                  beh("brake", "u1")])
    assert [d.live for d in s.derived] == ["v", "x"]
    pts = s.frames.tracks[0].pts
    assert math.isclose(max(q[5] for q in pts), 20 * canvas.BRAKE_AT + 20 * 20 / (2 * 5), rel_tol=1e-3)


def test_focus_makes_a_camera_box_and_zoom_out_clears_it():
    ops = [thing("m1", "mountain", "huge"), thing("c1", "cube", "small"), rel("on_top_of", "c1", "m1")]
    s, _ = build(["Imagine a cube on a mountain. Look at the cube."], ops + [{"op": "focus", "ids": ["c1"]}])
    x, y, w, h = s.stage.camera
    assert w >= canvas.W / canvas.MAX_ZOOM - 0.1 and math.isclose(w / h, canvas.W / canvas.H, rel_tol=1e-3)
    cx, cy, _, _ = box(s, "c1")
    assert x <= cx <= x + w and y <= cy <= y + h
    s, refused = build(["Imagine a cube on a mountain. Look at the cube. Zoom out."],
                       ops + [{"op": "focus", "ids": ["c1"]}, {"op": "focus", "ids": []}])
    assert s.stage.camera is None and not refused


def test_a_focused_part_opens_the_magnifier_at_its_place_on_the_whole():
    ops = [thing("b1", "bicycle"), thing("w1", "wheel", "small"), rel("part_of", "w1", "b1")]
    s, _ = build(["A bicycle and its wheel."], ops)
    assert s.get("w1").geom.hidden and s.stage.magnifier is None
    s, _ = build(["A bicycle and its wheel. Zoom into the wheel."], ops + [{"op": "focus", "ids": ["w1"]}])
    m, (bx, by, bw, bh) = s.stage.magnifier, box(s, "b1")
    assert s.get("w1").geom.hidden and s.stage.camera is None and m.of == "w1"   # the inset, not the camera
    assert m.at[0] == bx and by < m.at[1] <= by + bh / 2                         # a wheel: the bottom of the bicycle
    assert m.r >= 0.2 * H and abs(m.c[0] - bx) > m.r                              # beside the whole, not over it


@pytest.mark.parametrize("kind, check_", [
    ("spin", lambda tr: tr.pts[-1][3] != 0),
    ("grow", lambda tr: tr.sa[-1][0] > 1.4),
    ("vanish", lambda tr: tr.sa[-1][2] == 0),
    ("shake", lambda tr: len({q[1] for q in tr.pts}) > 3),
    ("walk", lambda tr: tr.pts[-1][1] > tr.pts[0][1] and min(q[2] for q in tr.pts) < tr.pts[0][2]),
])
def test_drawn_actions_move_the_picture(kind, check_):
    s, refused = build(["A dog."], [thing("d1", "dog"), beh(kind, "d1")])
    assert not refused and check_(s.frames.tracks[0])


def test_emit_sits_beside_a_motion_and_push_draws_an_arrow():
    s, _ = build(["A fish swims and blows bubbles."], [thing("f1", "fish"), beh("move", "f1"),
                                                      beh("emit", "f1", text="bubbles"), thing("c1", "cart"),
                                                      beh("push", "c1")])
    assert {b.kind for b in s.behaviors if b.target == "f1"} == {"move", "emit"}
    assert [(e.of, e.kind) for e in s.stage.effects] == [("f1", "bubbles"), ("c1", "push")]


def test_a_new_place_replaces_the_old_and_keeps_its_relations():
    s, _ = build(["A boat on a lake. Now the boat is in the sea."],
                 [{"op": "add", "id": "p1", "kind": "place", "name": "lake"}, thing("b1", "boat"),
                  rel("at", "b1", "p1"), {"op": "add", "id": "p2", "kind": "place", "name": "sea"}])
    assert [e.id for e in s.entities if e.kind == "place"] == ["p2"] and s.relations[0].b == "p2"


# ---- the validator -----------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("op, why", [
    ({"op": "add", "id": "t1", "kind": "thing"}, "needs its said noun"),
    ({"op": "add", "id": "t1", "kind": "thing", "name": "<svg onload=x>"}, "needs its said noun"),
    ({"op": "add", "id": "t1", "kind": "thing", "name": "nude man"}, "blocked noun"),
    ({"op": "relate", "kind": "on_top_of", "a": "t1", "b": "s1"}, "things, bodies and the place"),
    ({"op": "relate", "kind": "between", "a": "t1", "b": "t2"}, "between: needs"),
    ({"op": "behave", "kind": "emit", "target": "t1", "text": "lava"}, "emit:"),
    ({"op": "behave", "kind": "chase", "target": "t1"}, "needs another thing"),
    ({"op": "behave", "kind": "transform_into", "target": "t1", "text": "a corpse"}, "blocked"),
    ({"op": "behave", "kind": "dance", "target": "t1"}, "unknown behaviour"),
])
def test_bad_canvas_ops_are_refused(op, why):
    base = [thing("t1", "cat"), thing("t2", "dog"), {"op": "add", "id": "s1", "kind": "square", "name": "square"}]
    _, refused = build(["A cat, a dog and a square."], base + [op])
    assert any(why in r for r in refused), refused


def test_parts_are_at_most_four_and_sizes_come_from_the_list():
    ops = [thing("b1", "bicycle")] + [x for i in range(5) for x in (thing(f"p{i}", "part"), rel("part_of", f"p{i}", "b1"))]
    s, refused = build(["A bicycle."], ops + [thing("t1", "tree", "gigantic")])
    assert sum(r.kind == "part_of" for r in s.relations) == 4 and any("has 4 parts" in r for r in refused)
    assert any("size 'gigantic' refused" in r for r in refused) and s.get("t1").size == ""


def test_an_unsaid_noun_is_drawn_but_not_printed():
    s, _ = build(["Imagine something on a table."], [thing("t1", "laptop")])
    assert s.get("t1").label.source == "none" and s.get("t1").look.noun == "laptop"


# ---- pictures ----------------------------------------------------------------------------------------------------------
def test_the_emoji_ladder_by_alias_word_and_head():
    e = pictures.Emoji()
    assert e.match("book") == "closed book" and e.match("airplane") == "airplane" and e.match("toy car") == "automobile"
    assert e.match("bicycle") == "bicycle" and e.match("quantum flux") == "" and e.match("nude man") == ""


class _Resp:
    def __init__(self, status, content):
        self.status_code, self.content = status, content


class _Client:
    def __init__(self, resp=None, err=None):
        self.resp, self.err, self.calls = resp, err, 0

    def get(self, url, **kw):
        self.calls += 1
        if self.err:
            raise self.err
        return self.resp


def _png() -> bytes:
    from PIL import Image
    b = io.BytesIO()
    Image.new("RGBA", (600, 600), (200, 30, 30, 255)).save(b, "PNG")
    return b.getvalue()


def test_a_picture_is_fetched_once_re_encoded_and_then_cached(tmp_path):
    c = _Client(_Resp(200, _png()))
    url = pictures.fetch("dog", tmp_path, client=c)
    assert url == "/scene-pic/dog.png" and c.calls == 1
    from PIL import Image
    assert max(Image.open(tmp_path / "dog.png").size) <= pictures.MAX_PX
    assert pictures.fetch("dog", tmp_path, client=c) == url and c.calls == 1  # cache hit
    assert pictures.cached("dog", tmp_path) == url


@pytest.mark.parametrize("client", [_Client(err=OSError("offline")), _Client(_Resp(404, b"")),
                                    _Client(_Resp(200, b"<html>not an image</html>"))])
def test_offline_or_a_bad_answer_leaves_no_picture(tmp_path, client):
    assert pictures.fetch("dog", tmp_path, client=client) == "" and not list(tmp_path.iterdir())


def test_picturable_lines():
    assert pictures.picturable("A cat sleeps under a table.") and pictures.picturable("it starts to fall")
    assert pictures.picturable("we get 5 metres per second")
    assert not pictures.picturable("So the derivative is the slope.") and not pictures.picturable("Any questions?")
    assert pictures.picturable("and the thing goes", ["thing"])


# ---- safety ------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("text, bad", [("a bullet fired from a gun", ""), ("a bomb explosion", ""),
                                       ("red blood cells", ""), ("the knee joint", ""), ("a nude man", "nude"),
                                       ("self-harm", "self-harm"), ("a bloody knife", "bloody")])
def test_the_blocklist_keeps_physics_and_biology_words(text, bad):
    assert safety.blocked(text) == bad


# ---- the controller: safety, unsafe, pictures, Imagine Mode ------------------------------------------------------------
ANSWERS = {
    "Imagine a cube on a mountain.": '{"op":"add","id":"m1","kind":"thing","name":"mountain","size":"huge"}\n'
                                     '{"op":"add","id":"c1","kind":"thing","name":"cube","size":"small"}\n'
                                     '{"op":"relate","kind":"on_top_of","a":"c1","b":"m1"}',
    "Now imagine it on the moon.": '{"op":"add","id":"n1","kind":"place","name":"moon"}',
    "Imagine a dog in a weird scene.": '{"op":"add","id":"d1","kind":"thing","name":"dog"}\n{"op":"unsafe"}\n'
                                       '{"op":"add","id":"d2","kind":"thing","name":"cat"}',
    "A dog stands in a garden.": '{"op":"add","id":"g1","kind":"place","name":"garden"}\n'
                                 '{"op":"add","id":"d1","kind":"thing","name":"dog"}',
    "Now imagine a rocket in space.": '{"op":"add","id":"s1","kind":"place","name":"space"}\n'
                                      '{"op":"add","id":"r1","kind":"thing","name":"rocket"}',
}


async def canvas_lecture(tmp_path):
    bus, deck, eng, clock, talk, replay = await scene_lecture()
    replay = ReplayCompiler(ANSWERS)
    eng._scenes.compiler = replay
    eng._scenes.fetch_pictures = False
    eng._scenes.pics_dir = tmp_path
    return bus, deck, eng, clock, talk, replay


async def test_a_blocked_line_is_never_sent(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await said(bus, eng, talk, "Imagine a nude man on a beach.")
    assert replay.calls == [] and scene_on(deck) is None


async def test_the_unsafe_op_drops_the_call_and_draws_nothing(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await said(bus, eng, talk, "Imagine a dog in a weird scene.")
    assert eng._scenes.unsafe == 1 and (scene_on(deck) is None or scene_on(deck).entities == [])


async def test_a_cached_picture_is_used_at_once_and_a_canvas_cue_that_refers_edits(tmp_path):
    (tmp_path / "mountain.png").write_bytes(_png())
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await said(bus, eng, talk, "Imagine a cube on a mountain.")
    s = scene_on(deck)
    assert s.get("m1").look.emoji == "/scene-pic/mountain.png" and s.get("c1").look.form == "cube"
    slide = deck.live.id
    await said(bus, eng, talk, "Now imagine it on the moon.")
    assert deck.live.id == slide and scene_on(deck).get("n1") is not None   # "it": the same scene


async def test_the_teachers_picture_for_a_thing_survives_edits(tmp_path):
    (tmp_path / "mountain.png").write_bytes(_png())
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await said(bus, eng, talk, "Imagine a cube on a mountain.")
    await send(bus, CommandReceived(command=Command(kind="scene_look", args={
        "slide_id": deck.live.id, "id": "m1", "icon": "mountain"})))
    await said(bus, eng, talk, "Now imagine it on the moon.")
    lk = scene_on(deck).get("m1").look
    assert lk.pick == "teacher" and lk.icon == "mountain" and lk.emoji == ""


async def test_imagine_mode_draws_picturable_lines_until_end_then_one_recap(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await send(bus, CommandReceived(command=Command(kind="imagine_mode", args={"on": True})))
    assert deck.imagine and deck.sim_mode == deck.live.id and deck.live.title == "Imagine"
    await said(bus, eng, talk, "So what do you think about that?")       # nothing to picture: no call
    assert replay.calls == []
    await said(bus, eng, talk, "A dog stands in a garden.")
    assert replay.calls == [["A dog stands in a garden."]] and scene_on(deck).get("d1") is not None
    first = deck.live.id
    await said(bus, eng, talk, "Okay, let's get back to the slides.")      # only End ends it
    assert deck.sim_mode is not None and deck.imagine
    await said(bus, eng, talk, "Now imagine a rocket in space.")         # a new scene, the same mode
    assert deck.live.id != first and scene_on(deck).get("r1") is not None and eng._sims.mode.imagine
    assert len(eng._sims.mode.names) == 2
    await send(bus, CommandReceived(command=Command(kind="imagine_mode", args={"on": False})))
    assert deck.sim_mode is None and not deck.imagine and eng._sims.mode is None


def test_the_contract_lists_are_wired_into_the_prompt():
    from copilot.scene.compiler import SYSTEM
    for word in ("thing", "place", "on_top_of", "transform_into", "unsafe", "brake", "bubbles"):
        assert word in SYSTEM
    assert SceneOp(op="add", id="t1", kind="thing", name="cat", size="small").size == "small"


# ---- review fixes ----------------------------------------------------------------------------------------------------
def test_a_brake_with_only_a_said_speed_prints_no_stopping_distance():
    s, _ = build(["The bus moves at 20 m/s and then it brakes."],
                 [thing("u1", "bus", props={"speed": [20, "m/s"]}), beh("brake", "u1")])
    assert s.derived == [] and s.frames.tracks[0].pts[-1][4] == 0  # drawn to a stop, nothing printed


@pytest.mark.parametrize("text", ["a retarding force", "uniformly retarded motion", "visible to the naked eye"])
def test_kinematics_and_everyday_words_are_not_blocked(text):
    assert safety.blocked(text) == ""


def test_a_name_is_matched_as_a_whole_word():
    assert pictures.picturable("and the cars go", ["car"]) and not pictures.picturable("so the carbon is", ["car"])


async def test_an_empty_imagine_stage_goes_when_the_first_scene_opens(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await send(bus, CommandReceived(command=Command(kind="imagine_mode", args={"on": True})))
    empty = deck.live.id
    await said(bus, eng, talk, "Now imagine a rocket in space.")
    assert deck.live.id != empty and empty not in [x.id for x in deck.slides]
    assert eng._sims.mode.imagine and eng._sims.mode.names == [deck.live.title]


# ---- test32 fixes (2026-10-23) ---------------------------------------------------------------------------------------
def test_one_thing_alone_fills_the_slide_and_two_keep_their_real_size_order():
    s, _ = build(["Imagine a book."], [thing("k1", "book")])
    _, _, _, h = box(s, "k1")
    room = canvas.GROUND - canvas.TOP - 50
    assert h >= 0.8 * room and s.stage.size == (canvas.W, canvas.H)          # full size at first
    s, _ = build(["Imagine a boy holding a book."], [thing("b1", "boy"), thing("k1", "book"),
                                                     rel("holding", "k1", "b1")])
    bx, by, bw, bh = box(s, "b1")
    kx, ky, kw, kh = box(s, "k1")
    assert 0.25 * bh <= kh <= 0.6 * bh and bh >= 0.6 * room                 # a book is clearly smaller, both readable
    assert bx < kx < bx + bw / 2 + kw and by - bh / 2 < ky < by + bh / 2      # in his hand, beside his middle


def test_a_stack_and_a_mountain_keep_their_order_and_fit_the_stage():
    s, _ = build(["A dog on a man, a cat on the dog, a rat on the cat."],
                 [thing("n1", "man"), thing("d1", "dog"), thing("c1", "cat"), thing("r1", "rat"),
                  rel("on_top_of", "d1", "n1"), rel("on_top_of", "c1", "d1"), rel("on_top_of", "r1", "c1")])
    hs = [box(s, i)[3] for i in ("n1", "d1", "c1", "r1")]
    assert hs == sorted(hs, reverse=True) and hs[-1] >= canvas.MIN_H * canvas.H
    assert min(box(s, i)[1] - box(s, i)[3] / 2 for i in ("n1", "d1", "c1", "r1")) >= canvas.TOP   # under the title
    s, _ = build(["Imagine yourself at the top of a mountain."],
                 [thing("m1", "mountain"), thing("y1", "yourself"), rel("on_top_of", "y1", "m1")])
    assert box(s, "y1")[3] <= 0.3 * box(s, "m1")[3]


def test_a_person_is_drawn_whole_and_posed_by_what_they_do():
    assert pictures.person("boy") == "person standing" and pictures.person("yourself") == "person standing"
    assert pictures.person("you", "walk") == "person walking" and pictures.person("woman", "chase") == "woman running"
    assert pictures.person("dog") == "" and pictures.place_type("the moon") == "moon"


async def test_engine_kinds_get_pictures_too(tmp_path):
    # test32: "car" and "basketball" came as the motion kinds car / ball and stayed placeholders
    (tmp_path / "automobile.png").write_bytes(_png())
    (tmp_path / "person-standing.png").write_bytes(_png())
    ANSWERS["Imagine you are riding a car in the space."] = (
        '{"op":"add","id":"s1","kind":"place","name":"space"}\n{"op":"add","id":"c1","kind":"car","name":"car"}\n'
        '{"op":"add","id":"y1","kind":"thing","name":"you"}\n{"op":"relate","kind":"inside","a":"y1","b":"c1"}')
    ANSWERS["Imagine you are riding a rocket in the space."] = (
        '{"op":"add","id":"s1","kind":"place","name":"space"}\n{"op":"add","id":"r1","kind":"thing","name":"rocket"}')
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    await said(bus, eng, talk, "Imagine you are riding a car in the space.")
    s = scene_on(deck)
    assert s.world == "canvas" and s.get("c1").look.emoji == "/scene-pic/automobile.png"
    assert s.get("y1").look.emoji == "/scene-pic/person-standing.png"
    first = deck.live.id
    await said(bus, eng, talk, "Imagine you are riding a rocket in the space.")   # "you" is not the open scene's
    assert deck.live.id != first and scene_on(deck).get("r1") is not None


async def test_a_canvas_cue_opens_a_full_slide_canvas_at_once(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    eng._scenes.compiler = None  # the model has not answered yet: the stage alone
    async with eng._lock:
        await eng._scenes.start(["Imagine you are standing with a tall stick in your hand."], origin="cue")
    s = scene_on(deck)
    assert s.world == "canvas" and s.entities == [] and s.stage.size == (canvas.W, canvas.H)   # no layout jump later
    from copilot.scene.detector import cue
    assert cue("Imagine you are standing with a tall stick in your hand.") == "canvas"
    assert cue("Imagine yourself at the top of a building.") == "canvas" and cue("Suppose you are given a matrix.") is None


def test_back_to_the_slide_ends_a_scene():
    from copilot.simulation.detector import end_cue
    assert end_cue("Back to the slide.") and end_cue("Let's get back to the slide.")
    assert not end_cue("We will go back to the slides later.")


async def test_an_end_with_nothing_to_recap_shows_the_slide_before(tmp_path):
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    before = deck.live.id
    await said(bus, eng, talk, "Imagine a cube on a mountain.")
    assert deck.live.id != before
    eng._sims.mode.collected.clear()                           # nothing worth a recap was said
    await said(bus, eng, talk, "Let's get back to the slides.")
    assert deck.sim_mode is None and deck.live.id == before and deck.following


def test_a_photo_matte_must_be_one_whole_object():
    import numpy as np
    from copilot.scene.photos import judge
    a = np.zeros((100, 100), np.uint8)
    a[20:80, 30:70] = 255
    assert judge(a) == ""
    two = np.zeros((100, 100), np.uint8)
    two[20:40, 10:30] = 255
    two[60:80, 60:80] = 255
    assert "several" in judge(two)                              # players, two spears, chairs
    trunk = a.copy()
    trunk[:, 45:55] = 255
    assert "cut off" in judge(trunk)                            # a tree trunk running out of the photo
    assert "share" in judge(np.full((100, 100), 255, np.uint8))


class _Photos:
    def __init__(self):
        self.asked = []

    @staticmethod
    def wanted(noun):
        from copilot.scene.photos import Photos
        return Photos.wanted(noun)

    def cached(self, noun):
        return ""

    def cached_place(self, name):
        return ""

    async def thing(self, noun):
        self.asked.append(noun)
        return f"/scene-pic/photo-{noun}.png"

    async def place(self, name):
        self.asked.append("place:" + name)
        return "/media/0123456789abcdef.jpg"


async def test_a_noun_with_no_3d_picture_gets_a_photo_and_a_place_its_backdrop(tmp_path):
    ANSWERS["Imagine a man with a spear in the desert."] = (
        '{"op":"add","id":"d0","kind":"place","name":"desert"}\n{"op":"add","id":"m1","kind":"thing","name":"man"}\n'
        '{"op":"add","id":"s1","kind":"thing","name":"spear"}\n{"op":"relate","kind":"holding","a":"s1","b":"m1"}')
    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    eng._scenes.photos = ph = _Photos()
    eng._scenes.fetch_pictures = True
    eng._scenes.emoji = pictures.Emoji()
    await said(bus, eng, talk, "Imagine a man with a spear in the desert.")
    o = eng._scenes.open
    import asyncio
    await asyncio.gather(*[t for t in o.glyph_tasks if t.get_name() == "scene:photo"])
    await bus.drain()
    s = scene_on(deck)
    assert "man" not in ph.asked and "spear" in ph.asked                    # a person: never a photo; spear: no emoji
    assert s.get("s1").look.photo == "/scene-pic/photo-spear.png"
    assert s.stage.backdrop.photo == "/media/0123456789abcdef.jpg" and s.stage.backdrop.type == "desert"


def test_a_command_line_in_a_fixture_presses_a_button():
    from copilot.sim.simulator import parse_script
    sc = parse_script("Hello.\n@command imagine_mode on=true\nA dog in a garden.\n@command imagine_mode on=false\n")
    assert sc.utterances[1].commands == [("imagine_mode", {"on": True})] and sc.tail == [("imagine_mode", {"on": False})]


async def test_a_scene_that_drew_nothing_goes_when_the_next_cue_opens_a_scene(tmp_path):
    # C1 live run: the boy's call was still running when the dog's cue came; its empty slide stayed in the deck
    import asyncio

    class Slow(ReplayCompiler):
        async def compile(self, lines, scene, topic, on_op):
            if lines and lines[-1].startswith("Imagine a boy"):
                await asyncio.sleep(30)  # the model has not answered yet
            return await super().compile(lines, scene, topic, on_op)

    bus, deck, eng, clock, talk, replay = await canvas_lecture(tmp_path)
    eng._scenes.compiler = Slow(ANSWERS)
    await talk.say("Imagine a boy holding a book.")
    await bus.drain()
    empty = deck.live.id
    assert eng._scenes.open is not None and scene_on(deck).entities == []
    await said(bus, eng, talk, "Imagine a cube on a mountain.")
    assert empty not in [x.id for x in deck.slides] and scene_on(deck).get("m1") is not None


def test_a_sphere_inscribed_in_a_cuboid_is_drawn_inside_it():
    # C1 live run: "a cuboid with a sphere inside it" came as inscribed_in, refused, and the two stood side by side
    from copilot.scene import layout
    from copilot.scene.ops import apply
    from copilot.scene.spec import SceneSpec
    from copilot.scene.validate import Corpus, check
    s = SceneSpec()
    for op in (SceneOp(op="add", id="c1", kind="cuboid", name="cuboid"),
               SceneOp(op="add", id="s1", kind="sphere", name="sphere"),
               SceneOp(op="relate", kind="inscribed_in", a="s1", b="c1")):
        ok, why = check(op, s, Corpus.of(["Imagine a cuboid with a sphere inside it."]))
        assert ok is not None, why
        s = apply(s, ok)
    assert [(r.kind, r.a, r.b) for r in s.relations] == [("inside", "s1", "c1")]
    out = layout.solve(s)
    assert out.world == "canvas" and out.get("c1").geom.glass


@pytest.mark.parametrize("line, world", [("Imagine you are given a triangle with sides 3, 4, 5.", "geometry"),
                                         ("Imagine we are solving a quadratic.", None),
                                         ("Imagine you are solving a quadratic.", None),
                                         ("Imagine you are in a rocket going to the sun.", "canvas"),
                                         ("Imagine a car moving at 20 metres per second.", "motion")])
def test_you_in_a_scene_is_a_canvas_only_when_nothing_else_decides(line, world):
    from copilot.scene.detector import cue
    assert cue(line) == world


def test_a_measured_solid_keeps_the_geometry_world_and_its_numbers():
    # review: "a cube of side 4 cm with a sphere inside it" must not lose the said 4 cm and the computed volume
    from copilot.scene import layout
    from copilot.scene.ops import apply
    from copilot.scene.spec import SceneSpec
    from copilot.scene.validate import Corpus, check
    lines = ["Imagine a cube of side 4 cm with a sphere inside it."]
    s = SceneSpec()
    for op in (SceneOp(op="add", id="c1", kind="cube", name="cube", props={"side": [4, "cm"]}),
               SceneOp(op="add", id="s1", kind="sphere", name="sphere"),
               SceneOp(op="relate", kind="inside", a="s1", b="c1")):
        ok, why = check(op, s, Corpus.of(lines))
        assert ok is not None, why
        s = apply(s, ok)
    assert layout.world_of(s) == "geometry"
    out = layout.solve(s)
    assert any("4 cm" in (e.geom.note or "") or any("4 cm" in d[2] for d in (e.geom.dims or []))
               for e in out.entities if e.geom)


async def test_a_failed_photo_search_is_tried_again_but_a_judged_miss_is_not(tmp_path):
    # review: a slow / failed search must not block the noun's photo for the whole lecture
    from types import SimpleNamespace

    from copilot.scene.photos import Photos

    class Finder:
        def __init__(self, images):
            self.images, self.calls = images, 0
            self.cache = SimpleNamespace(path=lambda i: f"/nowhere/{i}.jpg")

        async def find(self, q, kind):
            self.calls += 1
            return SimpleNamespace(images=self.images, reason="budget")

    f = Finder([])
    ph = Photos(f, matting=object(), pics_dir=tmp_path)
    assert await ph.thing("table") == "" and await ph.thing("table") == "" and f.calls == 2   # asked again
    f = Finder([SimpleNamespace(id="x1", title="t", aspect=1.0)])
    ph = Photos(f, matting=object(), pics_dir=tmp_path)
    assert await ph.thing("table") == "" and await ph.thing("table") == "" and f.calls == 1   # judged: once
    assert await ph.place("table") == "" and f.calls == 2 and "table" in ph.place_misses      # places apart
