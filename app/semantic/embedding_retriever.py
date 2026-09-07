"""
Embedding Retriever

Retrieves candidate concepts using embedding similarity.
Integrates with ConceptRegistry for entity resolution.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import numpy as np

from .semantic_models import Concept, ConceptRef, Mention
from .embedding_index import EmbeddingIndex
from .concept_registry import ConceptRegistry


class EmbeddingRetriever:
    """Retrieves candidate concepts using embeddings"""
    
    def __init__(self, embedding_index: Optional[EmbeddingIndex] = None):
        self.embedding_index = embedding_index or EmbeddingIndex()
        
        # Retrieval thresholds
        self.high_similarity_threshold = 0.85
        self.medium_similarity_threshold = 0.70
        self.low_similarity_threshold = 0.55
    
    def retrieve_candidates(
        self,
        query_embedding: np.ndarray,
        registry: ConceptRegistry,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None,
        top_k: int = 10
    ) -> List[Tuple[ConceptRef, float]]:
        """
        Retrieve candidate concepts for a query embedding.
        
        Prioritizes active concepts, then topic concepts, then all concepts.
        """
        candidates = []
        seen_ids = set()
        
        # Priority 1: Active concepts
        if active_concepts:
            active_ids = [ref.concept_id for ref in active_concepts]
            active_matches = self.embedding_index.find_similar_concepts(
                query_embedding,
                candidate_ids=active_ids,
                threshold=self.low_similarity_threshold,
                top_k=top_k
            )
            
            for concept_id, similarity in active_matches:
                concept = registry.get_concept(concept_id)
                if concept:
                    candidates.append((
                        ConceptRef(
                            concept_id=concept_id,
                            canonical_name=concept.canonical_name,
                            confidence=similarity
                        ),
                        similarity
                    ))
                    seen_ids.add(concept_id)
        
        # Priority 2: Topic concepts
        if topic_concepts and len(candidates) < top_k:
            topic_ids = [
                ref.concept_id for ref in topic_concepts
                if ref.concept_id not in seen_ids
            ]
            
            if topic_ids:
                topic_matches = self.embedding_index.find_similar_concepts(
                    query_embedding,
                    candidate_ids=topic_ids,
                    threshold=self.medium_similarity_threshold,
                    top_k=top_k - len(candidates)
                )
                
                for concept_id, similarity in topic_matches:
                    concept = registry.get_concept(concept_id)
                    if concept:
                        candidates.append((
                            ConceptRef(
                                concept_id=concept_id,
                                canonical_name=concept.canonical_name,
                                confidence=similarity
                            ),
                            similarity
                        ))
                        seen_ids.add(concept_id)
        
        # Priority 3: All concepts
        if len(candidates) < top_k:
            all_matches = self.embedding_index.find_similar_concepts(
                query_embedding,
                candidate_ids=None,
                threshold=self.medium_similarity_threshold,
                top_k=top_k - len(candidates)
            )
            
            for concept_id, similarity in all_matches:
                if concept_id in seen_ids:
                    continue
                
                concept = registry.get_concept(concept_id)
                if concept:
                    candidates.append((
                        ConceptRef(
                            concept_id=concept_id,
                            canonical_name=concept.canonical_name,
                            confidence=similarity
                        ),
                        similarity
                    ))
                    seen_ids.add(concept_id)
        
        # Sort by similarity
        candidates.sort(key=lambda x: x[1], reverse=True)
        
        return candidates[:top_k]
    
    def get_best_match(
        self,
        query_embedding: np.ndarray,
        registry: ConceptRegistry,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None,
        margin_threshold: float = 0.05
    ) -> Optional[Tuple[ConceptRef, float]]:
        """
        Get best matching concept with margin check.
        
        Returns None if no match above threshold or if top two matches
        are too close (ambiguous).
        """
        candidates = self.retrieve_candidates(
            query_embedding,
            registry,
            active_concepts=active_concepts,
            topic_concepts=topic_concepts,
            top_k=5
        )
        
        if not candidates:
            return None
        
        best_match, best_similarity = candidates[0]
        
        # Check if similarity is high enough
        if best_similarity < self.medium_similarity_threshold:
            return None
        
        # Check margin (avoid ambiguous matches)
        if len(candidates) > 1:
            second_similarity = candidates[1][1]
            
            if best_similarity - second_similarity < margin_threshold:
                # Too close to call - ambiguous
                return None
        
        return best_match, best_similarity
    
    def encode_and_retrieve(
        self,
        text: str,
        registry: ConceptRegistry,
        active_concepts: Optional[List[ConceptRef]] = None,
        topic_concepts: Optional[List[ConceptRef]] = None
    ) -> List[Tuple[ConceptRef, float]]:
        """Encode text and retrieve candidates"""
        embedding = self.embedding_index.encode(text)
        
        if embedding is None:
            return []
        
        return self.retrieve_candidates(
            embedding,
            registry,
            active_concepts=active_concepts,
            topic_concepts=topic_concepts
        )