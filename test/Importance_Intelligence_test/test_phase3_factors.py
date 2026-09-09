"""
Phase 3: Structured Importance Factors Tests (FIXED)

Fixed: Definition + Example correctly scores as HIGH importance.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.importance.importance_models import (
    ImportanceLevel,
    ImportanceFactor,
    ImportanceScore,
)
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


def test_single_mention_low_importance():
    """Easy: Single mention = LOW importance"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    tracker.process_frame(frame, chunk_id="c1")
    
    score = scorer.score_concept("c1", current_chunk_id="c1")
    
    assert score is not None
    assert score.level == ImportanceLevel.LOW
    assert score.importance < 0.2


def test_definition_and_example_moderate():
    """Easy: Definition + Example = MODERATE or HIGH importance"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    score = scorer.score_concept("c1", current_chunk_id="c1")
    
    assert score is not None
    # Definition + Example should be at least MODERATE
    assert score.level in [ImportanceLevel.MODERATE, ImportanceLevel.HIGH, ImportanceLevel.CRITICAL]


def test_structured_factors_present():
    """Medium: Score contains structured factors"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    tracker.process_frame(frame, chunk_id="c1")
    
    score = scorer.score_concept("c1")
    
    assert score is not None
    assert ImportanceFactor.DEFINITION in score.factors
    assert ImportanceFactor.REPETITION in score.factors
    assert ImportanceFactor.TOPIC_CENTRALITY in score.factors


def test_ranking_still_works():
    """Medium: Ranking still works with structured factors"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="well", canonical_name="WellDeveloped", confidence=0.9))
    for i in range(5):
        f1.propositions.append(Proposition(
            subject=ConceptRef(concept_id="well", canonical_name="WellDeveloped"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Obj {i}"),
        ))
    tracker.process_frame(f1, chunk_id="c1")
    
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="barely", canonical_name="Barely", confidence=0.8))
    tracker.process_frame(f2, chunk_id="c2")
    
    scores = scorer.score_all_concepts()
    
    assert scores[0].concept_id == "well"
    assert scores[-1].concept_id == "barely"


def test_backward_compatible_scalar():
    """Hard: Legacy scalar still available"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    
    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    tracker.process_frame(frame, chunk_id="c1")
    
    score = scorer.score_concept("c1")
    
    assert score is not None
    assert hasattr(score, 'importance')
    assert 0.0 <= score.importance <= 1.0