"""F-013 S3a: representation quality, deterministic (0 tokens). Every case is a real line from verify_results/testN."""
import pytest

from copilot.core.interpretation import ConcernItem, ContentItems, DiscourseAct, Interpretation, TimedEvent
from copilot.core.state import LectureState
from copilot.core.textutil import normalise_spoken, stem
from copilot.presentation.composer import frame_slide, is_duplicate, merge
from copilot.presentation.content import Piece, cap, clean, pieces_from_act
from copilot.presentation.mathtext import mark_math, to_latex
from copilot.understanding.gate import BufferedLine
from copilot.understanding.interpreter import (
    _cover_dropped_sentences, _sanitise, _strip_meta_notes, fallback_interpretation, tidy_spoken,
)
from copilot.understanding.quality import problem, strip_meta


def act(kind, lines=(1,), **items):
    return DiscourseAct(act=kind, lines=list(lines), items=ContentItems(**items))


def interp(*acts, concerns=()):
    return Interpretation(topic="T", subtopic="S", relation="same_concept", acts=list(acts), concerns=list(concerns))


def lines(*texts):
    return [BufferedLine(str(i), t, float(i), float(i) + 1) for i, t in enumerate(texts)]


def guarded(it, ls):
    """The texts the coverage guard added."""
    out = _cover_dropped_sentences(it, ls, "")
    return [p for a in out.acts[len(it.acts):] for p in a.items.points]


# ---- item 3: the same quantity spoken and written -----------------------------------------------------------
def test_spoken_quantities_normalise_like_written_ones():
    # test4
    assert normalise_spoken("Atomic radii are of the order of 10 to the power minus 8 centimeter") \
        == "atomic radii are of the order of 10^-8 cm"
    assert normalise_spoken("Atomic radii: ~10⁻⁸ cm") == "atomic radii: 10^-8 cm"
    assert normalise_spoken("9.58 into 10 to the power minus 4 coulombs per gram") == "9.58x10^-4 c per g"
    assert normalise_spoken("minus 55 degrees Celsius") == "-55 °c"  # test5
    assert normalise_spoken("second law of motion") == "second law of motion"  # a unit only after a number


def test_stemmer_folds_the_forms_one_statement_takes():
    assert stem("masses") == stem("mass")          # test20 "Chantment among the masses" / "Mass discontent"
    assert stem("rioting") == stem("riots")        # test20
    assert stem("wars") == stem("war")
    assert stem("status") == "status"


def test_written_and_spoken_quantity_is_one_item():
    assert is_duplicate("Atomic radii: ~10⁻⁸ cm", "Atomic radii are of the order of 10 to the power minus 8 centimeter")
    assert not is_duplicate("Speed 3×10^8 m/s", "Mass 3×10^8 kg")
    assert not is_duplicate("Freezing point 55 °C", "Freezes at minus 55 degrees Celsius")  # the sign differs


# ---- item 4: the coverage guard and the garbage gate ---------------------------------------------------------
def test_guard_does_not_repeat_a_paraphrased_sentence():
    # S2 live run (session 20261016-122638-6e6a): the model's points covered both; the guard added them verbatim
    it = interp(act("explanation", lines=(1,), points=["Aristocratic luxury spread disease",
                                                      "Mass discontent from extreme poverty and hunger"]))
    assert guarded(it, lines("Chantment among the masses who then were leading life of extreme poverty and "
                             "widespread hunger.")) == []
    it = interp(act("explanation", points=["Wars drained treasury and left workforce empty",
                                           "Privileged classes exempt from taxes"]))
    assert guarded(it, lines("Economic, as a result of numerous wars wages by Louis XVI, the state of workforce was "
                             "empty.")) == []


def test_guard_spoken_quantity_counts_as_covered():
    it = interp(act("explanation", points=["Atomic radii: ~10⁻⁸ cm"]))  # test4
    assert guarded(it, lines("Atomic radii are of the order of 10 to the power minus 8 centimeter.")) == []


def test_guard_still_recovers_a_dropped_fact():
    # live chemistry test 2026-10-05: the reason the guard exists
    it = interp(act("explanation", lines=(1,), points=["Matter has mass and occupies space"]))
    out = guarded(it, lines("Matter has mass and occupies space.",
                            "The matter particles attract each other and are in the state of continuous motion."))
    assert out == ["The matter particles attract each other and are in the state of continuous motion"]


@pytest.mark.parametrize("said", [
    "Recall that thermal energy continuously creates pair of free electrons and holes.",                   # test30
    "These devices will be discussed in later chapter.",                                                  # test30
    "You will have the basic idea somewhere in the vicinity of the junction these opposite charges recombine.",
    "Single inverted comma b1 semicolon end end module.",                                                 # test26
    "It can involve reviewing, configuration, examining, systems testing, applications and evaluating security.",
    "The third topic is Integral Calculus.",                                                              # test23
    "Doping a semiconductor One way to increase conductivity of a semiconductor is by doping.",           # test30
    "Will come out of the cell to follow the genetic analysis.",                                          # test15
])
def test_guard_does_not_show_noise(said):
    it = interp(act("explanation", lines=(2,), points=["Unrelated point about something else"]))
    assert guarded(it, lines("Short.", said)) == []


def test_line_the_model_cited_needs_almost_nothing_on_the_slide():
    # test30: the model summarised the line; the guard's 34 % rule re-added it as said
    it = interp(act("explanation", lines=(1,), points=["Secondary voltage peaks negative"]))
    assert guarded(it, lines("Again, the secondary voltage is at the negative peak.")) == []
    # a sentence with a quarter of its words on the slide: back as said only when the model did not cite its line
    said = "The transformer output reverses its polarity at the negative peak during each half cycle."
    cited = interp(act("explanation", lines=(1,), points=["Secondary voltage peaks negative"]))
    uncited = interp(act("explanation", lines=(2,), points=["Secondary voltage peaks negative"]))
    assert guarded(cited, lines(said, "Short.")) == []
    assert guarded(uncited, lines(said, "Short.")) == [said.rstrip(".")]


@pytest.mark.parametrize("text", [
    "The oxygen we breathe is produced by photosynthesis",            # a generic "we" in a statement
    "World War I (1914-1918) involved most European nations",
    "This situation is called thrashing",                             # test25: "This X is called Y" names a term
    "Hydrogen, the lightest element, has one proton",
    "Vitamin A is needed for vision",
    "If light frequency is below the threshold, no electrons are ejected",
])
def test_gate_keeps_real_statements(text):
    assert problem(text) == ""


def test_tidy_drops_linking_words_but_not_qualifiers():
    assert tidy_spoken("Thus, Ethical Hacking is not limited to finding vulnerabilities.") == \
        "Ethical Hacking is not limited to finding vulnerabilities"                                     # test27
    assert tidy_spoken("As a result, rioting, looting, and general strikes became the norm") == \
        "Rioting, looting, and general strikes became the norm"                                         # test20
    assert tidy_spoken("Generally, when the price decreases, demand rises").startswith("Generally,")   # test29
    assert tidy_spoken("Well-developed digestive system extracts nutrients").startswith("Well-developed")


def test_fallback_keeps_the_teachers_examples_but_not_spoken_code():
    out = fallback_interpretation(LectureState(session_id="s"), lines(
        "If you buy the book, the movie is your next best alternative that you give up.",            # test29
        "Single inverted comma b1 semicolon end end module."))
    texts = [p for a in out.acts for p in a.items.points]
    assert texts == ["If you buy the book, the movie is your next best alternative that you give up"]


def test_note_about_the_transcript_leaves_the_item():
    # test6
    assert strip_meta("Violent crackdowns on peaceful protesters, notably at the [unclear location, likely mis‑heard]") \
        == "Violent crackdowns on peaceful protesters"
    it = _strip_meta_notes(interp(act("explanation", points=["Arrests at the [unclear word] camp", "Plain point"])))
    assert it.acts[0].items.points == ["Arrests at the camp", "Plain point"]


def test_concern_whose_correction_is_a_note_is_dropped():
    c = ConcernItem(claim="notably at the Resinart Sidewalk", issue="misheard place",
                    suggested_correction="notably at the [unclear location, likely mis-heard]", confidence=0.6,
                    lines=[1], kind="transcription")
    out = _sanitise(interp(act("explanation", points=["x"]), concerns=[c]), 1, 0.6, LectureState(session_id="s"))
    assert out.concerns == []


# ---- item 2: definition cards ---------------------------------------------------------------------------------
def pieces(kind="definition", **items):
    return pieces_from_act(act(kind, **items))


def test_definition_repeating_its_term_loses_the_repeat():
    p, = pieces(term="Hypothalamus", definition="Hypothalamus: brain region below thalamus controlling temperature")
    assert p.kind == "definition" and p.definition == "Brain region below thalamus controlling temperature"  # test13


def test_a_fact_about_a_term_is_a_point_not_a_definition():
    p, = pieces(term="Electron", definition="was discovered as a result of study of cathode rays by J.J. Thompson")
    assert p.kind == "points" and p.texts == ("Electron was discovered as a result of study of cathode rays by "
                                              "J.J. Thompson",)                                     # test4


def test_a_list_given_as_a_definition_is_a_list():
    p, = pieces(term="Prime number", definition="Encryption; Secure communication; Digital signature; Cyber security")
    assert p.kind == "points" and p.texts == ("Encryption", "Secure communication", "Digital signature",
                                              "Cyber security")                                     # test23


def test_greek_symbol_keeps_its_case():
    assert cap("ν") == "ν" and cap("λ0") == "λ0" and cap("electron") == "Electron"  # test15 showed "Ν"


# ---- the sign of a number --------------------------------------------------------------------------------------
def test_a_minus_sign_is_not_a_list_marker():
    # test5: the model wrote "-55 °C", the slide showed "55 °C"
    assert clean("-55 °C") == "-55 °C" and clean("–18 °C") == "–18 °C"
    assert clean("- Photosynthesis makes food") == "Photosynthesis makes food"


# ---- item 3 on the slide ---------------------------------------------------------------------------------------
def test_definition_replaces_the_same_term_said_as_a_shorter_point():
    s, _ = merge(frame_slide("Plate Tectonics", "Boundaries"), Piece("points", texts=(
        "Convergent: plates move toward each other, causing collisions, mountain ranges, subduction",
        "Divergent: plates move apart, magma rises to form new crust")))
    s, left = merge(s, Piece("definition", term="Convergent", definition=(
        "Plates move toward each other, causing collisions, mountain ranges, subduction, volcanic activity, and "
        "earthquakes")))                                                                             # test28
    texts = [i.text for b in s.blocks if b.type == "points" for i in b.items]
    assert left is None and len(texts) == 1 and texts[0].startswith("Divergent")
    assert any(b.type == "definition" and b.term == "Convergent" for b in s.blocks)


def test_fuller_version_of_a_point_grows_it_in_place():
    s, _ = merge(frame_slide("Brain", "Pons"), Piece("points", texts=("Connects the spinal cord",)))
    item_id = s.blocks[0].items[0].id
    s, left = merge(s, Piece("points", texts=("Connects the spinal cord, pons, and cerebral cortex",)))  # test13
    assert left is None and [(i.id, i.text) for i in s.blocks[0].items] == [
        (item_id, "Connects the spinal cord, pons, and cerebral cortex")]


# ---- item 6: formulas ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("spoken, latex", [
    ("Φ = hν₀ = hc/λ₀", r"\Phi = h \nu_{0} = \dfrac{h c}{\lambda_{0}}"),           # test15
    ("E = hν", r"E = h \nu"),
    ("Φ = h c / λ_T", r"\Phi = \dfrac{h c}{\lambda_{T}}"),
    ("Φ = h nu naught", r"\Phi = h \nu_{0}"),                                     # spoken subscript
    ("sin(θ) = opposite / hypotenuse", r"\sin \left(\theta\right) = \dfrac{\text{opposite}}{\text{hypotenuse}}"),
    ("f(x) = a_0/2 + ...", r"f \left(x\right) = \dfrac{a_{0}}{2} + \cdots"),      # test23 rendered nothing
    ("Δx = v Δt", r"\Delta x = v \Delta t"),                                      # unchanged
    ("x = A sin ωt", r"x = A \sin \omega t"),
])
def test_formula_symbols(spoken, latex):
    assert to_latex(spoken) == latex


# ---- item 7: layouts -------------------------------------------------------------------------------------------
def test_named_groups_said_as_points_are_group_cards():
    p, = pieces("classification", label="Main combatant groups", points=[
        "Central Powers: Germany, Austria, Hungary, Turkey",
        "Allied Powers: France, Great Britain, Prussia, Italy, Japan, United States"])           # test7
    assert p.kind == "groups" and p.groups[0] == ("Central Powers", ("Germany", "Austria", "Hungary", "Turkey"))


def test_short_attributes_with_numbers_are_fact_tiles():
    ps = pieces("explanation", points=["Distance: 240 miles", "Initial followers: 78",
                                       "Targeted British Salt Monopoly"])                         # test6
    assert [p.kind for p in ps] == ["facts", "points"]
    assert ps[0].pairs == (("Distance", "240 miles"), ("Initial followers", "78"))


def test_one_labelled_line_stays_a_point():
    p, = pieces("explanation", points=["Distance: 240 miles", "Gandhi led the march"])
    assert p.kind == "points"


def test_kinds_each_described_are_member_cards():
    ps = pieces("classification", points=["Star: Devices connect to a central switch or hub",
                                          "Bus: Devices share a common communication backbone"])   # test24
    assert [(p.kind, p.term) for p in ps] == [("definition", "Star"), ("definition", "Bus")]
    # a description with commas is not a list of names (test28)
    ps = pieces("classification", points=["Tropical: warm year-round, often heavy rainfall",
                                          "Dry: limited precipitation, includes many deserts"])
    assert [p.kind for p in ps] == ["definition", "definition"]


def test_explanation_with_labels_stays_points():
    p, = pieces("explanation", points=["Probability 0: Impossible event", "Probability 1: Certain event"])  # test23
    assert p.kind == "points"


def test_timeline_keeps_dated_events_only():
    ps = pieces("timeline", events=[TimedEvent(when="12 March 1930", what="March started from Sabarmati Ashram"),
                                    TimedEvent(when="Distance", what="240 miles")])
    assert [p.kind for p in ps] == ["timeline", "points"]
    assert ps[0].pairs == (("12 March 1930", "March started from Sabarmati Ashram"),)


def test_fuller_list_said_again_adds_to_its_group_card():
    s, _ = merge(frame_slide("World War 1", "Overview"), pieces("classification", label="Main combatant groups", points=[
        "Central Powers: Germany, Austria, Hungary, Turkey",
        "Allied Powers: France, Great Britain, Prussia, Italy, Japan"])[0])
    s, left = merge(s, Piece("points", texts=("Allied Powers: France, Great Britain, Prussia, Italy, Japan, United "
                                              "States",)))                                     # test7
    groups = {g.label: [i.text for i in g.items] for b in s.blocks if b.type == "groups" for g in b.groups}
    assert left is None and groups["Allied Powers"][-1] == "United States"
    assert not any(b.type == "points" for b in s.blocks)


def test_example_about_a_definition_stays_with_its_card():
    from copilot.presentation.composer import _split
    from copilot.presentation.spec import DefinitionBlock, ExampleBlock, Item, PointsBlock
    d = DefinitionBlock(term="Atom", definition="the smallest particle of an element")
    own = ExampleBlock(text="Molecule example: O3 (triatomic)", about=d.id)       # test3: drawn twice before
    other = ExampleBlock(text="NH3 (heteroatomic)")
    main, aside = _split([PointsBlock(items=[Item(text="Atomic theory proposed in 1803")]), d, own, other])
    assert own in main and own not in aside and aside == [other]
