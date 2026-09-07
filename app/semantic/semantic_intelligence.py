"""
Semantic Intelligence - Main Orchestrator (Phase 5)

Integrates validation, confidence calculation, and contradiction detection.
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
    UnresolvedReference,
    PropositionLifecycle
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
from .validator import SemanticValidator
from .confidence import ConfidenceCalculator
from .contradiction_detector import ContradictionDetector


class SemanticIntelligence:
    """
    Main orchestrator with validation, confidence, and contradiction detection.
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
        
        # Phase 5
        self.validator = SemanticValidator()
        self.confidence_calculator = ConfidenceCalculator()
        self.contradiction_detector = ContradictionDetector()
    
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
        resolve_coreferences: bool = True,
        validate: bool = True,
        detect_contradictions: bool = True
    ) -> SemanticFrame:
        """
        Process a transcript chunk and produce a validated SemanticFrame.
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
        
        # Generate embeddings
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
        
        # Phase 4: Coreference resolution
        if resolve_coreferences:
            coreferences = self.coreference_resolver.resolve_all(
                transcript_text,
                self.semantic_memory.registry,
                active_refs,
                evidence
            )
            frame.coreferences = coreferences
            
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
        
        # Phase 5: Contradiction detection
        if detect_contradictions and propositions:
            existing_props = list(self.semantic_memory._propositions.values())
            
            for prop in propositions:
                contradiction = self.contradiction_detector.detect_contradiction(
                    prop,
                    existing_props
                )
                
                if contradiction:
                    self.contradiction_detector.handle_contradiction(
                        contradiction,
                        self.semantic_memory._propositions
                    )
        
        # Add propositions to memory
        for prop in propositions:
            self.semantic_memory.add_proposition(prop)
        
        frame.propositions = propositions
        
        # Extract relations
        relations = self._extract_relations(propositions)
        frame.relations = relations
        
        # Detect instructional acts
        concept_refs = [ref for ref in concept_ref_map.values()]
        
        instructional_acts = self.instructional_detector.detect(
            transcript_text,
            evidence=evidence,
            concept_refs=concept_refs,
            active_concepts=active_refs
        )
        frame.instructional_acts = instructional_acts
        
        # Phase 5: Validation
        validation_report = None
        if validate:
            frame_valid, validation_confidence, validation_report = (
                self.validator.validate_frame(
                    resolved_concepts,
                    propositions,
                    frame.evidence
                )
            )
            
            if not frame_valid:
                frame.extraction_status = ExtractionStatus.PARTIAL
        
        # Calculate confidence
        frame.frame_confidence = self.confidence_calculator.calculate_frame_confidence(
            resolved_concepts,
            propositions,
            frame.evidence,
            asr_confidence=asr_confidence,
            validation_report=validation_report
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
    
    def get_memory_statistics(self) -> Dict[str, Any]:
        """Get semantic memory statistics"""
        stats = self.semantic_memory.get_statistics()
        stats.update(self.embedding_index.get_stats())
        stats["contradictions"] = len(self.contradiction_detector.get_contradictions())
        return stats
    
    def get_all_concepts(self) -> List[Concept]:
        """Get all concepts from memory"""
        return self.entity_resolver.get_all_concepts()
    
    def get_concept(self, concept_id: str) -> Optional[Concept]:
        """Get concept by ID"""
        return self.entity_resolver.get_concept(concept_id)
    
    def get_contradictions(self) -> List[Any]:
        """Get all detected contradictions"""
        return self.contradiction_detector.get_contradictions()
    
    def get_active_propositions(self) -> List[Proposition]:
        """Get active propositions only"""
        return self.contradiction_detector.get_active_propositions(
            self.semantic_memory._propositions
        )