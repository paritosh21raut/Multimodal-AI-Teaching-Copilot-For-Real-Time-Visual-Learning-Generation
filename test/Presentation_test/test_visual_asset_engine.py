"""
Visual Asset Engine - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.visual_assets.visual_asset_engine import (
    VisualAssetEngine,
    VisualAssetCandidate,
    VisualAssetResult,
)


# EASY TESTS

def test_engine_initializes():
    """Easy: Engine initializes"""
    engine = VisualAssetEngine()
    assert engine is not None


def test_no_visual_for_comparison():
    """Easy: Comparison doesn't need external image"""
    engine = VisualAssetEngine()
    
    result = engine.decide(
        concepts=["TCP", "UDP"],
        representation_type="comparison",
        visual_need="none",
    )
    
    assert not result.selected
    assert "No visual needed" in result.reason


def test_no_visual_for_flowchart():
    """Easy: Flowchart doesn't need external image"""
    engine = VisualAssetEngine()
    
    result = engine.decide(
        concepts=["TCP"],
        representation_type="flowchart",
    )
    
    assert not result.selected


# MEDIUM TESTS

def test_visual_needed_for_explanation():
    """Medium: Explanation may benefit from image"""
    engine = VisualAssetEngine()
    
    result = engine.decide(
        concepts=["photosynthesis"],
        representation_type="explanation",
        visual_need="educational_diagram",
    )
    
    # Either selects or falls back to native diagram
    assert result is not None
    assert result.use_native_diagram or result.selected


def test_no_concepts_uses_native_diagram():
    """Medium: No concepts = native diagram"""
    engine = VisualAssetEngine()
    
    result = engine.decide(
        concepts=[],
        representation_type="explanation",
        visual_need="image",
    )
    
    assert not result.selected
    assert result.use_native_diagram


def test_scoring_ranks_relevant_higher():
    """Medium: Relevant candidates score higher"""
    engine = VisualAssetEngine()
    
    relevant = VisualAssetCandidate(
        source="wikimedia",
        url="http://test.com/relevant.jpg",
        title="Photosynthesis Diagram",
        tags=["photosynthesis", "biology", "plant", "chlorophyll"],
        license="CC BY-SA",
        width=1920,
        height=1080,
    )
    
    irrelevant = VisualAssetCandidate(
        source="pixabay",
        url="http://test.com/random.jpg",
        title="Generic Nature",
        tags=["nature", "green", "leaf"],
        license="",
        width=800,
        height=600,
    )
    
    scored = engine._score_candidates(
        [irrelevant, relevant],
        concepts=["photosynthesis"],
    )
    
    assert scored[0] == relevant
    assert scored[0].overall_score > scored[1].overall_score


# HARD TESTS

def test_low_confidence_rejected():
    """Hard: Low confidence candidates rejected"""
    engine = VisualAssetEngine()
    
    poor_candidate = VisualAssetCandidate(
        source="pixabay",
        url="http://test.com/poor.jpg",
        title="",
        tags=[],
        license="",
        width=100,
        height=100,
    )
    
    # Inject candidate into cache
    engine._cache["test"] = [poor_candidate]
    
    result = engine.decide(
        concepts=["test"],
        representation_type="explanation",
        visual_need="image",
    )
    
    assert not result.selected
    assert result.use_native_diagram


def test_source_trust_affects_score():
    """Hard: High trust sources score better"""
    engine = VisualAssetEngine()
    
    wikimedia = VisualAssetCandidate(
        source="wikimedia",
        url="http://test.com/wiki.jpg",
        title="Educational Diagram",
        tags=["diagram", "education"],
        width=1920,
        height=1080,
    )
    
    pixabay = VisualAssetCandidate(
        source="pixabay",
        url="http://test.com/pixabay.jpg",
        title="Educational Diagram",
        tags=["diagram", "education"],
        width=1920,
        height=1080,
    )
    
    scored = engine._score_candidates([pixabay, wikimedia], concepts=["diagram"])
    
    assert scored[0].source == "wikimedia"


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Works for any domain"""
    engine = VisualAssetEngine()
    
    domains = {
        "networking": ["TCP", "protocol"],
        "biology": ["photosynthesis", "plant"],
        "physics": ["force", "motion"],
        "math": ["derivative", "calculus"],
    }
    
    for domain, concepts in domains.items():
        result = engine.decide(
            concepts=concepts,
            representation_type="explanation",
            visual_need="educational_diagram",
        )
        
        assert result is not None
        # Either selects or falls back
        assert result.selected or result.use_native_diagram