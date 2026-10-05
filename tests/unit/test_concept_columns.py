"""Concept columns (user's issue 6, live energy test 2026-10-06): content about one of two concepts defined side by
side goes into that concept's column; definitions pair only as peers (issue 4, kinematics)."""
from copilot.presentation.composer import frame_slide, merge
from copilot.presentation.content import Piece, pieces_from
from copilot.understanding.interpreter import parse_interpretation

from tests.unit.test_formula_parsing import RAW_ENERGY


def build(spec, pieces):
    left = []
    for p in pieces:
        spec, rest = merge(spec, p)
        if rest is not None:
            left.append(rest)
    return spec, left


def defs(*pairs):
    return [Piece("definition", term=t, definition=d, about=t) for t, d in pairs]


def column_of(spec, block):
    by_id = {b.id: b for b in spec.blocks}
    return by_id[block.about].term if block.about else ""


def test_energy_lecture_content_goes_to_its_concept():
    s, left = build(frame_slide("Energy", "Kinetic and Potential Energy"), defs(
        ("Kinetic energy", "energy of motion"),
        ("Potential energy", "energy stored based on object's position or state")))
    assert not left and [b.type for b in s.blocks] == ["definition", "definition"]  # peers: side by side
    s, left = build(s, pieces_from(parse_interpretation(RAW_ENERGY)))   # KE formula, examples, PE formula
    assert not left
    placed = {(b.type, column_of(s, b)) for b in s.blocks if b.type != "definition"}
    assert placed == {("formula", "Kinetic energy"), ("example", "Kinetic energy"), ("formula", "Potential energy")}
    ke_example = next(b for b in s.blocks if b.type == "example")
    assert ke_example.text == "rolling ball; running person; speeding car"


def test_text_naming_a_concept_wins_and_shared_content_stays_full_width():
    s, _ = build(frame_slide("Energy", "Kinetic and Potential Energy"), defs(
        ("Kinetic energy", "energy of motion"), ("Potential energy", "stored energy")))
    s, _ = merge(s, Piece("points", texts=("Potential energy depends on height",), about="Kinetic energy"))
    s, _ = merge(s, Piece("points", texts=("Kinetic and potential energy convert into each other",)))
    pts = [b for b in s.blocks if b.type == "points"]
    assert [(column_of(s, b), [i.text for i in b.items]) for b in pts] == [
        ("Potential energy", ["Potential energy depends on height"]),
        ("", ["Kinetic and potential energy convert into each other"])]


def test_topic_definition_is_not_a_peer():
    """Kinematics live test: "Distance" was paired with the topic's own definition "Kinematics"."""
    s, left = build(frame_slide("Kinematics", "Definition"), defs(
        ("Kinematics", "the branch of mechanics that describes motion"),
        ("Distance", "total length of the path travelled"),
        ("Displacement", "straight-line change in position")))
    assert [b.term for b in s.blocks if b.type == "definition"] == ["Kinematics"]
    part2, left2 = build(frame_slide("Kinematics", "Definition"), left)
    assert not left2 and [b.term for b in part2.blocks] == ["Distance", "Displacement"]
    assert part2.title == "Distance and displacement"


def test_further_examples_join_the_example_card():
    s, _ = build(frame_slide("Energy", "Potential Energy"), [
        Piece("definition", term="Potential energy", definition="stored energy"),
        Piece("example", texts=("water at the top of a dam",)), Piece("example", texts=("a compressed spring",))])
    ex = [b for b in s.blocks if b.type == "example"]
    assert len(ex) == 1 and ex[0].text == "water at the top of a dam; a compressed spring"


def test_examples_after_a_point_naming_a_concept_follow_it():
    """Energy lecture unit 3: "Mass, height ... determine potential energy", then "e.g. water at top of a dam"."""
    from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation
    s, _ = build(frame_slide("Energy", "Kinetic and Potential Energy"), defs(
        ("Kinetic energy", "energy of motion"), ("Potential energy", "stored energy")))
    it = Interpretation(topic="Energy", subtopic="Kinetic and Potential Energy", relation="same_concept", acts=[
        DiscourseAct(act="explanation", lines=[1], items=ContentItems(
            points=["Mass, height and physical configuration determine potential energy"])),
        DiscourseAct(act="example", lines=[2], items=ContentItems(examples=["water at the top of a dam"]))])
    s, left = build(s, pieces_from(it))
    assert not left
    assert {(b.type, column_of(s, b)) for b in s.blocks if b.type != "definition"} == {
        ("points", "Potential energy"), ("example", "Potential energy")}


def test_the_concept_chain_carries_into_the_next_unit_of_the_same_frame():
    """Live energy re-run: the KE formula came in one unit, its examples ("rolling ball", ...) in the next."""
    from copilot.core.interpretation import ContentItems, DiscourseAct, Formula, Interpretation
    from copilot.presentation.content import pieces_and_chain
    t, s_ = "Energy", "Kinetic and Potential Energy"
    u1 = Interpretation(topic=t, subtopic=s_, relation="same_concept", acts=[DiscourseAct(
        act="formula", lines=[1], items=ContentItems(formula=Formula(expression="KE = 1/2 m v^2")))])
    u2 = Interpretation(topic=t, subtopic=s_, relation="same_concept", acts=[DiscourseAct(
        act="explanation", lines=[1], items=ContentItems(points=["rolling ball", "running person"]))])
    p1, chain = pieces_and_chain(u1)
    p2, _ = pieces_and_chain(u2, chain)
    s, _ = build(frame_slide(t, s_), defs(("Kinetic energy", "energy of motion"), ("Potential energy", "stored")))
    s, left = build(s, p1 + p2)
    assert not left
    assert {(b.type, column_of(s, b)) for b in s.blocks if b.type != "definition"} == {
        ("formula", "Kinetic energy"), ("points", "Kinetic energy")}


def test_live_kinematics_unit_definition_kept_whole_and_no_empty_comparison():
    """Live kinematics re-run 2026-10-06: the definition was cut ("... without looking at the…") and
    compare: ["Speed", "Velocity"] without rows became a table of two headings over nothing."""
    from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation
    long_def = ("the branch of classical mechanics that describes the motion of objects such as position, velocity "
                "and acceleration without looking at the force or masses that cause the motion")
    it = Interpretation(topic="Kinematics", subtopic="Definition", relation="same_concept", acts=[
        DiscourseAct(act="definition", lines=[1], items=ContentItems(term="Kinematics", definition=long_def)),
        DiscourseAct(act="comparison", lines=[2], items=ContentItems(compare=["Speed", "Velocity"])),
        DiscourseAct(act="explanation", lines=[3], items=ContentItems(points=[
            "Speed is how fast an object moves", "Velocity includes speed and direction of motion"]))])
    ps = pieces_from(it)
    assert [p.kind for p in ps] == ["definition", "points"]
    assert ps[0].definition == long_def
