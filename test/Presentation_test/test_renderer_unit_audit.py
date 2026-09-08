"""
Renderer Unit Conversion Audit

Verifies that ALL rendered shapes stay within slide bounds
for ALL layout families and density levels.
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from pptx import Presentation
from pptx.util import Inches

from app.presentation.models.presentation_models import (
    SlidePlan,
    LayoutPlan,
    LayoutFamily,
    ContentBlock,
    ContentBlockType,
    RepresentationType,
    RepresentationDecision,
)
from app.presentation.renderer.slide_renderer import SlideRenderer
from app.presentation.layout.layout_engine import LayoutEngine
from app.presentation.qa.slide_validator import SlideValidator
from app.presentation.design.design_system import design_system


def create_dense_plan(family):
    """Create a plan with lots of content"""
    return SlidePlan(
        focal_message="Test focal message for slide",
        content_blocks=[
            ContentBlock(block_type=ContentBlockType.KEY_CLAIM, text="Key claim one"),
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Explanation one"),
            ContentBlock(block_type=ContentBlockType.EXPLANATION, text="Explanation two"),
            ContentBlock(block_type=ContentBlockType.EXAMPLE, text="Example one"),
            ContentBlock(block_type=ContentBlockType.EXAMPLE, text="Example two"),
        ],
        representation=RepresentationDecision(
            representation_type=RepresentationType.EXPLANATION,
            confidence=0.8,
            reason="Test",
        ),
        layout_family=family,
        density=0.8,
    )


def test_all_shapes_within_bounds_all_families():
    """
    CRITICAL: Verify every rendered shape stays within slide bounds.
    
    This catches unit conversion bugs like the accent line issue.
    """
    renderer = SlideRenderer()
    engine = LayoutEngine()
    
    slide_width = design_system.slide_width
    slide_height = design_system.slide_height
    tolerance = 0.02  # Very tight tolerance - catches real bugs
    
    failures = []
    
    for family in LayoutFamily:
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[1])
        
        plan = create_dense_plan(family)
        layout = engine.create_layout(plan)
        
        renderer.render_slide(slide, plan, layout)
        
        # Check every shape
        for shape in slide.shapes:
            if shape.left is None or shape.top is None:
                continue
            
            left_inches = shape.left / 914400
            top_inches = shape.top / 914400
            width_inches = shape.width / 914400 if shape.width else 0
            height_inches = shape.height / 914400 if shape.height else 0
            
            right = left_inches + width_inches
            bottom = top_inches + height_inches
            
            if left_inches < -tolerance:
                failures.append(f"{family}: shape {shape.shape_id} left={left_inches:.2f} < 0")
            if top_inches < -tolerance:
                failures.append(f"{family}: shape {shape.shape_id} top={top_inches:.2f} < 0")
            if right > slide_width + tolerance:
                failures.append(f"{family}: shape {shape.shape_id} right={right:.2f} > {slide_width}")
            if bottom > slide_height + tolerance:
                failures.append(f"{family}: shape {shape.shape_id} bottom={bottom:.2f} > {slide_height}")
    
    if failures:
        print("\nFAILURES FOUND:")
        for f in failures:
            print(f"  ❌ {f}")
    
    assert len(failures) == 0, f"{len(failures)} shapes out of bounds"


def test_no_double_multiplication_bug():
    """
    Verify shapes aren't placed at absurd positions (> 10 inches).
    The accent line bug placed shapes at 35 inches.
    """
    renderer = SlideRenderer()
    engine = LayoutEngine()
    
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[1])
    
    plan = create_dense_plan(LayoutFamily.HERO_DEFINITION)
    layout = engine.create_layout(plan)
    
    renderer.render_slide(slide, plan, layout)
    
    max_position = 0.0
    for shape in slide.shapes:
        if shape.left is not None:
            max_position = max(max_position, shape.left / 914400)
        if shape.top is not None:
            max_position = max(max_position, shape.top / 914400)
    
    # No shape should be beyond slide dimensions
    assert max_position <= design_system.slide_width + 0.1, f"Shape at {max_position:.2f} inches"


def test_all_density_levels_render_in_bounds():
    """Verify all density levels render correctly"""
    renderer = SlideRenderer()
    engine = LayoutEngine()
    
    for density in [0.2, 0.5, 0.9]:
        for family in [LayoutFamily.HERO_DEFINITION, LayoutFamily.FULL_WIDTH_PROCESS]:
            prs = Presentation()
            slide = prs.slides.add_slide(prs.slide_layouts[1])
            
            plan = create_dense_plan(family)
            plan.density = density
            
            layout = engine.create_layout(plan)
            renderer.render_slide(slide, plan, layout)
            
            validator = SlideValidator()
            result = validator.validate_slide(slide, plan)
            
            assert result.severity != "severe", f"Severe for density={density}, family={family}: {result.issues}"