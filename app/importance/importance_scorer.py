"""
Importance Intelligence Scorer

Scores pedagogical importance of concepts.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import threading

from .importance_models import ImportanceScore, ImportanceLevel

from app.development.development_models import (
    ConceptDevelopment,
    DevelopmentState,
)

from app.development.development_tracker import DevelopmentTracker

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    Proposition,
    Relation,
    ConceptRef,
    RelationType,
)


class ImportanceScorer:
    """
    Scores importance of concepts based on:
    - Development level (ESTABLISHED > DEVELOPING > MENTIONED)
    - Definition presence
    - Example presence
    - Proposition depth
    - Relational centrality (how connected)
    - Recency (recently discussed = more important)
    """
    
    def __init__(
        self,
        development_tracker: Optional[DevelopmentTracker] = None,
    ):
        self.development_tracker = development_tracker or DevelopmentTracker()
        
        # Importance weights
        self.weights = {
            "development": 0.30,
            "definition": 0.20,
            "example": 0.15,
            "proposition_depth": 0.15,
            "centrality": 0.10,
            "recency": 0.10,
        }
        
        # Importance thresholds
        self.low_threshold = 0.25
        self.moderate_threshold = 0.50
        self.high_threshold = 0.75
    
    def score_concept(
        self,
        concept_id: str,
        current_chunk_id: str = "",
    ) -> Optional[ImportanceScore]:
        """
        Score importance of a concept.
        
        Args:
            concept_id: The concept to score
            current_chunk_id: Current chunk for recency calculation
            
        Returns:
            ImportanceScore or None if concept not tracked
        """
        dev = self.development_tracker.get_development(concept_id)
        
        if dev is None:
            return None
        
        factors = {}
        
        # 1. Development factor
        factors["development"] = self._score_development(dev)
        
        # 2. Definition factor
        factors["definition"] = min(1.0, dev.definition_count / 2)
        
        # 3. Example factor
        factors["example"] = min(1.0, dev.example_count / 2)
        
        # 4. Proposition depth
        factors["proposition_depth"] = min(1.0, dev.proposition_count / 5)
        
        # 5. Centrality (relations to other concepts)
        factors["centrality"] = min(1.0, dev.relation_count / 4)
        
        # 6. Recency (recently mentioned = more important)
        factors["recency"] = self._score_recency(dev, current_chunk_id)
        
        # Calculate weighted importance
        importance = sum(
            factors.get(factor, 0.0) * weight
            for factor, weight in self.weights.items()
        )
        
        importance = round(min(1.0, max(0.0, importance)), 4)
        
        # Determine level
        level = self._determine_level(importance)
        
        return ImportanceScore(
            concept_id=concept_id,
            canonical_name=dev.canonical_name,
            importance=importance,
            level=level,
            confidence=dev.confidence,
            factors=factors,
        )
    
    def score_all_concepts(
        self,
        current_chunk_id: str = "",
    ) -> List[ImportanceScore]:
        """Score all tracked concepts"""
        scores = []
        
        for dev in self.development_tracker.get_all_developments():
            score = self.score_concept(
                dev.concept_id,
                current_chunk_id,
            )
            if score:
                scores.append(score)
        
        # Sort by importance (highest first)
        scores.sort(key=lambda x: x.importance, reverse=True)
        
        # Assign ranks
        for i, score in enumerate(scores):
            score.rank = i + 1
        
        return scores
    
    def get_top_important(
        self,
        limit: int = 10,
        current_chunk_id: str = "",
    ) -> List[ImportanceScore]:
        """Get most important concepts"""
        scores = self.score_all_concepts(current_chunk_id)
        return scores[:limit]
    
    def get_critical_concepts(
        self,
        current_chunk_id: str = "",
    ) -> List[ImportanceScore]:
        """Get CRITICAL importance concepts"""
        scores = self.score_all_concepts(current_chunk_id)
        return [s for s in scores if s.level == ImportanceLevel.CRITICAL]
    
    def get_high_importance_concepts(
        self,
        current_chunk_id: str = "",
    ) -> List[ImportanceScore]:
        """Get HIGH importance concepts"""
        scores = self.score_all_concepts(current_chunk_id)
        return [
            s for s in scores
            if s.level in [ImportanceLevel.HIGH, ImportanceLevel.CRITICAL]
        ]
    
    def _score_development(self, dev: ConceptDevelopment) -> float:
        """Score based on development state"""
        if dev.state == DevelopmentState.ESTABLISHED:
            return 1.0
        elif dev.state == DevelopmentState.DEVELOPING:
            return 0.6
        else:
            return 0.3
    
    def _score_recency(
        self,
        dev: ConceptDevelopment,
        current_chunk_id: str,
    ) -> float:
        """
        Score based on how recently the concept was discussed.
        
        Higher score if concept was discussed in the current chunk
        or recent chunks.
        """
        if not current_chunk_id:
            return 0.5
        
        # If in current chunk, highest recency
        if current_chunk_id in dev.distinct_chunks:
            return 1.0
        
        # If recently discussed (last 3 chunks)
        if dev.distinct_chunks:
            # Assume chunks are in order, check if in last 3
            try:
                chunk_index = dev.distinct_chunks.index(current_chunk_id)
                return 0.7
            except ValueError:
                pass
            
            # If it was seen recently (within last few chunks)
            if len(dev.distinct_chunks) >= 1:
                return 0.4
        
        return 0.2
    
    def _determine_level(self, importance: float) -> ImportanceLevel:
        """Determine importance level from score"""
        if importance >= self.high_threshold:
            return ImportanceLevel.CRITICAL
        elif importance >= self.moderate_threshold:
            return ImportanceLevel.HIGH
        elif importance >= self.low_threshold:
            return ImportanceLevel.MODERATE
        else:
            return ImportanceLevel.LOW
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get importance statistics"""
        scores = self.score_all_concepts()
        
        if not scores:
            return {
                "total_scored": 0,
                "critical": 0,
                "high": 0,
                "moderate": 0,
                "low": 0,
            }
        
        return {
            "total_scored": len(scores),
            "critical": sum(1 for s in scores if s.level == ImportanceLevel.CRITICAL),
            "high": sum(1 for s in scores if s.level == ImportanceLevel.HIGH),
            "moderate": sum(1 for s in scores if s.level == ImportanceLevel.MODERATE),
            "low": sum(1 for s in scores if s.level == ImportanceLevel.LOW),
            "average_importance": sum(s.importance for s in scores) / len(scores),
        }