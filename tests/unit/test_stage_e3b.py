"""F-017 E3b fixes, one test per cause (test34): continuity, repairs, the draft merge, pictures, the timeline for drive /
fly / a throw with no numbers, unsure ghosts, the empty stage, one recap for a run of stages, the STT outro cut, an
invalid key, a blank topic (0 tokens)."""
import httpx

from copilot.presentation.stage import _title_of, same_scene
from copilot.stage import fastpath, lookup, timeline
from copilot.stage.director_llm import ReplayDirector
from copilot.stage.log import EventLog
from copilot.stage.validate import check_delta
from copilot.stt.engine import guard, strip_outros
from copilot.understanding.interpreter import parse_interpretation
from tests.unit.test_llm_router import deadline, make_router
from tests.unit.test_stage_live import cmd, ents, stage_lecture, stage_on

MAN = {"op": "add", "id": "man", "kind": "agent", "w": "man"}


def graph(*ops, line="l1", text="x"):
    log = EventLog()
    log.say(line, text)
    log.delta(list(ops), line, "llm")
    return log, log.fold()


# ---- A: continuity -------------------------------------------------------------------------------------------------
def test_same_scene_by_pronoun_definite_repeat_and_verb_object_never_by_a_new_imagine():
    _, g = graph(MAN, {"op": "add", "id": "box", "kind": "prop", "w": "box"},
                 {"op": "act", "id": "push1", "verb": "push", "agent": "man", "obj": "box"})
    assert same_scene(fastpath.draft("Imagine a dog run past him.", g), g)              # him = the man
    assert same_scene(fastpath.draft("Imagine the box on ice.", g), g)                  # the box
    assert same_scene(fastpath.draft("Imagine a man pushing a box.", g), g)             # a repeat
    assert same_scene(fastpath.draft("Imagine a girl pushing a box.", g), g)            # the same push
    assert not same_scene(fastpath.draft("Imagine an elephant sitting on a sofa.", g), g)
    k = fastpath.draft("Imagine a kettle sits on the stove and steam comes out of it.", g)
    assert not same_scene(k, g) and not k.pron                                           # "it" = the kettle
    assert fastpath.draft("Imagine a DC circuit.", g).prefetch == ["circuit"]
    assert fastpath.draft("Imagine a box placed on an inclined plane.").prefetch == []   # a catalog name


def test_you_is_a_person_only_as_the_subject():
    assert any(o.get("w") == "you" for o in fastpath.draft("Imagine you are pushing a box.").ops)
    for t in ("Thank you.", "I'll see you in the lab.", "I will show you how to use it."):
        assert not any(o.get("w") == "you" for o in fastpath.draft(t).ops), t


def test_titles_name_the_main_actor_and_a_late_actor_does_not_take_over():
    _, g = graph(MAN, {"op": "add", "id": "box", "kind": "prop", "w": "box"},
                 {"op": "act", "id": "push1", "verb": "push", "agent": "man", "obj": "box"},
                 {"op": "end", "id": "push1"}, {"op": "add", "id": "dog", "kind": "animal", "w": "dog"},
                 {"op": "act", "id": "run1", "verb": "run", "agent": "dog"})
    assert _title_of(g) == "Man pushing a box"
    _, g = graph({"op": "add", "id": "box", "kind": "prop", "w": "box"},
                 {"op": "add", "id": "ramp", "kind": "prop", "w": "ramp"}, {"op": "relate", "a": "box", "kind": "on", "b": "ramp"})
    assert _title_of(g) == "Box on a ramp"


# ---- B / C11: repairs ----------------------------------------------------------------------------------------------
def test_repairs_ids_kinds_seat_sides_sitting_things_and_restated_actions():
    d = check_delta([{"op": "add", "id": "see-saw", "kind": "prop", "w": "see-saw"},
                     {"op": "add", "id": "you", "kind": "agent", "w": "you"},
                     {"op": "relate", "a": "you", "kind": "sitting_on", "b": "left"},
                     {"op": "add", "id": "box", "kind": "agent", "w": "box"},
                     {"op": "add", "id": "bird", "kind": "prop", "w": "flying bird"},
                     {"op": "add", "id": "kettle", "kind": "prop", "w": "kettle"},
                     {"op": "add", "id": "stove", "kind": "prop", "w": "stove"},
                     {"op": "relate", "a": "kettle", "kind": "sitting_on", "b": "stove"}], EventLog().fold(), ["x"])
    assert not d.rejected, [r.reason for r in d.rejected]
    got = {op.id if op.op == "add" else (op.a, op.kind, op.b): op for op, _ in d.ok}
    assert "see_saw" in got and got["box"].kind == "prop" and got["bird"].kind == "animal"
    assert ("you", "sitting_on", "see_saw") in got and ("kettle", "on", "stove") in got
    log, g = graph(MAN, {"op": "act", "id": "walk1", "verb": "walk", "agent": "man"})
    log.say("l2", "He walks.")
    d = log.delta([{"op": "act", "id": "walk1", "verb": "walk", "agent": "man"},
                   {"op": "add", "id": "dog", "kind": "agent", "w": "dog"},
                   {"op": "act", "id": "c1", "verb": "chase", "agent": "dog", "obj": "man"}], "l2")
    assert not d.rejected and [op.verb for op, _ in d.ok if op.op == "act"] == ["run"]   # restated walk1: no op
    assert log.fold().ents["dog"].kind == "animal"


def test_a_given_filed_under_an_action_goes_to_its_law():
    log, g = graph(MAN, {"op": "add", "id": "rain", "kind": "prop", "w": "rain"},
                   {"op": "act", "id": "walk1", "verb": "walk", "agent": "man"},
                   {"op": "act", "id": "fall1", "verb": "fall", "agent": "rain", "dir": "down"})
    log.say("l2", "He walks at 5 mps and the rain falls at 2 mps.")
    d = log.delta([{"op": "given", "law": "walk1", "sym": "v", "v": 5, "u": "m/s", "q": "at 5 mps"},
                   {"op": "given", "law": "fall1", "sym": "v", "v": 2, "u": "m/s", "q": "falls at 2 mps"}], "l2")
    assert not d.rejected, [r.reason for r in d.rejected]
    law = next(iter(log.fold().laws.values()))
    assert law.name == "relative_motion" and {s: x.v for s, x in law.givens.items()} == {"vb": 5, "va": 2}
    log2, _ = graph(MAN, {"op": "act", "id": "walk1", "verb": "walk", "agent": "man"})
    log2.say("l2", "He walks at 5 mps.")
    log2.delta([{"op": "given", "law": "walk1", "sym": "v", "v": 5, "u": "m/s", "q": "at 5 mps"}], "l2")
    assert [l.name for l in log2.fold().laws.values()] == ["uniform_motion"]


def test_put_down_after_standing_still_and_carry_holds():
    log, g = graph({"op": "add", "id": "woman", "kind": "agent", "w": "woman"},
                   {"op": "add", "id": "bucket", "kind": "prop", "w": "bucket"},
                   {"op": "act", "id": "carry1", "verb": "carry", "agent": "woman", "obj": "bucket"})
    assert g.holder("bucket") == "woman"
    log.say("l2", "She stands still.")
    log.delta([{"op": "act", "id": "stand1", "verb": "stand", "agent": "woman"}], "l2")
    log.say("l3", "She puts it down.")
    d = log.delta([{"op": "act", "id": "put1", "verb": "put_down", "agent": "woman", "obj": "bucket"}], "l3")
    assert not d.rejected


# ---- C10: the delta merges with the draft ---------------------------------------------------------------------------
def test_the_llm_delta_keeps_drafted_things_it_does_not_name():
    log = EventLog()
    log.say("l1", "Imagine you are driving a car.")
    log.delta(fastpath.draft("Imagine you are driving a car.").ops, "l1", "fast")
    log.delta([MAN, {"op": "act", "id": "drive1", "verb": "drive", "agent": "man"}], "l1", "llm")
    g = log.fold()
    assert "car" in g.ents and "you" not in g.ents                          # the model's person replaces "you"
    assert next(a for a in g.actions.values() if a.verb == "drive").obj == "car"   # drive -> the one vehicle
    p = timeline.build(g)
    sock = next(t for t in p["tracks"] if t.get("kind") == "socket" and t["id"] == "man")
    assert sock["parent"] == "car" and sock["socket"] == "seat"              # the driver in the car
    log.say("l2", "Imagine. in a boat.")
    log.delta(fastpath.draft("Imagine. in a boat.", log.fold()).ops, "l2", "fast")
    log.delta([], "l2", "llm")                                               # the model answered nothing
    assert "boat" in log.fold().ents


# ---- B: pictures ----------------------------------------------------------------------------------------------------
def test_pictures_never_a_person_for_a_thing_icons_by_head_noun_sky_is_outdoors():
    lad = lookup.Ladder(fetch=False, log_misses=False)
    assert not lad.pick("agent", "rocket", None, [], set()).draw.startswith("cast:")
    assert lad.pick("agent", "box", None, [], set()).draw == "crate"

    class Emoji:
        def match(self, w):
            return {"bird": "flying disc", "stove": "cooking", "laptop": "laptop"}.get(w, "")

    lad.emoji = Emoji()
    assert lad._icon_name("flying bird") == "" and lad._icon_name("stove") == ""
    assert lad._icon_name("old laptop") == "laptop"
    assert lad.pick("place", "sky", None, [], set()).draw == "backdrop:outdoor"


# ---- C12 / C14: the timeline ----------------------------------------------------------------------------------------
def test_a_bird_flies_in_the_air_and_a_throw_with_no_numbers_releases_the_ball():
    _, g = graph({"op": "add", "id": "bird", "kind": "animal", "w": "bird"},
                 {"op": "act", "id": "fly1", "verb": "fly", "agent": "bird"})
    p = timeline.build(g)
    path = next(t for t in p["tracks"] if t["id"] == "bird" and t["kind"] == "path")
    assert all(s[2] > 1.0 for s in path["samples"])
    _, g = graph({"op": "add", "id": "girl", "kind": "agent", "w": "girl"},
                 {"op": "add", "id": "ball", "kind": "prop", "w": "ball"},
                 {"op": "act", "id": "throw1", "verb": "throw", "agent": "girl", "obj": "ball"})
    p = timeline.build(g)
    ball = next(t for t in p["tracks"] if t["id"] == "ball" and t["kind"] == "path")
    assert max(s[2] for s in ball["samples"]) > 1.5                          # it flies, it does not lie on the ground
    assert not any(o.get("kind") == "card" for o in p["overlays"])          # no numbers were said


# ---- D16, A4: unsure ghosts time out, an empty stage closes ------------------------------------------------------------
async def test_unsure_ghosts_clear_after_a_while_and_an_empty_stage_closes():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    eng._stage.director = ReplayDirector({})
    await cmd(bus, "imagine_mode", on=True)
    o = eng._stage.open
    await talk.say("A man pushes a crate.")
    await bus.drain()
    o.unsure["crate"], o.unsure_at["crate"] = [], eng.now()
    await eng._stage._publish(o)
    assert ents(deck)["crate"].get("ghost")
    eng.now = lambda: o.unsure_at["crate"] + 31
    await eng._stage._publish(o)
    assert stage_on(deck).unsure == []
    await cmd(bus, "imagine_mode", on=False)
    await eng._stage.tick()
    await talk.say("Imagine a sofa in a strange room.")      # a cue: a stage with only an unknown noun
    await bus.drain()
    o = eng._stage.open
    if o is not None:
        o.patch = None
        t0 = o.opened
        eng.now = lambda: t0 + 21
        await eng._stage.tick()
        assert eng._stage.open is None and deck.sim_mode is None


# ---- A1: one recap for a run of stages ------------------------------------------------------------------------------
async def test_a_run_of_stages_makes_one_recap_and_a_one_line_stage_none():
    bus, deck, eng, talk, replay, lines = await stage_lecture()
    sims = eng._sims
    await eng._stage.start(origin="cue", title="Ball")
    sims.mode.lines = 1
    sims.mode.collected = ["piece-a"]
    await eng._stage.start(origin="cue", title="Box")               # one line: its piece is not kept
    assert sims.mode.collected == [] and sims.mode.names[:1] == ["Ball"]
    sims.mode.lines = 3
    sims.mode.collected = ["piece-b"]
    await eng._stage.start(origin="cue", title="Elephant")
    assert sims.mode.collected == ["piece-b"] and sims.mode.carried == 1
    recaps = [s for s in deck.slides if s.title.startswith("Recap")]
    assert recaps == []                                              # no recap between the stages


# ---- E20, E22, E23 ---------------------------------------------------------------------------------------------------
def test_whisper_outros_are_cut_and_real_lines_kept():
    assert strip_outros("He pushes with 50N. Thank you for your attention.") == "He pushes with 50N."
    assert strip_outros("Imagine a girl throws a ball up into the air. you") == "Imagine a girl throws a ball up into the air."
    assert strip_outros("Imagine an elephant sitting on sofa. for watching. I'll see you next time.") == \
        "Imagine an elephant sitting on sofa."
    assert guard(strip_outros("This is the last part of the video."), 2.0, -0.2, 0.1, 1.0) == "empty"
    for keep in ("Thank you for helping me, said the girl.", "I will see you in the lab.", "Hello."):
        assert strip_outros(keep) == keep


async def test_an_invalid_key_is_left_out_for_the_session():
    calls = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.test":
            return httpx.Response(401, text='{"error":{"code":"invalid_api_key"}}')
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}],
                                         "usage": {"prompt_tokens": 1, "completion_tokens": 1}})

    router, client = make_router(handler)
    for _ in range(3):
        await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert calls.count("a.test") == 1 and router.entries[0].dead


def test_a_blank_topic_takes_the_lecture_topic():
    it = parse_interpretation('{"topic": "", "relation": "same_concept", "acts": []}', "Projectile Motion")
    assert it.topic == "Projectile Motion"


# ---- review findings ------------------------------------------------------------------------------------------------
def test_review_outros_keep_real_sentences_and_a_number_line():
    for keep in ("A telescope is used for watching stars.", "The subscriber line is busy.", "Who pushes? You!"):
        assert strip_outros(keep) == keep
    assert guard("9.8.", 1.0, -0.2, 0.1, 1.0) is None


def test_review_continuity_attributes_and_a_dummy_it():
    _, g = graph({"op": "add", "id": "box", "kind": "prop", "w": "box"})
    assert same_scene(fastpath.draft("Now imagine the very heavy box hits a wall.", g), g)
    d = fastpath.draft("Imagine it is raining and a girl walks in the park.", g)
    assert not d.pron and not same_scene(d, g)


def test_review_a_malformed_op_is_refused_not_a_crash_and_put_down_needs_the_holder():
    log, _ = graph(MAN, {"op": "add", "id": "girl", "kind": "agent", "w": "girl"},
                   {"op": "add", "id": "box", "kind": "prop", "w": "box"},
                   {"op": "act", "id": "c1", "verb": "carry", "agent": "man", "obj": "box"},
                   {"op": "act", "id": "c2", "verb": "carry", "agent": "girl", "obj": "box"})
    log.say("l2", "x")
    d = log.delta([{"op": "add", "id": ["cup"], "kind": "prop", "w": "cup"},
                   {"op": "act", "id": "p1", "verb": "put_down", "agent": "man", "obj": "box"}], "l2")
    assert len(d.rejected) == 2 and not d.ok


def test_review_riding_a_horse_is_not_driving_it():
    _, g = graph({"op": "add", "id": "girl", "kind": "agent", "w": "girl"},
                 {"op": "add", "id": "horse", "kind": "animal", "w": "horse"},
                 {"op": "act", "id": "r1", "verb": "drive", "agent": "girl", "obj": "horse"})
    p = timeline.build(g)
    assert not any(t.get("kind") == "socket" and t.get("parent") == "horse" for t in p["tracks"])
