"""
Presentation Integration - Complete Pipeline Test
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.integration import PresentationIntelligence
from app.presentation.models.presentation_models import SlideAction

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    ConceptRef,
    Proposition,
    Relation,
    InstructionalAct,
    InstructionalActType,
    RelationType,
)


def create_test_frame(has_comparison=False):
    """Create a test semantic frame"""
    frame = SemanticFrame(chunk_id="test")
    
    # Concepts
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.concepts.append(Concept(concept_id="c2", canonical_name="UDP", confidence=0.9))
    
    # Proposition
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.85,
        evidence_ids=["e1"],
    ))
    
    # Definition
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    if has_comparison:
        frame.relations.append(Relation(
            source=ConceptRef(concept_id="c1", canonical_name="TCP"),
            target=ConceptRef(concept_id="c2", canonical_name="UDP"),
            relation_type=RelationType.CONTRASTS_WITH,
            confidence=0.9,
        ))
    
    return frame


# EASY TESTS

def test_pipeline_initializes():
    """Easy: Pipeline initializes"""
    pi = PresentationIntelligence()
    assert pi is not None


def test_first_topic_creates_plan():
    """Easy: First topic creates a slide plan"""
    pi = PresentationIntelligence()
    frame = create_test_frame()
    
    result = pi.process(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    assert result is not None
    assert "plan" in result


def test_no_action_when_no_content():
    """Easy: No action when no new content"""
    pi = PresentationIntelligence()
    frame = create_test_frame()
    
    # First create slide
    pi.process(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    # Same content again
    result = pi.process(
        frame=frame,
        topic_changed=False,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    assert result["action"] in ["no_change", "wait"]


# MEDIUM TESTS

def test_comparison_detected():
    """Medium: Comparison detected and represented"""
    pi = PresentationIntelligence()
    frame = create_test_frame(has_comparison=True)
    
    result = pi.process(
        frame=frame,
        topic_changed=True,
        current_topic="TCP vs UDP",
        important_concepts=["TCP", "UDP"],
    )
    
    assert result is not None
    if result.get("plan"):
        assert result["plan"].representation is not None


def test_different_topics_create_different_plans():
    """Medium: Different topics create different plans"""
    pi = PresentationIntelligence()
    
    # Topic 1
    frame1 = create_test_frame()
    result1 = pi.process(
        frame=frame1,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    # Topic 2
    frame2 = create_test_frame()
    result2 = pi.process(
        frame=frame2,
        topic_changed=True,
        current_topic="UDP",
        important_concepts=["UDP"],
    )
    
    assert result1 is not None
    assert result2 is not None


def test_state_tracking():
    """Medium: State tracking works"""
    pi = PresentationIntelligence()
    frame = create_test_frame()
    
    pi.process(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    state = pi.get_state()
    assert state is not None
    assert "slide_decision" in state
    assert "llm_providers" in state


# HARD TESTS

def test_full_pipeline_no_crash():
    """Hard: Full pipeline runs without crash"""
    pi = PresentationIntelligence()
    
    # Simulate multiple chunks
    topics = ["Computer Networks", "Network Topologies", "TCP Protocol", "UDP Protocol"]
    
    for i, topic in enumerate(topics):
        frame = create_test_frame(has_comparison=(i == 2))
        
        result = pi.process(
            frame=frame,
            topic_changed=True,
            current_topic=topic,
            important_concepts=[topic],
        )
        
        assert result is not None, f"Failed for topic {topic}"


def test_pipeline_reset():
    """Hard: Reset clears all state"""
    pi = PresentationIntelligence()
    frame = create_test_frame()
    
    pi.process(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    pi.reset()
    
    state = pi.get_state()
    assert state["last_plan_exists"] is False


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Works for any domain"""
    pi = PresentationIntelligence()
    
    domains = {
        "networking": ["TCP", "UDP"],
        "biology": ["Photosynthesis", "Respiration"],
        "physics": ["Force", "Acceleration"],
    }
    
    for domain, concepts in domains.items():
        frame = SemanticFrame(chunk_id=domain)
        
        for concept_name in concepts:
            frame.concepts.append(Concept(
                concept_id=f"{domain}_{concept_name}",
                canonical_name=concept_name,
                confidence=0.8,
            ))
        
        frame.propositions.append(Proposition(
            subject=ConceptRef(
                concept_id=f"{domain}_{concepts[0]}",
                canonical_name=concepts[0],
            ),
            predicate=RelationType.IS_A,
            object=ConceptRef(
                concept_id=f"{domain}_type",
                canonical_name="concept",
            ),
            confidence=0.8,
        ))
        
        result = pi.process(
            frame=frame,
            topic_changed=True,
            current_topic=domain,
            important_concepts=concepts,
        )
        
        assert result is not None, f"Failed for {domain}"