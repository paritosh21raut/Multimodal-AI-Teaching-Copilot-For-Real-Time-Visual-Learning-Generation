"""
Embedding Index

Manages embeddings for concepts and mentions using sentence-transformers.
Provides fast similarity search and candidate retrieval.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple, Any
import numpy as np
import threading


class EmbeddingIndex:
    """Manages concept embeddings and similarity search"""
    
    def __init__(self, model=None):
        self._lock = threading.RLock()
        self._model = model
        self._loaded = model is not None
        
        # concept_id -> embedding (numpy array)
        self._concept_embeddings: Dict[str, np.ndarray] = {}
        
        # Cache for similarity computations
        self._similarity_cache: Dict[Tuple[str, str], float] = {}
        self._cache_max_size = 10000
    
    def _ensure_model(self):
        """Lazy-load sentence-transformers model"""
        if not self._loaded:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("all-MiniLM-L6-v2")
                self._loaded = True
            except ImportError:
                raise ImportError("sentence-transformers not available")
        return self._model
    
    def encode(self, text: str) -> Optional[np.ndarray]:
        """Encode text to embedding"""
        model = self._ensure_model()
        
        try:
            embedding = model.encode(
                text,
                convert_to_numpy=True,
                normalize_embeddings=True
            )
            return np.array(embedding, dtype=np.float32)
        except Exception:
            return None
    
    def add_concept_embedding(self, concept_id: str, embedding: np.ndarray) -> None:
        """Add or update concept embedding"""
        with self._lock:
            self._concept_embeddings[concept_id] = embedding
    
    def add_concept_embedding_from_text(self, concept_id: str, text: str) -> Optional[np.ndarray]:
        """Encode text and add as concept embedding"""
        embedding = self.encode(text)
        if embedding is not None:
            self.add_concept_embedding(concept_id, embedding)
        return embedding
    
    def get_concept_embedding(self, concept_id: str) -> Optional[np.ndarray]:
        """Get embedding for concept"""
        with self._lock:
            return self._concept_embeddings.get(concept_id)
    
    def remove_concept(self, concept_id: str) -> None:
        """Remove concept embedding"""
        with self._lock:
            if concept_id in self._concept_embeddings:
                del self._concept_embeddings[concept_id]
            
            # Clean cache
            self._similarity_cache = {
                k: v for k, v in self._similarity_cache.items()
                if concept_id not in k
            }
    
    def find_similar_concepts(
        self,
        query_embedding: np.ndarray,
        candidate_ids: Optional[List[str]] = None,
        threshold: float = 0.7,
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """
        Find concepts similar to query embedding.
        
        Args:
            query_embedding: Query embedding vector
            candidate_ids: Optional list of concept IDs to search (None = all)
            threshold: Minimum similarity threshold
            top_k: Maximum number of results
            
        Returns:
            List of (concept_id, similarity) tuples
        """
        with self._lock:
            results = []
            
            # Determine candidates to search
            if candidate_ids:
                candidates = {
                    cid: self._concept_embeddings.get(cid)
                    for cid in candidate_ids
                    if cid in self._concept_embeddings
                }
            else:
                candidates = self._concept_embeddings
            
            for concept_id, embedding in candidates.items():
                if embedding is None:
                    continue
                
                similarity = self._cosine_similarity(query_embedding, embedding)
                
                if similarity >= threshold:
                    results.append((concept_id, similarity))
            
            # Sort by similarity (highest first)
            results.sort(key=lambda x: x[1], reverse=True)
            
            return results[:top_k]
    
    def find_most_similar(
        self,
        query_embedding: np.ndarray,
        candidate_ids: Optional[List[str]] = None,
        threshold: float = 0.7
    ) -> Optional[Tuple[str, float]]:
        """Find single most similar concept"""
        results = self.find_similar_concepts(
            query_embedding,
            candidate_ids=candidate_ids,
            threshold=threshold,
            top_k=1
        )
        
        if results:
            return results[0]
        
        return None
    
    def compute_similarity(
        self,
        concept_id1: str,
        concept_id2: str
    ) -> float:
        """Compute similarity between two concepts"""
        cache_key = (concept_id1, concept_id2)
        
        with self._lock:
            # Check cache
            if cache_key in self._similarity_cache:
                return self._similarity_cache[cache_key]
            
            emb1 = self._concept_embeddings.get(concept_id1)
            emb2 = self._concept_embeddings.get(concept_id2)
            
            if emb1 is None or emb2 is None:
                return 0.0
            
            similarity = self._cosine_similarity(emb1, emb2)
            
            # Cache result
            if len(self._similarity_cache) < self._cache_max_size:
                self._similarity_cache[cache_key] = similarity
                self._similarity_cache[(concept_id2, concept_id1)] = similarity
            
            return similarity
    
    def batch_encode(self, texts: List[str]) -> List[Optional[np.ndarray]]:
        """Encode multiple texts"""
        model = self._ensure_model()
        
        try:
            embeddings = model.encode(
                texts,
                convert_to_numpy=True,
                normalize_embeddings=True,
                batch_size=8
            )
            return [np.array(emb, dtype=np.float32) for emb in embeddings]
        except Exception:
            return [None] * len(texts)
    
    def clear(self) -> None:
        """Clear all embeddings and cache"""
        with self._lock:
            self._concept_embeddings.clear()
            self._similarity_cache.clear()
    
    def get_stats(self) -> Dict[str, int]:
        """Get index statistics"""
        with self._lock:
            return {
                "total_embeddings": len(self._concept_embeddings),
                "cache_size": len(self._similarity_cache)
            }
    
    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        if a is None or b is None or len(a) != len(b):
            return 0.0
        
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        similarity = dot_product / (norm_a * norm_b)
        return float(max(-1.0, min(1.0, similarity)))