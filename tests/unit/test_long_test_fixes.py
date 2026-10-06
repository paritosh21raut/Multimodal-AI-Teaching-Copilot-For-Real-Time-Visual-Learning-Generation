"""V1 long lecture test (user 2026-10-06, session 20261006-193517-c513, chemical bonding → gas laws, 18 min): the
content relations, titles, parts and formulas that came out wrong. Items are the model's answers from that session."""
from copilot.core.interpretation import ContentItems, DiscourseAct, Interpretation
from copilot.presentation.composer import body_height, fits, frame_slide, merge, revise_item, what_is
from copilot.presentation.content import FormulaData, Piece, pieces_and_chain, pieces_from
from copilot.presentation.mathtext import to_latex
from tests.unit.test_presentation_engine import act, make, ready, send, texts
from copilot.core.events import ConceptSignal


def interp(*acts, topic="Chemical Bonding", sub="Covalent Bond"):
    return Interpretation(topic=topic, subtopic=sub, relation="same_concept", acts=list(acts))


def a(kind, **items):
    return DiscourseAct(act=kind, lines=[1], items=ContentItems(**items))


def build(spec, pieces):
    left = []
    for p in pieces:
        spec, rest = merge(spec, p)
        if rest is not None:
            left.append(rest)
    return spec, left


def defs_of(spec):
    return [b.term for b in spec.blocks if b.type == "definition"]


def points_of(spec):
    return [i.text for b in spec.blocks if b.type == "points" for i in b.items]


# ---- a longer term is another concept ------------------------------------------------------------------------
def test_a_qualified_term_is_its_own_concept_not_a_point_of_the_shorter_one():
    """"Resonance hybrid" became a point under "Resonance", "Bond dissociation enthalpy" a point under "Bond
    enthalpy" (term lost), "Polar covalent bond" a point under "Non-polar covalent bond" (titles_match is meant for
    headings: one extra word = the same heading)."""
    s, left = build(frame_slide("Chemical Bonding", "Resonance"), pieces_from(interp(
        a("definition", term="Resonance", definition="A single Lewis structure cannot explain all molecular properties"),
        a("explanation", points=["Molecule has multiple structures", "Each structure explains most properties"]),
        a("definition", term="Resonance hybrid", definition="Actual structure lying between all contributing structures"),
        a("definition", term="Canonical structure",
          definition="Individual resonating structures contributing to the hybrid"))))
    assert not left and defs_of(s) == ["Resonance", "Resonance hybrid", "Canonical structure"]
    s, left = build(frame_slide("Chemical Bonding", "Bond Enthalpy"), pieces_from(interp(
        a("definition", term="Bond Enthalpy", definition="Energy released when one mole of covalent bonds forms"),
        a("definition", term="Bond Dissociation Enthalpy", definition="Energy required to break one mole of bonds"))))
    assert not left and defs_of(s) == ["Bond Enthalpy", "Bond Dissociation Enthalpy"]
    s, left = build(frame_slide("Chemical Bonding", "Covalent Bond"), pieces_from(interp(
        a("definition", term="Non-polar covalent bond", definition="Bond between atoms of exactly equal electronegativity"),
        a("definition", term="Polar covalent bond", definition="Bond between different atoms; shared pair displaced"))))
    assert not left and defs_of(s) == ["Non-polar covalent bond", "Polar covalent bond"]


def test_the_same_term_again_still_adds_its_text_as_a_point():
    s, _ = build(frame_slide("Chemical Bonding", "Ionic Bond"), pieces_from(interp(
        a("definition", term="Ionic Bond", definition="Bond formed by complete electron transfer"),
        a("definition", term="ionic bonds", definition="Formed between a metal and a non-metal"))))
    assert defs_of(s) == ["Ionic Bond"] and points_of(s) == ["Formed between a metal and a non-metal"]


def test_general_properties_after_a_member_do_not_go_into_its_card():
    """The properties of covalent compounds (next unit) went into the "Non-polar covalent bond" card, then onto a
    lonely "Non-polar covalent bond" slide ("Usually insoluble in water")."""
    s = frame_slide("Chemical Bonding", "Covalent Bond")
    u1 = interp(a("definition", term="Non-polar covalent bond",
                  definition="Covalent bond formed between two homonuclear atoms of exactly equal electronegativity",
                  examples=["H₂", "Cl₂"]))
    u2 = interp(a("definition", term="Polar covalent bond",
                  definition="Covalent bond between different atoms where shared pair is displaced towards the more "
                             "electronegative atom, developing ionic character", examples=["HCl"]))
    u3 = interp(a("explanation", points=["Exist as liquids or gases at room temperature",
                                         "Have low melting and boiling points"]))
    u4 = interp(a("explanation", points=["Poor conductors of electricity", "Lack free electrons or ions",
                                         "Soluble in non-polar solvents like benzene", "Usually insoluble in water"]))
    chain, overflow = "", []
    for u in (u1, u2, u3, u4):
        pieces, chain = pieces_and_chain(u, chain)
        s, left = build(s, pieces)
        overflow += left  # what does not fit continues on the next part (the engine's job)
    by_id = {b.id: b for b in s.blocks}
    general = [b for b in s.blocks if b.type == "points" and not b.about]
    assert defs_of(s) == ["Non-polar covalent bond", "Polar covalent bond"]
    shown = [i.text for b in general for i in b.items] + [t for p in overflow for t in p.texts]
    from copilot.presentation.composer import member_of
    assert all(p.kind == "points" and member_of(s, p) is None for p in overflow)  # no lonely member slide either
    assert shown == [
        "Exist as liquids or gases at room temperature", "Have low melting and boiling points",
        "Poor conductors of electricity", "Lack free electrons or ions", "Soluble in non-polar solvents like benzene",
        "Usually insoluble in water"]
    in_cards = {by_id[b.about].term: [i.text for i in b.items] for b in s.blocks if b.type == "points" and b.about}
    assert in_cards == {"Non-polar covalent bond": ["H₂", "Cl₂"], "Polar covalent bond": ["HCl"]}


def test_short_example_like_items_still_follow_the_concept_into_the_next_unit():
    s, _ = build(frame_slide("Energy", "Kinetic and Potential Energy"), [
        Piece("definition", term="Kinetic energy", definition="energy of motion", about="Kinetic energy"),
        Piece("definition", term="Potential energy", definition="stored energy", about="Potential energy")])
    _, chain = pieces_and_chain(interp(a("definition", term="Kinetic energy", definition="energy of motion")))
    p, _ = pieces_and_chain(interp(a("explanation", points=["rolling ball", "running person"])), chain)
    assert p[0].about  # still carried: short items are examples of the concept just named


# ---- lists, trees and nonsense lines -------------------------------------------------------------------------
def test_labelled_properties_are_a_list_with_a_heading_not_a_tree():
    """"Characteristics of ionic compounds" was drawn as a classification tree."""
    ps = pieces_from(interp(a("explanation", label="Characteristics of ionic compounds",
                              points=["Usually solid in nature", "High melting and boiling points", "Soluble in water"])))
    assert [(p.kind, p.term) for p in ps] == [("points", "Characteristics of ionic compounds")]
    tree = pieces_from(interp(a("classification", label="Types of covalent bond",
                                points=["Non-polar covalent bond", "Polar covalent bond"])))
    assert [p.kind for p in tree] == ["tree"]


def test_a_one_item_types_announcement_is_not_shown():
    """"Types of molecular velocities: Most probable velocity" became a lone note card."""
    assert pieces_from(interp(a("classification", label="Types of molecular velocities",
                                points=["Most probable velocity"]))) == []


def test_lines_that_only_repeat_the_term_are_dropped():
    assert pieces_from(interp(a("definition", term="Electron pairs", definition="Known as electron pairs"))) == []
    assert pieces_from(interp(a("explanation", points=["Bond angle is also known as Bond Angle"]))) == []
    p = pieces_from(interp(a("definition", term="Bond angle",
                             definition="Angle formed between bonds in a molecule (also called Bond Angle)")))
    assert p[0].definition == "Angle formed between bonds in a molecule"


def test_a_revision_does_not_repeat_the_term_or_its_alias_in_the_definition():
    s, _ = merge(frame_slide("Chemical Bonding", "Ionic Bond"), Piece(
        "definition", term="Ionic Bond", definition="Chemical bond formed by complete electron transfer"))
    d = s.blocks[0]
    s2 = revise_item(s, d.id, "Ionic Bond (Electrovalent Bond): Chemical bond formed by complete electron transfer "
                              "from metal to non-metal")
    assert s2.blocks[0].definition == "Chemical bond formed by complete electron transfer from metal to non-metal"
    s, _ = merge(frame_slide("Chemical Bonding", "Covalent Bond"), Piece(
        "definition", term="Bond angle", definition="Angle formed between bonds in a multi-atom covalent molecule"))
    s3 = revise_item(s, s.blocks[0].id, "Bond angle: Angle formed between bonds in a multi-atom covalent molecule "
                                        "(also called Bond Angle)")
    assert s3.blocks[0].definition == "Angle formed between bonds in a multi-atom covalent molecule"


def test_a_value_given_as_a_definition_is_a_fact():
    """"1 Debye (SI)" = "3.33564 × 10⁻³⁰ Coulomb-meter" was a definition card with a huge heading."""
    p = pieces_from(interp(a("definition", term="1 Debye (SI)", definition="3.33564 × 10⁻³⁰ Coulomb-meter")))
    assert [(x.kind, x.pairs) for x in p] == [("facts", (("1 Debye (SI)", "3.33564 × 10⁻³⁰ Coulomb-meter"),))]


def test_a_shorter_point_with_only_words_of_an_existing_one_is_not_added():
    s, _ = merge(frame_slide("Chemical Bonding", "Covalent Bond"), Piece(
        "points", texts=("Formed by end-to-end overlap of half-filled orbitals with opposite spin",
                         "It is based on the wave nature of electrons")))
    s2, left = merge(s, Piece("points", texts=("Formed by end-to-end overlap of orbitals",)))
    assert left is None and points_of(s2) == points_of(s)
    s3, _ = merge(s, Piece("points", texts=("Sigma bond strength depends on orbital overlap extent",)))
    assert len(points_of(s3)) == 3  # new words: a new point


# ---- a term defined below other content: a card on the same slide ------------------------------------------
def test_terms_defined_after_other_content_are_cards_on_the_same_slide():
    """Intermolecular forces: a definition + 2 points, then three terms → a part II with only the three cards
    (part I two thirds empty); States of matter: "Melting point" as a giant heading."""
    s, left = build(frame_slide("Chemical Bonding", "Intermolecular Forces"), pieces_from(interp(
        a("definition", term="Intermolecular forces", definition="Forces of attraction existing among molecules of a "
                                                                  "substance"),
        a("explanation", points=["Greater intermolecular force leads to higher melting and boiling points",
                                 "Attractive intermolecular forces are known as Van der Waals forces"]))))
    for term, d in (("Dipole-induced dipole forces", "Attraction between a polar molecule and a non-polar molecule"),
                    ("Hydrogen bond", "Special case of dipole-dipole interaction in molecules with N-H, O-H or H-F"),
                    ("Thermal energy", "Energy arising from the motion of atoms in a body")):
        s, rest = merge(s, Piece("definition", term=term, definition=d))
        assert rest is None, term
    assert [b.type for b in s.blocks] == ["definition", "points", "definition", "definition", "definition"]
    assert fits(s) and body_height(s) > 600  # the three cards are counted


def test_a_point_naming_a_card_goes_into_it():
    s, _ = build(frame_slide("Chemical Bonding", "Covalent Bond"), [
        Piece("points", texts=("Poor conductors of electricity", "Usually insoluble in water")),
        Piece("definition", term="Bond length", definition="Distance between the nuclei of two covalently bonded atoms"),
        Piece("points", texts=("Bond length increases with larger atom size",)),
        Piece("points", texts=("Covalent compounds are usually soft",))])
    card = next(b for b in s.blocks if b.type == "definition")
    assert [[i.text for i in b.items] for b in s.blocks if b.type == "points" and b.about == card.id] == [
        ["Bond length increases with larger atom size"]]
    assert points_of(s)[-1] == "Covalent compounds are usually soft" or "Covalent compounds are usually soft" in \
        [i.text for b in s.blocks if b.type == "points" and not b.about for i in b.items]


def test_one_card_after_a_formula_keeps_the_cases_that_follow_it():
    """Regression found by the old/new replay of the multitopic test (411e): the discriminant's cases (the next
    unit, one misheard as "Discrement") split off into a lonely part II."""
    s, _ = build(frame_slide("Quadratic Equations", "Formula"), [
        Piece("formula", formula=FormulaData("x = (-b ± √(b² - 4ac)) / 2a")),
        Piece("definition", term="Discriminant", definition="The expression b² - 4ac inside the square root")])
    _, chain = pieces_and_chain(interp(a("definition", term="Discriminant", definition="b² - 4ac")))
    p, _ = pieces_and_chain(interp(a("explanation", points=["Discrement is less than zero",
                                                            "Two complex imaginary roots are formed"])), chain)
    s, left = build(s, p)
    card = next(b for b in s.blocks if b.type == "definition")
    assert not left and [i.text for b in s.blocks if b.type == "points" and b.about == card.id for i in b.items] == [
        "Discrement is less than zero", "Two complex imaginary roots are formed"]


# ---- titles and parts ----------------------------------------------------------------------------------------
def test_what_is_titles_keep_names_and_grammar():
    # Title Case stays as said: names cannot be told from words ("French Revolution"; old replay of 998d)
    assert what_is("Boyle's Law") == "What is Boyle's Law?"
    assert what_is("Kinetic Theory of Gases") == "What is Kinetic Theory of Gases?"
    assert what_is("Chemical Bond") == "What is Chemical Bond?"
    assert what_is("French Revolution") == "What is French Revolution?"
    assert what_is("Dipole moment") == "What is dipole moment?"
    assert what_is("Human body systems") == "What are human body systems?"
    assert what_is("DNA") == "What is DNA?"


async def test_a_frame_taken_up_again_numbers_its_parts_from_one():
    """Covalent Bond had parts I-IV; after Dipole Moment the teacher came back to it: the new run showed I, then V."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    long = [f"Covalent bond fact number {i} with a fairly long explanation attached to it" for i in range(12)]
    await send(bus, ready("Chemical Bonding", "Covalent Bond", [act("explanation", points=long)], relation="new_topic"))
    first_run = len(deck.slides)
    assert first_run >= 2
    r = ready("Dipole Moment", "", [act("explanation", points=["Product of charge and distance"])], relation="new_topic")
    await send(bus, ConceptSignal(segment_id=r.segment_ids[0], shift_score=0.4, boundary=True), r)
    more = [f"Valence bond theory statement {i} with a fairly long explanation attached" for i in range(12)]
    r2 = ready("Chemical Bonding", "Covalent Bond", [act("explanation", points=more)], relation="new_topic")
    await send(bus, ConceptSignal(segment_id=r2.segment_ids[0], shift_score=0.4, boundary=True), r2)
    again = deck.slides[first_run + 1:]
    assert len(again) >= 2 and [s.part for s in again] == list(range(1, len(again) + 1))
    assert sum(len(texts(s)) for s in again) == 12
    await eng.stop()


# ---- formulas --------------------------------------------------------------------------------------------------
def test_numbered_variables_are_subscripts():
    """"P₁V₁ = P₂V₂" showed as "P1V1 = P₂V₂" (the left side as one upright word)."""
    assert to_latex("P₁V₁ = P₂V₂") == to_latex("P_1V_1 = P_2V_2") == "P_{1} V_{1} = P_{2} V_{2}"
    assert to_latex("P1V1 = P2V2") == "P_{1} V_{1} = P_{2} V_{2}"
    assert to_latex("6CO2 + 6H2O → C6H12O6 + 6O2").count(r"\text") > 4  # chemistry stays chemistry
    assert to_latex("V1/T1 = V2/T2") == "\\dfrac{V_{1}}{T_{1}} = \\dfrac{V_{2}}{T_{2}}"  # unchanged
