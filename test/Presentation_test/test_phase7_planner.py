"""
Phase 7: Presentation Planner - Production Readiness Tests (UPDATED CONTRACT)
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.planner.presentation_planner import PresentationPlanner
from app.presentation.models.presentation_models import (
    SlidePlan, SlideAction, SelectedInformation, RepresentationDecision,
    RepresentationType, LayoutFamily, ContentBlockType, SemanticEvidence,
)


def create_planner_inputs():
    decision = SlideAction.CREATE_NEW
    
    info = SelectedInformation()
    info.focal_claim = SemanticEvidence(
        subject="TCP", predicate="PROVIDES", object="reliable delivery",
        evidence_id="e1", confidence=0.9,
    )
    info.semantic_units = [
        SemanticEvidence(subject="TCP", predicate="PROVIDES", object="reliability", evidence_id="e2"),
    ]
    info.definitions = ["TCP"]
    info.evidence_ids = ["e1", "e2"]
    
    rep = RepresentationDecision(
        representation_type=RepresentationType.DEFINITION,
        confidence=0.85,
        reason="Test",
    )
    return decision, info, rep


def test_planner_creates_plan():
    planner = PresentationPlanner()
    decision, info, rep = create_planner_inputs()
    plan = planner.plan(slide_decision=decision, selected_info=info, representation=rep, topic_id="tcp")
    assert plan is not None
    assert plan.focal_message != ""
    assert plan.topic_id == "tcp"


def test_planner_maps_layout():
    planner = PresentationPlanner()
    decision, info, rep = create_planner_inputs()
    plan = planner.plan(decision, info, rep, topic_id="tcp")
    assert plan.layout_family == LayoutFamily.HERO_DEFINITION


def test_planner_builds_content_blocks():
    planner = PresentationPlanner()
    decision, info, rep = create_planner_inputs()
    plan = planner.plan(decision, info, rep, topic_id="tcp")
    assert len(plan.content_blocks) >= 1


def test_planner_preserves_evidence():
    planner = PresentationPlanner()
    decision, info, rep = create_planner_inputs()
    plan = planner.plan(decision, info, rep, topic_id="tcp")
    assert "e1" in plan.evidence_ids


def test_planner_calculates_density():
    planner = PresentationPlanner()
    decision, info, rep = create_planner_inputs()
    plan = planner.plan(decision, info, rep, topic_id="tcp")
    assert 0.0 <= plan.density <= 1.0


def test_planner_handles_empty():
    planner = PresentationPlanner()
    info = SelectedInformation()
    plan = planner.plan(
        slide_decision=SlideAction.NO_CHANGE,
        selected_info=info,
        representation=None,
        topic_id="",
    )
    assert plan is not None


def test_planner_generic_domains():
    planner = PresentationPlanner()
    domains = {
        "networking": ("TCP", "PROVIDES", "reliability"),
        "biology": ("Photosynthesis", "PRODUCES", "glucose"),
        "physics": ("Force", "CAUSES", "acceleration"),
    }
    for domain, (subject, pred, obj) in domains.items():
        info = SelectedInformation()
        info.focal_claim = SemanticEvidence(subject=subject, predicate=pred, object=obj)
        info.semantic_units = [SemanticEvidence(subject=subject, predicate=pred, object=obj)]
        rep = RepresentationDecision(representation_type=RepresentationType.EXPLANATION, confidence=0.8, reason="Test")
        plan = planner.plan(SlideAction.CREATE_NEW, info, rep, topic_id=domain)
        assert plan.focal_message != "", f"Failed for {domain}"