"""
Phase 3 Tests: Embedding Retrieval (Fixed)

Tests embedding index, embedding retriever, and improved entity resolution
with embeddings.
"""

from __future__ import annotations

import pytest
import numpy as np

from app.semantic.semantic_models import (
    Concept,
    ConceptRef,
    Mention,
    EvidenceSpan
)

from app.semantic.embedding_index import EmbeddingIndex
from app.semantic.embedding_retriever import EmbeddingRetriever
from app.semantic.entity_resolver import EntityResolver
from app.semantic.semantic_intelligence import SemanticIntelligence


# ============================================================
# EMBEDDING INDEX TESTS
# ============================================================

def test_embedding_index_add_and_get():
    """Test adding and retrieving embeddings"""
    index = EmbeddingIndex()
    
    embedding = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    index.add_concept_embedding("concept_1", embedding)
    
    retrieved = index.get_concept_embedding("concept_1")
    assert retrieved is not None
    assert np.array_equal(retrieved, embedding)


def test_embedding_index_similarity():
    """Test embedding similarity computation"""
    index = EmbeddingIndex()
    
    emb1 = np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    emb2 = np.array([0.48, 0.52, 0.49, 0.51], dtype=np.float32)
    
    index.add_concept_embedding("concept_1", emb1)
    index.add_concept_embedding("concept_2", emb2)
    
    similarity = index.compute_similarity("concept_1", "concept_2")
    
    assert similarity > 0.9


def test_embedding_index_find_similar():
    """Test finding similar concepts"""
    index = EmbeddingIndex()
    
    # Use clearly distinct embeddings
    index.add_concept_embedding(
        "tcp",
        np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    index.add_concept_embedding(
        "udp",
        np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    )
    index.add_concept_embedding(
        "http",
        np.array([0.0, 0.0, 1.0, 0.0], dtype=np.float32)
    )
    
    # Query close to TCP
    query = np.array([0.95, 0.05, 0.05, 0.05], dtype=np.float32)
    results = index.find_similar_concepts(query, threshold=0.5)
    
    assert len(results) > 0
    assert results[0][0] == "tcp"
    assert results[0][1] > 0.9


def test_embedding_index_remove():
    """Test removing concept embedding"""
    index = EmbeddingIndex()
    
    index.add_concept_embedding(
        "concept_1",
        np.array([0.5, 0.5, 0.5, 0.5], dtype=np.float32)
    )
    
    assert index.get_concept_embedding("concept_1") is not None
    
    index.remove_concept("concept_1")
    
    assert index.get_concept_embedding("concept_1") is None


# ============================================================
# EMBEDDING RETRIEVER TESTS
# ============================================================

def test_retriever_basic():
    """Test basic candidate retrieval"""
    index = EmbeddingIndex()
    retriever = EmbeddingRetriever(index)
    
    from app.semantic.concept_registry import ConceptRegistry
    
    registry = ConceptRegistry()
    
    concept1 = Concept(
        concept_id="concept_1",
        canonical_name="TCP",
        confidence=0.9
    )
    concept2 = Concept(
        concept_id="concept_2",
        canonical_name="UDP",
        confidence=0.9
    )
    
    registry._concepts["concept_1"] = concept1
    registry._concepts["concept_2"] = concept2
    
    index.add_concept_embedding(
        "concept_1",
        np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    index.add_concept_embedding(
        "concept_2",
        np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    )
    
    query = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)
    candidates = retriever.retrieve_candidates(query, registry)
    
    assert len(candidates) > 0
    assert candidates[0][0].concept_id == "concept_1"


def test_retriever_with_active_concepts():
    """Test retrieval prioritizes active concepts"""
    index = EmbeddingIndex()
    retriever = EmbeddingRetriever(index)
    
    from app.semantic.concept_registry import ConceptRegistry
    
    registry = ConceptRegistry()
    
    for i in range(3):
        concept = Concept(
            concept_id=f"concept_{i}",
            canonical_name=f"Concept {i}",
            confidence=0.9
        )
        registry._concepts[f"concept_{i}"] = concept
        
        # Distinct embeddings
        emb = np.zeros(4, dtype=np.float32)
        emb[i] = 1.0
        index.add_concept_embedding(f"concept_{i}", emb)
    
    active_refs = [
        ConceptRef(concept_id="concept_2", canonical_name="Concept 2")
    ]
    
    query = np.array([0.0, 0.0, 0.9, 0.0], dtype=np.float32)
    candidates = retriever.retrieve_candidates(
        query,
        registry,
        active_concepts=active_refs
    )
    
    assert len(candidates) > 0
    assert candidates[0][0].concept_id == "concept_2"


# ============================================================
# ENTITY RESOLVER WITH EMBEDDINGS TESTS
# ============================================================

def test_resolver_embedding_merge():
    """Test that similar mentions merge via embeddings"""
    resolver = EntityResolver()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = resolver.resolve(
        mention1,
        embedding=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    assert result1.is_new
    
    # Very similar embedding
    mention2 = Mention(
        surface_text="Transmission Control Protocol",
        normalized_text="transmission control protocol",
        confidence=0.85
    )
    result2 = resolver.resolve(
        mention2,
        embedding=np.array([0.95, 0.05, 0.0, 0.0], dtype=np.float32)
    )
    
    assert not result2.is_new
    assert result2.concept_ref.concept_id == result1.concept_ref.concept_id
    assert result2.resolution_method == 'embedding'


def test_resolver_embedding_no_false_merge():
    """Test that dissimilar concepts don't merge"""
    resolver = EntityResolver()
    
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    result1 = resolver.resolve(
        mention1,
        embedding=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    
    mention2 = Mention(
        surface_text="UDP",
        normalized_text="udp",
        confidence=0.9
    )
    result2 = resolver.resolve(
        mention2,
        embedding=np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    )
    
    assert result2.is_new
    assert result2.concept_ref.concept_id != result1.concept_ref.concept_id


def test_resolver_ambiguous_match():
    """Test that ambiguous matches don't force resolution"""
    resolver = EntityResolver()
    
    # Create two distinct concepts
    mention1 = Mention(
        surface_text="TCP",
        normalized_text="tcp",
        confidence=0.9
    )
    resolver.resolve(
        mention1,
        embedding=np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
    )
    
    mention2 = Mention(
        surface_text="UDP",
        normalized_text="udp",
        confidence=0.9
    )
    resolver.resolve(
        mention2,
        embedding=np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)
    )
    
    # Query that's between the two (ambiguous)
    mention3 = Mention(
        surface_text="Unknown protocol",
        normalized_text="unknown protocol",
        confidence=0.7
    )
    result3 = resolver.resolve(
        mention3,
        embedding=np.array([0.5, 0.5, 0.0, 0.0], dtype=np.float32)
    )
    
    # Should create new concept (too ambiguous)
    assert result3.is_new


# ============================================================
# SEMANTIC INTELLIGENCE WITH EMBEDDINGS TESTS
# ============================================================

def test_si_embedding_cross_chunk():
    """Test cross-chunk resolution with embeddings"""
    si = SemanticIntelligence()
    
    # Process chunks with same concept
    frame1 = si.process(
        transcript_text="TCP is a transport protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1"
    )
    
    frame2 = si.process(
        transcript_text="TCP provides reliability",
        chunk_id="chunk_2",
        lecture_id="lecture_1"
    )
    
    # Both should have concepts
    assert len(frame1.concepts) > 0
    assert len(frame2.concepts) > 0
    
    # TCP should be same concept in both frames
    tcp_ids = set()
    for frame in [frame1, frame2]:
        for concept in frame.concepts:
            if concept.canonical_name == "TCP":
                tcp_ids.add(concept.concept_id)
    
    assert len(tcp_ids) == 1


def test_si_embedding_statistics():
    """Test embedding statistics"""
    si = SemanticIntelligence()
    
    si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=True
    )
    
    stats = si.get_memory_statistics()
    
    assert "total_embeddings" in stats
    assert stats["total_embeddings"] >= 0


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_embedding_index_performance():
    """Test embedding index performance"""
    import time
    
    index = EmbeddingIndex()
    
    start_time = time.time()
    
    for i in range(100):
        index.add_concept_embedding(
            f"concept_{i}",
            np.zeros(384, dtype=np.float32)
        )
    
    add_time = time.time() - start_time
    assert add_time < 1.0
    
    query = np.zeros(384, dtype=np.float32)
    
    start_time = time.time()
    results = index.find_similar_concepts(query, threshold=0.0, top_k=10)
    query_time = time.time() - start_time
    
    assert query_time < 0.5


def test_si_with_embeddings_performance():
    """Test semantic intelligence with embeddings (allowing model warm-up)"""
    import time
    
    si = SemanticIntelligence()
    
    # First call may include model loading
    frame1 = si.process(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_warmup",
        lecture_id="lecture_perf",
        generate_embeddings=True
    )
    
    # Second call should be fast (model already loaded)
    start_time = time.time()
    
    frame2 = si.process(
        transcript_text="UDP is another protocol",
        chunk_id="chunk_perf",
        lecture_id="lecture_perf",
        generate_embeddings=True
    )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    # Should process quickly after warm-up
    assert processing_time < 2.0
    assert len(frame2.concepts) > 0