"""
Slide Decision Engine (Improved)

Proper saturation accumulation with interpretable decision making.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime, timedelta
import threading

from app.presentation.models.presentation_models import SlideAction, SlideDecision


class SlideDecisionEngine:
    """
    Independent slide decision subsystem.
    
    Saturation Model:
    - Each displayed semantic unit contributes to saturation
    - Each chunk contributes smaller amount
    - Novelty accelerates saturation
    - Once saturation exceeds threshold, slide is "full"
    """

    def __init__(
        self,
        min_slide_duration_seconds: float = 5.0,
        max_slide_duration_seconds: float = 120.0,
        saturation_threshold: float = 0.7,
        max_semantic_units_per_slide: int = 8,
    ):
        self.min_slide_duration = min_slide_duration_seconds
        self.max_slide_duration = max_slide_duration_seconds
        self.saturation_threshold = saturation_threshold
        self.max_semantic_units_per_slide = max_semantic_units_per_slide
        
        # State
        self._lock = threading.RLock()
        self._current_slide_topic: str = ""
        self._current_slide_started: datetime = datetime.now()
        self._chunks_on_current_slide: int = 0
        self._displayed_semantic_units: Set[str] = set()
        self._saturation_score: float = 0.0
        self._has_slide: bool = False
        
        # History
        self._recent_decisions: List[SlideDecision] = []
        self._max_history = 20
    
    def decide(
        self,
        topic_changed: bool = False,
        new_concepts: List[str] = None,
        important_concepts: List[str] = None,
        semantic_novelty: float = 0.0,
        development_changed: bool = False,
        current_topic: str = "",
        chunk_id: str = "",
    ) -> SlideDecision:
        """
        Decide slide state change.
        
        Decision Priority (highest first):
        1. First topic → CREATE_NEW
        2. Topic change (after debounce) → CREATE_NEW
        3. Saturation reached → CREATE_NEW or FINALIZE
        4. Important new content → UPDATE
        5. Development milestone → REFINE
        6. Max duration → FINALIZE
        7. Default → NO_CHANGE
        """
        with self._lock:
            new_concepts = new_concepts or []
            important_concepts = important_concepts or []
            
            # ==========================================
            # PRIORITY 1: First topic
            # ==========================================
            if not self._has_slide and current_topic:
                self._has_slide = True
                self._current_slide_topic = current_topic
                self._current_slide_started = datetime.now()
                return self._create_decision(
                    action=SlideAction.CREATE_NEW,
                    trigger="initial_topic",
                    confidence=1.0,
                    reason=f"Initial topic: {current_topic}",
                    topic_path=current_topic,
                )
            
            time_on_slide = (datetime.now() - self._current_slide_started).total_seconds()
            
            # ==========================================
            # PRIORITY 2: Topic change
            # ==========================================
            if topic_changed and current_topic and current_topic != self._current_slide_topic:
                if time_on_slide >= self.min_slide_duration:
                    self._current_slide_topic = current_topic
                    return self._create_decision(
                        action=SlideAction.CREATE_NEW,
                        trigger="topic_change",
                        confidence=0.9,
                        reason=f"Topic changed: {self._current_slide_topic} → {current_topic}",
                        topic_path=current_topic,
                    )
                else:
                    return self._create_decision(
                        action=SlideAction.WAIT,
                        trigger="debounce",
                        confidence=0.6,
                        reason=f"Topic change too soon ({time_on_slide:.1f}s < {self.min_slide_duration}s)",
                        topic_path=current_topic,
                    )
            
            # ==========================================
            # Update saturation BEFORE checking
            # ==========================================
            self._update_saturation(
                new_concepts=new_concepts,
                important_concepts=important_concepts,
                novelty=semantic_novelty,
            )
            
            # ==========================================
            # PRIORITY 3: Saturation
            # ==========================================
            if self._saturation_score >= self.saturation_threshold:
                if important_concepts:
                    return self._create_decision(
                        action=SlideAction.CREATE_NEW,
                        trigger="slide_saturated",
                        confidence=0.75,
                        reason=f"Slide full ({self._saturation_score:.2f}), new content available",
                        topic_path=current_topic,
                    )
                else:
                    return self._create_decision(
                        action=SlideAction.FINALIZE,
                        trigger="slide_saturated",
                        confidence=0.7,
                        reason=f"Slide full ({self._saturation_score:.2f}), no new content",
                        topic_path=current_topic,
                    )
            
            # ==========================================
            # PRIORITY 4: Important new content
            # ==========================================
            if important_concepts:
                new_important = [
                    c for c in important_concepts
                    if c not in self._displayed_semantic_units
                ]
                
                if new_important:
                    # Add to displayed units
                    for concept in new_important[:3]:
                        self._displayed_semantic_units.add(concept)
                    
                    return self._create_decision(
                        action=SlideAction.UPDATE,
                        trigger="important_content",
                        confidence=0.7,
                        reason=f"New important concepts: {new_important[:3]}",
                        topic_path=current_topic,
                    )
            
            # ==========================================
            # PRIORITY 5: Development milestone
            # ==========================================
            if development_changed and semantic_novelty > 0.2:
                return self._create_decision(
                    action=SlideAction.REFINE,
                    trigger="development_milestone",
                    confidence=0.6,
                    reason="Concept development milestone reached",
                    topic_path=current_topic,
                )
            
            # ==========================================
            # PRIORITY 6: Max duration
            # ==========================================
            if time_on_slide >= self.max_slide_duration:
                return self._create_decision(
                    action=SlideAction.FINALIZE,
                    trigger="max_duration",
                    confidence=0.6,
                    reason=f"Maximum slide duration ({time_on_slide:.0f}s)",
                    topic_path=current_topic,
                )
            
            # ==========================================
            # DEFAULT: Accumulating
            # ==========================================
            return self._create_decision(
                action=SlideAction.NO_CHANGE,
                trigger="accumulating",
                confidence=0.5,
                reason=f"Accumulating (saturation: {self._saturation_score:.2f})",
                topic_path=current_topic,
            )
    
    def _update_saturation(
        self,
        new_concepts: List[str],
        important_concepts: List[str],
        novelty: float,
    ) -> None:
        """
        Update saturation score.
        
        Saturation grows with:
        - Each chunk processed (small contribution)
        - Each NEW concept displayed (medium contribution)
        - Semantic novelty (accelerator)
        """
        self._chunks_on_current_slide += 1
        
        # Each chunk adds small amount
        chunk_contribution = 0.05
        
        # Each new unique concept adds more
        new_unique = set(new_concepts) - self._displayed_semantic_units
        concept_contribution = len(new_unique) * 0.08
        
        # Novelty accelerates
        novelty_contribution = novelty * 0.1
        
        # Combine
        total_addition = chunk_contribution + concept_contribution + novelty_contribution
        
        self._saturation_score = min(
            1.0,
            self._saturation_score + total_addition,
        )
        
        # Round for readability
        self._saturation_score = round(self._saturation_score, 3)
    
    def _create_decision(
        self,
        action: SlideAction,
        trigger: str,
        confidence: float,
        reason: str,
        topic_path: str = "",
    ) -> SlideDecision:
        """Create decision and update state"""
        decision = SlideDecision(
            action=action,
            trigger=trigger,
            confidence=confidence,
            reason=reason,
            topic_path=topic_path,
            saturation_score=self._saturation_score,
        )
        
        self._recent_decisions.append(decision)
        if len(self._recent_decisions) > self._max_history:
            self._recent_decisions = self._recent_decisions[-self._max_history:]
        
        # Reset on CREATE_NEW
        if action == SlideAction.CREATE_NEW:
            self._current_slide_started = datetime.now()
            self._chunks_on_current_slide = 0
            self._displayed_semantic_units = set()
            self._saturation_score = 0.0
            self._current_slide_topic = topic_path
            self._has_slide = True
        
        return decision
    
    def get_recent_decisions(self) -> List[SlideDecision]:
        with self._lock:
            return list(self._recent_decisions)
    
    def get_state(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "current_slide_topic": self._current_slide_topic,
                "chunks_on_current_slide": self._chunks_on_current_slide,
                "saturation_score": self._saturation_score,
                "displayed_semantic_units": len(self._displayed_semantic_units),
                "time_on_slide": (datetime.now() - self._current_slide_started).total_seconds(),
                "has_slide": self._has_slide,
            }
    
    def reset(self):
        with self._lock:
            self._current_slide_topic = ""
            self._current_slide_started = datetime.now()
            self._chunks_on_current_slide = 0
            self._displayed_semantic_units = set()
            self._saturation_score = 0.0
            self._recent_decisions = []
            self._has_slide = False