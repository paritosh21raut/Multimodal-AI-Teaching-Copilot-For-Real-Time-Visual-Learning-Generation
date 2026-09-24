from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SlideDecisionAction(str, Enum):
    NEW_SLIDE = "NEW_SLIDE"
    UPDATE_CURRENT_SLIDE = "UPDATE_CURRENT_SLIDE"
    KEEP_CURRENT_SLIDE = "KEEP_CURRENT_SLIDE"


@dataclass
class SlideDecisionResult:
    """
    Phase 6 output for one chunk.

    `confidence_hint` is an internal heuristic indicator, NOT a calibrated
    probability. It is provided for logging/ordering only.
    """

    decision: str
    reason: str
    confidence_hint: float = 0.0

    current_slide_id: Optional[int] = None
    current_slide_topic: Optional[str] = None
    target_topic: Optional[str] = None

    lsi_relation: Optional[str] = None
    lsi_is_new_topic: bool = False
    lsi_is_new_subtopic: bool = False
    lsi_similarity: Optional[float] = None

    concept_label: Optional[str] = None
    concept_first_seen: Optional[bool] = None
    concept_prior_assertions_count: Optional[int] = None

    centrality: Optional[str] = None
    developmental_roles: List[str] = field(default_factory=list)
    explicit_emphasis: Optional[str] = None

    previous_decision: Optional[str] = None

    signals: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "confidence_hint": float(self.confidence_hint),
            "current_slide_id": self.current_slide_id,
            "current_slide_topic": self.current_slide_topic,
            "target_topic": self.target_topic,
            "lsi_relation": self.lsi_relation,
            "lsi_is_new_topic": self.lsi_is_new_topic,
            "lsi_is_new_subtopic": self.lsi_is_new_subtopic,
            "lsi_similarity": self.lsi_similarity,
            "concept_label": self.concept_label,
            "concept_first_seen": self.concept_first_seen,
            "concept_prior_assertions_count": self.concept_prior_assertions_count,
            "centrality": self.centrality,
            "developmental_roles": list(self.developmental_roles),
            "explicit_emphasis": self.explicit_emphasis,
            "previous_decision": self.previous_decision,
            "signals": dict(self.signals),
        }


def is_valid_action(value: str) -> bool:
    return value in {a.value for a in SlideDecisionAction}