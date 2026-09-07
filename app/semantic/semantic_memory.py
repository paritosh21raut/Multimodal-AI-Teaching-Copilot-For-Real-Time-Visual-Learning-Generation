"""
Semantic Memory

Maintains active context, topic-local memory, and lecture-wide memory.
Supports incremental updates and bounded retrieval.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any
from collections import deque
from datetime import datetime
import threading

from .semantic_models import Concept, ConceptRef, Proposition, EvidenceSpan
from .concept_registry import ConceptRegistry


class ActiveContext:
    """Maintains sliding window of recently active concepts"""
    
    def __init__(self, window_size: int = 10):
        self._window = deque(maxlen=window_size)
        self._activation_scores: Dict[str, float] = {}
        self._lock = threading.RLock()
    
    def add_concept(self, concept_id: str, activation: float = 1.0) -> None:
        """Add or activate a concept"""
        with self._lock:
            if concept_id not in self._window:
                self._window.append(concept_id)
            
            # Boost activation
            self._activation_scores[concept_id] = activation
            
            # Decay other concepts
            self._decay(0.8)
    
    def get_active_concepts(self, limit: int = 10) -> List[Tuple[str, float]]:
        """Get active concepts with activation scores"""
        with self._lock:
            sorted_concepts = sorted(
                self._activation_scores.items(),
                key=lambda x: x[1],
                reverse=True
            )
            return sorted_concepts[:limit]
    
    def get_concept_refs(self, registry: ConceptRegistry, limit: int = 10) -> List[ConceptRef]:
        """Get concept refs for active concepts"""
        refs = []
        for concept_id, activation in self.get_active_concepts(limit):
            concept = registry.get_concept(concept_id)
            if concept:
                refs.append(ConceptRef(
                    concept_id=concept_id,
                    canonical_name=concept.canonical_name,
                    confidence=activation
                ))
        return refs
    
    def _decay(self, factor: float) -> None:
        """Decay all activation scores"""
        for concept_id in self._activation_scores:
            self._activation_scores[concept_id] *= factor
        
        # Remove very low activations
        self._activation_scores = {
            cid: score for cid, score in self._activation_scores.items()
            if score > 0.05
        }
    
    def clear(self) -> None:
        """Clear active context"""
        with self._lock:
            self._window.clear()
            self._activation_scores.clear()


class TopicMemory:
    """Maintains concepts associated with topics"""
    
    def __init__(self):
        self._topic_concepts: Dict[str, Set[str]] = {}  # topic_path -> concept_ids
        self._lock = threading.RLock()
    
    def add_concept_to_topic(self, topic_path: str, concept_id: str) -> None:
        """Associate concept with topic"""
        with self._lock:
            if topic_path not in self._topic_concepts:
                self._topic_concepts[topic_path] = set()
            self._topic_concepts[topic_path].add(concept_id)
    
    def get_topic_concepts(self, topic_path: str) -> Set[str]:
        """Get concepts for a topic"""
        with self._lock:
            return self._topic_concepts.get(topic_path, set())
    
    def get_topic_concept_refs(
        self,
        topic_path: str,
        registry: ConceptRegistry,
        limit: int = 20
    ) -> List[ConceptRef]:
        """Get concept refs for a topic"""
        concept_ids = self.get_topic_concepts(topic_path)
        refs = []
        
        for concept_id in list(concept_ids)[:limit]:
            concept = registry.get_concept(concept_id)
            if concept:
                refs.append(ConceptRef(
                    concept_id=concept_id,
                    canonical_name=concept.canonical_name,
                    confidence=concept.confidence
                ))
        
        return refs
    
    def clear(self) -> None:
        """Clear topic memory"""
        with self._lock:
            self._topic_concepts.clear()


class SemanticMemory:
    """Complete semantic memory for the lecture"""
    
    def __init__(self):
        self.registry = ConceptRegistry()
        self.active_context = ActiveContext(window_size=10)
        self.topic_memory = TopicMemory()
        
        # Proposition store
        self._propositions: Dict[str, Proposition] = {}
        
        # Evidence store
        self._evidence: Dict[str, EvidenceSpan] = {}
        
        # Compressed archive for older content
        self._archive: Dict[str, Any] = {}
        
        self._lock = threading.RLock()
    
    def add_concept(
        self,
        concept: Concept,
        topic_path: Optional[str] = None
    ) -> None:
        """Add concept to memory"""
        with self._lock:
            self.registry._concepts[concept.concept_id] = concept
            
            # Add to alias index
            for alias in concept.aliases:
                self.registry._alias_index[self.registry._normalize(alias)] = concept.concept_id
            
            self.registry._exact_index[concept.canonical_name.lower().strip()] = concept.concept_id
            
            # Activate in context
            self.active_context.add_concept(concept.concept_id)
            
            # Associate with topic
            if topic_path:
                self.topic_memory.add_concept_to_topic(topic_path, concept.concept_id)
    
    def resolve_mention(
        self,
        mention: Mention,
        embedding: Optional[List[float]] = None,
        topic_path: Optional[str] = None
    ) -> ResolutionResult:
        """Resolve mention to concept"""
        # Get active concepts for resolution
        active_refs = self.active_context.get_concept_refs(self.registry)
        
        # Get topic concepts
        topic_refs = None
        if topic_path:
            topic_refs = self.topic_memory.get_topic_concept_refs(
                topic_path, self.registry
            )
        
        # Resolve
        result = self.registry.resolve(
            mention=mention,
            embedding=embedding,
            active_concepts=active_refs
        )
        
        # If new concept, add to active context and topic
        if result.is_new:
            self.active_context.add_concept(result.concept_ref.concept_id)
            if topic_path:
                self.topic_memory.add_concept_to_topic(
                    topic_path, result.concept_ref.concept_id
                )
        else:
            # Activate existing concept
            self.active_context.add_concept(result.concept_ref.concept_id)
        
        return result
    
    def add_proposition(self, proposition: Proposition) -> None:
        """Add proposition to memory"""
        with self._lock:
            self._propositions[proposition.proposition_id] = proposition
    
    def get_proposition(self, proposition_id: str) -> Optional[Proposition]:
        """Get proposition by ID"""
        with self._lock:
            return self._propositions.get(proposition_id)
    
    def get_propositions_for_concept(self, concept_id: str) -> List[Proposition]:
        """Get all propositions involving a concept"""
        with self._lock:
            result = []
            for prop in self._propositions.values():
                if (prop.subject and prop.subject.concept_id == concept_id) or \
                   (prop.object and prop.object.concept_id == concept_id):
                    result.append(prop)
            return result
    
    def add_evidence(self, evidence: EvidenceSpan) -> None:
        """Add evidence to memory"""
        with self._lock:
            self._evidence[evidence.evidence_id] = evidence
    
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceSpan]:
        """Get evidence by ID"""
        with self._lock:
            return self._evidence.get(evidence_id)
    
    def decay_context(self, factor: float = 0.9) -> None:
        """Decay active context"""
        self.active_context._decay(factor)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics"""
        with self._lock:
            return {
                "registry": self.registry.get_statistics(),
                "active_concepts": len(self.active_context._activation_scores),
                "topic_count": len(self.topic_memory._topic_concepts),
                "propositions": len(self._propositions),
                "evidence": len(self._evidence),
                "archive": len(self._archive)
            }
    
    def compress_old_content(self, threshold_minutes: int = 30) -> None:
        """
        Compress content older than threshold.
        Moves old propositions to archive while preserving evidence links.
        """
        with self._lock:
            current_time = datetime.now()
            
            for prop_id, prop in list(self._propositions.items()):
                if (current_time - prop.created_at).total_seconds() > threshold_minutes * 60:
                    # Move to archive
                    self._archive[prop_id] = prop
                    del self._propositions[prop_id]
    
    def clear(self) -> None:
        """Clear all memory"""
        with self._lock:
            self.registry = ConceptRegistry()
            self.active_context.clear()
            self.topic_memory.clear()
            self._propositions.clear()
            self._evidence.clear()
            self._archive.clear()