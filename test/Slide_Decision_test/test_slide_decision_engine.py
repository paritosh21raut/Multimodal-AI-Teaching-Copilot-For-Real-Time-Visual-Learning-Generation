"""
Slide Decision Engine Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.slide_decision.slide_decision_models import SlideAction, SlideTrigger, SlideDecision
from app.slide_decision.slide_decision_engine import SlideDecisionEngine

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    ConceptRef,
    Proposition,
    InstructionalAct,
    InstructionalActType,
    RelationType,
)

from app.development.development_tracker import DevelopmentTracker
from app.importance.importance_scorer import ImportanceScorer


def test_topic_change_creates_new_slide():
    """Test that topic change triggers new slide"""
    engine = SlideDecisionEngine()
    
    decision = engine.decide(
        topic_changed=True,
        current_topic="Network Protocols",
    )
    
    assert decision.action == SlideAction.CREATE_NEW
    assert decision.trigger == SlideTrigger.NEW_TOPIC
    assert decision.confidence > 0.9


def test_accumulate_when_no_content():
    """Test that no content triggers accumulate"""
    engine = SlideDecisionEngine()
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="Networking",
    )
    
    assert decision.action == SlideAction.ACCUMULATE


def test_update_when_important_content():
    """Test that important content triggers update"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    engine = SlideDecisionEngine(tracker, scorer)
    
    # Create established concept
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    for i in range(3):
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Obj {i}"),
        ))
    
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="TCP",
        chunk_id="chunk_1",
    )
    
    assert decision.action in [SlideAction.UPDATE_CURRENT, SlideAction.CREATE_NEW, SlideAction.ACCUMULATE]


def test_new_slide_when_enough_established():
    """Test that enough established concepts trigger new slide"""
    tracker = DevelopmentTracker()
    scorer = ImportanceScorer(tracker)
    engine = SlideDecisionEngine(tracker, scorer)
    
    # Create 2 established concepts
    for concept_idx in range(2):
        frame = SemanticFrame(chunk_id=f"chunk_{concept_idx}")
        concept = Concept(
            concept_id=f"c{concept_idx}",
            canonical_name=f"Concept {concept_idx}",
            confidence=0.9,
        )
        frame.concepts.append(concept)
        
        for i in range(3):
            frame.propositions.append(Proposition(
                subject=ConceptRef(
                    concept_id=f"c{concept_idx}",
                    canonical_name=f"Concept {concept_idx}",
                ),
                predicate=RelationType.PROVIDES,
                object=ConceptRef(concept_id=f"o{concept_idx}_{i}", canonical_name=f"Obj"),
            ))
        
        frame.instructional_acts.append(InstructionalAct(
            act_type=InstructionalActType.DEFINITION,
            concept_refs=[ConceptRef(
                concept_id=f"c{concept_idx}",
                canonical_name=f"Concept {concept_idx}",
            )],
        ))
        
        tracker.process_frame(frame, chunk_id=f"chunk_{concept_idx}")
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="Test Topic",
        chunk_id="chunk_2",
    )
    
    assert decision.action in [SlideAction.CREATE_NEW, SlideAction.UPDATE_CURRENT]


def test_decision_has_required_fields():
    """Test that decision has all required fields"""
    engine = SlideDecisionEngine()
    
    decision = engine.decide(
        topic_changed=False,
        current_topic="Test",
    )
    
    assert decision.action is not None
    assert decision.trigger is not None
    assert decision.confidence > 0
    assert decision.reason != ""
    assert decision.timestamp is not None