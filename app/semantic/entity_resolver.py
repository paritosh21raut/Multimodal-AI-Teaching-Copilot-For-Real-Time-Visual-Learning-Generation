"""
Entity Resolver

Resolves mentions to concepts using multiple signals.
Prevents incorrect merging while maintaining concept identity.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any
import re

from .semantic_models import Concept, ConceptRef, Mention, EvidenceSpan
from .concept_registry import ConceptRegistry, ResolutionResult


class EntityResolver:
    """Resolves mentions to stable concept identities"""
    
    def __init__(self):
        self.registry = ConceptRegistry()
        
        # Minimum confidence thresholds
        self.exact_match_threshold = 1.0
        self.normalized_match_threshold = 0.85
        self.embedding_match_threshold = 0.80
        self.min_confidence = 0.50
    
    def resolve(
        self,
        mention: Mention,
        embedding: Optional[List[float]] = None,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None
    ) -> ResolutionResult:
        """
        Resolve mention to concept.
        
        Args:
            mention: The mention to resolve
            embedding: Optional embedding for similarity matching
            active_concepts: Currently active concepts (recent context)
            topic_concepts: Concepts associated with current topic
            
        Returns:
            ResolutionResult
        """
        # Try exact match first
        result = self.registry.resolve(
            mention=mention,
            embedding=embedding,
            active_concepts=active_concepts
        )
        
        # If new concept, check if we should be more conservative
        if result.is_new and embedding is not None:
            # Check topic-local concepts for potential matches
            if topic_concepts:
                topic_match = self._check_topic_concepts(
                    mention, embedding, topic_concepts
                )
                if topic_match:
                    return topic_match
        
        return result
    
    def resolve_all(
        self,
        mentions: List[Mention],
        embeddings: Optional[Dict[str, List[float]]] = None,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None
    ) -> List[ResolutionResult]:
        """Resolve multiple mentions"""
        results = []
        
        for mention in mentions:
            embedding = None
            if embeddings and mention.normalized_text in embeddings:
                embedding = embeddings[mention.normalized_text]
            
            result = self.resolve(
                mention=mention,
                embedding=embedding,
                active_concepts=active_concepts,
                topic_concepts=topic_concepts
            )
            results.append(result)
        
        return results
    
    def _check_topic_concepts(
        self,
        mention: Mention,
        embedding: List[float],
        topic_concepts: List[ConceptRef]
    ) -> Optional[ResolutionResult]:
        """Check if mention matches any topic-local concepts"""
        best_match = None
        best_similarity = 0.0
        
        for ref in topic_concepts:
            concept = self.registry.get_concept(ref.concept_id)
            if concept and concept.centroid_embedding:
                similarity = self._cosine_similarity(
                    embedding,
                    concept.centroid_embedding
                )
                
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_match = concept
        
        # If strong match found, merge into existing
        if best_match and best_similarity > self.embedding_match_threshold:
            # Add alias
            if mention.surface_text not in best_match.aliases:
                best_match.aliases.append(mention.surface_text)
            
            best_match.mention_count += 1
            
            return ResolutionResult(
                concept_ref=ConceptRef(
                    concept_id=best_match.concept_id,
                    canonical_name=best_match.canonical_name,
                    confidence=best_similarity
                ),
                is_new=False,
                confidence=best_similarity,
                resolution_method='topic_local',
                candidates=[ConceptRef(
                    concept_id=best_match.concept_id,
                    canonical_name=best_match.canonical_name,
                    confidence=best_similarity
                )]
            )
        
        return None
    
    def merge_concepts(self, source_id: str, target_id: str) -> bool:
        """Merge two concepts"""
        return self.registry.merge_concepts(source_id, target_id)
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.registry.get_concept(concept_id)
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts"""
        return self.registry.get_all_concepts()
    
    def get_statistics(self) -> Dict[str, int]:
        """Get resolver statistics"""
        return self.registry.get_statistics()
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity"""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)