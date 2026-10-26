"""F-017 E2 stage core: validator, laws (closed forms), provenance, event log fold / undo, director, timeline, fixtures."""
import math
import sys
from pathlib import Path

import pytest

from copilot.stage import director, timeline
from copilot.stage.acting import ACT
from copilot.stage.graph import Graph, GivenRec
from copilot.stage.laws import LAWS
from copilot.stage.log import EventLog
from copilot.stage.validate import check_delta

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools" / "stage"))
import replay  # noqa: E402

MAN = {"op": "add", "id": "man", "kind": "agent", "w": "man"}
BOX = {"op": "add", "id": "box", "kind": "prop", "w": "box"}
FLOOR = {"op": "add", "id": "floor", "kind": "surface", "w": "floor"}


def delta(ops, lines=("A man pushes a box.",), g=None):
    return check_delta(list(ops), g or Graph(), list(lines))


def reasons(d):
    return [r.reason for r in d.rejected]


# ---------- validator ----------
def test_validator_rejects_bad_ids_unknown_verbs_and_missing_refs():
    d = delta([{**MAN, "id": "Man!"}, MAN, {"op": "act", "id": "a1", "verb": "shove", "agent": "man"},
               {"op": "act", "id": "a2", "verb": "push", "agent": "ghost", "obj": "man"},
               {"op": "relate", "a": "man", "kind": "inside_of", "b": "man"}, {"op": "act", "id": "a3", "verb": "push", "agent": "man"}])
    rs = reasons(d)
    assert len(d.ok) == 1 and len(rs) == 5
    assert "bad id" in rs[0] and "unknown verb" in rs[1] and "unknown id" in rs[2] and "unknown relation" in rs[3]
    assert "needs an object" in rs[4]


def test_validator_checks_quote_number_and_unit():
    law = {"op": "law", "id": "pr", "name": "projectile", "roles": {"body": "ball"}}
    ball = {"op": "add", "id": "ball", "kind": "prop", "w": "ball"}
    line = ["He throws the ball at ten metres per second at 30 degrees."]
    ok = {"op": "given", "law": "pr", "sym": "v0", "v": 10, "u": "m/s", "q": "at ten metres per second"}
    d = delta([ball, law, ok,
               {**ok, "v": 12},                                    # not the number said
               {**ok, "q": "at 12 metres per second"},             # a quote the teacher did not say
               {**ok, "u": "kg"},                                  # wrong dimension
               {**ok, "u": "km/h"},                                # the quote says m/s
               {"op": "given", "law": "pr", "sym": "theta", "v": 30, "u": "m", "q": "at 30 degrees"},
               {"op": "given", "law": "pr", "sym": "theta", "v": 30, "u": "deg", "q": "at 30 degrees"},
               {"op": "given", "law": "pr", "sym": "mass", "v": 3, "u": "kg", "q": "at 30 degrees"}], line)
    rs = reasons(d)
    assert [type(o).__name__ for o, _ in d.ok] == ["Add", "Law", "Given", "Given"]
    assert "not said in the quote" in rs[0] and "not in the teacher's recent lines" in rs[1]
    assert "does not fit" in rs[2] and "the quote says m/s" in rs[3] and "not an angle unit" in rs[4]
    assert "has no given" in rs[5]
    assert d.ok[2][1]["si"] == 10.0 and d.ok[3][1] == {"si": 30.0, "si_u": "deg"}


def test_a_given_in_km_per_hour_is_converted_and_rest_is_zero():
    g = Graph()
    d = delta([{"op": "add", "id": "car", "kind": "prop", "w": "car"},
               {"op": "law", "id": "am", "name": "accelerated_motion", "roles": {"body": "car"}},
               {"op": "given", "law": "am", "sym": "u", "v": 36, "u": "km/h", "q": "at 36 km/h"},
               {"op": "given", "law": "am", "sym": "u", "v": 0, "u": "m/s", "q": "starts from rest"}],
              ["A car going at 36 km/h", "another car starts from rest"], g)
    assert not d.rejected
    assert abs(d.ok[2][1]["si"] - 10.0) < 1e-9 and d.ok[3][1]["si"] == 0.0


def test_validator_checks_law_preconditions_and_unbuilt_laws():
    d = delta([MAN, BOX, FLOOR, {"op": "law", "id": "fr", "name": "sliding_friction", "roles": {"body": "box", "surface": "floor"}},
               {"op": "relate", "a": "box", "kind": "on", "b": "floor"},
               {"op": "law", "id": "fr", "name": "sliding_friction", "roles": {"body": "box", "surface": "floor"}},
               {"op": "law", "id": "ec", "name": "echo", "roles": {"source": "man"}},
               {"op": "law", "id": "zz", "name": "magic", "roles": {}},
               {"op": "law", "id": "mo", "name": "moments", "roles": {"beam": "box", "pivot": "floor", "loads": "man"}}])
    rs = reasons(d)
    assert "precondition: box is not on floor" in rs[0] and "not built yet" in rs[1] and "unknown law" in rs[2]
    assert "must be a list" in rs[3]
    assert sum(type(o).__name__ == "Law" for o, _ in d.ok) == 1


def test_unsafe_blocklist_budgets_and_catalog():
    assert delta([MAN, {"op": "unsafe"}]).dropped == "unsafe"
    assert delta([{**MAN, "w": "corpse"}]).dropped.startswith("blocked")
    assert "per delta" in delta([MAN] * 17).dropped
    adds = [{"op": "add", "id": f"p{i}", "kind": "prop", "w": "ball"} for i in range(13)]
    d = check_delta(adds[:12], Graph(), ["balls"])
    g = Graph()
    for op, f in d.ok:
        from copilot.stage.graph import apply
        apply(g, op, f, "l1")
    assert "more than 12" in reasons(check_delta(adds[12:], g, ["balls"]))[0]
    rs = reasons(delta([{"op": "add", "id": "x", "kind": "prop", "w": "gizmo", "near": "flux capacitor"},
                        {"op": "add", "id": "y", "kind": "prop", "w": "gizmo"},
                        {"op": "add", "id": "z", "kind": "prop", "w": "gizmo", "near": "box"}]))
    assert "not in the catalog" in rs[0] and "nothing draws" in rs[1] and len(rs) == 2


def test_labels_and_diagram_params_must_be_said():
    d = delta([MAN, {"op": "label", "id": "man", "text": "the man"}, {"op": "label", "id": "man", "text": "Newton"},
               {"op": "diagram", "id": "d1", "recipe": "strobe", "params": {"n": 5}},
               {"op": "diagram", "id": "d2", "recipe": "strobe", "params": {"n": 4}}], ["The man takes 4 steps."])
    rs = reasons(d)
    assert len(d.ok) == 3 and "did not say" in rs[0] and "was not said" in rs[1]


def test_put_down_needs_the_thing_held():
    rs = reasons(delta([{"op": "add", "id": "woman", "kind": "agent", "w": "woman"}, BOX,
                        {"op": "act", "id": "p1", "verb": "put_down", "agent": "woman", "obj": "box"}]))
    assert "not holding" in rs[0]


# ---------- laws: closed forms ----------
def G(**kw):
    return {k: GivenRec(k, v, u, "q", v, u) for k, (v, u) in kw.items()}


def test_laws_match_their_closed_forms():
    L = {n: s.solve for n, s in LAWS.items()}
    r = L["uniform_motion"]("u", G(v=(3.0, "m/s"), t=(4.0, "s")), {})
    assert r.nums["d"].v == 12.0 and r.nums["d"].src == "computed"
    r = L["accelerated_motion"]("a", G(u=(2.0, "m/s"), a=(3.0, "m/s^2"), t=(2.0, "s")), {})
    assert math.isclose(r.nums["v"].v, 8.0) and math.isclose(r.nums["s"].v, 10.0)
    r = L["projectile"]("p", G(v0=(20.0, "m/s"), theta=(45.0, "deg"), h0=(0.0, "m")), {})
    assert math.isclose(r.nums["R"].v, 400 / 9.8, rel_tol=1e-9) and math.isclose(r.nums["T"].v, 2 * 20 * math.sin(math.pi / 4) / 9.8)
    assert math.isclose(r.nums["h_apex"].v, 100 / 9.8)
    r = L["sliding_friction"]("f", G(m=(10.0, "kg"), mu_k=(0.5, "1"), v=(4.9, "m/s")), {"phase": "released"})
    assert math.isclose(r.nums["f"].v, 49.0) and math.isclose(r.nums["t_stop"].v, 1.0) and math.isclose(r.nums["s_stop"].v, 2.45)
    r = L["sliding_friction"]("f", G(m=(10.0, "kg"), mu_k=(0.5, "1"), F=(69.0, "N")), {"phase": "hard", "v0": 0.3})
    assert math.isclose(r.nums["a"].v, 2.0)
    r = L["relative_motion"]("r", G(va=(4.0, "m/s"), vb=(3.0, "m/s")), {})
    assert math.isclose(r.nums["v_rel"].v, 5.0) and math.isclose(r.nums["theta"].v, math.degrees(math.atan(3 / 4)))
    r = L["free_fall_compare"]("c", G(v0=(2.0, "m/s")), {"places": ["moon", "mars"]})
    assert math.isclose(r.nums["h_moon"].v, 4 / (2 * 1.62)) and math.isclose(r.nums["ratio"].v, 3.71 / 1.62)
    r = L["moments"]("m", G(W1=(600.0, "N"), d1=(1.0, "m"), W2=(250.0, "N")), {"balance": True})
    assert math.isclose(r.nums["d2"].v, 2.4) and r.facts["balanced"]
    r = L["moments"]("m", G(W1=(600.0, "N"), d1=(1.0, "m"), W2=(250.0, "N"), d2=(3.0, "m")), {})
    assert r.facts["turns"] == "right_down" and not r.facts["balanced"]
    r = L["pendulum_energy"]("p", G(L=(1.0, "m"), theta0=(5.0, "deg")), {})
    assert math.isclose(r.nums["T"].v, 2 * math.pi * math.sqrt(1 / 9.8), rel_tol=2e-3)  # small angle
    assert math.isclose(r.nums["v_max"].v, math.sqrt(2 * 9.8 * (1 - math.cos(math.radians(5)))))
    e = r.samples["energy"]
    assert all(abs(p + k - 1) < 1e-3 for _, p, k in e) and e[0][1] == 1.0
    r = L["buoyancy"]("b", G(m=(0.6, "kg"), V=(0.001, "m^3")), {"rho_key": "rho_water"})
    assert r.facts["floats"] and math.isclose(r.nums["frac"].v, 0.6) and math.isclose(r.nums["U"].v, 0.6 * 9.8)
    assert r.nums["rho"].src == "constant"
    r = L["apparent_weight"]("w", G(m=(50.0, "kg"), a=(2.0, "m/s^2")), {"sign": 1})
    assert math.isclose(r.nums["N"].v, 590.0) and math.isclose(r.nums["W"].v, 490.0)
    r = L["apparent_weight"]("w", G(m=(50.0, "kg"), a=(2.0, "m/s^2")), {"sign": -1})
    assert math.isclose(r.nums["N"].v, 390.0)


def test_defaults_make_it_illustrative_and_their_results_symbols():
    r = LAWS["projectile"].solve("p", {}, {"h0": 1.5})
    assert r.illustrative and not r.nums["v0"].known and not r.nums["t_apex"].known and r.nums["g"].src == "constant"
    r = LAWS["projectile"].solve("p", G(v0=(10.0, "m/s"), theta=(30.0, "deg")), {"h0": 1.5})
    assert not r.illustrative and r.nums["t_apex"].known and not r.nums["R"].known  # h0 is the drawing's: R a symbol
    for n in r.nums.values():
        if n.src == "computed":
            assert n.inputs and all(r.nums[i].known for i in n.inputs)


# ---------- provenance in patches ----------
@pytest.fixture(scope="module")
def replays():
    return {n: replay.replay(n) for n in replay.ORDER}


def test_every_printed_number_has_a_record(replays):
    for n, (_, _, patches) in replays.items():
        for p in patches:
            timeline.check_numbers(p)  # raises on a digit without provenance
            for pid, rec in p["numbers"].items():
                assert rec["src"] in ("said", "computed", "constant") and rec["v"] is not None, (n, pid)
                if rec["src"] == "said":
                    assert rec["q"], (n, pid)
                if rec["src"] == "computed":
                    assert rec["law"] and rec["inputs"], (n, pid)
            assert ("Illustrative" in p["badges"]) == any(l["illustrative"] for l in p["laws"].values()) or not p["laws"], n


def test_check_numbers_refuses_an_unrecorded_number():
    p = {"overlays": [{"kind": "words", "text": "v = 12 m/s"}], "numbers": {}}
    with pytest.raises(ValueError):
        timeline.check_numbers(p)
    p["overlays"][0]["value"] = "x.v"
    p["numbers"]["x.v"] = {"v": 12}
    timeline.check_numbers(p)
    timeline.check_numbers({"overlays": [{"kind": "words", "text": "“at 12 m/s”", "said": "l1"}], "numbers": {}})


@pytest.mark.parametrize("name", replay.ORDER)
def test_fixture_key_facts(replays, name):
    head, log, patches = replays[name]
    assert replay.check(head, log, patches) == []


# ---------- event log ----------
def test_fold_undo_and_fast_drafts():
    log = EventLog()
    log.say("l1", "A man pushes a box.")
    log.delta([MAN, BOX], "l1")
    assert set(log.fold().ents) == {"man", "box"}
    add_box = next(e.seq for e in log.events if e.op.get("id") == "box")
    log.say("l2", "He pushes it.")
    log.delta([{"op": "act", "id": "p1", "verb": "push", "agent": "man", "obj": "box"}], "l2")
    assert log.fold().actions["p1"].active
    log.undo(add_box)
    g = log.fold()
    assert set(g.ents) == {"man"} and "p1" not in g.actions  # the push used the undone box: skipped
    assert log.fold(upto=add_box + 1).ents.keys() == {"man", "box"}
    # a fast draft counts until the LLM delta of its line replaces it
    log.say("l3", "A ball.")
    log.delta([{"op": "add", "id": "ball", "kind": "prop", "w": "ball"}], "l3", src="fast")
    assert "ball" in log.fold().ents
    log.delta([{"op": "add", "id": "rock", "kind": "prop", "w": "rock"}], "l3", src="llm")
    assert "ball" not in log.fold().ents and "rock" in log.fold().ents
    assert all({"seq", "t_ms", "src", "line_id", "op", "ok"} <= set(e.row()) for e in log.events)


# ---------- director ----------
def test_entities_stay_inside_the_frame(replays):
    for n, (_, _, patches) in replays.items():
        for p in patches:
            if p["view"] == "split":
                continue
            fr = director.Frame(**p["frame"])
            w = director.Where(p)
            for t in w.times(24):
                for i in w.ents:
                    assert director.inside(fr, w.box(i, t), slack=4.0), (n, p["rev"], i, t, fr.screen_box(w.box(i, t)))


def test_labels_do_not_overlap_figures_or_each_other():
    figs = [[[100, 100, 300, 400]], [[120, 100, 320, 400]]]
    out = director.place_labels([{"text": "the box", "at": [[200, 110], [220, 110]]},
                                 {"text": "the man", "at": [[210, 110], [230, 110]]}], figs, [[0, 0, 50, 50]])
    for k in range(2):
        a, b = out[0]["boxes"][k], out[1]["boxes"][k]
        assert not director.overlaps(a, b)
        assert not any(director.overlaps(x, f) for x in (a, b) for f in figs[k])


def test_the_dog_label_is_clear(replays):
    p = replays["dog"][2][-1]
    boxes = p["label_boxes"][0]
    fr, w = director.Frame(**p["frame"]), director.Where(p)
    for k, t in enumerate(w.times(24)):
        assert not any(director.overlaps(boxes[k], fr.screen_box(w.box(i, t))) for i in w.ents)


def test_far_row_is_scaled_and_drawn_behind():
    log = EventLog()
    log.say("l1", "A man stands in front of a tree; behind him is a house.")
    log.delta([MAN, {"op": "add", "id": "house", "kind": "prop", "w": "house"},
               {"op": "relate", "a": "house", "kind": "behind", "b": "man"},
               {"op": "act", "id": "s1", "verb": "stand", "agent": "man"}], "l1")
    p = timeline.build(log.fold())
    e = next(e for e in p["entities"] if e["id"] == "house")
    assert e["xform"]["row"] == "far"
    b = director.Where(p).box("house", 0)
    assert math.isclose(b[2] - b[0], 8.0 * director.FAR, rel_tol=1e-6) and b[1] > 0  # 0.6 scale, up the backdrop


def test_groups_lay_out_left_to_right_with_a_badge_when_enlarged():
    log = EventLog()
    log.say("l1", "A bus and a ball.")
    log.delta([{"op": "add", "id": "bus", "kind": "prop", "w": "bus"}, {"op": "add", "id": "ball", "kind": "prop", "w": "ball"}], "l1")
    p = timeline.build(log.fold())
    xs = {e["id"]: e.get("xform", {}).get("x", 0) for e in p["entities"]}
    assert xs["ball"] > xs["bus"] and "Not to scale" in p["badges"]


def test_dimming_and_entrance_stagger():
    log = EventLog()
    log.say("l1", "A man.")
    log.delta([MAN], "l1")
    p1 = timeline.build(log.fold())
    for i, s in enumerate(["A box.", "A ball.", "A rock.", "A cup."]):
        log.say(f"m{i}", s)
        log.delta([{"op": "add", "id": f"x{i}", "kind": "prop", "w": s.split()[1].rstrip(".").lower()}], f"m{i}")
    p2 = timeline.build(log.fold(), p1)
    ents = {e["id"]: e for e in p2["entities"]}
    assert ents["man"]["xform"].get("dim") and not ents["x3"].get("xform", {}).get("dim")
    assert "enter_ms" not in ents["man"] and sorted(ents[f"x{i}"]["enter_ms"] for i in range(4)) == [0, 100, 200, 300]


def test_frame_avoids_the_slide_no_go_box():
    log = EventLog()
    log.say("l1", "A man walks.")
    log.delta([MAN, {"op": "act", "id": "w", "verb": "walk", "agent": "man", "dir": "right"}], "l1")
    nogo = [[0, 0, 700, 1000]]
    p = timeline.build(log.fold(), nogo=nogo)
    fr, w = director.Frame(**p["frame"]), director.Where(p)
    for t in w.times(12):
        assert fr.screen_box(w.box("man", t))[0] >= 700


# ---------- acting ----------
def test_throw_release_is_the_solver_t0(replays):
    for p in replays["throw"][2]:
        rel = next(e["t"] for t in p["tracks"] if t["kind"] == "clip" for e in t.get("events", []) if e["name"] == "release")
        path = next(t for t in p["tracks"] if t["id"] == "book" and t["kind"] == "path")
        sock = next(t for t in p["tracks"] if t["id"] == "book" and t["kind"] == "socket")
        assert abs(path["samples"][0][0] - rel) <= 1 / 24 and abs(sock["t1"] - rel) <= 1 / 24
        assert abs(rel - ACT.event_t("OverhandThrow", "release")) < 1e-3


def test_warped_push_plays_at_the_box_speed(replays):
    p = replays["push"][2][1]  # harder: the box speeds up, the push clip follows
    segs = [t for t in p["tracks"] if t["id"] == "man" and t["kind"] == "clip"]
    assert len(segs) > 4 and segs[-1]["rate"] > segs[0]["rate"]
    stride = ACT.stride("Push_Loop", "cast:man")
    box = next(t for t in p["tracks"] if t["id"] == "box" and t["kind"] == "path")["samples"]
    for s in segs:
        mid = s["t0"] + 0.125
        a = next(q for q in box if q[0] >= mid - 1e-9)
        b = next(q for q in reversed(box) if q[0] <= mid - 1 / 12 + 1e-9)
        v = (a[1] - b[1]) / (a[0] - b[0])
        assert abs(s["rate"] * stride - v) < 0.03, (s, v)
    # the phase carries over: no pose jump between segments
    for a, b in zip(segs, segs[1:]):
        assert abs(a["t_offset"] + (b["t0"] - a["t0"]) * a["rate"] - b["t_offset"]) < 1e-4


# ---------- timeline ----------
def test_replay_is_deterministic_and_diffs_round_trip(replays):
    import json
    a = replay.replay("seesaw")[2]
    b = replays["seesaw"][2]
    assert json.dumps(a) == json.dumps(b)
    for x, y in zip(b, b[1:]):
        d = timeline.diff(x, y)
        assert timeline.undiff(x, d)["numbers"] == y["numbers"]
        back = timeline.undiff(x, d)
        assert sorted(map(json.dumps, back["tracks"])) == sorted(map(json.dumps, y["tracks"]))
        assert {e["id"]: e for e in back["entities"]} == {e["id"]: e for e in y["entities"]}


# ---------- review regressions (E2 review) ----------
def _logged(ops_, lines):
    log = EventLog()
    for i, line in enumerate(lines):
        log.say(f"l{i}", line)
    log.delta(ops_, f"l{len(lines) - 1}")
    return log


CAR = [{"op": "add", "id": "car", "kind": "prop", "w": "car"}, {"op": "add", "id": "road", "kind": "surface", "w": "road"},
       {"op": "relate", "a": "car", "kind": "on", "b": "road"},
       {"op": "act", "id": "d1", "verb": "move", "agent": "car", "dir": "right"},
       {"op": "law", "id": "am", "name": "accelerated_motion", "roles": {"body": "car"}}]
PUSH = [MAN, BOX, FLOOR, {"op": "relate", "a": "box", "kind": "on", "b": "floor"},
        {"op": "act", "id": "p1", "verb": "push", "agent": "man", "obj": "box", "dir": "right"},
        {"op": "law", "id": "fr", "name": "sliding_friction", "roles": {"body": "box", "surface": "floor", "force_from": "man"}}]


def test_quote_must_be_whole_words_of_a_line():
    d = delta(CAR + [{"op": "given", "law": "am", "sym": "u", "v": 5, "u": "m/s", "q": "5 m/s"}], ["A car moves at 25 m/s."])
    assert "not in the teacher's recent lines" in reasons(d)[0]


def test_signs_and_ranges_are_checked():
    rs = reasons(delta(PUSH + [{"op": "given", "law": "fr", "sym": "mu_k", "v": -0.3, "u": "", "q": "mu is 0.3"},
                               {"op": "given", "law": "fr", "sym": "mu_k", "v": 3, "u": "", "q": "mu is 3"}],
                       ["A man pushes a box; mu is 0.3, no, mu is 3."]))
    assert "no minus sign" in rs[0] and "out of range" in rs[1]
    d = delta(CAR + [{"op": "given", "law": "am", "sym": "a", "v": -2, "u": "m/s^2", "q": "2 m/s^2"},
                     {"op": "given", "law": "am", "sym": "a", "v": -2, "u": "m/s^2", "q": "slows down at 2 m/s^2"}],
              ["A car moves; it speeds up at 2 m/s^2, then slows down at 2 m/s^2."])
    assert len(reasons(d)) == 1 and "no minus sign" in reasons(d)[0]
    sw = [{"op": "add", "id": "girl", "kind": "agent", "w": "girl"}, {"op": "add", "id": "swing", "kind": "prop", "w": "swing"},
          {"op": "relate", "a": "girl", "kind": "sitting_on", "b": "swing"},
          {"op": "law", "id": "pe", "name": "pendulum_energy", "roles": {"bob": "girl", "pivot": "swing"}},
          {"op": "given", "law": "pe", "sym": "theta0", "v": 0, "u": "deg", "q": "at 0 degrees"}]
    assert "out of range" in reasons(delta(sw, ["A girl on a swing starts at 0 degrees."]))[0]


def test_a_quote_unit_of_another_dimension_is_refused_not_raised():
    pr = [{"op": "add", "id": "ball", "kind": "prop", "w": "ball"},
          {"op": "law", "id": "pr", "name": "projectile", "roles": {"body": "ball"}},
          {"op": "given", "law": "pr", "sym": "v0", "v": 30, "u": "m/s", "q": "at 10 m/s at 30 degrees"}]
    d = delta(pr, ["A ball is thrown at 10 m/s at 30 degrees."])
    assert d.rejected and "the quote says" in reasons(d)[-1]


def test_ids_share_one_namespace():
    d = delta([MAN, BOX, {"op": "act", "id": "p1", "verb": "push", "agent": "man", "obj": "box"},
               {"op": "act", "id": "p1", "verb": "push", "agent": "man", "obj": "box", "manner": "hard"},
               {"op": "add", "id": "p1", "kind": "prop", "w": "ball"},
               {"op": "law", "id": "p1", "name": "uniform_motion", "roles": {"body": "box"}}])
    rs = reasons(d)
    assert len(rs) == 3 and "action id" in rs[0] and "already used" in rs[1] and "bad law id" in rs[2]


RAIN_MAN = [{"op": "add", "id": "rain", "kind": "prop", "w": "rain"}, MAN,
            {"op": "act", "id": "f1", "verb": "fall", "agent": "rain", "dir": "down"},
            {"op": "act", "id": "w1", "verb": "walk", "agent": "man", "dir": "right"}]


def test_relative_motion_follows_the_roles():
    """roles a = the man, b = the rain: the man's said speed is va; θ is still atan(v_man / v_rain)."""
    ops_ = RAIN_MAN + [{"op": "law", "id": "rm", "name": "relative_motion", "roles": {"a": "man", "b": "rain", "observer": "man"}},
                       {"op": "given", "law": "rm", "sym": "va", "v": 1.5, "u": "m/s", "q": "walks at 1.5 m/s"},
                       {"op": "given", "law": "rm", "sym": "vb", "v": 6, "u": "m/s", "q": "falling at 6 m/s"}]
    log = _logged(ops_, ["Rain falling at 6 m/s on a man who walks at 1.5 m/s."])
    p = timeline.build(log.fold())
    assert math.isclose(p["numbers"]["rm.theta"]["v"], math.degrees(math.atan(1.5 / 6)), rel_tol=1e-3)
    assert next(e for e in p["entities"] if e["id"] == "rain")["state"]["speed"] == 6.0
    card = next(o for o in p["overlays"] if o.get("title") == "Rain seen by the walker")
    assert any(row[0] == "v_m" and "1.5" in row[1] for row in card["rows"])


def test_a_walker_standing_still_does_not_crash():
    ops_ = RAIN_MAN[:3] + [
        {"op": "law", "id": "rm", "name": "relative_motion", "roles": {"a": "rain", "b": "man", "observer": "man"}},
        {"op": "given", "law": "rm", "sym": "vb", "v": 0, "u": "m/s", "q": "stands still"}]
    p = timeline.build(_logged(ops_, ["Rain falls on a man who stands still."]).fold())
    man = next(t for t in p["tracks"] if t["id"] == "man" and t["kind"] == "path")["samples"]
    assert man[0][1] == man[-1][1]  # he stays where he is


def test_accelerated_motion_that_stops_before_s_prints_no_time():
    r = LAWS["accelerated_motion"].solve("a", G(u=(10.0, "m/s"), a=(-2.0, "m/s^2"), s=(30.0, "m")), {})
    assert r.facts["stops_before"] and "t" not in r.printable() and "v" not in r.printable()
    assert math.isclose(r.nums["s_stop"].v, 25.0)
    r = LAWS["accelerated_motion"].solve("a", G(u=(10.0, "m/s"), a=(-2.0, "m/s^2"), s=(16.0, "m")), {})
    assert math.isclose(r.nums["t"].v, 2.0) and math.isclose(r.nums["v"].v, 6.0)


def test_balance_follows_the_latest_line_and_negation():
    assert timeline.balance_asked(["Where must she sit to balance?"])
    assert not timeline.balance_asked(["Where must she sit to balance?", "Now it does not balance."])
    assert not timeline.balance_asked(["The seesaw is unbalanced."]) and not timeline.balance_asked(["A seesaw."])


def test_a_said_push_decides_the_caption():
    ops_ = PUSH + [{"op": "given", "law": "fr", "sym": "F", "v": 100, "u": "N", "q": "with 100 N"},
                   {"op": "given", "law": "fr", "sym": "m", "v": 30, "u": "kg", "q": "is 30 kg"},
                   {"op": "given", "law": "fr", "sym": "mu_k", "v": 0.5, "u": "", "q": "mu is 0.5"}]
    p = timeline.build(_logged(ops_, ["A man pushes the box with 100 N; the box is 30 kg and mu is 0.5."]).fold())
    card = next(o for o in p["overlays"] if o.get("title") == "Friction")
    assert card["lines"] == ["F < f: the box slows down"] and p["numbers"]["fr.a"]["v"] < 0


def test_a_late_llm_delta_keeps_later_lines():
    log = EventLog()
    log.say("l1", "A man.")
    log.delta([MAN], "l1", src="fast")
    log.say("l2", "He walks.")
    log.delta([{"op": "act", "id": "w1", "verb": "walk", "agent": "man", "dir": "right"}], "l2")
    log.delta([MAN], "l1", src="llm")  # the LLM's delta for line 1 arrives after line 2
    g = log.fold()
    assert "man" in g.ents and g.actions["w1"].active


def test_removing_a_law_role_and_digit_labels_do_not_crash():
    log = _logged(PUSH + [{"op": "label", "id": "box", "text": "Box 2"}], ["A man pushes Box 2."])
    p = timeline.build(log.fold())
    assert any(o.get("text") == "Box 2" and o.get("said") for o in p["overlays"])
    log.say("l9", "Take the box away.")
    log.delta([{"op": "remove", "id": "box"}], "l9")
    g = log.fold()
    assert "fr" not in g.laws
    timeline.build(g)


def test_a_title_band_keeps_height_not_width():
    fr = director.fit([[-1, 0, 1, 1.8]], nogo=[[100, 40, 1500, 140]])
    assert fr.screen_box([-1, 0, 1, 1.8])[1] >= 150 and fr.s > 200


def test_diff_round_trips_every_key_and_the_order(replays):
    for n in replay.ORDER:
        ps = replays[n][2]
        for a, b in zip(ps, ps[1:]):
            back = timeline.undiff(a, timeline.diff(a, b))
            assert back == b and [e["id"] for e in back["entities"]] == [e["id"] for e in b["entities"]], n
