"""
Phase 3: Development Intelligence Hardening Tests

Covers:
- structured coverage -> stage projection
- repetition dedup
- low-confidence gating
- contradiction gating
- trajectory log
- topic anchor
- gap detection
- scalar compatibility
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.development.development_models import (
    DevelopmentState,
    CoverageDimension,
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
    PropositionLifecycle,
)


def _concept(cid: str = "c1", name: str = "TCP") -> Concept:
    return Concept(concept_id=cid, canonical_name=name, confidence=0.9)


def _prop(subj: str, pred: RelationType, obj: str, cid: str = "p1",
          confidence: float = 0.0,
          lifecycle: PropositionLifecycle = PropositionLifecycle.ACTIVE) -> Proposition:
    return Proposition(
        proposition_id=cid,
        subject=ConceptRef(concept_id=subj, canonical_name=subj),
        predicate=pred,
        object=ConceptRef(concept_id=obj, canonical_name=obj),
        confidence=confidence,
        lifecycle=lifecycle,
    )


def test_structured_progression():
    """Coverage → stage progression over multiple chunks"""
    tracker = DevelopmentTracker()

    # Chunk 1: mention only
    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(_concept())
    tracker.process_frame(f1, chunk_id="c1")
    assert tracker.get_development("c1").state == DevelopmentState.MENTIONED

    # Chunk 2: definition
    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(_concept())
    f2.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(f2, chunk_id="c2")

    # Chunk 3: mechanism
    f3 = SemanticFrame(chunk_id="c3")
    f3.concepts.append(_concept())
    f3.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.MECHANISM,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(f3, chunk_id="c3")

    # Chunk 4: example
    f4 = SemanticFrame(chunk_id="c4")
    f4.concepts.append(_concept())
    f4.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.EXAMPLE,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(f4, chunk_id="c4")

    dev = tracker.get_development("c1")
    assert dev.is_covered(CoverageDimension.INTRODUCED)
    assert dev.is_covered(CoverageDimension.DEFINED)
    assert dev.is_covered(CoverageDimension.MECHANISM_EXPLAINED)
    assert dev.is_covered(CoverageDimension.EXAMPLE_GIVEN)
    assert dev.state in [DevelopmentState.ESTABLISHED, DevelopmentState.FULLY_EXPLAINED]


def test_repetition_does_not_advance_coverage():
    """Identical proposition repeated must not add new coverage"""
    tracker = DevelopmentTracker()
    dev = None

    for i in range(5):
        frame = SemanticFrame(chunk_id=f"c{i}")
        frame.concepts.append(_concept())
        frame.propositions.append(_prop("c1", RelationType.PROVIDES, "reliability",
                                       cid="same_prop"))
        tracker.process_frame(frame, chunk_id=f"c{i}")

    dev = tracker.get_development("c1")
    # Only one unique proposition signature counted
    assert dev.proposition_count == 1
    # Coverage dimensions reflect single EXPLAINED signal
    assert dev.is_covered(CoverageDimension.EXPLAINED)
    # Trajectory should have exactly one EXPLAINED entry
    explained_entries = [t for t in dev.trajectory if t["dimension"] == "explained"]
    assert len(explained_entries) == 1


def test_trajectory_logged():
    """Trajectory records ordered coverage events"""
    tracker = DevelopmentTracker()

    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(_concept())
    tracker.process_frame(f1, chunk_id="c1")

    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(_concept())
    f2.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(f2, chunk_id="c2")

    traj = tracker.get_trajectory("c1")
    assert len(traj) == 2
    assert traj[0]["dimension"] == "introduced"
    assert traj[0]["chunk_id"] == "c1"
    assert traj[1]["dimension"] == "defined"
    assert traj[1]["chunk_id"] == "c2"


def test_low_confidence_gated():
    """Evidence with 0 < confidence < 0.30 must not advance coverage"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
        confidence=0.10,
    ))
    frame.propositions.append(_prop("c1", RelationType.PROVIDES, "x",
                                    cid="lowconf", confidence=0.10))
    tracker.process_frame(frame, chunk_id="c1")

    dev = tracker.get_development("c1")
    assert not dev.is_covered(CoverageDimension.DEFINED)
    assert dev.proposition_count == 0


def test_contradicted_proposition_gated():
    """Contradicted/superseded propositions must not advance development"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    frame.propositions.append(_prop(
        "c1", RelationType.PROVIDES, "x",
        cid="contra",
        lifecycle=PropositionLifecycle.CONTRADICTED,
    ))
    tracker.process_frame(frame, chunk_id="c1")

    dev = tracker.get_development("c1")
    assert dev.proposition_count == 0
    assert not dev.is_covered(CoverageDimension.EXPLAINED)


def test_topic_anchor():
    """Topic node id is propagated to development records"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    tracker.process_frame(frame, chunk_id="c1", topic_node_id=42)

    dev = tracker.get_development("c1")
    assert dev.topic_node_id == 42
    assert dev.first_seen_topic_id == 42
    assert dev.last_seen_topic_id == 42


def test_topic_anchor_updates_on_return():
    """Return to previous topic updates last_seen_topic_id, preserves first"""
    tracker = DevelopmentTracker()

    f1 = SemanticFrame(chunk_id="c1")
    f1.concepts.append(_concept())
    tracker.process_frame(f1, chunk_id="c1", topic_node_id=1)

    f2 = SemanticFrame(chunk_id="c2")
    f2.concepts.append(_concept())
    tracker.process_frame(f2, chunk_id="c2", topic_node_id=2)

    dev = tracker.get_development("c1")
    assert dev.first_seen_topic_id == 1
    assert dev.last_seen_topic_id == 2


def test_gap_detection():
    """Gaps expose missing dimensions"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    frame.instructional_acts.append(InstructionalAct(
        act_type=InstructionalActType.DEFINITION,
        concept_refs=[ConceptRef(concept_id="c1", canonical_name="TCP")],
    ))
    tracker.process_frame(frame, chunk_id="c1")

    gaps = tracker.get_gaps("c1")
    assert "example_given" in gaps
    assert "application_given" in gaps


def test_scalar_matches_structured_state():
    """Scalar cannot exceed its structured stage thresholds"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    tracker.process_frame(frame, chunk_id="c1")

    dev = tracker.get_development("c1")
    assert dev.state == DevelopmentState.MENTIONED
    assert dev.development_score < tracker.DEVELOPING_THRESHOLD

    # Add many mentions only
    for i in range(10):
        f = SemanticFrame(chunk_id=f"mc{i}")
        f.concepts.append(_concept())
        tracker.process_frame(f, chunk_id=f"mc{i}")

    dev = tracker.get_development("c1")
    # Even with 11 mentions, mention component is capped - no EXPLAINED coverage
    assert not dev.is_covered(CoverageDimension.EXPLAINED)
    assert dev.state != DevelopmentState.FULLY_EXPLAINED


def test_reset_clears_state():
    """reset() must clear all development records"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    tracker.process_frame(frame, chunk_id="c1")

    assert tracker.get_development("c1") is not None
    tracker.reset()
    assert tracker.get_development("c1") is None
    assert tracker.get_statistics()["total_concepts"] == 0


def test_coverage_report_contains_phase3_fields():
    """get_coverage_report exposes trajectory and topic anchor"""
    tracker = DevelopmentTracker()

    frame = SemanticFrame(chunk_id="c1")
    frame.concepts.append(_concept())
    tracker.process_frame(frame, chunk_id="c1", topic_node_id=7)

    report = tracker.get_coverage_report("c1")
    assert "trajectory" in report
    assert "topic_node_id" in report
    assert report["topic_node_id"] == 7
    assert len(report["trajectory"]) >= 1