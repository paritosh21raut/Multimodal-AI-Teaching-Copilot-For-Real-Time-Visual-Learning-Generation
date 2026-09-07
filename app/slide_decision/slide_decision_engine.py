"""
Slide Decision Engine

Decides whether presentation state should change.
Uses Development + Importance Intelligence outputs.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
from datetime import datetime
import threading

from .slide_decision_models import SlideAction, SlideTrigger, SlideDecision

from app.semantic.semantic_models import SemanticFrame
from app.development.development_tracker import DevelopmentTracker
from app.development.development_models import DevelopmentState, ConceptDevelopment
from app.importance.importance_scorer import ImportanceScorer
from app.importance.importance_models import ImportanceScore, ImportanceLevel


class SlideDecisionEngine:
    """
    Decides when to change slides based on:
    - Topic changes (from LSI)
    - Concept development (ESTABLISHED concepts deserve slides)
    - Content accumulation (enough material for a slide)
    - Importance (critical concepts need slides)
    - Time elapsed (don't stay on same slide too long)
    """
    
    def __init__(
        self,
        development_tracker: Optional[DevelopmentTracker] = None,
        importance_scorer: Optional[ImportanceScorer] = None,
    ):
        self.development_tracker = development_tracker or DevelopmentTracker()
        self.importance_scorer = importance_scorer or ImportanceScorer(
            self.development_tracker
        )
        
        # State
        self._current_topic: str = ""
        self._current_slide_concepts: List[str] = []
        self._chunks_on_current_slide: int = 0
        self._last_slide_time: datetime = datetime.now()
        
        # Thresholds
        self.max_concepts_per_slide = 5
        self.max_chunks_per_slide = 10
        self.min_established_concepts = 1
        self.min_high_importance_concepts = 2
        
        self._lock = threading.RLock()
    
    def decide(
        self,
        topic_changed: bool = False,
        current_topic: str = "",
        chunk_id: str = "",
    ) -> SlideDecision:
        """
        Decide whether presentation state should change.
        
        Args:
            topic_changed: True if LSI detected a new topic
            current_topic: Current topic name
            chunk_id: Current chunk identifier
            
        Returns:
            SlideDecision
        """
        with self._lock:
            
            # Update current topic
            if current_topic and current_topic != self._current_topic:
                self._current_topic = current_topic
                self._chunks_on_current_slide = 0
                self._current_slide_concepts = []
            
            self._chunks_on_current_slide += 1
            
            # Check triggers in priority order
            
            # 1. Topic change → NEW SLIDE
            if topic_changed and current_topic:
                return self._create_decision(
                    SlideAction.CREATE_NEW,
                    SlideTrigger.NEW_TOPIC,
                    confidence=0.95,
                    reason=f"New topic: {current_topic}",
                    topic=current_topic,
                )
            
            # 2. Get established concepts
            established = self.development_tracker.get_established_concepts()
            
            # 3. Get important concepts
            important = self.importance_scorer.get_high_importance_concepts(
                current_chunk_id=chunk_id,
            )
            
            # 4. If enough established + important concepts → NEW SLIDE
            if (
                len(established) >= self.min_established_concepts
                and len(important) >= self.min_high_importance_concepts
            ):
                return self._create_decision(
                    SlideAction.CREATE_NEW,
                    SlideTrigger.CONCEPT_ESTABLISHED,
                    confidence=0.80,
                    reason=f"{len(established)} established, {len(important)} important concepts",
                    topic=self._current_topic,
                    concepts=[c.canonical_name for c in important[:3]],
                )
            
            # 5. If accumulated enough chunks → UPDATE CURRENT
            if self._chunks_on_current_slide >= self.max_chunks_per_slide:
                return self._create_decision(
                    SlideAction.UPDATE_CURRENT,
                    SlideTrigger.ENOUGH_CONTENT,
                    confidence=0.75,
                    reason=f"Accumulated {self._chunks_on_current_slide} chunks",
                    topic=self._current_topic,
                )
            
            # 6. If important content appeared → UPDATE CURRENT
            if important:
                return self._create_decision(
                    SlideAction.UPDATE_CURRENT,
                    SlideTrigger.IMPORTANT_CONTENT,
                    confidence=0.70,
                    reason=f"Important concepts: {[c.canonical_name for c in important[:3]]}",
                    topic=self._current_topic,
                    concepts=[c.canonical_name for c in important[:3]],
                )
            
            # 7. Default: ACCUMULATE
            return self._create_decision(
                SlideAction.ACCUMULATE,
                SlideTrigger.ENOUGH_CONTENT,
                confidence=0.60,
                reason="Accumulating content",
                topic=self._current_topic,
            )
    
    def _create_decision(
        self,
        action: SlideAction,
        trigger: SlideTrigger,
        confidence: float,
        reason: str,
        topic: str = "",
        concepts: List[str] = None,
    ) -> SlideDecision:
        """Create a slide decision"""
        return SlideDecision(
            action=action,
            trigger=trigger,
            confidence=confidence,
            reason=reason,
            topic=topic,
            concepts=concepts or [],
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get decision engine statistics"""
        return {
            "current_topic": self._current_topic,
            "chunks_on_current_slide": self._chunks_on_current_slide,
            "current_slide_concepts": len(self._current_slide_concepts),
        }
    
    def reset(self):
        """Reset state"""
        with self._lock:
            self._current_topic = ""
            self._current_slide_concepts = []
            self._chunks_on_current_slide = 0
            self._last_slide_time = datetime.now()