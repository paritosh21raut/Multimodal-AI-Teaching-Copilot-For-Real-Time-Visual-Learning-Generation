"""F-015 L1 Live Scene Engine: contract, ops, validator (truthfulness), world engines vs exact values, plot parser
safety, JSONL stream parse, detector, provider streaming, and the controller path (a recorded answer -> slide patch,
0 tokens)."""
import json
import math

import httpx
import pytest

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, RepresentationIntent, SimulationModeChanged
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.scene import layout
from copilot.scene.compiler import JsonlStream, ReplayCompiler, context, messages
from copilot.scene.detector import SceneDetector, cue, wants_edit
from copilot.scene.ops import apply
from copilot.scene.spec import SceneOp, SceneSpec
from copilot.scene.validate import Corpus, check
from copilot.scene.worlds import geometry, motion, plot
from copilot.simulation.detector import SimulationDetector
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines


def build(lines, ops):
    """Ops through the validator and apply (refusals collected), then solved."""
    s, corpus, refused = SceneSpec(), Corpus.of(lines), []
    for o in ops:
        c, why = check(SceneOp(**o), s, corpus)
        if c is None:
            refused.append(why)
            continue
        refused += c.notes
        s = apply(s, c)
    return layout.solve(s), refused


SQ = {"op": "add", "id": "s1", "kind": "square", "name": "square", "props": {"side": [4, "cm"]}}


# ---- contract and ops ---------------------------------------------------------------------------------------------
def test_a_solved_scene_round_trips_through_json():
    s, _ = build(["Imagine a square of side 4 cm, a circle inside it."],
                 [SQ, {"op": "add", "id": "c1", "kind": "circle", "name": "circle"},
                  {"op": "relate", "kind": "inscribed_in", "a": "c1", "b": "s1"}])
    assert SceneSpec.model_validate_json(s.model_dump_json()) == s
    with pytest.raises(ValueError):
        SceneSpec.model_validate({**s.model_dump(), "extra": 1})


def test_every_op_applies():
    lines = ["Imagine a ball at 3 m/s, label it A, then remove the box."]
    s, refused = build(lines, [
        {"op": "add", "id": "b1", "kind": "ball", "name": "ball", "props": {"speed": [3, "m/s"]}},
        {"op": "add", "id": "k1", "kind": "block", "name": "box"},
        {"op": "behave", "kind": "move", "target": "b1"},
        {"op": "set", "id": "b1", "props": {"speed": [3, "m/s"]}},
        {"op": "label", "id": "b1", "text": "A"},
        {"op": "focus", "ids": ["b1"]},
        {"op": "relate", "kind": "left_of", "a": "k1", "b": "b1"},
        {"op": "remove", "id": "k1"},
    ])
    assert not refused and s.rev == 8
    assert [e.id for e in s.entities] == ["b1"] and s.relations == [] and s.focus == ["b1"]
    assert s.get("b1").label.text == "A" and s.behaviors[0].kind == "move"
    assert s.get("b1").props["speed"].source == "said"


def test_a_repeated_add_merges_so_a_retried_stream_is_harmless():
    s, refused = build(["Imagine a square of side 4 cm."], [SQ, SQ])
    assert len(s.entities) == 1 and not refused


# ---- validator: truthfulness ----------------------------------------------------------------------------------------
def test_an_unsaid_number_is_drawn_but_never_printed():
    s, _ = build(["Imagine a square."], [{**SQ, "props": {"side": [5, "cm"]}}])
    e = s.get("s1")
    assert e.props["side"].source == "default"
    assert s.derived == [] and e.geom.dims == []  # no area, no "5 cm"


def test_a_said_number_is_printed_and_results_rest_on_it():
    s, _ = build(["Imagine a square of side four centimetres."], [SQ])
    assert s.get("s1").props["side"].source == "said" and s.get("s1").geom.dims[0][2] == "4 cm"
    assert [(d.label, d.text) for d in s.derived] == [("Area of the square", "16 cm²")]


def test_double_it_of_a_known_value_is_computed():
    c = Corpus.of(["The ball moves at 3 m/s.", "Now double it."])
    s, _ = build(["The ball moves at 3 m/s."], [{"op": "add", "id": "b1", "kind": "ball",
                                                   "props": {"speed": [3, "m/s"]}}])
    checked, _ = check(SceneOp(op="set", id="b1", props={"speed": [6, "m/s"]}), s, c)
    assert checked.props["speed"].source == "computed"


@pytest.mark.parametrize("op, why", [
    ({"op": "set", "id": "zz", "props": {}}, "no entity"),
    ({"op": "relate", "kind": "inscribed_in", "a": "s1", "b": "nope"}, "bad refs"),
    ({"op": "relate", "kind": "glued_to", "a": "s1", "b": "s1"}, "unknown relation"),
    ({"op": "add", "id": "x1", "kind": "dragon"}, "not drawn"),
    ({"op": "add", "id": "Bad-Id", "kind": "square"}, "bad id"),
    ({"op": "behave", "kind": "move", "target": "s1"}, "not a body"),
    ({"op": "label", "id": "s1", "text": "Pythagoras"}, "was not said"),
    ({"op": "explode", "id": "s1"}, "unknown op"),
    ({"op": "add", "id": "f1", "kind": "curve", "expr": "__import__('os')"}, "expr refused"),
])
def test_bad_ops_are_refused_with_a_reason(op, why):
    s, _ = build(["Imagine a square of side 4 cm."], [SQ])
    checked, reason = check(SceneOp(**op), s, Corpus.of(["Imagine a square of side 4 cm."]))
    assert checked is None and why in reason


def test_a_bad_unit_or_an_out_of_range_value_refuses_that_prop_only():
    s, refused = build(["A ball at 3 m/s at 400 degrees."], [
        {"op": "add", "id": "b1", "kind": "ball", "props": {"speed": [3, "kg"], "angle": [400, "deg"]}}])
    assert s.get("b1") is not None and s.get("b1").props == {}
    assert any("not a speed unit" in r for r in refused) and any("out of range" in r for r in refused)


def test_a_name_not_said_is_not_printed():
    s, refused = build(["Imagine a square."], [{**SQ, "name": "rhombus", "props": {}}])
    assert s.get("s1").name == "" and s.get("s1").label.source == "none"
    assert any("not said" in r for r in refused)


# ---- geometry vs exact values -------------------------------------------------------------------------------------
def gs(lines, ops):
    s, _ = build(lines, ops)
    return geometry.solve(s)[0], s


def test_a_circle_inscribed_in_a_square_and_its_diagonal():
    g, s = gs(["Imagine a square of side 4 cm, a circle inside it and its diagonal."], [
        SQ, {"op": "add", "id": "c1", "kind": "circle", "name": "circle"},
        {"op": "relate", "kind": "inscribed_in", "a": "c1", "b": "s1"},
        {"op": "add", "id": "d1", "kind": "segment", "name": "diagonal"},
        {"op": "relate", "kind": "diagonal_of", "a": "d1", "b": "s1"}])
    assert g["c1"].r == pytest.approx(2.0) and g["c1"].c == pytest.approx(g["s1"].centre())
    assert g["d1"].length() == pytest.approx(4 * math.sqrt(2))
    shown = {d.label: d.text for d in s.derived}
    assert shown["Area of the circle"] == "12.6 cm²" and shown["Radius of the circle"] == "2 cm"
    assert shown["Length of the diagonal"] == "5.66 cm"


@pytest.mark.parametrize("a, b, rel, check_", [
    ("square", {"kind": "circle", "props": {"radius": [2, "cm"]}}, "inscribed_in",
     lambda g: math.dist(g.pts[0], g.pts[1]) == pytest.approx(2 * math.sqrt(2))),
    ("circle", {"kind": "triangle", "props": {"side": [6, "cm"]}}, "around", lambda g: g.r == pytest.approx(6 / math.sqrt(3))),
    ("circle", {"kind": "triangle", "props": {"side": [6, "cm"]}}, "inscribed_in",
     lambda g: g.r == pytest.approx(6 / (2 * math.sqrt(3)))),
    ("circle", {"kind": "polygon", "props": {"sides": [6, ""], "side": [3, "cm"]}}, "inscribed_in",
     lambda g: g.r == pytest.approx(3 * math.sqrt(3) / 2)),
    ("square", {"kind": "circle", "props": {"radius": [3, "cm"]}}, "around",
     lambda g: math.dist(g.pts[0], g.pts[1]) == pytest.approx(6)),
    ("circle", {"kind": "rectangle", "props": {"width": [6, "cm"], "height": [8, "cm"]}}, "around",
     lambda g: g.r == pytest.approx(5)),
])
def test_constructions_match_exact_values(a, b, rel, check_):
    line = ["A shape with radius 2 cm, 3 cm, side 6 cm, width 6 cm, height 8 cm and 6 sides."]
    g, _ = gs(line, [{"op": "add", "id": "b1", **b}, {"op": "add", "id": "a1", "kind": a},
                     {"op": "relate", "kind": rel, "a": "a1", "b": "b1"}])
    assert check_(g["a1"]) and g["a1"].known


def test_a_construction_on_a_default_size_prints_nothing():
    s, _ = build(["Imagine a square with a circle inside it."], [
        {**SQ, "props": {}}, {"op": "add", "id": "c1", "kind": "circle", "name": "circle"},
        {"op": "relate", "kind": "inscribed_in", "a": "c1", "b": "s1"}])
    assert s.derived == []


def test_geometry_fits_the_stage():
    s, _ = build(["Imagine a square of side 4 cm."], [SQ])
    xs = [p[0] for p in s.get("s1").geom.pts]
    ys = [p[1] for p in s.get("s1").geom.pts]
    assert 0 < min(xs) and max(xs) < layout.W and 0 < min(ys) and max(ys) < layout.H


# ---- plot -------------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("bad", ["__import__('os')", "x.real", "open('f')", "lambda: 1", "[x]", "x if x else 1",
                                 "eval('1')", "y + 1", "sin(x, x)", "a" * 100])
def test_the_plot_parser_refuses_anything_outside_its_whitelist(bad):
    with pytest.raises(ValueError):
        plot.parse(bad)


def test_the_plot_parser_evaluates_and_prints():
    f = plot.evaluator("y = 2x^2 - 3")
    assert f(2) == pytest.approx(5) and plot.evaluator("log(x)")(-1) is None and plot.evaluator("1/x")(0) is None
    assert plot.pretty("x**2-3*x") == "y = x² − 3x"
    assert plot.evaluator("2sin(x)")(math.pi / 2) == pytest.approx(2)


def test_a_point_on_a_curve_gets_its_computed_coordinates():
    s, _ = build(["Consider y equals x squared minus 3, mark the point where x is 2."], [
        {"op": "add", "id": "f1", "kind": "curve", "name": "graph", "expr": "x^2-3"},
        {"op": "add", "id": "p1", "kind": "point", "props": {"x": [2, ""]}},
        {"op": "relate", "kind": "on", "a": "p1", "b": "f1"}])
    assert s.world == "plot" and s.get("p1").geom.note == "(2, 1)"
    assert s.get("f1").expr_shown == "y = x² − 3" and s.get("f1").geom.d.startswith("M")


def test_an_expression_with_an_unsaid_number_is_drawn_without_its_equation():
    s, _ = build(["Consider a parabola."], [{"op": "add", "id": "f1", "kind": "curve", "expr": "x^2-7"}])
    assert s.get("f1").expr_shown == "" and s.get("f1").geom.d


# ---- motion vs formulas ---------------------------------------------------------------------------------------------
def test_a_ball_that_speeds_up_follows_x_equals_v0_t_plus_half_a_t_squared():
    s, _ = build(["Imagine a ball moving at 3 m/s.", "Now it speeds up at 2 m/s squared."], [
        {"op": "add", "id": "b1", "kind": "ball", "name": "ball", "props": {"speed": [3, "m/s"]}},
        {"op": "behave", "kind": "move", "target": "b1"},
        {"op": "set", "id": "b1", "props": {"acceleration": [2, "m/s^2"]}}])
    pts = s.frames.tracks[0].pts
    at2 = next(p for p in pts if p[0] == pytest.approx(2.0))  # a Step (0.25 s) lands on a sample
    assert at2[4] == pytest.approx(7.0) and at2[5] == pytest.approx(10.0)
    assert [d.live for d in s.derived] == ["v", "x"]


def test_slowing_down_stops_and_stays():
    b = motion.path(_ball(5, -2), _beh(), 81)
    end = b.pts[-1]
    assert end[3] == 0.0 and end[1] == pytest.approx(25 / 4)  # v0² / 2|a|


def _ball(v, a):
    from copilot.scene.spec import Entity, Q
    return Entity(id="b1", kind="ball", props={"speed": Q(value=v, unit="m/s", source="said"),
                                               "acceleration": Q(value=a, unit="m/s^2", source="said")})


def _beh(kind="move", **params):
    from copilot.scene.spec import Behavior
    return Behavior(kind=kind, target="b1", params=params)


def test_a_launch_lands_at_the_range_formula():
    from copilot.scene.spec import Entity, Q
    e = Entity(id="b1", kind="ball", props={"speed": Q(value=20, unit="m/s", source="said"),
                                             "angle": Q(value=30, unit="deg", source="said")})
    p = motion.path(e, _beh("launch"), 120)
    assert p.T == pytest.approx(2 * 20 * 0.5 / motion.G_EARTH)
    assert p.pts[-1][1] == pytest.approx(20 ** 2 * math.sin(math.radians(60)) / motion.G_EARTH) and p.known


def test_a_speed_not_said_moves_the_body_but_prints_nothing():
    s, _ = build(["Imagine a ball rolling."], [{"op": "add", "id": "b1", "kind": "ball", "name": "ball"},
                                                {"op": "behave", "kind": "move", "target": "b1"}])
    assert s.frames.tracks[0].pts[-1][1] > s.frames.tracks[0].pts[0][1] and s.derived == []


def test_frames_stay_within_the_point_budget():
    lines = ["Six balls at 1, 2, 3, 4, 5 and 6 m/s."]
    s, _ = build(lines, [x for i in range(1, 7) for x in (
        {"op": "add", "id": f"b{i}", "kind": "ball", "props": {"speed": [i, "m/s"]}},
        {"op": "behave", "kind": "move", "target": f"b{i}"})])
    assert sum(len(t.pts) for t in s.frames.tracks) <= 400


# ---- compiler: JSONL stream, context ----------------------------------------------------------------------------------
def test_jsonl_objects_come_out_as_soon_as_complete():
    p = JsonlStream()
    text = '```jsonl\n{"op":"add","id":"s1","kind":"square","props":{"side":[4,"cm"]}}\n{"op":"add",\n"id":"c1"}{"op":"remove","id":"c1"}\nnot json {oops}\n{"op":"focus","ids":["s1"]}\n```'
    out = []
    for i in range(0, len(text), 7):
        out += p.feed(text[i:i + 7])
    out += p.finish()
    assert [o["op"] for o in out] == ["add", "add", "remove", "focus"]
    assert out[0]["props"]["side"] == [4, "cm"]


def test_a_retried_stream_does_not_repeat_ops():
    p = JsonlStream()
    a = p.feed('{"op":"add","id":"s1","kind":"square"}\n')
    p.reset()
    b = p.feed('{"op":"add","id":"s1","kind":"square"}\n{"op":"remove","id":"s1"}\n')
    assert len(a) == 1 and [o["op"] for o in b] == ["remove"]


def test_the_context_is_compact_and_bounded():
    s, _ = build(["Imagine a square of side 4 cm."], [SQ])
    assert context(s) == 's1 square "square" side=4 cm'
    m = messages([f"line {i}" for i in range(10)], s, "Geometry")
    assert "line 9" in m[1]["content"] and "line 5" not in m[1]["content"]


# ---- detector ---------------------------------------------------------------------------------------------------------
@pytest.mark.parametrize("line, world", [
    ("Imagine a square of side 4 cm.", "geometry"),
    ("Now draw its diagonal.", "geometry"),
    ("Consider the graph of y equals x squared.", "plot"),
    ("Let's plot y equals sin x.", "plot"),
    ("Imagine a ball moving at 3 metres per second.", "motion"),
    ("Think of a car on a straight road.", "motion"),
    ("Imagine you are in a library.", None),
    ("Look at the slide again.", None),
    ("A square has four equal sides.", None),
])
def test_a_cue_needs_a_drawable_noun(line, world):
    assert cue(line) == world


def test_an_edit_needs_a_reason_to_call():
    assert wants_edit("Now it speeds up.", []) and wants_edit("The square is red.", ["square"])
    assert not wants_edit("This is very important for the exam.", ["square"])


async def test_the_detector_publishes_cues_and_edits_while_a_scene_is_open():
    bus = EventBus()
    got = []

    async def keep(ev):
        got.append(ev.strength)
    bus.subscribe("t", keep, [RepresentationIntent])
    SceneDetector(bus).attach()
    talk = Lines(bus)
    await talk.say("Imagine a square.")
    await send(bus, SimulationModeChanged(on=True, template="scene"))
    await talk.say("Now a circle inside it.")
    await talk.say("Now imagine a ball moving.")  # another world: a new scene
    await send(bus, SimulationModeChanged(on=False, template="scene"))
    await talk.say("A square has four sides.")    # nothing open, no cue
    assert got == ["cue", "edit", "cue"]


# ---- provider streaming -----------------------------------------------------------------------------------------------
async def test_the_provider_streams_sse_and_records_usage():
    chunks = ['{"op":"add",', '"id":"s1","kind":"square"}\n', '{"op":"focus","ids":["s1"]}']
    body = "".join(f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n" for c in chunks)
    body += f"data: {json.dumps({'choices': [], 'x_groq': {'usage': {'prompt_tokens': 900, 'completion_tokens': 60}}})}\n\n"
    body += "data: [DONE]\n\n"
    sent = {}

    def handler(request):
        sent.update(json.loads(request.content))
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        prov = OpenAICompatProvider(ProviderConfig(name="g", base_url="http://x/v1", model="m"), "k", client)
        pieces = []
        r = await prov.complete([{"role": "user", "content": "hi"}], max_tokens=100, timeout=5, on_text=pieces.append)
    assert sent["stream"] is True and "response_format" not in sent
    assert pieces == chunks and r.text == "".join(chunks)
    assert (r.prompt_tokens, r.completion_tokens) == (900, 60)


async def stream_of(*chunks, finish="stop"):
    body = "".join(f"data: {json.dumps({'choices': [{'delta': {'content': c}}]})}\n\n" for c in chunks)
    body += f"data: {json.dumps({'choices': [{'delta': {}, 'finish_reason': finish}]})}\n\ndata: [DONE]\n\n"
    async with httpx.AsyncClient(transport=httpx.MockTransport(
            lambda r: httpx.Response(200, text=body, headers={"content-type": "text/event-stream"}))) as client:
        prov = OpenAICompatProvider(ProviderConfig(name="g", base_url="http://x/v1", model="m"), "k", client)
        return await prov.complete([{"role": "user", "content": "hi"}], max_tokens=100, timeout=5, on_text=lambda _: None)


async def test_an_empty_streamed_answer_means_nothing_to_change_not_a_failure():
    """Live run 2026-10-22: "the diagonal is longer than the side by root two" -> no ops; an empty stream was an
    error and the router retried it on every key."""
    from copilot.llm.providers import InvalidOutput
    assert (await stream_of()).text == ""
    with pytest.raises(InvalidOutput):
        await stream_of(finish="length")


# ---- the controller path: a recorded answer -> slide patches (0 tokens) ------------------------------------------------
ANSWERS = {
    "Imagine a square of side 4 cm.": json.dumps(SQ),
    "Now a circle inside it.": '{"op":"add","id":"c1","kind":"circle","name":"circle"}\n'
                               '{"op":"relate","kind":"inscribed_in","a":"c1","b":"s1"}\n'
                               '{"op":"label","id":"c1","text":"Excalibur"}',
    "Imagine a ball moving at 3 metres per second.":
        '{"op":"add","id":"b1","kind":"ball","name":"ball","props":{"speed":[3,"m/s"]}}\n'
        '{"op":"behave","kind":"move","target":"b1"}',
    "Now it speeds up at 2 metres per second squared.": '{"op":"set","id":"b1","props":{"acceleration":[2,"m/s^2"]}}',
}


async def scene_lecture(**settings):
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False, **settings)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    replay = ReplayCompiler(ANSWERS)
    eng._scenes.compiler = replay
    await send(bus, ready("Geometry", "Geometry", [act("explanation", points=["Shapes have area"])],
                          relation="new_topic"))
    return bus, deck, eng, clock, Lines(bus), replay


async def said(bus, eng, talk, line):
    await talk.say(line)
    o = eng._scenes.open
    if o is not None and o.task is not None:
        await o.task
    await bus.drain()


def scene_on(deck):
    return next((b.scene for b in deck.live.blocks if b.type == "scene"), None)


async def test_a_cue_opens_a_scene_and_an_edit_patches_it():
    bus, deck, eng, clock, talk, replay = await scene_lecture()
    await said(bus, eng, talk, "Imagine a square of side 4 cm.")
    s = scene_on(deck)
    assert s is not None and deck.sim_mode == deck.live.id and [e.id for e in s.entities] == ["s1"]
    slide_id = deck.live.id
    await said(bus, eng, talk, "Now a circle inside it.")
    s = scene_on(deck)
    assert deck.live.id == slide_id and [e.id for e in s.entities] == ["s1", "c1"]
    assert deck.live.title == "Square and circle"
    assert eng._sims.mode.names[-1] == "Square and circle"  # the recap's title
    assert s.get("c1").label.text == "circle"  # the unsaid label op was refused
    assert replay.calls == [["Imagine a square of side 4 cm."], ["Now a circle inside it."]]
    assert eng._scenes.stats.rejected == 1


async def test_a_patch_never_restarts_the_clock_and_the_end_cue_resumes_slides():
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    await said(bus, eng, talk, "Imagine a ball moving at 3 metres per second.")
    rev = scene_on(deck).playback.rev
    await said(bus, eng, talk, "Now it speeds up at 2 metres per second squared.")
    s = scene_on(deck)
    assert s.playback.rev == rev and s.get("b1").props["acceleration"].source == "said"
    await send(bus, CommandReceived(command=Command(kind="sim_pause", args={"slide_id": deck.live.id})))
    assert scene_on(deck).playback.rev == rev + 1 and scene_on(deck).playback.state == "paused"
    await said(bus, eng, talk, "Okay, let's get back to the slides.")
    assert deck.sim_mode is None


async def test_without_an_llm_there_is_no_scene():
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    eng._scenes.compiler = None
    await said(bus, eng, talk, "Imagine a square of side 4 cm.")
    assert scene_on(deck) is None and deck.sim_mode is None


async def test_setting_off_ignores_and_suggest_offers_a_chip():
    bus, deck, eng, clock, talk, _ = await scene_lecture(simulations="off")
    await said(bus, eng, talk, "Imagine a square of side 4 cm.")
    assert scene_on(deck) is None
    bus, deck, eng, clock, talk, _ = await scene_lecture(simulations="suggest")
    await said(bus, eng, talk, "Imagine a square of side 4 cm.")
    assert scene_on(deck) is None and eng._scenes.suggestion is not None
    await send(bus, CommandReceived(command=Command(kind="sim_accept", args={"id": eng._scenes.suggestion.id})))
    if eng._scenes.open is not None and eng._scenes.open.task is not None:
        await eng._scenes.open.task
    await bus.drain()
    assert [e.id for e in scene_on(deck).entities] == ["s1"]


async def test_a_template_cue_no_longer_starts_a_template_by_itself():
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    eng._scenes.compiler = None  # no scene either: the line shows nothing new
    await said(bus, eng, talk, "Consider a block of mass 5 kg resting on a rough floor.")
    assert not any(b.type == "simulation" for b in deck.live.blocks) and deck.sim_mode is None


# ---- review findings (2026-10-22) ---------------------------------------------------------------------------------
async def test_a_restarted_stream_resets_the_parser_and_keeps_applied_ops():
    from copilot.scene.compiler import SceneCompiler

    class Router:  # the first attempt breaks off mid-object, the retry streams the whole answer
        async def complete(self, messages, *, on_text, **kw):
            on_text(None)
            on_text('{"op":"add","id":"s1","kind":"square"}\n{"op":"add","id":"c1","ki')
            on_text(None)
            on_text('{"op":"add","id":"s1","kind":"square"}\n{"op":"add","id":"c1","kind":"circle"}\n')
            from copilot.llm.providers import LLMResponse
            from copilot.llm.router import RouterResult
            return RouterResult(LLMResponse(text="", prompt_tokens=1, completion_tokens=1), "r")
    got = []

    async def on_op(op):
        got.append(op.id)
    await SceneCompiler(Router()).compile(["x"], None, "", on_op)
    assert got == ["s1", "c1"]


def test_a_converted_value_is_computed_only_in_its_base_unit():
    c = Corpus.of(["The car moves at 36 km/h."])
    s = SceneSpec()
    ok, _ = check(SceneOp(op="add", id="b1", kind="car", props={"speed": [10, "m/s"]}), s, c)
    bad, _ = check(SceneOp(op="add", id="b1", kind="car", props={"speed": [10, "km/h"]}), s, c)
    assert ok.props["speed"].source == "computed" and bad.props["speed"].source == "default"


def test_a_number_said_with_another_unit_family_is_not_said():
    c = Corpus.of(["The circle has a radius of 5 metres per second."])
    checked, _ = check(SceneOp(op="add", id="s1", kind="square", props={"side": [5, "cm"]}), SceneSpec(), c)
    assert checked.props["side"].source == "default"


def test_a_length_without_a_unit_is_in_the_scenes_unit():
    s, _ = build(["Imagine a square of side 4 cm and a circle of radius 2 beside it."], [
        SQ, {"op": "add", "id": "c1", "kind": "circle", "name": "circle", "props": {"radius": [2, ""]}}])
    assert {d.label: d.text for d in s.derived}["Area of the circle"] == "12.6 cm²"


def test_a_point_on_a_curve_with_an_unsaid_number_prints_no_coordinates():
    s, _ = build(["Consider a parabola and mark the point where x is 2."], [
        {"op": "add", "id": "f1", "kind": "curve", "expr": "x^2-3"},
        {"op": "add", "id": "p1", "kind": "point", "props": {"x": [2, ""]}},
        {"op": "relate", "kind": "on", "a": "p1", "b": "f1"}])
    assert s.get("p1").geom is not None and s.get("p1").geom.note == ""


def test_a_longer_cycle_of_relations_is_refused():
    lines = ["Three squares."]
    s, refused = build(lines, [{"op": "add", "id": i, "kind": "square"} for i in ("a1", "b1", "c1")] + [
        {"op": "relate", "kind": "inside", "a": "a1", "b": "b1"},
        {"op": "relate", "kind": "inside", "a": "b1", "b": "c1"},
        {"op": "relate", "kind": "inside", "a": "c1", "b": "a1"}])
    assert any("cycle" in r for r in refused) and all(e.geom is not None for e in s.entities)


def test_a_one_letter_label_must_be_said_as_one():
    s, _ = build(["Imagine a square."], [{**SQ, "props": {}}])
    no, _ = check(SceneOp(op="label", id="s1", text="A"), s, Corpus.of(["Imagine a square."]))
    yes, _ = check(SceneOp(op="label", id="s1", text="A"), s, Corpus.of(["Call the corner point A."]))
    assert no is None and yes is not None


def test_a_launch_at_zero_speed_is_not_drawn_at_the_default():
    from copilot.scene.spec import Entity, Q
    e = Entity(id="b1", kind="ball", props={"speed": Q(value=0, unit="m/s", source="said"),
                                             "angle": Q(value=30, unit="deg", source="said")})
    assert motion.path(e, _beh("launch"), 50).pts[-1][1] == 0.0


async def test_a_cue_that_draws_nothing_leaves_no_empty_stage():
    bus, deck, eng, clock, talk, _ = await scene_lecture()
    await said(bus, eng, talk, "Imagine a ball and a car racing in a cartoon.")  # no recorded ops
    assert scene_on(deck) is None and deck.sim_mode is None and eng._scenes.open is None


@pytest.mark.parametrize("line", ["Imagine the human body as a machine.", "Look at the function of the kidney.",
                                  "Consider the objects in this room."])
def test_nouns_of_other_subjects_are_not_scene_cues(line):
    assert cue(line) is None
