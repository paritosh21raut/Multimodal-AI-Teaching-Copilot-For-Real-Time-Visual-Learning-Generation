"""
Presentation Planner

Composes complete SlidePlan from:
- SlideDecision (what action)
- SelectedInformation (what content)
- RepresentationDecision (what visual form)

Produces a complete plan that the Layout Engine and Renderer consume.
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
    SlideDecision,
    RepresentationType,
)


class PresentationPlanner:
    """
    Composes slide plans from intelligence decisions.
    
    Maps:
    - SlideAction → SlidePlan.lifecycle_action
    - SelectedInformation → ContentBlocks
    - RepresentationDecision → LayoutFamily
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        self._slide_counter = 0
    
    def plan(
        self,
        slide_decision: SlideDecision,
        selected_info: SelectedInformation,
        representation: Optional[RepresentationDecision] = None,
        topic_id: str = "",
    ) -> SlidePlan:
        """
        Create a complete slide plan.
        
        Args:
            slide_decision: Decision about slide action
            selected_info: Selected information for display
            representation: Visual representation decision
            topic_id: Current topic identifier
            
        Returns:
            SlidePlan
        """
        with self._lock:
            self._slide_counter += 1
            
            plan = SlidePlan(
                slide_id=f"slide_{self._slide_counter}",
                topic_id=topic_id,
                purpose=self._determine_purpose(slide_decision),
                pedagogical_goal=self._determine_goal(representation),
                focal_message=selected_info.focal_claim,
                representation=representation,
                confidence=min(
                    slide_decision.confidence,
                    representation.confidence if representation else 0.5,
                ),
                lifecycle_action=slide_decision.action,
                evidence_ids=selected_info.evidence_ids,
                density=self._determine_density(selected_info),
            )
            
            # Build content blocks
            plan.content_blocks = self._build_content_blocks(
                selected_info,
                representation,
            )
            
            # Determine layout family
            plan.layout_family = self._determine_layout(representation)
            
            # Set emphasis
            plan.emphasis = self._determine_emphasis(selected_info)
            
            return plan
    
    def _determine_purpose(self, decision: SlideDecision) -> str:
        """Determine slide purpose from action"""
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
        return purposes.get(decision.action, "General content")
    
    def _determine_goal(
        self,
        representation: Optional[RepresentationDecision],
    ) -> str:
        """Determine pedagogical goal from representation"""
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
            RepresentationType.NUMBER_STATISTIC: "Highlight key value",
            RepresentationType.FORMULA: "Present formula",
            RepresentationType.EXPLANATION: "Explain concept",
            RepresentationType.KEY_CONCEPT: "Emphasize key concept",
        }
        return goals.get(representation.representation_type, "Explain concept")
    
    def _build_content_blocks(
        self,
        selected_info: SelectedInformation,
        representation: Optional[RepresentationDecision],
    ) -> List[ContentBlock]:
        """Build content blocks from selected information"""
        blocks = []
        
        # Focal claim block
        if selected_info.focal_claim:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.KEY_CLAIM,
                text=selected_info.focal_claim,
                priority=1.0,
                visual_role="primary",
                placement_role="center",
                max_space=0.4,
            ))
        
        # Definition blocks
        for definition in selected_info.definitions:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.DEFINITION,
                text=definition,
                priority=0.8,
                visual_role="supporting",
                placement_role="body",
                max_space=0.3,
            ))
        
        # Semantic unit blocks
        for unit in selected_info.semantic_units:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.EXPLANATION,
                text=unit,
                priority=0.6,
                visual_role="supporting",
                placement_role="body",
                max_space=0.25,
                optional=True,
            ))
        
        # Example blocks
        for example in selected_info.examples:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.EXAMPLE,
                text=example,
                priority=0.5,
                visual_role="supporting",
                placement_role="body",
                max_space=0.2,
                optional=True,
            ))
        
        # Number blocks
        for number in selected_info.numbers:
            blocks.append(ContentBlock(
                block_type=ContentBlockType.NUMBER,
                text=str(number.get("value", "")),
                priority=0.7,
                visual_role="highlight",
                placement_role="center",
                max_space=0.3,
            ))
        
        # Sort by priority (highest first)
        blocks.sort(key=lambda b: b.priority, reverse=True)
        
        return blocks
    
    def _determine_layout(
        self,
        representation: Optional[RepresentationDecision],
    ) -> LayoutFamily:
        """Map representation to layout family"""
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
            RepresentationType.NUMBER_STATISTIC: LayoutFamily.BIG_NUMBER,
            RepresentationType.FORMULA: LayoutFamily.CENTERED_FORMULA,
            RepresentationType.EXPLANATION: LayoutFamily.TEXT_LEFT_VISUAL_RIGHT,
            RepresentationType.SYSTEM_DIAGRAM: LayoutFamily.SYSTEM_ARCHITECTURE,
            RepresentationType.ARCHITECTURE_DIAGRAM: LayoutFamily.SYSTEM_ARCHITECTURE,
            RepresentationType.CONCEPT_MAP: LayoutFamily.CONCEPT_MAP_FULL,
        }
        
        return mapping.get(
            representation.representation_type,
            LayoutFamily.TEXT_LEFT_VISUAL_RIGHT,
        )
    
    def _determine_density(self, selected_info: SelectedInformation) -> float:
        """Determine slide density from content amount"""
        total_items = (
            len(selected_info.semantic_units) +
            len(selected_info.definitions) +
            len(selected_info.examples) +
            len(selected_info.numbers)
        )
        
        # Map item count to density (0-1)
        if total_items <= 2:
            return 0.3  # Sparse
        elif total_items <= 4:
            return 0.5  # Medium
        elif total_items <= 6:
            return 0.7  # Dense
        else:
            return 0.9  # Very dense
    
    def _determine_emphasis(self, selected_info: SelectedInformation) -> str:
        """Determine emphasis target"""
        if selected_info.focal_claim:
            return "focal_claim"
        elif selected_info.definitions:
            return "definition"
        elif selected_info.numbers:
            return "number"
        return "none"