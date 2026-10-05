"""M4 presentation engine: content mapping, composer, planner (pure) — F-005."""
from copilot.core.interpretation import ContentItems, DiscourseAct, Formula, Interpretation, Pair
from copilot.presentation.composer import (
    CAPACITY, clear_provisional, describe, frame_slide, merge, set_provisional, slide_title, teacher_items,
)
from copilot.presentation.content import FormulaData, Piece, pieces_from
from copilot.presentation.spec import PointsBlock
from copilot.presentation.planner import Frame, Signal, Working, decide


def act(kind, lines=(1,), added=False, **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items), added=added)


def interp(topic="Photosynthesis", sub="Process", relation="same_concept", acts=(), meta=()):
    return Interpretation(topic=topic, subtopic=sub, relation=relation, acts=list(acts), meta_lines=list(meta))


# ---- content ------------------------------------------------------------------------------------------
def test_process_given_as_points_becomes_steps_and_definitions_are_pieces():
    ps = pieces_from(interp(acts=[
        act("process", points=["Input: roots absorb water", "Chlorophyll absorbs sunlight"]),
        act("definition", term="Photosynthesis", definition="Plants make food using light", points=["photo = light"]),
    ]))
    assert [p.kind for p in ps] == ["steps", "definition", "points"]
    assert ps[0].texts == ("Input: roots absorb water", "Chlorophyll absorbs sunlight")


def test_questions_transitions_and_meta_lines_give_no_pieces():
    it = interp(acts=[act("transition"), act("question"), act("explanation", lines=(2,), points=["Open your books"])],
                meta=[2])
    assert pieces_from(it) == []


def test_comparison_pairs_map_to_columns_and_rows():
    (p,) = pieces_from(interp(acts=[act("comparison", compare=["Photosynthesis", "Respiration"],
                                        pairs=[Pair(aspect="When", left="Sunlight only", right="All the time")])]))
    assert p.kind == "comparison" and p.columns == ("Photosynthesis", "Respiration")
    assert p.rows == (("When", ("Sunlight only", "All the time")),)


# ---- composer -----------------------------------------------------------------------------------------
def pts(*texts, added=False):
    return Piece("points", lines=(1,), texts=tuple(texts), added=added)


def test_points_merge_in_place_with_stable_ids_dedupe_and_capacity():
    s = frame_slide("Photosynthesis", "Requirements")
    s, left = merge(s, pts("Sunlight", "Water from the roots"))
    assert left is None and s.layout == "key_points"
    ids = [i.id for i in s.blocks[0].items]
    s2, left = merge(s, pts("water from the roots.", "Carbon dioxide", "Chlorophyll", "Minerals", "Warmth", "Air",
                            "Soil", "Light"))
    items = s2.blocks[0].items
    assert [i.id for i in items[:2]] == ids                       # existing items untouched
    assert [i.text for i in items] == ["Sunlight", "Water from the roots", "Carbon dioxide", "Chlorophyll",
                                       "Minerals", "Warmth", "Air", "Soil"]  # duplicate skipped, cap 8 per list
    assert left is not None and left.texts == ("Light",)           # the rest continues on the next part


def test_steps_capacity_and_formula_needs_its_own_slide():
    s, left = merge(frame_slide("P", "Process"), Piece("steps", texts=tuple(f"step {i}" for i in range(8))))
    assert s.layout == "process_flow" and len(s.blocks[0].steps) == CAPACITY["steps"]
    assert left.texts == ("step 6", "step 7")
    f = Piece("formula", formula=FormulaData("CO2 + H2O -> C6H12O6 + O2"))
    s2, left2 = merge(s, f)
    assert s2 == s and left2 == f


def test_at_most_one_added_item_per_slide():
    s, _ = merge(frame_slide("P", "Requirements"), pts("Sunlight"))
    s, _ = merge(s, pts("Plants also need warmth", added=True))
    s2, left = merge(s, pts("Another addition", added=True))
    assert left is None and s2 == s
    assert sum(i.added for i in s.blocks[0].items) == 1


def test_definition_then_notes_and_other_terms():
    s, _ = merge(frame_slide("Photosynthesis", "Definition"),
                 Piece("definition", term="Photosynthesis", definition="How plants make food using sunlight"))
    assert s.layout == "definition"
    s, _ = merge(s, Piece("definition", term="photosynthesis", definition="How plants make food using sunlight."))
    assert s.blocks[0].notes == []                                  # same definition again: nothing new
    s, _ = merge(s, Piece("definition", term="photo", definition="means light"))
    assert [n.text for n in s.blocks[0].notes] == ["photo means light"]   # a word part: a note
    s, left = merge(s, Piece("definition", term="Chlorophyll", definition="the green pigment in leaves"))
    assert left is not None and left.kind == "definition"           # another concept: its own definition card
    s, left = merge(s, pts("synthesis = putting together", "Plants are producers", "Light is needed"))
    assert left is None and [b.type for b in s.blocks] == ["definition", "points"]
    assert [n.text for n in s.blocks[0].notes] == ["photo means light"]   # chips: word-part notes only
    assert [i.text for i in s.blocks[1].items] == ["synthesis = putting together", "Plants are producers",
                                                   "Light is needed"]    # parallel points stay one list


def test_provisional_item_updates_in_place_and_refined_content_replaces_it():
    s, _ = merge(frame_slide("P", "Requirements"), pts("Sunlight"))
    p1 = set_provisional(s, "carbon dioxide · stomata")
    p2 = set_provisional(p1, "chlorophyll · green pigment")
    i1, i2 = p1.blocks[0].items[-1], p2.blocks[0].items[-1]
    assert i1.provisional and i1.id == i2.id and i2.text == "chlorophyll · green pigment"
    assert teacher_items(p2) == 1
    assert clear_provisional(p2) == s
    # an otherwise empty slide with only a provisional item is reshaped by the first refined piece
    e = set_provisional(frame_slide("P", "Process").model_copy(update={"blocks": [PointsBlock()]}), "teaser")
    out, left = merge(e, Piece("steps", texts=("Light is absorbed",)))
    assert left is None and out.layout == "process_flow" and len(out.blocks) == 1


def test_titles_and_description():
    assert slide_title("Photosynthesis", "Definition") == "What is photosynthesis?"
    assert slide_title("Photosynthesis", "Process") == "How photosynthesis works"
    assert slide_title("Photosynthesis", "Stages") == "Stages"          # the crumb shows the topic
    assert slide_title("Respiration", "Respiration") == "Respiration"
    assert slide_title("DNA", "Importance") == "Why DNA matters"
    s, _ = merge(frame_slide("Photosynthesis", "Process"), Piece("steps", texts=("Light absorbed", "Water split")))
    d, refs = describe(s)
    assert d.startswith("How photosynthesis works (process flow, has room)") and "[S1] step: Light absorbed" in d
    assert list(refs) == ["S1", "S2"] and refs["S1"] == f"{s.id}/{s.blocks[0].steps[0].id}"


# ---- planner ------------------------------------------------------------------------------------------
W = Working(Frame("Photosynthesis", "Requirements"), has_content=True)


def test_planner_table():
    same = interp(sub="Requirements", acts=[act("explanation", points=["x"])])
    assert decide(W, same, [], None, has_pieces=True).op == "update"
    facet = interp(sub="Process", relation="sibling_concept")
    assert decide(W, facet, [], None, has_pieces=True).op == "continue"
    assert decide(Working(W.frame, has_content=False), facet, [], None, has_pieces=True).op == "retitle"
    assert decide(None, facet, [], None, has_pieces=True).op == "new"
    assert decide(Working(W.frame, False, is_title=True), facet, [], None, has_pieces=True).op == "new"
    assert decide(W, interp(relation="digression"), [], None, has_pieces=True).op == "noop"
    assert decide(W, facet, [], None, has_pieces=False).op == "noop"


def test_new_topic_needs_confirmation():
    resp = interp(topic="Respiration", sub="Comparison", relation="new_topic")
    d = decide(W, resp, [Signal(0.3, False)], None, has_pieces=True)
    assert d.op == "update" and d.frame == W.frame and d.candidate == "Respiration"   # provisional: stay
    d2 = decide(W, interp(topic="Respiration", sub="Comparison"), [], d.candidate, has_pieces=True)
    assert d2.op == "new" and d2.candidate is None                                    # two agree
    assert decide(W, resp, [Signal(0.2, True)], None, has_pieces=True).op == "new"    # boundary cue
    assert decide(W, resp, [Signal(0.8, False)], None, has_pieces=True).op == "new"   # shift score
    # back on the old topic: the candidate is forgotten
    d3 = decide(W, interp(sub="Requirements"), [], "Respiration", has_pieces=True)
    assert d3.op == "update" and d3.candidate is None


def test_llm_quirks_examples_in_explanations_and_aspect_as_compare():
    ps = pieces_from(interp(acts=[act("explanation", examples=["Water is absorbed by the roots"]),
                                  act("example", examples=["A plant in a dark cupboard turns pale"])]))
    assert [(p.kind, p.texts) for p in ps] == [("points", ("Water is absorbed by the roots",)),
                                               ("example", ("A plant in a dark cupboard turns pale",))]
    (c,) = pieces_from(interp(acts=[act("comparison", compare=["carbon dioxide usage"], pairs=[
        Pair(aspect="CO2", left="uses it", right="releases it")])]))
    assert c.columns == ()
    s, _ = merge(frame_slide("Respiration", "Comparison"), Piece("comparison", columns=("Photosynthesis", "Respiration"),
                                                                rows=(("Timing", ("sunlight", "always")),)))
    s2, left = merge(s, c)
    assert left is None and len(s2.blocks[0].rows) == 2               # merged into the same table


def test_empty_content_act_gets_the_spoken_line():
    from copilot.understanding.gate import BufferedLine
    from copilot.understanding.interpreter import _fill_empty_acts
    lines = [BufferedLine("a", "Why is it important?", 0, 1),
             BufferedLine("b", "And the oxygen we breathe is produced by photosynthesis.", 1, 4)]
    it = interp(acts=[act("question", lines=(1,)), act("explanation", lines=(2,))])
    out = _fill_empty_acts(it, lines)
    assert out.acts[0].items.points == []                             # questions are not filled
    assert out.acts[1].items.points == ["The oxygen we breathe is produced by photosynthesis"]  # filler dropped


def test_two_labelled_classifications_become_named_groups_and_yes_facts_become_points():
    from copilot.core.interpretation import Fact
    ps = pieces_from(interp(acts=[
        act("classification", label="Inner planets", points=["Mercury", "Venus", "Earth", "Mars"]),
        act("classification", lines=(2,), label="Outer planets", points=["Jupiter", "Saturn", "Uranus", "Neptune"]),
        act("explanation", lines=(3,), facts=[Fact(label="Smallest planet", value="Mercury"),
                                              Fact(label="Milky Way contains our solar system", value="Yes")])]))
    assert [p.kind for p in ps] == ["groups", "facts", "points"]
    assert [g[0] for g in ps[0].groups] == ["Inner planets", "Outer planets"]
    assert ps[1].pairs == (("Smallest planet", "Mercury"),)
    assert ps[2].texts == ("Milky Way contains our solar system",)


def test_facts_and_a_definition_may_join_a_slide_with_a_diagram():
    s, _ = merge(frame_slide("Chemistry", "Molecules"), Piece("tree", term="Types of molecules",
                                                              texts=("Monoatomic", "Diatomic")))
    s, left = merge(s, Piece("definition", term="Molecule", definition="Simplest particle with independent existence"))
    assert left is None and [b.type for b in s.blocks] == ["hierarchy", "definition"]
    s, left = merge(s, Piece("tree", term="States", texts=("Solid", "Liquid")))
    assert left is None and s.blocks[-1].type == "groups"                # a second classification: groups


def test_announced_topic_is_remembered_by_a_noop():
    w = Working(Frame("Solar System", "Overview"), has_content=True)
    d = decide(w, interp(topic="Galaxies", sub="", relation="new_topic"), [Signal(0.4, True)], None,
               has_pieces=False)
    assert d.op == "noop" and d.candidate == "Galaxies"
    d2 = decide(w, interp(topic="Galaxies", sub=""), [], d.candidate, has_pieces=True)
    assert d2.op == "new"
