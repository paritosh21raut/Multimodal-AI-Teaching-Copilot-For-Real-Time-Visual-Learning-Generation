"""
Phase 2: Structured Coverage Tests (FIXED)

Fixed test expectations:
- Coverage dimensions use lowercase values (enum .value)
- More coverage signals needed for ESTABLISHED state
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.development.development_models import (
    DevelopmentState,
    CoverageDimension,
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
)


def create_frame_with_definition():
    """Frame with a definition"""
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    return frame


def test_definition_marks_defined():
    """Easy: Definition marks DEFINED dimension"""
    tracker = DevelopmentTracker()
    frame = create_frame_with_definition()
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("c1")
    assert dev.is_covered(CoverageDimension.DEFINED)
    assert dev.is_covered(CoverageDimension.INTRODUCED)


def test_example_marks_example_given():
    """Easy: Example marks EXAMPLE_GIVEN"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("c1")
    assert dev.is_covered(CoverageDimension.EXAMPLE_GIVEN)


def test_relation_marks_mechanism():
    """Easy: CAUSES relation marks MECHANISM_EXPLAINED"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="Force", confidence=0.9))
    frame.relations.append(Relation(
        source=ConceptRef(concept_id="c1", canonical_name="Force"),
        target=ConceptRef(concept_id="o1", canonical_name="Acceleration"),
        relation_type=RelationType.CAUSES,
        confidence=0.8,
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("c1")
    assert dev.is_covered(CoverageDimension.MECHANISM_EXPLAINED)


def test_provides_marks_explained():
    """Easy: PROVIDES relation marks EXPLAINED"""
    tracker = DevelopmentTracker()
    frame = SemanticFrame(chunk_id="test")
    frame.concepts.append(Concept(concept_id="c1", canonical_name="TCP", confidence=0.9))
    frame.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="o1", canonical_name="reliability"),
        confidence=0.8,
    ))
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("c1")
    assert dev.is_covered(CoverageDimension.EXPLAINED)


def test_full_coverage_report():
    """Medium: Coverage report shows covered and missing dimensions (lowercase values)"""
    tracker = DevelopmentTracker()
    frame = create_frame_with_definition()
    tracker.process_frame(frame, chunk_id="c1")
    
    report = tracker.get_coverage_report("c1")
    assert report["concept"] == "TCP"
    # Coverage report uses .value which is lowercase
    assert "defined" in report["covered_dimensions"]
    assert "example_given" in report["missing_dimensions"]


def test_state_progression():
    """Hard: State progresses with MORE coverage signals"""
    tracker = DevelopmentTracker()
    
    # Just mention
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(Concept(concept_id="c1", canonical_name="Memory", confidence=0.8))
    tracker.process_frame(f1, chunk_id="c1")
    assert tracker.get_development("c1").state == DevelopmentState.MENTIONED
    
    # Add definition + example + proposition + relation to get enough coverage
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(Concept(concept_id="c1", canonical_name="Memory", confidence=0.8))
    
    # Definition
    f2.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="Memory")],
    ))
    
    # Example
    f2.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="Memory")],
    ))
    
    # Proposition with HAS_PART (structure)
    f2.propositions.append(Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="Memory"),
        predicate=RelationType.HAS_PART,
        object=ConceptRef(concept_id="o1", canonical_name="RAM"),
        confidence=0.8,
    ))
    
    # Relation with CAUSES (mechanism)
    f2.relations.append(Relation(
        source=ConceptRef(concept_id="c1", canonical_name="Memory"),
        target=ConceptRef(concept_id="o2", canonical_name="Performance"),
        relation_type=RelationType.CAUSES,
        confidence=0.8,
    ))
    
    tracker.process_frame(f2, chunk_id="c2")
    
    state = tracker.get_development("c1").state
    assert state in [DevelopmentState.DEVELOPING, DevelopmentState.ESTABLISHED, DevelopmentState.FULLY_EXPLAINED]
    
    # Add MORE to push to ESTABLISHED
    f3 = SemanticFrame(chunk_id="c3")
    f3.concepts.append(Concept(concept_id="c1", canonical_name="Memory", confidence=0.8))
    
    # More propositions
    for i in range(3):
        f3.propositions.append(Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="Memory"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id=f"o{i}", canonical_name=f"Benefit {i}"),
            confidence=0.8,
        ))
    
    # More relations
    f3.relations.append(Relation(
        source=ConceptRef(concept_id="c1", canonical_name="Memory"),
        target=ConceptRef(concept_id="o3", canonical_name="Speed"),
        relation_type=RelationType.USED_FOR,
        confidence=0.8,
    ))
    
    # Comparison
    f3.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.COMPARISON,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="Memory")],
    ))
    
    tracker.process_frame(f3, chunk_id="c3")
    
    final_state = tracker.get_development("c1").state
    assert final_state in [DevelopmentState.ESTABLISHED, DevelopmentState.FULLY_EXPLAINED]


def test_coverage_percentage():
    """Medium: Coverage percentage calculated correctly"""
    tracker = DevelopmentTracker()
    frame = create_frame_with_definition()
    tracker.process_frame(frame, chunk_id="c1")
    
    dev = tracker.get_development("c1")
    pct = dev.coverage_percentage()
    
    # 2 dimensions covered out of 17 total
    assert 0.0 < pct < 0.3