from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class SlideAction(str, Enum):

    CREATE = "create"

    UPDATE = "update"


class ContentType(str, Enum):

    DEFINITION = "definition"

    EXPLANATION = "explanation"

    LIST = "list"

    EXAMPLES = "examples"

    COMPARISON = "comparison"

    CLASSIFICATION = "classification"

    PROCESS = "process"

    SEQUENCE = "sequence"

    CAUSE_EFFECT = "cause_effect"

    ADVANTAGES_DISADVANTAGES = (
        "advantages_disadvantages"
    )

    FORMULA = "formula"

    DATA = "data"

    APPLICATION = "application"

    SUMMARY = "summary"

    MIXED = "mixed"


class VisualType(str, Enum):

    NONE = "none"

    IMAGE = "image"

    DIAGRAM = "diagram"

    FLOWCHART = "flowchart"

    COMPARISON_TABLE = (
        "comparison_table"
    )

    CHART = "chart"

    TIMELINE = "timeline"

    HIERARCHY = "hierarchy"

    EXAMPLE_GRID = "example_grid"

    FORMULA = "formula"

    CONCEPT_MAP = "concept_map"


@dataclass(slots=True)
class BulletPoint:

    text: str

    level: int = 0


@dataclass(slots=True)
class ImageAsset:

    query: str

    local_path: Optional[str] = None

    source: Optional[str] = None

    caption: Optional[str] = None


@dataclass(slots=True)
class DiagramAsset:

    title: str

    description: str

    diagram_type: str = "flowchart"

    data: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class SlideContent:

    title: str

    subtitle: Optional[str] = None

    bullets: List[BulletPoint] = field(
        default_factory=list
    )

    summary: Optional[str] = None

    notes: Optional[str] = None

    image: Optional[ImageAsset] = None

    diagram: Optional[DiagramAsset] = None

    image_query: Optional[str] = None

    keywords: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    # =========================================================
    # NEW INTELLIGENCE FIELDS
    # =========================================================

    content_type: str = (
        ContentType.EXPLANATION.value
    )

    visual_type: str = (
        VisualType.NONE.value
    )

    visual_reason: Optional[str] = None

    visual_spec: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass(slots=True)
class SlideRequest:

    action: SlideAction

    slide_number: int

    topic: str

    content: SlideContent

    timestamp: datetime = field(
        default_factory=datetime.now
    )


@dataclass(slots=True)
class SlideResult:

    success: bool

    slide_number: int

    message: str = ""

    presentation_path: Optional[str] = None 