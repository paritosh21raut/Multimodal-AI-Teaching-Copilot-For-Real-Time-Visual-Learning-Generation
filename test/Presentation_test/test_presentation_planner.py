"""
Presentation Planner - Updated Contract Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.planner.presentation_planner import PresentationPlanner
from app.presentation.models.presentation_models import (
    SlideAction, SlidePlan, ContentBlockType, LayoutFamily,
    RepresentationType, RepresentationDecision, SelectedInformation, SemanticEvidence,
)


def create_test_selection():
    info = SelectedInformation()
    info.focal_claim = SemanticEvidence(
        subject="TCP", predicate="IS_A", object="protocol",
        evidence_id="e1", confidence=0.9,
    )
    info.semantic_units = [
        SemanticEvidence(subject="TCP", predicate="PROVIDES", object="reliability", evidence_id="e2"),
    ]
    info.definitions = ["TCP"]
    info.examples = ["three-way handshake"]
    info.evidence_ids = ["e1", "e2"]
    return info


def create_test_representation(rep_type=RepresentationType.DEFINITION):
    return RepresentationDecision(
        representation_type=rep_type,
        confidence=0.85,
        reason="Test",
    )


def create_test_slide_decision(action=SlideAction.CREATE_NEW):
    return action  # Planner now accepts SlideAction directly


def test_plan_created():
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
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(RepresentationType.DEFINITION),
    )
    assert plan.layout_family == LayoutFamily.HERO_DEFINITION


def test_layout_family_for_comparison():
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(RepresentationType.COMPARISON),
    )
    assert plan.layout_family == LayoutFamily.FULL_WIDTH_COMPARISON


def test_content_blocks_created():
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    assert len(plan.content_blocks) >= 1
    assert plan.content_blocks[0].block_type == ContentBlockType.KEY_CLAIM


def test_evidence_preserved():
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    assert "e1" in plan.evidence_ids
    assert "e2" in plan.evidence_ids


def test_density_calculated():
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=create_test_representation(),
    )
    assert 0.0 <= plan.density <= 1.0


def test_different_layouts_for_different_representations():
    planner = PresentationPlanner()
    mapping = {
        RepresentationType.DEFINITION: LayoutFamily.HERO_DEFINITION,
        RepresentationType.COMPARISON: LayoutFamily.FULL_WIDTH_COMPARISON,
        RepresentationType.CONTRAST: LayoutFamily.TWO_COLUMN_CONTRAST,
        RepresentationType.FLOWCHART: LayoutFamily.FULL_WIDTH_PROCESS,
        RepresentationType.HIERARCHY: LayoutFamily.HIERARCHY_CENTERED,
    }
    for rep_type, expected_layout in mapping.items():
        plan = planner.plan(
            slide_decision=create_test_slide_decision(),
            selected_info=create_test_selection(),
            representation=create_test_representation(rep_type),
        )
        assert plan.layout_family == expected_layout, f"Failed for {rep_type}"


def test_sparse_content_low_density():
    planner = PresentationPlanner()
    info = SelectedInformation()
    info.focal_claim = SemanticEvidence(subject="TCP", predicate="IS_A", object="protocol")
    plan = planner.plan(
        slide_decision=SlideAction.CREATE_NEW,
        selected_info=info,
        representation=create_test_representation(),
    )
    assert plan.density <= 0.4


def test_dense_content_high_density():
    planner = PresentationPlanner()
    info = SelectedInformation()
    info.focal_claim = SemanticEvidence(subject="TCP", predicate="IS_A", object="protocol")
    for i in range(6):
        info.semantic_units.append(
            SemanticEvidence(subject=f"Subject{i}", predicate="PROVIDES", object=f"Object{i}")
        )
    info.definitions = ["d1", "d2"]
    info.examples = ["e1", "e2", "e3"]
    plan = planner.plan(
        slide_decision=SlideAction.CREATE_NEW,
        selected_info=info,
        representation=create_test_representation(),
    )
    assert plan.density >= 0.5


def test_works_with_empty_representation():
    planner = PresentationPlanner()
    plan = planner.plan(
        slide_decision=create_test_slide_decision(),
        selected_info=create_test_selection(),
        representation=None,
    )
    assert plan.layout_family == LayoutFamily.TEXT_LEFT_VISUAL_RIGHT


def test_planner_generic_across_domains():
    planner = PresentationPlanner()
    domains = {
        "networking": ("TCP", "PROVIDES", "reliability"),
        "biology": ("Photosynthesis", "PRODUCES", "glucose"),
        "physics": ("Force", "CAUSES", "acceleration"),
    }
    for domain, (subj, pred, obj) in domains.items():
        info = SelectedInformation()
        info.focal_claim = SemanticEvidence(subject=subj, predicate=pred, object=obj)
        info.semantic_units = [SemanticEvidence(subject=subj, predicate=pred, object=obj)]
        plan = planner.plan(
            slide_decision=SlideAction.CREATE_NEW,
            selected_info=info,
            representation=create_test_representation(RepresentationType.EXPLANATION),
            topic_id=domain,
        )
        assert plan.topic_id == domain
        assert plan.focal_message != ""