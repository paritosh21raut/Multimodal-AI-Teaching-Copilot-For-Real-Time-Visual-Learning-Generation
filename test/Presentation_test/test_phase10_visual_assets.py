"""
Phase 10: Visual Asset Intelligence - Production Readiness Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.visual_assets.visual_asset_engine import (
    VisualAssetEngine, VisualAssetCandidate, VisualAssetResult,
)


def test_no_visual_for_comparison():
    engine = VisualAssetEngine()
    result = engine.decide(
        concepts=["TCP", "UDP"],
        representation_type="comparison",
    )
    assert not result.selected


def test_no_visual_for_flowchart():
    engine = VisualAssetEngine()
    result = engine.decide(
        concepts=["TCP"],
        representation_type="flowchart",
    )
    assert not result.selected


def test_native_diagram_fallback_when_no_concepts():
    engine = VisualAssetEngine()
    result = engine.decide(
        concepts=[],
        representation_type="explanation",
        visual_need="image",
    )
    assert result.use_native_diagram


def test_scoring_ranks_relevant_higher():
    engine = VisualAssetEngine()
    relevant = VisualAssetCandidate(
        source="wikimedia", url="x", title="TCP Diagram",
        tags=["tcp", "protocol", "network"], width=1920, height=1080,
        license="CC BY-SA",
    )
    irrelevant = VisualAssetCandidate(
        source="pixabay", url="y", title="Random",
        tags=["random"], width=800, height=600, license="",
    )
    scored = engine._score_candidates([irrelevant, relevant], concepts=["tcp"])
    assert scored[0] == relevant


def test_source_trust_affects_score():
    engine = VisualAssetEngine()
    wiki = VisualAssetCandidate(source="wikimedia", url="x", title="T", tags=["t"], width=1920, height=1080)
    pixabay = VisualAssetCandidate(source="pixabay", url="y", title="T", tags=["t"], width=1920, height=1080)
    scored = engine._score_candidates([pixabay, wiki], concepts=["t"])
    assert scored[0].source == "wikimedia"


def test_low_confidence_rejected():
    engine = VisualAssetEngine()
    poor = VisualAssetCandidate(source="pixabay", url="x", title="", tags=[], width=100, height=100)
    engine._cache["test"] = [poor]
    result = engine.decide(concepts=["test"], representation_type="explanation", visual_need="image")
    assert not result.selected
    assert result.use_native_diagram


def test_works_across_domains():
    engine = VisualAssetEngine()
    domains = {
        "networking": ["TCP", "protocol"],
        "biology": ["photosynthesis", "plant"],
        "physics": ["force", "motion"],
    }
    for domain, concepts in domains.items():
        result = engine.decide(
            concepts=concepts,
            representation_type="explanation",
            visual_need="educational_diagram",
        )
        assert result is not None
        assert result.selected or result.use_native_diagram