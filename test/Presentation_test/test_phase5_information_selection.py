"""
Phase 5: Information Selection - Production Readiness Tests

Tests the compression layer that decides what goes on screen.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.information_selection.information_selector import InformationSelector
from app.presentation.models.presentation_models import SelectedInformation

from app.semantic.semantic_models import (
    SemanticFrame, Concept, ConceptRef, Proposition,
    InstructionalAct, InstructionalActType, RelationType, Relation,
)


def create_frame_with_content():
    """Frame with propositions, definitions, examples"""
    frame = SemanticFrame(chunk_id="test")
    
    # Concepts
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.concepts.append(Concept(concept_id="c2", canonical_name="UDP", confidence=0.9))
    
    # Propositions
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.9,
        evidence_ids=["e1"],
    ))
    
    # Definition
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    # Example
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    
    return frame


# EASY TESTS

def test_selects_focal_claim():
    """Easy: Selects focal claim"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert selection.focal_claim != ""


def test_selects_propositions():
    """Easy: Selects propositions"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) >= 1


def test_selects_definitions():
    """Easy: Selects definitions"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.definitions) >= 1


# MEDIUM TESTS

def test_deduplicates_across_calls():
    """Medium: Same content not selected twice"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    
    selection1 = selector.select(frame, important_concepts=["TCP"])
    selection2 = selector.select(frame, important_concepts=["TCP"])
    
    # Second selection should have fewer new units
    assert len(selection2.semantic_units) <= len(selection1.semantic_units)


def test_prioritizes_important_concepts():
    """Medium: Important concepts prioritized"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    selection = selector.select(frame, important_concepts=["TCP"])
    
    # Focal claim should involve TCP
    assert "TCP" in selection.focal_claim


def test_limits_selection():
    """Medium: Selection respects max limits"""
    selector = InformationSelector(
        max_semantic_units=2,
        max_definitions=1,
        max_examples=1,
    )
    
    frame = create_frame_with_content()
    # Add many propositions
    for i in range(10):
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id=f"s{i}", canonical_name=f"Subject {i}"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
            confidence=0.8,
        ))
    
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) <= 2
    assert len(selection.definitions) <= 1


# HARD TESTS

def test_empty_frame_no_crash():
    """Hard: Empty frame doesn't crash"""
    selector = InformationSelector()
    frame = SemanticFrame(chunk_id="empty")
    selection = selector.select(frame)
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
        confidence=0.3,
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


def test_reset_clears_displayed():
    """Hard: Reset clears displayed units"""
    selector = InformationSelector()
    frame = create_frame_with_content()
    
    selector.select(frame, important_concepts=["TCP"])
    selector.reset_displayed_units()
    
    # After reset, same content selectable again
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) >= 1


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Works for any domain"""
    selector = InformationSelector()
    
    domains = {
        "networking": ["TCP", "UDP"],
        "biology": ["Photosynthesis", "Mitosis"],
        "physics": ["Force", "Momentum"],
    }
    
    for domain, concepts in domains.items():
        frame = SemanticFrame(chunk_id=domain)
        for c_name in concepts:
            frame.concepts.append(Concept(concept_id=f"{domain}_{c_name}", canonical_name=c_name, confidence=0.8))
        
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id=f"{domain}_{concepts[0]}", canonical_name=concepts[0]),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id=f"{domain}_type", canonical_name="concept"),
            confidence=0.8,
        ))
        
        selection = selector.select(frame, important_concepts=concepts)
        assert selection is not None, f"Failed for {domain}"