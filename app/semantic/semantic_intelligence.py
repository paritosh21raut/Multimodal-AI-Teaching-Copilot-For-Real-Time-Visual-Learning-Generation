"""
Semantic Intelligence - Main Orchestrator (Phase 2)

Integrates semantic memory, entity resolution, and concept registry
for incremental cross-chunk understanding.
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
from .entity_resolver import EntityResolver
from .semantic_memory import SemanticMemory


class SemanticIntelligence:
    """
    Main orchestrator for semantic extraction with memory.
    
    Maintains concept identity across chunks through entity resolution
    and semantic memory.
    """
    
    def __init__(self):
        self.evidence_manager = EvidenceManager()
        self.mention_extractor = MentionExtractor()
        self.proposition_extractor = PropositionExtractor()
        self.relation_normalizer = RelationNormalizer()
        self.instructional_detector = InstructionalDetector()
        
        # Phase 2: Memory and entity resolution
        self.entity_resolver = EntityResolver()
        self.semantic_memory = SemanticMemory()
    
    def process(
        self,
        transcript_text: str,
        chunk_id: str = "",
        lecture_id: str = "",
        structural_context: Optional[Dict[str, Any]] = None,
        asr_confidence: Optional[float] = None,
        timestamp: Optional[float] = None,
        topic_path: Optional[str] = None,
        embeddings: Optional[Dict[str, List[float]]] = None
    ) -> SemanticFrame:
        """
        Process a transcript chunk and produce a SemanticFrame.
        
        Args:
            transcript_text: Refined transcript text
            chunk_id: Current chunk identifier
            lecture_id: Current lecture identifier
            structural_context: Context from Lecture Structure Intelligence
            asr_confidence: ASR confidence score
            timestamp: Transcript timestamp
            topic_path: Current topic path from LSI
            embeddings: Optional embeddings for mentions
            
        Returns:
            SemanticFrame with resolved concepts and memory integration
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
        self.semantic_memory.add_evidence(evidence)
        
        # Extract mentions
        mentions = self.mention_extractor.extract_mentions(
            transcript_text,
            evidence=evidence,
            chunk_id=chunk_id
        )
        frame.mentions = mentions
        
        # Resolve mentions to concepts (Phase 2)
        resolved_concepts = []
        concept_ref_map = {}  # mention normalized -> ConceptRef
        
        for mention in mentions:
            # Get embedding for this mention if available
            embedding = None
            if embeddings and mention.normalized_text in embeddings:
                embedding = embeddings[mention.normalized_text]
            
            # Resolve to concept
            resolution = self.entity_resolver.resolve(
                mention=mention,
                embedding=embedding,
                topic_concepts=(
                    self.semantic_memory.topic_memory.get_topic_concept_refs(
                        topic_path, self.semantic_memory.registry
                    )
                    if topic_path else None
                )
            )
            
            # Get the concept
            concept = self.entity_resolver.get_concept(
                resolution.concept_ref.concept_id
            )
            
            if concept:
                resolved_concepts.append(concept)
                concept_ref_map[mention.normalized_text] = resolution.concept_ref
                
                # Add to semantic memory
                if resolution.is_new:
                    self.semantic_memory.add_concept(
                        concept,
                        topic_path=topic_path
                    )
                else:
                    # Activate existing concept
                    self.semantic_memory.active_context.add_concept(
                        concept.concept_id
                    )
        
        frame.concepts = resolved_concepts
        
        # Extract propositions with resolved concepts
        chunk_concepts = {
            name.lower(): ref
            for name, ref in concept_ref_map.items()
        }
        
        propositions = self.proposition_extractor.extract_propositions(
            transcript_text,
            evidence=evidence,
            concepts=chunk_concepts
        )
        
        # Add propositions to memory
        for prop in propositions:
            self.semantic_memory.add_proposition(prop)
        
        frame.propositions = propositions
        
        # Extract relations from propositions
        relations = self._extract_relations(propositions)
        frame.relations = relations
        
        # Detect instructional acts
        concept_refs = [ref for ref in concept_ref_map.values()]
        
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
        if propositions or resolved_concepts:
            frame.extraction_status = ExtractionStatus.COMPLETE
        elif mentions:
            frame.extraction_status = ExtractionStatus.PARTIAL
        else:
            frame.extraction_status = ExtractionStatus.REJECTED
        
        return frame
    
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
    
    def _calculate_frame_confidence(
        self,
        frame: SemanticFrame,
        asr_confidence: Optional[float]
    ) -> Confidence:
        """Calculate multi-dimensional confidence"""
        
        asr_quality = asr_confidence if asr_confidence is not None else 0.8
        
        if frame.propositions:
            extraction_confidence = 0.8
        elif frame.concepts:
            extraction_confidence = 0.6
        elif frame.mentions:
            extraction_confidence = 0.4
        else:
            extraction_confidence = 0.0
        
        grounding_confidence = 0.9 if frame.evidence else 0.0
        entity_resolution_confidence = 0.7 if frame.concepts else 0.0
        
        # Higher confidence if concepts were resolved (not new)
        if frame.concepts:
            resolved_count = sum(
                1 for c in frame.concepts if c.mention_count > 1
            )
            if resolved_count > 0:
                entity_resolution_confidence = 0.9
        
        validation_confidence = 0.5
        consistency_confidence = 0.5
        
        return Confidence(
            asr_quality=asr_quality,
            extraction_confidence=extraction_confidence,
            entity_resolution_confidence=entity_resolution_confidence,
            grounding_confidence=grounding_confidence,
            validation_confidence=validation_confidence,
            consistency_confidence=consistency_confidence
        )
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get semantic memory statistics"""
        return self.semantic_memory.get_statistics()
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts from memory"""
        return self.entity_resolver.get_all_concepts()
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.entity_resolver.get_concept(concept_id)