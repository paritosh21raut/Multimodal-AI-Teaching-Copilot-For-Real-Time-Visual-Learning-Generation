"""P1a: op / affordance registry and the story benchmark (fixture integrity, oracle, scorer)."""
from copilot.story import ops as O
from copilot.story import world as W
from copilot.story.compile import Compiler, asset_for, assets
from copilot.story.scene_llm import PREFIX
from tools import story_bench as B


# ---- registry ------------------------------------------------------------------------------------------------------
def test_every_op_has_a_full_registry_entry():
    assert O.check_registry() == []
    for name in W.OPS:
        op = O.OPS[name]
        assert op.actor and op.fail and op.target in ("required", "optional", "none") and op.dur >= 0


def test_sidecars_carry_affordances_with_anchors():
    a = assets()
    for name in ("tree", "horse", "apple", "village", "person"):
        assert "affordances" in a[name], name
        for aff in a[name]["affordances"].values():
            assert {"target", "actor"} <= set(aff)
    assert "rideable" in a["horse"]["affordances"] and "shade" in a["tree"]["affordances"]


def world_of(*ents):
    w = W.World()
    for e in ents:
        w.entities[e.id] = e
    return w


BOY = W.Entity("e1", "person", "The boy", "boy")
HORSE = W.Entity("e2", "animal", "his horse", "horse")
TREE = W.Entity("e3", "prop", "a tree", "tree")
BENCH = W.Entity("e4", "prop", "a bench", "bench")
APPLE = W.Entity("e5", "prop", "an apple", "apple")


def cls(ev, w):
    return O.classify(ev, w, asset_for, assets())[0]


def test_classify_four_ways():
    w = world_of(BOY, HORSE, TREE, BENCH, APPLE)
    assert cls(W.Event("attach", "e1", "e2", value="ride"), w) == "executable"
    assert cls(W.Event("attach", "e1", "e3", value="ride"), w) == "invalid"          # ride a tree
    assert cls(W.Event("attach", "e1", "e4", value="sit_on"), w) == "missing_asset"  # no bench drawn
    assert cls(W.Event("attach", "e1", "e4", value="in"), w) == "unsupported"        # understood, no motion yet (P1b: hold has one)
    assert cls(W.Event("work", "e1", "e3"), w) == "unsupported"
    assert cls(W.Event("speak", "e1", "e2"), w) == "executable"
    assert cls(W.Event("change_posture", "e3", value="sit"), w) == "invalid"         # a tree sits
    assert cls(W.Event("look_at", "e1"), w) == "invalid"                             # no target


def test_invalid_never_animates_and_the_spec_carries_the_class():
    w = world_of(BOY, TREE)
    w.events = [W.Event("attach", "e1", "e3", value="ride", verb="rode")]
    w.relations = [W.Relation("e1", "next_to", "e3")]
    w.rev = 1
    spec = Compiler().compile(w, "The boy rode a tree.")
    assert spec["checks"] == [{"op": "attach", "actor": "e1", "target": "e3", "class": "invalid",
                               "why": "ride: tree is not rideable", "fallback": "ride: tree is not rideable"}]
    assert spec["events"] == [] and spec["fallback"][0]["why"] == "ride: tree is not rideable"


# ---- benchmark fixture -----------------------------------------------------------------------------------------------
def test_benchmark_shape_and_split_by_story():
    ss = B.load()
    assert len(ss) == 24 and len({s["id"] for s in ss}) == 24
    for g in B.GENRES:
        mine = [s for s in ss if s["genre"] == g]
        assert len(mine) == 8 and sum(s["familiar"] for s in mine) == 4
    splits = [s["split"] for s in ss]
    assert (splits.count("dev"), splits.count("val"), splits.count("test")) == (8, 4, 12)
    assert all(6 <= len(s["lines"]) <= 12 for s in ss)
    n = sum(len(ln.get("ev", [])) for s in ss for ln in s["lines"])
    assert 230 <= n <= 320, n


def test_benchmark_lines_are_unseen_and_fixture_is_consistent():
    import json
    from pathlib import Path
    p0 = json.loads((Path(B.BENCH).parent / "p0_relations.json").read_text(encoding="utf-8"))
    p0_lines = {it["line"] for it in p0["items"]} | {x for p in p0["pairs"] for x in p["lines"]}
    texts = [ln["text"] for s in B.load() for ln in s["lines"]]
    assert len(texts) == len(set(texts))
    assert not [t for t in texts if t in PREFIX or t in p0_lines]
    assert [p for s in B.load() for p in B.problems(s)] == []


def test_oracle_deltas_validate_and_map_back_to_the_cast():
    for s in B.load():
        world, ids = W.World(), {}
        for i, ln in enumerate(s["lines"]):
            d, why = W.validate(B.oracle_answer(s, i, world, ids), world, ln["text"])
            assert d is not None, (s["id"], i, why)
            assert world.apply(d)
        assert all(B.map_entity(world.entities[eid], s) == k for k, eid in ids.items()), s["id"]


def test_same_ids_lists_earlier_cast_only():
    s = next(x for x in B.load() if x["id"] == "m01")
    same = B.same_ids(s)
    assert same[0] == [] and "fox" in same[2] and "grapes" in same[5]


# ---- scorer ----------------------------------------------------------------------------------------------------------
def test_oracle_report_is_honest_and_ranks_unknowns():
    r = B.report(B.load({"dev", "val"}))
    a = r["all"]
    assert a["refused"] == 0 and a["continuity"] == 100.0 and a["fallback_honesty"] == 100.0
    assert 0 < a["events"] < 100 and a["relations"] >= 90
    assert r["unknown_action"][0][1] >= r["unknown_action"][-1][1]
    assert set(r["tags"]) <= set(B.TAGS)


def test_scorer_tags_a_pronoun_entity_and_a_wrong_target():
    s = {"id": "x1", "genre": "moral", "split": "dev", "familiar": False, "title": "t",
         "cast": {"boy": {"kind": "person", "name": "The boy"}, "horse": {"kind": "animal", "name": "his horse"},
                  "village": {"kind": "place", "name": "the village"}},
         "lines": [{"text": "The boy saw his horse.", "ev": [{"act": "look", "by": "boy", "to": "horse"}]},
                   {"text": "He walked to the village.", "ev": [{"act": "walk", "by": "boy", "to": "village"}]},
                   {"text": "He nodded.", "ev": [{"act": "nod", "by": "boy"}]}]}
    import json
    a0 = {"rev": 0, "new": [{"id": "e1", "kind": "person", "name": "The boy"},
                            {"id": "e2", "kind": "animal", "name": "his horse"}],
          "events": [{"op": "look_at", "actor": "e1", "target": "e1"}]}             # wrong target: 0.5
    a1 = {"rev": 1, "new": [{"id": "e3", "kind": "person", "name": "He"}, {"id": "e4", "kind": "place", "name": "the village"}],
          "events": [{"op": "move_to", "actor": "e3", "target": "e4"}]}             # a new "He": coreference
    a2 = {"rev": 2, "events": [{"op": "react", "actor": "e1", "value": "happy"}]}  # a guessed gesture for "jumped"
    t = B.score_story(s, [{"text": json.dumps(a), "s": 1.0} for a in (a0, a1, a2)])
    assert t.ev == 0.5 and t.ev_n == 3
    assert t.tags["COREFERENCE"] >= 1 and t.tags["UNKNOWN_ACTION"] == 1
    assert t.honest == 0 and t.honest_n == 1
    assert t.cont < t.cont_n                       # the pronoun entity breaks continuity


def test_refused_lines_score_nothing_not_even_ends_or_old_relations():
    s = next(x for x in B.load() if x["id"] == "m08")
    t = B.score_story(s, [{"text": "{}"} for _ in s["lines"]])
    assert t.refused == len(s["lines"]) and t.rel == 0 and t.ev == 0 and t.rel_n > 0


def test_speak_duration_is_the_p0_sum():
    sp = O.OPS["speak"]
    for n in (5, 27, 29, 63):
        assert 0.3 + sp.dur + sp.per_char * n + sp.tail == 0.3 + 0.5 + 0.06 * n + 1.6
