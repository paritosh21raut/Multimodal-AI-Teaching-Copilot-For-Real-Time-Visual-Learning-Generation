"""
Concept Registry

Maintains canonical concept identities and aliases across the lecture.
Handles entity resolution, merging, and deduplication.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from datetime import datetime
import re
import hashlib
import uuid

from .semantic_models import Concept, ConceptRef, Mention, EvidenceSpan


@dataclass
class ResolutionResult:
    """Result of entity resolution"""
    concept_ref: ConceptRef
    is_new: bool
    confidence: float
    resolution_method: str  # 'exact', 'normalized', 'embedding', 'new'
    candidates: List[ConceptRef] = field(default_factory=list)


class ConceptRegistry:
    """Maintains concept identity across lecture chunks"""
    
    def __init__(self):
        self._concepts: Dict[str, Concept] = {}
        self._alias_index: Dict[str, str] = {}  # normalized alias -> concept_id
        self._exact_index: Dict[str, str] = {}  # exact match -> concept_id
        self._embedding_index: Dict[str, List[float]] = {}  # concept_id -> embedding
        
        # Statistics
        self._total_mentions = 0
        self._total_resolutions = 0
        self._total_merges = 0
    
    def resolve(
        self,
        mention: Mention,
        embedding: Optional[List[float]] = None,
        active_concepts: Optional[List[ConceptRef]] = None
    ) -> ResolutionResult:
        """
        Resolve a mention to a concept.
        
        Resolution order:
        1. Exact match
        2. Normalized match
        3. Embedding similarity (if available)
        4. Create new concept
        
        Returns:
            ResolutionResult with concept ref and resolution info
        """
        self._total_resolutions += 1
        
        # Stage 1: Exact match
        exact_key = mention.surface_text.lower().strip()
        concept_id = self._exact_index.get(exact_key)
        if concept_id:
            concept = self._concepts[concept_id]
            concept.mention_count += 1
            concept.updated_at = datetime.now()
            self._total_mentions += 1
            
            return ResolutionResult(
                concept_ref=ConceptRef(
                    concept_id=concept_id,
                    canonical_name=concept.canonical_name,
                    confidence=1.0
                ),
                is_new=False,
                confidence=1.0,
                resolution_method='exact'
            )
        
        # Stage 2: Normalized match
        normalized_key = self._normalize(mention.surface_text)
        concept_id = self._alias_index.get(normalized_key)
        if concept_id:
            concept = self._concepts[concept_id]
            
            # Add this surface form as alias
            if mention.surface_text not in concept.aliases:
                concept.aliases.append(mention.surface_text)
                self._alias_index[self._normalize(mention.surface_text)] = concept_id
                self._exact_index[exact_key] = concept_id
            
            concept.mention_count += 1
            concept.updated_at = datetime.now()
            self._total_mentions += 1
            
            return ResolutionResult(
                concept_ref=ConceptRef(
                    concept_id=concept_id,
                    canonical_name=concept.canonical_name,
                    confidence=0.9
                ),
                is_new=False,
                confidence=0.9,
                resolution_method='normalized'
            )
        
        # Stage 3: Embedding similarity (if we have embeddings)
        if embedding is not None and self._embedding_index:
            best_match = self._find_embedding_match(embedding, active_concepts)
            
            if best_match and best_match[1] > 0.85:
                concept_id, similarity = best_match
                concept = self._concepts[concept_id]
                
                # Merge this mention into existing concept
                if mention.surface_text not in concept.aliases:
                    concept.aliases.append(mention.surface_text)
                    self._alias_index[self._normalize(mention.surface_text)] = concept_id
                    self._exact_index[exact_key] = concept_id
                
                concept.mention_count += 1
                concept.updated_at = datetime.now()
                self._total_mentions += 1
                
                return ResolutionResult(
                    concept_ref=ConceptRef(
                        concept_id=concept_id,
                        canonical_name=concept.canonical_name,
                        confidence=similarity
                    ),
                    is_new=False,
                    confidence=similarity,
                    resolution_method='embedding',
                    candidates=[ConceptRef(
                        concept_id=concept_id,
                        canonical_name=concept.canonical_name,
                        confidence=similarity
                    )]
                )
        
        # Stage 4: Create new concept
        concept = Concept(
            concept_id=str(uuid.uuid4()),
            canonical_name=mention.surface_text,
            aliases=[mention.normalized_text] if mention.normalized_text != mention.surface_text.lower() else [],
            anchor_embedding=embedding,
            centroid_embedding=embedding,
            first_mention=mention.evidence,
            mention_count=1,
            confidence=mention.confidence if mention.confidence > 0 else 0.7,
            concept_type=self._determine_concept_type(mention.surface_text)
        )
        
        self._concepts[concept.concept_id] = concept
        self._alias_index[normalized_key] = concept.concept_id
        self._exact_index[exact_key] = concept.concept_id
        
        if embedding is not None:
            self._embedding_index[concept.concept_id] = embedding
        
        self._total_mentions += 1
        
        return ResolutionResult(
            concept_ref=ConceptRef(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=0.7
            ),
            is_new=True,
            confidence=0.7,
            resolution_method='new'
        )
    
    def merge_concepts(self, source_id: str, target_id: str) -> bool:
        """
        Merge source concept into target concept.
        
        Returns:
            True if merge was successful
        """
        if source_id not in self._concepts or target_id not in self._concepts:
            return False
        
        if source_id == target_id:
            return False
        
        source = self._concepts[source_id]
        target = self._concepts[target_id]
        
        # Merge aliases
        for alias in source.aliases:
            if alias not in target.aliases:
                target.aliases.append(alias)
                self._alias_index[self._normalize(alias)] = target_id
                self._exact_index[alias.lower().strip()] = target_id
        
        # Merge mention counts
        target.mention_count += source.mention_count
        
        # Merge embeddings (weighted average)
        if source.centroid_embedding and target.centroid_embedding:
            target.centroid_embedding = self._average_embeddings(
                target.centroid_embedding,
                source.centroid_embedding,
                target.mention_count,
                source.mention_count
            )
        
        # Update aliases for canonical name
        if source.canonical_name not in target.aliases:
            target.aliases.append(source.canonical_name)
        
        # Remove source concept
        del self._concepts[source_id]
        if source_id in self._embedding_index:
            del self._embedding_index[source_id]
        
        self._total_merges += 1
        
        return True
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self._concepts.get(concept_id)
    
    def get_concept_by_alias(self, alias: str) -> Optional[Concept]:
        """Get concept by alias"""
        normalized = self._normalize(alias)
        concept_id = self._alias_index.get(normalized)
        if concept_id:
            return self._concepts.get(concept_id)
        return None
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts"""
        return list(self._concepts.values())
    
    def get_concept_count(self) -> int:
        """Get total number of concepts"""
        return len(self._concepts)
    
    def get_statistics(self) -> Dict[str, int]:
        """Get registry statistics"""
        return {
            "total_concepts": len(self._concepts),
            "total_aliases": len(self._alias_index),
            "total_mentions": self._total_mentions,
            "total_resolutions": self._total_resolutions,
            "total_merges": self._total_merges
        }
    
    def _find_embedding_match(
        self,
        embedding: List[float],
        active_concepts: Optional[List[ConceptRef]] = None
    ) -> Optional[Tuple[str, float]]:
        """Find best embedding match"""
        best_id = None
        best_similarity = 0.0
        
        # Prioritize active concepts
        if active_concepts:
            for ref in active_concepts:
                if ref.concept_id in self._embedding_index:
                    similarity = self._cosine_similarity(
                        embedding,
                        self._embedding_index[ref.concept_id]
                    )
                    if similarity > best_similarity:
                        best_similarity = similarity
                        best_id = ref.concept_id
        
        # Check all concepts if no good match in active
        if best_similarity < 0.85:
            for concept_id, concept_embedding in self._embedding_index.items():
                similarity = self._cosine_similarity(embedding, concept_embedding)
                if similarity > best_similarity:
                    best_similarity = similarity
                    best_id = concept_id
        
        if best_id and best_similarity > 0.7:
            return best_id, best_similarity
        
        return None
    
    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot_product = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot_product / (norm_a * norm_b)
    
    @staticmethod
    def _average_embeddings(
        a: List[float],
        b: List[float],
        weight_a: int,
        weight_b: int
    ) -> List[float]:
        """Calculate weighted average of two embeddings"""
        if len(a) != len(b):
            return a
        
        total_weight = weight_a + weight_b
        return [
            (a[i] * weight_a + b[i] * weight_b) / total_weight
            for i in range(len(a))
        ]
    
    @staticmethod
    def _normalize(text: str) -> str:
        """Normalize text for comparison"""
        normalized = text.lower()
        normalized = re.sub(r'\b(the|a|an)\b', '', normalized)
        normalized = re.sub(r'[^\w\s-]', ' ', normalized)
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        
        # Basic singularization
        if normalized.endswith('ies') and len(normalized) > 4:
            normalized = normalized[:-3] + 'y'
        elif normalized.endswith('es') and len(normalized) > 4:
            normalized = normalized[:-2]
        elif normalized.endswith('s') and len(normalized) > 3:
            if not normalized.endswith(('ss', 'us', 'is')):
                normalized = normalized[:-1]
        
        return normalized
    
    @staticmethod
    def _determine_concept_type(name: str) -> str:
        """Determine concept type based on name"""
        if name.isupper() and len(name) <= 5:
            return "entity"  # Acronyms
        elif " " in name:
            return "abstraction"  # Multi-word concepts
        elif name[0].isupper():
            return "entity"  # Proper nouns
        else:
            return "abstraction"