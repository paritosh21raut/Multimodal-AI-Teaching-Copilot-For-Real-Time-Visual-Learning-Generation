"""
Contradiction Detector

Identifies contradictory propositions and manages proposition lifecycles.
Never overwrites old propositions - preserves history.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass
from datetime import datetime

from .semantic_models import (
    Proposition,
    PropositionLifecycle,
    ConceptRef,
    RelationType,
    GroundingStatus
)


@dataclass
class Contradiction:
    """Represents a detected contradiction"""
    contradiction_id: str
    original_proposition_id: str
    challenge_proposition_id: str
    confidence: float
    detection_method: str
    timestamp: datetime


class ContradictionDetector:
    """Detects and manages contradictions between propositions"""
    
    def __init__(self):
        self._contradictions: Dict[str, Contradiction] = {}
        self._proposition_history: Dict[str, List[str]] = {}  # concept_id -> proposition_ids
    
    def detect_contradiction(
        self,
        new_proposition: Proposition,
        existing_propositions: List[Proposition]
    ) -> Optional[Contradiction]:
        """
        Detect if new proposition contradicts existing ones.
        
        Returns:
            Contradiction if found, None otherwise
        """
        if not new_proposition.subject:
            return None
        
        # Find propositions about same subject
        same_subject = [
            p for p in existing_propositions
            if p.subject and p.subject.concept_id == new_proposition.subject.concept_id
        ]
        
        for existing in same_subject:
            if self._are_contradictory(existing, new_proposition):
                confidence = self._contradiction_confidence(existing, new_proposition)
                
                contradiction = Contradiction(
                    contradiction_id=f"contra_{len(self._contradictions)}",
                    original_proposition_id=existing.proposition_id,
                    challenge_proposition_id=new_proposition.proposition_id,
                    confidence=confidence,
                    detection_method="predicate_conflict",
                    timestamp=datetime.now()
                )
                
                self._contradictions[contradiction.contradiction_id] = contradiction
                
                return contradiction
        
        return None
    
    def _are_contradictory(
        self,
        prop1: Proposition,
        prop2: Proposition
    ) -> bool:
        """Check if two propositions contradict each other"""
        # Same subject required
        if not prop1.subject or not prop2.subject:
            return False
        
        if prop1.subject.concept_id != prop2.subject.concept_id:
            return False
        
        # Different polarity is a contradiction
        if prop1.polarity != prop2.polarity:
            # Same predicate but different polarity
            if prop1.predicate == prop2.predicate:
                return True
        
        # Opposite predicates
        opposite_predicates = {
            RelationType.IS_A: [RelationType.CONTRASTS_WITH],
            RelationType.CONTRASTS_WITH: [RelationType.IS_A],
            RelationType.REQUIRES: [RelationType.LIMITED_BY],
            RelationType.LIMITED_BY: [RelationType.REQUIRES],
        }
        
        if prop1.predicate in opposite_predicates:
            if prop2.predicate in opposite_predicates[prop1.predicate]:
                return True
        
        # Same predicate but contradictory objects
        if prop1.predicate == prop2.predicate:
            # If objects are different and both are explicit
            if (prop1.object and prop2.object and
                prop1.object.concept_id != prop2.object.concept_id):
                
                # For IS_A, different objects might be contradictory
                if prop1.predicate == RelationType.IS_A:
                    return True
                
                # For HAS_ATTRIBUTE, different values might be contradictory
                if prop1.predicate == RelationType.HAS_ATTRIBUTE:
                    return True
        
        return False
    
    def _contradiction_confidence(
        self,
        prop1: Proposition,
        prop2: Proposition
    ) -> float:
        """Calculate confidence that two propositions contradict"""
        confidence = 0.0
        
        # Both explicit = higher confidence
        if (prop1.grounding_status == GroundingStatus.EXPLICIT and
            prop2.grounding_status == GroundingStatus.EXPLICIT):
            confidence += 0.4
        
        # Same subject = higher confidence
        if (prop1.subject and prop2.subject and
            prop1.subject.concept_id == prop2.subject.concept_id):
            confidence += 0.3
        
        # Different objects = higher confidence
        if (prop1.object and prop2.object and
            prop1.object.concept_id != prop2.object.concept_id):
            confidence += 0.3
        
        return min(1.0, confidence)
    
    def handle_contradiction(
        self,
        contradiction: Contradiction,
        propositions: Dict[str, Proposition]
    ) -> None:
        """Handle detected contradiction by updating lifecycles"""
        original_id = contradiction.original_proposition_id
        challenge_id = contradiction.challenge_proposition_id
        
        if original_id in propositions:
            propositions[original_id].lifecycle = PropositionLifecycle.CONTRADICTED
            propositions[original_id].updated_at = datetime.now()
        
        if challenge_id in propositions:
            propositions[challenge_id].lifecycle = PropositionLifecycle.CONTRADICTED
            propositions[challenge_id].updated_at = datetime.now()
    
    def handle_correction(
        self,
        old_proposition_id: str,
        new_proposition_id: str,
        propositions: Dict[str, Proposition]
    ) -> None:
        """Handle explicit correction (teacher says "actually...")"""
        if old_proposition_id in propositions:
            propositions[old_proposition_id].lifecycle = PropositionLifecycle.SUPERSEDED
            propositions[old_proposition_id].updated_at = datetime.now()
        
        if new_proposition_id in propositions:
            propositions[new_proposition_id].lifecycle = PropositionLifecycle.ACTIVE
            propositions[new_proposition_id].updated_at = datetime.now()
    
    def get_contradictions(self) -> List[Contradiction]:
        """Get all detected contradictions"""
        return list(self._contradictions.values())
    
    def get_contradiction(self, contradiction_id: str) -> Optional[Contradiction]:
        """Get contradiction by ID"""
        return self._contradictions.get(contradiction_id)
    
    def get_active_propositions(
        self,
        propositions: Dict[str, Proposition]
    ) -> List[Proposition]:
        """Get only active propositions"""
        return [
            p for p in propositions.values()
            if p.lifecycle == PropositionLifecycle.ACTIVE
        ]
    
    def get_superseded_propositions(
        self,
        propositions: Dict[str, Proposition]
    ) -> List[Proposition]:
        """Get superseded propositions"""
        return [
            p for p in propositions.values()
            if p.lifecycle == PropositionLifecycle.SUPERSEDED
        ]
    
    def get_contradicted_propositions(
        self,
        propositions: Dict[str, Proposition]
    ) -> List[Proposition]:
        """Get contradicted propositions"""
        return [
            p for p in propositions.values()
            if p.lifecycle == PropositionLifecycle.CONTRADICTED
        ]