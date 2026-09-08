"""
Presentation Bridge - Complete Integration Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.bridge import PresentationBridge

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


def create_test_frame():
    """Create a test semantic frame"""
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.85,
        evidence_ids=["e1"],
    ))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    return frame


# EASY TESTS

def test_bridge_initializes():
    """Easy: Bridge initializes"""
    bridge = PresentationBridge()
    assert bridge is not None


def test_bridge_processes_frame():
    """Easy: Bridge processes frame"""
    bridge = PresentationBridge()
    frame = create_test_frame()
    
    result = bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    assert result is not None


def test_bridge_tracks_slide_count():
    """Easy: Bridge tracks slide count"""
    bridge = PresentationBridge()
    frame = create_test_frame()
    
    bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    state = bridge.get_state()
    assert state["current_slide"] >= 0


# MEDIUM TESTS

def test_bridge_dashboard_updates():
    """Medium: Dashboard updated with data"""
    bridge = PresentationBridge()
    frame = create_test_frame()
    
    bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    dashboard = bridge.get_dashboard_state()
    assert dashboard is not None


def test_bridge_no_action_when_same_content():
    """Medium: No action for duplicate content"""
    bridge = PresentationBridge()
    frame = create_test_frame()
    
    # First
    bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    # Duplicate
    result = bridge.process_transcript(
        frame=frame,
        topic_changed=False,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    assert result["action"] in ["no_change", "wait"]


# HARD TESTS

def test_bridge_full_pipeline_no_crash():
    """Hard: Full pipeline runs multiple topics"""
    bridge = PresentationBridge()
    
    topics = ["Computer Networks", "TCP Protocol", "UDP Protocol"]
    
    for i, topic in enumerate(topics):
        frame = create_test_frame()
        result = bridge.process_transcript(
            frame=frame,
            topic_changed=(i > 0),  # Topic change after first
            current_topic=topic,
            important_concepts=[topic],
        )
        
        assert result is not None, f"Failed for {topic}"


def test_bridge_reset():
    """Hard: Reset clears everything"""
    bridge = PresentationBridge()
    frame = create_test_frame()
    
    bridge.process_transcript(
        frame=frame,
        topic_changed=True,
        current_topic="TCP",
        important_concepts=["TCP"],
    )
    
    bridge.reset()
    
    state = bridge.get_state()
    assert state["current_slide"] == 0
    assert state["total_slides"] == 0


# GENERIC TESTS

def test_bridge_works_across_domains():
    """Generic: Bridge works for any domain"""
    bridge = PresentationBridge()
    
    domains = {
        "networking": "TCP",
        "biology": "Photosynthesis",
        "physics": "Momentum",
    }
    
    for domain, concept_name in domains.items():
        frame = SemanticFrame(chunk_id=domain)
        frame.concepts.append(Concept(
            concept_id=f"{domain}_c1",
            canonical_name=concept_name,
            confidence=0.8,
        ))
        frame.propositions.append(Proposition(
            subject=ConceptRef(
                concept_id=f"{domain}_c1",
                canonical_name=concept_name,
            ),
            predicate=RelationType.IS_A,
            object=ConceptRef(
                concept_id=f"{domain}_type",
                canonical_name="concept",
            ),
            confidence=0.8,
        ))
        
        result = bridge.process_transcript(
            frame=frame,
            topic_changed=True,
            current_topic=domain,
            important_concepts=[concept_name],
        )
        
        assert result is not None, f"Failed for {domain}"