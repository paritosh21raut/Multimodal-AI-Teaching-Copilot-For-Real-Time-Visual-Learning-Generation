"""
Integration Tests

Tests that Semantic Intelligence integrates correctly with
LecturePipeline and existing systems.
"""

from __future__ import annotations

import pytest
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.semantic.semantic_pipeline import SemanticPipeline


# ============================================================
# SEMANTIC PIPELINE INTEGRATION TESTS
# ============================================================

def test_semantic_pipeline_standalone():
    """Test semantic pipeline works standalone"""
    pipeline = SemanticPipeline()
    
    result = pipeline.process_transcript(
        transcript_text="TCP provides reliable delivery",
        chunk_id="chunk_1",
        lecture_id="lecture_test",
        generate_embeddings=False
    )
    
    assert result is not None
    assert result["frame"] is not None
    assert result["slide_content"] is not None


def test_semantic_pipeline_multiple_domains():
    """Test semantic pipeline across domains"""
    pipeline = SemanticPipeline()
    
    domains = {
        "networks": "TCP provides reliable delivery",
        "electronics": "A transistor amplifies signals",
        "databases": "An index improves query performance",
        "physics": "Force equals mass times acceleration",
    }
    
    for domain, text in domains.items():
        result = pipeline.process_transcript(
            transcript_text=text,
            chunk_id=f"chunk_{domain}",
            lecture_id="lecture_domains",
            generate_embeddings=False
        )
        
        assert result is not None
        assert result["frame"] is not None


def test_semantic_pipeline_slide_content():
    """Test that slide content is generated"""
    pipeline = SemanticPipeline()
    
    result = pipeline.process_transcript(
        transcript_text="TCP is a transport protocol that provides reliable delivery",
        chunk_id="chunk_slide",
        lecture_id="lecture_slide",
        generate_embeddings=False
    )
    
    assert result is not None
    
    slide_content = result.get("slide_content")
    assert slide_content is not None
    
    if slide_content:
        assert hasattr(slide_content, "key_concepts")
        assert hasattr(slide_content, "propositions")


def test_semantic_pipeline_statistics():
    """Test statistics tracking"""
    pipeline = SemanticPipeline()
    
    # Process multiple chunks
    for i in range(5):
        pipeline.process_transcript(
            transcript_text=f"Concept {i} is important",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_stats",
            generate_embeddings=False
        )
    
    stats = pipeline.get_statistics()
    assert stats is not None
    assert "performance" in stats
    assert stats["performance"]["total_frames"] == 5


def test_semantic_pipeline_health():
    """Test health monitoring"""
    pipeline = SemanticPipeline()
    
    pipeline.process_transcript(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_health",
        lecture_id="lecture_health",
        generate_embeddings=False
    )
    
    health = pipeline.get_health_report()
    assert health is not None
    assert health["status"] in ["healthy", "degraded"]


# ============================================================
# GRACEFUL DEGRADATION TESTS
# ============================================================

def test_pipeline_without_llm():
    """Test pipeline works without LLM"""
    from app.semantic.config import SemanticConfig
    
    config = SemanticConfig()
    config.enable_llm = False
    
    pipeline = SemanticPipeline(config=config)
    
    result = pipeline.process_transcript(
        transcript_text="TCP provides reliability",
        chunk_id="chunk_no_llm",
        lecture_id="lecture_no_llm",
        generate_embeddings=False
    )
    
    assert result is not None


def test_pipeline_empty_transcript():
    """Test empty transcript handling"""
    pipeline = SemanticPipeline()
    
    result = pipeline.process_transcript(
        transcript_text="",
        chunk_id="chunk_empty",
        lecture_id="lecture_empty"
    )
    
    assert result is None


def test_pipeline_whitespace_transcript():
    """Test whitespace transcript handling"""
    pipeline = SemanticPipeline()
    
    result = pipeline.process_transcript(
        transcript_text="   ",
        chunk_id="chunk_ws",
        lecture_id="lecture_ws"
    )
    
    assert result is None


# ============================================================
# PERFORMANCE TESTS
# ============================================================

def test_pipeline_sustained_processing():
    """Test sustained processing performance"""
    import time
    
    pipeline = SemanticPipeline()
    
    start_time = time.time()
    
    # Process 20 chunks
    for i in range(20):
        pipeline.process_transcript(
            transcript_text=f"Topic {i} is being discussed in this lecture",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_sustained",
            generate_embeddings=False
        )
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Should process 20 chunks in under 10 seconds (no embeddings)
    assert total_time < 10.0
    
    # Average under 500ms per chunk
    assert total_time / 20 < 0.5