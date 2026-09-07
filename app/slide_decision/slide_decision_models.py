"""
Slide Decision Engine - Core Models

Decides when presentation state should change based on
semantic + development + importance intelligence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class SlideAction(str, Enum):
    """Actions for slide decision"""
    NO_ACTION = "no_action"           # Nothing to do
    ACCUMULATE = "accumulate"         # Add to current content
    UPDATE_CURRENT = "update_current"  # Update current slide
    CREATE_NEW = "create_new"         # Create new slide
    CREATE_CONTINUATION = "create_continuation"  # New slide, same topic
    FINALIZE_CURRENT = "finalize_current"  # Close current slide


class SlideTrigger(str, Enum):
    """What triggered the slide action"""
    NEW_TOPIC = "new_topic"              # Topic changed
    CONCEPT_ESTABLISHED = "concept_established"  # Concept fully developed
    ENOUGH_CONTENT = "enough_content"    # Accumulated enough material
    IMPORTANT_CONTENT = "important_content"  # Critical content appeared
    TIME_ELAPSED = "time_elapsed"        # Too long on same slide


@dataclass
class SlideDecision:
    """Decision about slide state change"""
    action: SlideAction
    trigger: SlideTrigger
    confidence: float
    reason: str
    topic: str = ""
    concepts: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "action": self.action.value,
            "trigger": self.trigger.value,
            "confidence": self.confidence,
            "reason": self.reason,
            "topic": self.topic,
            "concepts": self.concepts,
            "timestamp": self.timestamp.isoformat(),
        }