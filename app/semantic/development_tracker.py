"""
Development Tracker

Tracks how developed each concept is based on semantic evidence.
More mentions, propositions, and relations indicate higher development.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime

from .semantic_models import (
    Concept,
    Proposition,
    Relation,
    ConceptRef,
    GroundingStatus
)


@dataclass
class DevelopmentScore:
    """Development score for a concept"""
    concept_id: str
    mention_count: int
    proposition_count: int
    relation_count: int
    definition_count: int
    example_count: int
    total_score: float
    development_level: str  # 'low', 'medium', 'high', 'very_high'
    last_updated: datetime


class DevelopmentTracker:
    """Tracks concept development across lecture"""
    
    def __init__(self):
        self._concept_development: Dict[str, Dict[str, Any]] = {}
        
        # Scoring weights
        self.weights = {
            "mention": 0.1,
            "proposition": 0.3,
            "relation": 0.2,
            "definition": 0.5,
            "example": 0.3,
            "repetition": 0.1
        }
        
        # Development thresholds
        self.thresholds = {
            "low": 0.3,
            "medium": 0.6,
            "high": 0.8,
            "very_high": 1.2
        }
    
    def update_from_frame(
        self,
        concepts: List[Concept],
        propositions: List[Proposition],
        relations: List[Relation],
        instructional_acts: List[Any] = None
    ) -> None:
        """Update development scores from a semantic frame"""
        
        # Update concept mentions
        for concept in concepts:
            self._update_concept(
                concept.concept_id,
                "mention",
                concept.mention_count
            )
        
        # Update propositions
        for prop in propositions:
            if prop.subject:
                self._update_concept(
                    prop.subject.concept_id,
                    "proposition",
                    1
                )
            
            if prop.object:
                self._update_concept(
                    prop.object.concept_id,
                    "proposition",
                    0.5  # Object gets half credit
                )
        
        # Update relations
        for relation in relations:
            if relation.source:
                self._update_concept(
                    relation.source.concept_id,
                    "relation",
                    1
                )
            
            if relation.target:
                self._update_concept(
                    relation.target.concept_id,
                    "relation",
                    0.5
                )
        
        # Update from instructional acts
        if instructional_acts:
            for act in instructional_acts:
                for concept_ref in act.concept_refs:
                    if act.act_type and act.act_type.value == "DEFINITION":
                        self._update_concept(
                            concept_ref.concept_id,
                            "definition",
                            1
                        )
                    elif act.act_type and act.act_type.value == "EXAMPLE":
                        self._update_concept(
                            concept_ref.concept_id,
                            "example",
                            1
                        )
    
    def _update_concept(self, concept_id: str, metric: str, value: float) -> None:
        """Update a specific metric for a concept"""
        if concept_id not in self._concept_development:
            self._concept_development[concept_id] = {
                "mention": 0,
                "proposition": 0,
                "relation": 0,
                "definition": 0,
                "example": 0,
                "total_score": 0.0,
                "last_updated": datetime.now()
            }
        
        self._concept_development[concept_id][metric] += value
        self._concept_development[concept_id]["last_updated"] = datetime.now()
        
        # Recalculate total score
        self._recalculate_score(concept_id)
    
    def _recalculate_score(self, concept_id: str) -> None:
        """Recalculate total development score"""
        dev = self._concept_development[concept_id]
        
        total = (
            dev["mention"] * self.weights["mention"] +
            dev["proposition"] * self.weights["proposition"] +
            dev["relation"] * self.weights["relation"] +
            dev["definition"] * self.weights["definition"] +
            dev["example"] * self.weights["example"]
        )
        
        dev["total_score"] = total
    
    def get_development_score(self, concept_id: str) -> Optional[DevelopmentScore]:
        """Get development score for a concept"""
        if concept_id not in self._concept_development:
            return None
        
        dev = self._concept_development[concept_id]
        
        # Determine development level
        level = "low"
        if dev["total_score"] >= self.thresholds["very_high"]:
            level = "very_high"
        elif dev["total_score"] >= self.thresholds["high"]:
            level = "high"
        elif dev["total_score"] >= self.thresholds["medium"]:
            level = "medium"
        
        return DevelopmentScore(
            concept_id=concept_id,
            mention_count=int(dev["mention"]),
            proposition_count=int(dev["proposition"]),
            relation_count=int(dev["relation"]),
            definition_count=int(dev["definition"]),
            example_count=int(dev["example"]),
            total_score=dev["total_score"],
            development_level=level,
            last_updated=dev["last_updated"]
        )
    
    def get_all_scores(self) -> Dict[str, DevelopmentScore]:
        """Get all development scores"""
        return {
            concept_id: self.get_development_score(concept_id)
            for concept_id in self._concept_development
        }
    
    def get_most_developed(self, limit: int = 10) -> List[DevelopmentScore]:
        """Get most developed concepts"""
        scores = list(self.get_all_scores().values())
        scores.sort(key=lambda x: x.total_score, reverse=True)
        return scores[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get development statistics"""
        scores = list(self.get_all_scores().values())
        
        if not scores:
            return {
                "total_concepts_tracked": 0,
                "average_score": 0.0,
                "max_score": 0.0,
                "highly_developed": 0
            }
        
        return {
            "total_concepts_tracked": len(scores),
            "average_score": sum(s.total_score for s in scores) / len(scores),
            "max_score": max(s.total_score for s in scores),
            "highly_developed": sum(
                1 for s in scores if s.development_level in ["high", "very_high"]
            )
        }