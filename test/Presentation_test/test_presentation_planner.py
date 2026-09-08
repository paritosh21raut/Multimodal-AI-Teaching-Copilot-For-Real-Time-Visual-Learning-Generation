"""
Presentation Planner - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import (
    SlideAction,
    SlidePlan,
    ContentBlockType,
    LayoutFamily,
    RepresentationType,
    RepresentationDecision,
    SelectedInformation,
    SlideDecision,
)
from app.presentation.planner.presentation_planner import PresentationPlanner


def create_test_selection():
    """Create test selected information"""
    return SelectedInformation(
        focal_claim="TCP is a connection-oriented protocol",
        semantic_units=["TCP PROVIDES reliable delivery"],
        definitions=["TCP"],
        examples=["three-way handshake"],
        evidence_ids=["e1", "e2"],
    )


def create_test_representation(rep_type=RepresentationType.DEFINITION):
    """Create test representation decision"""
    return RepresentationDecision(
        representation_type=rep_type,
        confidence=0.85,
        reason="Test",
    )


def create_test_slide_decision(action=SlideAction.CREATE_NEW):
    """Create test slide decision"""
    return SlideDecision(
        action=action,
        trigger="topic_change",
        confidence=0.9,
        reason="New topic",
    )


# EASY TESTS

def test_plan_created():
    """Easy: Plan is created with all fields"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
        topic_id="tcp",
    )
    
    assert plan is not None
    assert plan.slide_id != ""
    assert plan.topic_id == "tcp"
    assert plan.focal_message != ""


def test_layout_family_for_definition():
    """Easy: Definition → HERO_DEFINITION layout"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(RepresentationType.DEFINITION),
    )
    
    assert plan.layout_family == LayoutFamily.HERO_DEFINITION


def test_layout_family_for_comparison():
    """Easy: Comparison → FULL_WIDTH_COMPARISON"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(RepresentationType.COMPARISON),
    )
    
    assert plan.layout_family == LayoutFamily.FULL_WIDTH_COMPARISON


# MEDIUM TESTS

def test_content_blocks_created():
    """Medium: Content blocks built from selection"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    
    assert len(plan.content_blocks) >= 1
    # Focal claim should be first (highest priority)
    assert plan.content_blocks[0].block_type == ContentBlockType.KEY_CLAIM


def test_evidence_preserved():
    """Medium: Evidence IDs preserved in plan"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    
    assert "e1" in plan.evidence_ids
    assert "e2" in plan.evidence_ids


def test_density_calculated():
    """Medium: Density calculated from content amount"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    
    assert 0.0 <= plan.density <= 1.0


# HARD TESTS

def test_different_layouts_for_different_representations():
    """Hard: Each representation gets correct layout"""
    planner = PresentationPlanner()
    
    mapping = {
        RepresentationType.DEFINITION: LayoutFamily.HERO_DEFINITION,
        RepresentationType.COMPARISON: LayoutFamily.FULL_WIDTH_COMPARISON,
        RepresentationType.CONTRAST: LayoutFamily.TWO_COLUMN_CONTRAST,
        RepresentationType.FLOWCHART: LayoutFamily.FULL_WIDTH_PROCESS,
        RepresentationType.HIERARCHY: LayoutFamily.HIERARCHY_CENTERED,
        RepresentationType.NUMBER_STATISTIC: LayoutFamily.BIG_NUMBER,
        RepresentationType.FORMULA: LayoutFamily.CENTERED_FORMULA,
        RepresentationType.EXAMPLE_GRID: LayoutFamily.EXAMPLE_GRID,
    }
    
    for rep_type, expected_layout in mapping.items():
        plan = planner.plan(
            slide_decision=create_test_slide_decision(),
            selected_info=create_test_selection(),
            representation=create_test_representation(rep_type),
        )
        assert plan.layout_family == expected_layout, f"Failed for {rep_type}"


def test_sparse_content_low_density():
    """Hard: Sparse content gives low density"""
    planner = PresentationPlanner()
    
    sparse_info = SelectedInformation(
        focal_claim="Simple claim",
        semantic_units=[],
        definitions=[],
        examples=[],
    )
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=sparse_info,
        representation=create_test_representation(),
    )
    
    assert plan.density <= 0.4


def test_dense_content_high_density():
    """Hard: Dense content gives high density"""
    planner = PresentationPlanner()
    
    dense_info = SelectedInformation(
        focal_claim="Claim",
        semantic_units=[f"unit_{i}" for i in range(6)],
        definitions=["d1", "d2"],
        examples=["e1", "e2", "e3"],
        numbers=[{"value": 42}],
    )
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=dense_info,
        representation=create_test_representation(),
    )
    
    assert plan.density >= 0.7


# GENERIC TESTS

def test_works_with_empty_representation():
    """Generic: No representation → default layout"""
    planner = PresentationPlanner()
    
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=None,
    )
    
    assert plan.layout_family == LayoutFamily.TEXT_LEFT_VISUAL_RIGHT


def test_planner_generic_across_domains():
    """Generic: Planner works for any domain content"""
    planner = PresentationPlanner()
    
    domains = {
        "networking": "TCP provides reliability",
        "biology": "Photosynthesis converts light to energy",
        "physics": "Force equals mass times acceleration",
        "math": "Derivative represents rate of change",
    }
    
    for domain, claim in domains.items():
        info = SelectedInformation(
            focal_claim=claim,
            semantic_units=[claim],
        )
        
        plan = planner.plan(
            slide_decision=create_test_slide_decision(),
            selected_info=info,
            representation=create_test_representation(RepresentationType.EXPLANATION),
            topic_id=domain,
        )
        
        assert plan.topic_id == domain
        assert plan.focal_message == claim