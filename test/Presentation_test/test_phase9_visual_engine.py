"""
Phase 9: Structured Visual Engine - Production Readiness Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.visuals.structured_visual_engine import StructuredVisualEngine
from app.presentation.models.presentation_models import (
    SlidePlan, ContentBlock, ContentBlockType, RepresentationType, RepresentationDecision,
)


def create_plan(rep_type, blocks=None):
    return SlidePlan(
        focal_message="Test",
        content_blocks=blocks or [],
        representation=RepresentationDecision(
            representation_type=rep_type,
            confidence=0.8,
            reason="Test",
        ),
    )


def test_flowchart_spec():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.FLOWCHART, blocks=[
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 2"),
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 3"),
    ])
    spec = engine.build_visual_spec(plan)
    assert spec is not None
    assert spec["type"] == "flowchart"
    assert len(spec["nodes"]) == 3


def test_comparison_spec():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.COMPARISON, blocks=[
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="TCP CONTRASTS_WITH UDP"),
    ])
    spec = engine.build_visual_spec(plan)
    assert spec is not None
    assert spec["type"] == "comparison_table"


def test_hierarchy_spec():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.HIERARCHY, blocks=[
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Computer HAS_PART CPU"),
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Computer HAS_PART Memory"),
    ])
    spec = engine.build_visual_spec(plan)
    assert spec is not None
    assert spec["type"] == "hierarchy"


def test_causal_chain_spec():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.CAUSAL_CHAIN, blocks=[
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Force CAUSES Acceleration"),
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Acceleration CAUSES Velocity"),
    ])
    spec = engine.build_visual_spec(plan)
    assert spec is not None
    assert spec["type"] == "causal_chain"


def test_concept_map_spec():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.CONCEPT_MAP, blocks=[
        ContentBlock(block_type=ContentBlockType.EXPLANATION, text="A RELATES_TO B"),
    ])
    spec = engine.build_visual_spec(plan)
    assert spec is not None
    assert spec["type"] == "concept_map"


def test_max_nodes_limited():
    engine = StructuredVisualEngine()
    blocks = [ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text=f"Step {i}") for i in range(20)]
    plan = create_plan(RepresentationType.FLOWCHART, blocks=blocks)
    spec = engine.build_visual_spec(plan)
    assert len(spec["nodes"]) <= 6


def test_deduplicates_nodes():
    engine = StructuredVisualEngine()
    plan = create_plan(RepresentationType.FLOWCHART, blocks=[
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 2"),
    ])
    spec = engine.build_visual_spec(plan)
    assert len(spec["nodes"]) == 2


def test_works_across_domains():
    engine = StructuredVisualEngine()
    domains = {
        "networking": ("TCP", "UDP"),
        "biology": ("Photosynthesis", "Respiration"),
        "physics": ("Force", "Acceleration"),
    }
    for domain, (a, b) in domains.items():
        plan = create_plan(RepresentationType.COMPARISON, blocks=[
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text=f"{a} CONTRASTS_WITH {b}"),
        ])
        spec = engine.build_visual_spec(plan)
        assert spec is not None, f"Failed for {domain}"
        