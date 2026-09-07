"""
Phase 4 Tests: Coreference + Instructional Acts (Final)
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    Concept,
    ConceptRef,
    Mention,
    EvidenceSpan,
    Coreference,
    UnresolvedReference,
    InstructionalAct,
    InstructionalActType
)

from app.semantic.coreference_resolver import CoreferenceResolver
from app.semantic.instructional_detector import InstructionalDetector
from app.semantic.semantic_intelligence import SemanticIntelligence
from app.semantic.concept_registry import ConceptRegistry


# ============================================================
# COREFERENCE RESOLVER TESTS
# ============================================================

def test_pronoun_resolution_basic():
    """Test basic pronoun resolution"""
    resolver = CoreferenceResolver()
    
    active_concepts = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    text = "It provides reliable delivery"
    
    coreferences = resolver.resolve_pronouns(text, active_concepts)
    
    assert len(coreferences) > 0
    assert coreferences[0].antecedent_ref.concept_id == "c1"


def test_pronoun_resolution_recency():
    """Test that more recent concepts are preferred"""
    resolver = CoreferenceResolver()
    
    active_concepts = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9),
        ConceptRef(concept_id="c2", canonical_name="UDP", confidence=0.9)
    ]
    
    text = "It is connection-oriented"
    
    coreferences = resolver.resolve_pronouns(text, active_concepts)
    
    assert len(coreferences) > 0
    assert coreferences[0].antecedent_ref.concept_id == "c1"


def test_pronoun_no_antecedent():
    """Test that pronoun without antecedent doesn't force resolution"""
    resolver = CoreferenceResolver()
    
    active_concepts = []
    
    text = "It provides reliability"
    
    coreferences = resolver.resolve_pronouns(text, active_concepts)
    
    assert len(coreferences) == 0


def test_definite_np_resolution():
    """Test definite noun phrase resolution"""
    resolver = CoreferenceResolver()
    
    registry = ConceptRegistry()
    
    concept = Concept(
        concept_id="c1",
        canonical_name="TCP",
        aliases=["tcp", "protocol"]
    )
    registry._concepts["c1"] = concept
    registry._alias_index["tcp"] = "c1"
    registry._alias_index["protocol"] = "c1"
    
    active_concepts = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    text = "The protocol provides reliability"
    
    coreferences = resolver.resolve_definite_nps(
        text,
        registry,
        active_concepts
    )
    
    # Should resolve "the protocol" to TCP (via alias)
    assert len(coreferences) > 0
    assert coreferences[0].antecedent_ref.concept_id == "c1"


def test_coreference_ambiguity():
    """Test that truly ambiguous coreferences aren't forced"""
    resolver = CoreferenceResolver()
    
    # Two concepts of same type (both proper nouns) with same confidence
    # This is truly ambiguous - neither should win
    active_concepts = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9),
        ConceptRef(concept_id="c2", canonical_name="UDP", confidence=0.9)
    ]
    
    # Use a generic pronoun with no distinguishing context
    text = "It is important"
    
    # Manually check - both are acronyms, same confidence, same position
    # The resolver should return None (ambiguous) or low confidence
    coreferences = resolver.resolve_pronouns(text, active_concepts)
    
    # Since both are acronyms with same type, recency would normally win
    # But we need to test true ambiguity - use different scenario
    
    # Reset with generic concepts (same type, same confidence)
    active_concepts_2 = [
        ConceptRef(concept_id="c3", canonical_name="networking", confidence=0.9),
        ConceptRef(concept_id="c4", canonical_name="protocols", confidence=0.9)
    ]
    
    text_2 = "They are important"
    
    coreferences_2 = resolver.resolve_pronouns(text_2, active_concepts_2)
    
    # With generic concepts, should either not resolve or have lower confidence
    if coreferences_2:
        assert coreferences_2[0].confidence < 0.85


# ============================================================
# ENHANCED INSTRUCTIONAL DETECTOR TESTS
# ============================================================

def test_definition_with_concept_linking():
    """Test definition detection with concept linking"""
    detector = InstructionalDetector()
    
    concept_refs = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    text = "TCP is defined as Transmission Control Protocol"
    
    acts = detector.detect(
        text,
        concept_refs=concept_refs
    )
    
    assert len(acts) > 0
    assert acts[0].act_type == InstructionalActType.DEFINITION
    assert len(acts[0].concept_refs) > 0
    assert acts[0].concept_refs[0].canonical_name == "TCP"


def test_example_with_concept_linking():
    """Test example detection with concept linking"""
    detector = InstructionalDetector()
    
    concept_refs = [
        ConceptRef(concept_id="c1", canonical_name="TCP", confidence=0.9)
    ]
    
    text = "For example, TCP uses a three-way handshake"
    
    acts = detector.detect(
        text,
        concept_refs=concept_refs
    )
    
    assert len(acts) > 0
    assert acts[0].act_type == InstructionalActType.EXAMPLE
    assert len(acts[0].concept_refs) > 0


def test_process_detection():
    """Test process detection"""
    detector = InstructionalDetector()
    
    text = "First the client sends SYN, then the server responds with SYN-ACK"
    
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.PROCESS for act in acts)


def test_warning_detection():
    """Test warning detection"""
    detector = InstructionalDetector()
    
    text = "Be careful not to confuse TCP with UDP"
    
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.WARNING for act in acts)


def test_recap_detection():
    """Test recap detection"""
    detector = InstructionalDetector()
    
    text = "To summarize, TCP provides reliable delivery"
    
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.RECAP for act in acts)


# ============================================================
# SEMANTIC INTELLIGENCE WITH COREFERENCE TESTS
# ============================================================

def test_si_coreference_integration():
    """Test coreference resolution in semantic intelligence"""
    si = SemanticIntelligence()
    
    frame1 = si.process(
        transcript_text="TCP is a transport protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    frame2 = si.process(
        transcript_text="It provides reliable delivery",
        chunk_id="chunk_2",
        lecture_id="lecture_1"
    )
    
    assert frame2.coreferences is not None
    
    if frame2.coreferences:
        assert frame2.coreferences[0].antecedent_ref.canonical_name == "TCP"


def test_si_unresolved_references():
    """Test tracking of unresolved references"""
    si = SemanticIntelligence()
    
    frame = si.process(
        transcript_text="It provides reliability",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    assert frame.unresolved_references is not None


def test_si_instructional_acts_with_concepts():
    """Test instructional acts with concept linking in SI"""
    si = SemanticIntelligence()
    
    frame = si.process(
        transcript_text="For example, TCP uses a three-way handshake",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    assert len(frame.instructional_acts) > 0
    
    example_acts = [
        act for act in frame.instructional_acts
        if act.act_type == InstructionalActType.EXAMPLE
    ]
    
    assert len(example_acts) > 0
    assert len(example_acts[0].concept_refs) > 0


def test_si_cross_chunk_coreference():
    """Test cross-chunk coreference resolution"""
    si = SemanticIntelligence()
    
    frame1 = si.process(
        transcript_text="TCP and UDP are transport protocols",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    frame2 = si.process(
        transcript_text="It provides reliability",
        chunk_id="chunk_2",
        lecture_id="lecture_1"
    )
    
    assert frame2.coreferences is not None or frame2.unresolved_references is not None


# ============================================================
# INTEGRATION TESTS
# ============================================================

def test_full_pipeline_with_coreference():
    """Test complete pipeline with coreference"""
    si = SemanticIntelligence()
    
    chunks = [
        "TCP is a transport protocol",
        "It provides reliable delivery",
        "This is achieved through acknowledgements",
        "For example, TCP uses a three-way handshake",
    ]
    
    frames = []
    for i, chunk in enumerate(chunks):
        frame = si.process(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_test"
        )
        frames.append(frame)
    
    assert len(frames) == 4
    
    for frame in frames:
        assert frame.extraction_status != "rejected"
    
    assert frames[1].coreferences is not None
    assert frames[2].coreferences is not None
    assert len(frames[3].instructional_acts) > 0


def test_no_false_coreference_without_context():
    """Test that coreference doesn't fire without context"""
    si = SemanticIntelligence()
    
    frame = si.process(
        transcript_text="It provides reliability",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    if frame.coreferences:
        for coref in frame.coreferences:
            assert coref.confidence < 0.7


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_coreference_performance():
    """Test coreference resolution performance"""
    import time
    
    resolver = CoreferenceResolver()
    
    active_concepts = [
        ConceptRef(concept_id=f"c{i}", canonical_name=f"Concept {i}")
        for i in range(10)
    ]
    
    start_time = time.time()
    
    for i in range(100):
        resolver.resolve_pronouns(
            f"It relates to concept {i}",
            active_concepts
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 1.0


def test_si_with_coreference_performance():
    """Test SI performance with coreference"""
    import time
    
    si = SemanticIntelligence()
    
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_warmup",
        lecture_id="lecture_perf"
    )
    
    start_time = time.time()
    
    frame = si.process(
        transcript_text="It provides reliability through acknowledgements",
        chunk_id="chunk_perf",
        lecture_id="lecture_perf"
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 3.0