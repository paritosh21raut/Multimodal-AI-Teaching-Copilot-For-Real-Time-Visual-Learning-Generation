"""
Whisper Confidence Tests

Tests confidence scoring in Whisper model.
"""

from __future__ import annotations

import sys
import os
import numpy as np
import pytest

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.speech.whisper_model import WhisperModel


@pytest.fixture(scope="module")
def whisper_model():
    """Load Whisper model once for all tests"""
    return WhisperModel()


def test_confidence_calculation(whisper_model):
    """Test confidence calculation"""
    confidence = whisper_model._calculate_confidence(
        avg_logprob=-0.5,
        no_speech_prob=0.1,
        compression_ratio=1.0,
    )
    
    assert confidence is not None
    assert "overall_confidence" in confidence
    assert 0.0 <= confidence["overall_confidence"] <= 1.0
    assert confidence["overall_confidence"] > 0.5  # Good quality


def test_confidence_low_quality(whisper_model):
    """Test confidence for poor quality audio"""
    confidence = whisper_model._calculate_confidence(
        avg_logprob=-2.0,
        no_speech_prob=0.8,
        compression_ratio=3.0,
    )
    
    assert confidence["overall_confidence"] < 0.5  # Poor quality


def test_confidence_bounds(whisper_model):
    """Test confidence stays within bounds"""
    # Extreme values
    confidence = whisper_model._calculate_confidence(
        avg_logprob=-5.0,
        no_speech_prob=1.0,
        compression_ratio=5.0,
    )
    
    assert 0.0 <= confidence["overall_confidence"] <= 1.0


def test_transcribe_with_confidence(whisper_model):
    """Test transcription with confidence (short audio)"""
    # Create 2 seconds of silence (should return low confidence)
    audio = np.zeros(32000, dtype=np.float32)
    
    text, confidence = whisper_model.transcribe_with_confidence(audio)
    
    assert confidence is not None
    assert "overall_confidence" in confidence