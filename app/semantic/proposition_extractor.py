"""
Proposition Extraction

Extracts atomic semantic propositions from transcript chunks using
pattern matching and dependency-like heuristics. No heavy dependencies.
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any, Tuple
import re

from .semantic_models import (
    Proposition,
    EvidenceSpan,
    ConceptRef,
    RelationType,
    GroundingStatus,
    ExtractionStatus
)


class PropositionExtractor:
    """Extracts propositions from transcript text using deterministic patterns"""
    
    # Verb patterns to relation types
    RELATION_PATTERNS = {
        RelationType.IS_A: [
            r'\bis\s+(?:a|an|the)\s+',
            r'\bare\s+(?:a|an|the)\s+',
            r'\bwas\s+(?:a|an|the)\s+',
            r'\bwere\s+(?:a|an|the)\s+',
        ],
        RelationType.DEFINED_AS: [
            r'\bis\s+defined\s+as\s+',
            r'\brefers\s+to\s+',
            r'\bmeans\s+',
            r'\bis\s+called\s+',
        ],
        RelationType.PROVIDES: [
            r'\bprovides?\s+',
            r'\boffers?\s+',
            r'\bdelivers?\s+',
            r'\benables?\s+',
            r'\ballows?\s+',
        ],
        RelationType.USES: [
            r'\buses?\s+',
            r'\busing\s+',
            r'\butilizes?\s+',
            r'\bemploys?\s+',
        ],
        RelationType.REQUIRES: [
            r'\brequires?\s+',
            r'\bneeds?\s+',
            r'\bdepends?\s+on\s+',
        ],
        RelationType.CAUSES: [
            r'\bcauses?\s+',
            r'\bresults?\s+in\s+',
            r'\bleads?\s+to\s+',
        ],
        RelationType.HAS_PART: [
            r'\bcontains?\s+',
            r'\bincludes?\s+',
            r'\bconsists?\s+of\s+',
        ],
        RelationType.HAS_ATTRIBUTE: [
            r'\bhas\s+(?:a|an|the)?\s*\w+\s+',
            r'\bhave\s+(?:a|an|the)?\s*\w+\s+',
        ],
    }
    
    # Patterns for subject extraction
    SUBJECT_PATTERNS = [
        r'^([A-Za-z][A-Za-z\s-]{1,50}?)\s+(?:is|are|was|were|provides|uses|'
        r'requires|causes|contains|has|have|enables|allows|delivers|offers)\b',
    ]
    
    def __init__(self):
        self._compiled_relations = {}
        for rel_type, patterns in self.RELATION_PATTERNS.items():
            self._compiled_relations[rel_type] = [
                re.compile(pattern, re.IGNORECASE) for pattern in patterns
            ]
    
    def extract_propositions(
        self,
        text: str,
        evidence: Optional[EvidenceSpan] = None,
        concepts: Optional[Dict[str, ConceptRef]] = None
    ) -> List[Proposition]:
        """
        Extract propositions from text.
        
        Args:
            text: Transcript text
            evidence: Evidence span for grounding
            concepts: Known concepts (name -> ConceptRef)
            
        Returns:
            List of Proposition objects
        """
        if not text or not text.strip():
            return []
        
        propositions = []
        
        # Split into sentences
        sentences = self._split_sentences(text)
        
        for sentence in sentences:
            sentence_props = self._extract_from_sentence(
                sentence, evidence, concepts
            )
            propositions.extend(sentence_props)
        
        return propositions
    
    def _split_sentences(self, text: str) -> List[str]:
        """Split text into sentences"""
        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        
        # Filter empty sentences
        return [s.strip() for s in sentences if s.strip()]
    
    def _extract_from_sentence(
        self,
        sentence: str,
        evidence: Optional[EvidenceSpan],
        concepts: Optional[Dict[str, ConceptRef]]
    ) -> List[Proposition]:
        """Extract propositions from a single sentence"""
        propositions = []
        
        # Try to extract subject and object
        subject = self._extract_subject(sentence)
        
        if not subject:
            return propositions
        
        # Find relation type and object
        for rel_type, patterns in self._compiled_relations.items():
            for pattern in patterns:
                match = pattern.search(sentence)
                
                if match:
                    obj = self._extract_object(sentence, match)
                    
                    if obj:
                        proposition = self._create_proposition(
                            subject=subject,
                            predicate=rel_type,
                            object=obj,
                            evidence=evidence,
                            concepts=concepts
                        )
                        
                        if proposition:
                            propositions.append(proposition)
                    
                    break  # One relation per sentence for now
        
        return propositions
    
    def _extract_subject(self, sentence: str) -> Optional[str]:
        """Extract subject from sentence"""
        for pattern in self.SUBJECT_PATTERNS:
            match = re.match(pattern, sentence, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        # Fallback: first noun phrase before verb
        words = sentence.split()
        for i, word in enumerate(words):
            if word.lower() in {"is", "are", "was", "were", "provides", "uses",
                               "requires", "causes", "contains", "has", "have"}:
                if i > 0:
                    return " ".join(words[:i]).strip('.,;:!?()')
                break
        
        return None
    
    def _extract_object(self, sentence: str, match) -> Optional[str]:
        """Extract object after the verb"""
        # Get text after the verb match
        after_verb = sentence[match.end():].strip()
        
        if not after_verb:
            return None
        
        # Remove leading articles
        after_verb = re.sub(r'^(?:a|an|the)\s+', '', after_verb, flags=re.IGNORECASE)
        
        # Take first few words as object
        words = after_verb.split()
        
        # Stop at conjunctions or punctuation
        object_words = []
        for word in words:
            clean_word = word.strip('.,;:!?()')
            
            if clean_word.lower() in {"and", "or", "but", "for", "with", "by", 
                                       "using", "through", "via", "to"}:
                break
            
            object_words.append(clean_word)
            
            if len(object_words) >= 5:
                break
        
        if not object_words:
            return None
        
        obj = " ".join(object_words).strip('.,;:!?()')
        
        return obj if len(obj) > 1 else None
    
    def _create_proposition(
        self,
        subject: str,
        predicate: RelationType,
        object: str,
        evidence: Optional[EvidenceSpan],
        concepts: Optional[Dict[str, ConceptRef]]
    ) -> Optional[Proposition]:
        """Create a Proposition object"""
        subject_clean = self._clean_text(subject)
        object_clean = self._clean_text(object)
        
        if not subject_clean or not object_clean:
            return None
        
        # Create concept refs
        subject_ref = None
        object_ref = None
        
        if concepts:
            subject_ref = concepts.get(subject_clean.lower())
            object_ref = concepts.get(object_clean.lower())
        
        if not subject_ref:
            subject_ref = ConceptRef(
                concept_id="",
                canonical_name=subject_clean,
                confidence=0.6
            )
        
        if not object_ref:
            object_ref = ConceptRef(
                concept_id="",
                canonical_name=object_clean,
                confidence=0.6
            )
        
        return Proposition(
            subject=subject_ref,
            predicate=predicate,
            object=object_ref,
            evidence_ids=[evidence.evidence_id] if evidence else [],
            confidence=0.6,
            grounding_status=GroundingStatus.EXPLICIT if evidence else GroundingStatus.UNSUPPORTED,
            extraction_status=ExtractionStatus.COMPLETE
        )
    
    def _clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'^(?:the|a|an)\s+', '', text, flags=re.IGNORECASE)
        return text.strip('.,;:!?()')