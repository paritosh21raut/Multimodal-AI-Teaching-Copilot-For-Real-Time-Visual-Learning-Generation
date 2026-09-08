"""
Dashboard - Comprehensive Tests
"""

from __future__ import annotations

import sys
import os
import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from app.presentation.dashboard.dashboard_models import (
    DashboardState,
    TeacherCockpitData,
    StudentViewData,
)
from app.presentation.dashboard.dashboard_builder import DashboardBuilder


# EASY TESTS

def test_dashboard_initializes():
    """Easy: Dashboard initializes"""
    builder = DashboardBuilder()
    assert builder is not None


def test_teacher_and_student_separate():
    """Easy: Teacher and student views are separate"""
    builder = DashboardBuilder()
    
    builder.update_teacher_view(topic="TCP")
    builder.update_student_view(slide_title="TCP Slide")
    
    teacher = builder.get_teacher_view()
    student = builder.get_student_view()
    
    assert teacher is not None
    assert student is not None
    # Different objects
    assert teacher != student


def test_mode_switching():
    """Easy: Mode can be switched"""
    builder = DashboardBuilder()
    
    builder.set_mode("teacher")
    assert builder.get_state().mode == "teacher"
    
    builder.set_mode("student")
    assert builder.get_state().mode == "student"


# MEDIUM TESTS

def test_teacher_view_has_all_fields():
    """Medium: Teacher view has all diagnostic fields"""
    builder = DashboardBuilder()
    
    builder.update_teacher_view(
        transcript="TCP provides reliability",
        topic="TCP",
        topic_path=["Networking", "TCP"],
        concepts=["TCP", "reliability"],
        instructional_act="DEFINITION",
        propositions=["TCP IS_A protocol"],
        development_states={"TCP": "ESTABLISHED"},
        important_concepts=["TCP"],
        slide_action="UPDATE",
        slide_reason="Important content",
        representation="definition",
        pipeline_stage="Complete",
        latency_ms=15.5,
        queue_depth=0,
        errors=[],
        llm_provider="deterministic",
    )
    
    teacher = builder.get_teacher_view()
    
    assert teacher.current_topic == "TCP"
    assert teacher.topic_path == ["Networking", "TCP"]
    assert "TCP" in teacher.concepts
    assert teacher.instructional_act == "DEFINITION"
    assert teacher.development_states["TCP"] == "ESTABLISHED"
    assert teacher.slide_action == "UPDATE"
    assert teacher.llm_provider == "deterministic"


def test_student_view_clean():
    """Medium: Student view is clean (no diagnostics)"""
    builder = DashboardBuilder()
    
    builder.update_student_view(
        slide_title="TCP Protocol",
        bullet_points=["Connection-oriented", "Reliable delivery"],
        visual_type="none",
        slide_number=1,
        total_slides=5,
    )
    
    student = builder.get_student_view()
    
    assert student.slide_title == "TCP Protocol"
    assert len(student.bullet_points) == 2
    assert student.current_slide_number == 1
    # No diagnostic fields in student view
    assert not hasattr(student, 'latency_ms')
    assert not hasattr(student, 'queue_depth')


# HARD TESTS

def test_incremental_updates_preserve_old_data():
    """Hard: Incremental updates don't overwrite existing data"""
    builder = DashboardBuilder()
    
    # Initial update
    builder.update_teacher_view(topic="TCP", concepts=["TCP"])
    
    # Partial update (only slide action)
    builder.update_teacher_view(slide_action="UPDATE")
    
    teacher = builder.get_teacher_view()
    
    # Old data preserved
    assert teacher.current_topic == "TCP"
    assert "TCP" in teacher.concepts
    assert teacher.slide_action == "UPDATE"


def test_reset_clears_all():
    """Hard: Reset clears everything"""
    builder = DashboardBuilder()
    
    builder.update_teacher_view(topic="TCP")
    builder.update_student_view(slide_title="TCP Slide")
    
    builder.reset()
    
    teacher = builder.get_teacher_view()
    student = builder.get_student_view()
    
    assert teacher.current_topic == ""
    assert student.slide_title == ""


# GENERIC TESTS

def test_works_across_domains():
    """Generic: Dashboard works for any domain"""
    builder = DashboardBuilder()
    
    domains = {
        "networking": ["TCP", "UDP"],
        "biology": ["Photosynthesis", "Mitosis"],
        "physics": ["Force", "Momentum"],
    }
    
    for domain, concepts in domains.items():
        builder.update_teacher_view(
            topic=domain,
            concepts=concepts,
            instructional_act="EXPLANATION",
        )
        
        teacher = builder.get_teacher_view()
        assert teacher.current_topic == domain
        assert len(teacher.concepts) == len(concepts)