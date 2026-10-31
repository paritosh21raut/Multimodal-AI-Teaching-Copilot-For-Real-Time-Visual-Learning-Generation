"""F-018 K1 diagram core: the validator (closed kinds, ids, counts, quotes, labels), the fast path on the 12 fixtures
(op scripts), and the layout's contact rules (ON the slope, IN the beaker, hung FROM the spring end, orbits in order),
labels clear of every part and of each other. 0 tokens."""
import json
import math
from pathlib import Path

import pytest

from copilot.diagram import fastpath, patch
from copilot.diagram.route import route
from copilot.diagram.graph import DiagramLog
from copilot.diagram.layout import VIEW, crosses_ring, field_lines, solve
from copilot.presentation.stage import _title_nogo

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "tests" / "fixtures" / "diagram"
IDS = ["d1", "d2", "d3", "d4", "d5", "d9", "d10", "x1", "x2", "x3", "x4", "x5"]


def fixture(i):
    return json.loads((FIX / f"k1_{i}.json").read_text(encoding="utf-8"))


def build(i):
    """The fixture's op script through the validator into a graph (the said lines are the quotes' context)."""
    log = DiagramLog()
    for k, ln in enumerate(fixture(i)["lines"]):
        log.say(f"l{k}", ln["line"])
        d = log.delta(ln["ops"], f"l{k}", "fast", text=ln["line"])
        assert not d.rejected, d.rejected
    return log.fold()


def check(raws, *lines, src="llm"):
    log = DiagramLog()
    for k, ln in enumerate(lines):
        log.say(f"l{k}", ln)
    return log.delta(raws, "lx", src, text=lines[-1] if lines else "")


# ---- validator ------------------------------------------------------------------------------------------------------
def test_unknown_kinds_ids_relations_and_schema_are_refused_with_reasons():
    d = check([{"op": "part", "id": "x", "kind": "spaceship"},
               {"op": "part", "id": "b", "kind": "beaker"},
               {"op": "place", "a": "b", "rel": "inside_of", "b": "b"},
               {"op": "place", "a": "ghost", "rel": "on", "b": "b"},
               {"op": "part", "id": "b", "kind": "block"},
               {"op": "part", "id": "c", "kind": "block", "x": 10},
               {"op": "contain", "a": "c2", "b": "b"}], "a beaker")
    why = [r for _, r in d.rejected]
    assert len(d.ok) == 1 and len(why) == 6
    assert "unknown part kind 'spaceship'" in why[0] and "unknown relation" in why[1] and why[2] == "unknown id"
    assert "exists" in why[3] and why[4].startswith("schema") and why[5] == "unknown id"


def test_in_needs_a_container_hang_needs_an_end_and_no_cycles():
    d = check([{"op": "part", "id": "box", "kind": "block"}, {"op": "part", "id": "c", "kind": "circle"},
               {"op": "place", "a": "c", "rel": "in", "b": "box"},
               {"op": "place", "a": "c", "rel": "hang_from", "b": "box"},
               {"op": "place", "a": "box", "rel": "on", "b": "c"},
               {"op": "place", "a": "c", "rel": "on", "b": "box"}], "x")
    why = [r for _, r in d.rejected]
    assert why == ["block holds nothing", "block has no end to hang from", "a placement cycle"]


def test_a_said_count_is_drawn_exactly():
    line = "Imagine two circles, C1 and C2."
    three = [{"op": "part", "id": f"c{i}", "kind": "circle"} for i in (1, 2, 3)] + [
        {"op": "place", "a": "c3", "rel": "beside", "b": "c1"}]
    d = check(three, line)
    assert [o.id for o in d.ok if o.op == "part"] == ["c1", "c2"]
    assert any("said 2 circle" in r for _, r in d.rejected) and any("refused part" in r for _, r in d.rejected)
    d = check(three[:1], line)
    assert any("only 1 given" in r for _, r in d.rejected)
    assert len(fastpath.draft("Imagine ten resistors in series with a cell.").ops) == 10 + 1 + 1


def test_numbers_need_their_quote_and_unit():
    line = "A box on an incline at an angle of 30 degrees."
    ok = {"op": "given", "sym": "theta", "v": 30, "u": "deg", "q": "an angle of 30 degrees"}
    assert check([ok], line).ok
    bad = [dict(ok, v=35), dict(ok, q="an angle of 45 degrees"), dict(ok, u="kg"), dict(ok, sym="speed"),
           {"op": "given", "sym": "m", "v": 30, "u": "kg", "q": "an angle of 30 degrees"}]
    why = [r for _, r in check(bad, line).rejected]
    assert len(why) == 5
    assert "not said in the quote" in why[0] and "not in the teacher" in why[1] and "takes deg" in why[2]
    assert "no given 'speed'" in why[3] and "needs kg" in why[4]


def test_labels_are_said_auto_within_the_count_or_the_fast_paths_table_names():
    auto = {"label_src": "auto"}
    d = check([{"op": "part", "id": "a", "kind": "circle", "label": "C1"},
               {"op": "part", "id": "b", "kind": "circle", "label": "C9"},
               {"op": "part", "id": "r1", "kind": "resistor", "label": "R1", "attr": auto},
               {"op": "part", "id": "r2", "kind": "resistor", "label": "R2", "attr": auto},
               {"op": "part", "id": "r9", "kind": "resistor", "label": "R9", "attr": auto},
               {"op": "part", "id": "q", "kind": "planet", "label": "Mars", "attr": {"label_src": "table", "name": "Mars"}}],
              "two circles C1 and C2")
    assert [o.id for o in d.ok] == ["a", "r1", "r2"]   # C9 not said, R9 beyond 3, a table name only from the tables
    why = [r for _, r in d.rejected]
    assert "beyond" in why[1] and "fast path" in why[2]
    d = check([{"op": "part", "id": "q", "kind": "planet", "label": "Mars", "attr": {"label_src": "table", "name": "Mars"}},
               {"op": "part", "id": "v", "kind": "planet", "label": "Vulcan", "attr": {"label_src": "table", "name": "Vulcan"}}],
              "planets", src="fast")
    assert [o.id for o in d.ok] == ["q"]


def test_review_attrs_are_whitelisted_and_ids_checked_without_a_crash():
    d = check([{"op": "part", "id": "b", "kind": "beaker"}, {"op": "part", "id": "w", "kind": "liquid", "attr": {"fill": 3.0}},
               {"op": "part", "id": "s", "kind": "switch", "attr": {"state": "half"}},
               {"op": "part", "id": "r1", "kind": "resistor"}, {"op": "part", "id": "r2", "kind": "resistor"},
               {"op": "group", "id": "par", "mode": "parallel", "items": ["r1", "r2"]},
               {"op": "contain", "a": "par", "b": "r1"}, {"op": "contain", "a": "r1.2", "b": "b"},
               {"op": "given", "sym": "m", "v": 2, "u": "kg", "q": "2 kg", "on": "nope"}], "a 2 kg mass")
    why = [r for _, r in d.rejected]
    assert "attribute 'fill'" in why[0] and "state='half'" in why[1] and why[2:] == ["unknown id"] * 3


def test_review_measures_are_not_counts_and_everyday_words_are_not_parts():
    kinds = lambda t: [o["kind"] for o in fastpath.draft(t).ops if o["op"] == "part"]  # noqa: E731
    assert kinds("Imagine a 5 kg block on an inclined plane at 30 degrees.") == ["block", "incline"]
    assert kinds("Imagine a 10 ohm resistor connected to a cell.") == ["resistor", "cell"]
    assert kinds("Imagine a block of mass 2 kg on a table.") == ["block", "floor"]
    for t in ("Imagine a spring morning.", "Imagine a switch from coal to gas.", "Imagine a mass of air.",
              "Imagine a cell membrane.", "Consider the cell."):
        assert route(t) is None, t
    log = DiagramLog()
    for k, t in enumerate(("Imagine in a beaker you have HCl.", "So the HCl undergoes a reaction and gives a precipitate.",
                           "Now a third circle.")):
        log.say(f"l{k}", t)
        log.delta(fastpath.draft(t, log.fold()).ops, f"l{k}", "fast", text=t)
    assert not log.fold().of("unknown")


def test_review_relations_it_passive_pour_and_circuits_said_later():
    g = build_lines("Imagine a spring hanging from the ceiling with a mass attached to it.")
    assert g.rels["mass"] == ("hang_from", "spring") and g.rels["spring"] == ("hang_from", "support")
    g = build_lines("Imagine a beaker.", "HCl is slowly added to the water in the beaker.")
    assert {(p.kind, p.label) for p in g.parts.values()} >= {("pourer", "HCl"), ("liquid", "water")}
    g = build_lines("Imagine a cell, a bulb and a switch.", "Now add two resistors in parallel.")
    assert g.groups["loop"][1] == ["cell", "bulb", "switch", "par"]
    g = build_lines("Imagine two resistors in parallel.")
    p = patch.build(g)
    assert len([o for o in p["overlays"] if o["kind"] == "node"]) >= 2  # two terminals, no closed loop
    g = build_lines("Imagine a bar magnet and a compass.")
    L = solve(g)
    c, m = L.nodes["compass"], L.nodes["bar_magnet"]
    assert c.cx > m.cx and abs(c.attr["needle"]) < 1  # on the N side the field points away from N


def build_lines(*lines):
    log = DiagramLog()
    for k, t in enumerate(lines):
        log.say(f"l{k}", t)
        d = log.delta(fastpath.draft(t, log.fold()).ops, f"l{k}", "fast", text=t)
        assert not d.rejected, d.rejected
    return log.fold()


def test_an_llm_delta_keeps_the_op_budget_the_fast_path_expands_tables():
    many = [{"op": "part", "id": f"r{i}", "kind": "resistor"} for i in range(20)]
    assert len(check(many, "resistors").ok) == 16
    assert len(check(many, "resistors", src="fast").ok) == 20
    log = DiagramLog()
    log.say("l1", "Imagine our solar system.")
    d = fastpath.draft("Imagine our solar system.")
    assert len(log.delta(d.ops, "l1", "fast", text="Imagine our solar system.").ok) == 17


# ---- fast path: the 12 fixtures are its op scripts -------------------------------------------------------------------
@pytest.mark.parametrize("i", IDS)
def test_fast_path_reproduces_each_fixture_op_script(i):
    log = DiagramLog()
    for k, ln in enumerate(fixture(i)["lines"]):
        log.say(f"l{k}", ln["line"])
        d = fastpath.draft(ln["line"], log.fold())
        assert d.ops == ln["ops"], (ln["line"], d.ops)
        log.delta(d.ops, f"l{k}", "fast", text=ln["line"])


def test_follow_up_lines_refer_to_the_open_diagram_and_a_new_line_does_not():
    log = DiagramLog()
    log.say("l1", "Imagine in a beaker you have HCL.")
    log.delta(fastpath.draft("Imagine in a beaker you have HCL.").ops, "l1", "fast", text="x")
    g = log.fold()
    assert fastpath.draft("and you're adding water to it slowly", g).refers
    assert fastpath.draft("Now stir the beaker.", g).old == ["beaker"]
    assert not fastpath.draft("Imagine a spring with a mass hanging from it.", g).refers
    assert not fastpath.draft("Imagine a bar magnet and its field.", g).refers


# ---- layout ---------------------------------------------------------------------------------------------------------
def lay(i):
    g = build(i)
    return g, solve(g, _title_nogo(fixture(i)["title"]))


def overlap(a, b, pad=0.0):
    return a[0] < b[2] - pad and b[0] < a[2] - pad and a[1] < b[3] - pad and b[1] < a[3] - pad


def test_d1_the_box_sits_on_the_slope_surface_along_it_and_the_angle_is_marked():
    g, L = lay("d1")
    box, inc = L.nodes["box"], L.nodes["inclined_plane"]
    th = math.radians(inc.attr["theta"])
    top, low = (inc.cx - inc.w / 2, inc.cy - inc.h / 2), (inc.cx + inc.w / 2, inc.cy + inc.h / 2)

    def above(p):  # signed distance from the slope line (positive: outside the wedge)
        return (p[0] - low[0]) * math.sin(th) - (p[1] - low[1]) * math.cos(th)
    bl, br = box.at(0, 1), box.at(1, 1)
    assert abs(above(bl)) <= 1 and abs(above(br)) <= 1          # both bottom corners on the slope (contact, no gap)
    assert all(above(c) >= -1 for c in box.corners())           # nothing sunk into the wedge
    assert top[0] < bl[0] < low[0] and top[0] < br[0] < low[0]  # within the slope, not beside the triangle
    assert math.isclose(box.rot, inc.attr["theta"])
    assert [o["text"] for o in L.overlays if o["kind"] == "angle"] == ["θ"] and "Illustrative angle" in L.badges


def test_d1_a_said_angle_is_printed_with_its_quote():
    log = DiagramLog()
    line = "Imagine a box on an incline at an angle of 30 degrees."
    log.say("l1", line)
    log.delta(fastpath.draft(line).ops, "l1", "fast", text=line)
    p = patch.build(log.fold())
    assert [o["text"] for o in p["overlays"] if o["kind"] == "angle"] == ["θ = 30°"]
    assert p["givens"]["theta"]["q"] == "an angle of 30 degrees" and "Illustrative angle" not in p["badges"]


def test_d4_the_liquid_is_in_the_beaker_and_the_water_pours_onto_it():
    g, L = lay("d4")
    b, liq, pour = L.nodes["beaker"], L.nodes["hcl"], L.nodes["water"]
    bx = b.box()
    assert bx[1] < liq.attr["level"] < liq.attr["floor"] <= bx[3]
    assert bx[0] <= liq.box()[0] and liq.box()[2] <= bx[2]
    stream = next(w for w in L.wires if w["kind"] == "stream")
    assert math.isclose(stream["pts"][-1][1], liq.attr["level"]) and bx[0] < stream["pts"][-1][0] < bx[2]
    assert not overlap(pour.box(), bx)                          # the pourer is over the beaker, not in it
    assert {p.kind for p in g.parts.values()} == {"beaker", "liquid", "pourer"}  # no person, no ground


def test_d10_the_mass_hangs_from_the_spring_end_and_the_spring_from_its_support():
    g, L = lay("d10")
    s, m, sup = L.nodes["spring"], L.nodes["mass"], L.nodes["support"]
    assert math.dist(s.anchor("end"), m.anchor("top")) <= 1
    assert math.dist(sup.anchor("end"), s.anchor("top")) <= 1


def test_d3_eight_planets_in_true_order_on_growing_orbits_with_true_period_ratios():
    g, L = lay("d3")
    tr = [t for t in L.tracks if t["kind"] == "orbit"]
    names = [g.parts[t["id"]].label for t in tr]
    assert names == ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
    assert all(a["rx"] < b["rx"] for a, b in zip(tr, tr[1:]))
    assert math.isclose(tr[2]["period"] / tr[0]["period"], 1.0 / 0.241, rel_tol=1e-3)
    for t in tr:  # each planet on its ellipse at t = 0
        n = L.nodes[t["id"]]
        assert math.isclose(((n.cx - t["cx"]) / t["rx"]) ** 2 + ((n.cy - t["cy"]) / t["ry"]) ** 2, 1, rel_tol=1e-3)


def test_d5_an_atom_is_a_nucleus_shells_and_electrons_from_the_table():
    g, L = lay("d5")
    kinds = [n.kind for n in L.nodes.values()]
    assert kinds.count("nucleus") == 1 and kinds.count("shell") == 2 and kinds.count("electron") == 6  # carbon 2, 4
    assert "Illustrative atom (carbon)" in L.badges
    log = DiagramLog()
    log.say("l1", "Imagine a sodium atom.")
    log.delta(fastpath.draft("Imagine a sodium atom.").ops, "l1", "fast", text="x")
    L2 = solve(log.fold())
    assert [n.kind for n in L2.nodes.values()].count("electron") == 11 and not L2.badges


def test_d9_field_lines_leave_n_and_reach_s_outside_the_bar():
    g, L = lay("d9")
    m = L.nodes["bar_magnet"]
    lines = field_lines(m)
    assert len(lines) >= 14
    n_pole, s_pole = (m.cx + m.w / 2, m.cy), (m.cx - m.w / 2, m.cy)
    for pts in lines:
        assert not any(abs(x - m.cx) < m.w / 2 and abs(y - m.cy) < m.h / 2 for x, y in pts)
        starts_n = math.dist(pts[0], n_pole) < math.dist(pts[0], s_pole)
        ends_s = math.dist(pts[-1], s_pole) < math.dist(pts[-1], n_pole)
        assert starts_n or ends_s                               # N -> S along every line


def test_x3_x4_the_flask_on_the_gauze_and_one_block_on_each_side_of_the_pulley():
    g, L = lay("x3")
    assert math.dist(L.nodes["flask"].anchor("bottom"), L.nodes["burner"].anchor("top")) <= 1
    g, L = lay("x4")
    p, a, b = L.nodes["pulley"], L.nodes["block"], L.nodes["block2"]
    assert a.cx < p.cx < b.cx and not overlap(a.box(), b.box())


@pytest.mark.parametrize("i", IDS)
def test_every_diagram_fits_the_slide_labels_are_clear_and_free_parts_do_not_overlap(i):
    g, L = lay(i)
    nogo = _title_nogo(fixture(i)["title"])[0]
    boxes = [(n.id, n.box()) for n in L.nodes.values() if n.kind not in ("loop", "atom")]
    for nid, b in boxes:
        assert b[0] >= 0 and b[1] >= nogo[3] - 40 and b[2] <= VIEW[0] and b[3] <= VIEW[1], (nid, b)
    labelled = [n for n in L.nodes.values() if n.label]
    assert {lab["for"] for lab in L.labels} == {n.id for n in labelled}, "a label found no free spot"
    lb = [(lab["for"], (lab["x"] - lab["w"] / 2, lab["y"] - lab["h"] / 2, lab["x"] + lab["w"] / 2, lab["y"] + lab["h"] / 2))
          for lab in L.labels]
    for k, (f, b) in enumerate(lb):
        assert not overlap(b, nogo), f
        for f2, b2 in lb[k + 1:]:
            assert not overlap(b, b2), (f, f2)
        own = {f, L.nodes[f].attr.get("cid"), f.rsplit("_", 1)[0]}
        inside = L.nodes[f].kind in ("circle", "unknown", "liquid")
        for nid, pb in boxes:
            if L.nodes[nid].kind == "shell":  # a ring: the label stays off its line (inside or outside it)
                r = L.nodes[nid]
                assert not crosses_ring(b, r.cx, r.cy, r.w / 2, 0), (f, nid)
                continue
            if nid in own or (inside and nid == f):
                continue
            assert not overlap(b, pb, 2), (f, nid)
    roots = {n.tree for n in L.nodes.values()}
    trees = {r: [b for nid, b in boxes if L.nodes[nid].tree == r] for r in roots}
    keys = sorted(trees)
    for k, r in enumerate(keys):
        for r2 in keys[k + 1:]:
            assert not any(overlap(a, b) for a in trees[r] for b in trees[r2]), (r, r2)
