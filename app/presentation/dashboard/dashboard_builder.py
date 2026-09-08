"""
Dashboard Builder

Builds dashboard data from presentation intelligence state.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from .dashboard_models import DashboardState, TeacherCockpitData, StudentViewData


class DashboardBuilder:
    """
    Builds dashboard data from current system state.
    
    Keeps teacher cockpit and student view SEPARATE.
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._state = DashboardState()
    
    def update_teacher_view(
        self,
        transcript: str = "",
        topic: str = "",
        topic_path: List[str] = None,
        concepts: List[str] = None,
        instructional_act: str = "",
        propositions: List[str] = None,
        development_states: Dict[str, str] = None,
        important_concepts: List[str] = None,
        slide_action: str = "",
        slide_reason: str = "",
        representation: str = "",
        pipeline_stage: str = "",
        latency_ms: float = 0.0,
        queue_depth: int = 0,
        errors: List[str] = None,
        llm_provider: str = "",
    ):
        """Update teacher cockpit data"""
        with self._lock:
            self._state.teacher_view = TeacherCockpitData(
                authoritative_transcript=transcript or self._state.teacher_view.authoritative_transcript,
                current_utterance=transcript,
                current_topic=topic or self._state.teacher_view.current_topic,
                topic_path=topic_path or self._state.teacher_view.topic_path,
                concepts=concepts or self._state.teacher_view.concepts,
                instructional_act=instructional_act or self._state.teacher_view.instructional_act,
                propositions=propositions or self._state.teacher_view.propositions,
                development_states=development_states or self._state.teacher_view.development_states,
                important_concepts=important_concepts or self._state.teacher_view.important_concepts,
                slide_action=slide_action or self._state.teacher_view.slide_action,
                slide_reason=slide_reason or self._state.teacher_view.slide_reason,
                representation=representation or self._state.teacher_view.representation,
                pipeline_stage=pipeline_stage or self._state.teacher_view.pipeline_stage,
                latency_ms=latency_ms,
                queue_depth=queue_depth,
                errors=errors or self._state.teacher_view.errors,
                llm_provider=llm_provider or self._state.teacher_view.llm_provider,
            )
    
    def update_student_view(
        self,
        slide_title: str = "",
        bullet_points: List[str] = None,
        visual_type: str = "none",
        image_path: str = "",
        slide_number: int = 0,
        total_slides: int = 0,
    ):
        """Update student view data"""
        with self._lock:
            self._state.student_view = StudentViewData(
                slide_title=slide_title or self._state.student_view.slide_title,
                bullet_points=bullet_points or self._state.student_view.bullet_points,
                visual_type=visual_type,
                image_path=image_path or self._state.student_view.image_path,
                current_slide_number=slide_number,
                total_slides=total_slides,
            )
    
    def set_mode(self, mode: str):
        """Set dashboard mode (teacher or student)"""
        with self._lock:
            if mode in ["teacher", "student"]:
                self._state.mode = mode
    
    def get_state(self) -> DashboardState:
        """Get complete dashboard state"""
        with self._lock:
            return self._state
    
    def get_teacher_view(self) -> TeacherCockpitData:
        """Get teacher cockpit data"""
        with self._lock:
            return self._state.teacher_view
    
    def get_student_view(self) -> StudentViewData:
        """Get student view data"""
        with self._lock:
            return self._state.student_view
    
    def reset(self):
        """Reset dashboard state"""
        with self._lock:
            self._state = DashboardState()


dashboard_builder = DashboardBuilder()