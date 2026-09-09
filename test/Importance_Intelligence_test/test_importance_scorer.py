"""
Importance Intelligence Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.importance.importance_models import ImportanceScore, ImportanceLevel
from app.importance.importance_scorer import ImportanceScorer

from app.development.development_tracker import DevelopmentTracker
from app.development.development_models import DevelopmentState

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    ConceptRef,
    Proposition,
    InstructionalAct,
    InstructionalActType,
    RelationType,
)


def test_low_importance_for_mention():
    """Test that a single mention has LOW importance"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    score = scorer.score_concept("c1", current_chunk_id="chunk_1")
    
    assert score is not None
    assert score.level == ImportanceLevel.LOW
    assert score.importance < 0.25


def test_high_importance_for_established():
    """Test that established concept has HIGH importance"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    # Add propositions
    for i in range(3):
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Obj {i}"),
        ))
    
    # Add definition
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    # Add example
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    score = scorer.score_concept("c1", current_chunk_id="chunk_1")
    
    assert score is not None
    assert score.level in [ImportanceLevel.HIGH, ImportanceLevel.CRITICAL]
    assert score.importance >= 0.50


def test_importance_ranking():
    """Test that concepts are ranked correctly"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    # Concept 1: Well developed (TCP)
    frame1 = SemanticFrame(chunk_id="chunk_1")
    concept1 = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame1.concepts.append(concept1)
    for i in range(3):
        frame1.propositions.append(Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Obj {i}"),
        ))
    tracker.process_frame(frame1, chunk_id="chunk_1")
    
    # Concept 2: Just mentioned (UDP)
    frame2 = SemanticFrame(chunk_id="chunk_2")
    concept2 = Concept(concept_id="c2", canonical_name="UDP", confidence=0.9)
    frame2.concepts.append(concept2)
    tracker.process_frame(frame2, chunk_id="chunk_2")
    
    scores = scorer.score_all_concepts()
    
    assert len(scores) == 2
    assert scores[0].concept_id == "c1"  # TCP more important
    assert scores[1].concept_id == "c2"  # UDP less important
    assert scores[0].rank == 1
    assert scores[1].rank == 2


def test_get_top_important():
    """Test getting top important concepts"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    # Create multiple concepts
    for i in range(5):
        frame = SemanticFrame(chunk_id=f"chunk_{i}")
        concept = Concept(
            concept_id=f"c{i}",
            canonical_name=f"Concept {i}",
            confidence=0.9,
        )
        frame.concepts.append(concept)
        
        # Add varying number of propositions
        for j in range(i + 1):
            frame.propositions.append(Proposition(
                subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}"),
                predicate=RelationType.PROVIDES,
                object=ConceptRef(concept_id=f"o{i}_{j}", canonical_name=f"Obj {i}_{j}"),
            ))
        
        tracker.process_frame(frame, chunk_id=f"chunk_{i}")
    
    top = scorer.get_top_important(limit=3)
    
    assert len(top) == 3
    # New scoring considers multiple factors - any well-developed concept can be top
    assert top[0].concept_id in ["c2", "c3", "c4"]
    assert top[0].importance >= top[1].importance


def test_statistics():
    """Test statistics"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    stats = scorer.get_statistics()
    
    assert stats["total_scored"] == 1
    assert "critical" in stats
    assert "high" in stats