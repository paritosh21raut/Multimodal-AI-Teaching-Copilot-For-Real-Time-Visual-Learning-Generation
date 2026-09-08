"""
Presentation Intelligence - Core Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class SlideAction(str, Enum):
    NO_CHANGE = "no_change"
    WAIT = "wait"
    UPDATE = "update"
    REFINE = "refine"
    TRANSFORM = "transform"
    CREATE_NEW = "create_new"
    FINALIZE = "finalize"
    SECTION_TRANSITION = "section_transition"


class RepresentationType(str, Enum):
    DEFINITION = "definition"
    KEY_CONCEPT = "key_concept"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    EXAMPLE_GRID = "example_grid"
    COMPARISON = "comparison"
    CONTRAST = "contrast"
    PROS_CONS = "pros_cons"
    CLASSIFICATION = "classification"
    HIERARCHY = "hierarchy"
    PROCESS = "process"
    FLOWCHART = "flowchart"
    SEQUENCE = "sequence"
    TIMELINE = "timeline"
    CYCLE = "cycle"
    CAUSE_EFFECT = "cause_effect"
    CAUSAL_CHAIN = "causal_chain"
    SYSTEM_DIAGRAM = "system_diagram"
    ARCHITECTURE_DIAGRAM = "architecture_diagram"
    COMPONENT_DIAGRAM = "component_diagram"
    CONCEPT_MAP = "concept_map"
    FORMULA = "formula"
    EQUATION_EXPLANATION = "equation_explanation"
    WORKED_EXAMPLE = "worked_example"
    DATA_CHART = "data_chart"
    NUMBER_STATISTIC = "number_statistic"
    ANALOGY = "analogy"
    INPUT_PROCESS_OUTPUT = "input_process_output"
    SUMMARY = "summary"
    HYBRID = "hybrid"
    NONE = "none"


class LayoutFamily(str, Enum):
    HERO_DEFINITION = "hero_definition"
    TITLE_PLUS_FOCAL_VISUAL = "title_plus_focal_visual"
    TEXT_LEFT_VISUAL_RIGHT = "text_left_visual_right"
    FULL_WIDTH_PROCESS = "full_width_process"
    FULL_WIDTH_TIMELINE = "full_width_timeline"
    FULL_WIDTH_COMPARISON = "full_width_comparison"
    CENTERED_FORMULA = "centered_formula"
    HIERARCHY_CENTERED = "hierarchy_centered"
    CONCEPT_MAP_FULL = "concept_map_full"
    TWO_COLUMN_CONTRAST = "two_column_contrast"
    SYSTEM_ARCHITECTURE = "system_architecture"
    DIAGRAM_WITH_SIDE_NOTES = "diagram_with_side_notes"
    EXAMPLE_GRID = "example_grid"
    BIG_NUMBER = "big_number"


class ContentBlockType(str, Enum):
    DEFINITION = "definition"
    KEY_CLAIM = "key_claim"
    EXPLANATION = "explanation"
    EXAMPLE = "example"
    COMPARISON = "comparison"
    PROCESS_STEP = "process_step"
    FORMULA = "formula"
    NUMBER = "number"
    RELATION = "relation"
    VISUAL = "visual"
    CAPTION = "caption"
    EMPHASIS = "emphasis"


@dataclass
class SlideDecision:
    action: SlideAction
    trigger: str
    confidence: float
    reason: str
    topic_path: str = ""
    saturation_score: float = 0.0
    semantic_change_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SelectedInformation:
    focal_claim: str = ""
    semantic_units: List[str] = field(default_factory=list)
    definitions: List[str] = field(default_factory=list)
    examples: List[str] = field(default_factory=list)
    relations: List[str] = field(default_factory=list)
    numbers: List[Dict[str, Any]] = field(default_factory=list)
    formula: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    priority: float = 0.0
    redundancy_score: float = 0.0


@dataclass
class RepresentationDecision:
    representation_type: RepresentationType
    confidence: float
    reason: str
    visual_need: str = ""
    supporting_visuals: List[str] = field(default_factory=list)


@dataclass
class ContentBlock:
    block_type: ContentBlockType
    text: str = ""
    semantic_ids: List[str] = field(default_factory=list)
    priority: float = 1.0
    visual_role: str = ""
    placement_role: str = ""
    max_space: float = 0.5
    optional: bool = False


@dataclass
class SlidePlan:
    slide_id: str = ""
    topic_id: str = ""
    purpose: str = ""
    pedagogical_goal: str = ""
    focal_message: str = ""
    content_blocks: List[ContentBlock] = field(default_factory=list)
    representation: Optional[RepresentationDecision] = None
    supporting_visuals: List[str] = field(default_factory=list)
    emphasis: str = ""
    density: float = 0.5
    layout_family: LayoutFamily = LayoutFamily.TEXT_LEFT_VISUAL_RIGHT
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    lifecycle_action: SlideAction = SlideAction.NO_CHANGE


@dataclass
class LayoutPlan:
    layout_family: LayoutFamily
    regions: Dict[str, Dict[str, float]] = field(default_factory=dict)
    constraints: Dict[str, Any] = field(default_factory=dict)
    typography_assignments: Dict[str, str] = field(default_factory=dict)


@dataclass
class SlideValidationResult:
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    severity: str = "none"
    confidence: float = 1.0