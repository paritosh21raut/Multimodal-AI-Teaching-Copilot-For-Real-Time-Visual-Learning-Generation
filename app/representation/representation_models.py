"""
Representation Engine - Core Models

Decides how to visually represent educational content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class VisualRepresentation(str, Enum):
    """Visual representation types"""
    NONE = "none"                    # Text only
    IMAGE = "image"                  # External image
    DIAGRAM = "diagram"              # Architecture/component diagram
    FLOWCHART = "flowchart"          # Process/step flowchart
    COMPARISON_TABLE = "comparison_table"  # Side-by-side comparison
    CHART = "chart"                  # Numeric chart
    TIMELINE = "timeline"            # Chronological sequence
    HIERARCHY = "hierarchy"          # Tree structure
    EXAMPLE_GRID = "example_grid"    # Grid of examples
    FORMULA = "formula"              # Mathematical formula
    CONCEPT_MAP = "concept_map"      # Related concepts network


class ContentType(str, Enum):
    """Content types for representation"""
    DEFINITION = "definition"
    EXPLANATION = "explanation"
    COMPARISON = "comparison"
    PROCESS = "process"
    SEQUENCE = "sequence"
    CLASSIFICATION = "classification"
    CAUSE_EFFECT = "cause_effect"
    EXAMPLES = "examples"
    FORMULA = "formula"
    DATA = "data"
    RELATIONSHIPS = "relationships"
    SUMMARY = "summary"
    MIXED = "mixed"


@dataclass
class RepresentationDecision:
    """Decision about visual representation"""
    visual_type: VisualRepresentation
    content_type: ContentType
    confidence: float
    reason: str
    visual_spec: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "visual_type": self.visual_type.value,
            "content_type": self.content_type.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "visual_spec": self.visual_spec,
            "timestamp": self.timestamp.isoformat(),
        }