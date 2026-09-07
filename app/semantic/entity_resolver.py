"""
Entity Resolver (Phase 3 - Fixed)

Resolves mentions to concepts using multiple signals including
embeddings for improved accuracy with proper ambiguity handling.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any
import re
import numpy as np
from datetime import datetime

from .semantic_models import Concept, ConceptRef, Mention, EvidenceSpan
from .concept_registry import ConceptRegistry, ResolutionResult
from .embedding_index import EmbeddingIndex
from .embedding_retriever import EmbeddingRetriever


class EntityResolver:
    """Resolves mentions to stable concept identities"""
    
    def __init__(self, embedding_index: Optional[EmbeddingIndex] = None):
        self.registry = ConceptRegistry()
        self.embedding_index = embedding_index or EmbeddingIndex()
        self.embedding_retriever = EmbeddingRetriever(self.embedding_index)
        
        # Resolution thresholds
        self.exact_match_threshold = 1.0
        self.normalized_match_threshold = 0.85
        self.embedding_match_threshold = 0.85
        self.margin_threshold = 0.03
        self.min_confidence = 0.50
    
    def resolve(
        self,
        mention: Mention,
        embedding: Optional[np.ndarray] = None,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None
    ) -> ResolutionResult:
        """
        Resolve mention to concept using multi-stage approach.
        """
        # Stage 1 & 2: Exact and normalized match (from registry)
        result = self.registry.resolve(
            mention=mention,
            embedding=embedding.tolist() if isinstance(embedding, np.ndarray) else embedding,
            active_concepts=active_concepts
        )
        
        # If resolved via exact or normalized, return immediately
        if not result.is_new:
            return result
        
        # Stage 3: Embedding similarity (only for new concepts)
        if embedding is not None and result.is_new:
            embedding_result = self._resolve_with_embedding(
                mention,
                embedding,
                active_concepts,
                topic_concepts
            )
            
            if embedding_result:
                return embedding_result
        
        # If still new, register its embedding
        if embedding is not None and result.is_new:
            self.embedding_index.add_concept_embedding(
                result.concept_ref.concept_id,
                embedding
            )
        
        return result
    
    def _resolve_with_embedding(
        self,
        mention: Mention,
        embedding: np.ndarray,
        active_concepts: Optional[List[ConceptRef]],
        topic_concepts: Optional[List[ConceptRef]]
    ) -> Optional[ResolutionResult]:
        """Resolve using embedding similarity with ambiguity check"""
        
        # Retrieve top candidates
        candidates = self.embedding_retriever.retrieve_candidates(
            embedding,
            self.registry,
            active_concepts=active_concepts,
            topic_concepts=topic_concepts,
            top_k=5
        )
        
        if not candidates:
            return None
        
        best_match, best_similarity = candidates[0]
        
        # Check if similarity is high enough
        if best_similarity < self.embedding_match_threshold:
            return None
        
        # Check ambiguity (if second match is very close)
        if len(candidates) > 1:
            second_similarity = candidates[1][1]
            
            if best_similarity - second_similarity < self.margin_threshold:
                # Too ambiguous - don't force match
                return None
        
        # Merge with existing concept
        concept = self.registry.get_concept(best_match.concept_id)
        
        if concept:
            # Add this mention as alias
            if mention.surface_text not in concept.aliases:
                concept.aliases.append(mention.surface_text)
                self.registry._alias_index[
                    self.registry._normalize(mention.surface_text)
                ] = concept.concept_id
                self.registry._exact_index[
                    mention.surface_text.lower().strip()
                ] = concept.concept_id
            
            concept.mention_count += 1
            concept.updated_at = datetime.now()
            
            # Update centroid embedding (weighted average)
            if concept.centroid_embedding:
                old_embedding = np.array(concept.centroid_embedding)
                concept.centroid_embedding = (
                    0.7 * old_embedding + 0.3 * embedding
                ).tolist()
                
                self.embedding_index.add_concept_embedding(
                    concept.concept_id,
                    np.array(concept.centroid_embedding)
                )
            
            return ResolutionResult(
                concept_ref=ConceptRef(
                    concept_id=concept.concept_id,
                    canonical_name=concept.canonical_name,
                    confidence=best_similarity
                ),
                is_new=False,
                confidence=best_similarity,
                resolution_method='embedding',
                candidates=[c[0] for c in candidates[:3]]
            )
        
        return None
    
    def resolve_all(
        self,
        mentions: List[Mention],
        embeddings: Optional[Dict[str, np.ndarray]] = None,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None
    ) -> List[ResolutionResult]:
        """Resolve multiple mentions"""
        results = []
        
        for mention in mentions:
            embedding = None
            if embeddings and mention.normalized_text in embeddings:
                embedding = embeddings[mention.normalized_text]
            elif embeddings and mention.surface_text in embeddings:
                embedding = embeddings[mention.surface_text]
            
            result = self.resolve(
                mention=mention,
                embedding=embedding,
                active_concepts=active_concepts,
                topic_concepts=topic_concepts
            )
            results.append(result)
        
        return results
    
    def merge_concepts(self, source_id: str, target_id: str) -> bool:
        """Merge two concepts"""
        success = self.registry.merge_concepts(source_id, target_id)
        
        if success:
            # Remove source embedding
            self.embedding_index.remove_concept(source_id)
        
        return success
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.registry.get_concept(concept_id)
    
    def get_concept_by_alias(self, alias: str) -> Optional[Concept]:
        """Get concept by alias"""
        return self.registry.get_concept_by_alias(alias)
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts"""
        return self.registry.get_all_concepts()
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get resolver statistics"""
        stats = self.registry.get_statistics()
        stats.update(self.embedding_index.get_stats())
        return stats