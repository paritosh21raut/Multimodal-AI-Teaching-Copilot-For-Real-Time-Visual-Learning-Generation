"""
Term Tracker Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.speech.term_tracker import TermTracker


def test_add_term():
    """Test adding terms"""
    tracker = TermTracker()
    
    tracker.add_term("Proportional")
    tracker.add_term("Proportional")
    tracker.add_term("Proportional")
    
    trusted = tracker.get_trusted_terms()
    
    assert "proportional" in trusted


def test_correct_misrecognition():
    """Test correcting misrecognition"""
    tracker = TermTracker()
    
    # Add "Proportional" multiple times
    for _ in range(5):
        tracker.add_term("Proportional")
    
    # Now correct "Portional" (misrecognition)
    text = "Portional integral and derivative"
    corrected, corrections = tracker.correct(text)
    
    assert "Proportional" in corrected
    assert len(corrections) > 0


def test_no_correction_without_trust():
    """Test that no correction happens without enough occurrences"""
    tracker = TermTracker()
    
    # Add term only once
    tracker.add_term("Proportional")
    
    text = "Portional integral"
    corrected, corrections = tracker.correct(text)
    
    # Should NOT correct (not enough occurrences)
    assert "Portional" in corrected
    assert len(corrections) == 0


def test_add_terms_from_text():
    """Test extracting terms from text"""
    tracker = TermTracker()
    
    text = "TCP provides reliable transmission. TCP uses acknowledgements. TCP is connection-oriented."
    tracker.add_terms_from_text(text)
    
    trusted = tracker.get_trusted_terms()
    
    # TCP should be trusted after 3 occurrences
    assert "tcp" in trusted


def test_similarity_threshold():
    """Test that dissimilar terms are not matched"""
    tracker = TermTracker()
    
    # Add "TCP" multiple times
    for _ in range(5):
        tracker.add_term("TCP")
    
    # Try to correct "UDP" (should NOT match TCP)
    text = "UDP is connectionless"
    corrected, corrections = tracker.correct(text)
    
    # UDP should remain unchanged
    assert "UDP" in corrected