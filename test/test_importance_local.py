from __future__ import annotations

from app.importance.importance_types import (
    Centrality,
    DevelopmentalRole,
    Emphasis,
)
from app.importance.local_importance import (
    classify_structural_centrality,
    detect_developmental_roles,
    detect_explicit_emphasis,
)


# ---------------------------------------------------------- #
# EXPLICIT EMPHASIS
# ---------------------------------------------------------- #

def test_emphasis_yes_remember_this():
    val, ev = detect_explicit_emphasis(
        "Remember this: a capacitor stores electrical energy."
    )
    assert val == Emphasis.YES.value
    assert ev is not None and "remember this" in ev.lower()


def test_emphasis_yes_pay_attention():
    val, ev = detect_explicit_emphasis(
        "Pay close attention to the sign conventions."
    )
    assert val == Emphasis.YES.value
    assert ev is not None


def test_emphasis_yes_key_point():
    val, ev = detect_explicit_emphasis(
        "This is the key point: capacitors block DC."
    )
    assert val == Emphasis.YES.value


def test_emphasis_no_on_plain_assertion():
    val, ev = detect_explicit_emphasis(
        "A capacitor stores electrical energy in an electric field."
    )
    assert val == Emphasis.NO.value
    assert ev is None


# ---------------------------------------------------------- #
# DEVELOPMENTAL ROLES
# ---------------------------------------------------------- #

def test_role_definition():
    roles = detect_developmental_roles(
        "Recursion is defined as a function that calls itself."
    )
    assert DevelopmentalRole.DEFINITION.value in roles


def test_role_property():
    roles = detect_developmental_roles(
        "Another important property is that capacitors oppose sudden voltage changes."
    )
    assert DevelopmentalRole.PROPERTY.value in roles


def test_role_example():
    roles = detect_developmental_roles(
        "For example, you can find capacitors in power supplies."
    )
    assert DevelopmentalRole.EXAMPLE.value in roles


def test_role_application():
    roles = detect_developmental_roles(
        "Capacitors are used in power supplies to smooth the output voltage."
    )
    assert DevelopmentalRole.APPLICATION.value in roles


def test_role_procedure():
    roles = detect_developmental_roles(
        "First check whether n is zero, then multiply n by the factorial."
    )
    assert DevelopmentalRole.PROCEDURE.value in roles


def test_role_synthesis():
    roles = detect_developmental_roles(
        "In summary, recursion requires a base case and a reduction step."
    )
    assert DevelopmentalRole.SYNTHESIS.value in roles


def test_role_exception():
    roles = detect_developmental_roles(
        "Except when the recursion depth exceeds the stack size, the program crashes."
    )
    assert DevelopmentalRole.EXCEPTION.value in roles


def test_role_meta():
    roles = detect_developmental_roles("Now let's move on to inductors.")
    assert DevelopmentalRole.META.value in roles


def test_role_mechanism():
    roles = detect_developmental_roles(
        "A stack overflow happens when the base case is never reached."
    )
    assert DevelopmentalRole.MECHANISM.value in roles


def test_role_relationship():
    roles = detect_developmental_roles(
        "There is a well-known relationship between recursion and induction."
    )
    assert DevelopmentalRole.RELATIONSHIP.value in roles


def test_role_multilabel():
    roles = detect_developmental_roles(
        "For example, capacitors are used in power supplies."
    )
    assert DevelopmentalRole.EXAMPLE.value in roles
    assert DevelopmentalRole.APPLICATION.value in roles


# ---------------------------------------------------------- #
# ARCHITECT-REQUIRED FIX TESTS
# ---------------------------------------------------------- #

def test_intro_role_on_framing_phrase():
    """Test 5: 'We will learn about capacitors.' -> INTRODUCTION."""
    roles = detect_developmental_roles(
        "We will learn about capacitors.",
        lsi_relation="new_topic",
    )
    assert DevelopmentalRole.INTRODUCTION.value in roles


def test_intro_role_on_now_lets_learn():
    """Test 6: 'Now let's learn about capacitor charging.' -> INTRODUCTION."""
    roles = detect_developmental_roles(
        "Now let's learn about capacitor charging.",
        lsi_relation="new_topic",
    )
    assert DevelopmentalRole.INTRODUCTION.value in roles


def test_no_core_from_copular_is_a():
    """Test 1: Copular sentence must not become CORE from 'is a'."""
    val, reason = classify_structural_centrality(
        text="The capacitor is connected to the source.",
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=2,
        prior_assertions_for_concept=("stores energy",),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val != Centrality.CORE.value


def test_no_core_from_is_a_component():
    """Test 2: 'X is a Y' must not become CORE from 'is a'."""
    val, reason = classify_structural_centrality(
        text="The capacitor is a component used in circuits.",
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=2,
        prior_assertions_for_concept=("stores energy",),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val != Centrality.CORE.value


def test_property_emphasis_no_core_from_is():
    """Test 3: PROPERTY + emphasis YES, no CORE from 'is'."""
    text = (
        "An important property is that capacitors oppose sudden "
        "voltage changes."
    )
    val, _ = classify_structural_centrality(
        text=text,
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=2,
        prior_assertions_for_concept=("stores energy",),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val != Centrality.CORE.value

    roles = detect_developmental_roles(text, lsi_relation="continuation")
    assert DevelopmentalRole.PROPERTY.value in roles

    emphasis, _ = detect_explicit_emphasis(text)
    assert emphasis == Emphasis.YES.value


def test_no_core_on_lsi_continuation_first_mention_guess():
    """Test 4: continuation + first-mention guess must not produce CORE."""
    val, _ = classify_structural_centrality(
        text=(
            "First, the capacitor is connected to the source, "
            "then current flows and the capacitor voltage rises."
        ),
        concept_label="learn about capacitor",  # deliberately unmatched
        concept_first_seen=True,
        concept_mention_count=0,
        prior_assertions_for_concept=(),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val != Centrality.CORE.value


def test_high_confidence_definition_is_core():
    """Test 7: 'Capacitance is defined as...' -> CORE + DEFINITION."""
    text = "Capacitance is defined as the ratio of charge to voltage."
    val, _ = classify_structural_centrality(
        text=text,
        concept_label="capacitance",
        concept_first_seen=True,
        concept_mention_count=0,
        prior_assertions_for_concept=(),
        lsi_relation="new_topic",
        lsi_node_id="n1",
    )
    assert val == Centrality.CORE.value

    roles = detect_developmental_roles(text, lsi_relation="new_topic")
    assert DevelopmentalRole.DEFINITION.value in roles


def test_existing_concept_development_is_supporting():
    """Test 8: 'The capacitor voltage rises...' -> SUPPORTING."""
    val, _ = classify_structural_centrality(
        text="The capacitor voltage rises as charging continues.",
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=3,
        prior_assertions_for_concept=("stores energy",),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val == Centrality.SUPPORTING.value


def test_incidental_lab_value():
    """Test 9: 'By the way, our lab uses a 10 uF capacitor.' -> INCIDENTAL."""
    val, _ = classify_structural_centrality(
        text="By the way, our lab uses a 10 microfarad capacitor.",
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=3,
        prior_assertions_for_concept=("stores energy",),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val == Centrality.INCIDENTAL.value


def test_new_subconcept_can_still_be_core():
    """Test 10: continuation is not hard-coded to SUPPORTING.
    A new concept introduced under a new LSI structure can still be CORE."""
    val, _ = classify_structural_centrality(
        text="Capacitance is defined as the ratio of charge to voltage.",
        concept_label="capacitance",
        concept_first_seen=True,
        concept_mention_count=0,
        prior_assertions_for_concept=(),
        lsi_relation="subtopic",
        lsi_node_id="n2",
    )
    assert val == Centrality.CORE.value


# ---------------------------------------------------------- #
# PREVIOUSLY PASSING CENTRALITY TESTS (kept)
# ---------------------------------------------------------- #

def test_centrality_core_new_concept():
    val, _ = classify_structural_centrality(
        text="A capacitor stores electrical energy in an electric field.",
        concept_label="capacitor",
        concept_first_seen=True,
        concept_mention_count=1,
        prior_assertions_for_concept=(),
        lsi_relation="new_topic",
        lsi_node_id="n1",
    )
    assert val == Centrality.CORE.value


def test_centrality_supporting_already_introduced():
    val, _ = classify_structural_centrality(
        text="Capacitors oppose sudden voltage changes.",
        concept_label="capacitor",
        concept_first_seen=False,
        concept_mention_count=2,
        prior_assertions_for_concept=(
            "stores electrical energy in an electric field",
        ),
        lsi_relation="continuation",
        lsi_node_id="n1",
    )
    assert val == Centrality.SUPPORTING.value


def test_centrality_incidental_meta():
    val, _ = classify_structural_centrality(
        text="Now let's move on to inductors.",
        concept_label=None,
        concept_first_seen=False,
        concept_mention_count=0,
        prior_assertions_for_concept=(),
        lsi_relation="new_topic",
        lsi_node_id=None,
    )
    assert val == Centrality.INCIDENTAL.value


def test_centrality_does_not_fire_core_on_generic_incidental():
    val, _ = classify_structural_centrality(
        text="The CS building closes at five.",
        concept_label=None,
        concept_first_seen=False,
        concept_mention_count=0,
        prior_assertions_for_concept=(),
        lsi_relation="irrelevant",
        lsi_node_id=None,
    )
    assert val == Centrality.INCIDENTAL.value