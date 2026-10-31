"""F-019 M1: said quantities on the open diagram (`qty`: validator, attachment, latest wins) and the contact-mechanics
solver against hand-worked answers (each fixture's `about` and the docstrings below), plus the patch's arrows, values
panel and tracks. Every number on the slide is said (its quote is in the lines) or computed (from known inputs).
0 tokens."""
import json
import math
from pathlib import Path

import pytest

from copilot.diagram import fastpath, mech, patch
from copilot.diagram.graph import DiagramLog
from copilot.diagram.solvers import run
from copilot.diagram.solvers.contact import _regime

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "diagram"
M1 = sorted(p.stem for p in FIX.glob("m1_*.json"))
G = 9.8


def say(lines):
    """Each line through the fast path and the validator (as the stage does), yielding (log, line dict, draft)."""
    log = DiagramLog()
    for k, ln in enumerate(lines):
        text = ln["say"] if isinstance(ln, dict) else ln
        log.say(f"l{k}", text)
        d = fastpath.draft(text, log.fold())
        res = log.delta(d.ops, f"l{k}", "fast", text=text)
        assert not [r for r in res.rejected if r[0].get("op") == "qty"], res.rejected
        yield log, ln, d


def values(res):
    return {f"{v.on}:{v.sym}": v for v in res.values}


@pytest.mark.parametrize("name", M1)
def test_fixture(name):
    fx = json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))
    assert fx["lines"]
    for log, ln, d in say(fx["lines"]):
        exp = ln.get("expect")
        if not exp:
            continue
        g = log.fold()
        for key, v in exp.get("qty", {}).items():
            on, sym = key.split(":")
            assert g.value(on, sym) is not None, (ln["say"], key, g.qty)
            assert math.isclose(g.value(on, sym)["v"], v, abs_tol=1e-9), (key, g.value(on, sym))
        if "qty" in exp and not exp["qty"]:
            assert not d.ops or not [o for o in d.ops if o["op"] == "qty"], d.ops
        for key, note in exp.get("note", {}).items():
            assert g.value(*key.split(":"))["note"] == note
        for key, way in exp.get("dir", {}).items():
            assert g.value(*key.split(":"))["dir"] == way
        for a, (rel, b) in exp.get("rels", {}).items():
            assert g.rels.get(a) == (rel, b), (a, g.rels)
        res = run(g)
        assert res is not None, ln["say"]
        vals = values(res)
        for key, v in exp.get("values", {}).items():
            assert key in vals and vals[key].known, (ln["say"], key, {k: x.text() for k, x in vals.items()})
            assert math.isclose(vals[key].v, v, rel_tol=1e-6, abs_tol=1e-9), (key, vals[key].v, v)
        for key in exp.get("symbols", []):
            assert key in vals and not vals[key].known, (key, vals.get(key))
        states = {m.on: m for m in res.motions}
        for on, st in exp.get("motions", {}).items():
            assert states[on].state == st, (on, states[on])
        for on, ang in exp.get("motion_ang", {}).items():
            assert math.isclose(states[on].ang, ang, abs_tol=1e-9), (on, states[on])
        for words in exp.get("notes", []):
            assert any(words in n for n in res.notes), (words, res.notes)
        _provenance(log, g)


def _provenance(log, g):
    """No number without a source: every value on the slide is said (quote in the recent lines, the number in it),
    computed from known inputs (with its equation) or the constant g; a symbol prints no number."""
    p = patch.build(g)
    lines = " ".join(log.recent()).lower()
    res = run(g)
    for v in res.values:
        if v.src == "said":
            assert v.q and v.q.lower() in lines, (v, lines)
        elif v.src == "computed":
            assert v.known and v.frm and v.eq, v
        elif v.src == "symbol":
            assert v.v is None and v.text() == v.sym
        else:
            assert v.src == "constant" and v.sym == "g" and v.v == 9.8
    texts = {f"{v.on}:{v.text()}" for v in res.values} | {v.text() for v in res.values}
    for a in p["mech"]["forces"]:
        assert a["text"] in texts, a
        assert (a["src"] == "symbol") == ("=" not in a["text"])
    for r in p["mech"]["panel"]["rows"] if p["mech"]["panel"] else []:
        if r["kind"] == "value":
            assert r["text"] in texts and (r["src"] != "said" or r["sub"].startswith("said:")), r


# ---- the solver alone: textbook answers -----------------------------------------------------------------------------
def test_regime_two_blocks_threshold():
    """Two blocks (top 2 kg on bottom 3 kg, μ 0.4 between, frictionless floor), F on the bottom block. The top block can
    accelerate at most μg = 3.92 m/s², so the pair moves together while F/(5 kg) ≤ 3.92, i.e. F ≤ 19.6 N."""
    m, N = [3.0, 2.0], [5 * G, 2 * G]
    mus = muk = [0.0, 0.4]
    sup = [-1, 0]
    for F, together in ((19.0, True), (20.5, False)):
        sols = []
        for st in (("slip+", "stick"), ("slip+", "slip-"), ("slip+", "slip+")):
            s = _regime(st, [F, 0.0], m, N, mus, muk, sup)
            if s:
                sols.append((st, s))
        assert sols
        st, (a, f) = sols[0]
        assert (st[1] == "stick") == together, (F, st)
        if together:
            assert math.isclose(a[0], F / 5) and math.isclose(a[1], F / 5)
        else:
            assert math.isclose(a[1], 0.4 * G) and math.isclose(a[0], (F - 0.4 * 2 * G) / 3)


def test_incline_no_push_slides_or_holds():
    """No push: a = g(sin θ − μ cos θ) when tan θ > μ, else it stays (f = mg sin θ)."""
    for deg, mu in ((30, 0.3), (30, 0.7)):
        lines = [f"Imagine a block on an inclined plane at {deg} degrees.", "The mass of the block is 2 kg.",
                 f"The coefficient of friction is {mu}."]
        *_, (log, _, _) = list(say(lines))
        v = values(run(log.fold()))
        th = math.radians(deg)
        if math.tan(th) > mu:
            assert math.isclose(v["block:a"].v, G * (math.sin(th) - mu * math.cos(th)), rel_tol=1e-9)
        else:
            assert v["block:a"].v == 0 and math.isclose(v["block:f"].v, 2 * G * math.sin(th), rel_tol=1e-9)


def test_unattached_value_is_logged_not_guessed():
    """Two bodies and "the coefficient of friction is 0.4" with no surface said: two contacts, so no guess."""
    *_, (log, _, d) = list(say(["Imagine two blocks, one on top of the other, on the floor.",
                                "The coefficient of friction is 0.4."]))
    assert d.unattached == [("mu", "coefficient of friction is 0.4")]
    assert not log.fold().qty


def test_validator_refuses_unsaid_or_unconverted():
    log = DiagramLog()
    log.say("l0", "Imagine a block on the floor.")
    log.delta(fastpath.draft("Imagine a block on the floor.").ops, "l0")
    log.say("l1", "The block is 500 grams.")
    bad = [{"op": "qty", "on": "block", "sym": "m", "v": 500, "u": "kg", "q": "500 grams"},      # not converted
           {"op": "qty", "on": "block", "sym": "m", "v": 7, "u": "kg", "q": "7 kg"},             # not said
           {"op": "qty", "on": "floor", "sym": "m", "v": 0.5, "u": "kg", "q": "500 grams"},      # not a body
           {"op": "qty", "on": "block", "sym": "F", "v": 0.5, "u": "N", "q": "500 grams"}]       # not a force
    ok = {"op": "qty", "on": "block", "sym": "m", "v": 0.5, "u": "kg", "q": "500 grams"}
    d = log.delta(bad + [ok], "l1", "llm")
    assert len(d.rejected) == 4 and len(d.ok) == 1, d.rejected


def test_latest_value_wins_and_old_is_logged():
    *_, (log, _, _) = list(say(["Imagine a block on the floor.", "The block is 10 kg.", "No, the block is 12 kg."]))
    assert log.fold().value("block", "m")["v"] == 12.0
    assert [e.op.v for e in log.events if e.ok and getattr(e.op, "op", "") == "qty"] == [10.0, 12.0]


def test_patch_arrows_panel_tracks():
    lines = json.loads((FIX / "m1_incline_full.json").read_text(encoding="utf-8"))["lines"][:4]
    *_, (log, _, _) = list(say(lines))
    p = patch.build(log.fold())
    kinds = {a["kind"]: a for a in p["mech"]["forces"]}
    assert set(kinds) == {"weight", "normal", "friction", "applied"}
    w = kinds["weight"]
    assert w["x2"] == w["x1"] and w["y2"] > w["y1"] and w["text"] == "W = 49 N"   # straight down
    nx, ny = kinds["normal"]["x2"] - kinds["normal"]["x1"], kinds["normal"]["y2"] - kinds["normal"]["y1"]
    assert nx > 0 and ny < 0                                                        # up and out of the slope
    fx_, fy = kinds["friction"]["x2"] - kinds["friction"]["x1"], kinds["friction"]["y2"] - kinds["friction"]["y1"]
    assert fx_ < 0 and fy < 0 and kinds["friction"]["text"] == "f = 12.7 N"        # up the slope (it slides down)
    slide = [t for t in p["tracks"] if t["kind"] == "slide"]
    assert len(slide) == 1 and slide[0]["ux"] > 0 and slide[0]["uy"] > 0           # down the slope
    rows = [r["text"] for r in p["mech"]["panel"]["rows"]]
    assert "m = 5 kg" in rows and "a = 1.35 m/s²" in rows and "not simulated" not in p["badges"]
    panel_x = p["mech"]["panel"]["x"]
    assert all(q["cx"] + q["w"] / 2 <= panel_x + 1 for q in p["parts"]), "the picture keeps clear of the panel"


def test_not_simulated_badge_only_for_mechanics():
    *_, (log, _, _) = list(say(["Imagine a spring.", "The spring constant is 100 newtons per metre."]))
    p = patch.build(log.fold())
    assert "not simulated" in p["badges"] and not p["mech"]["forces"]
    for line in ("Imagine a beaker on a table.", "Imagine a lamp hanging from the ceiling.", "Imagine a spring."):
        *_, (log, _, _) = list(say([line]))
        assert "not simulated" not in patch.build(log.fold())["badges"], line


# ---- review findings (M1 phase A): each input put a wrong or unsourced number on the slide ---------------------------
def _final(lines):
    *_, (log, _, d) = list(say(lines))
    return log.fold(), d


def test_table_case_in_either_word_order():
    """m_h = 1, m_t = 4, frictionless: a = 1.96, T = 7.84, whichever body is said first."""
    g, _ = _final(["Imagine a hanging mass connected by a rope over a pulley to a block on a table.",
                   "The block on the table is 4 kg and the hanging mass is 1 kg.", "The table is frictionless."])
    v = values(run(g))
    assert math.isclose(v[":a"].v, 1.96) and math.isclose(v[":T"].v, 7.84)


def test_rope_systems_not_solved_stay_symbols():
    for lines in (["Imagine a block on a table connected by a rope over a pulley to a hanging mass.",
                   "The block on the table is 4 kg and the hanging mass is 1 kg.", "The table is frictionless.",
                   "We pull the block to the left with 30 newtons."],
                  ["Imagine a block on an inclined plane connected by a rope over a pulley to a hanging mass."]):
        g, _ = _final(lines)
        res = run(g)
        assert not [x for x in res.values if x.sym in ("a", "T") and x.known], [x.text() for x in res.values]
        assert any("not solved" in n for n in res.notes), res.notes


@pytest.mark.parametrize("line", ["The friction is one hundred newtons.", "The friction force is 2 point 5 N.",
                                  "The frictional force of twenty five newtons.", "Friction of five hundred grams.",
                                  "The floor is not smooth.", "It is not a frictionless surface."])
def test_no_mu_from_forces_cut_numbers_or_negations(line):
    from copilot.diagram.quantities import found
    assert not [s for s in found(line) if s.sym.startswith("mu")], found(line)


def test_long_friction_phrase_and_push_after_friction():
    from copilot.diagram.quantities import found
    s = found("The coefficient of friction between the block and the floor is 0.3.")
    assert [(x.sym, x.v) for x in s] == [("mu", 0.3)]
    s = found("The floor is frictionless and we push it with 10 newtons.")
    assert [(x.sym, x.v) for x in s] == [("mu", 0.0), ("F", 10.0)]


def test_angle_outside_the_drawn_range_is_refused():
    """80°: the layout draws 3–75° only; a solver run at 80° on a slope drawn at 30° would mislead."""
    log = DiagramLog()
    for k, t in enumerate(["Imagine a box on an inclined plane.", "The angle is 80 degrees."]):
        log.say(f"l{k}", t)
        res = log.delta(fastpath.draft(t, log.fold()).ops, f"l{k}", "fast", text=t)
    assert log.fold().value("inclined_plane", "theta") is None
    assert any("not drawn" in why for raw, why in res.rejected if raw.get("op") == "qty")


def test_push_on_a_slope_with_no_angle_draws_no_friction_direction():
    g, _ = _final(["Imagine a block on an inclined plane.", "The mass of the block is 1 kg.",
                   "We push it up the slope with 5 newtons."])
    assert not [f for f in run(g).forces if f.kind == "friction"]
    g, _ = _final(["Imagine a block on an inclined plane.", "The mass of the block is 1 kg."])
    fr = [f for f in run(g).forces if f.kind == "friction"]
    assert len(fr) == 1 and math.isclose(fr[0].ang % 360, 210.0)  # no push: up the (drawn 30°) slope


def test_said_stack_order_stands():
    """The first block said ("a small block") is the one stacked on the second."""
    g, _ = _final(["Imagine a small block stacked on a big block on the floor."])
    assert g.rels["block"] == ("on", "block2") and g.rels["block2"] == ("on", "floor"), g.rels


def test_test40_repeat_adds_no_second_mass():
    *_, (log, _, _) = list(say([{"say": "Imagine a spring with a mass hanging from it."},
                                {"say": "Imagine a spring with a hanging mass."}]))
    assert [p.kind for p in log.fold().parts.values()].count("mass") == 1


def test_test40_atwood_heads_name_the_said_masses():
    lines = json.loads((FIX / "m1_atwood.json").read_text(encoding="utf-8"))["lines"]
    *_, (log, _, _) = list(say(lines))
    heads = [r["text"] for r in patch.build(log.fold())["mech"]["panel"]["rows"] if r["kind"] == "head"]
    assert len(set(heads)) == len(heads) == 2, heads


def test_test40_label_never_runs_under_the_panel():
    for name in M1:
        *_, (log, _, _) = list(say(json.loads((FIX / f"{name}.json").read_text(encoding="utf-8"))["lines"]))
        p = patch.build(log.fold())
        if not p["mech"]["panel"]:
            continue
        for a in p["mech"]["forces"]:
            if a["anchor"] == "start":
                assert a["lx"] + mech.LABEL_W * len(a["text"]) <= p["mech"]["panel"]["x"], (name, a["text"])


def test_test41_plural_bottom_blocks_is_the_bottom_block():
    *_, (log, _, _) = list(say(["Imagine two blocks, one on top of the other on the floor.",
                                "We apply 50N on the bottom blocks."]))
    assert log.fold().value("block", "F")["v"] == 50.0


def test_test41_panel_fits_the_slide_and_masses_are_written_in_the_bodies():
    from copilot.diagram.layout import VIEW
    lines = json.loads((FIX / "m1_two_blocks_slip.json").read_text(encoding="utf-8"))["lines"]
    *_, (log, _, _) = list(say(lines))
    m = patch.build(log.fold())["mech"]
    pn = m["panel"]
    assert pn["y"] + mech._height(pn, m["notes"]) * pn["scale"] <= VIEW[1] - 16
    assert any(r["text"] == "a = 3.92 m/s²" for r in pn["rows"])
    assert {(k["on"], k["text"]) for k in m["marks"]} == {("block", "3 kg"), ("block2", "2 kg")}
