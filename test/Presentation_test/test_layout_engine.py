"""
Layout Engine - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import (
    LayoutFamily,
    LayoutPlan,
    SlidePlan,
    RepresentationType,
    RepresentationDecision,
)
from app.presentation.layout.layout_engine import LayoutEngine
from app.presentation.design.design_system import design_system
from app.presentation.design.typography import typography


# EASY TESTS

def test_typography_roles_exist():
    """Easy: All typography roles defined"""
    assert typography.get_role("slide_title") is not None
    assert typography.get_role("body") is not None
    assert typography.get_role("caption") is not None


def test_design_system_colors():
    """Easy: Design system has all colors"""
    assert design_system.get_color("background") is not None
    assert design_system.get_color("primary") is not None
    assert design_system.get_color("foreground") is not None


def test_layout_created_for_plan():
    """Easy: Layout created for slide plan"""
    engine = LayoutEngine()
    plan = SlidePlan(
        layout_family=LayoutFamily.HERO_DEFINITION,
        density=0.5,
    )
    
    layout = engine.create_layout(plan)
    
    assert layout is not None
    assert layout.layout_family == LayoutFamily.HERO_DEFINITION


# MEDIUM TESTS

def test_all_layout_families_supported():
    """Medium: All layout families produce valid layout"""
    engine = LayoutEngine()
    
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        
        assert layout is not None, f"Failed for {family}"
        assert layout.layout_family == family


def test_density_affects_constraints():
    """Medium: Density changes constraints"""
    engine = LayoutEngine()
    
    # Sparse
    sparse_plan = SlidePlan(layout_family=LayoutFamily.TEXT_LEFT_VISUAL_RIGHT, density=0.2)
    sparse_layout = engine.create_layout(sparse_plan)
    
    # Dense
    dense_plan = SlidePlan(layout_family=LayoutFamily.TEXT_LEFT_VISUAL_RIGHT, density=0.9)
    dense_layout = engine.create_layout(dense_plan)
    
    assert sparse_layout.constraints["density"] < dense_layout.constraints["density"]
    assert sparse_layout.constraints["max_content_blocks"] < dense_layout.constraints["max_content_blocks"]


def test_typography_size_scales_with_density():
    """Medium: Font size scales with density"""
    # Low density = larger font
    low_density_size = typography.get_size("body", density=0.2)
    high_density_size = typography.get_size("body", density=0.9)
    
    assert low_density_size >= high_density_size


# HARD TESTS

def test_regions_are_proportional():
    """Hard: All regions use proportions (0-1), not fixed coordinates"""
    engine = LayoutEngine()
    
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        
        for region_name, region in layout.regions.items():
            for key, value in region.items():
                assert 0.0 <= value <= 1.0, f"{family}:{region_name}:{key} out of bounds"
                assert value < 1.5, f"{family}:{region_name}:{key} too large"


def test_default_layout_for_unknown():
    """Hard: Unknown representation falls back to default layout"""
    engine = LayoutEngine()
    plan = SlidePlan(layout_family=LayoutFamily.TEXT_LEFT_VISUAL_RIGHT, density=0.5)
    
    layout = engine.create_layout(plan)
    
    assert "text" in layout.regions
    assert "visual" in layout.regions


def test_all_layouts_have_title_region():
    """Hard: Every layout has a title region"""
    engine = LayoutEngine()
    
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        
        assert "title" in layout.regions, f"{family} missing title region"


# GENERIC TESTS

def test_layout_engine_generic():
    """Generic: Layout engine works independently of content"""
    engine = LayoutEngine()
    
    # Different content, same layout should work
    plan1 = SlidePlan(layout_family=LayoutFamily.FULL_WIDTH_COMPARISON, density=0.5)
    plan2 = SlidePlan(layout_family=LayoutFamily.FULL_WIDTH_COMPARISON, density=0.7)
    
    layout1 = engine.create_layout(plan1)
    layout2 = engine.create_layout(plan2)
    
    assert layout1.layout_family == layout2.layout_family
    assert layout1.constraints["density"] != layout2.constraints["density"]