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
                            "Soil"))
    items = s2.blocks[0].items
    assert [i.id for i in items[:2]] == ids                       # existing items untouched
    assert [i.text for i in items] == ["Sunlight", "Water from the roots", "Carbon dioxide", "Chlorophyll",
                                       "Minerals", "Warmth"]       # duplicate skipped, capacity 6
    assert left is not None and left.texts == ("Air", "Soil")      # the rest continues on a new slide


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
    s, _ = merge(s, pts("photo = light"))
    s, left = merge(s, Piece("definition", term="Chlorophyll", definition="green pigment"))
    assert [n.text for n in s.blocks[0].notes] == ["photo = light", "Chlorophyll: green pigment"]
    s, left = merge(s, pts("synthesis = putting together", "Plants are producers", "Light is needed", "Leaves"))
    assert [b.type for b in s.blocks] == ["definition", "points"]   # notes full: a short supporting list (cap 3)
    assert [i.text for i in s.blocks[1].items] == ["synthesis = putting together", "Plants are producers",
                                                   "Light is needed"]
    assert left is not None and left.texts == ("Leaves",)


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
    assert slide_title("Photosynthesis", "Stages") == "Stages of Photosynthesis"
    assert slide_title("Respiration", "Respiration") == "Respiration"
    assert slide_title("DNA", "Importance") == "Why DNA matters"
    s, _ = merge(frame_slide("Photosynthesis", "Process"), Piece("steps", texts=("Light absorbed", "Water split")))
    d = describe(s)
    assert "How photosynthesis works (process flow)" in d and "1. Light absorbed" in d and "room for 4 more steps" in d


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
    assert out.acts[1].items.points == ["And the oxygen we breathe is produced by photosynthesis."]
