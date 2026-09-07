"""
Semantic Intelligence - Main Orchestrator

Coordinates evidence extraction, mention extraction, proposition extraction,
relation normalization, and instructional act detection.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import uuid
from datetime import datetime

from .semantic_models import (
    SemanticFrame,
    EvidenceSpan,
    Mention,
    Concept,
    Proposition,
    Relation,
    InstructionalAct,
    ConceptRef,
    Confidence,
    GroundingStatus,
    ExtractionStatus,
    RelationType
)
from .evidence import EvidenceManager
from .mention_extractor import MentionExtractor
from .proposition_extractor import PropositionExtractor
from .relation_normalizer import RelationNormalizer
from .instructional_detector import InstructionalDetector


class SemanticIntelligence:
    """
    Main orchestrator for semantic extraction.
    
    Processes refined transcript chunks and produces SemanticFrames
    containing extracted concepts, propositions, relations, and
    instructional acts.
    """
    
    def __init__(self):
        self.evidence_manager = EvidenceManager()
        self.mention_extractor = MentionExtractor()
        self.proposition_extractor = PropositionExtractor()
        self.relation_normalizer = RelationNormalizer()
        self.instructional_detector = InstructionalDetector()
        
        # Known concepts (name -> ConceptRef)
        self._concept_registry: Dict[str, ConceptRef] = {}
    
    def process(
        self,
        transcript_text: str,
        chunk_id: str = "",
        lecture_id: str = "",
        structural_context: Optional[Dict[str, Any]] = None,
        asr_confidence: Optional[float] = None,
        timestamp: Optional[float] = None
    ) -> SemanticFrame:
        """
        Process a transcript chunk and produce a SemanticFrame.
        
        Args:
            transcript_text: Refined transcript text
            chunk_id: Current chunk identifier
            lecture_id: Current lecture identifier
            structural_context: Context from Lecture Structure Intelligence
            asr_confidence: ASR confidence score from Whisper
            timestamp: Transcript timestamp
            
        Returns:
            SemanticFrame with extracted semantic content
        """
        # Create frame
        frame = SemanticFrame(
            lecture_id=lecture_id,
            chunk_id=chunk_id,
            structural_context=structural_context
        )
        
        if not transcript_text or not transcript_text.strip():
            frame.extraction_status = ExtractionStatus.REJECTED
            frame.frame_confidence = Confidence(
                extraction_confidence=0.0,
                grounding_confidence=0.0
            )
            return frame
        
        # Create evidence span
        evidence = self.evidence_manager.create_evidence(
            chunk_id=chunk_id,
            transcript_id=lecture_id,
            text=transcript_text,
            asr_confidence=asr_confidence,
            timestamp=timestamp
        )
        frame.evidence.append(evidence)
        
        # Extract mentions
        mentions = self.mention_extractor.extract_mentions(
            transcript_text,
            evidence=evidence,
            chunk_id=chunk_id
        )
        frame.mentions = mentions
        
        # Extract concepts from mentions
        concepts = self._extract_concepts(mentions)
        frame.concepts = concepts
        
        # Build concept registry for this chunk
        chunk_concepts = {
            concept.canonical_name.lower(): ConceptRef(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence
            )
            for concept in concepts
        }
        
        # Extract propositions
        propositions = self.proposition_extractor.extract_propositions(
            transcript_text,
            evidence=evidence,
            concepts=chunk_concepts
        )
        frame.propositions = propositions
        
        # Extract relations from propositions
        relations = self._extract_relations(propositions)
        frame.relations = relations
        
        # Detect instructional acts
        concept_refs = [
            ConceptRef(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence
            )
            for concept in concepts
        ]
        
        instructional_acts = self.instructional_detector.detect(
            transcript_text,
            evidence=evidence,
            concept_refs=concept_refs
        )
        frame.instructional_acts = instructional_acts
        
        # Calculate frame confidence
        frame.frame_confidence = self._calculate_frame_confidence(
            frame,
            asr_confidence
        )
        
        # Set extraction status
        if propositions or concepts:
            frame.extraction_status = ExtractionStatus.COMPLETE
        else:
            frame.extraction_status = ExtractionStatus.PARTIAL
        
        return frame
    
    def _extract_concepts(self, mentions: List[Mention]) -> List[Concept]:
        """Extract concepts from mentions"""
        concepts = []
        seen_names = set()
        
        for mention in mentions:
            name = mention.surface_text
            
            if name.lower() in seen_names:
                continue
            
            seen_names.add(name.lower())
            
            concept = Concept(
                canonical_name=name,
                aliases=[mention.normalized_text] if mention.normalized_text != name.lower() else [],
                first_mention=mention.evidence,
                mention_count=1,
                confidence=mention.confidence,
                concept_type=self._determine_concept_type(name)
            )
            
            concepts.append(concept)
            
            # Register in concept registry
            self._concept_registry[name.lower()] = ConceptRef(
                concept_id=concept.concept_id,
                canonical_name=concept.canonical_name,
                confidence=concept.confidence
            )
        
        return concepts
    
    def _extract_relations(self, propositions: List[Proposition]) -> List[Relation]:
        """Extract relations from propositions"""
        relations = []
        
        for prop in propositions:
            if prop.subject and prop.object and prop.predicate:
                relation = Relation(
                    source=prop.subject,
                    target=prop.object,
                    relation_type=prop.predicate,
                    source_proposition_id=prop.proposition_id,
                    confidence=prop.confidence,
                    evidence_ids=prop.evidence_ids
                )
                relations.append(relation)
        
        return relations
    
    def _determine_concept_type(self, name: str) -> str:
        """Determine concept type based on name patterns"""
        if name.isupper() and len(name) <= 5:
            return "entity"  # Acronyms like TCP, CPU
        elif " " in name:
            return "abstraction"  # Multi-word concepts
        elif name[0].isupper():
            return "entity"  # Proper nouns
        else:
            return "abstraction"
    
    def _calculate_frame_confidence(
        self,
        frame: SemanticFrame,
        asr_confidence: Optional[float]
    ) -> Confidence:
        """Calculate multi-dimensional confidence for frame"""
        
        # ASR quality
        asr_quality = asr_confidence if asr_confidence is not None else 0.8
        
        # Extraction confidence based on what was extracted
        if frame.propositions:
            extraction_confidence = 0.8
        elif frame.concepts:
            extraction_confidence = 0.6
        elif frame.mentions:
            extraction_confidence = 0.4
        else:
            extraction_confidence = 0.0
        
        # Grounding confidence
        if frame.evidence:
            grounding_confidence = 0.9
        else:
            grounding_confidence = 0.0
        
        # Entity resolution confidence (basic for now)
        entity_resolution_confidence = 0.7 if frame.concepts else 0.0
        
        # Validation confidence (no validation yet in Phase 1)
        validation_confidence = 0.5
        
        # Consistency confidence (no consistency check yet)
        consistency_confidence = 0.5
        
        return Confidence(
            asr_quality=asr_quality,
            extraction_confidence=extraction_confidence,
            entity_resolution_confidence=entity_resolution_confidence,
            grounding_confidence=grounding_confidence,
            validation_confidence=validation_confidence,
            consistency_confidence=consistency_confidence
        )
    
    def get_registered_concepts(self) -> Dict[str, ConceptRef]:
        """Get all registered concepts"""
        return dict(self._concept_registry)