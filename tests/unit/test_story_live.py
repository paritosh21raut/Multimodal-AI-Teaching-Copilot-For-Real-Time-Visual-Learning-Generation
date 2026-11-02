"""V3 P1c live story animation wiring (docs/v3/P1c-live-wiring.md): story line -> scene call -> world -> compiler ->
the shot on the story slide. Replay answers (0 tokens)."""
from __future__ import annotations

import json

from copilot.story import world as W
from copilot.story.live import StoryAnim
from copilot.story.scene_llm import ReplaySceneReader
from tests.unit.test_story import story_lecture, story_on

CUE = "Let me tell you the story of Ravi."
PICK = "Ravi picked up a stone and walked to the tree."
SAID = "Ravi said to Meena, I am tired."


def _ans(new=(), events=(), relations=(), end=()) -> str:
    return json.dumps({"new": list(new), "events": list(events), "relations": list(relations), "end": list(end)})


def _person(i, name, g=""):
    return {"id": i, "kind": "person", "name": name, "noun": name, "known": "", "gender": g, "posture": "stand"}


def _thing(i, kind, name, noun):
    return {"id": i, "kind": kind, "name": name, "noun": noun, "known": "", "gender": "", "posture": "stand"}


def _ev(op, actor, target="", obj="", value="", verb=""):
    return {"op": op, "actor": actor, "target": target, "obj": obj, "value": value, "verb": verb}


ANSWERS = {
    CUE: _ans(new=[_person("e1", "Ravi")]),
    PICK: _ans(new=[_thing("e2", "prop", "a stone", "stone"), _thing("e3", "prop", "the tree", "tree")],
               events=[_ev("attach", "e1", "e2", value="hold", verb="picked"), _ev("move_to", "e1", "e3", verb="walked")],
               relations=[{"a": "e1", "rel": "hold", "b": "e2"}, {"a": "e1", "rel": "next_to", "b": "e3"}]),
    SAID: _ans(new=[_person("e4", "Meena")], events=[_ev("speak", "e1", "e4", value="I am tired", verb="said")]),
}


async def anim_lecture(answers=None):
    bus, deck, eng, clock, talk, asked = await story_lecture()
    reader = ReplaySceneReader(dict(ANSWERS if answers is None else answers))
    eng._story.anim = reader
    return bus, deck, eng, talk, asked, reader


async def say(eng, talk, line):
    await talk.say(line)
    await eng._story.settle()


async def test_each_story_line_becomes_a_numbered_shot_in_said_order():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    s = story_on(deck)
    assert s is not None and s.anim and s.shot is not None and s.shot["n"] == 1
    await say(eng, talk, PICK)
    s = story_on(deck)
    assert s.shot["n"] == 2 and s.shot["line"] == PICK
    assert [e["op"] for e in s.shot["events"]][:1] and {e["id"] for e in s.shot["entities"]} >= {"e1", "e2"}
    await say(eng, talk, SAID)
    assert story_on(deck).shot["n"] == 3 and any(e["op"] == "speak" for e in story_on(deck).shot["events"])
    assert [m[1]["content"].rsplit("The line: ", 1)[1] for m in reader.calls] == [CUE, PICK, SAID]
    st = eng._story.stats
    assert st.anim_lines == 3 and st.anim_shots == 3 and st.anim_refused == 0 and len(st.anim_secs) == 3


async def test_a_refused_line_keeps_the_last_shot_and_is_shown_unread():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    await say(eng, talk, "Ravi danced with the moon.")      # no recorded answer: no JSON -> refused
    s = story_on(deck)
    assert s.shot["n"] == 1 and s.unread == "Ravi danced with the moon."
    assert eng._story.stats.anim_refused == 1
    await say(eng, talk, PICK)                                # the next line still animates (rev unchanged)
    s = story_on(deck)
    assert s.shot["n"] == 2 and s.unread == ""


async def test_a_repeat_and_class_talk_make_no_call_and_no_picture_search():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    await say(eng, talk, PICK)
    await say(eng, talk, PICK)                                # the same line again
    await say(eng, talk, "Okay class, look at the board.")    # class talk
    assert len(reader.calls) == 2 and story_on(deck).shot["n"] == 2
    assert not asked                                          # the canvas draws the story: no image searches


async def test_a_speaker_alone_joins_the_next_line_for_one_call():
    words = "I am tired."
    joined = "Ravi said to Meena, " + words
    bus, deck, eng, talk, asked, reader = await anim_lecture({**ANSWERS, joined: ANSWERS[SAID]})
    await say(eng, talk, CUE)
    await say(eng, talk, "Ravi said to Meena,")
    assert len(reader.calls) == 1
    await say(eng, talk, words)
    assert len(reader.calls) == 2 and reader.calls[-1][1]["content"].endswith(joined)


async def test_the_story_end_makes_the_shot_still():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    slide = deck.live.id
    await say(eng, talk, PICK)
    await talk.say("And that's the end of the story.")
    await eng._story.tick()
    b = next(x for x in eng._spec(slide).blocks if x.type == "story")
    assert b.still and b.story.shot["n"] == 2


async def test_a_line_that_changes_nothing_keeps_the_shot_playing():
    line = "Ravi was there."
    bus, deck, eng, talk, asked, reader = await anim_lecture({**ANSWERS, line: _ans()})
    await say(eng, talk, CUE)
    await say(eng, talk, PICK)
    await say(eng, talk, line)
    s = story_on(deck)
    assert len(reader.calls) == 3 and s.shot["n"] == 2 and s.unread == ""


async def test_gender_comes_from_the_cast_only_on_an_exact_name():
    a = StoryAnim(ReplaySceneReader({CUE: ANSWERS[CUE]}))
    shot = await a.read(CUE, {"Ravi": "he", "Meena": "she"})
    assert shot.spec is not None and a.world.entities["e1"].gender == "he"
    b = StoryAnim(ReplaySceneReader({CUE: ANSWERS[CUE]}))
    await b.read(CUE, {"Ravindra": "he"})
    assert b.world.entities["e1"].gender == ""
    assert isinstance(a.world, W.World) and a.before == [CUE]


async def test_the_end_said_during_the_last_call_still_lands_its_shot_on_the_still_slide():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    slide, o = deck.live.id, eng._story.open
    reader.delay_s = 0.05
    await talk.say(PICK)                                      # the call is in flight ...
    await talk.say("And that's the end of the story.")        # ... when the story ends
    await eng._story.tick()
    assert eng._story.open is None
    await o.atask
    b = next(x for x in eng._spec(slide).blocks if x.type == "story")
    assert b.still and b.story.shot["n"] == 2


async def test_a_refused_line_said_again_is_read_again():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    reader.answers.pop(PICK.strip())
    await say(eng, talk, PICK)                                # refused (no answer)
    reader.answers[PICK] = ANSWERS[PICK]
    await say(eng, talk, PICK)                                # said again: read again, now drawn
    assert len(reader.calls) == 3 and story_on(deck).shot["n"] == 2


# ---- test58 fixes (P1c live, 3 tries) ----------------------------------------------------------------------------
async def _run58(upto=None):
    from tests.fixtures.story.p1c_test58 import ANSWERS as A58, LINES as L58
    a = StoryAnim(ReplaySceneReader(A58))
    shots = {}
    for line, _ in L58[:upto]:
        s = await a.read(line, {"Mina": "she"})
        assert s.spec is not None, (line, s.why)
        shots[line] = s.spec
    return a, shots


def _ent(spec, name):
    return next(e for e in spec["entities"] if e["name"] == name)


async def test58_a_new_basket_stands_on_the_ground_and_the_apple_goes_in():
    a, shots = await _run58()
    sp = shots["Ravi, put the apple in a basket."]
    b = _ent(sp, "a basket")
    assert b["start"]["holder"] == "" and b["start"]["y"] < 0.5 and b["end"]["holder"] == ""
    assert _ent(sp, "An apple")["end"]["holder"] == ""
    climb = shots["Ravi climbed the apple tree."]
    assert _ent(climb, "a basket")["end"]["holder"] == ""        # he climbs empty-handed


async def test58_a_met_person_walks_in_beside_him_never_inside_the_trunk():
    a, shots = await _run58()
    sp = shots["There he met his sister, Mina."]
    m, r, tr = _ent(sp, "Mina"), _ent(sp, "Ravi"), _ent(sp, "an apple tree")
    assert not 0 < m["start"]["x"] < 14                           # off stage first ...
    assert any(e["op"] == "move" and e["actor"] == m["id"] for e in sp["events"])   # ... walks in
    assert abs(m["end"]["x"] - r["end"]["x"]) <= 2.3 and abs(m["end"]["x"] - tr["end"]["x"]) > 0.6


async def test58_the_horse_rides_on_to_a_free_spot_at_the_village():
    a, shots = await _run58()
    sp = shots["An old man rode his horse to the village."]
    h = _ent(sp, "his horse")["end"]["x"]
    people = [e["end"]["x"] for e in sp["entities"] if e["asset"] == "person" and e["name"] in ("Ravi", "Mina")]
    assert all(abs(h - x) >= 1.5 for x in people) and h > max(people)


async def test58_a_misheard_name_is_the_same_person():
    ans = {CUE.replace("Ravi", "Rabi"): _ans(new=[_person("e1", "Rabi")]),
           "Ravi was sitting.": _ans(new=[_person("e2", "Ravi")], events=[_ev("change_posture", "e2", value="sit",
                                                                                 verb="sitting")])}
    a = StoryAnim(ReplaySceneReader(ans))
    await a.read(CUE.replace("Ravi", "Rabi"))
    s = await a.read("Ravi was sitting.")
    assert s.spec is not None and list(a.world.entities) == ["e1"] and a.world.entities["e1"].posture == "sit"


async def test58_class_talk_with_anyone_makes_no_call():
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    await say(eng, talk, "Can anyone see the screen?")
    assert len(reader.calls) == 1


async def test58_the_end_lines_late_reading_makes_no_slide():
    from tests.unit.test_presentation_engine import act, ready, send
    bus, deck, eng, talk, asked, reader = await anim_lecture()
    await say(eng, talk, CUE)
    await say(eng, talk, PICK)
    sid = await talk.say("And that is the end of the story.")
    await eng._story.tick()
    n = len(deck.slides)
    await send(bus, ready("Ravi", "Biography", [act("explanation", points=["The story ends."])], relation="new_topic",
                          segs=[sid]))
    assert len(deck.slides) == n and not any(s.title == "Biography" for s in deck.slides)
