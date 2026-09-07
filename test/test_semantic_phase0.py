"""
Phase 0 Tests: Semantic Models and State Management

Tests the core data structures and state management without
requiring any external dependencies or other subsystems.
"""

from __future__ import annotations

import pytest
from datetime import datetime

from app.semantic.semantic_models import (
    SemanticFrame,
    SemanticEvent,
    SemanticEventLog,
    Concept,
    ConceptRef,  # Added this import
    Proposition,
    Relation,
    EvidenceSpan,
    Mention,
    Confidence,
    GroundingStatus,
    ExtractionStatus,
    PropositionLifecycle,
    RelationType,
    SemanticEventType
)

from app.semantic.semantic_state import SemanticState
from app.semantic.evidence import EvidenceManager


# ============================================================
# EVIDENCE SPAN TESTS
# ============================================================

def test_evidence_span_creation():
    """Test evidence span creation and serialization"""
    evidence = EvidenceSpan(
        chunk_id="chunk_1",
        text="TCP provides reliable delivery",
        start_char=0,
        end_char=29,
        asr_confidence=0.95
    )

    assert evidence.evidence_id != ""
    assert evidence.chunk_id == "chunk_1"
    assert evidence.text == "TCP provides reliable delivery"
    assert evidence.asr_confidence == 0.95

    # Test serialization
    data = evidence.to_dict()
    assert data["evidence_id"] == evidence.evidence_id
    assert data["chunk_id"] == "chunk_1"

    # Test deserialization
    restored = EvidenceSpan.from_dict(data)
    assert restored.evidence_id == evidence.evidence_id
    assert restored.text == evidence.text


# ============================================================
# CONCEPT TESTS
# ============================================================

def test_concept_creation():
    """Test concept creation with aliases"""
    concept = Concept(
        canonical_name="TCP",
        aliases=["Transmission Control Protocol", "tcp"],
        confidence=0.95,
        concept_type="protocol"
    )

    assert concept.concept_id != ""
    assert concept.canonical_name == "TCP"
    assert "Transmission Control Protocol" in concept.aliases
    assert concept.confidence == 0.95


def test_concept_serialization():
    """Test concept serialization round-trip"""
    concept = Concept(
        canonical_name="TCP",
        aliases=["Transmission Control Protocol"],
        confidence=0.9
    )

    data = concept.to_dict()
    assert data["canonical_name"] == "TCP"
    assert "Transmission Control Protocol" in data["aliases"]


# ============================================================
# PROPOSITION TESTS
# ============================================================

def test_proposition_creation():
    """Test proposition creation"""
    subject = ConceptRef(concept_id="concept_1", canonical_name="TCP")
    obj = ConceptRef(concept_id="concept_2", canonical_name="reliable delivery")

    prop = Proposition(
        subject=subject,
        predicate=RelationType.PROVIDES,
        object=obj,
        evidence_ids=["evidence_1"],
        confidence=0.85,
        grounding_status=GroundingStatus.EXPLICIT,
        extraction_status=ExtractionStatus.COMPLETE
    )

    assert prop.subject.canonical_name == "TCP"
    assert prop.predicate == RelationType.PROVIDES
    assert prop.object.canonical_name == "reliable delivery"
    assert "evidence_1" in prop.evidence_ids


def test_proposition_lifecycle():
    """Test proposition lifecycle transitions"""
    prop = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c2", canonical_name="protocol")
    )

    assert prop.lifecycle == PropositionLifecycle.ACTIVE

    prop.lifecycle = PropositionLifecycle.SUPERSEDED
    assert prop.lifecycle == PropositionLifecycle.SUPERSEDED


# ============================================================
# CONFIDENCE TESTS
# ============================================================

def test_confidence_components():
    """Test multi-dimensional confidence"""
    conf = Confidence(
        asr_quality=0.9,
        extraction_confidence=0.8,
        entity_resolution_confidence=0.85,
        grounding_confidence=0.9,
        validation_confidence=0.75,
        consistency_confidence=0.8
    )

    assert conf.asr_quality == 0.9
    assert conf.extraction_confidence == 0.8

    # Overall should be weighted average
    overall = conf.overall
    assert 0.0 <= overall <= 1.0

    # Test serialization
    data = conf.to_dict()
    assert "asr_quality" in data
    assert "overall" in data


# ============================================================
# SEMANTIC FRAME TESTS
# ============================================================

def test_semantic_frame_creation():
    """Test semantic frame creation"""
    frame = SemanticFrame(
        lecture_id="lecture_1",
        chunk_id="chunk_1"
    )

    assert frame.frame_id != ""
    assert frame.lecture_id == "lecture_1"
    assert frame.chunk_id == "chunk_1"
    assert frame.extraction_status == ExtractionStatus.UNCERTAIN


def test_semantic_frame_with_content():
    """Test semantic frame with extracted content"""
    frame = SemanticFrame(
        lecture_id="lecture_1",
        chunk_id="chunk_1"
    )

    # Add evidence
    evidence = EvidenceSpan(
        chunk_id="chunk_1",
        text="TCP provides reliable delivery"
    )
    frame.evidence.append(evidence)

    # Add concept
    concept = Concept(
        canonical_name="TCP",
        confidence=0.9
    )
    frame.concepts.append(concept)

    # Add proposition
    prop = Proposition(
        subject=ConceptRef(concept_id=concept.concept_id, canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="", canonical_name="reliable delivery"),
        evidence_ids=[evidence.evidence_id]
    )
    frame.propositions.append(prop)

    assert len(frame.evidence) == 1
    assert len(frame.concepts) == 1
    assert len(frame.propositions) == 1


# ============================================================
# SEMANTIC STATE TESTS
# ============================================================

def test_semantic_state_initialization():
    """Test semantic state initialization"""
    state = SemanticState(lecture_id="lecture_1")

    assert state.lecture_id == "lecture_1"
    stats = state.get_statistics()
    assert stats["total_concepts"] == 0
    assert stats["total_propositions"] == 0


def test_concept_creation_event():
    """Test concept creation through event"""
    state = SemanticState(lecture_id="lecture_1")

    concept = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        aliases=["Transmission Control Protocol"],
        confidence=0.9
    )

    event = SemanticEvent(
        event_type=SemanticEventType.CONCEPT_CREATED,
        lecture_id="lecture_1",
        payload={
            "concept": concept.to_dict()
        }
    )

    state.apply_event(event)

    # Verify concept was created
    retrieved = state.get_concept("concept_1")
    assert retrieved is not None
    assert retrieved.canonical_name == "TCP"

    # Verify alias lookup
    alias_lookup = state.get_concept_by_alias("Transmission Control Protocol")
    assert alias_lookup is not None
    assert alias_lookup.concept_id == "concept_1"

    # Verify statistics
    stats = state.get_statistics()
    assert stats["total_concepts"] == 1
    assert stats["total_events"] == 1


def test_proposition_addition_event():
    """Test proposition addition through event"""
    state = SemanticState(lecture_id="lecture_1")

    prop = Proposition(
        proposition_id="prop_1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliable delivery"),
        evidence_ids=["e1"],
        confidence=0.85,
        grounding_status=GroundingStatus.EXPLICIT,
        extraction_status=ExtractionStatus.COMPLETE
    )

    event = SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED,
        lecture_id="lecture_1",
        payload={
            "proposition": prop.to_dict()
        }
    )

    state.apply_event(event)

    retrieved = state.get_proposition("prop_1")
    assert retrieved is not None
    assert retrieved.subject.canonical_name == "TCP"
    assert retrieved.predicate == RelationType.PROVIDES

    stats = state.get_statistics()
    assert stats["total_propositions"] == 1


def test_proposition_supersession():
    """Test proposition supersession through event"""
    state = SemanticState(lecture_id="lecture_1")

    # Create two propositions
    prop1 = Proposition(
        proposition_id="prop_1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c2", canonical_name="unreliable protocol")
    )

    prop2 = Proposition(
        proposition_id="prop_2",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c3", canonical_name="reliable protocol")
    )

    # Add both propositions
    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED,
        payload={"proposition": prop1.to_dict()}
    ))

    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED,
        payload={"proposition": prop2.to_dict()}
    ))

    # Supersede prop1
    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_SUPERSEDED,
        payload={
            "old_proposition_id": "prop_1",
            "new_proposition_id": "prop_2"
        }
    ))

    # Verify prop1 is superseded
    retrieved1 = state.get_proposition("prop_1")
    assert retrieved1.lifecycle == PropositionLifecycle.SUPERSEDED

    # Verify prop2 is still active
    retrieved2 = state.get_proposition("prop_2")
    assert retrieved2.lifecycle == PropositionLifecycle.ACTIVE


def test_contradiction_detection():
    """Test contradiction detection through event"""
    state = SemanticState(lecture_id="lecture_1")

    prop1 = Proposition(
        proposition_id="prop_1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c2", canonical_name="connectionless")
    )

    prop2 = Proposition(
        proposition_id="prop_2",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c3", canonical_name="connection-oriented")
    )

    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED,
        payload={"proposition": prop1.to_dict()}
    ))

    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED,
        payload={"proposition": prop2.to_dict()}
    ))

    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.CONTRADICTION_DETECTED,
        payload={
            "proposition1_id": "prop_1",
            "proposition2_id": "prop_2"
        }
    ))

    # Both should be marked as contradicted
    retrieved1 = state.get_proposition("prop_1")
    assert retrieved1.lifecycle == PropositionLifecycle.CONTRADICTED

    retrieved2 = state.get_proposition("prop_2")
    assert retrieved2.lifecycle == PropositionLifecycle.CONTRADICTED


def test_active_context_decay():
    """Test active context decay"""
    state = SemanticState(lecture_id="lecture_1")

    # Create concepts
    for i in range(3):
        concept = Concept(
            concept_id=f"concept_{i}",
            canonical_name=f"Concept {i}"
        )
        state.apply_event(SemanticEvent(
            event_type=SemanticEventType.CONCEPT_CREATED,
            payload={"concept": concept.to_dict()}
        ))

    # All should be active
    active = state.get_active_concepts(limit=10)
    assert len(active) == 3

    # Decay context
    state.decay_active_context(decay_factor=0.5)

    # Still active but with lower confidence
    active_after_decay = state.get_active_concepts(limit=10)
    assert len(active_after_decay) == 3
    assert active_after_decay[0].confidence < active[0].confidence

    # Decay multiple times to remove concepts
    for _ in range(10):
        state.decay_active_context(decay_factor=0.5)

    active_final = state.get_active_concepts(limit=10)
    assert len(active_final) == 0


# ============================================================
# EVIDENCE MANAGER TESTS
# ============================================================

def test_evidence_manager_creation():
    """Test evidence manager creation and linking"""
    manager = EvidenceManager()

    evidence = manager.create_evidence(
        chunk_id="chunk_1",
        text="TCP provides reliable delivery",
        asr_confidence=0.95
    )

    assert evidence.evidence_id != ""
    assert evidence.chunk_id == "chunk_1"

    # Link to proposition
    manager.link_proposition_evidence("prop_1", [evidence.evidence_id])

    # Retrieve evidence
    proposition_evidence = manager.get_proposition_evidence("prop_1")
    assert len(proposition_evidence) == 1
    assert proposition_evidence[0].evidence_id == evidence.evidence_id


def test_grounding_validation():
    """Test grounding validation"""
    manager = EvidenceManager()

    # Create evidence with high confidence
    evidence1 = manager.create_evidence(
        chunk_id="chunk_1",
        text="TCP provides reliable delivery",
        asr_confidence=0.95
    )

    evidence2 = manager.create_evidence(
        chunk_id="chunk_2",
        text="TCP ensures ordered delivery",
        asr_confidence=0.90
    )

    # Single evidence = EXPLICIT
    status, confidence = manager.validate_grounding(
        evidence_ids=[evidence1.evidence_id],
        extraction_confidence=0.9,
        asr_confidence=0.95
    )
    assert status == GroundingStatus.EXPLICIT
    assert confidence > 0.8

    # Multiple evidence = SUPPORTED
    status2, confidence2 = manager.validate_grounding(
        evidence_ids=[evidence1.evidence_id, evidence2.evidence_id],
        extraction_confidence=0.85
    )
    assert status2 == GroundingStatus.SUPPORTED
    assert confidence2 > 0.7

    # No evidence = UNSUPPORTED
    status3, confidence3 = manager.validate_grounding(
        evidence_ids=[],
        extraction_confidence=0.9
    )
    assert status3 == GroundingStatus.UNSUPPORTED
    assert confidence3 == 0.0


# ============================================================
# EVENT LOG TESTS
# ============================================================

def test_event_log_replay():
    """Test event log replay capability"""
    log = SemanticEventLog()

    # Create events
    for i in range(3):
        event = SemanticEvent(
            event_type=SemanticEventType.CONCEPT_CREATED,
            payload={"index": i}
        )
        log.append(event)

    # Check length
    assert len(log) == 3

    # Replay events
    events = log.replay()
    assert len(events) == 3
    assert events[0].payload["index"] == 0
    assert events[2].payload["index"] == 2

    # Test retrieval by ID
    event_id = events[1].event_id
    retrieved = log.get_event(event_id)
    assert retrieved is not None
    assert retrieved.payload["index"] == 1


def test_event_log_filtering():
    """Test event log filtering by type"""
    log = SemanticEventLog()

    # Mix of event types
    log.append(SemanticEvent(
        event_type=SemanticEventType.CONCEPT_CREATED
    ))
    log.append(SemanticEvent(
        event_type=SemanticEventType.PROPOSITION_ADDED
    ))
    log.append(SemanticEvent(
        event_type=SemanticEventType.CONCEPT_CREATED
    ))

    concept_events = log.get_events_by_type(SemanticEventType.CONCEPT_CREATED)
    assert len(concept_events) == 2

    prop_events = log.get_events_by_type(SemanticEventType.PROPOSITION_ADDED)
    assert len(prop_events) == 1


# ============================================================
# SERIALIZATION TESTS
# ============================================================

def test_state_serialization_roundtrip(tmp_path):
    """Test state serialization to JSON and back"""
    state = SemanticState(lecture_id="lecture_1")

    # Add some data
    concept = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        aliases=["Transmission Control Protocol"]
    )
    state.apply_event(SemanticEvent(
        event_type=SemanticEventType.CONCEPT_CREATED,
        payload={"concept": concept.to_dict()}
    ))

    # Save to file
    filepath = tmp_path / "semantic_state.json"
    state.save_to_json(str(filepath))

    # Load into new state
    new_state = SemanticState()
    new_state.load_from_json(str(filepath))

    # Verify data
    assert new_state.lecture_id == "lecture_1"
    retrieved = new_state.get_concept("concept_1")
    assert retrieved is not None
    assert retrieved.canonical_name == "TCP"
    assert "Transmission Control Protocol" in retrieved.aliases


# ============================================================
# THREAD SAFETY TESTS
# ============================================================

def test_semantic_state_thread_safety():
    """Test that semantic state handles concurrent access"""
    import threading

    state = SemanticState(lecture_id="lecture_1")

    def add_concepts(start_idx, count):
        for i in range(start_idx, start_idx + count):
            concept = Concept(
                concept_id=f"concept_{i}",
                canonical_name=f"Concept {i}"
            )
            state.apply_event(SemanticEvent(
                event_type=SemanticEventType.CONCEPT_CREATED,
                payload={"concept": concept.to_dict()}
            ))

    # Create threads
    threads = []
    for i in range(4):
        t = threading.Thread(target=add_concepts, args=(i * 100, 100))
        threads.append(t)

    # Run threads
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    # Verify all concepts were added
    stats = state.get_statistics()
    assert stats["total_concepts"] == 400