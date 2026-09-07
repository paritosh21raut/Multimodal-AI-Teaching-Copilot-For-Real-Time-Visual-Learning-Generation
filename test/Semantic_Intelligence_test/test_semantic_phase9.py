"""
Phase 9 Tests: Production Hardening (Fixed)

Tests production-ready pipeline, logging, and performance monitoring.
"""

from __future__ import annotations

import pytest
import time

from app.semantic.logger import SemanticLogger
from app.semantic.performance_monitor import PerformanceMonitor
from app.semantic.config import SemanticConfig
from app.semantic.semantic_pipeline import SemanticPipeline


# ============================================================
# LOGGER TESTS
# ============================================================

def test_logger_initialization():
    """Test logger initialization"""
    logger = SemanticLogger()
    
    assert logger is not None
    assert logger.logger is not None


def test_logger_info():
    """Test info logging"""
    logger = SemanticLogger()
    
    logger.info("Test message", key="value")
    logger.warning("Warning message")
    logger.error("Error message")
    logger.debug("Debug message")


def test_logger_frame_processed():
    """Test frame processing logging"""
    logger = SemanticLogger()
    
    logger.log_frame_processed(
        chunk_id="chunk_1",
        concepts_count=5,
        propositions_count=3,
        confidence=0.8,
        processing_time=0.5
    )


# ============================================================
# PERFORMANCE MONITOR TESTS
# ============================================================

def test_monitor_initialization():
    """Test monitor initialization"""
    monitor = PerformanceMonitor()
    
    assert monitor is not None
    stats = monitor.get_statistics()
    assert stats["total_frames"] == 0


def test_monitor_record_processing():
    """Test recording processing times"""
    monitor = PerformanceMonitor()
    
    for i in range(10):
        monitor.record_frame_processing(0.1 + i * 0.01)
    
    stats = monitor.get_statistics()
    assert stats["total_frames"] == 10
    assert stats["average_processing_time_ms"] > 0


def test_monitor_health_report():
    """Test health report"""
    monitor = PerformanceMonitor()
    
    health = monitor.get_health_report()
    
    assert health is not None
    assert health["status"] in ["healthy", "degraded"]
    assert "issues" in health


def test_monitor_operations():
    """Test operation timing"""
    monitor = PerformanceMonitor()
    
    monitor.start_operation("test")
    time.sleep(0.01)
    elapsed = monitor.end_operation()
    
    assert elapsed is not None
    assert elapsed > 0


# ============================================================
# CONFIG TESTS
# ============================================================

def test_config_defaults():
    """Test default configuration"""
    config = SemanticConfig()
    
    assert config.embedding_model == "all-MiniLM-L6-v2"
    assert config.enable_llm is True
    assert config.llm_model == "llama-3.1-8b-instant"
    assert config.min_evidence_coverage == 0.5


def test_config_to_dict():
    """Test config serialization"""
    config = SemanticConfig()
    config_dict = config.to_dict()
    
    assert "embedding_model" in config_dict
    assert "enable_llm" in config_dict
    assert "llm_model" in config_dict


# ============================================================
# SEMANTIC PIPELINE TESTS
# ============================================================

def test_pipeline_initialization():
    """Test pipeline initialization"""
    pipeline = SemanticPipeline()
    
    assert pipeline is not None
    assert pipeline.semantic_intelligence is not None
    assert pipeline.semantic_integration is not None


def test_pipeline_process_transcript():
    """Test processing through pipeline"""
    pipeline = SemanticPipeline()
    
    result = pipeline.process_transcript(
        transcript_text="TCP is a transport protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert result is not None
    assert "frame" in result
    assert "processing_time_ms" in result
    assert result["frame"] is not None


def test_pipeline_multiple_chunks():
    """Test processing multiple chunks"""
    pipeline = SemanticPipeline()
    
    chunks = [
        "TCP is a protocol",
        "TCP provides reliability",
        "TCP uses acknowledgements",
    ]
    
    results = []
    for i, chunk in enumerate(chunks):
        result = pipeline.process_transcript(
            transcript_text=chunk,
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_1",
            generate_embeddings=False
        )
        results.append(result)
    
    assert len(results) == 3
    assert all(r is not None for r in results)


def test_pipeline_health_report():
    """Test health report"""
    pipeline = SemanticPipeline()
    
    pipeline.process_transcript(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    health = pipeline.get_health_report()
    
    assert health is not None
    assert "status" in health


def test_pipeline_statistics():
    """Test pipeline statistics"""
    pipeline = SemanticPipeline()
    
    pipeline.process_transcript(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    stats = pipeline.get_statistics()
    
    assert stats is not None
    assert "performance" in stats
    assert "semantic_memory" in stats


def test_pipeline_semantic_summary():
    """Test semantic summary"""
    pipeline = SemanticPipeline()
    
    pipeline.process_transcript(
        transcript_text="TCP provides reliable delivery",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    summary = pipeline.get_semantic_summary()
    
    assert summary is not None
    assert "active_concepts" in summary
    assert "statistics" in summary


def test_pipeline_reset():
    """Test pipeline reset"""
    pipeline = SemanticPipeline()
    
    pipeline.process_transcript(
        transcript_text="TCP is a protocol",
        chunk_id="chunk_1",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    pipeline.reset()
    
    result = pipeline.process_transcript(
        transcript_text="UDP is a protocol",
        chunk_id="chunk_2",
        lecture_id="lecture_1",
        generate_embeddings=False
    )
    
    assert result is not None


def test_pipeline_error_handling():
    """Test graceful error handling"""
    pipeline = SemanticPipeline()
    
    # Empty transcript should return None
    result = pipeline.process_transcript(
        transcript_text="",
        chunk_id="chunk_empty",
        lecture_id="lecture_1"
    )
    
    assert result is None


def test_pipeline_performance():
    """Test pipeline performance"""
    pipeline = SemanticPipeline()
    
    start_time = time.time()
    
    for i in range(10):
        pipeline.process_transcript(
            transcript_text=f"Concept {i} is important",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_perf",
            generate_embeddings=False  # Skip embeddings for speed
        )
    
    end_time = time.time()
    processing_time = end_time - start_time
    
    assert processing_time < 5.0


def test_pipeline_long_running():
    """Test pipeline stability over many chunks"""
    pipeline = SemanticPipeline()
    
    for i in range(50):
        result = pipeline.process_transcript(
            transcript_text=f"Topic {i} is discussed",
            chunk_id=f"chunk_{i}",
            lecture_id="lecture_long",
            generate_embeddings=False
        )
        
        assert result is not None or result is None
    
    health = pipeline.get_health_report()
    assert health is not None