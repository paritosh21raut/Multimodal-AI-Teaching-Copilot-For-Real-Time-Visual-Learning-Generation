"""
Term Tracker Tests (Fixed for acronym preservation)
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
    
    for _ in range(5):
        tracker.add_term("Proportional")
    
    text = "Portional integral and derivative"
    corrected, corrections = tracker.correct(text)
    
    assert "Proportional" in corrected
    assert len(corrections) > 0


def test_no_correction_without_trust():
    """Test that no correction happens without enough occurrences"""
    tracker = TermTracker()
    
    tracker.add_term("Proportional")
    
    text = "Portional integral"
    corrected, corrections = tracker.correct(text)
    
    assert "Portional" in corrected
    assert len(corrections) == 0


def test_add_terms_from_text():
    """Test extracting terms - acronyms preserved as uppercase"""
    tracker = TermTracker()
    
    text = "TCP provides reliable transmission. TCP uses acknowledgements. TCP is connection-oriented."
    tracker.add_terms_from_text(text)
    
    trusted = tracker.get_trusted_terms()
    
    # TCP should be trusted (uppercase preserved)
    assert "TCP" in trusted


def test_similarity_threshold():
    """Test that dissimilar terms are not matched"""
    tracker = TermTracker()
    
    for _ in range(5):
        tracker.add_term("TCP")
    
    text = "UDP is connectionless"
    corrected, corrections = tracker.correct(text)
    
    # UDP should remain unchanged
    assert "UDP" in corrected


def test_acronym_preservation():
    """Test that acronyms are not lowercased"""
    tracker = TermTracker()
    
    for _ in range(5):
        tracker.add_term("TCP")
    
    text = "TCP provides reliable delivery"
    corrected, corrections = tracker.correct(text)
    
    # TCP should stay TCP (not Tcp)
    assert "TCP" in corrected
    assert "Tcp" not in corrected