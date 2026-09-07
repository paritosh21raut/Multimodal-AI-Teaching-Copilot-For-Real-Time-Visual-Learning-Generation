"""
Importance Intelligence - Core Models
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class ImportanceLevel(str, Enum):
    """Importance levels"""
    LOW = "low"           # Minor mention, not critical
    MODERATE = "moderate" # Somewhat important
    HIGH = "high"         # Important concept
    CRITICAL = "critical" # Core concept, heavily developed


@dataclass
class ImportanceScore:
    """Importance score for a concept"""
    concept_id: str
    canonical_name: str
    importance: float
    level: ImportanceLevel
    confidence: float
    factors: Dict[str, float]
    rank: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "importance": self.importance,
            "level": self.level.value,
            "confidence": self.confidence,
            "factors": self.factors,
            "rank": self.rank,
        }