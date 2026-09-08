"""
Structured Visual Engine - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import (
    SlidePlan,
    ContentBlock,
    ContentBlockType,
    RepresentationType,
    RepresentationDecision,
)
from app.presentation.visuals.structured_visual_engine import StructuredVisualEngine


def create_plan_with_rep(rep_type, blocks=None):
    """Helper to create plan with representation"""
    return SlidePlan(
        slide_id="test",
        focal_message="Test message",
        content_blocks=blocks or [],
        representation=RepresentationDecision(
            representation_type=rep_type,
            confidence=0.8,
            reason="Test",
        ),
    )


def create_relation_blocks():
    """Create content blocks with relations"""
    return [
        ContentBlock(
            block_type=ContentBlockType.EXPLANATION,
            text="TCP CONTRASTS_WITH UDP",
        ),
        ContentBlock(
            block_type=ContentBlockType.EXPLANATION,
            text="TCP PROVIDES reliability",
        ),
    ]


# EASY TESTS

def test_flowchart_spec():
    """Easy: Flowchart spec created"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.FLOWCHART,
        blocks=[
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 2"),
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 3"),
        ],
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is not None
    assert spec["type"] == "flowchart"
    assert len(spec["nodes"]) == 3
    assert len(spec["edges"]) == 2


def test_comparison_spec():
    """Easy: Comparison spec created"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.COMPARISON,
        blocks=create_relation_blocks(),
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is not None
    assert spec["type"] == "comparison_table"


def test_no_visual_for_definition():
    """Easy: Definition doesn't produce structured visual"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(RepresentationType.DEFINITION)
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is None  # Definitions use text layout, not structured visual


# MEDIUM TESTS

def test_hierarchy_spec():
    """Medium: Hierarchy spec from PART_OF relations"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.HIERARCHY,
        blocks=[
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Computer HAS_PART CPU"),
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Computer HAS_PART Memory"),
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Memory HAS_PART RAM"),
        ],
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is not None
    assert spec["type"] == "hierarchy"
    assert spec["root"] == "Computer"


def test_causal_chain_spec():
    """Medium: Causal chain spec"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.CAUSAL_CHAIN,
        blocks=[
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Force CAUSES Acceleration"),
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Acceleration CAUSES Velocity"),
        ],
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is not None
    assert spec["type"] == "causal_chain"
    assert len(spec["chain"]) >= 2


def test_concept_map_spec():
    """Medium: Concept map spec with relations"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.CONCEPT_MAP,
        blocks=create_relation_blocks(),
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert spec is not None
    assert spec["type"] == "concept_map"
    assert len(spec["concepts"]) >= 1


# HARD TESTS

def test_max_nodes_limited():
    """Hard: Node count limited to prevent overflow"""
    engine = StructuredVisualEngine()
    blocks = [
        ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text=f"Step {i}")
        for i in range(20)
    ]
    plan = create_plan_with_rep(RepresentationType.FLOWCHART, blocks=blocks)
    
    spec = engine.build_visual_spec(plan)
    
    assert len(spec["nodes"]) <= 6


def test_empty_blocks_returns_spec():
    """Hard: Empty blocks still produce valid spec for some types"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(RepresentationType.FLOWCHART, blocks=[])
    
    spec = engine.build_visual_spec(plan)
    
    # Flowchart with no nodes is valid (empty)
    assert spec is not None
    assert spec["type"] == "flowchart"


def test_duplicate_nodes_deduplicated():
    """Hard: Duplicate nodes removed"""
    engine = StructuredVisualEngine()
    plan = create_plan_with_rep(
        RepresentationType.FLOWCHART,
        blocks=[
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 1"),
            ContentBlock(block_type=ContentBlockType.PROCESS_STEP, text="Step 2"),
        ],
    )
    
    spec = engine.build_visual_spec(plan)
    
    assert len(spec["nodes"]) == 2  # Duplicate removed


# GENERIC TESTS

def test_all_visual_types():
    """Generic: All structured visual types produce valid spec"""
    engine = StructuredVisualEngine()
    
    visual_types = [
        RepresentationType.FLOWCHART,
        RepresentationType.COMPARISON,
        RepresentationType.CONTRAST,
        RepresentationType.HIERARCHY,
        RepresentationType.TIMELINE,
        RepresentationType.CONCEPT_MAP,
        RepresentationType.CAUSAL_CHAIN,
        RepresentationType.PROCESS,
        RepresentationType.EXAMPLE_GRID,
        RepresentationType.SYSTEM_DIAGRAM,
        RepresentationType.ARCHITECTURE_DIAGRAM,
    ]
    
    for rep_type in visual_types:
        plan = create_plan_with_rep(rep_type, blocks=create_relation_blocks())
        spec = engine.build_visual_spec(plan)
        
        assert spec is not None, f"Failed for {rep_type}"
        assert "type" in spec, f"Missing type for {rep_type}"


def test_works_across_domains():
    """Generic: Visual specs work for any domain"""
    engine = StructuredVisualEngine()
    
    domains = {
        "networking": [("TCP", "UDP"), ("Router", "Switch")],
        "biology": [("Photosynthesis", "Respiration"), ("Mitosis", "Meiosis")],
        "physics": [("Force", "Acceleration"), ("Energy", "Work")],
    }
    
    for domain, relations in domains.items():
        blocks = [
            ContentBlock(
                block_type=ContentBlockType.EXPLANATION,
                text=f"{source} CONTRASTS_WITH {target}",
            )
            for source, target in relations
        ]
        
        plan = create_plan_with_rep(RepresentationType.COMPARISON, blocks=blocks)
        spec = engine.build_visual_spec(plan)
        
        assert spec is not None, f"Failed for {domain}"
        assert spec["type"] == "comparison_table"