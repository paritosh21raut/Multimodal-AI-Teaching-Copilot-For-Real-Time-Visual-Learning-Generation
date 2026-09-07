"""
Phase 1 Tests: Evidence-First Deterministic Extraction

Tests mention extraction, proposition extraction, relation normalization,
instructional act detection, and the main semantic intelligence orchestrator.
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    SemanticFrame,
    EvidenceSpan,
    Mention,
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    ConceptRef,
    Confidence,
    GroundingStatus,
    ExtractionStatus,
    RelationType,
    InstructionalActType
)

from app.semantic.mention_extractor import MentionExtractor
from app.semantic.proposition_extractor import PropositionExtractor
from app.semantic.relation_normalizer import RelationNormalizer
from app.semantic.instructional_detector import InstructionalDetector
from app.semantic.semantic_intelligence import SemanticIntelligence


# ============================================================
# MENTION EXTRACTOR TESTS
# ============================================================

def test_mention_extraction_basic():
    """Test basic mention extraction"""
    extractor = MentionExtractor()
    
    text = "TCP provides reliable data transmission"
    mentions = extractor.extract_mentions(text)
    
    assert len(mentions) > 0
    
    tcp_mentions = [m for m in mentions if "TCP" in m.surface_text]
    assert len(tcp_mentions) > 0


def test_mention_extraction_acronyms():
    """Test acronym extraction"""
    extractor = MentionExtractor()
    
    text = "TCP and UDP are transport protocols"
    mentions = extractor.extract_mentions(text)
    
    surfaces = [m.surface_text for m in mentions]
    assert any("TCP" in s for s in surfaces)
    assert any("UDP" in s for s in surfaces)


def test_mention_extraction_partitive():
    """Test X-of-Y pattern extraction"""
    extractor = MentionExtractor()
    
    text = "The architecture of a microcontroller includes CPU and memory"
    mentions = extractor.extract_mentions(text)
    
    surfaces = [m.surface_text.lower() for m in mentions]
    assert any("architecture" in s for s in surfaces)


def test_mention_normalization():
    """Test mention normalization"""
    extractor = MentionExtractor()
    
    assert extractor._normalize_mention("datasets") == "dataset"
    assert extractor._normalize_mention("networks") == "network"
    assert "the" not in extractor._normalize_mention("the network")
    assert extractor._normalize_mention("TCP") == "tcp"


# ============================================================
# PROPOSITION EXTRACTOR TESTS
# ============================================================

def test_proposition_extraction_is_a():
    """Test IS_A proposition extraction"""
    extractor = PropositionExtractor()
    
    text = "TCP is a transport protocol"
    evidence = EvidenceSpan(chunk_id="chunk_1", text=text)
    
    props = extractor.extract_propositions(text, evidence)
    
    assert len(props) > 0
    
    prop = props[0]
    assert prop.subject is not None
    assert prop.predicate == RelationType.IS_A
    assert prop.object is not None
    assert "TCP" in prop.subject.canonical_name
    assert "protocol" in prop.object.canonical_name.lower()


def test_proposition_extraction_provides():
    """Test PROVIDES proposition extraction"""
    extractor = PropositionExtractor()
    
    text = "TCP provides reliable delivery"
    evidence = EvidenceSpan(chunk_id="chunk_1", text=text)
    
    props = extractor.extract_propositions(text, evidence)
    
    assert len(props) > 0
    
    prop = props[0]
    assert "TCP" in prop.subject.canonical_name
    assert prop.predicate == RelationType.PROVIDES
    assert "reliable" in prop.object.canonical_name.lower()


def test_proposition_extraction_uses():
    """Test USES proposition extraction"""
    extractor = PropositionExtractor()
    
    text = "TCP uses acknowledgements for reliability"
    evidence = EvidenceSpan(chunk_id="chunk_1", text=text)
    
    props = extractor.extract_propositions(text, evidence)
    
    assert len(props) > 0
    
    prop = props[0]
    assert "TCP" in prop.subject.canonical_name
    assert prop.predicate == RelationType.USES


def test_proposition_grounding():
    """Test proposition evidence grounding"""
    extractor = PropositionExtractor()
    
    text = "TCP is a protocol"
    evidence = EvidenceSpan(
        chunk_id="chunk_1",
        text=text,
        evidence_id="evidence_1"
    )
    
    props = extractor.extract_propositions(text, evidence)
    
    assert len(props) > 0
    assert len(props[0].evidence_ids) > 0
    assert "evidence_1" in props[0].evidence_ids
    assert props[0].grounding_status == GroundingStatus.EXPLICIT


# ============================================================
# RELATION NORMALIZER TESTS
# ============================================================

def test_relation_normalization():
    """Test relation normalization"""
    normalizer = RelationNormalizer()
    
    assert normalizer.normalize(RelationType.IS_A) == RelationType.IS_A
    assert normalizer.normalize(RelationType.PROVIDES) == RelationType.PROVIDES
    
    assert normalizer.normalize_from_verb("is") == RelationType.IS_A
    assert normalizer.normalize_from_verb("provides") == RelationType.PROVIDES
    assert normalizer.normalize_from_verb("uses") == RelationType.USES


def test_relation_validation():
    """Test relation validation"""
    normalizer = RelationNormalizer()
    
    assert normalizer.validate_relation(RelationType.IS_A)
    assert normalizer.validate_relation(RelationType.PROVIDES)
    assert normalizer.validate_relation(RelationType.USES)
    
    valid_relations = normalizer.get_all_valid_relations()
    assert len(valid_relations) > 20


# ============================================================
# INSTRUCTIONAL DETECTOR TESTS
# ============================================================

def test_definition_detection():
    """Test definition detection"""
    detector = InstructionalDetector()
    
    text = "TCP is defined as Transmission Control Protocol"
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.DEFINITION for act in acts)


def test_example_detection():
    """Test example detection"""
    detector = InstructionalDetector()
    
    text = "For example, consider a client sending a request"
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.EXAMPLE for act in acts)


def test_process_detection():
    """Test process detection"""
    detector = InstructionalDetector()
    
    text = "First the client sends SYN, then the server responds with SYN-ACK"
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.PROCESS for act in acts)


def test_comparison_detection():
    """Test comparison detection"""
    detector = InstructionalDetector()
    
    text = "TCP is similar to UDP in that both are transport protocols"
    acts = detector.detect(text)
    
    assert len(acts) > 0
    assert any(act.act_type == InstructionalActType.COMPARISON for act in acts)


# ============================================================
# SEMANTIC INTELLIGENCE ORCHESTRATOR TESTS
# ============================================================

def test_semantic_intelligence_basic():
    """Test basic semantic intelligence processing"""
    si = SemanticIntelligence()
    
    text = "TCP is a transport protocol that provides reliable delivery"
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert frame is not None
    assert frame.chunk_id == "chunk_1"
    assert frame.lecture_id == "lecture_1"
    assert len(frame.evidence) > 0
    assert len(frame.concepts) > 0
    assert len(frame.propositions) > 0
    assert frame.frame_confidence.extraction_confidence > 0.5
    assert frame.extraction_status == ExtractionStatus.COMPLETE


def test_semantic_intelligence_empty():
    """Test semantic intelligence with empty input"""
    si = SemanticIntelligence()
    
    frame = si.process(
        transcript_text="",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    assert frame is not None
    assert frame.extraction_status == ExtractionStatus.REJECTED
    assert frame.frame_confidence.extraction_confidence == 0.0


def test_semantic_intelligence_multiple_propositions():
    """Test multiple proposition extraction"""
    si = SemanticIntelligence()
    
    text = "TCP is a protocol. TCP provides reliability. TCP uses acknowledgements."
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_2",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert len(frame.propositions) >= 2
    assert len(frame.concepts) > 0


def test_semantic_intelligence_relations():
    """Test relation extraction from propositions"""
    si = SemanticIntelligence()
    
    text = "TCP provides reliable delivery"
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_3",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert len(frame.relations) > 0
    
    relation = frame.relations[0]
    assert relation.relation_type == RelationType.PROVIDES
    assert relation.source.canonical_name == "TCP"


def test_semantic_intelligence_instructional_acts():
    """Test instructional act detection in orchestrator"""
    si = SemanticIntelligence()
    
    text = "For example, TCP uses a three-way handshake"
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_4",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert len(frame.instructional_acts) > 0
    assert any(
        act.act_type == InstructionalActType.EXAMPLE
        for act in frame.instructional_acts
    )


# ============================================================
# INTEGRATION TESTS
# ============================================================

def test_full_extraction_pipeline():
    """Test complete extraction pipeline"""
    si = SemanticIntelligence()
    
    text = (
        "TCP is a connection-oriented protocol. "
        "It provides reliable data transmission. "
        "For example, TCP uses a three-way handshake to establish connections."
    )
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_integration",
        lecture_id="lecture_test",
        generate_embeddings=False
    )
    
    assert len(frame.concepts) >= 3
    assert len(frame.propositions) >= 2
    assert len(frame.relations) >= 2
    assert any(
        act.act_type == InstructionalActType.EXAMPLE
        for act in frame.instructional_acts
    )
    
    for prop in frame.propositions:
        assert len(prop.evidence_ids) > 0


def test_domain_generalization():
    """Test that system works across domains"""
    si = SemanticIntelligence()
    
    domains = {
        "networks": "TCP provides reliable delivery",
        "electronics": "A transistor amplifies signals",
        "databases": "An index improves query performance",
        "physics": "Force equals mass times acceleration",
        "biology": "Mitochondria produce energy for cells",
        "math": "The derivative represents the rate of change",
    }
    
    for domain, text in domains.items():
        frame = si.process(
            transcript_text=text,
            chunk_id=f"chunk_{domain}",
            lecture_id="lecture_domains",
            generate_embeddings=False
        )
        
        assert frame.extraction_status != ExtractionStatus.REJECTED
        assert len(frame.concepts) > 0 or len(frame.propositions) > 0


def test_no_hallucination():
    """Test that system doesn't invent facts"""
    si = SemanticIntelligence()
    
    text = "TCP uses a three-way handshake"
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_no_hallucination",
        lecture_id="lecture_test",
        generate_embeddings=False
    )
    
    all_content = ""
    for concept in frame.concepts:
        all_content += concept.canonical_name + " "
    for prop in frame.propositions:
        if prop.subject:
            all_content += prop.subject.canonical_name + " "
        if prop.object:
            all_content += prop.object.canonical_name + " "
    
    assert "reliable" not in all_content.lower()
    assert "guarantees" not in all_content.lower()
    assert "port 80" not in all_content.lower()
    
    assert "TCP" in all_content
    assert "handshake" in all_content.lower()


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_processing_speed():
    """Test that processing is fast (after warm-up)"""
    import time
    
    si = SemanticIntelligence()
    
    # Warm-up (skip embeddings for speed)
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_warmup",
        lecture_id="lecture_perf",
        generate_embeddings=False
    )
    
    text = (
        "TCP is a transport protocol that provides reliable data transmission. "
        "It uses acknowledgements and retransmissions to ensure delivery. "
        "The three-way handshake establishes the connection before data transfer."
    )
    
    start_time = time.time()
    
    frame = si.process(
        transcript_text=text,
        chunk_id="chunk_perf",
        lecture_id="lecture_perf",
        generate_embeddings=False
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 1.0


def test_multiple_chunks_incremental():
    """Test processing multiple chunks"""
    si = SemanticIntelligence()
    
    chunks = [
        "TCP is a transport protocol",
        "TCP provides reliable delivery",
        "TCP uses acknowledgements for reliability",
    ]
    
    frames = []
    for i, chunk in enumerate(chunks):
        frame = si.process(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_sequence",
            generate_embeddings=False
        )
        frames.append(frame)
    
    assert len(frames) == 3
    
    for frame in frames:
        assert frame.extraction_status != ExtractionStatus.REJECTED
    
    # Concepts should be tracked
    concepts = si.get_all_concepts()
    assert len(concepts) > 0