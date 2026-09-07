"""
Development Intelligence Tracker (Fixed)

Tracks concept development across the lecture.
Fixed: Lower thresholds, only track explicitly mentioned concepts.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import threading
import uuid

from .development_models import (
    DevelopmentState,
    DevelopmentEventType,
    DevelopmentEvent,
    ConceptDevelopment,
)

from app.semantic.semantic_models import (
    SemanticFrame,
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    InstructionalActType,
    ConceptRef,
    RelationType,
)


class DevelopmentTracker:
    """Tracks concept development across lecture chunks"""
    
    def __init__(self):
        self._lock = threading.RLock()
        
        self._concepts: Dict[str, ConceptDevelopment] = {}
        self._events: List[DevelopmentEvent] = []
        
        # Only track concepts that are explicitly mentioned in frame.concepts
        self._explicit_concepts: Set[str] = set()
        
        # Scoring weights
        self.weights = {
            "mention": 0.10,
            "proposition": 0.25,
            "definition": 0.25,
            "example": 0.20,
            "relation": 0.10,
            "revisit": 0.10,
        }
        
        # LOWERED thresholds
        self.developing_threshold = 0.10  # Lowered from 0.15
        self.established_threshold = 0.40  # Lowered from 0.50
    
    def process_frame(
        self,
        frame: SemanticFrame,
        chunk_id: str = "",
    ) -> List[DevelopmentEvent]:
        """Process a semantic frame and update development states"""
        with self._lock:
            events = []
            
            # Track explicitly mentioned concepts
            for concept in frame.concepts:
                self._explicit_concepts.add(concept.concept_id)
                event = self._track_mention(concept, chunk_id)
                if event:
                    events.append(event)
            
            # Track propositions - ONLY for explicitly mentioned concepts
            for prop in frame.propositions:
                if prop.subject and prop.subject.concept_id in self._explicit_concepts:
                    event = self._track_proposition(prop.subject, chunk_id)
                    if event:
                        events.append(event)
                
                if prop.object and prop.object.concept_id in self._explicit_concepts:
                    event = self._track_proposition(prop.object, chunk_id)
                    if event:
                        events.append(event)
            
            # Track definitions
            for act in frame.instructional_acts:
                if act.act_type == InstructionalActType.DEFINITION:
                    for concept_ref in act.concept_refs:
                        if concept_ref.concept_id in self._explicit_concepts:
                            event = self._track_definition(concept_ref, chunk_id)
                            if event:
                                events.append(event)
            
            # Track examples
            for act in frame.instructional_acts:
                if act.act_type == InstructionalActType.EXAMPLE:
                    for concept_ref in act.concept_refs:
                        if concept_ref.concept_id in self._explicit_concepts:
                            event = self._track_example(concept_ref, chunk_id)
                            if event:
                                events.append(event)
            
            # Track relations - only for explicitly mentioned concepts
            for relation in frame.relations:
                if relation.source and relation.source.concept_id in self._explicit_concepts:
                    event = self._track_relation(relation.source, chunk_id)
                    if event:
                        events.append(event)
                
                if relation.target and relation.target.concept_id in self._explicit_concepts:
                    event = self._track_relation(relation.target, chunk_id)
                    if event:
                        events.append(event)
            
            # Recalculate scores and check state transitions
            for concept_id in self._concepts:
                self._recalculate_score(concept_id)
                state_event = self._check_state_transition(concept_id, chunk_id)
                if state_event:
                    events.append(state_event)
            
            self._events.extend(events)
            
            return events
    
    def _track_mention(
        self,
        concept: Concept,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Track a concept mention"""
        dev = self._get_or_create_concept(concept)
        
        dev.mention_count += 1
        dev.last_seen = datetime.now()
        
        if chunk_id and chunk_id not in dev.distinct_chunks:
            dev.distinct_chunks.append(chunk_id)
        
        return DevelopmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=DevelopmentEventType.CONCEPT_MENTIONED,
            concept_id=concept.concept_id,
            chunk_id=chunk_id,
            payload={"concept_name": concept.canonical_name},
        )
    
    def _track_proposition(
        self,
        concept_ref: ConceptRef,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Track a proposition about a concept"""
        dev = self._get_or_create_concept_from_ref(concept_ref)
        
        dev.proposition_count += 1
        dev.last_seen = datetime.now()
        
        return DevelopmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=DevelopmentEventType.PROPOSITION_ADDED,
            concept_id=concept_ref.concept_id,
            chunk_id=chunk_id,
            payload={"concept_name": concept_ref.canonical_name},
        )
    
    def _track_definition(
        self,
        concept_ref: ConceptRef,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Track a definition"""
        dev = self._get_or_create_concept_from_ref(concept_ref)
        
        dev.definition_count += 1
        dev.last_seen = datetime.now()
        
        return DevelopmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=DevelopmentEventType.DEFINITION_ADDED,
            concept_id=concept_ref.concept_id,
            chunk_id=chunk_id,
        )
    
    def _track_example(
        self,
        concept_ref: ConceptRef,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Track an example"""
        dev = self._get_or_create_concept_from_ref(concept_ref)
        
        dev.example_count += 1
        dev.last_seen = datetime.now()
        
        return DevelopmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=DevelopmentEventType.EXAMPLE_ADDED,
            concept_id=concept_ref.concept_id,
            chunk_id=chunk_id,
        )
    
    def _track_relation(
        self,
        concept_ref: ConceptRef,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Track a relation"""
        dev = self._get_or_create_concept_from_ref(concept_ref)
        
        dev.relation_count += 1
        dev.last_seen = datetime.now()
        
        return DevelopmentEvent(
            event_id=str(uuid.uuid4()),
            event_type=DevelopmentEventType.RELATION_ADDED,
            concept_id=concept_ref.concept_id,
            chunk_id=chunk_id,
        )
    
    def _get_or_create_concept(
        self,
        concept: Concept,
    ) -> ConceptDevelopment:
        """Get existing or create new concept development"""
        if concept.concept_id not in self._concepts:
            self._concepts[concept.concept_id] = ConceptDevelopment(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence,
            )
        
        return self._concepts[concept.concept_id]
    
    def _get_or_create_concept_from_ref(
        self,
        concept_ref: ConceptRef,
    ) -> ConceptDevelopment:
        """Get existing or create from ConceptRef"""
        if concept_ref.concept_id not in self._concepts:
            self._concepts[concept_ref.concept_id] = ConceptDevelopment(
                concept_id=concept_ref.concept_id,
                canonical_name=concept_ref.canonical_name,
                confidence=concept_ref.confidence,
            )
        
        return self._concepts[concept_ref.concept_id]
    
    def _recalculate_score(self, concept_id: str) -> None:
        """Recalculate development score"""
        dev = self._concepts[concept_id]
        
        score = (
            min(1.0, dev.mention_count / 2) * self.weights["mention"] +
            min(1.0, dev.proposition_count / 2) * self.weights["proposition"] +
            min(1.0, dev.definition_count) * self.weights["definition"] +
            min(1.0, dev.example_count) * self.weights["example"] +
            min(1.0, dev.relation_count / 2) * self.weights["relation"] +
            min(1.0, dev.revisit_count) * self.weights["revisit"]
        )
        
        dev.development_score = round(min(1.0, score), 4)
    
    def _check_state_transition(
        self,
        concept_id: str,
        chunk_id: str,
    ) -> Optional[DevelopmentEvent]:
        """Check if concept should change state"""
        dev = self._concepts[concept_id]
        
        old_state = dev.state
        new_state = old_state
        
        if dev.development_score >= self.established_threshold:
            new_state = DevelopmentState.ESTABLISHED
        elif dev.development_score >= self.developing_threshold:
            new_state = DevelopmentState.DEVELOPING
        else:
            new_state = DevelopmentState.MENTIONED
        
        if new_state != old_state:
            dev.state = new_state
            
            return DevelopmentEvent(
                event_id=str(uuid.uuid4()),
                event_type=DevelopmentEventType.STATE_CHANGED,
                concept_id=concept_id,
                chunk_id=chunk_id,
                payload={
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "concept_name": dev.canonical_name,
                },
            )
        
        return None
    
    def get_development(self, concept_id: str) -> Optional[ConceptDevelopment]:
        """Get development state for a concept"""
        with self._lock:
            return self._concepts.get(concept_id)
    
    def get_all_developments(self) -> List[ConceptDevelopment]:
        """Get all concept developments"""
        with self._lock:
            return list(self._concepts.values())
    
    def get_established_concepts(self) -> List[ConceptDevelopment]:
        """Get concepts that are ESTABLISHED"""
        with self._lock:
            return [
                d for d in self._concepts.values()
                if d.state == DevelopmentState.ESTABLISHED
            ]
    
    def get_developing_concepts(self) -> List[ConceptDevelopment]:
        """Get concepts that are DEVELOPING"""
        with self._lock:
            return [
                d for d in self._concepts.values()
                if d.state == DevelopmentState.DEVELOPING
            ]
    
    def get_mentioned_concepts(self) -> List[ConceptDevelopment]:
        """Get concepts that are only MENTIONED"""
        with self._lock:
            return [
                d for d in self._concepts.values()
                if d.state == DevelopmentState.MENTIONED
            ]
    
    def get_top_developed(self, limit: int = 10) -> List[ConceptDevelopment]:
        """Get most developed concepts"""
        with self._lock:
            sorted_concepts = sorted(
                self._concepts.values(),
                key=lambda x: x.development_score,
                reverse=True,
            )
            return sorted_concepts[:limit]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get development statistics"""
        with self._lock:
            established = len(self.get_established_concepts())
            developing = len(self.get_developing_concepts())
            mentioned = len(self.get_mentioned_concepts())
            
            return {
                "total_concepts": len(self._concepts),
                "established": established,
                "developing": developing,
                "mentioned": mentioned,
                "total_events": len(self._events),
            }