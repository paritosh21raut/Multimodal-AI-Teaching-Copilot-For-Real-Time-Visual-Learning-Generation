"""F-019 M0: trust and continuity (test36) — numbers are sacred, a recap holds only its own scene, a repeat is the same
slide, "another / C3 / inside" continue the open diagram, a mishear of a concept noun; the test36 replay (0 tokens)."""
import json
from pathlib import Path

import pytest

from copilot.core.interpretation import ConcernItem, ContentItems, DiscourseAct, Interpretation
from copilot.diagram import fastpath as dfast
from copilot.diagram.graph import DiagramLog
from copilot.diagram.layout import solve
from copilot.presentation.content import Piece
from copilot.presentation.recap import recap_pieces
from copilot.presentation.stage import cue_words
from copilot.scene.detector import SceneDetector
from copilot.simulation.detector import SimulationDetector
from copilot.stage.director_llm import ReplayDirector
from copilot.stt.engine import guard
from copilot.understanding.numbers import guard_numbers
from tests.unit.test_diagram_routing import block, stage_slides
from tests.unit.test_presentation_engine import act, make, ready, send
from tests.unit.test_simulation import Lines

FIX = Path(__file__).resolve().parents[1] / "fixtures" / "diagram" / "m0_test36_lines.jsonl"


def interp(points, concerns=()):
    return Interpretation(topic="Physics", relation="same_concept",
                          acts=[DiscourseAct(act="explanation", lines=[1], items=ContentItems(points=points))],
                          concerns=list(concerns))


# ---- 1. numbers are sacred ------------------------------------------------------------------------------------------
def test_a_said_5_kg_stays_and_the_kn_concern_is_dropped():
    said = ["The weight of the box is 5kg."]
    c = ConcernItem(claim="The weight of the box is 5kg", issue="weight is a force",
                    suggested_correction="The weight of the box is 5 kN", confidence=0.9, lines=[1], kind="factual")
    it, notes = guard_numbers(interp(["Weight of box: 5 kN", "The box rests on the slope"], [c]), said)
    assert it.acts[0].items.points == ["Weight of box: 5kg", "The box rests on the slope"]
    assert it.concerns == [] and notes


def test_a_number_nobody_said_is_dropped_and_a_said_one_kept():
    said = ["The angle of the incline is 20 degrees.", "It has two shells."]
    it, _ = guard_numbers(interp(["The incline is at 30 degrees", "The incline is at 20°", "2 shells",
                                  "H2O and CO2 are molecules", "The atom has 11 protons"]), said)
    assert it.acts[0].items.points == ["The incline is at 20°", "2 shells", "H2O and CO2 are molecules"]


def test_a_unit_said_twice_with_one_number_is_not_guessed():
    it, _ = guard_numbers(interp(["Weight 5 kN"]), ["The box is 5kg.", "The push is 5N."])
    assert it.acts[0].items.points == []  # 5 kg or 5 N? neither is guessed: the item goes


def test_the_5k_mishear_is_shown_as_said_not_as_5_kn():
    it, _ = guard_numbers(interp(["The box's weight is given as 5 kN."]),
                          ["And we apply a weight of the box in the 5K GING."])
    assert "kN" not in it.acts[0].items.points[0] and "5K" in it.acts[0].items.points[0]


def test_nothing_changes_when_every_number_was_said():
    it0 = interp(["A force of 10 N", "Speed 10 m/s"])
    it, notes = guard_numbers(it0, ["a force of 10 newtons", "a speed of 10 meter per second"])
    assert it is it0 and notes == []


# ---- 2. recap scope -------------------------------------------------------------------------------------------------
def test_a_recap_drops_invented_links_and_other_scenes_things():
    p = Piece(kind="points", lines=(1,), texts=("Riding a horse illustrates collisions",
                                               "Pulling the rope represents the force on a charge",
                                               "The horse moves forward",
                                               "Friction opposes the motion"))
    kept, _ = recap_pieces([p], foreign={"horse", "rope"})
    assert [t for k in kept for t in k.texts] == ["Friction opposes the motion"]


async def test_each_stage_recaps_only_itself_and_a_one_line_stage_none():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    await send(bus, ready("Physics", "Physics", [act("explanation", points=["Forces"])], relation="new_topic"))
    sims = eng._sims
    await eng._stage.start(origin="cue", title="Ball")
    sims.mode.lines = 3
    sims.mode.collected = [Piece(kind="points", texts=("A thrown ball slows down going up",))]
    await eng._stage.start(origin="cue", title="Box")          # the ball's own recap, now
    assert sims.mode.collected == [] and sims.mode.names == ["Box"]
    sims.mode.lines = 1
    sims.mode.collected = [Piece(kind="points", texts=("Boxes are heavy",))]
    await eng._stage.start(origin="cue", title="Elephant")     # one line: no recap
    recaps = [s.title for s in deck.slides if s.title.startswith("Recap")]
    assert recaps == ["Recap: Ball"]


# ---- 3./4. repeat and continue --------------------------------------------------------------------------------------
def test_cue_words_fold_repeats():
    assert cue_words("Imagine you jump on the surface of the moon.") == cue_words("Imagine you jump on moon.")
    assert cue_words("Imagine you are teaching students.") <= cue_words(
        "Imagine you are in a classroom teaching students.")


def g_of(*lines):
    log = DiagramLog()
    for i, line in enumerate(lines):
        log.say(f"l{i}", line)
        res = log.delta(dfast.draft(line, log.fold()).ops, f"l{i}", "fast", t_ms=i, text=line)
        assert not res.rejected, res.rejected
    return log.fold()


def test_another_and_named_counts_add_only_the_new_part():
    g = g_of("Imagine two circles, C1 and C2.")
    d = dfast.draft("Imagine another circle of C3.", g)
    assert d.more and [o["label"] for o in d.ops if o["op"] == "part"] == ["C3"]
    d = dfast.draft("Imagine three circles C1, C2 and C3.", g)
    assert sorted(d.named) == ["c1", "c2"] and [o["label"] for o in d.ops if o["op"] == "part"] == ["C3"]


def test_a_square_inside_c3_is_centred_inside_it_and_smaller():
    g = g_of("Imagine three circles C1, C2 and C3.", "If a square was inside C3.")
    sq = next(p for p in g.parts.values() if p.kind == "square")
    c3 = next(p for p in g.parts.values() if p.label == "C3")
    assert g.rels[sq.id] == ("inside", c3.id)
    L = solve(g)
    a, b = L.nodes[sq.id], L.nodes[c3.id]
    assert abs(a.cx - b.cx) < 1 and abs(a.cy - b.cy) < 1
    assert a.w <= 0.7 * b.w + 0.5 and (a.w ** 2 + a.h ** 2) ** 0.5 <= b.w  # corners inside the circle


def test_another_box_on_the_box_is_a_second_box_on_top():
    g = g_of("Imagine a box placed on a surface.", "Another box is placed on top of the box.")
    boxes = [p.id for p in g.parts.values() if p.kind == "block"]
    assert len(boxes) == 2 and g.rels[boxes[1]] == ("on", boxes[0])


def test_a_laptop_of_sodium_is_an_atom_of_sodium():
    assert dfast.concept_mishear("Imagine a laptop of sodium.") == "Imagine an atom of sodium."
    for keep in ("Imagine a piece of sodium.", "Imagine a block of iron.", "Imagine an atom of sodium.",
                 "Imagine a cup of tea."):
        assert dfast.concept_mishear(keep) is None


# ---- 6. the test36 / test37 replays ---------------------------------------------------------------------------------
def rows(name="m0_test36_lines.jsonl"):
    return [json.loads(s) for s in (FIX.parent / name).read_text(encoding="utf-8").splitlines() if s.strip()]


@pytest.mark.parametrize("name", ["m0_test36_lines.jsonl", "m0_test37_lines.jsonl", "m0_test38_lines.jsonl"])
async def test_live_replay_one_slide_per_concept_and_the_diagram_continues(name):
    head, *lines = rows(name)
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0, templates_auto=False)
    SimulationDetector(bus).attach()
    SceneDetector(bus).attach()
    eng._stage.director = ReplayDirector({})
    await send(bus, ready("Lecture", "Lecture", [act("explanation", points=["Pictures of ideas"])], relation="new_topic"))
    talk = Lines(bus)
    bad = []
    for r in lines:
        if guard(r["say"], 2.5, -0.3, 0.1, 1.0):
            continue
        clock.t = r["t"]
        before = len(stage_slides(deck))
        await talk.say(r["say"])
        o = eng._stage.open
        if o is not None and o.task is not None:
            await o.task
        await bus.drain()
        after, o, f = len(stage_slides(deck)), eng._stage._live(), r.get("facts") or {}
        want = f.get("diagram") or f.get("stage")
        if want == "new" and after != before + 1 or want == "same" and after != before:
            bad.append(f"{r['n']} {r['say']!r}: {want} expected ({before} -> {after})")
        if "diagram" not in f:
            continue
        if o is None or o.mode != "diagram":
            bad.append(f"{r['n']}: no open diagram")
            continue
        g = o.dlog.fold()
        kinds = [p.kind for p in g.parts.values()]
        bad += [f"{r['n']}: no {k} ({kinds})" for k in f.get("kinds", []) if k not in kinds]
        bad += [f"{r['n']}: {k} x{kinds.count(k)}, {n} expected" for k, n in f.get("count", {}).items()
                if kinds.count(k) != n]
        labels = {p.label: p.id for p in g.parts.values()}
        bad += [f"{r['n']}: label {x} missing" for x in f.get("labels", []) if x not in labels]
        if "inside" in f:
            k, host = f["inside"]
            if not any(p.kind == k and g.rels.get(p.id) == ("inside", labels.get(host)) for p in g.parts.values()):
                bad.append(f"{r['n']}: no {k} inside {host} ({dict(g.rels)})")
    assert not bad, "\n".join(bad)
    titles = [s.title for s in stage_slides(deck)]
    assert titles == head["slides"], titles
    for s in stage_slides(deck):
        if block(s).mode == "diagram":
            assert not any(p["kind"] in ("agent", "animal") for p in block(s).diagram["parts"]), s.title


# ---- review findings ------------------------------------------------------------------------------------------------
def test_review_numbers_rows_units_words_and_numbering():
    from copilot.understanding.numbers import Said, fix
    it = Interpretation(topic="P", relation="same_concept", acts=[DiscourseAct(act="comparison", lines=[1], items=ContentItems(
        compare=["A", "B"], rows=[{"aspect": "mass", "values": ["7 kg", "5 kg"]}]))])
    it, _ = guard_numbers(it, ["B is 5 kg."])
    assert it.acts[0].items.rows[0].values == ["", "5 kg"]  # emptied in place: B's value stays under B
    s = Said(["It speeds up at 2 meters per second squared."])
    assert fix("Acceleration: 2 m/s²", s) == "Acceleration: 2 m/s²" and fix("a = 2 m/s^2", s) == "a = 2 m/s^2"
    assert fix("5 a block", Said(["The box is 5kg."])) == "5 a block"
    assert fix("25 N", Said(["a force of twenty five newtons"])) == "25 N"
    assert fix("150 g", Said(["a hundred and fifty grams"])) == "150 g"
    assert fix("Step 1: push the box", Said(["push the box"])) == "Step 1: push the box"


def test_review_recap_keeps_represent_bullets_and_concept_words():
    from copilot.presentation.simulations import _things
    p = Piece(kind="points", lines=(1,), texts=("Arrows represent forces", "This demonstrates Newton's third law",
                                                "Friction opposes the motion of the box"))
    kept, _ = recap_pieces([p], foreign=_things(["Friction on a block", "Ball on an inclined plane"])
                           - _things(["Box on a rough floor"]))
    assert [t for k in kept for t in k.texts] == list(p.texts)


def test_review_another_and_mishear_false_positives():
    g = g_of("Imagine a box on a surface.")
    for line in ("After a second the box slides.", "We have added the box."):
        d = dfast.draft(line, g)
        assert not d.more and not any(o["op"] == "part" and o["kind"] == "block" for o in d.ops), line
    for keep in ("Imagine a balloon of helium.", "a tank of oxygen", "a kind of carbon", "a form of carbon is diamond",
                 "a cylinder of hydrogen gas"):
        assert dfast.concept_mishear(keep) is None, keep


# ---- fix round (test37) ---------------------------------------------------------------------------------------------
def test_fix_ink_like_plane_is_an_inclined_plane():
    assert dfast.concept_mishear("Imagine a box on an ink-like plane.") == "Imagine a box on an inclined plane."
    for keep in ("Imagine a box on a flat plane.", "Imagine an air plane.", "the x y plane"):
        assert dfast.concept_mishear(keep) is None, keep


def test_fix_host_first_outside_garbled_label_and_one_pentagon():
    g = g_of("Imagine three circles C1, C2 and C3.")
    d = dfast.draft("If C1 has a pentagon inside it.", g)
    assert [o for o in d.ops if o["op"] == "place"] == [{"op": "place", "a": "pentagon", "rel": "inside", "b": "c1"}]
    d = dfast.draft("A hexagon is outside C2.", g)
    assert [o["rel"] for o in d.ops if o["op"] == "place"] == ["beside"]
    g = g_of("Imagine three circles C1, C2 and C3.", "Pentagon is outside Cleveland.", "If a pentagon is inside, C1C.")
    assert [(p.kind, g.rels.get(p.id)) for p in g.parts.values() if p.kind == "pentagon"] == [("pentagon", ("inside", "c1"))]


def test_fix_shapes_title_and_picture_only_bullets():
    from copilot.presentation.recap import only_picture
    from copilot.presentation.stage import picture_words, shapes_title
    g = g_of("Imagine two circles C1 and C2.", "Imagine another circle of C3.", "If a square is inside C3.")
    assert shapes_title(g) == "Three circles C1, C2, C3"
    pic = picture_words(g)
    assert only_picture("Square is inside circle C3", pic) and only_picture("Three circles labeled C1, C2, C3", pic)
    assert not only_picture("A square has four equal sides", pic)


# ---- fix round 2 (test38) -------------------------------------------------------------------------------------------
def test_fix2_a_property_line_draws_nothing_and_sc3_is_c3():
    g = g_of("Imagine three circles C1, C2 and C3.")
    assert not [o for o in dfast.draft("A square has 4 equal sides.", g).ops if o["op"] == "part"]
    assert [o["kind"] for o in dfast.draft("A triangle is added.", g).ops if o["op"] == "part"] == ["triangle"]
    d = dfast.draft("A hexagon is inside SC3.", g)
    assert [o for o in d.ops if o["op"] == "place"] == [{"op": "place", "a": "hexagon", "rel": "inside", "b": "c3"}]


def test_fix2_recap_drops_garbled_placing_and_whisper_is_primed():
    from copilot.presentation.recap import only_picture
    from copilot.presentation.stage import diagram_nouns, picture_words
    g = g_of("Imagine three circles C1, C2 and C3.", "If C1 has a pentagon inside it.")
    pic = picture_words(g)
    for t in ("The figure contains a pentagon inside the circle", "C1 contains the pentagon", "Gun is inside C3",
              "Zagon location: Inside C3"):
        assert only_picture(t, pic), t
    assert not only_picture("Square has 4 equal sides", pic)
    words = diagram_nouns(g)
    assert {"C1", "C3", "pentagon", "hexagon", "inside", "outside"} <= set(words)
