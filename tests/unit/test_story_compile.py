"""P0 part 2 story compiler (docs/v3/P0-animation-proof.md, ADR-0015 §4): the recorded gpt-oss-20b deltas for the
gate lines A-D (0 tokens) -> world -> StorySceneSpec; the relations come out geometrically true."""
import asyncio
import math

import pytest

from copilot.story import world as W
from copilot.story.compile import G, Compiler, assets
from tools.p0_specs import TESTS, build, recorded, story_specs


@pytest.fixture(scope="module")
def specs():
    return asyncio.run(build())


def ent(spec, asset):
    return [e for e in spec["entities"] if e["asset"] == asset]


def ev(spec, op):
    return [e for e in spec["events"] if e["op"] == op]


def head(p):
    """The head top as the rig draws it (person.json: the posture's pelvis height and lean)."""
    P = assets()["person"]
    lean, reach = P["lean"][p["posture"]], P["torso"] + P["neck"] + P["head_r"]
    return (p["x"] + p["facing"] * math.sin(lean) * reach,
            P["pelvis"][p["posture"]] + math.cos(lean) * reach + P["head_r"])


def head_top(p):
    return head(p)[1]


def test_a_newton_sits_under_the_canopy_clear_of_the_trunk(specs):
    a = specs["A"]
    (tree,), (newton,) = ent(a, "tree"), ent(a, "person")
    T = assets()["tree"]
    x, tx = newton["end"]["x"], tree["start"]["x"]
    assert tx + T["under"]["x0"] <= x <= tx + T["under"]["x1"]
    assert abs(x - tx) >= T["trunk"]["w"] / 2 + T["under"]["clear"] - 1e-9
    assert newton["start"]["posture"] == "stand" and newton["end"]["posture"] == "sit"
    assert ev(a, "posture")[0]["to"] == "sit"
    assert newton["known"] == "newton" and tree["fruit"] == "apple" and tree["hidden"] == []
    assert head_top(newton["end"]) < T["canopy"]["cy"] - T["canopy"]["ry"]   # the head stays below the leaves


def test_b_the_same_apple_falls_onto_his_head_and_he_reacts(specs):
    a, b = specs["A"], specs["B"]
    (newton,) = ent(b, "person")
    assert newton["start"] == ent(a, "person")[0]["end"]          # B starts where A ended (same id, same place)
    (apple,), (tree,) = ent(b, "apple"), ent(b, "tree")
    k = apple["start"]["fruit"]
    fx, fy = assets()["tree"]["fruit"][k]
    assert apple["start"]["tree"] == tree["id"] and k in tree["hidden"]   # one of the tree's own apples
    assert (apple["start"]["x"], apple["start"]["y"]) == pytest.approx((tree["start"]["x"] + fx, fy))
    (fall,) = ev(b, "fall")
    c = fall["contact"]
    assert c["on"] == newton["id"] and c["part"] == "head"
    assert c["at"][1] == pytest.approx(head_top(newton["start"]) + fall["r"])
    h = fall["from"][1] - c["at"][1]
    assert c["t"] - fall["t0"] == pytest.approx(math.sqrt(2 * h / G), abs=1e-3)   # free fall, Python's g
    x_at = fall["from"][0] + fall["v"][0] * (c["t"] - fall["t0"])
    assert x_at == pytest.approx(head(newton["start"])[0], abs=1e-3)                  # it lands on the head
    (react,) = ev(b, "react")
    assert react["actor"] == newton["id"] and react["t0"] == c["t"] and react["style"] == "hit_reacts"
    assert fall["rest"][1] == pytest.approx(assets()["apple"]["r"])               # it ends on the ground


def test_c_the_horse_carries_the_rider_to_the_village(specs):
    c = specs["C"]
    (boy,), (horse,), (village,) = ent(c, "person"), ent(c, "horse"), ent(c, "village")
    (mount,), (move,) = ev(c, "mount"), ev(c, "move")
    assert boy["start"]["carrier"] == "" and boy["end"]["carrier"] == horse["id"] and boy["end"]["anchor"] == "saddle"
    assert mount["t1"] <= move["t0"]
    assert move["actor"] == horse["id"] and move["carries"] == [boy["id"]]          # the carrier moves, not the boy
    assert not [e for e in c["events"] if e["op"] == "move" and e["actor"] == boy["id"]]
    front = move["to"] + assets()["horse"]["length"] / 2
    assert front <= village["start"]["x"] + assets()["village"]["entrance"] + 1e-6   # stops at the village edge
    assert move["to"] - move["from"] > 3


def test_d_einstein_faces_his_friend_and_speaks(specs):
    d = specs["D"]
    people = {e["known"] or "friend": e for e in ent(d, "person")}
    e, f = people["einstein"], people["friend"]
    assert (f["start"]["x"] - e["start"]["x"]) * e["start"]["facing"] > 0
    assert e["start"]["facing"] == -f["start"]["facing"]
    (sp,) = ev(d, "speak")
    assert sp["actor"] == e["id"] and sp["to"] == f["id"] and sp["text"] == "time is relative"
    assert [s["name"] for s in d["skipped"]] == ["time"]                            # an abstract word is not drawn


def test_stale_and_unknown_ops_are_explicit():
    """An op with no motion stays as an explicit fallback (logged), never a guessed gesture."""
    w = W.World()
    d, why = W.validate({"rev": 0, "new": [{"id": "e1", "kind": "person", "name": "The man", "posture": "stand"},
                                           {"id": "e2", "kind": "prop", "name": "the wood"}],
                         "events": [{"op": "work", "actor": "e1", "target": "e2", "verb": "chopped"}]},
                        w, "The man chopped the wood.")
    assert why == "" and w.apply(d)
    spec = Compiler().compile(w, "The man chopped the wood.")
    assert spec["fallback"] == [{"op": "work", "actor": "e1", "verb": "chopped", "why": "no motion for this op in P0"}]
    assert {e["asset"] for e in spec["entities"]} == {"person", "box"}               # the wood: a labelled box


def test_specs_file_matches_the_recorded_answers(specs):
    import json
    from pathlib import Path
    saved = json.loads((Path(__file__).resolve().parents[2] / "web/story/anim/p0_specs.json").read_text("utf-8"))
    assert {k: saved[k] for k in specs} == json.loads(json.dumps(specs))
    assert set(TESTS) == {"AB", "C", "D"} and recorded()
    # the A world feeds B: a fresh compiler on B alone would not know the tree
    got = asyncio.run(story_specs(TESTS["AB"], recorded()))
    assert got[1]["entities"][0]["start"]["posture"] == "sit"


# ---- review fixes (worlds beyond A-D, hand-written deltas) ---------------------------------------------------------
def run(lines):
    """[(line, delta dict)] on one world + one compiler -> the specs."""
    w, comp, out = W.World(), Compiler(), []
    for line, ans in lines:
        d, why = W.validate({"rev": w.rev, **ans}, w, line)
        assert why == "" and w.apply(d), why
        out.append(comp.compile(w, line))
    return out


P = lambda i, name, **k: {"id": i, "kind": "person", "name": name, **k}  # noqa: E731
PL = lambda i, name: {"id": i, "kind": "place", "name": name}  # noqa: E731


def test_a_new_relation_for_an_earlier_actor_walks_him_there():
    s1, s2 = run([("The boy stood in the field.", {"new": [P("e1", "The boy"), PL("e2", "the field")],
                                                    "relations": [{"a": "e1", "rel": "in", "b": "e2"}]}),
                  ("The boy sat under an apple tree.", {"new": [PL("e3", "an apple tree")],
                   "events": [{"op": "change_posture", "actor": "e1", "value": "sit"}],
                   "relations": [{"a": "e1", "rel": "under", "b": "e3"}]})])
    tree = next(e for e in s2["entities"] if e["asset"] == "tree")
    boy = next(e for e in s2["entities"] if e["id"] == "e1")
    T = assets()["tree"]
    assert tree["start"]["x"] + T["under"]["x0"] <= boy["end"]["x"] <= tree["start"]["x"] + T["under"]["x1"]
    ops = [e["op"] for e in s2["events"]]
    assert ops == ["move", "posture"] and boy["end"]["posture"] == "sit" and boy["end"]["tree"] == "e3"


def test_a_restated_ride_never_slides_and_two_destinations_get_two_places():
    horse = {"id": "e2", "kind": "animal", "name": "his horse"}
    ride = {"op": "attach", "actor": "e1", "target": "e2", "value": "ride"}
    s1, s2 = run([("The boy rode his horse to the village.",
                   {"new": [P("e1", "The boy"), horse, PL("e3", "the village")],
                    "events": [ride, {"op": "move_to", "actor": "e1", "target": "e3"}],
                    "relations": [{"a": "e1", "rel": "ride", "b": "e2"}]}),
                  ("He rode his horse to the river.", {"new": [PL("e4", "the river")],
                   "events": [ride, {"op": "move_to", "actor": "e1", "target": "e4"}]})])
    places = {e["id"]: e["start"]["x"] for e in s2["entities"] if e["kind"] == "place"}
    assert places["e3"] != places["e4"]
    assert [e["op"] for e in s2["events"]] == ["move"]                          # no second mount
    boy = next(e for e in s2["entities"] if e["id"] == "e1")
    hor = next(e for e in s2["entities"] if e["id"] == "e2")
    assert boy["start"]["x"] == hor["start"]["x"] and boy["end"]["x"] == hor["end"]["x"]   # the rider's x follows


def test_a_person_falls_over_where_he_is_and_a_ground_prop_does_not_fly():
    s1, = run([("The man fell.", {"new": [P("e1", "The man")], "events": [{"op": "fall", "actor": "e1"}]})])
    (ev,) = s1["events"]
    assert ev["op"] == "posture" and ev["to"] == "lie"
    man = s1["entities"][0]
    assert man["end"]["x"] == man["start"]["x"] and man["end"]["y"] == 0
    s2, = run([("The stone fell.", {"new": [{"id": "e1", "kind": "prop", "name": "The stone"}],
                                     "events": [{"op": "fall", "actor": "e1"}]})])
    assert s2["events"] == [] and s2["fallback"][0]["why"] == "already on the ground"


def test_fruit_is_not_taken_from_a_tree_he_is_not_under():
    s1, s2 = run([("An apple tree stood by the village.", {"new": [PL("e1", "An apple tree"), PL("e2", "the village")]}),
                  ("An apple fell on the man.", {"new": [{"id": "e3", "kind": "prop", "name": "An apple"},
                                                         P("e4", "the man")],
                   "events": [{"op": "fall", "actor": "e3", "target": "e4", "value": "head"}]})])
    tree = next(e for e in s2["entities"] if e["asset"] == "tree")
    (fall,) = [e for e in s2["events"] if e["op"] == "fall"]
    assert tree["hidden"] == [] and abs(fall["v"][0]) < 1e-6                    # straight down from above him


def test_speak_carries_the_turns_the_browser_plays():
    s1, s2 = run([("Ravi met Sita.", {"new": [P("e1", "Ravi"), P("e2", "Sita")]}),
                  ("Sita said to Ravi, hello.", {"events": [{"op": "speak", "actor": "e2", "target": "e1",
                                                             "value": "hello"}]})])
    (sp,) = s2["events"]
    a = {e["id"]: e for e in s2["entities"]}
    assert sp["facing"] and all(a[i]["end"]["facing"] == f for i, f in sp["facing"].items())
    assert (a["e1"]["end"]["x"] - a["e2"]["end"]["x"]) * a["e2"]["end"]["facing"] > 0


# ---- look round (user 2026-11-02): name tags, main vs supporting looks, free spots, walking together ---------------
def test_name_tags_only_for_named_people():
    from copilot.story.look import label
    E = W.Entity
    assert label(E("e1", "person", "Geeta", "Geeta")) == "Geeta"
    assert label(E("e2", "person", "her brother Arun", "Arun")) == "Arun"
    assert label(E("e3", "person", "Newton", "Newton", known="newton")) == "Newton"
    for name in ("The boy", "his friend", "two boys", "The old man", "A Farmer"):
        assert label(E("e4", "person", name, W.words(name)[-1])) == "", name
    assert label(E("e5", "animal", "Moti", "Moti")) == "" and label(E("e6", "place", "the Village", "village")) == ""


def test_main_characters_differ_and_supporting_ones_share_a_look():
    from tools.p0_specs import look_demo
    e, f = look_demo()
    p = {x["id"]: x for x in e["entities"] if x["kind"] == "person"}
    geeta, arun, b1, b2 = p["e1"], p["e2"], p["e3"], p["e4"]
    assert (geeta["label"], arun["label"], b1["label"]) == ("Geeta", "Arun", "")
    assert geeta["look"]["main"] and arun["look"]["main"] and not b1["look"]["main"]
    assert geeta["look"]["shirt"] != arun["look"]["shirt"]
    assert geeta["look"]["dress"] and not arun["look"]["dress"]                  # "she" from the said words only
    assert b1["look"] == b2["look"] and b1["look"]["scale"] < 1                  # supporting boys: one shared look
    xs = sorted(x["end"]["x"] for x in p.values())
    assert all(b - a >= 0.8 for a, b in zip(xs, xs[1:]))                       # nobody stands inside anybody
    moves = [x for x in e["events"] if x["op"] == "move"]
    assert len({m["t0"] for m in moves}) == 1                                   # they walk together
    assert all(m["to"] > m["from"] for m in moves)                              # all towards the village
    (sp,) = f["events"]
    assert p["e1"]["end"]["x"] != p["e2"]["end"]["x"] and sp["facing"]


def test_two_named_look_alikes_get_different_hair():
    from copilot.story.look import Looks
    w = W.World()
    w.apply(W.Delta(0, new=[W.Entity("e1", "person", "Ravi", "Ravi", gender="he"),
                            W.Entity("e2", "person", "Mohan", "Mohan", gender="he"),
                            W.Entity("e3", "person", "Sohan", "Sohan", gender="he")]))
    looks = Looks().update(w)
    assert len({(v["hair"], v["acc"], v["shirt"]) for v in looks.values()}) == 3
    assert looks["e3"]["acc"] == "cap"
