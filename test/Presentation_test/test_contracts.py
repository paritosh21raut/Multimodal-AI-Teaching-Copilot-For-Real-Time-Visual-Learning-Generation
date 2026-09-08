"""
Presentation Contracts Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.models.presentation_models import (
    SlideAction,
    RepresentationType,
    LayoutFamily,
    ContentBlockType,
    SlideDecision,
    SelectedInformation,
    RepresentationDecision,
    ContentBlock,
    SlidePlan,
    LayoutPlan,
    SlideValidationResult,
)


def test_slide_decision_model():
    decision = SlideDecision(
        action=SlideAction.UPDATE,
        trigger="important_content",
        confidence=0.8,
        reason="Important content appeared",
    )
    assert decision.action == SlideAction.UPDATE
    assert decision.confidence > 0.7


def test_selected_information_model():
    info = SelectedInformation(
        focal_claim="TCP is connection-oriented",
        semantic_units=["TCP IS_A protocol", "TCP PROVIDES reliability"],
        evidence_ids=["e1", "e2"],
    )
    assert info.focal_claim != ""
    assert len(info.semantic_units) == 2


def test_representation_decision_model():
    decision = RepresentationDecision(
        representation_type=RepresentationType.COMPARISON,
        confidence=0.85,
        reason="Two contrasting concepts detected",
    )
    assert decision.representation_type == RepresentationType.COMPARISON


def test_slide_plan_model():
    plan = SlidePlan(
        slide_id="slide_1",
        topic_id="tcp",
        purpose="Explain TCP",
        focal_message="TCP provides reliable delivery",
        layout_family=LayoutFamily.FULL_WIDTH_COMPARISON,
    )
    assert plan.slide_id == "slide_1"
    assert plan.layout_family == LayoutFamily.FULL_WIDTH_COMPARISON


def test_layout_plan_model():
    layout = LayoutPlan(
        layout_family=LayoutFamily.HERO_DEFINITION,
        regions={"title": {"top": 0.1, "height": 0.2}},
    )
    assert layout.layout_family == LayoutFamily.HERO_DEFINITION
    assert "title" in layout.regions


def test_validation_model():
    result = SlideValidationResult(is_valid=True, issues=[], severity="none")
    assert result.is_valid
    
    result2 = SlideValidationResult(is_valid=False, issues=["Text overflow"], severity="severe")
    assert not result2.is_valid
    assert result2.severity == "severe"