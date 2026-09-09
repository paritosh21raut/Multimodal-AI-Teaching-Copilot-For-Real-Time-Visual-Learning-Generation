"""
Proposition Extraction (PHASE 1 FIXED)

Fixes:
- Distinguishes IS_A (category) from HAS_ATTRIBUTE (property)
- Splits combined "is a [adjective] [noun]" into TWO propositions
- Detects "while/whereas" contrast
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
    """Extracts propositions from transcript text"""
    
    # Relation patterns
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
            r'\bis\s+(?!a|an|the)\s*',  # "is" without article → attribute
        ],
    }
    
    # Known category indicators (nouns that represent types/categories)
    CATEGORY_INDICATORS = {
        "protocol", "device", "system", "process", "algorithm",
        "network", "model", "architecture", "language", "method",
        "technique", "mechanism", "layer", "interface", "component",
    }
    
    # Known property/attribute indicators (adjectives/descriptive words)
    PROPERTY_INDICATORS = {
        "connectionless", "connection-oriented", "reliable", "unreliable",
        "fast", "slow", "secure", "insecure", "volatile", "non-volatile",
        "synchronous", "asynchronous", "deterministic", "probabilistic",
        "static", "dynamic", "analog", "digital",
    }
    
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
        """Extract propositions from text"""
        if not text or not text.strip():
            return []
        
        propositions = []
        
        # Split into clauses (handle "while", "whereas")
        clauses = self._split_clauses(text)
        
        for clause in clauses:
            clause_props = self._extract_from_clause(clause, evidence, concepts)
            propositions.extend(clause_props)
        
        # Detect contrast between clauses
        contrast_props = self._detect_contrast(clauses, evidence, concepts)
        propositions.extend(contrast_props)
        
        return propositions
    
    def _split_clauses(self, text: str) -> List[str]:
        """Split text into clauses by contrast conjunctions"""
        # Split on "while", "whereas", "but", "however"
        split_pattern = r'(?:\bwhile\b|\bwhereas\b|\bbut\b|\bhowever\b)'
        parts = re.split(split_pattern, text, flags=re.IGNORECASE)
        return [p.strip() for p in parts if p.strip()]
    
    def _extract_from_clause(
        self,
        clause: str,
        evidence: Optional[EvidenceSpan],
        concepts: Optional[Dict[str, ConceptRef]]
    ) -> List[Proposition]:
        """Extract propositions from a single clause"""
        propositions = []
        
        subject = self._extract_subject(clause)
        if not subject:
            return propositions
        
        # Check IS_A with article
        for pattern in self._compiled_relations.get(RelationType.IS_A, []):
            match = pattern.search(clause)
            if match:
                obj_phrase = self._extract_object(clause, match)
                if obj_phrase:
                    # Check if combined type + property
                    split_result = self._split_object_phrase(obj_phrase)
                    
                    if split_result:
                        adjective, noun = split_result
                        
                        # Create IS_A with just the noun
                        if noun:
                            prop_is_a = self._create_proposition(
                                subject=subject,
                                predicate=RelationType.IS_A,
                                object=noun,
                                evidence=evidence,
                                concepts=concepts,
                            )
                            propositions.append(prop_is_a)
                        
                        # Create HAS_ATTRIBUTE with the adjective
                        if adjective:
                            prop_attr = self._create_proposition(
                                subject=subject,
                                predicate=RelationType.HAS_ATTRIBUTE,
                                object=adjective,
                                evidence=evidence,
                                concepts=concepts,
                            )
                            propositions.append(prop_attr)
                    else:
                        # Just a category
                        prop = self._create_proposition(
                            subject=subject,
                            predicate=RelationType.IS_A,
                            object=obj_phrase,
                            evidence=evidence,
                            concepts=concepts,
                        )
                        propositions.append(prop)
                break
        
        # Check HAS_ATTRIBUTE (is without article)
        for pattern in self._compiled_relations.get(RelationType.HAS_ATTRIBUTE, []):
            match = pattern.search(clause)
            if match:
                obj_phrase = self._extract_object(clause, match)
                if obj_phrase and self._is_property(obj_phrase):
                    prop = self._create_proposition(
                        subject=subject,
                        predicate=RelationType.HAS_ATTRIBUTE,
                        object=obj_phrase,
                        evidence=evidence,
                        concepts=concepts,
                    )
                    propositions.append(prop)
                break
        
        # Check other relation types
        for rel_type, patterns in self._compiled_relations.items():
            if rel_type in [RelationType.IS_A, RelationType.HAS_ATTRIBUTE]:
                continue  # Already handled
            
            for pattern in patterns:
                match = pattern.search(clause)
                if match:
                    obj = self._extract_object(clause, match)
                    if obj:
                        prop = self._create_proposition(
                            subject=subject,
                            predicate=rel_type,
                            object=obj,
                            evidence=evidence,
                            concepts=concepts,
                        )
                        propositions.append(prop)
                    break
        
        return propositions
    
    def _detect_contrast(
        self,
        clauses: List[str],
        evidence: Optional[EvidenceSpan],
        concepts: Optional[Dict[str, ConceptRef]]
    ) -> List[Proposition]:
        """Detect contrast between two clauses"""
        if len(clauses) < 2:
            return []
        
        propositions = []
        
        # Extract subjects from each clause
        subjects = []
        for clause in clauses:
            subject = self._extract_subject(clause)
            if subject and subject not in subjects:
                subjects.append(subject)
        
        # If two different subjects found, create CONTRASTS_WITH
        if len(subjects) >= 2:
            # Create contrast proposition
            source_ref = ConceptRef(
                concept_id="",
                canonical_name=subjects[0],
                confidence=0.7,
            )
            target_ref = ConceptRef(
                concept_id="",
                canonical_name=subjects[1],
                confidence=0.7,
            )
            
            prop = Proposition(
                subject=source_ref,
                predicate=RelationType.CONTRASTS_WITH,
                object=target_ref,
                evidence_ids=[evidence.evidence_id] if evidence else [],
                confidence=0.7,
                grounding_status=GroundingStatus.EXPLICIT if evidence else GroundingStatus.UNSUPPORTED,
                extraction_status=ExtractionStatus.COMPLETE,
            )
            propositions.append(prop)
        
        return propositions
    
    def _split_object_phrase(self, phrase: str) -> Optional[Tuple[str, str]]:
        """
        Split object phrase into (adjective, noun).
        
        Returns None if no split needed.
        """
        words = phrase.split()
        
        if len(words) < 2:
            return None
        
        # Check if first word(s) are property indicators
        for i in range(1, len(words)):
            candidate_adj = " ".join(words[:i])
            candidate_noun = " ".join(words[i:])
            
            if (
                candidate_adj in self.PROPERTY_INDICATORS
                or candidate_adj.lower() in self.PROPERTY_INDICATORS
            ):
                # Check noun is a category indicator
                if candidate_noun.split()[-1].lower() in self.CATEGORY_INDICATORS:
                    return (candidate_adj, candidate_noun)
        
        # Also check hyphenated forms
        for word in words:
            if word.lower() in self.PROPERTY_INDICATORS:
                idx = words.index(word)
                if idx + 1 < len(words):
                    adjective = word
                    noun = " ".join(words[idx+1:])
                    return (adjective, noun)
        
        return None
    
    def _is_property(self, phrase: str) -> bool:
        """Check if phrase is a property/attribute"""
        phrase_lower = phrase.lower().strip()
        
        if phrase_lower in self.PROPERTY_INDICATORS:
            return True
        
        # Single descriptive word
        if len(phrase.split()) == 1:
            return True
        
        return False
    
    def _extract_subject(self, clause: str) -> Optional[str]:
        """Extract subject from clause"""
        words = clause.split()
        for i, word in enumerate(words):
            if word.lower() in {"is", "are", "was", "were", "provides", "uses",
                               "requires", "causes", "contains", "has", "have"}:
                if i > 0:
                    return " ".join(words[:i]).strip('.,;:!?()')
                break
        return None
    
    def _extract_object(self, clause: str, match) -> Optional[str]:
        """Extract object after verb match"""
        after_verb = clause[match.end():].strip()
        
        if not after_verb:
            return None
        
        after_verb = re.sub(r'^(?:a|an|the)\s+', '', after_verb, flags=re.IGNORECASE)
        
        words = after_verb.split()
        object_words = []
        
        for word in words:
            clean_word = word.strip('.,;:!?()')
            if clean_word.lower() in {"and", "or", "but", "for", "with", "by", "using"}:
                break
            object_words.append(clean_word)
            if len(object_words) >= 5:
                break
        
        if not object_words:
            return None
        
        return " ".join(object_words).strip('.,;:!?()')
    
    def _create_proposition(
        self,
        subject: str,
        predicate: RelationType,
        object: str,
        evidence: Optional[EvidenceSpan],
        concepts: Optional[Dict[str, ConceptRef]],
    ) -> Optional[Proposition]:
        """Create proposition from extracted components"""
        subject_clean = subject.strip()
        object_clean = object.strip()
        
        if not subject_clean or not object_clean:
            return None
        
        subject_ref = ConceptRef(
            concept_id="",
            canonical_name=subject_clean,
            confidence=0.7,
        )
        object_ref = ConceptRef(
            concept_id="",
            canonical_name=object_clean,
            confidence=0.7,
        )
        
        return Proposition(
            subject=subject_ref,
            predicate=predicate,
            object=object_ref,
            evidence_ids=[evidence.evidence_id] if evidence else [],
            confidence=0.7,
            grounding_status=GroundingStatus.EXPLICIT if evidence else GroundingStatus.UNSUPPORTED,
            extraction_status=ExtractionStatus.COMPLETE,
        )