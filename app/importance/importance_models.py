"""
Importance Intelligence - Core Models (PHASE 3)

Adds structured importance factors while preserving legacy scalar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class ImportanceLevel(str, Enum):
    """Importance levels"""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    CRITICAL = "critical"


class ImportanceFactor(str, Enum):
    """Structured importance factors"""
    TEACHER_EMPHASIS = "teacher_emphasis"
    DEFINITION = "definition"
    PREREQUISITE_ROLE = "prerequisite_role"
    DEPENDENCY_CENTRALITY = "dependency_centrality"
    REPETITION = "repetition"
    RECAP = "recap"
    CONTRAST = "contrast"
    MECHANISM = "mechanism"
    FORMULA = "formula"
    CAUSAL_ROLE = "causal_role"
    TOPIC_CENTRALITY = "topic_centrality"
    DOWNSTREAM_DEPENDENCY = "downstream_dependency"
    CURRENT_INSTRUCTIONAL_ACT = "current_instructional_act"
    LEARNER_USEFULNESS = "learner_usefulness"


@dataclass
class ImportanceScore:
    """Importance score with structured factors"""
    concept_id: str
    canonical_name: str
    importance: float
    level: ImportanceLevel
    confidence: float
    factors: Dict[ImportanceFactor, float] = field(default_factory=dict)
    rank: int = 0
    
    # Legacy compatibility
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "importance": self.importance,
            "level": self.level.value,
            "confidence": self.confidence,
            "factors": {f.value: v for f, v in self.factors.items()},
            "rank": self.rank,
        }