"""
Presentation Planner (FIXED)

Fixed: Accepts SlideAction directly, not SlideDecision.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading
import uuid

from app.presentation.models.presentation_models import (
    SlideAction,
    SlidePlan,
    ContentBlock,
    ContentBlockType,
    LayoutFamily,
    RepresentationDecision,
    SelectedInformation,
    RepresentationType,  # <-- ADD THIS
)

class PresentationPlanner:
    """Composes slide plans from intelligence decisions"""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._slide_counter = 0
    
    def plan(
        self,
        slide_decision: Any,  # Accepts SlideAction or SlideDecision
        selected_info: SelectedInformation,
        representation: Optional[RepresentationDecision] = None,
        topic_id: str = "",
    ) -> SlidePlan:
        """Create a complete slide plan"""
        with self._lock:
            self._slide_counter += 1
            
            # Extract action - accept both SlideAction and SlideDecision
            action = slide_decision
            if hasattr(slide_decision, 'action'):
                action = slide_decision.action
            
            plan = SlidePlan(
                slide_id=f"slide_{self._slide_counter}",
                topic_id=topic_id,
                purpose=self._determine_purpose(action),
                pedagogical_goal=self._determine_goal(representation),
                focal_message=selected_info.focal_claim,
                representation=representation,
                confidence=(
                    representation.confidence if representation else 0.5
                ),
                lifecycle_action=action,
                evidence_ids=selected_info.evidence_ids,
                density=self._determine_density(selected_info),
            )
            
            plan.content_blocks = self._build_content_blocks(selected_info, representation)
            plan.layout_family = self._determine_layout(representation)
            plan.emphasis = self._determine_emphasis(selected_info)
            
            return plan
    
    def _determine_purpose(self, action: SlideAction) -> str:
        purposes = {
            SlideAction.CREATE_NEW: "Introduce new concept",
            SlideAction.UPDATE: "Expand current concept",
            SlideAction.REFINE: "Refine explanation",
            SlideAction.TRANSFORM: "Transform representation",
            SlideAction.FINALIZE: "Complete current concept",
            SlideAction.NO_CHANGE: "Accumulate content",
            SlideAction.WAIT: "Waiting for more information",
            SlideAction.SECTION_TRANSITION: "Section transition",
        }
        return purposes.get(action, "General content")
    
    def _determine_goal(self, representation):
        if not representation:
            return "Explain concept"
        goals = {
            RepresentationType.DEFINITION: "Define concept clearly",
            RepresentationType.COMPARISON: "Compare concepts",
            RepresentationType.CONTRAST: "Contrast concepts",
            RepresentationType.FLOWCHART: "Explain process step-by-step",
            RepresentationType.CAUSAL_CHAIN: "Show cause-effect relationship",
            RepresentationType.HIERARCHY: "Show classification structure",
            RepresentationType.EXAMPLE_GRID: "Illustrate with examples",
        }
        return goals.get(representation.representation_type, "Explain concept")
    
    def _build_content_blocks(self, selected_info, representation):
        blocks = []
        
        if selected_info.focal_claim:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.KEY_CLAIM,
                text=selected_info.focal_claim,
                priority=1.0,
                visual_role="primary",
                placement_role="center",
            ))
        
        for definition in selected_info.definitions:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.DEFINITION,
                text=definition,
                priority=0.8,
                visual_role="supporting",
            ))
        
        for unit in selected_info.semantic_units:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.EXPLANATION,
                text=unit,
                priority=0.6,
                visual_role="supporting",
                optional=True,
            ))
        
        for example in selected_info.examples:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.EXAMPLE,
                text=example,
                priority=0.5,
                visual_role="supporting",
                optional=True,
            ))
        
        blocks.sort(key=lambda b: b.priority, reverse=True)
        return blocks
    
    def _determine_layout(self, representation):
        if not representation:
            return LayoutFamily.TEXT_LEFT_VISUAL_RIGHT
        
        mapping = {
            RepresentationType.DEFINITION: LayoutFamily.HERO_DEFINITION,
            RepresentationType.KEY_CONCEPT: LayoutFamily.TITLE_PLUS_FOCAL_VISUAL,
            RepresentationType.COMPARISON: LayoutFamily.FULL_WIDTH_COMPARISON,
            RepresentationType.CONTRAST: LayoutFamily.TWO_COLUMN_CONTRAST,
            RepresentationType.FLOWCHART: LayoutFamily.FULL_WIDTH_PROCESS,
            RepresentationType.CAUSAL_CHAIN: LayoutFamily.FULL_WIDTH_PROCESS,
            RepresentationType.HIERARCHY: LayoutFamily.HIERARCHY_CENTERED,
            RepresentationType.EXAMPLE_GRID: LayoutFamily.EXAMPLE_GRID,
        }
        return mapping.get(representation.representation_type, LayoutFamily.TEXT_LEFT_VISUAL_RIGHT)
    
    def _determine_density(self, selected_info):
        total = len(selected_info.semantic_units) + len(selected_info.definitions) + len(selected_info.examples)
        if total <= 2: return 0.3
        if total <= 4: return 0.5
        if total <= 6: return 0.7
        return 0.9
    
    def _determine_emphasis(self, selected_info):
        if selected_info.focal_claim: return "focal_claim"
        if selected_info.definitions: return "definition"
        return "none"