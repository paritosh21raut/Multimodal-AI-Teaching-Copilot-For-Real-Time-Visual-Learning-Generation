"""
Phase 3 topic identity propagation regression tests.

Covers:
- A: concise identity for definitional sentences
- B: later chunks must not mutate identity into accumulated transcript
- C: current_topic stable while context grows
- D: bridge propagates topic identity unchanged
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.topics.topic_intelligence import TopicIntelligence, StructuralDecision


def _engine() -> TopicIntelligence:
    return TopicIntelligence(
        model_name="all-MiniLM-L6-v2",
        new_topic_threshold=0.55,
        irrelevant_threshold=0.30,
        subtopic_threshold=0.45,
        centroid_update_weight=0.15,
    )


# --- A --------------------------------------------------------------

def test_cpu_scheduling_concise_identity():
    engine = _engine()
    d = engine.process(
        "CPU scheduling is the process of deciding which ready process gets the CPU next.",
    )
    assert d.is_relevant
    assert d.topic.lower() == "cpu scheduling"


def test_no_copula_still_concise_identity():
    """ASR may drop the copula: the anchor must still be concise."""
    engine = _engine()
    d = engine.process(
        "CPU scheduling process of deciding which ready process gets the CPU next.",
    )
    assert d.is_relevant
    # Must not contain " of " or a comma
    assert "," not in d.topic
    assert len(d.topic.split()) <= 5


# --- B --------------------------------------------------------------

def test_later_chunk_does_not_mutate_identity():
    engine = _engine()

    first = engine.process(
        "CPU scheduling is the process of deciding which ready process gets the CPU next.",
    )
    assert first.is_relevant

    second = engine.process(
        "The scheduler selects the next process based on priority.",
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )
    assert second.is_relevant
    # Topic identity must remain concise and not accumulate transcript text.
    assert len(second.topic.split()) <= 5
    assert "," not in second.topic
    assert second.topic.lower() == first.topic.lower()


# --- C --------------------------------------------------------------

def test_current_topic_stable_while_context_grows():
    engine = _engine()

    first = engine.process(
        "CPU scheduling is the process of deciding which ready process gets the CPU next.",
    )
    context = "CPU scheduling is the process of deciding which ready process gets the CPU next."

    for chunk in [
        "The scheduler selects the next process based on priority.",
        "Round robin assigns a fixed time slice.",
        "Priority scheduling picks the highest priority process.",
    ]:
        d = engine.process(
            chunk,
            rolling_context=context,
            current_topic=first.topic,
            current_embedding=first.embedding,
        )
        if d.is_relevant:
            context = f"{context} {chunk}"
            assert d.topic.lower() == first.topic.lower()


# --- D --------------------------------------------------------------

def test_discourse_only_chunk_does_not_become_trusted_topic():
    engine = _engine()

    first = engine.process(
        "CPU scheduling is the process of deciding which ready process gets the CPU next.",
    )
    assert first.is_relevant

    # Malformed ASR like "Next, we have feds. That" must not become a trusted
    # structural topic.
    second = engine.process(
        "Next, we have feds. That",
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )
    if second.structural_decision == StructuralDecision.NEW_MAJOR_TOPIC:
        assert second.topic.lower() not in ("next", "next,")
        assert len(second.topic.split()) <= 5
        assert "," not in second.topic


# --- E --------------------------------------------------------------

def test_bridge_propagates_topic_unchanged():
    """PresentationBridge must not rewrite the topic identity."""
    from app.presentation.bridge import PresentationBridge
    from app.semantic.semantic_models import (
        SemanticFrame, Concept, ConceptRef, Proposition, RelationType,
    )

    bridge = PresentationBridge()
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="CPU scheduling", confidence=0.9))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="CPU scheduling"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="throughput"),
        confidence=0.8,
    ))

    topic_in = "CPU scheduling"
    result = bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic=topic_in,
        important_concepts=["CPU scheduling"],
        authoritative_transcript="CPU scheduling is the process of deciding which ready process gets the CPU next.",
        chunk_id="c1",
    )

    # Bridge must not introduce a topic field with a rewritten identity.
    if "topic" in result:
        assert result["topic"] == topic_in