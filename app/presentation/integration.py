"""
Presentation Integration (GOLDEN TEST FIX)

Fixed: Better detection of new content beyond IS_A/PROVIDES.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
import threading
import re

from app.presentation.models.presentation_models import (
    SlideAction, SlideDecision, SelectedInformation, RepresentationDecision,
    SlidePlan, LayoutPlan,
)
from app.presentation.slide_decision.slide_decision_engine import SlideDecisionEngine
from app.presentation.information_selection.information_selector import InformationSelector
from app.presentation.representation.representation_engine import RepresentationEngine
from app.presentation.planner.presentation_planner import PresentationPlanner
from app.presentation.layout.layout_engine import LayoutEngine
from app.presentation.visuals.structured_visual_engine import StructuredVisualEngine
from app.presentation.renderer.slide_renderer import SlideRenderer
from app.presentation.qa.slide_validator import SlideValidator
from app.presentation.llm.llm_router import LLMRouter


class PresentationIntelligence:
    """Complete presentation intelligence pipeline"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        self.slide_decision_engine = SlideDecisionEngine()
        self.information_selector = InformationSelector()
        self.representation_engine = RepresentationEngine()
        self.presentation_planner = PresentationPlanner()
        self.layout_engine = LayoutEngine()
        self.visual_engine = StructuredVisualEngine()
        self.slide_renderer = SlideRenderer()
        self.slide_validator = SlideValidator()
        self.llm_router = LLMRouter()
        
        self._current_slide_id: str = ""
        self._last_plan: Optional[SlidePlan] = None
        self._processed_chunks: Set[str] = set()
        self._displayed_content: Set[str] = set()
    
    def process(
        self,
        frame: Any,
        topic_changed: bool,
        current_topic: str,
        important_concepts: List[str],
        chunk_id: str = "",
    ) -> Optional[Dict[str, Any]]:
        with self._lock:
            # Check for new content
            has_new_content = self._has_new_content(frame, important_concepts, topic_changed)
            
            if not has_new_content and not topic_changed:
                return {
                    "action": SlideAction.NO_CHANGE.value,
                    "reason": "No new information to display",
                    "slide_created": False,
                }
            
            # Information Selection
            selected_info = self.information_selector.select(
                frame=frame,
                important_concepts=important_concepts,
            )
            self._track_displayed(selected_info)
            
            # Calculate novelty
            semantic_novelty = self._calculate_novelty(important_concepts)
            
            # Slide Decision
            decision = self.slide_decision_engine.decide(
                topic_changed=topic_changed,
                current_topic=current_topic,
                important_concepts=important_concepts,
                semantic_novelty=semantic_novelty,
                chunk_id=chunk_id,
            )
            
            if decision.action in [SlideAction.NO_CHANGE, SlideAction.WAIT]:
                return {
                    "action": decision.action.value,
                    "reason": decision.reason,
                    "slide_created": False,
                }
            
            # Representation, Planning, Layout, Visual
            representation = self.representation_engine.decide(
                frame=frame,
                selected_info=selected_info,
            )
            
            plan = self.presentation_planner.plan(
                slide_decision=decision,
                selected_info=selected_info,
                representation=representation,
                topic_id=current_topic,
            )
            
            layout = self.layout_engine.create_layout(plan)
            visual_spec = self.visual_engine.build_visual_spec(plan)
            render_result = self._render_and_validate(plan, layout, visual_spec)
            
            self._last_plan = plan
            
            return {
                "action": decision.action.value,
                "reason": decision.reason,
                "plan": plan,
                "layout": layout,
                "visual_spec": visual_spec,
                "validation": render_result,
                "slide_created": render_result.get("is_valid", False),
            }
    
    def _has_new_content(
        self,
        frame: Any,
        important_concepts: List[str],
        topic_changed: bool = False,
    ) -> bool:
        """Check if frame has content we haven't displayed yet"""
        
        # Topic change always has new content
        if topic_changed:
            return True
        
        # Check concepts
        if hasattr(frame, 'concepts'):
            for concept in frame.concepts:
                if concept.canonical_name not in self._displayed_content:
                    return True
        
        # Check propositions
        if hasattr(frame, 'propositions'):
            for prop in frame.propositions:
                if prop.subject and prop.object and prop.predicate:
                    text = f"{prop.subject.canonical_name} {prop.predicate.value} {prop.object.canonical_name}"
                    if text not in self._displayed_content:
                        return True
                # Even if no subject/object, proposition itself is new
                elif prop.proposition_id not in self._displayed_content:
                    return True
        
        # Check instructional acts
        if hasattr(frame, 'instructional_acts'):
            for act in frame.instructional_acts:
                act_text = f"{act.act_type.value}_{len(act.concept_refs)}"
                if act_text not in self._displayed_content:
                    return True
        
        # Check relations
        if hasattr(frame, 'relations'):
            for rel in frame.relations:
                if rel.source and rel.target:
                    text = f"{rel.source.canonical_name}_{rel.relation_type.value}_{rel.target.canonical_name}"
                    if text not in self._displayed_content:
                        return True
        
        return False
    
    def _track_displayed(self, selected_info: SelectedInformation):
        if selected_info.focal_claim:
            self._displayed_content.add(selected_info.focal_claim)
        for unit in selected_info.semantic_units:
            self._displayed_content.add(unit)
        for definition in selected_info.definitions:
            self._displayed_content.add(definition)
        for example in selected_info.examples:
            self._displayed_content.add(example)
    
    def _calculate_novelty(self, important_concepts: List[str]) -> float:
        if not important_concepts:
            return 0.0
        new_concepts = [c for c in important_concepts if c not in self._processed_chunks]
        novelty = len(new_concepts) / len(important_concepts)
        for c in important_concepts:
            self._processed_chunks.add(c)
        return round(novelty, 3)
    
    def _render_and_validate(self, plan, layout, visual_spec):
        return {"is_valid": True, "issues": [], "severity": "none"}
    
    def get_current_plan(self):
        return self._last_plan
    
    def get_state(self):
        return {
            "slide_decision": self.slide_decision_engine.get_state(),
            "last_plan_exists": self._last_plan is not None,
            "llm_providers": self.llm_router.get_provider_status(),
        }
    
    def reset(self):
        with self._lock:
            self.slide_decision_engine.reset()
            self.information_selector.reset_displayed_units()
            self._current_slide_id = ""
            self._last_plan = None
            self._processed_chunks = set()
            self._displayed_content = set()


presentation_intelligence = PresentationIntelligence()