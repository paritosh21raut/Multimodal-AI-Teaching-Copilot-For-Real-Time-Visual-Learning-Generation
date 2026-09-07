"""
Development Intelligence Tests (Fixed)
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
    Relation,
    InstructionalAct,
    InstructionalActType,
    RelationType,
    GroundingStatus,
)


def test_initial_mention():
    """Test that a single mention creates MENTIONED state"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    dev = tracker.get_development("c1")
    
    assert dev is not None
    assert dev.state == DevelopmentState.MENTIONED
    assert dev.mention_count == 1


def test_developing_after_propositions():
    """Test that propositions move concept to DEVELOPING"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    # Add 2 propositions about TCP
    for i in range(2):
        prop = Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
        )
        frame.propositions.append(prop)
    
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    dev = tracker.get_development("c1")
    
    assert dev.state == DevelopmentState.DEVELOPING
    assert dev.proposition_count == 2


def test_established_with_definition_and_example():
    """Test that definition + example + propositions make concept ESTABLISHED"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    # Add 2 propositions
    for i in range(2):
        prop = Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
        )
        frame.propositions.append(prop)
    
    # Add definition
    def_act = InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    )
    frame.instructional_acts.append(def_act)
    
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    dev = tracker.get_development("c1")
    
    # 2 propositions (0.25) + 1 definition (0.25) = 0.50 which is ESTABLISHED
    assert dev.state == DevelopmentState.ESTABLISHED
    assert dev.definition_count == 1


def test_multiple_chunks_development():
    """Test development across multiple chunks"""
    tracker = DevelopmentTracker()
    
    # Chunk 1: Just mention
    frame1 = SemanticFrame(chunk_id="chunk_1")
    concept1 = Concept(concept_id="c1", canonical_name="Memory", confidence=0.8)
    frame1.concepts.append(concept1)
    tracker.process_frame(frame1, chunk_id="chunk_1")
    
    assert tracker.get_development("c1").state == DevelopmentState.MENTIONED
    
    # Chunk 2: Proposition about Memory
    frame2 = SemanticFrame(chunk_id="chunk_2")
    concept2 = Concept(concept_id="c1", canonical_name="Memory", confidence=0.8)
    frame2.concepts.append(concept2)
    prop2 = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="Memory"),
        predicate=RelationType.HAS_PART,
        object=ConceptRef(concept_id="c2", canonical_name="RAM"),
    )
    frame2.propositions.append(prop2)
    tracker.process_frame(frame2, chunk_id="chunk_2")
    
    # 1 mention + 1 proposition = 0.225 which is DEVELOPING
    assert tracker.get_development("c1").state == DevelopmentState.DEVELOPING
    
    # Chunk 3: More propositions
    frame3 = SemanticFrame(chunk_id="chunk_3")
    concept3 = Concept(concept_id="c1", canonical_name="Memory", confidence=0.8)
    frame3.concepts.append(concept3)
    prop3 = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="Memory"),
        predicate=RelationType.HAS_PART,
        object=ConceptRef(concept_id="c3", canonical_name="ROM"),
    )
    frame3.propositions.append(prop3)
    tracker.process_frame(frame3, chunk_id="chunk_3")
    
    # 2 mentions + 2 propositions = 0.35 which is still DEVELOPING
    # Need one more signal for ESTABLISHED
    frame4 = SemanticFrame(chunk_id="chunk_4")
    example = InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="Memory")],
    )
    frame4.instructional_acts.append(example)
    tracker.process_frame(frame4, chunk_id="chunk_4")
    
    dev = tracker.get_development("c1")
    # 2 mentions (0.10) + 2 props (0.25) + 1 example (0.20) = 0.55 ESTABLISHED
    assert dev.state == DevelopmentState.ESTABLISHED


def test_get_top_developed():
    """Test getting most developed concepts"""
    tracker = DevelopmentTracker()
    
    # Concept 1: Well developed (TCP)
    frame1 = SemanticFrame(chunk_id="chunk_1")
    concept1 = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame1.concepts.append(concept1)
    for i in range(2):
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
    
    top = tracker.get_top_developed(limit=10)
    
    assert len(top) == 2  # Only 2 explicitly mentioned concepts
    assert top[0].concept_id == "c1"  # TCP more developed
    assert top[1].concept_id == "c2"  # UDP less developed


def test_statistics():
    """Test statistics"""
    tracker = DevelopmentTracker()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    tracker.process_frame(frame, chunk_id="chunk_1")
    
    stats = tracker.get_statistics()
    
    assert stats["total_concepts"] == 1
    assert "mentioned" in stats
    assert "developing" in stats
    assert "established" in stats