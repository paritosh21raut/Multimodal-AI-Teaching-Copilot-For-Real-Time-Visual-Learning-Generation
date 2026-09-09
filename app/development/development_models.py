"""
Development Intelligence - Core Models (PHASE 2 - Backward Compatible)

Adds structured coverage dimensions while preserving legacy classes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any


class DevelopmentState(str, Enum):
    """Development lifecycle of a concept"""
    MENTIONED = "mentioned"
    DEVELOPING = "developing"
    ESTABLISHED = "established"
    FULLY_EXPLAINED = "fully_explained"


class DevelopmentEventType(str, Enum):
    """Types of development events (LEGACY - kept for backward compatibility)"""
    CONCEPT_MENTIONED = "concept_mentioned"
    CONCEPT_EXPLAINED = "concept_explained"
    DEFINITION_ADDED = "definition_added"
    EXAMPLE_ADDED = "example_added"
    RELATION_ADDED = "relation_added"
    PROPOSITION_ADDED = "proposition_added"
    CONCEPT_REVISITED = "concept_revisited"
    STATE_CHANGED = "state_changed"


class CoverageDimension(str, Enum):
    """Structured coverage dimensions for concept development"""
    INTRODUCED = "introduced"
    DEFINED = "defined"
    EXPLAINED = "explained"
    PURPOSE_EXPLAINED = "purpose_explained"
    STRUCTURE_EXPLAINED = "structure_explained"
    MECHANISM_EXPLAINED = "mechanism_explained"
    PROCESS_EXPLAINED = "process_explained"
    EXAMPLE_GIVEN = "example_given"
    COUNTEREXAMPLE_GIVEN = "counterexample_given"
    COMPARISON_GIVEN = "comparison_given"
    CONDITION_GIVEN = "condition_given"
    QUANTITY_GIVEN = "quantity_given"
    FORMULA_GIVEN = "formula_given"
    DERIVATION_GIVEN = "derivation_given"
    APPLICATION_GIVEN = "application_given"
    LIMITATION_GIVEN = "limitation_given"
    SUMMARY_GIVEN = "summary_given"


@dataclass
class DevelopmentEvent:
    """Event representing a development update (LEGACY - kept for compatibility)"""
    event_id: str
    event_type: DevelopmentEventType
    concept_id: str
    chunk_id: str
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConceptDevelopment:
    """Development state for a single concept with coverage dimensions"""
    concept_id: str
    canonical_name: str
    state: DevelopmentState = DevelopmentState.MENTIONED
    
    # Coverage dimensions (structured)
    coverage: Dict[CoverageDimension, bool] = field(default_factory=dict)
    
    # Legacy scalar (compatibility)
    mention_count: int = 0
    proposition_count: int = 0
    definition_count: int = 0
    example_count: int = 0
    relation_count: int = 0
    revisit_count: int = 0
    
    distinct_chunks: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    
    first_seen: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    
    development_score: float = 0.0
    confidence: float = 0.0
    
    def mark_covered(self, dimension: CoverageDimension, evidence_id: str = ""):
        """Mark a coverage dimension as covered"""
        self.coverage[dimension] = True
        if evidence_id and evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)
    
    def is_covered(self, dimension: CoverageDimension) -> bool:
        """Check if a coverage dimension is covered"""
        return self.coverage.get(dimension, False)
    
    def coverage_percentage(self) -> float:
        """Percentage of dimensions covered"""
        total = len(CoverageDimension)
        covered = sum(1 for d in CoverageDimension if self.coverage.get(d, False))
        return covered / total if total > 0 else 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "state": self.state.value,
            "coverage": {d.value: self.coverage.get(d, False) for d in CoverageDimension},
            "mention_count": self.mention_count,
            "proposition_count": self.proposition_count,
            "definition_count": self.definition_count,
            "example_count": self.example_count,
            "relation_count": self.relation_count,
            "revisit_count": self.revisit_count,
            "distinct_chunks": len(self.distinct_chunks),
            "evidence_ids": self.evidence_ids,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "development_score": self.development_score,
            "coverage_percentage": self.coverage_percentage(),
            "confidence": self.confidence,
        }