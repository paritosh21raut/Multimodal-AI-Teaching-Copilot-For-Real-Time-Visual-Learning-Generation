"""
Importance Scorer

Scores importance of concepts and propositions based on
development, instructional emphasis, and structural position.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from .semantic_models import (
    Concept,
    Proposition,
    ConceptRef,
    GroundingStatus,
    PropositionLifecycle
)
from .development_tracker import DevelopmentTracker


@dataclass
class ImportanceScore:
    """Importance score for a concept or proposition"""
    entity_id: str
    importance: float
    confidence: float
    factors: Dict[str, float]
    rank: int


class ImportanceScorer:
    """Scores importance of semantic content"""
    
    def __init__(self, development_tracker: Optional[DevelopmentTracker] = None):
        self.development_tracker = development_tracker or DevelopmentTracker()
        
        # Importance weights
        self.weights = {
            "development": 0.35,
            "definition_present": 0.25,
            "example_present": 0.15,
            "proposition_count": 0.15,
            "centrality": 0.10
        }
    
    def score_concept(
        self,
        concept: Concept,
        propositions: List[Proposition] = None
    ) -> ImportanceScore:
        """Score importance of a concept"""
        factors = {}
        
        # Development factor
        dev_score = self.development_tracker.get_development_score(concept.concept_id)
        if dev_score:
            factors["development"] = min(1.0, dev_score.total_score / 2.0)
        else:
            factors["development"] = 0.0
        
        # Definition present
        has_definition = any(
            p.subject and p.subject.concept_id == concept.concept_id and
            p.predicate and p.predicate.value == "DEFINED_AS"
            for p in (propositions or [])
        )
        factors["definition_present"] = 1.0 if has_definition else 0.0
        
        # Example present
        has_example = any(
            p.subject and p.subject.concept_id == concept.concept_id and
            p.modality == "example"
            for p in (propositions or [])
        )
        factors["example_present"] = 1.0 if has_example else 0.0
        
        # Proposition count
        prop_count = sum(
            1 for p in (propositions or [])
            if (p.subject and p.subject.concept_id == concept.concept_id) or
               (p.object and p.object.concept_id == concept.concept_id)
        )
        factors["proposition_count"] = min(1.0, prop_count / 5.0)
        
        # Centrality (based on mention count)
        factors["centrality"] = min(1.0, concept.mention_count / 5.0)
        
        # Calculate weighted importance
        importance = sum(
            factors.get(factor, 0.0) * weight
            for factor, weight in self.weights.items()
        )
        
        return ImportanceScore(
            entity_id=concept.concept_id,
            importance=min(1.0, importance),
            confidence=concept.confidence,
            factors=factors,
            rank=0  # Will be set after sorting
        )
    
    def score_proposition(
        self,
        proposition: Proposition
    ) -> ImportanceScore:
        """Score importance of a proposition"""
        factors = {}
        
        # Grounding factor
        if proposition.grounding_status == GroundingStatus.EXPLICIT:
            factors["grounding"] = 1.0
        elif proposition.grounding_status == GroundingStatus.SUPPORTED:
            factors["grounding"] = 0.7
        else:
            factors["grounding"] = 0.3
        
        # Lifecycle factor
        if proposition.lifecycle == PropositionLifecycle.ACTIVE:
            factors["lifecycle"] = 1.0
        elif proposition.lifecycle == PropositionLifecycle.QUALIFIED:
            factors["lifecycle"] = 0.7
        else:
            factors["lifecycle"] = 0.3
        
        # Confidence factor
        factors["confidence"] = proposition.confidence
        
        # Calculate importance
        importance = (
            factors["grounding"] * 0.4 +
            factors["lifecycle"] * 0.3 +
            factors["confidence"] * 0.3
        )
        
        return ImportanceScore(
            entity_id=proposition.proposition_id,
            importance=min(1.0, importance),
            confidence=proposition.confidence,
            factors=factors,
            rank=0
        )
    
    def score_all_concepts(
        self,
        concepts: List[Concept],
        propositions: List[Proposition]
    ) -> List[ImportanceScore]:
        """Score all concepts and rank them"""
        scores = [
            self.score_concept(concept, propositions)
            for concept in concepts
        ]
        
        # Sort by importance
        scores.sort(key=lambda x: x.importance, reverse=True)
        
        # Assign ranks
        for i, score in enumerate(scores):
            score.rank = i + 1
        
        return scores
    
    def get_top_concepts(
        self,
        concepts: List[Concept],
        propositions: List[Proposition],
        limit: int = 10
    ) -> List[ImportanceScore]:
        """Get top N most important concepts"""
        scores = self.score_all_concepts(concepts, propositions)
        return scores[:limit]