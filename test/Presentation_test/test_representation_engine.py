"""
Representation Engine - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import RepresentationType
from app.presentation.representation.representation_engine import RepresentationEngine

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


def create_frame_with_relation(relation_type, source="A", target="B"):
    """Helper to create frame with specific relation"""
    frame = SemanticFrame(chunk_id="test")
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="s1", canonical_name=source),
        target=ConceptRef(concept_id="t1", canonical_name=target),
        relation_type=relation_type,
        confidence=0.9,
    ))
    return frame


def create_frame_with_act(act_type, concept_name="TCP"):
    """Helper to create frame with instructional act"""
    frame = SemanticFrame(chunk_id="test")
    frame.instructional_acts.append(InstructionalAct(
        act_type=act_type,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name=concept_name)],
    ))
    return frame


# EASY TESTS

def test_definition_relation():
    """Easy: DEFINED_AS → DEFINITION"""
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.DEFINED_AS)
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.DEFINITION


def test_contrast_relation():
    """Easy: CONTRASTS_WITH → CONTRAST"""
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.CONTRASTS_WITH, "TCP", "UDP")
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.CONTRAST


def test_process_relation():
    """Easy: PRECEDES → FLOWCHART"""
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.PRECEDES, "Step1", "Step2")
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.FLOWCHART


# MEDIUM TESTS

def test_definition_act():
    """Medium: DEFINITION act → DEFINITION"""
    engine = RepresentationEngine()
    frame = create_frame_with_act(InstructionalActType.DEFINITION)
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.DEFINITION


def test_example_act():
    """Medium: EXAMPLE act → EXAMPLE_GRID"""
    engine = RepresentationEngine()
    frame = create_frame_with_act(InstructionalActType.EXAMPLE)
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.EXAMPLE_GRID


def test_process_act():
    """Medium: PROCESS act → FLOWCHART"""
    engine = RepresentationEngine()
    frame = create_frame_with_act(InstructionalActType.PROCESS)
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.FLOWCHART


def test_causal_relation():
    """Medium: CAUSES → CAUSAL_CHAIN"""
    engine = RepresentationEngine()
    frame = create_frame_with_relation(RelationType.CAUSES, "Cause", "Effect")
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.CAUSAL_CHAIN


# HARD TESTS

def test_priority_definition_over_explanation():
    """Hard: Definition takes priority over explanation"""
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="test")
    
    # Both definition and general proposition
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


def test_priority_comparison_over_process():
    """Hard: Comparison takes priority over process"""
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="test")
    
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="s1", canonical_name="TCP"),
        target=ConceptRef(concept_id="t1", canonical_name="UDP"),
        relation_type=RelationType.CONTRASTS_WITH,
    ))
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="s2", canonical_name="Step1"),
        target=ConceptRef(concept_id="t2", canonical_name="Step2"),
        relation_type=RelationType.PRECEDES,
    ))
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.CONTRAST


def test_numeric_detection():
    """Hard: Numeric data detected"""
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="test")
    
    prop = Proposition(
        subject=ConceptRef(concept_id="s1", canonical_name="Speed"),
        predicate=RelationType.HAS_VALUE,
        object=ConceptRef(concept_id="o1", canonical_name="value"),
        quantities={"value": 299792458},
    )
    frame.propositions.append(prop)
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.NUMBER_STATISTIC


def test_empty_frame():
    """Hard: Empty frame defaults to explanation"""
    engine = RepresentationEngine()
    frame = SemanticFrame(chunk_id="empty")
    
    decision = engine.decide(frame)
    
    assert decision.representation_type == RepresentationType.EXPLANATION
    assert decision.confidence < 0.6


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Same relations work for any domain"""
    domains = {
        "networking": (RelationType.CONTRASTS_WITH, "TCP", "UDP"),
        "biology": (RelationType.PART_OF, "Mitochondria", "Cell"),
        "physics": (RelationType.CAUSES, "Force", "Acceleration"),
        "math": (RelationType.DEFINED_AS, "Derivative", "Rate of change"),
    }
    
    for domain, (rel_type, source, target) in domains.items():
        engine = RepresentationEngine()
        frame = create_frame_with_relation(rel_type, source, target)
        decision = engine.decide(frame)
        
        assert decision.representation_type != RepresentationType.NONE, f"Failed for {domain}"
        assert decision.confidence > 0.5, f"Low confidence for {domain}"