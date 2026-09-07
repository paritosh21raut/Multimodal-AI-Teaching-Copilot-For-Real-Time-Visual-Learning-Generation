"""
Representation Engine Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.representation.representation_models import (
    VisualRepresentation,
    ContentType,
    RepresentationDecision,
)

from app.representation.representation_engine import RepresentationEngine

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


def test_definition_no_visual():
    """Test that definition gets no visual"""
    engine = RepresentationEngine()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    frame.concepts.append(concept)
    
    act = InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    )
    frame.instructional_acts.append(act)
    
    decision = engine.decide(frame)
    
    assert decision.visual_type == VisualRepresentation.NONE
    assert decision.content_type == ContentType.DEFINITION


def test_comparison_gets_table():
    """Test that comparison gets table"""
    engine = RepresentationEngine()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept1 = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    concept2 = Concept(concept_id="c2", canonical_name="UDP", confidence=0.9)
    frame.concepts.append(concept1)
    frame.concepts.append(concept2)
    
    act = InstructionalAct(
        act_type=InstructionalActType.COMPARISON,
        concept_refs=[
            ConceptRef(concept_id="c1", canonical_name="TCP"),
            ConceptRef(concept_id="c2", canonical_name="UDP"),
        ],
    )
    frame.instructional_acts.append(act)
    
    decision = engine.decide(frame)
    
    assert decision.visual_type == VisualRepresentation.COMPARISON_TABLE
    assert decision.content_type == ContentType.COMPARISON


def test_process_gets_flowchart():
    """Test that process gets flowchart"""
    engine = RepresentationEngine()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    
    act = InstructionalAct(
        act_type=InstructionalActType.PROCESS,
        concept_refs=[],
    )
    frame.instructional_acts.append(act)
    
    decision = engine.decide(frame)
    
    assert decision.visual_type == VisualRepresentation.FLOWCHART


def test_decision_has_spec():
    """Test that comparison decision has spec"""
    engine = RepresentationEngine()
    
    frame = SemanticFrame(chunk_id="chunk_1")
    concept1 = Concept(concept_id="c1", canonical_name="TCP", confidence=0.9)
    concept2 = Concept(concept_id="c2", canonical_name="UDP", confidence=0.9)
    frame.concepts.append(concept1)
    frame.concepts.append(concept2)
    
    relation = Relation(
        source=ConceptRef(concept_id="c1", canonical_name="TCP"),
        target=ConceptRef(concept_id="c2", canonical_name="UDP"),
        relation_type=RelationType.CONTRASTS_WITH,
    )
    frame.relations.append(relation)
    
    decision = engine.decide(frame)
    
    assert decision.visual_spec is not None