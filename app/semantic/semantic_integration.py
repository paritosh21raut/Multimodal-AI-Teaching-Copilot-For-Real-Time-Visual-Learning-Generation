"""
Semantic Integration (Updated with Slide Grounding)

Provides clean API for downstream systems including slide generation.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime

from .semantic_models import (
    SemanticFrame,
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    ConceptRef,
    GroundingStatus,
    PropositionLifecycle
)
from .development_tracker import DevelopmentTracker, DevelopmentScore
from .importance_scorer import ImportanceScorer, ImportanceScore
from .slide_grounder import SlideGrounder, SlideContent


@dataclass
class SemanticSummary:
    """Summary of current semantic state for downstream systems"""
    active_concepts: List[ConceptRef]
    top_developed_concepts: List[DevelopmentScore]
    top_important_concepts: List[ImportanceScore]
    active_propositions: List[Proposition]
    recent_instructional_acts: List[InstructionalAct]
    statistics: Dict[str, Any]
    timestamp: datetime


class SemanticIntegration:
    """Integration layer for downstream systems"""
    
    def __init__(
        self,
        development_tracker: Optional[DevelopmentTracker] = None,
        importance_scorer: Optional[ImportanceScorer] = None
    ):
        self.development_tracker = development_tracker or DevelopmentTracker()
        self.importance_scorer = importance_scorer or ImportanceScorer(
            self.development_tracker
        )
        self.slide_grounder = SlideGrounder()
        
        # Recent frames for context
        self._recent_frames: List[SemanticFrame] = []
        self._max_recent_frames = 10
    
    def process_frame(
        self,
        frame: SemanticFrame,
        semantic_memory=None
    ) -> None:
        """Process a semantic frame and update tracking"""
        
        # Update development tracker
        self.development_tracker.update_from_frame(
            frame.concepts,
            frame.propositions,
            frame.relations,
            frame.instructional_acts
        )
        
        # Store recent frame
        self._recent_frames.append(frame)
        if len(self._recent_frames) > self._max_recent_frames:
            self._recent_frames = self._recent_frames[-self._max_recent_frames:]
    
    def get_semantic_summary(
        self,
        semantic_memory=None,
        concepts: List[Concept] = None,
        propositions: List[Proposition] = None,
        active_concepts: List[ConceptRef] = None
    ) -> SemanticSummary:
        """Get current semantic summary for downstream systems"""
        
        all_concepts = concepts or []
        all_propositions = propositions or []
        active = active_concepts or []
        
        developed = self.development_tracker.get_most_developed(limit=10)
        
        important = self.importance_scorer.get_top_concepts(
            all_concepts,
            all_propositions,
            limit=10
        )
        
        active_props = [
            p for p in all_propositions
            if p.lifecycle == PropositionLifecycle.ACTIVE
        ]
        
        recent_acts = []
        for frame in self._recent_frames[-3:]:
            recent_acts.extend(frame.instructional_acts)
        
        stats = {
            "development": self.development_tracker.get_statistics(),
            "total_concepts": len(all_concepts),
            "total_propositions": len(all_propositions),
            "active_propositions": len(active_props),
            "recent_frames": len(self._recent_frames)
        }
        
        return SemanticSummary(
            active_concepts=active,
            top_developed_concepts=developed,
            top_important_concepts=important,
            active_propositions=active_props,
            recent_instructional_acts=recent_acts,
            statistics=stats,
            timestamp=datetime.now()
        )
    
    def prepare_slide_content(
        self,
        topic: str,
        concepts: List[Concept],
        propositions: List[Proposition],
        instructional_acts: List[InstructionalAct] = None,
        relations: List[Relation] = None
    ) -> SlideContent:
        """
        Prepare slide content from semantic data.
        
        This is the bridge between Semantic Intelligence and ContentGenerator.
        """
        return self.slide_grounder.prepare_slide_content(
            topic=topic,
            concepts=concepts,
            propositions=propositions,
            instructional_acts=instructional_acts,
            relations=relations
        )
    
    def get_concepts_for_slide_generation(
        self,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get concepts suitable for slide generation"""
        developed = self.development_tracker.get_most_developed(limit=limit)
        
        result = []
        for score in developed:
            result.append({
                "concept_id": score.concept_id,
                "development_score": score.total_score,
                "development_level": score.development_level
            })
        
        return result[:limit]
    
    def get_propositions_for_slide(
        self,
        active_propositions: List[Proposition],
        min_confidence: float = 0.6
    ) -> List[Proposition]:
        """Get propositions suitable for slide content"""
        return [
            p for p in active_propositions
            if p.confidence >= min_confidence and
               p.grounding_status in [GroundingStatus.EXPLICIT, GroundingStatus.SUPPORTED] and
               p.lifecycle == PropositionLifecycle.ACTIVE
        ]