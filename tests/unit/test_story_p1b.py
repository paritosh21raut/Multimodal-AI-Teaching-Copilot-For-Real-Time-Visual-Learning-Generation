"""P1b semantic actions (docs/v3/P1b-semantic-actions.md): rev stamped by the caller, new ids renumbered / definite
names reused, the new ops validated and applied, every motion compiled with Python's numbers (hand anchor, g)."""
import math

import pytest

from copilot.story import ops as O
from copilot.story import world as W
from copilot.story.compile import G, Compiler, assets
from tools.p0_specs import p1b_demo
from tools.story_bench import load, report


def world_with(*ents):
    w = W.World()
    assert w.apply(W.Delta(0, new=[W.Entity(*e) for e in ents]))
    return w


def test_rev_is_stamped_by_the_caller():
    w = world_with(("e1", "person", "Ravi", "ravi"))
    ans = {"rev": 7, "events": [{"op": "react", "actor": "e1", "value": "happy"}]}
    assert W.validate(ans, w, "Ravi smiled")[0].rev == 7                       # old callers: the echoed rev
    d, _ = W.validate(ans, w, "Ravi smiled", rev=w.rev)
    assert d.rev == w.rev and w.apply(d)


def test_a_taken_new_id_is_renumbered_with_its_references():
    w = world_with(("e1", "person", "Ravi", "ravi"))
    ans = {"new": [{"id": "e1", "kind": "prop", "name": "a stone", "noun": "stone"}],
           "events": [{"op": "attach", "actor": "e1", "target": "e1", "value": "hold"}]}
    d, why = W.validate(ans, w, "Ravi picked up a stone", rev=w.rev)
    assert why == "" and d.new[0].id == "e2" and d.events[0].target == "e2" and d.events[0].actor == "e2"


def test_a_definite_name_is_the_thing_already_in_the_world():
    w = world_with(("e1", "animal", "a fox", "fox"), ("e2", "prop", "a bunch of grapes", "grapes"))
    ans = {"new": [{"id": "e3", "kind": "prop", "name": "the grapes", "noun": "grapes"}],
           "events": [{"op": "look_at", "actor": "e1", "target": "e3"}]}
    d, _ = W.validate(ans, w, "The fox looked at the grapes", rev=w.rev)
    assert d.new == [] and d.events[0].target == "e2"
    ans["new"][0]["name"] = "a grapes"                                          # indefinite: a new thing
    assert W.validate(ans, w, "The fox looked at a grapes", rev=w.rev)[0].new[0].id == "e3"


def test_new_ops_validate_and_apply():
    w = world_with(("e1", "person", "Ravi", "ravi"), ("e2", "prop", "a cup", "cup"), ("e3", "prop", "a table", "table"),
                   ("e4", "person", "Meena", "meena"), ("e5", "prop", "the tree", "tree"))
    w.relations.append(W.Relation("e1", "hold", "e2"))
    assert W.validate({"events": [{"op": "put", "actor": "e1", "target": "e3"}]}, w, "x", rev=w.rev)[1] == "put: no obj"
    assert W.validate({"events": [{"op": "push", "actor": "e1", "target": "e3", "value": "shove"}]}, w, "x",
                      rev=w.rev)[0] is None
    d, _ = W.validate({"events": [{"op": "put", "actor": "e1", "obj": "e2", "target": "e3"}]}, w, "x", rev=w.rev)
    assert d.events[0].value == "on" and w.apply(d)
    assert W.Relation("e2", "on", "e3") in w.relations and W.Relation("e1", "hold", "e2") not in w.relations
    w.relations.append(W.Relation("e1", "hold", "e2"))
    assert w.apply(W.Delta(w.rev, events=[W.Event("give", "e1", "e4", "e2")]))
    assert W.Relation("e4", "hold", "e2") in w.relations and W.Relation("e1", "hold", "e2") not in w.relations
    assert w.apply(W.Delta(w.rev, events=[W.Event("climb", "e1", "e5")]))
    assert W.Relation("e1", "on", "e5") in w.relations
    assert w.apply(W.Delta(w.rev, events=[W.Event("jump", "e1", "e5", value="off")]))
    assert not any(r.a == "e1" and r.rel == "on" for r in w.relations)


def test_registry_and_classes():
    assert O.check_registry() == []
    A = assets()
    w = world_with(("e1", "person", "Ravi", "ravi"), ("e2", "prop", "a horse", "horse"), ("e3", "prop", "the tree", "tree"),
                   ("e4", "agent", "the wind", "wind"), ("e5", "prop", "an apple", "apple"))
    from copilot.story.compile import asset_for
    cls = lambda ev: O.classify(ev, w, asset_for, A)[0]
    assert cls(W.Event("climb", "e1", "e3")) == "executable"
    assert cls(W.Event("climb", "e1", "e2")) == "invalid"                       # a horse is not climbable
    assert cls(W.Event("give", "e1", "e3", "e5")) == "invalid"                  # a tree cannot take it
    assert cls(W.Event("push", "e4", "e5")) == "executable"                     # the wind needs no drawing
    assert cls(W.Event("attach", "e1", "e5", value="hold")) == "executable"


@pytest.fixture(scope="module")
def demo():
    return p1b_demo()


def ops(spec):
    return [e["op"] for e in spec["events"]]


def test_demo_compiles_every_motion_with_no_fallback(demo):
    assert [s["fallback"] for s in demo] == [[]] * 7
    want = [{"grip", "move"}, {"place", "climb"}, {"jump"}, {"handover"}, {"throw_arm", "fall"},
            {"grip", "push", "slide"}, {"fall", "move"}]
    for s, w in zip(demo, want):
        assert w <= set(ops(s)), (s["line"], ops(s))
    assert {c["class"] for s in demo for c in s["checks"]} <= {"executable", "missing_asset"}   # stone, cart: boxes


def test_jump_and_throw_follow_g(demo):
    j = next(e for e in demo[2]["events"] if e["op"] == "jump")
    assert j["v0"] == pytest.approx(math.sqrt(2 * G * assets()["person"]["jump_h"]), rel=1e-3)
    y_land = j["from"][1] + j["v0"] * (j["t_land"] - j["t_up"]) - 0.5 * G * (j["t_land"] - j["t_up"]) ** 2
    assert y_land == pytest.approx(j["to"][1], abs=1e-3)
    f = next(e for e in demo[4]["events"] if e["op"] == "fall")
    d = f["contact"]["t"] - f["t0"]
    assert f["from"][0] + f["v"][0] * d == pytest.approx(f["contact"]["at"][0], abs=1e-3)
    assert f["from"][1] + f["v"][1] * d - 0.5 * G * d * d == pytest.approx(f["contact"]["at"][1], abs=1e-3)


def test_exit_leaves_the_stage_and_is_not_drawn_next_line(demo):
    boy_end = next(e for e in demo[6]["entities"] if e["id"] == "e5")["end"]
    assert boy_end["gone"] and not 0 <= boy_end["x"] <= 14
    w, c = W.World(), Compiler()
    for spec_line, delta in zip(range(7), __import__("tools.p0_specs", fromlist=["P1B_DEMO"]).P1B_DEMO):
        w.apply(delta[1])
        c.compile(w, delta[0])
    assert w.apply(W.Delta(w.rev, events=[W.Event("react", "e1", value="happy")]))
    nxt = c.compile(w, "Ravi smiled.")
    assert "e5" not in {e["id"] for e in nxt["entities"]}
    assert any(s["id"] == "e5" and "gone" in s["why"] for s in nxt["skipped"])


def test_oracle_lifts_and_no_batch_motion_is_missing():
    r = report(load({"dev", "val"}))
    assert r["all"]["events"] >= 48 and r["all"]["relations"] == 100 and r["all"]["continuity"] == 100
    assert dict(r["motion"]) == {"attach in": 1}                                 # all batch-1 motions exist
    batch = {"put", "jump", "climb", "catch", "lift", "give", "push", "pull", "put_down", "follow", "wake"}
    assert not batch & {a for a, _ in r["unknown_action"]}


def run(lines):
    w, c, out = W.World(), Compiler(), []
    for line, d in lines:
        d.rev = w.rev
        assert w.apply(d), line
        out.append(c.compile(w, line))
    return out


def test_review_down_before_walking_and_gone_until_back():
    o = run([("Ravi climbed the tree.", W.Delta(0, new=[W.Entity("e1", "person", "Ravi", "ravi"),
                                                        W.Entity("e2", "prop", "the tree", "tree"),
                                                        W.Entity("e3", "place", "the village", "village")],
                                               events=[W.Event("climb", "e1", "e2")])),
             ("He walked to the village.", W.Delta(0, events=[W.Event("move_to", "e1", "e3")])),
             ("He left.", W.Delta(0, events=[W.Event("exit", "e1")])),
             ("Meena smiled.", W.Delta(0, new=[W.Entity("e4", "person", "Meena", "meena")],
                                       events=[W.Event("react", "e4", value="happy")])),
             ("Ravi came back.", W.Delta(0, events=[W.Event("enter", "e1")]))])
    assert ops(o[1])[:3] == ["posture", "jump", "move"]                         # off the branch, then walks
    assert next(e for e in o[1]["entities"] if e["id"] == "e1")["end"]["y"] == 0.0
    assert "e1" not in {e["id"] for e in o[3]["entities"]}                     # gone: not drawn, not a target
    back = next(e for e in o[4]["entities"] if e["id"] == "e1")
    assert not 0 <= back["start"]["x"] <= 14 and 0.6 <= back["end"]["x"] <= 13.4   # walks in from the edge


def test_review_pull_moves_the_thing_and_rider_jumps_off_by_dismounting():
    o = run([("Ravi pulled a box.", W.Delta(0, new=[W.Entity("e1", "person", "Ravi", "ravi"),
                                                    W.Entity("e2", "prop", "a box", "box")],
                                           events=[W.Event("push", "e1", "e2", value="pull")]))])
    sl = next(e for e in o[0]["events"] if e["op"] == "slide")
    assert abs(sl["to"] - sl["from"]) == pytest.approx(1.2, abs=0.01)
    o = run([("The boy rode his horse.", W.Delta(0, new=[W.Entity("e1", "person", "The boy", "boy"),
                                                         W.Entity("e2", "animal", "his horse", "horse")],
                                                events=[W.Event("attach", "e1", "e2", value="ride")],
                                                relations=[W.Relation("e1", "ride", "e2")])),
             ("He jumped off the horse.", W.Delta(0, events=[W.Event("jump", "e1", "e2", value="off")]))])
    assert "dismount" in ops(o[1]) and not next(e for e in o[1]["entities"] if e["id"] == "e1")["end"]["carrier"]


def test_review_got_off_keeps_the_lamp_and_other_boy_is_new():
    w = world_with(("e1", "person", "The boy", "boy"), ("e2", "animal", "a horse", "horse"), ("e3", "prop", "a lamp", "lamp"))
    w.relations += [W.Relation("e1", "ride", "e2"), W.Relation("e1", "hold", "e3")]
    assert w.apply(W.Delta(w.rev, events=[W.Event("detach", "e1")]))
    assert W.Relation("e1", "hold", "e3") in w.relations and W.Relation("e1", "ride", "e2") not in w.relations
    ans = {"new": [{"id": "e4", "kind": "person", "name": "the other boy", "noun": "boy"}],
           "events": [{"op": "react", "actor": "e4", "value": "happy"}]}
    assert W.validate(ans, w, "the other boy smiled", rev=w.rev)[0].new[0].id == "e4"


def test_round1_put_is_set_down_beside_him(demo):
    s = demo[1]
    pl = next(e for e in s["events"] if e["op"] == "place")
    ravi_x = next(e for e in s["entities"] if e["id"] == "e1")["start"]["x"]
    mv = [e for e in s["events"] if e["op"] == "move" and e["t1"] <= pl["t0"]]
    stand_x = mv[-1]["to"] if mv else ravi_x
    assert abs(pl["to"][0] - stand_x) <= 0.4                                     # within reach, not tossed to the trunk
    assert any(e["op"] == "posture" and e["to"] == "reach_down" and e["t1"] <= pl["t0"] for e in s["events"])


def test_round1_throw_is_caught_and_held(demo):
    s = demo[4]
    f = next(e for e in s["events"] if e["op"] == "fall")
    assert f["contact"]["caught"] and f["contact"]["on"] == "e5"
    assert any(e["op"] == "ready" and e["actor"] == "e5" and e["t0"] < f["contact"]["t"] < e["t1"] for e in s["events"])
    assert not any(e["op"] == "react" for e in s["events"])                      # a catch is not a hit
    assert next(e for e in s["entities"] if e["id"] == "e2")["end"]["holder"] == "e5"


def test_round1_drawn_props():
    from copilot.story.compile import PROPS, asset_for
    for noun, a in (("stone", "stone"), ("bucket", "pot"), ("scrolls", "book"), ("cart", "cart")):
        assert asset_for(W.Entity("x", "prop", f"a {noun}", noun)) == a
    A = assets()
    assert all(A[p]["width"] > 0 and A[p]["height"] > 0 for p in PROPS)
    assert "holdable" not in A["cart"]["affordances"] and "holdable" in A["boat"]["affordances"]


# ---- close: optional parts only once said (user: "only show branches when the teacher says the branch") ----------
def _tree(o, i="e2"):
    return next(e for e in o["entities"] if e["id"] == i)


def test_branch_drawn_only_once_said_and_it_stays():
    specs = p1b_demo()
    assert _tree(specs[0], "e3")["parts"] == []                              # G: "walked to the tree" = the plain tree
    assert _tree(specs[1], "e3")["parts"] == ["branch"]                      # H: "... sat on a branch"
    assert all(_tree(s, "e3")["parts"] == ["branch"] for s in specs[2:4])   # once drawn, it stays


def test_climb_with_no_branch_said_clings_to_the_trunk():
    T = assets()["tree"]
    o = run([("Ravi climbed the tree.", W.Delta(0, new=[W.Entity("e1", "person", "Ravi", "ravi"),
                                                        W.Entity("e2", "prop", "the tree", "tree")],
                                               events=[W.Event("climb", "e1", "e2")]))])
    c = next(e for e in o[0]["events"] if e["op"] == "climb")
    assert _tree(o[0])["parts"] == [] and c["end"] == "climb" and c["to"][1] == T["cling"]["y"]
    assert abs(c["to"][0] - _tree(o[0])["start"]["x"]) < T["trunk"]["w"] / 2 + 0.3   # at the trunk, not on a limb


def test_a_branch_entity_is_the_trees_part_not_a_box_and_a_clinger_sits_on_it():
    T = assets()["tree"]
    o = run([("Varun climbed the tree.", W.Delta(0, new=[W.Entity("e1", "person", "Varun", "varun"),
                                                         W.Entity("e2", "prop", "the tree", "tree")],
                                                events=[W.Event("climb", "e1", "e2")])),
             ("He sat on a high branch.", W.Delta(0, new=[W.Entity("e3", "prop", "a high branch", "branch")],
                                                  events=[W.Event("change_posture", "e1", "e3", value="sit")],
                                                  relations=[W.Relation("e1", "on", "e3")]))])
    assert "e3" not in {e["id"] for e in o[1]["entities"]}                   # never a labelled box
    assert any(s["id"] == "e3" and "part of e2" in s["why"] for s in o[1]["skipped"])
    assert _tree(o[1])["parts"] == ["branch"]
    c = next(e for e in o[1]["events"] if e["op"] == "climb")
    assert c["end"] == "sit" and c["to"][1] == T["branch"]["y"]
