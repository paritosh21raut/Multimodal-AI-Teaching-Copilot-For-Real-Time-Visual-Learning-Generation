"""
Semantic Intelligence - Main Orchestrator (Phase 4)

Integrates coreference resolution and enhanced instructional act detection.
"""

from __future__ import annotations

from typing import Optional, Dict, Any, List
import uuid
import numpy as np
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
    RelationType,
    Coreference,
    UnresolvedReference
)
from .evidence import EvidenceManager
from .mention_extractor import MentionExtractor
from .proposition_extractor import PropositionExtractor
from .relation_normalizer import RelationNormalizer
from .instructional_detector import InstructionalDetector
from .entity_resolver import EntityResolver
from .semantic_memory import SemanticMemory
from .embedding_index import EmbeddingIndex
from .coreference_resolver import CoreferenceResolver


class SemanticIntelligence:
    """
    Main orchestrator with coreference resolution and instructional acts.
    """
    
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.evidence_manager = EvidenceManager()
        self.mention_extractor = MentionExtractor()
        self.proposition_extractor = PropositionExtractor()
        self.relation_normalizer = RelationNormalizer()
        self.instructional_detector = InstructionalDetector()
        
        # Phase 3
        self.embedding_index = EmbeddingIndex()
        self.entity_resolver = EntityResolver(self.embedding_index)
        self.semantic_memory = SemanticMemory()
        
        # Phase 4
        self.coreference_resolver = CoreferenceResolver()
    
    def process(
        self,
        transcript_text: str,
        chunk_id: str = "",
        lecture_id: str = "",
        structural_context: Optional[Dict[str, Any]] = None,
        asr_confidence: Optional[float] = None,
        timestamp: Optional[float] = None,
        topic_path: Optional[str] = None,
        generate_embeddings: bool = True,
        resolve_coreferences: bool = True
    ) -> SemanticFrame:
        """
        Process a transcript chunk and produce a SemanticFrame.
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
        
        # Generate embeddings for mentions
        mention_embeddings = {}
        if generate_embeddings and mentions:
            mention_texts = [
                m.surface_text for m in mentions
                if m.surface_text.strip()
            ]
            
            if mention_texts:
                embeddings = self.embedding_index.batch_encode(mention_texts)
                
                for mention, embedding in zip(mentions, embeddings):
                    if embedding is not None:
                        mention_embeddings[mention.normalized_text] = embedding
        
        # Get active concepts
        active_refs = self.semantic_memory.active_context.get_concept_refs(
            self.semantic_memory.registry
        )
        
        # Get topic concepts
        topic_refs = None
        if topic_path:
            topic_refs = self.semantic_memory.topic_memory.get_topic_concept_refs(
                topic_path,
                self.semantic_memory.registry
            )
        
        # Resolve mentions to concepts
        resolved_concepts = []
        concept_ref_map = {}
        
        for mention in mentions:
            embedding = mention_embeddings.get(mention.normalized_text)
            
            resolution = self.entity_resolver.resolve(
                mention=mention,
                embedding=embedding,
                active_concepts=active_refs,
                topic_concepts=topic_refs
            )
            
            concept = self.entity_resolver.get_concept(
                resolution.concept_ref.concept_id
            )
            
            if concept:
                resolved_concepts.append(concept)
                concept_ref_map[mention.normalized_text] = resolution.concept_ref
                
                if resolution.is_new:
                    self.semantic_memory.add_concept(
                        concept,
                        topic_path=topic_path
                    )
                    
                    if embedding is not None:
                        self.embedding_index.add_concept_embedding(
                            concept.concept_id,
                            embedding
                        )
                else:
                    self.semantic_memory.active_context.add_concept(
                        concept.concept_id
                    )
        
        frame.concepts = resolved_concepts
        
        # Phase 4: Resolve coreferences
        if resolve_coreferences:
            coreferences = self.coreference_resolver.resolve_all(
                transcript_text,
                self.semantic_memory.registry,
                active_refs,
                evidence
            )
            frame.coreferences = coreferences
            
            # Track unresolved references
            unresolved = self._find_unresolved_references(
                transcript_text,
                active_refs
            )
            frame.unresolved_references = unresolved
        
        # Extract propositions
        chunk_concepts = {
            name.lower(): ref
            for name, ref in concept_ref_map.items()
        }
        
        propositions = self.proposition_extractor.extract_propositions(
            transcript_text,
            evidence=evidence,
            concepts=chunk_concepts
        )
        
        for prop in propositions:
            self.semantic_memory.add_proposition(prop)
        
        frame.propositions = propositions
        
        # Extract relations
        relations = self._extract_relations(propositions)
        frame.relations = relations
        
        # Detect instructional acts with concept linking
        concept_refs = [ref for ref in concept_ref_map.values()]
        
        instructional_acts = self.instructional_detector.detect(
            transcript_text,
            evidence=evidence,
            concept_refs=concept_refs,
            active_concepts=active_refs
        )
        frame.instructional_acts = instructional_acts
        
        # Calculate confidence
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
    
    def _find_unresolved_references(
        self,
        text: str,
        active_concepts: List[ConceptRef]
    ) -> List[UnresolvedReference]:
        """Find references that couldn't be resolved"""
        unresolved = []
        
        # Check for pronouns without clear antecedents
        pronouns = ["it", "this", "that", "these", "those", "they", "them"]
        
        words = text.lower().split()
        for word in words:
            clean_word = word.strip('.,;:!?()')
            
            if clean_word in pronouns and len(active_concepts) == 0:
                unresolved.append(UnresolvedReference(
                    mention_text=clean_word,
                    reason="no_active_concepts"
                ))
        
        return unresolved
    
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
        
        if frame.concepts:
            resolved_count = sum(
                1 for c in frame.concepts if c.mention_count > 1
            )
            if resolved_count > 0:
                entity_resolution_confidence = 0.9
        
        validation_confidence = 0.5
        consistency_confidence = 0.5
        
        # Boost consistency if coreferences resolved
        if frame.coreferences:
            consistency_confidence = 0.7
        
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
        stats = self.semantic_memory.get_statistics()
        stats.update(self.embedding_index.get_stats())
        return stats
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts from memory"""
        return self.entity_resolver.get_all_concepts()
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.entity_resolver.get_concept(concept_id)