"""
Audio Quality Monitor Tests
"""

from __future__ import annotations

import sys
import os
import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.audio.audio_quality import AudioQualityMonitor


@pytest.fixture
def monitor():
    return AudioQualityMonitor()


def test_silence_detection(monitor):
    """Test silence detection"""
    silence = np.zeros(16000, dtype=np.float32)
    metrics = monitor.analyze(silence)
    
    assert metrics["is_silence"]
    assert metrics["quality"] == "silence"
    assert metrics["rms_db"] < -50


def test_normal_speech_level(monitor):
    """Test normal speech level"""
    # Simulate speech at ~-20 dB
    speech = np.random.randn(16000).astype(np.float32) * 0.1
    metrics = monitor.analyze(speech)
    
    assert not metrics["clipped"]
    assert not metrics["is_silence"]
    assert metrics["quality"] in ["good", "acceptable", "marginal"]


def test_clipping_detection(monitor):
    """Test clipping detection"""
    # Very loud audio that clips
    loud = np.ones(16000, dtype=np.float32) * 0.99
    metrics = monitor.analyze(loud)
    
    assert metrics["clipped"]
    assert metrics["quality"] == "clipping"


def test_low_volume_detection(monitor):
    """Test low volume detection"""
    # Very quiet audio
    quiet = np.random.randn(16000).astype(np.float32) * 0.001
    metrics = monitor.analyze(quiet)
    
    assert metrics["low_volume"]
    assert metrics["quality"] == "too_quiet"


def test_dc_offset_detection(monitor):
    """Test DC offset detection"""
    # Audio with DC offset
    dc_audio = np.ones(16000, dtype=np.float32) * 0.05
    metrics = monitor.analyze(dc_audio)
    
    assert metrics["has_dc_offset"]


def test_statistics(monitor):
    """Test statistics accumulation"""
    # Process multiple chunks
    for _ in range(10):
        silence = np.zeros(8000, dtype=np.float32)
        monitor.analyze(silence)
    
    for _ in range(10):
        speech = np.random.randn(8000).astype(np.float32) * 0.1
        monitor.analyze(speech)
    
    stats = monitor.get_statistics()
    
    assert stats["total_chunks"] == 20
    assert "silence_ratio" in stats
    assert "avg_rms_db" in stats
    assert "current_quality" in stats