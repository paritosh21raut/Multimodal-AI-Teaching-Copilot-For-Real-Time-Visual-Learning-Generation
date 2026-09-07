"""
Coreference Resolution (Fixed v4)

Resolves pronouns and definite noun phrases to their antecedents.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple, Any
import re
from datetime import datetime

from .semantic_models import (
    Coreference,
    UnresolvedReference,
    ConceptRef,
    Mention,
    EvidenceSpan
)
from .concept_registry import ConceptRegistry


class CoreferenceResolver:
    """Resolves references to concepts across chunks"""
    
    PRONOUNS = {
        "it": "singular_neutral",
        "its": "singular_neutral",
        "this": "singular_neutral",
        "that": "singular_neutral",
        "these": "plural",
        "those": "plural",
        "they": "plural",
        "them": "plural",
        "their": "plural",
        "he": "singular_male",
        "she": "singular_female",
        "his": "singular_male",
        "her": "singular_female",
    }
    
    DEFINITE_NP_PATTERNS = [
        r'\bthe\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b',
        r'\bthis\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b',
        r'\bthat\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b',
        r'\bthese\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b',
        r'\bthose\s+([a-zA-Z]+(?:\s+[a-zA-Z]+){0,3})\b',
    ]
    
    def __init__(self):
        self._compiled_np_patterns = [
            re.compile(pattern, re.IGNORECASE)
            for pattern in self.DEFINITE_NP_PATTERNS
        ]
        
        self.min_pronoun_confidence = 0.5
        self.min_np_confidence = 0.5
        
        self.recency_weight = 0.2
        self.type_weight = 0.2
        self.acronym_bonus = 0.3
        self.proper_noun_bonus = 0.2
        self.generic_penalty = 0.1
    
    def resolve_pronouns(
        self,
        text: str,
        active_concepts: List[ConceptRef],
        evidence: Optional[EvidenceSpan] = None
    ) -> List[Coreference]:
        """Resolve pronouns in text to active concepts"""
        coreferences = []
        
        words = text.split()
        
        for i, word in enumerate(words):
            clean_word = word.lower().strip('.,;:!?()')
            
            if clean_word in self.PRONOUNS:
                antecedent = self._find_antecedent(
                    clean_word,
                    active_concepts
                )
                
                if antecedent and antecedent[1] >= self.min_pronoun_confidence:
                    coreference = Coreference(
                        mention_span=evidence,
                        antecedent_ref=antecedent[0],
                        confidence=min(1.0, antecedent[1])
                    )
                    coreferences.append(coreference)
        
        return coreferences
    
    def resolve_definite_nps(
        self,
        text: str,
        registry: ConceptRegistry,
        active_concepts: List[ConceptRef],
        evidence: Optional[EvidenceSpan] = None
    ) -> List[Coreference]:
        """Resolve definite noun phrases to concepts"""
        coreferences = []
        
        for pattern in self._compiled_np_patterns:
            for match in pattern.finditer(text):
                np_text = match.group(1).strip()
                
                matching_concept = self._find_np_match(
                    np_text,
                    registry,
                    active_concepts
                )
                
                if matching_concept and matching_concept[1] >= self.min_np_confidence:
                    coreference = Coreference(
                        mention_span=evidence,
                        antecedent_ref=matching_concept[0],
                        confidence=min(1.0, matching_concept[1])
                    )
                    coreferences.append(coreference)
        
        return coreferences
    
    def resolve_all(
        self,
        text: str,
        registry: ConceptRegistry,
        active_concepts: List[ConceptRef],
        evidence: Optional[EvidenceSpan] = None
    ) -> List[Coreference]:
        """Resolve all coreferences in text"""
        coreferences = []
        
        pronoun_corefs = self.resolve_pronouns(
            text,
            active_concepts,
            evidence
        )
        coreferences.extend(pronoun_corefs)
        
        np_corefs = self.resolve_definite_nps(
            text,
            registry,
            active_concepts,
            evidence
        )
        coreferences.extend(np_corefs)
        
        return self._deduplicate(coreferences)
    
    def _find_antecedent(
        self,
        pronoun: str,
        active_concepts: List[ConceptRef]
    ) -> Optional[Tuple[ConceptRef, float]]:
        """Find antecedent for pronoun"""
        if not active_concepts:
            return None
        
        pronoun_type = self.PRONOUNS.get(pronoun)
        
        if pronoun_type is None:
            return None
        
        scored = []
        for i, concept in enumerate(active_concepts):
            score = self._score_antecedent(concept, pronoun_type, i)
            scored.append((concept, score))
        
        scored.sort(key=lambda x: x[1], reverse=True)
        
        if scored and scored[0][1] > 0:
            if len(scored) == 1:
                return scored[0]
            
            top_concept, top_score = scored[0]
            second_concept, second_score = scored[1]
            
            margin = top_score - second_score
            
            # If clear margin, resolve
            if margin >= 0.2:
                return scored[0]
            
            # If same type, recency wins
            top_type = self._get_concept_type(top_concept.canonical_name)
            second_type = self._get_concept_type(second_concept.canonical_name)
            
            if top_type == second_type:
                return scored[0]
            
            # Different types - check if one is clearly better
            type_ranks = {"acronym": 3, "proper_noun": 2, "generic": 1}
            top_rank = type_ranks.get(top_type, 0)
            second_rank = type_ranks.get(second_type, 0)
            
            if top_rank > second_rank + 1:
                # Top is significantly better type (acronym vs generic)
                return scored[0]
            
            # Otherwise ambiguous
            return None
        
        return None
    
    def _score_antecedent(
        self,
        concept: ConceptRef,
        pronoun_type: str,
        position: int
    ) -> float:
        """Score a concept as potential antecedent"""
        concept_name = concept.canonical_name
        
        score = 0.3
        
        # Recency bonus
        score += self.recency_weight * max(0.0, 1.0 - position * 0.3)
        
        # Concept type score
        concept_type = self._get_concept_type(concept_name)
        if concept_type == "acronym":
            score += self.type_weight * (1.0 + self.acronym_bonus)
        elif concept_type == "proper_noun":
            score += self.type_weight * (0.8 + self.proper_noun_bonus)
        else:
            score += self.type_weight * (0.4 - self.generic_penalty)
        
        # Grammatical matching
        if pronoun_type == "singular_neutral":
            if self._is_singular(concept_name.lower()):
                score += 0.1
        elif pronoun_type == "plural":
            if self._is_plural(concept_name.lower()):
                score += 0.1
        
        score += concept.confidence * 0.1
        
        return min(1.0, score)
    
    def _get_concept_type(self, concept_name: str) -> str:
        """Determine concept type"""
        if concept_name.isupper() and len(concept_name) <= 5:
            return "acronym"
        
        if concept_name[0].isupper() and len(concept_name) > 2:
            return "proper_noun"
        
        return "generic"
    
    def _find_np_match(
        self,
        np_text: str,
        registry: ConceptRegistry,
        active_concepts: List[ConceptRef]
    ) -> Optional[Tuple[ConceptRef, float]]:
        """Find matching concept for definite NP"""
        np_normalized = np_text.lower().strip()
        
        # Check active concepts first
        for concept in active_concepts:
            concept_name = concept.canonical_name.lower()
            
            # Exact match
            if concept_name == np_normalized:
                return concept, 1.0
            
            # Get full concept from registry to check aliases
            concept_obj = registry.get_concept(concept.concept_id)
            if concept_obj:
                # Check aliases
                for alias in concept_obj.aliases:
                    alias_lower = alias.lower().strip()
                    if alias_lower == np_normalized:
                        return concept, 0.95
                    # Partial alias match
                    if np_normalized in alias_lower or alias_lower in np_normalized:
                        return concept, 0.75
            
            # Partial match with canonical name
            if np_normalized in concept_name or concept_name in np_normalized:
                return concept, 0.7
        
        # Check registry directly
        found = registry.get_concept_by_alias(np_text)
        if found:
            return ConceptRef(
                concept_id=found.concept_id,
                canonical_name=found.canonical_name,
                confidence=0.85
            ), 0.85
        
        return None
    
    def _deduplicate(self, coreferences: List[Coreference]) -> List[Coreference]:
        """Remove duplicate coreferences"""
        deduplicated = []
        seen = set()
        
        for coref in coreferences:
            key = (
                coref.antecedent_ref.concept_id if coref.antecedent_ref else "",
                coref.confidence
            )
            if key not in seen:
                seen.add(key)
                deduplicated.append(coref)
        
        return deduplicated
    
    @staticmethod
    def _is_singular(name: str) -> bool:
        return not name.endswith('s') or name.endswith('ss')
    
    @staticmethod
    def _is_plural(name: str) -> bool:
        return name.endswith('s') and not name.endswith('ss')