"""
Importance Scorer (PHASE 3 - FIXED)

Fixed: Uses CoverageDimension enum instead of string.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
import threading

from .importance_models import ImportanceScore, ImportanceLevel, ImportanceFactor

from app.development.development_models import (
    ConceptDevelopment,
    DevelopmentState,
    CoverageDimension,  # Add this import
)

from app.development.development_tracker import DevelopmentTracker


class ImportanceScorer:
    """Scores pedagogical importance with structured factors"""
    
    def __init__(
        self,
        development_tracker: Optional[DevelopmentTracker] = None,
    ):
        self.development_tracker = development_tracker or DevelopmentTracker()
        
        self.weights = {
            ImportanceFactor.TEACHER_EMPHASIS: 0.15,
            ImportanceFactor.DEFINITION: 0.15,
            ImportanceFactor.TOPIC_CENTRALITY: 0.15,
            ImportanceFactor.REPETITION: 0.10,
            ImportanceFactor.DEPENDENCY_CENTRALITY: 0.10,
            ImportanceFactor.CURRENT_INSTRUCTIONAL_ACT: 0.10,
            ImportanceFactor.CONTRAST: 0.05,
            ImportanceFactor.MECHANISM: 0.05,
            ImportanceFactor.FORMULA: 0.05,
            ImportanceFactor.RECAP: 0.05,
            ImportanceFactor.CAUSAL_ROLE: 0.05,
        }
        
        self.low_threshold = 0.15
        self.moderate_threshold = 0.35
        self.high_threshold = 0.60
    
    def score_concept(
        self,
        concept_id: str,
        current_chunk_id: str = "",
    ) -> Optional[ImportanceScore]:
        """Score importance of a concept with structured factors"""
        dev = self.development_tracker.get_development(concept_id)
        
        if dev is None:
            return None
        
        factors = {}
        
        # 1. Teacher emphasis
        factors[ImportanceFactor.TEACHER_EMPHASIS] = self._score_emphasis(dev)
        
        # 2. Definition
        factors[ImportanceFactor.DEFINITION] = min(1.0, dev.definition_count)
        
        # 3. Topic centrality
        factors[ImportanceFactor.TOPIC_CENTRALITY] = dev.development_score
        
        # 4. Repetition
        factors[ImportanceFactor.REPETITION] = min(1.0, dev.mention_count / 5)
        
        # 5. Dependency centrality
        factors[ImportanceFactor.DEPENDENCY_CENTRALITY] = min(1.0, dev.relation_count / 4)
        
        # 6. Current instructional act
        factors[ImportanceFactor.CURRENT_INSTRUCTIONAL_ACT] = self._score_recency(dev, current_chunk_id)
        
        # 7. Contrast - FIXED: use enum
        factors[ImportanceFactor.CONTRAST] = (
            1.0 if dev.is_covered(CoverageDimension.COMPARISON_GIVEN) else 0.0
        )
        
        # 8. Mechanism - FIXED: use enum
        factors[ImportanceFactor.MECHANISM] = (
            1.0 if dev.is_covered(CoverageDimension.MECHANISM_EXPLAINED) else 0.0
        )
        
        # 9. Formula - FIXED: use enum
        factors[ImportanceFactor.FORMULA] = (
            1.0 if dev.is_covered(CoverageDimension.FORMULA_GIVEN) else 0.0
        )
        
        # 10. Recap - FIXED: use enum
        factors[ImportanceFactor.RECAP] = (
            1.0 if dev.is_covered(CoverageDimension.SUMMARY_GIVEN) else 0.0
        )
        
        # 11. Causal role - FIXED: use enum
        factors[ImportanceFactor.CAUSAL_ROLE] = (
            1.0 if dev.is_covered(CoverageDimension.MECHANISM_EXPLAINED) else 0.0
        )
        
        importance = sum(
            factors.get(factor, 0.0) * weight
            for factor, weight in self.weights.items()
        )
        
        importance = round(min(1.0, max(0.0, importance)), 4)
        level = self._determine_level(importance)
        
        return ImportanceScore(
            concept_id=concept_id,
            canonical_name=dev.canonical_name,
            importance=importance,
            level=level,
            confidence=dev.confidence,
            factors=factors,
        )
    
    def score_all_concepts(self, current_chunk_id=""):
        scores = []
        for dev in self.development_tracker.get_all_developments():
            score = self.score_concept(dev.concept_id, current_chunk_id)
            if score:
                scores.append(score)
        
        scores.sort(key=lambda x: x.importance, reverse=True)
        for i, score in enumerate(scores):
            score.rank = i + 1
        
        return scores
    
    def get_top_important(self, limit=10, current_chunk_id=""):
        scores = self.score_all_concepts(current_chunk_id)
        return scores[:limit]
    
    def _score_emphasis(self, dev):
        if dev.state == DevelopmentState.FULLY_EXPLAINED:
            return 1.0
        elif dev.state == DevelopmentState.ESTABLISHED:
            return 0.7
        elif dev.state == DevelopmentState.DEVELOPING:
            return 0.4
        else:
            return 0.1
    
    def _score_recency(self, dev, current_chunk_id):
        if not current_chunk_id:
            return 0.3
        if current_chunk_id in dev.distinct_chunks:
            return 1.0
        return 0.3
    
    def _determine_level(self, importance):
        if importance >= self.high_threshold:
            return ImportanceLevel.CRITICAL
        elif importance >= self.moderate_threshold:
            return ImportanceLevel.HIGH
        elif importance >= self.low_threshold:
            return ImportanceLevel.MODERATE
        else:
            return ImportanceLevel.LOW
    
    def get_statistics(self):
        scores = self.score_all_concepts()
        
        if not scores:
            return {"total_scored": 0, "critical": 0, "high": 0, "moderate": 0, "low": 0}
        
        return {
            "total_scored": len(scores),
            "critical": sum(1 for s in scores if s.level == ImportanceLevel.CRITICAL),
            "high": sum(1 for s in scores if s.level == ImportanceLevel.HIGH),
            "moderate": sum(1 for s in scores if s.level == ImportanceLevel.MODERATE),
            "low": sum(1 for s in scores if s.level == ImportanceLevel.LOW),
            "average_importance": sum(s.importance for s in scores) / len(scores),
        }