"""
Phase 8: Layout + Design System - Production Readiness Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.layout.layout_engine import LayoutEngine
from app.presentation.design.design_system import design_system
from app.presentation.design.typography import typography
from app.presentation.models.presentation_models import LayoutFamily, SlidePlan


def test_all_layout_families_supported():
    engine = LayoutEngine()
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        assert layout is not None, f"Failed for {family}"


def test_density_affects_constraints():
    engine = LayoutEngine()
    sparse = SlidePlan(layout_family=LayoutFamily.TEXT_LEFT_VISUAL_RIGHT, density=0.2)
    dense = SlidePlan(layout_family=LayoutFamily.TEXT_LEFT_VISUAL_RIGHT, density=0.9)
    l1 = engine.create_layout(sparse)
    l2 = engine.create_layout(dense)
    assert l1.constraints["density"] < l2.constraints["density"]


def test_typography_scales_with_density():
    low = typography.get_size("body", density=0.2)
    high = typography.get_size("body", density=0.9)
    assert low >= high


def test_design_system_colors_exist():
    assert design_system.get_color("background") is not None
    assert design_system.get_color("primary") is not None
    assert design_system.get_color("foreground") is not None


def test_all_layouts_have_title():
    engine = LayoutEngine()
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        assert "title" in layout.regions, f"Missing title for {family}"


def test_regions_proportional():
    engine = LayoutEngine()
    for family in LayoutFamily:
        plan = SlidePlan(layout_family=family, density=0.5)
        layout = engine.create_layout(plan)
        for region in layout.regions.values():
            for key, value in region.items():
                assert 0.0 <= value <= 1.0, f"{family}:{key}={value} out of bounds"