"""
Phase 2 Tests: Semantic Memory / Entity Identity (Fixed)

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


# [Keep all existing tests here - they already pass]

# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_memory_scaling():
    """Test that memory scales reasonably (with warm-up)"""
    import time
    
    si = SemanticIntelligence()
    
    # Warm-up
    si.process(
        transcript_text="Warm up concept",
        chunk_id="chunk_warmup",
        lecture_id="lecture_scaling",
        generate_embeddings=False
    )
    
    start_time = time.time()
    
    for i in range(50):
        si.process(
            transcript_text=f"Concept {i} is related to concept {i+1}",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_scaling",
            generate_embeddings=False
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 5.0
    
    stats = si.get_memory_statistics()
    assert stats["registry"]["total_concepts"] > 0