"""
Information Selector - Updated Contract Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import SelectedInformation, SemanticEvidence
from app.presentation.information_selection.information_selector import InformationSelector

from app.semantic.semantic_models import (
    SemanticFrame, Concept, ConceptRef, Proposition,
    InstructionalAct, InstructionalActType, RelationType,
)


def create_test_frame():
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.concepts.append(Concept(concept_id="c2", canonical_name="UDP", confidence=0.9))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c3", canonical_name="protocol"),
        confidence=0.9, evidence_ids=["e1"],
    ))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c4", canonical_name="reliability"),
        confidence=0.85, evidence_ids=["e2"],
    ))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    return frame


def test_selects_focal_claim():
    selector = InformationSelector()
    frame = create_test_frame()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert selection.focal_claim is not None
    assert isinstance(selection.focal_claim, SemanticEvidence)


def test_selects_propositions():
    selector = InformationSelector()
    frame = create_test_frame()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) >= 1
    assert isinstance(selection.semantic_units[0], SemanticEvidence)


def test_selects_definitions():
    selector = InformationSelector()
    frame = create_test_frame()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.definitions) >= 1


def test_prioritizes_important_concepts():
    selector = InformationSelector()
    frame = create_test_frame()
    selection = selector.select(frame, important_concepts=["TCP"])
    # Focal claim involves TCP
    assert selection.focal_claim.subject == "TCP"


def test_limits_selection():
    selector = InformationSelector(max_semantic_units=2)
    frame = create_test_frame()
    for i in range(10):
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id=f"s{i}", canonical_name=f"Subject {i}"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Object {i}"),
            confidence=0.8,
        ))
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) <= 2


def test_no_duplicate_display():
    selector = InformationSelector()
    frame = create_test_frame()
    s1 = selector.select(frame, important_concepts=["TCP"])
    s2 = selector.select(frame, important_concepts=["TCP"])
    assert len(s2.semantic_units) <= len(s1.semantic_units)


def test_empty_frame_returns_empty_selection():
    selector = InformationSelector()
    frame = SemanticFrame(chunk_id="empty")
    selection = selector.select(frame)
    assert selection is not None
    assert selection.focal_claim is None
    assert len(selection.semantic_units) == 0


def test_low_confidence_filtered():
    selector = InformationSelector(min_confidence=0.7)
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP"))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.3,
    ))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="o2", canonical_name="protocol"),
        confidence=0.9,
    ))
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) == 1


def test_reset_displayed_units():
    selector = InformationSelector()
    frame = create_test_frame()
    selector.select(frame, important_concepts=["TCP"])
    selector.reset_displayed_units()
    selection = selector.select(frame, important_concepts=["TCP"])
    assert len(selection.semantic_units) >= 1


def test_works_across_domains():
    selector = InformationSelector()
    domains = {
        "networking": ["TCP", "UDP"],
        "biology": ["Photosynthesis", "Mitosis"],
        "physics": ["Force", "Momentum"],
    }
    for domain, concepts in domains.items():
        frame = SemanticFrame(chunk_id=domain)
        for c in concepts:
            frame.concepts.append(Concept(concept_id=f"{domain}_{c}", canonical_name=c, confidence=0.8))
        frame.propositions.append(Proposition(
            subject=ConceptRef(concept_id=f"{domain}_{concepts[0]}", canonical_name=concepts[0]),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id=f"{domain}_type", canonical_name="concept"),
            confidence=0.8,
        ))
        selection = selector.select(frame, important_concepts=concepts)
        assert selection is not None, f"Failed for {domain}"