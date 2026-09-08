"""
Presentation Bridge

Connects Presentation Intelligence to existing LecturePipeline.
This is the final integration layer.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from app.presentation.integration import PresentationIntelligence
from app.presentation.models.presentation_models import (
    SlideAction,
    SlidePlan,
    SlideDecision,
    SelectedInformation,
    RepresentationDecision,
)
from app.presentation.dashboard.dashboard_builder import DashboardBuilder


class PresentationBridge:
    """
    Bridge between LecturePipeline and Presentation Intelligence.
    
    This is what LecturePipeline will call instead of the old
    slide logic (is_new_topic → create_slide).
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self.presentation_intelligence = PresentationIntelligence()
        self.dashboard_builder = DashboardBuilder()
        
        # Track current slide state
        self._current_slide_number = 0
        self._total_slides = 0
    
    def process_transcript(
        self,
        frame: Any,
        topic_changed: bool,
        current_topic: str,
        important_concepts: List[str],
        authoritative_transcript: str = "",
        chunk_id: str = "",
    ) -> Dict[str, Any]:
        """
        Process transcript through complete presentation pipeline.
        
        Args:
            frame: SemanticFrame from Semantic Intelligence
            topic_changed: LSI detected topic change
            current_topic: Current topic name
            important_concepts: Importance Intelligence output
            authoritative_transcript: Full transcript for dashboard
            chunk_id: Current chunk identifier
            
        Returns:
            Dict with slide plan, render instructions, dashboard data
        """
        with self._lock:
            # ==========================================
            # Process through Presentation Intelligence
            # ==========================================
            result = self.presentation_intelligence.process(
                frame=frame,
                topic_changed=topic_changed,
                current_topic=current_topic,
                important_concepts=important_concepts,
                chunk_id=chunk_id,
            )
            
            if result is None:
                return self._no_action_result()
            
            # Update slide number if slide created
            if result.get("slide_created"):
                self._current_slide_number += 1
                self._total_slides += 1
            
            # ==========================================
            # Update Dashboard
            # ==========================================
            self._update_dashboard(result, frame, current_topic, important_concepts)
            
            return result
    
    def _no_action_result(self) -> Dict[str, Any]:
        """Return result when no action needed"""
        return {
            "action": "no_change",
            "reason": "No content to process",
            "slide_created": False,
            "slide_number": self._current_slide_number,
        }
    
    def _update_dashboard(
        self,
        result: Dict[str, Any],
        frame: Any,
        current_topic: str,
        important_concepts: List[str],
    ):
        """Update dashboard with current state"""
        
        # Teacher view
        self.dashboard_builder.update_teacher_view(
            topic=current_topic,
            concepts=[c.canonical_name for c in getattr(frame, 'concepts', [])],
            instructional_act=(
                frame.instructional_acts[0].act_type.value
                if hasattr(frame, 'instructional_acts') and frame.instructional_acts
                else ""
            ),
            propositions=[
                f"{p.subject.canonical_name} {p.predicate.value} {p.object.canonical_name}"
                for p in getattr(frame, 'propositions', [])
                if p.subject and p.object and p.predicate
            ],
            important_concepts=important_concepts,
            slide_action=result.get("action", ""),
            slide_reason=result.get("reason", ""),
            representation=(
                result.get("plan").representation.representation_type.value
                if result.get("plan") and result["plan"].representation
                else ""
            ),
        )
        
        # Student view (only if slide exists)
        if result.get("plan"):
            plan = result["plan"]
            self.dashboard_builder.update_student_view(
                slide_title=plan.focal_message,
                bullet_points=[
                    block.text for block in plan.content_blocks
                    if block.text and block.block_type.value != "visual"
                ],
                visual_type=(
                    plan.representation.representation_type.value
                    if plan.representation else "none"
                ),
                slide_number=self._current_slide_number,
                total_slides=self._total_slides,
            )
    
    def get_dashboard_state(self):
        """Get complete dashboard state"""
        return self.dashboard_builder.get_state()
    
    def get_state(self) -> Dict[str, Any]:
        """Get bridge state"""
        return {
            "presentation": self.presentation_intelligence.get_state(),
            "current_slide": self._current_slide_number,
            "total_slides": self._total_slides,
            "dashboard": self.dashboard_builder.get_state().mode,
        }
    
    def reset(self):
        """Reset bridge state"""
        with self._lock:
            self.presentation_intelligence.reset()
            self.dashboard_builder.reset()
            self._current_slide_number = 0
            self._total_slides = 0


# Singleton
presentation_bridge = PresentationBridge()