"""F-007a: formula blocks carry KaTeX source + the spoken form; title grammar."""
from copilot.presentation.composer import block_height, frame_slide, is_plural, merge, slide_title, substitute
from copilot.presentation.content import FormulaData, Piece
from copilot.presentation.mathtext import to_latex


def formula(expr, variables=()):
    return Piece("formula", formula=FormulaData(expr, tuple(variables)))


def test_formula_block_has_latex_and_spoken_form():
    s, left = merge(frame_slide("Force and motion", "Newton's Second Law"),
                    formula("F = m × a", [("F", "force"), ("CO2", "carbon dioxide")]))
    assert left is None and s.layout == "formula"
    fb = s.blocks[0]
    assert fb.spoken == "F = m × a" and fb.latex == r"F = m \times a"
    assert [v.latex for v in fb.variables] == ["F", r"\text{CO}_{\text{2}}"]


def test_same_formula_again_is_a_duplicate():
    s, _ = merge(frame_slide("P", "Equation"), formula("CO2 + H2O -> C6H12O6 + O2"))
    s2, left = merge(s, formula("CO2 + H2O -> C6H12O6 + O2"))
    assert left is None and s2 == s


def test_substitution_edits_the_spoken_words_and_rebuilds_latex():
    """Truthful slides: "show as I said" swaps words in the formula; the LaTeX must follow, not be patched."""
    s, _ = merge(frame_slide("P", "Equation"), formula("6CO2 + 6H2O → C6H12O6 + 6O2"))
    fb = s.blocks[0]
    s2 = substitute(s, {fb.id}, "6H2O", "6H2")
    fb2 = s2.blocks[0]
    assert fb2.spoken == "6CO2 + 6H2 → C6H12O6 + 6O2"
    assert fb2.latex == to_latex(fb2.spoken) and r"\text{6}\,\text{H}_{\text{2}} \rightarrow" in fb2.latex


def test_unrenderable_formula_keeps_the_spoken_form():
    s, _ = merge(frame_slide("P", "Formula"), formula(r"\frac{a}{b"))
    fb = s.blocks[0]
    assert fb.latex == "" and fb.spoken == r"\frac{a}{b"
    assert block_height(fb) > 0


def test_fraction_is_taller():
    plain, _ = merge(frame_slide("P", "Formula"), formula("speed = distance × time"))
    frac, _ = merge(frame_slide("P", "Formula"), formula("speed = distance / time"))
    assert block_height(frac.blocks[0]) > block_height(plain.blocks[0])


def test_title_templates_agree_with_plural_topics():
    assert slide_title("Human body systems", "Definition") == "What are human body systems?"
    assert slide_title("Photosynthesis", "Definition") == "What is photosynthesis?"
    assert slide_title("Lenses", "How it works") == "How lenses work"
    assert slide_title("Physics", "Importance") == "Why physics matters"
    assert slide_title("Plants", "Requirements") == "What plants need"
    assert [is_plural(w) for w in ("gas", "glass", "virus", "analysis", "genetics", "planets")] == \
        [False, False, False, False, False, True]


def test_definition_of_a_plural_term():
    s, _ = merge(frame_slide("Chemistry", "Definition"),
                 Piece("definition", term="Compounds", definition="Substances made of two or more elements"))
    assert s.title == "What are compounds?"


def test_points_mentioning_the_defined_term_are_not_dropped():
    """Regression (found in the V1a physics lesson): a point containing the slide's term (>= 12 chars) counted as
    a duplicate of the term and vanished."""
    s, _ = merge(frame_slide("Force and Motion", "Acceleration"),
                 Piece("definition", term="Acceleration", definition="The rate of change of velocity"))
    s, _ = merge(s, formula("v = u + at", [("a", "acceleration")]))
    s2, left = merge(s, Piece("points", texts=("Unit of acceleration: metre per second squared",)))
    shown = [getattr(b, "text", "") for b in s2.blocks] + [i.text for b in s2.blocks if b.type == "points"
                                                           for i in b.items]
    assert left is not None or "Unit of acceleration: metre per second squared" in shown


def test_a_point_with_a_few_extra_words_is_still_a_duplicate():
    s, _ = merge(frame_slide("Plants", "Requirements"), Piece("points", texts=("Plants need sunlight",)))
    s2, left = merge(s, Piece("points", texts=("Plants need sunlight daily",)))
    assert left is None and s2 == s
