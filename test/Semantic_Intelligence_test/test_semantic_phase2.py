"""
Phase 2 Tests: Semantic Memory / Entity Identity

Tests concept registry, entity resolution, semantic memory,
and cross-chunk concept identity maintenance.
"""

from __future__ import annotations

import pytest

from app.semantic.semantic_models import (
    Concept,
    ConceptRef,
    Mention,
    EvidenceSpan,
    Proposition,
    RelationType,
    GroundingStatus,
    ExtractionStatus
)

from app.semantic.concept_registry import ConceptRegistry, ResolutionResult
from app.semantic.entity_resolver import EntityResolver
from app.semantic.semantic_memory import SemanticMemory, ActiveContext, TopicMemory
from app.semantic.semantic_intelligence import SemanticIntelligence


# ============================================================
# CONCEPT REGISTRY TESTS
# ============================================================

def test_concept_registry_exact_match():
    """Test exact match resolution"""
    registry = ConceptRegistry()
    
    mention = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    
    result1 = registry.resolve(mention)
    assert result1.is_new
    assert result1.resolution_method == 'new'
    
    mention2 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result2 = registry.resolve(mention2)
    assert not result2.is_new
    assert result2.resolution_method == 'exact'
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id


def test_concept_registry_normalized_match():
    """Test normalized match (case, articles, plural)"""
    registry = ConceptRegistry()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = registry.resolve(mention1)
    
    mention2 = Mention(
        surface_text="tcp",
        normalized_text="tcp",
        confidence=0.9
    )
    result2 = registry.resolve(mention2)
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id
    
    mention3 = Mention(
        surface_text="the TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result3 = registry.resolve(mention3)
    assert not result3.is_new
    assert result3.concept_ref.concept_id == result1.concept_ref.concept_id


def test_concept_registry_plural_handling():
    """Test singular/plural normalization"""
    registry = ConceptRegistry()
    
    mention1 = Mention(
        surface_text="network",
        normalized_text="network",
        confidence=0.9
    )
    result1 = registry.resolve(mention1)
    
    mention2 = Mention(
        surface_text="networks",
        normalized_text="network",
        confidence=0.9
    )
    result2 = registry.resolve(mention2)
    
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id


def test_concept_registry_aliases():
    """Test alias management"""
    registry = ConceptRegistry()
    
    concept = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        aliases=["Transmission Control Protocol", "tcp"]
    )
    
    registry._concepts[concept.concept_id] = concept
    registry._alias_index["tcp"] = concept.concept_id
    registry._alias_index["transmission control protocol"] = concept.concept_id
    registry._exact_index["tcp"] = concept.concept_id
    
    found = registry.get_concept_by_alias("Transmission Control Protocol")
    assert found is not None
    assert found.concept_id == "concept_1"
    
    found2 = registry.get_concept_by_alias("TCP")
    assert found2 is not None
    assert found2.concept_id == "concept_1"


def test_concept_registry_merge():
    """Test concept merging"""
    registry = ConceptRegistry()
    
    concept1 = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        aliases=["tcp"]
    )
    concept2 = Concept(
        concept_id="concept_2",
        canonical_name="Transmission Control Protocol",
        aliases=["transmission control protocol"]
    )
    
    registry._concepts["concept_1"] = concept1
    registry._concepts["concept_2"] = concept2
    registry._alias_index["tcp"] = "concept_1"
    registry._alias_index["transmission control protocol"] = "concept_2"
    registry._exact_index["tcp"] = "concept_1"
    registry._exact_index["transmission control protocol"] = "concept_2"
    
    success = registry.merge_concepts("concept_2", "concept_1")
    assert success
    
    assert registry.get_concept("concept_2") is None
    
    merged = registry.get_concept("concept_1")
    assert merged is not None
    assert "transmission control protocol" in merged.aliases
    
    assert registry.get_concept_by_alias("tcp").concept_id == "concept_1"
    assert registry.get_concept_by_alias("transmission control protocol").concept_id == "concept_1"


# ============================================================
# ENTITY RESOLVER TESTS
# ============================================================

def test_entity_resolver_basic():
    """Test basic entity resolution"""
    resolver = EntityResolver()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = resolver.resolve(mention1)
    assert result1.is_new
    
    mention2 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result2 = resolver.resolve(mention2)
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id


def test_entity_resolver_embedding_match():
    """Test embedding-based resolution"""
    resolver = EntityResolver()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = resolver.resolve(
        mention1,
        embedding=[0.5, 0.5, 0.5, 0.5]
    )
    
    mention2 = Mention(
        surface_text="Transmission Control Protocol",
        normalized_text="transmission control protocol",
        confidence=0.85
    )
    result2 = resolver.resolve(
        mention2,
        embedding=[0.48, 0.52, 0.49, 0.51]
    )
    
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id


def test_entity_resolver_no_false_merge():
    """Test that different concepts don't merge"""
    resolver = EntityResolver()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = resolver.resolve(
        mention1,
        embedding=[0.5, 0.5, 0.5, 0.5]
    )
    
    mention2 = Mention(
        surface_text="UDP",
        normalized_text="udp",
        confidence=0.9
    )
    result2 = resolver.resolve(
        mention2,
        embedding=[-0.5, -0.5, -0.5, -0.5]
    )
    
    assert result2.is_new
    assert result2.concept_ref.concept_id != result1.concept_ref.concept_id


# ============================================================
# SEMANTIC MEMORY TESTS
# ============================================================

def test_semantic_memory_concept_tracking():
    """Test concept tracking in memory"""
    memory = SemanticMemory()
    
    concept = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        aliases=["tcp"],
        confidence=0.9
    )
    memory.add_concept(concept, topic_path="networks")
    
    assert memory.registry.get_concept("concept_1") is not None
    
    active = memory.active_context.get_active_concepts()
    assert len(active) > 0
    assert active[0][0] == "concept_1"
    
    topic_concepts = memory.topic_memory.get_topic_concepts("networks")
    assert "concept_1" in topic_concepts


def test_semantic_memory_resolution():
    """Test memory-based resolution"""
    memory = SemanticMemory()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = memory.resolve_mention(mention1, topic_path="networks")
    assert result1.is_new
    
    mention2 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result2 = memory.resolve_mention(mention2, topic_path="networks")
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id


def test_semantic_memory_propositions():
    """Test proposition storage"""
    memory = SemanticMemory()
    
    prop = Proposition(
        proposition_id="prop_1",
        subject=ConceptRef(concept_id="c1", canonical_name="TCP"),
        predicate=RelationType.PROVIDES,
        object=ConceptRef(concept_id="c2", canonical_name="reliability"),
        evidence_ids=["e1"]
    )
    memory.add_proposition(prop)
    
    retrieved = memory.get_proposition("prop_1")
    assert retrieved is not None
    assert retrieved.subject.canonical_name == "TCP"
    
    props = memory.get_propositions_for_concept("c1")
    assert len(props) == 1


def test_semantic_memory_context_decay():
    """Test active context decay"""
    memory = SemanticMemory()
    
    for i in range(5):
        concept = Concept(
            concept_id=f"concept_{i}",
            canonical_name=f"Concept {i}"
        )
        memory.add_concept(concept)
    
    active = memory.active_context.get_active_concepts()
    assert len(active) == 5
    
    memory.decay_context(factor=0.1)
    
    active_after = memory.active_context.get_active_concepts()
    assert len(active_after) < 5


# ============================================================
# SEMANTIC INTELLIGENCE WITH MEMORY TESTS
# ============================================================

def test_cross_chunk_concept_identity():
    """Test that concepts maintain identity across chunks"""
    si = SemanticIntelligence()
    
    # Process first chunk
    text1 = "TCP is a transport protocol"
    frame1 = si.process(
        transcript_text=text1,
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        topic_path="networks"
    )
    
    # Get TCP concept from first chunk
    tcp_concept_1 = None
    for concept in frame1.concepts:
        if concept.canonical_name == "TCP":
            tcp_concept_1 = concept
            break
    
    assert tcp_concept_1 is not None
    
    # Process second chunk
    text2 = "TCP provides reliable delivery"
    frame2 = si.process(
        transcript_text=text2,
        chunk_id="chunk_2",
        lecture_id="lecture_1",
        topic_path="networks"
    )
    
    # Get TCP concept from second chunk
    tcp_concept_2 = None
    for concept in frame2.concepts:
        if concept.canonical_name == "TCP":
            tcp_concept_2 = concept
            break
    
    assert tcp_concept_2 is not None
    
    # Concepts should have same ID (resolved to existing)
    assert tcp_concept_1.concept_id == tcp_concept_2.concept_id


def test_cross_chunk_no_duplicate_concepts():
    """Test that repeated mentions don't create duplicate concepts"""
    si = SemanticIntelligence()
    
    chunks = [
        "TCP is a protocol",
        "TCP provides reliability",
        "TCP uses acknowledgements",
    ]
    
    tcp_concept_ids = set()
    
    for i, chunk in enumerate(chunks):
        frame = si.process(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_1"
        )
        
        for concept in frame.concepts:
            if concept.canonical_name == "TCP":
                tcp_concept_ids.add(concept.concept_id)
    
    # All TCP mentions should have same concept ID
    assert len(tcp_concept_ids) == 1


def test_memory_statistics():
    """Test memory statistics tracking"""
    si = SemanticIntelligence()
    
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    si.process(
        transcript_text="TCP provides reliability",
        chunk_id="chunk_2",
        lecture_id="lecture_1"
    )
    
    stats = si.get_memory_statistics()
    
    assert stats is not None
    assert "registry" in stats
    assert stats["registry"]["total_concepts"] > 0
    assert stats["propositions"] > 0


def test_topic_memory_isolation():
    """Test that concepts are tracked per topic"""
    si = SemanticIntelligence()
    
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        topic_path="networks/transport"
    )
    
    si.process(
        transcript_text="A transistor amplifies signals",
        chunk_id="chunk_2",
        lecture_id="lecture_1",
        topic_path="electronics/components"
    )
    
    networks_concepts = si.semantic_memory.topic_memory.get_topic_concepts(
        "networks/transport"
    )
    electronics_concepts = si.semantic_memory.topic_memory.get_topic_concepts(
        "electronics/components"
    )
    
    assert len(networks_concepts) > 0
    assert len(electronics_concepts) > 0
    assert networks_concepts != electronics_concepts


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_memory_scaling():
    """Test that memory scales reasonably"""
    import time
    
    si = SemanticIntelligence()
    
    start_time = time.time()
    
    for i in range(50):
        si.process(
            transcript_text=f"Concept {i} is related to concept {i+1}",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_scaling"
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 5.0
    
    stats = si.get_memory_statistics()
    assert stats["registry"]["total_concepts"] > 0


def test_long_lecture_simulation():
    """Test simulation of longer lecture"""
    si = SemanticIntelligence()
    
    for i in range(30):
        text = f"Topic {i} is important for understanding the system"
        si.process(
            transcript_text=text,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_long"
        )
    
    stats = si.get_memory_statistics()
    assert stats["registry"]["total_concepts"] > 0
    assert stats["registry"]["total_concepts"] < 100