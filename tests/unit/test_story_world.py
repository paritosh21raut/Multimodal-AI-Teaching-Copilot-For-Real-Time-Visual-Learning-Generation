"""ADR-0015 P0 part 1: the story world (validate whole-or-nothing, apply, continuity, stale) and the scene reader step."""
import asyncio
import json
import sys
from pathlib import Path

from copilot.story import world as W
from copilot.story.scene_llm import ReplaySceneReader, messages, parse, step

ROOT = Path(__file__).resolve().parents[2]
NEWTON = "Newton was sitting under an apple tree."
APPLE = "An apple fell on his head."
A1 = {"rev": 0, "new": [
    {"id": "e1", "kind": "person", "name": "Newton", "noun": "Newton", "known": "newton", "posture": "sit"},
    {"id": "e2", "kind": "prop", "name": "an apple tree", "noun": "tree"}],
    "events": [{"op": "change_posture", "actor": "e1", "value": "sit", "verb": "sitting"}],
    "relations": [{"a": "e1", "rel": "under", "b": "e2"}], "end": []}
A2 = {"rev": 1, "new": [{"id": "e3", "kind": "prop", "name": "An apple", "noun": "apple"}],
      "events": [{"op": "fall", "actor": "e3", "target": "e1", "value": "head", "verb": "fell"},
                 {"op": "react", "actor": "e1", "value": "surprise"}], "relations": [], "end": []}


def _world(*deltas) -> W.World:
    w = W.World()
    for ans, line in deltas:
        d, why = W.validate(ans, w, line)
        assert d is not None, why
        assert w.apply(d)
    return w


def test_newton_sits_under_the_tree_then_the_apple_hits_the_same_newton():
    w = _world((A1, NEWTON))
    assert w.entities["e1"].posture == "sit" and w.entities["e1"].known == "newton"
    assert [r.summary() for r in w.relations] == ["e1 under e2"]
    w2 = _world((A1, NEWTON), (A2, APPLE))
    assert w2.rev == 2 and len([e for e in w2.entities.values() if e.kind == "person"]) == 1
    assert [(e.op, e.actor, e.target, e.value) for e in w2.events][0] == ("fall", "e3", "e1", "head")
    assert "e1 under e2" in [r.summary() for r in w2.relations]  # the earlier relation stays until changed


def test_refused_whole_unknown_id_op_relation_or_unsaid_words():
    w = _world((A1, NEWTON))
    for bad, why in [
        ({**A2, "events": [{"op": "fall", "actor": "e9", "target": "e1"}]}, "actor"),
        ({**A2, "events": [{"op": "teleport", "actor": "e3"}]}, "op"),
        ({**A2, "relations": [{"a": "e3", "rel": "inside_of", "b": "e1"}]}, "rel"),
        ({**A2, "new": [{"id": "e3", "kind": "prop", "name": "a banana"}]}, "not said"),
        ({**A2, "new": [{"id": "e2", "kind": "prop", "name": "An apple"}]}, "taken"),
        ({**A2, "events": [{"op": "react", "actor": "e1", "value": "bored"}]}, "value"),
        ({"rev": 1}, "empty"),
    ]:
        d, reason = W.validate(bad, w, APPLE)
        assert d is None and why in reason, (bad, reason)
    d, _ = W.validate({"rev": 1, "events": [{"op": "speak", "actor": "e1", "target": "e2", "value": "gravity"}]},
                      w, "Newton said, I have it.")
    assert d is None  # spoken words must be the line's own


def test_known_person_only_when_said_and_gender_only_from_said_words():
    d, _ = W.validate({"rev": 0, "new": [{"id": "e1", "kind": "person", "name": "The man", "known": "einstein",
                                         "gender": "she"}]}, W.World(), "The man walked in.")
    assert d.new[0].known == "" and d.new[0].gender == ""


def test_stale_delta_dropped_and_new_location_replaces_old():
    w = _world((A1, NEWTON))
    d, _ = W.validate({**A2, "rev": 0}, w, APPLE)
    assert d is not None and not w.apply(d) and w.rev == 1
    ride = "Then he rode his horse."
    w = _world((A1, NEWTON), ({"rev": 1, "new": [{"id": "e3", "kind": "animal", "name": "his horse"}],
                               "events": [{"op": "attach", "actor": "e1", "target": "e3", "value": "ride"}],
                               "relations": [{"a": "e1", "rel": "ride", "b": "e3"}]}, ride))
    assert [r.summary() for r in w.relations] == ["e1 ride e3"]  # no longer under the tree
    off = "He got off the horse."
    w = _world((A1, NEWTON), ({"rev": 1, "new": [{"id": "e3", "kind": "animal", "name": "his horse"}],
                               "relations": [{"a": "e1", "rel": "ride", "b": "e3"}]}, ride),
               ({"rev": 2, "events": [{"op": "detach", "actor": "e1", "target": "e3"}]}, off))
    assert w.relations == []


def test_prompt_is_bounded_and_prefix_fixed():
    w = _world((A1, NEWTON))
    m1 = messages(w, ["a", "b", "c", NEWTON], APPLE)
    m2 = messages(W.World(), [], NEWTON)
    assert m1[0] == m2[0]  # byte-identical prefix
    assert "- a\n" not in m1[1]["content"] and "e1 under e2" in m1[1]["content"]
    data = json.loads((ROOT / "tests/fixtures/story/p0_relations.json").read_text(encoding="utf-8"))
    for it in data["items"]:  # the test sentences are unseen: none in the prompt
        assert it["line"] not in m1[0]["content"]
    assert parse('```json\n{"rev": 0}\n```') == {"rev": 0} and parse("no") is None


def test_step_and_scorer_on_hand_answers():
    sys.path.insert(0, str(ROOT / "tools"))
    import record_p0 as R
    answers = {R.key([], NEWTON): json.dumps(A1), R.key([NEWTON], APPLE): json.dumps(A2)}
    world, fails, first = asyncio.run(R.run_lines(R.KeyedReplay(answers), [NEWTON, APPLE]))
    assert not fails and R.check(world, ["same", "newton"], first)
    assert R.check(world, ["op", "fall", "apple", "newton"], first)
    assert not R.check(world, ["rel", "newton", "on", "tree"], first)
    w = W.World()
    res, why = asyncio.run(step(ReplaySceneReader({NEWTON: "garbage"}), w, [], NEWTON))
    assert why == "no JSON" and w.rev == 0


def test_recorded_gpt_oss_answers_still_pass_the_gate():
    sys.path.insert(0, str(ROOT / "tools"))
    import record_p0 as R
    rec = json.loads((ROOT / "tests/fixtures/story/p0_llm_answers.json").read_text(encoding="utf-8"))["gpt-oss-20b"]
    s = asyncio.run(R.score(R.KeyedReplay(rec["answers"]), verbose=False))
    assert s["gate"] and s["ok"] >= 17 and s["valid"] == s["n"], s


def test_review_fixes_two_places_one_line_bad_types_gender_between_detach():
    line = "The old man sat on the bench under the tree."
    w = _world(({"rev": 0, "new": [{"id": "e1", "kind": "person", "name": "The old man", "gender": "he"},
                                   {"id": "e2", "kind": "prop", "name": "the bench"},
                                   {"id": "e3", "kind": "prop", "name": "the tree"}],
                 "relations": [{"a": "e1", "rel": "sit_on", "b": "e2"}, {"a": "e1", "rel": "under", "b": "e3"}]}, line))
    assert [r.summary() for r in w.relations] == ["e1 sit_on e2", "e1 under e3"] and w.entities["e1"].gender == "he"
    for bad in ({"rev": 0, "new": 5}, {"rev": 1e400}, {"rev": "0", "events": []}):
        assert W.validate(bad, W.World(), line)[0] is None
    d, _ = W.validate({"rev": 0, "new": [{"id": "e1", "kind": "person", "name": "The man", "gender": "she"},
                                         {"id": "e2", "kind": "prop", "name": "a book"}]}, W.World(),
                      "The man gave her a book.")
    assert d.new[0].gender == ""
    d, why = W.validate({"rev": 1, "relations": [{"a": "e1", "rel": "between", "b": "e2", "c": "e1"}]}, w, line)
    assert d is None and "between" in why
    w.relations.append(W.Relation("e1", "hold", "e3"))
    d, _ = W.validate({"rev": 1, "events": [{"op": "detach", "actor": "e1"}]}, w, line)
    w.apply(d)
    assert [r.summary() for r in w.relations] == ["e1 under e3"]  # let go: still under the tree
