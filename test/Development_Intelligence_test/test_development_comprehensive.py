"""
Development Intelligence - Comprehensive Tests

Coverage: Easy → Medium → Hard → Adversarial → Generic
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.development.development_models import (
    DevelopmentState,
    DevelopmentEventType,
    ConceptDevelopment,
)

from app.development.development_tracker import DevelopmentTracker

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    ConceptRef,
    Proposition,
    InstructionalAct,
    InstructionalActType,
    RelationType,
)


# ============================================================
# EASY TESTS
# ============================================================

def test_single_mention_creates_mentioned():
    """Easy: Single mention = MENTIONED state"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    tracker.process_frame(frame, chunk_id="c1")
    assert tracker.get_development("x1").state == DevelopmentState.MENTIONED


def test_multiple_mentions_same_concept():
    """Easy: Same concept mentioned twice = still tracked"""
    tracker = DevelopmentTracker()
    
    for i in range(2):
        frame = SemanticFrame(chunk_id=f"c{i}")
        frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
        tracker.process_frame(frame, chunk_id=f"c{i}")
    
    dev = tracker.get_development("x1")
    assert dev.mention_count == 2


def test_proposition_adds_development():
    """Easy: Proposition about concept increases development"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="x1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("x1")
    assert dev.proposition_count == 1
    assert dev.state in [DevelopmentState.DEVELOPING, DevelopmentState.ESTABLISHED]


# ============================================================
# MEDIUM TESTS
# ============================================================

def test_definition_boosts_development():
    """Medium: Definition significantly boosts development"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="x1", canonical_name="TCP")],
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("x1")
    assert dev.definition_count == 1
    assert dev.development_score >= 0.25


def test_example_boosts_development():
    """Medium: Example boosts development"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="x1", canonical_name="TCP")],
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("x1")
    assert dev.example_count == 1


def test_multiple_chunks_accumulate():
    """Medium: Development accumulates across chunks"""
    tracker = DevelopmentTracker()
    
    # Chunk 1: Mention
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="x1", canonical_name="Memory"))
    tracker.process_frame(f1, chunk_id="c1")
    
    # Chunk 2: Proposition
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="x1", canonical_name="Memory"))
    f2.propositions.append(Proposition(
        subject=ConceptRef(concept_id="x1", canonical_name="Memory"),
        predicate=RelationType.HAS_PART,
        object=ConceptRef(concept_id="o1", canonical_name="RAM"),
    ))
    tracker.process_frame(f2, chunk_id="c2")
    
    # Chunk 3: More propositions
    f3 = SemanticFrame(chunk_id="c3")
    f3.concepts.append(Concept(concept_id="x1", canonical_name="Memory"))
    f3.propositions.append(Proposition(
        subject=ConceptRef(concept_id="x1", canonical_name="Memory"),
        predicate=RelationType.HAS_PART,
        object=ConceptRef(concept_id="o2", canonical_name="ROM"),
    ))
    tracker.process_frame(f3, chunk_id="c3")
    
    dev = tracker.get_development("x1")
    assert len(dev.distinct_chunks) == 3
    assert dev.proposition_count == 2
    assert dev.state == DevelopmentState.ESTABLISHED


# ============================================================
# HARD TESTS
# ============================================================

def test_full_development_lifecycle():
    """Hard: Full lifecycle: MENTIONED → DEVELOPING → ESTABLISHED"""
    tracker = DevelopmentTracker()
    
    # Phase 1: Just mention
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="x1", canonical_name="PID"))
    tracker.process_frame(f1, chunk_id="c1")
    assert tracker.get_development("x1").state == DevelopmentState.MENTIONED
    
    # Phase 2: Definition
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="x1", canonical_name="PID"))
    f2.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="x1", canonical_name="PID")],
    ))
    tracker.process_frame(f2, chunk_id="c2")
    
    # Phase 3: Propositions + Example
    f3 = SemanticFrame(chunk_id="c3")
    f3.concepts.append(Concept(concept_id="x1", canonical_name="PID"))
    for i in range(3):
        f3.propositions.append(Proposition(
            subject=ConceptRef(concept_id="x1", canonical_name="PID"),
            predicate=RelationType.USES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"component_{i}"),
        ))
    f3.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="x1", canonical_name="PID")],
    ))
    tracker.process_frame(f3, chunk_id="c3")
    
    dev = tracker.get_development("x1")
    assert dev.state in [DevelopmentState.ESTABLISHED, DevelopmentState.FULLY_EXPLAINED]
    assert dev.definition_count == 1
    assert dev.example_count == 1
    assert dev.proposition_count == 3


def test_ranking_correctly_orders_concepts():
    """Hard: Concepts ranked by development"""
    tracker = DevelopmentTracker()
    
    # Well developed
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="well", canonical_name="WellDeveloped"))
    for i in range(5):
        f1.propositions.append(Proposition(
            subject=ConceptRef(concept_id="well", canonical_name="WellDeveloped"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"obj_{i}"),
        ))
    tracker.process_frame(f1, chunk_id="c1")
    
    # Barely mentioned
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="barely", canonical_name="BarelyMentioned"))
    tracker.process_frame(f2, chunk_id="c2")
    
    top = tracker.get_top_developed(limit=10)
    
    assert top[0].concept_id == "well"
    assert top[-1].concept_id == "barely"


def test_concept_correction_preserves_history():
    """Hard: Correction doesn't lose development history"""
    tracker = DevelopmentTracker()
    
    # Initial development
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    f1.propositions.append(Proposition(
        subject=ConceptRef(concept_id="x1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="o1", canonical_name="connectionless"),
    ))
    tracker.process_frame(f1, chunk_id="c1")
    
    # Correction
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    f2.propositions.append(Proposition(
        subject=ConceptRef(concept_id="x1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="o2", canonical_name="connection-oriented"),
    ))
    tracker.process_frame(f2, chunk_id="c2")
    
    dev = tracker.get_development("x1")
    assert dev.proposition_count == 2  # Both tracked, not overwritten


# ============================================================
# ADVERSARIAL TESTS
# ============================================================

def test_empty_frame():
    """Adversarial: Empty frame doesn't crash"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="c1")
    tracker.process_frame(frame, chunk_id="c1")
    assert tracker.get_statistics()["total_concepts"] == 0


def test_duplicate_concepts_same_chunk():
    """Adversarial: Same concept twice in one chunk"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    frame.concepts.append(Concept(concept_id="x1", canonical_name="TCP"))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("x1")
    assert dev.mention_count == 2  # Both counted


def test_unknown_concept_id():
    """Adversarial: Query for non-existent concept"""
    tracker = DevelopmentTracker()
    assert tracker.get_development("nonexistent") is None


# ============================================================
# GENERIC TESTS (DOMAIN-AGNOSTIC)
# ============================================================

def test_works_across_domains():
    """Generic: Same logic works for any domain"""
    domains = {
        "networking": ["TCP", "UDP", "Router"],
        "biology": ["Photosynthesis", "Mitosis", "Chlorophyll"],
        "physics": ["Momentum", "Velocity", "Acceleration"],
        "math": ["Derivative", "Integral", "Limit"],
        "economics": ["Inflation", "GDP", "Supply"],
    }
    
    for domain, concepts in domains.items():
        tracker = DevelopmentTracker()
        frame = SemanticFrame(chunk_id=f"{domain}_1")
        for concept_name in concepts:
            frame.concepts.append(Concept(
                concept_id=f"{domain}_{concept_name}",
                canonical_name=concept_name,
            ))
        tracker.process_frame(frame, chunk_id=f"{domain}_1")
        
        stats = tracker.get_statistics()
        assert stats["total_concepts"] == len(concepts), f"Failed for {domain}"