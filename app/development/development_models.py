"""
Development Intelligence - Core Models

Tracks how well concepts are developed in a lecture.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class DevelopmentState(str, Enum):
    """Development lifecycle of a concept"""
    MENTIONED = "mentioned"       # Just mentioned once
    DEVELOPING = "developing"     # Being explained, some propositions
    ESTABLISHED = "established"   # Well explained, multiple propositions/examples


class DevelopmentEventType(str, Enum):
    """Types of development events"""
    CONCEPT_MENTIONED = "concept_mentioned"
    CONCEPT_EXPLAINED = "concept_explained"
    DEFINITION_ADDED = "definition_added"
    EXAMPLE_ADDED = "example_added"
    RELATION_ADDED = "relation_added"
    PROPOSITION_ADDED = "proposition_added"
    CONCEPT_REVISITED = "concept_revisited"
    STATE_CHANGED = "state_changed"


@dataclass
class DevelopmentEvent:
    """Event representing a development update"""
    event_id: str
    event_type: DevelopmentEventType
    concept_id: str
    chunk_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConceptDevelopment:
    """Development state for a single concept"""
    concept_id: str
    canonical_name: str
    state: DevelopmentState = DevelopmentState.MENTIONED
    
    mention_count: int = 0
    proposition_count: int = 0
    definition_count: int = 0
    example_count: int = 0
    relation_count: int = 0
    revisit_count: int = 0
    
    distinct_chunks: List[str] = field(default_factory=list)
    
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    development_score: float = 0.0
    confidence: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "state": self.state.value,
            "mention_count": self.mention_count,
            "proposition_count": self.proposition_count,
            "definition_count": self.definition_count,
            "example_count": self.example_count,
            "relation_count": self.relation_count,
            "revisit_count": self.revisit_count,
            "distinct_chunks": len(self.distinct_chunks),
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "development_score": self.development_score,
            "confidence": self.confidence,
        }