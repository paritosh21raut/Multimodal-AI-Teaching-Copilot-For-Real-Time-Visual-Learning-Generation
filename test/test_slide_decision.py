from __future__ import annotations

from app.slide_decision.slide_decision_context import SlideDecisionContext
from app.slide_decision.slide_decision_engine import SlideDecisionEngine
from app.slide_decision.slide_decision_types import SlideDecisionAction


def _ctx(**overrides):
    base = dict(
        chunk_id="c",
        chunk_text="A capacitor stores electrical energy.",
        lsi_relation="continuation",
        lsi_is_new_topic=False,
        lsi_is_new_subtopic=False,
        lsi_is_return=False,
        lsi_topic="Capacitors",
        lsi_similarity=0.8,
        has_current_slide=True,
        current_slide_number=1,
        current_slide_topic="Capacitors",
        phase5_centrality="SUPPORTING",
        phase5_developmental_roles=["PROPERTY"],
        phase5_explicit_emphasis="NO",
        phase5_confidence=0.7,
        concept_label="capacitor",
        concept_first_seen=False,
        concept_prior_assertions_count=1,
        previous_decision=None,
        previous_topic=None,
    )
    base.update(overrides)
    return SlideDecisionContext(**base)


# ---------------- R1 / R2 / R3 ----------------

def test_empty_input_keeps():
    r = SlideDecisionEngine().decide(_ctx(chunk_text=""))
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value
    assert r.reason == "empty_or_invalid"


def test_lsi_irrelevant_keeps():
    r = SlideDecisionEngine().decide(_ctx(lsi_relation="irrelevant"))
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value
    assert r.reason == "lsi_irrelevant"


def test_incidental_keeps():
    r = SlideDecisionEngine().decide(
        _ctx(phase5_centrality="INCIDENTAL")
    )
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value
    assert r.reason == "incidental_content"


def test_meta_role_keeps_even_if_centrality_not_incidental():
    r = SlideDecisionEngine().decide(
        _ctx(
            phase5_centrality="SUPPORTING",
            phase5_developmental_roles=["META"],
        )
    )
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value
    assert r.reason == "meta_content"


# ---------------- R4 first slide ----------------

def test_first_topic_creates_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="new_topic",
            lsi_is_new_topic=True,
            has_current_slide=False,
            current_slide_number=None,
            current_slide_topic=None,
            phase5_centrality="CORE",
            phase5_developmental_roles=["INTRODUCTION"],
            concept_first_seen=True,
            concept_prior_assertions_count=0,
        )
    )
    assert r.decision == SlideDecisionAction.NEW_SLIDE.value
    assert r.reason == "first_slide"


# ---------------- R6 substantive new topic ----------------

def test_substantive_new_topic_creates_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="new_topic",
            lsi_is_new_topic=True,
            lsi_topic="Capacitor Charging",
            current_slide_topic="Capacitors",
            phase5_centrality="CORE",
            phase5_developmental_roles=["INTRODUCTION", "PROCEDURE"],
        )
    )
    assert r.decision == SlideDecisionAction.NEW_SLIDE.value
    assert r.reason == "substantive_new_topic"


def test_new_topic_without_phase5_does_not_create_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="new_topic",
            lsi_is_new_topic=True,
            lsi_topic="New Topic",
            current_slide_topic="Capacitors",
            phase5_centrality=None,
            phase5_developmental_roles=[],
        )
    )
    assert r.decision != SlideDecisionAction.NEW_SLIDE.value


# ---------------- R7 subtopic ----------------

def test_explicit_subtopic_core_creates_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="subtopic",
            lsi_is_new_subtopic=True,
            phase5_centrality="CORE",
        )
    )
    assert r.decision == SlideDecisionAction.NEW_SLIDE.value
    assert r.reason == "explicit_subtopic_introduction"


def test_subtopic_without_core_does_not_create_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="subtopic",
            lsi_is_new_subtopic=True,
            phase5_centrality="SUPPORTING",
        )
    )
    assert r.decision != SlideDecisionAction.NEW_SLIDE.value


# ---------------- R8 revised ----------------

def test_novel_concept_with_lsi_transition_creates_slide():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="new_topic",
            lsi_is_new_topic=True,
            lsi_topic="Microcontroller Architecture",
            current_slide_topic="Microcontrollers",
            phase5_centrality="CORE",
            concept_label="microcontroller architecture",
            concept_first_seen=True,
            concept_prior_assertions_count=0,
        )
    )
    assert r.decision == SlideDecisionAction.NEW_SLIDE.value
    assert r.reason in {
        "substantive_new_topic",
        "novel_concept_new_unit",
    }


def test_novel_concept_without_structural_corroboration_does_not_create():
    """Same topic, transition phrase but no new unit -> not NEW_SLIDE."""
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            lsi_topic="Capacitors",
            current_slide_topic="Capacitors",
            phase5_centrality="SUPPORTING",
            concept_label="capacitor",
            concept_first_seen=True,
            concept_prior_assertions_count=0,
        )
    )
    assert r.decision != SlideDecisionAction.NEW_SLIDE.value


def test_novel_concept_core_continuation_topic_separation_creates_slide():
    """
    R8 branch (b): CORE + continuation + low similarity + TOPIC SEPARATION.
    """
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            lsi_similarity=0.5,
            lsi_topic="Microcontroller Pins",
            current_slide_topic="Capacitors",
            phase5_centrality="CORE",
            concept_label="gpio",
            concept_first_seen=True,
            concept_prior_assertions_count=0,
        )
    )
    assert r.decision == SlideDecisionAction.NEW_SLIDE.value
    assert r.reason == "novel_concept_new_unit"


def test_novel_concept_core_continuation_same_topic_updates():
    """
    Boundary test protecting NEW CONCEPT != NEW SLIDE:
    same topic, novelty, CORE continuation, low similarity -> UPDATE.
    """
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            lsi_similarity=0.5,
            lsi_topic="Capacitors",
            current_slide_topic="Capacitors",
            phase5_centrality="CORE",
            concept_label="capacitor",
            concept_first_seen=True,
            concept_prior_assertions_count=0,
        )
    )
    assert r.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value
    assert r.reason == "develops_current_unit"


# ---------------- R9 develops current unit ----------------

def test_definition_of_current_concept_updates():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            phase5_centrality="SUPPORTING",
            phase5_developmental_roles=["DEFINITION"],
        )
    )
    assert r.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value


def test_property_updates():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            phase5_centrality="SUPPORTING",
            phase5_developmental_roles=["PROPERTY"],
        )
    )
    assert r.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value


def test_core_continuation_still_updates():
    """CORE does NOT imply NEW_SLIDE."""
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            phase5_centrality="CORE",
            concept_first_seen=False,
            concept_prior_assertions_count=1,
        )
    )
    assert r.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value


def test_process_step_updates():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="continuation",
            phase5_centrality="SUPPORTING",
            phase5_developmental_roles=["PROCEDURE"],
        )
    )
    assert r.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value


# ---------------- R10 fallback ----------------

def test_no_strong_signal_keeps():
    r = SlideDecisionEngine().decide(
        _ctx(
            lsi_relation="related",
            phase5_centrality="UNCERTAIN",
        )
    )
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value


# ---------------- fail-open ----------------

def test_empty_context_returns_keep_via_rule_path():
    """
    A context object with no chunk_text is treated as empty input by R1.
    This exercises the normal rule path, not the exception path.
    """
    engine = SlideDecisionEngine()

    class BadCtx:
        pass

    r = engine.decide(BadCtx())
    assert r.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value
    assert r.reason == "empty_or_invalid"


def test_engine_exception_is_fail_open():
    """
    Force a mid-rule exception: non-iterable developmental roles with a
    non-empty chunk. The engine must not raise and must route to its safe
    default, returning a valid decision.
    """
    engine = SlideDecisionEngine()

    class BadRolesCtx:
        chunk_text = "A capacitor stores electrical energy."
        phase5_developmental_roles = 12345  # non-iterable

    r = engine.decide(BadRolesCtx())
    assert r.decision in {
        SlideDecisionAction.KEEP_CURRENT_SLIDE.value,
        SlideDecisionAction.NEW_SLIDE.value,
        SlideDecisionAction.UPDATE_CURRENT_SLIDE.value,
    }
    assert r.reason.startswith("engine_exception:")

def test_engine_disabled_returns_safe_default():
    engine = SlideDecisionEngine(enabled=False)
    r = engine.decide(_ctx())
    assert r.reason == "engine_disabled"


# ---------------- sequence ----------------

def test_sequence_capacitor_lecture():
    engine = SlideDecisionEngine()

    # Chunk 1: first topic -> NEW_SLIDE
    r1 = engine.decide(_ctx(
        chunk_text="Today we will learn about capacitors.",
        lsi_relation="new_topic",
        lsi_is_new_topic=True,
        lsi_topic="Capacitors",
        has_current_slide=False,
        current_slide_number=None,
        current_slide_topic=None,
        phase5_centrality="CORE",
        phase5_developmental_roles=["INTRODUCTION"],
        concept_label="capacitor",
        concept_first_seen=True,
        concept_prior_assertions_count=0,
    ))
    assert r1.decision == SlideDecisionAction.NEW_SLIDE.value

    # Chunk 2: definition -> UPDATE
    r2 = engine.decide(_ctx(
        chunk_text="A capacitor stores electrical energy.",
        lsi_relation="continuation",
        lsi_topic="Capacitors",
        current_slide_topic="Capacitors",
        phase5_centrality="SUPPORTING",
        phase5_developmental_roles=["DEFINITION"],
        concept_first_seen=False,
        concept_prior_assertions_count=1,
        previous_decision=r1.decision,
        previous_topic="Capacitors",
    ))
    assert r2.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value

    # Chunk 3: property -> UPDATE (R5 removed; no duplicate false-positive)
    r3 = engine.decide(_ctx(
        chunk_text="It opposes sudden changes in voltage.",
        lsi_relation="continuation",
        lsi_topic="Capacitors",
        current_slide_topic="Capacitors",
        phase5_centrality="SUPPORTING",
        phase5_developmental_roles=["PROPERTY"],
        concept_first_seen=False,
        concept_prior_assertions_count=2,
        previous_decision=r2.decision,
        previous_topic="Capacitors",
    ))
    assert r3.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value

    # Chunk 4: new subtopic with explicit introduction -> NEW_SLIDE
    r4 = engine.decide(_ctx(
        chunk_text="Now let's learn about capacitor charging.",
        lsi_relation="subtopic",
        lsi_is_new_subtopic=True,
        lsi_topic="Capacitor Charging",
        current_slide_topic="Capacitors",
        phase5_centrality="CORE",
        phase5_developmental_roles=["INTRODUCTION"],
        concept_label="capacitor charging",
        concept_first_seen=True,
        concept_prior_assertions_count=0,
        previous_decision=r3.decision,
        previous_topic="Capacitors",
    ))
    assert r4.decision == SlideDecisionAction.NEW_SLIDE.value

    # Chunk 5: process step -> UPDATE
    r5 = engine.decide(_ctx(
        chunk_text="Current flows when connected to the source.",
        lsi_relation="continuation",
        lsi_topic="Capacitor Charging",
        current_slide_topic="Capacitor Charging",
        phase5_centrality="SUPPORTING",
        phase5_developmental_roles=["PROCEDURE"],
        concept_first_seen=False,
        concept_prior_assertions_count=1,
        previous_decision=r4.decision,
        previous_topic="Capacitor Charging",
    ))
    assert r5.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value

    # Chunk 6: mechanism -> UPDATE
    r6 = engine.decide(_ctx(
        chunk_text="The voltage rises exponentially.",
        lsi_relation="continuation",
        lsi_topic="Capacitor Charging",
        current_slide_topic="Capacitor Charging",
        phase5_centrality="SUPPORTING",
        phase5_developmental_roles=["MECHANISM"],
        concept_first_seen=False,
        concept_prior_assertions_count=2,
        previous_decision=r5.decision,
        previous_topic="Capacitor Charging",
    ))
    assert r6.decision == SlideDecisionAction.UPDATE_CURRENT_SLIDE.value


def test_sequence_incidental_does_not_create():
    engine = SlideDecisionEngine()

    r1 = engine.decide(_ctx(
        lsi_relation="new_topic",
        lsi_is_new_topic=True,
        has_current_slide=False,
        current_slide_number=None,
        current_slide_topic=None,
        phase5_centrality="CORE",
        phase5_developmental_roles=["INTRODUCTION"],
    ))
    assert r1.decision == SlideDecisionAction.NEW_SLIDE.value

    r2 = engine.decide(_ctx(
        chunk_text="By the way, the lab uses a 10 microfarad capacitor.",
        lsi_relation="continuation",
        lsi_topic="Capacitors",
        current_slide_topic="Capacitors",
        phase5_centrality="INCIDENTAL",
        phase5_developmental_roles=["META"],
        previous_decision=r1.decision,
        previous_topic="Capacitors",
    ))
    assert r2.decision == SlideDecisionAction.KEEP_CURRENT_SLIDE.value