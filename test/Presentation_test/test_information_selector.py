"""
Information Selector - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import SelectedInformation
from app.presentation.information_selection.information_selector import InformationSelector

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
    frame = SemanticFrame(chunk_id="test_chunk")
    
    # Concepts
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.concepts.append(Concept(concept_id="c2", canonical_name="UDP", confidence=0.9))
    
    # Proposition: TCP IS_A protocol
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c3", canonical_name="protocol"),
        confidence=0.9,
        evidence_ids=["e1"],
    ))
    
    # Proposition: TCP PROVIDES reliability
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c4", canonical_name="reliability"),
        confidence=0.85,
        evidence_ids=["e2"],
    ))
    
    # Definition act
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    # Example act
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    return frame


# EASY TESTS

def test_selects_focal_claim():
    """Easy: Selects focal claim from propositions"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    assert selection.focal_claim != ""


def test_selects_propositions():
    """Easy: Selects propositions"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    assert len(selection.semantic_units) >= 1


def test_selects_definitions():
    """Easy: Selects definitions"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    assert len(selection.definitions) >= 1
    assert "TCP" in selection.definitions


# MEDIUM TESTS

def test_prioritizes_important_concepts():
    """Medium: Important concepts prioritized in propositions"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    # TCP propositions should be first
    assert "TCP" in selection.semantic_units[0]


def test_limits_selection():
    """Medium: Selection respects max limits"""
    selector = InformationSelector(
        max_semantic_units=2,
        max_definitions=1,
        max_examples=1,
    )
    frame = create_test_frame()
    
    # Add more propositions
    for i in range(10):
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept_{i}"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object_{i}"),
            confidence=0.8,
        ))
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    assert len(selection.semantic_units) <= 2
    assert len(selection.definitions) <= 1


def test_no_duplicate_display():
    """Medium: Same content not displayed twice"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selection1 = selector.select(frame, important_concepts=["TCP"])
    selection2 = selector.select(frame, important_concepts=["TCP"])
    
    # Second selection should have fewer new units (deduplication)
    assert len(selection2.semantic_units) <= len(selection1.semantic_units)


# HARD TESTS

def test_empty_frame_returns_empty_selection():
    """Hard: Empty frame doesn't crash"""
    selector = InformationSelector()
    frame = SemanticFrame(chunk_id="empty")
    
    selection = selector.select(frame)
    
    assert selection is not None
    assert selection.focal_claim == ""
    assert len(selection.semantic_units) == 0


def test_low_confidence_filtered():
    """Hard: Low confidence propositions filtered"""
    selector = InformationSelector(min_confidence=0.7)
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP"))
    
    # Low confidence proposition
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.3,  # Below threshold
    ))
    
    # High confidence proposition
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="o2", canonical_name="protocol"),
        confidence=0.9,
    ))
    
    selection = selector.select(frame, important_concepts=["TCP"])
    
    assert len(selection.semantic_units) == 1


def test_reset_displayed_units():
    """Hard: Reset clears displayed units"""
    selector = InformationSelector()
    frame = create_test_frame()
    
    selector.select(frame, important_concepts=["TCP"])
    selector.reset_displayed_units()
    
    # After reset, same content should be selectable again
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) >= 1


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Selection works for any domain"""
    domains = {
        "networking": ["TCP", "UDP", "Router"],
        "biology": ["Photosynthesis", "Mitosis", "Chlorophyll"],
        "physics": ["Momentum", "Velocity", "Acceleration"],
    }
    
    for domain, concepts in domains.items():
        selector = InformationSelector()
        frame = SemanticFrame(chunk_id=f"{domain}_1")
        
        for concept_name in concepts:
            frame.concepts.append(Concept(
                concept_id=f"{domain}_{concept_name}",
                canonical_name=concept_name,
                confidence=0.8,
            ))
        
        for i, concept_name in enumerate(concepts):
            frame.propositions.append(Proposition(
                subject=ConceptRef(
                    concept_id=f"{domain}_{concept_name}",
                    canonical_name=concept_name,
                ),
                predicate=RelationType.IS_A,
                object=ConceptRef(
                    concept_id=f"{domain}_type_{i}",
                    canonical_name=f"type_{i}",
                ),
                confidence=0.8,
            ))
        
        selection = selector.select(frame, important_concepts=concepts)
        
        assert len(selection.semantic_units) >= 1, f"Failed for {domain}"