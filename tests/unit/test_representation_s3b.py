"""F-013 S3b: N-way comparison, lecture glossary, named equations, code. Every case is a real line from
verify_results/testN (0 tokens)."""
import json

from copilot.core.interpretation import CompareRow, ContentItems, DiscourseAct, Interpretation, Pair
from copilot.presentation.composer import frame_slide, merge
from copilot.presentation.content import Piece, pieces_from_act
from copilot.understanding import prompt as P
from copilot.understanding.cues import detect
from copilot.understanding.gate import BufferedLine
from copilot.understanding.interpreter import _compare_from_cue, parse_interpretation


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


def pieces(kind, **items):
    return pieces_from_act(act(kind, **items))


def lines(*texts):
    return [BufferedLine(str(i), t, float(i), float(i) + 1) for i, t in enumerate(texts)]


def table(spec):
    b = next(b for b in spec.blocks if b.type == "comparison")
    return [c.heading for c in b.columns], [(r.aspect, r.cells) for r in b.rows]


# ---- item 1: N-way comparison --------------------------------------------------------------------------------
def test_cells_that_name_their_column_make_a_three_way_table():
    # test18: ANN / CNN / RNN squeezed into a two-way table; the only "compared" name was the aspect
    p, = pieces("comparison", compare=["Model Complexity"], pairs=[
        Pair(aspect="Model complexity", left="ANN: moderate", right="TNN: moderate to high"),
        Pair(aspect="Model complexity", left="RNN: high", right="")])
    assert p.kind == "comparison" and p.columns == ("ANN", "TNN", "RNN")
    assert p.rows == (("Model complexity", ("Moderate", "Moderate to high", "High")),)


def test_one_heading_over_named_things_is_fact_tiles():
    # test5: "mixture of CaCl2 and H2O freezes at minus 55 degrees Celsius as compared with NaCl H2O at minus 18"
    p, = pieces("comparison", compare=["Freezing point of de-icing mixtures"], pairs=[
        Pair(aspect="Freezing temperature", left="CaCl₂ + H₂O mixture", right="-55 °C"),
        Pair(aspect="Freezing temperature", left="NaCl + H₂O mixture", right="-18 °C")])
    assert p.kind == "facts" and p.term == "Freezing temperature"
    assert p.pairs == (("CaCl₂ + H₂O mixture", "-55 °C"), ("NaCl + H₂O mixture", "-18 °C"))


def test_a_row_that_only_repeats_the_names_is_no_content():
    # test15: "the frequency of blue light is greater than the frequency of red light"
    assert pieces("comparison", compare=["blue light", "red light"],
                  pairs=[Pair(aspect="frequency", left="blue light", right="red light")]) == []


def test_n_way_rows_in_order_of_the_names():
    p, = pieces("comparison", compare=["ANN", "CNN", "RNN"], rows=[
        CompareRow(aspect="Data", values=["Tabular", "Images", "Sequences"])])
    assert p.columns == ("ANN", "CNN", "RNN") and p.rows == (("Data", ("Tabular", "Images", "Sequences")),)


def test_rows_keyed_by_the_compared_names_are_read_in_order():
    data = {"topic": "ML", "subtopic": "Networks", "relation": "same_concept", "acts": [{
        "act": "comparison", "lines": [1], "items": {"compare": ["CNN", "RNN"], "rows": [
            {"aspect": "Data type", "values": {"RNN": "Sequential", "CNN": "Spatial"}},
            {"aspect": "Memory", "CNN": "None", "RNN": "Hidden state"},
            ["Input length", "Fixed", "Variable"]]}}]}
    it = parse_interpretation(json.dumps(data))
    rows = [(r.aspect, r.values) for r in it.acts[0].items.rows]
    assert rows == [("Data type", ["Spatial", "Sequential"]), ("Memory", ["None", "Hidden state"]),
                    ("Input length", ["Fixed", "Variable"])]


def test_one_more_thing_compared_widens_the_table():
    s, _ = merge(frame_slide("Neural Networks", "Comparison"), Piece("comparison", columns=("CNN", "RNN"), rows=(
        ("Data type", ("Spatial", "Sequential")),)))                                                # test18
    s, left = merge(s, Piece("comparison", columns=("RNN", "ANN", "CNN"), rows=(
        ("Data type", ("Sequential", "Tabular", "Spatial")), ("Model complexity", ("High", "Moderate", "Moderate")))))
    heads, rows = table(s)
    assert left is None and heads == ["CNN", "RNN", "ANN"]
    assert rows == [("Data type", ["Spatial", "Sequential", "Tabular"]),
                    ("Model complexity", ["Moderate", "High", "Moderate"])]


def test_a_different_comparison_is_not_merged():
    s, _ = merge(frame_slide("Light", "Photons"), Piece("comparison", columns=("Blue light", "Red light"), rows=(
        ("Photon energy", ("Greater", "Less")),)))                                                   # test15
    _, left = merge(s, Piece("comparison", columns=("FPGA", "ASIC"), rows=(("Cost", ("Low", "High")),)))
    assert left is not None


def test_no_table_without_headings():
    # test18 / test5 rendered tables with empty headings: rows that name nothing become points
    s, left = merge(frame_slide("Temporal Neural Networks", "Comparison"),
                    Piece("comparison", rows=(("Input length handling", ("Fixed-length", "Variable-length")),)))
    assert left is None and not any(b.type == "comparison" for b in s.blocks)
    assert [i.text for b in s.blocks for i in b.items] == ["Input length handling: Fixed-length vs Variable-length"]


def test_announced_names_fill_a_comparison_without_names():
    ls = lines("Difference between ethical hacking and penetration testing.")                      # test27
    it = Interpretation(topic="Hacking", subtopic="EH vs PT", relation="same_concept", acts=[
        act("comparison", rows=[CompareRow(aspect="Scope", values=["Broad", "Narrow"])])])
    assert _compare_from_cue(it, ls).acts[0].items.compare == ["Ethical hacking", "Penetration testing"]
    three = Interpretation(topic="H", subtopic="S", relation="same_concept", acts=[
        act("comparison", rows=[CompareRow(aspect="Scope", values=["a", "b", "c"])])])
    assert _compare_from_cue(three, ls).acts[0].items.compare == []                  # the count does not fit


def test_comparison_cue_after_now():
    c = detect("Now let's differentiate between Artificial Intelligence and Deep Learning.").of("compare")  # test8
    assert c is not None and c.items == ("Artificial Intelligence", "Deep Learning")
    assert P.compared("Topic 9 FPGA vs ASIC") == "FPGA | ASIC"                                     # test26
    assert P.compared("You can explore the difference between machine learning and AI in a separate article.") == ""


def test_old_comparison_prompt_is_rebuilt_exactly():
    old = P.system_prompt(visual=True, hierarchy=False, named=False, compare=False)
    assert P.COMPARE_OLD in old and '"pairs": [{"aspect": "", "left": "", "right": ""}]' in old
    assert "(compares: A | B)" in P.system_prompt(visual=True, hierarchy=False, named=False)


# ---- item 5: lecture glossary ---------------------------------------------------------------------------------
from copilot.core.state import LectureSetup  # noqa: E402
from copilot.stt.factory import vocabulary_prompt  # noqa: E402
from copilot.understanding.glossary import Glossary, fix_interpretation, names_of  # noqa: E402


def study_glossary(*terms):
    g = Glossary()
    for t in terms:
        g.add(t, trusted=True)
    return g


def test_misheard_term_fixed_from_the_study_material():
    # test15: Whisper wrote "photolytic"; the teacher's material spells "photoelectric"
    g = study_glossary("photoelectric", "thermodynamics")
    text, fixes = g.fix_text("If λ is less than λts, then the photolytic effect will take place")
    assert text == "If λ is less than λts, then the photoelectric effect will take place"
    assert [(f.heard, f.shown) for f in fixes] == [("photolytic", "photoelectric")]


def test_misheard_multiword_term_keeps_its_spelling():
    g = study_glossary("Valence Bond Theory")                                                      # test19
    assert g.fix_text("Wannesbord theory: proposed by Pauling")[0] == "Valence Bond Theory: proposed by Pauling"


def test_terms_the_lecture_showed_do_not_fix_slides():
    # replay of tests 1-30: real terms the word list lacks were "fixed" into their neighbour on screen
    g = Glossary()
    assert g.learn(["Monodentate ligand", "Bidentate ligand"]) == ["Monodentate ligand", "Bidentate ligand"]
    assert g.fix_text("Polydentate ligand uses two or more donor atoms")[1] == []                  # test19


def test_real_words_and_acronyms_are_never_fixed():
    g = study_glossary("Scarcity", "EMAC", "CNN")
    assert g.fix_text("First is, Sky City")[1] == []                                               # test29
    assert g.fix_text("GSAT series satellites and the TNN input")[1] == []                         # test22, test18


def test_misheard_forms_are_not_admitted():
    g = Glossary()
    assert g.learn(["Wannesbord theory", "Valence Bond Theory"]) == ["Valence Bond Theory"]       # test19
    assert g.learn(["TNN"], ["The fixed-life input in TNN"]) == []                                 # test18
    assert g.learn(["CNN"], ["CNN, convolutional neural network for automatic spatial features"]) == ["CNN"]


def test_named_acronym_in_parentheses_is_learned():
    from copilot.core.interpretation import Interpretation
    it = Interpretation(topic="Machine Learning", subtopic="Convolutional Neural Network (CNN)",
                        relation="same_concept", acts=[])
    assert names_of(it) == ["Machine Learning", "Convolutional Neural Network", "CNN"]


def test_a_fix_is_a_transcription_concern():
    it = Interpretation(topic="Light", subtopic="Photoelectric Effect", relation="same_concept", acts=[
        act("explanation", points=["Photolytic effect needs a minimum frequency"])])
    out, fixes = fix_interpretation(study_glossary("photoelectric"), it, ["The photolytic effect needs ..."])
    assert out.acts[0].items.points == ["Photoelectric effect needs a minimum frequency"]
    c, = out.concerns
    assert (c.kind, c.wrong, c.right) == ("transcription", "Photolytic", "Photoelectric")


def test_whisper_prompt_keeps_the_newest_terms():
    setup = LectureSetup(subject="Chemistry", expected_topic="Coordination compounds")
    terms = [f"term{i}" for i in range(100)]
    p = vocabulary_prompt(setup, terms)
    assert p.startswith("A classroom lecture on Chemistry - Coordination compounds. Terms: term40,")
    assert p.endswith("term99.")


# ---- item 8: named equations ----------------------------------------------------------------------------------
import pytest  # noqa: E402

from copilot.presentation import equations as EQ  # noqa: E402


@pytest.mark.parametrize("line, ids", [
    ("Schrodinger's wave equation or Schrodinger's equation is one of the most fundamental equations of quantum "
     "physics", ["schrodinger_td"]),                                                                     # test16
    ("There are two equations which are time-dependent Schrodinger equation and the time-independent Schrodinger "
     "equation.", ["schrodinger_td", "schrodinger_ti"]),                                                 # test16
    ("Now let us understand the third law of Newton.", ["newton_3"]),                                    # test1
    ("Newton's first law of motion is also called the law of inertia.", []),                             # test1
    ("GDP formula, the expenditure approach to GDP is expressed as", ["gdp"]),                           # test29
    ("The law of conservation of energy forms the basis of the photolytic effect.", []),                 # test15
    ("Differential Equation is an equation involving an unknown function", []),                          # test23
    ("Maxwell's equations describe how electric and magnetic fields behave",
     ["gauss_e", "gauss_b", "faraday", "ampere"]),
    ("Gauss's law for magnetism says there are no magnetic monopoles", ["gauss_b"]),
])
def test_named_equations_in_real_lines(line, ids):
    assert EQ.named(line) == ids


def test_an_ambiguous_name_needs_its_subject():
    line = "continuity equation. Based on the conversation of conservation of mass"                    # test2
    assert EQ.named(line, "Fluid Dynamics mass flow rate") == ["continuity"]
    assert EQ.named(line, "Electromagnetism charge density") == []


def test_asked_for_the_equation_of_the_slide():
    assert EQ.asked_for("Now let us write the equation.", "Schrödinger's Equation") == ["schrodinger_td"]
    assert EQ.asked_for("Schrodinger equation gives the wave function", "Quantum Physics") == []


def test_library_search_for_control():
    assert [e.id for e in EQ.search("maxwell")][:4] == ["gauss_e", "gauss_b", "faraday", "ampere"]
    assert {e.id for e in EQ.search("gas")} >= {"ideal_gas", "boyle", "charles"}


async def test_named_equation_goes_on_the_slide_once_and_the_spoken_formula_wins():
    from copilot.core.events import Command, CommandReceived, InterpretationReady, TranscriptFinal, TranscriptSegment
    from copilot.core.interpretation import Formula
    from tests.unit.test_presentation_engine import make, send

    bus, store, deck, eng, clock = await make()

    def unit(rid, text, acts):
        seg = TranscriptSegment(text=text, start=0, end=1)
        return [TranscriptFinal(segment=seg), InterpretationReady(
            request_id=rid, segment_ids=[seg.id], provider="m", interpretation=Interpretation(
                topic="Quantum Physics", subtopic="Schrödinger's Equation", relation="same_concept", acts=acts))]

    said = "There are two equations which are time-dependent Schrodinger equation and the time-independent one."
    await send(bus, *unit("u1", said, [act("explanation", points=["Two forms: time-dependent and time-independent"])]))
    shown = [b for s in deck.slides for b in s.blocks if b.type == "formula"]
    assert [(b.name, b.standard) for b in shown] == [("Schrödinger equation (time-dependent)", True)]
    assert shown[0].latex == r"i\hbar\,\dfrac{\partial \Psi}{\partial t} = \hat{H}\,\Psi"
    assert [v.symbol for v in shown[0].variables] == ["Ψ", "ħ", "Ĥ", "t"]
    await send(bus, *unit("u2", "The time-dependent Schrodinger equation describes how the state changes.", [
        act("explanation", points=["Describes how a quantum state changes in time"])]))
    assert len([b for s in deck.slides for b in s.blocks if b.type == "formula"]) == 1      # once per lecture
    await send(bus, *unit("u3", "Ohm's law, V equals I R.", [
        act("formula", formula=Formula(expression="V = I R"))]))
    names = [b.name for s in deck.slides for b in s.blocks if b.type == "formula"]
    assert names == ["Schrödinger equation (time-dependent)", ""]                           # the teacher's own
    await send(bus, CommandReceived(command=Command(kind="show_equation", args={"id": "heisenberg"})))
    names = [b.name for s in deck.slides for b in s.blocks if b.type == "formula"]
    assert names[-1] == "Heisenberg uncertainty principle"
