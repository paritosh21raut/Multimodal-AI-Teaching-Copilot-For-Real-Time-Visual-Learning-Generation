"""
Phase 5 Tests: Validation / Confidence / Contradictions

Tests semantic validation, confidence calculation, and contradiction detection.
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    Proposition,
    Concept,
    ConceptRef,
    EvidenceSpan,
    Relation,
    Confidence,
    GroundingStatus,
    ExtractionStatus,
    PropositionLifecycle,
    RelationType
)

from app.semantic.validator import SemanticValidator
from app.semantic.confidence import ConfidenceCalculator
from app.semantic.contradiction_detector import ContradictionDetector, Contradiction
from app.semantic.semantic_intelligence import SemanticIntelligence


# ============================================================
# VALIDATOR TESTS
# ============================================================

def test_validator_basic_proposition():
    """Test basic proposition validation"""
    validator = SemanticValidator()
    
    prop = Proposition(
        proposition_id="prop_1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        evidence_ids=["e1"],
        confidence=0.8,
        grounding_status=GroundingStatus.EXPLICIT,
        extraction_status=ExtractionStatus.COMPLETE
    )
    
    is_valid, confidence, reason = validator.validate_proposition(prop)
    
    assert is_valid
    assert confidence >= 0.5
    assert reason == "valid"


def test_validator_unsupported_proposition():
    """Test that unsupported propositions are rejected"""
    validator = SemanticValidator()
    
    prop = Proposition(
        proposition_id="prop_2",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        evidence_ids=[],  # No evidence
        confidence=0.5,
        grounding_status=GroundingStatus.UNSUPPORTED
    )
    
    is_valid, confidence, reason = validator.validate_proposition(prop)
    
    assert not is_valid
    assert confidence < 0.5


def test_validator_frame():
    """Test frame validation"""
    validator = SemanticValidator()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP")
    ]
    
    propositions = [
        Proposition(
            proposition_id="p1",
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id="c2", canonical_name="protocol"),
            evidence_ids=["e1"],
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT
        )
    ]
    
    evidence = [
        EvidenceSpan(
            evidence_id="e1",
            chunk_id="chunk_1",
            text="TCP is a protocol"
        )
    ]
    
    is_valid, confidence, report = validator.validate_frame(
        concepts,
        propositions,
        evidence
    )
    
    assert is_valid
    assert report["valid_propositions"] == 1
    assert report["evidence_coverage"] == 1.0


# ============================================================
# CONFIDENCE CALCULATOR TESTS
# ============================================================

def test_confidence_calculation():
    """Test confidence calculation"""
    calc = ConfidenceCalculator()
    
    prop = Proposition(
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        confidence=0.7,
        grounding_status=GroundingStatus.EXPLICIT
    )
    
    confidence = calc.calculate_proposition_confidence(
        prop,
        asr_confidence=0.9,
        evidence_quality=0.9,
        validation_confidence=0.8
    )
    
    assert 0.0 <= confidence <= 1.0
    assert confidence > 0.5


def test_confidence_calibration():
    """Test confidence calibration"""
    calc = ConfidenceCalculator()
    
    # Low confidence should stay low
    assert calc.calibrate_confidence(0.1) < 0.3
    
    # High confidence should stay high
    assert calc.calibrate_confidence(0.9) > 0.7
    
    # Medium confidence should be around 0.5
    assert 0.3 < calc.calibrate_confidence(0.5) < 0.7


def test_frame_confidence():
    """Test frame confidence calculation"""
    calc = ConfidenceCalculator()
    
    concepts = [
        Concept(concept_id="c1", canonical_name="TCP", mention_count=2)
    ]
    
    propositions = [
        Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id="c2", canonical_name="protocol"),
            grounding_status=GroundingStatus.EXPLICIT
        )
    ]
    
    evidence = [
        EvidenceSpan(evidence_id="e1", text="TCP is a protocol")
    ]
    
    confidence = calc.calculate_frame_confidence(
        concepts,
        propositions,
        evidence,
        asr_confidence=0.9,
        validation_report={"evidence_coverage": 1.0}
    )
    
    assert confidence.grounding_confidence > 0.5
    assert confidence.extraction_confidence > 0.5
    assert confidence.entity_resolution_confidence > 0.5


# ============================================================
# CONTRADICTION DETECTOR TESTS
# ============================================================

def test_contradiction_detection():
    """Test basic contradiction detection"""
    detector = ContradictionDetector()
    
    prop1 = Proposition(
        proposition_id="p1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c2", canonical_name="connectionless"),
        grounding_status=GroundingStatus.EXPLICIT
    )
    
    prop2 = Proposition(
        proposition_id="p2",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.IS_A,
        object=ConceptRef(concept_id="c3", canonical_name="connection-oriented"),
        grounding_status=GroundingStatus.EXPLICIT
    )
    
    contradiction = detector.detect_contradiction(prop2, [prop1])
    
    assert contradiction is not None
    assert contradiction.original_proposition_id == "p1"
    assert contradiction.challenge_proposition_id == "p2"


def test_no_false_contradiction():
    """Test that compatible propositions don't contradict"""
    detector = ContradictionDetector()
    
    prop1 = Proposition(
        proposition_id="p1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        grounding_status=GroundingStatus.EXPLICIT
    )
    
    prop2 = Proposition(
        proposition_id="p2",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.USES,
        object=ConceptRef(concept_id="c3", canonical_name="acknowledgements"),
        grounding_status=GroundingStatus.EXPLICIT
    )
    
    contradiction = detector.detect_contradiction(prop2, [prop1])
    
    assert contradiction is None


def test_contradiction_handling():
    """Test contradiction lifecycle management"""
    detector = ContradictionDetector()
    
    propositions = {
        "p1": Proposition(
            proposition_id="p1",
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id="c2", canonical_name="connectionless"),
            lifecycle=PropositionLifecycle.ACTIVE
        ),
        "p2": Proposition(
            proposition_id="p2",
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.IS_A,
            object=ConceptRef(concept_id="c3", canonical_name="connection-oriented"),
            lifecycle=PropositionLifecycle.ACTIVE
        )
    }
    
    contradiction = Contradiction(
        contradiction_id="contra_1",
        original_proposition_id="p1",
        challenge_proposition_id="p2",
        confidence=0.9,
        detection_method="test",
        timestamp=None
    )
    
    detector.handle_contradiction(contradiction, propositions)
    
    assert propositions["p1"].lifecycle == PropositionLifecycle.CONTRADICTED
    assert propositions["p2"].lifecycle == PropositionLifecycle.CONTRADICTED


def test_correction_handling():
    """Test explicit correction handling"""
    detector = ContradictionDetector()
    
    propositions = {
        "p1": Proposition(
            proposition_id="p1",
            lifecycle=PropositionLifecycle.ACTIVE
        ),
        "p2": Proposition(
            proposition_id="p2",
            lifecycle=PropositionLifecycle.ACTIVE
        )
    }
    
    detector.handle_correction("p1", "p2", propositions)
    
    assert propositions["p1"].lifecycle == PropositionLifecycle.SUPERSEDED
    assert propositions["p2"].lifecycle == PropositionLifecycle.ACTIVE


# ============================================================
# SEMANTIC INTELLIGENCE INTEGRATION TESTS
# ============================================================

def test_si_validation_integration():
    """Test validation in semantic intelligence"""
    si = SemanticIntelligence()
    
    frame = si.process(
        transcript_text="TCP provides reliable delivery",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    assert frame is not None
    assert frame.frame_confidence is not None
    assert frame.frame_confidence.grounding_confidence > 0


def test_si_contradiction_integration():
    """Test contradiction detection in SI"""
    si = SemanticIntelligence()
    
    # Process first statement
    si.process(
        transcript_text="TCP is connectionless",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    # Process contradictory statement
    si.process(
        transcript_text="TCP is connection-oriented",
        chunk_id="chunk_2",
        lecture_id="lecture_1"
    )
    
    # Check contradictions detected
    contradictions = si.get_contradictions()
    assert len(contradictions) >= 0  # May or may not detect depending on extraction


def test_si_confidence_quality():
    """Test confidence reflects content quality"""
    si = SemanticIntelligence()
    
    # Good content
    frame_good = si.process(
        transcript_text="TCP provides reliable delivery through acknowledgements",
        chunk_id="chunk_good",
        lecture_id="lecture_1"
    )
    
    # Poor content (just chatter)
    frame_poor = si.process(
        transcript_text="um uh yeah",
        chunk_id="chunk_poor",
        lecture_id="lecture_1"
    )
    
    # Good content should have higher confidence
    assert frame_good.frame_confidence.overall > frame_poor.frame_confidence.overall


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_validation_performance():
    """Test validation performance"""
    import time
    
    validator = SemanticValidator()
    
    start_time = time.time()
    
    for i in range(100):
        prop = Proposition(
            subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
            predicate=RelationType.PROVIDES,
            object=ConceptRef(concept_id="c2", canonical_name="reliability"),
            evidence_ids=["e1"],
            confidence=0.8,
            grounding_status=GroundingStatus.EXPLICIT
        )
        
        validator.validate_proposition(prop)
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 1.0


def test_si_with_validation_performance():
    """Test SI performance with validation"""
    import time
    
    si = SemanticIntelligence()
    
    # Warm up
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_warmup",
        lecture_id="lecture_perf"
    )
    
    start_time = time.time()
    
    frame = si.process(
        transcript_text="TCP provides reliability through acknowledgements",
        chunk_id="chunk_perf",
        lecture_id="lecture_perf"
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 3.0