"""
Phase 6: Representation Intelligence - Production Readiness Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.representation.representation_engine import RepresentationEngine
from app.presentation.models.presentation_models import RepresentationType

from app.semantic.semantic_models import (
    SemanticFrame, Concept, ConceptRef, Proposition, Relation,
    InstructionalAct, InstructionalActType, RelationType,
)


def create_frame_with_relation(rel_type, source="A", target="B"):
    frame = SemanticFrame(chunk_id="test")
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="s1", canonical_name=source),
        target=ConceptRef(concept_id="t1", canonical_name=target),
        relation_type=rel_type,
        confidence=0.9,
    ))
    return frame


def test_definition_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.DEFINED_AS, "TCP", "protocol")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.DEFINITION


def test_contrast_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.CONTRASTS_WITH, "TCP", "UDP")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.CONTRAST


def test_process_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.PRECEDES, "Step1", "Step2")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.FLOWCHART


def test_causal_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.CAUSES, "Cause", "Effect")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.CAUSAL_CHAIN


def test_hierarchy_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.PART_OF, "RAM", "Computer")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.HIERARCHY


def test_example_relation():
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.EXAMPLE_OF, "Arduino", "Microcontroller")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.EXAMPLE_GRID


def test_empty_frame_defaults_explanation():
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="empty")
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.EXPLANATION


def test_priority_definition_over_explanation():
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="test")
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="s1", canonical_name="TCP"),
        target=ConceptRef(concept_id="t1", canonical_name="protocol"),
        relation_type=RelationType.DEFINED_AS,
    ))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="s1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
    ))
    decision = engine.decide(frame)
    assert decision.representation_type == RepresentationType.DEFINITION


def test_works_across_domains():
    engine = RepresentationEngine()
    domains = {
        "networking": (RelationType.CONTRASTS_WITH, "TCP", "UDP"),
        "biology": (RelationType.PART_OF, "Mitochondria", "Cell"),
        "physics": (RelationType.CAUSES, "Force", "Acceleration"),
        "math": (RelationType.DEFINED_AS, "Derivative", "Rate"),
    }
    for domain, (rel, s, t) in domains.items():
        frame = create_frame_with_relation(rel, s, t)
        decision = engine.decide(frame)
        assert decision.representation_type != RepresentationType.NONE, f"Failed for {domain}"