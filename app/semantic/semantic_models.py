"""
Semantic Intelligence - Core Data Models

Evidence-grounded semantic structures for lecture understanding.
No external dependencies beyond standard library.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple, Any
import uuid
import hashlib


class GroundingStatus(str, Enum):
    EXPLICIT = "explicit"
    SUPPORTED = "supported"
    INFERRED = "inferred"
    UNSUPPORTED = "unsupported"


class ExtractionStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    UNCERTAIN = "uncertain"
    REJECTED = "rejected"


class PropositionLifecycle(str, Enum):
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CONTRADICTED = "contradicted"
    QUALIFIED = "qualified"
    RETRACTED = "retracted"


class RelationType(str, Enum):
    IS_A = "IS_A"
    INSTANCE_OF = "INSTANCE_OF"
    PART_OF = "PART_OF"
    HAS_PART = "HAS_PART"
    HAS_ATTRIBUTE = "HAS_ATTRIBUTE"
    DEFINED_AS = "DEFINED_AS"
    USED_FOR = "USED_FOR"
    PROVIDES = "PROVIDES"
    REQUIRES = "REQUIRES"
    DEPENDS_ON = "DEPENDS_ON"
    ENABLES = "ENABLES"
    CAUSES = "CAUSES"
    RESULTS_IN = "RESULTS_IN"
    INPUT_TO = "INPUT_TO"
    OUTPUT_OF = "OUTPUT_OF"
    USES = "USES"
    CONNECTS_TO = "CONNECTS_TO"
    MEASURED_BY = "MEASURED_BY"
    HAS_VALUE = "HAS_VALUE"
    PRECEDES = "PRECEDES"
    FOLLOWS = "FOLLOWS"
    CONTRASTS_WITH = "CONTRASTS_WITH"
    SIMILAR_TO = "SIMILAR_TO"
    EXAMPLE_OF = "EXAMPLE_OF"
    CONDITION_FOR = "CONDITION_FOR"
    LIMITED_BY = "LIMITED_BY"


class InstructionalActType(str, Enum):
    DEFINITION = "DEFINITION"
    EXPLANATION = "EXPLANATION"
    MECHANISM = "MECHANISM"
    PROCESS = "PROCESS"
    EXAMPLE = "EXAMPLE"
    COUNTEREXAMPLE = "COUNTEREXAMPLE"
    COMPARISON = "COMPARISON"
    CONTRAST = "CONTRAST"
    ANALOGY = "ANALOGY"
    WARNING = "WARNING"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    DERIVATION = "DERIVATION"
    PROOF = "PROOF"
    OBSERVATION = "OBSERVATION"
    RECAP = "RECAP"
    CONCLUSION = "CONCLUSION"


class SemanticEventType(str, Enum):
    CONCEPT_CREATED = "CONCEPT_CREATED"
    CONCEPT_MERGED = "CONCEPT_MERGED"
    MENTION_LINKED = "MENTION_LINKED"
    PROPOSITION_ADDED = "PROPOSITION_ADDED"
    PROPOSITION_CONFIRMED = "PROPOSITION_CONFIRMED"
    PROPOSITION_REJECTED = "PROPOSITION_REJECTED"
    PROPOSITION_SUPERSEDED = "PROPOSITION_SUPERSEDED"
    CONTRADICTION_DETECTED = "CONTRADICTION_DETECTED"
    COREFERENCE_RESOLVED = "COREFERENCE_RESOLVED"
    INSTRUCTIONAL_ACT_ADDED = "INSTRUCTIONAL_ACT_ADDED"


@dataclass
class EvidenceSpan:
    """A specific span in the authoritative transcript"""
    evidence_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    chunk_id: str = ""
    transcript_id: str = ""
    sentence_id: str = ""
    start_char: int = 0
    end_char: int = 0
    text: str = ""
    timestamp: Optional[float] = None
    asr_confidence: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "chunk_id": self.chunk_id,
            "transcript_id": self.transcript_id,
            "sentence_id": self.sentence_id,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "text": self.text,
            "timestamp": self.timestamp,
            "asr_confidence": self.asr_confidence
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvidenceSpan':
        return cls(**data)


@dataclass
class Mention:
    """A literal mention of a concept in the transcript"""
    mention_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    surface_text: str = ""
    normalized_text: str = ""
    evidence: Optional[EvidenceSpan] = None
    start_char: int = 0
    end_char: int = 0
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mention_id": self.mention_id,
            "surface_text": self.surface_text,
            "normalized_text": self.normalized_text,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "start_char": self.start_char,
            "end_char": self.end_char,
            "confidence": self.confidence
        }


@dataclass
class ConceptRef:
    """Reference to a concept in semantic memory"""
    concept_id: str
    canonical_name: str
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "confidence": self.confidence
        }


@dataclass
class Concept:
    """A stable concept in lecture semantic memory"""
    concept_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    canonical_name: str = ""
    aliases: List[str] = field(default_factory=list)
    anchor_embedding: Optional[List[float]] = None
    centroid_embedding: Optional[List[float]] = None
    first_mention: Optional[EvidenceSpan] = None
    mention_count: int = 0
    confidence: float = 0.0
    concept_type: str = "entity"
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "concept_id": self.concept_id,
            "canonical_name": self.canonical_name,
            "aliases": self.aliases,
            "anchor_embedding": self.anchor_embedding,
            "centroid_embedding": self.centroid_embedding,
            "first_mention": self.first_mention.to_dict() if self.first_mention else None,
            "mention_count": self.mention_count,
            "confidence": self.confidence,
            "concept_type": self.concept_type,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Proposition:
    """An atomic semantic proposition extracted from transcript"""
    proposition_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    subject: Optional[ConceptRef] = None
    predicate: Optional[RelationType] = None
    object: Optional[ConceptRef] = None
    qualifiers: Dict[str, str] = field(default_factory=dict)
    polarity: bool = True
    modality: str = "fact"
    temporal_scope: Optional[str] = None
    quantities: Dict[str, float] = field(default_factory=dict)
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0
    grounding_status: GroundingStatus = GroundingStatus.UNSUPPORTED
    extraction_status: ExtractionStatus = ExtractionStatus.UNCERTAIN
    lifecycle: PropositionLifecycle = PropositionLifecycle.ACTIVE
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "proposition_id": self.proposition_id,
            "subject": self.subject.to_dict() if self.subject else None,
            "predicate": self.predicate.value if self.predicate else None,
            "object": self.object.to_dict() if self.object else None,
            "qualifiers": self.qualifiers,
            "polarity": self.polarity,
            "modality": self.modality,
            "temporal_scope": self.temporal_scope,
            "quantities": self.quantities,
            "evidence_ids": self.evidence_ids,
            "confidence": self.confidence,
            "grounding_status": self.grounding_status.value,
            "extraction_status": self.extraction_status.value,
            "lifecycle": self.lifecycle.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class Relation:
    """A typed relation between concepts"""
    relation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source: Optional[ConceptRef] = None
    target: Optional[ConceptRef] = None
    relation_type: Optional[RelationType] = None
    source_proposition_id: Optional[str] = None
    confidence: float = 0.0
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relation_id": self.relation_id,
            "source": self.source.to_dict() if self.source else None,
            "target": self.target.to_dict() if self.target else None,
            "relation_type": self.relation_type.value if self.relation_type else None,
            "source_proposition_id": self.source_proposition_id,
            "confidence": self.confidence,
            "evidence_ids": self.evidence_ids
        }


@dataclass
class InstructionalAct:
    """A pedagogical action detected in lecture"""
    act_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    act_type: Optional[InstructionalActType] = None
    concept_refs: List[ConceptRef] = field(default_factory=list)
    proposition_refs: List[str] = field(default_factory=list)
    evidence_ids: List[str] = field(default_factory=list)
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "act_id": self.act_id,
            "act_type": self.act_type.value if self.act_type else None,
            "concept_refs": [c.to_dict() for c in self.concept_refs],
            "proposition_refs": self.proposition_refs,
            "evidence_ids": self.evidence_ids,
            "confidence": self.confidence
        }


@dataclass
class Coreference:
    """A resolved coreference between mentions"""
    coref_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mention_span: Optional[EvidenceSpan] = None
    antecedent_ref: Optional[ConceptRef] = None
    confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "coref_id": self.coref_id,
            "mention_span": self.mention_span.to_dict() if self.mention_span else None,
            "antecedent_ref": self.antecedent_ref.to_dict() if self.antecedent_ref else None,
            "confidence": self.confidence
        }


@dataclass
class UnresolvedReference:
    """A reference that couldn't be resolved with confidence"""
    reference_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    mention_text: str = ""
    evidence: Optional[EvidenceSpan] = None
    reason: str = ""
    candidates: List[ConceptRef] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reference_id": self.reference_id,
            "mention_text": self.mention_text,
            "evidence": self.evidence.to_dict() if self.evidence else None,
            "reason": self.reason,
            "candidates": [c.to_dict() for c in self.candidates]
        }


@dataclass
class Confidence:
    """Multi-dimensional confidence components"""
    asr_quality: float = 0.0
    extraction_confidence: float = 0.0
    entity_resolution_confidence: float = 0.0
    grounding_confidence: float = 0.0
    validation_confidence: float = 0.0
    consistency_confidence: float = 0.0

    @property
    def overall(self) -> float:
        weights = {
            'asr_quality': 0.15,
            'extraction_confidence': 0.25,
            'entity_resolution_confidence': 0.20,
            'grounding_confidence': 0.20,
            'validation_confidence': 0.10,
            'consistency_confidence': 0.10
        }
        return (
            self.asr_quality * weights['asr_quality'] +
            self.extraction_confidence * weights['extraction_confidence'] +
            self.entity_resolution_confidence * weights['entity_resolution_confidence'] +
            self.grounding_confidence * weights['grounding_confidence'] +
            self.validation_confidence * weights['validation_confidence'] +
            self.consistency_confidence * weights['consistency_confidence']
        )

    def to_dict(self) -> Dict[str, float]:
        return {
            "asr_quality": self.asr_quality,
            "extraction_confidence": self.extraction_confidence,
            "entity_resolution_confidence": self.entity_resolution_confidence,
            "grounding_confidence": self.grounding_confidence,
            "validation_confidence": self.validation_confidence,
            "consistency_confidence": self.consistency_confidence,
            "overall": self.overall
        }


@dataclass
class SemanticFrame:
    """Complete semantic interpretation of a transcript chunk"""
    frame_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    lecture_id: str = ""
    chunk_id: str = ""
    structural_context: Optional[Dict[str, Any]] = None
    evidence: List[EvidenceSpan] = field(default_factory=list)
    mentions: List[Mention] = field(default_factory=list)
    concepts: List[Concept] = field(default_factory=list)
    propositions: List[Proposition] = field(default_factory=list)
    relations: List[Relation] = field(default_factory=list)
    instructional_acts: List[InstructionalAct] = field(default_factory=list)
    coreferences: List[Coreference] = field(default_factory=list)
    unresolved_references: List[UnresolvedReference] = field(default_factory=list)
    extraction_status: ExtractionStatus = ExtractionStatus.UNCERTAIN
    frame_confidence: Confidence = field(default_factory=Confidence)
    processing_version: str = "0.1.0"
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "frame_id": self.frame_id,
            "lecture_id": self.lecture_id,
            "chunk_id": self.chunk_id,
            "structural_context": self.structural_context,
            "evidence": [e.to_dict() for e in self.evidence],
            "mentions": [m.to_dict() for m in self.mentions],
            "concepts": [c.to_dict() for c in self.concepts],
            "propositions": [p.to_dict() for p in self.propositions],
            "relations": [r.to_dict() for r in self.relations],
            "instructional_acts": [a.to_dict() for a in self.instructional_acts],
            "coreferences": [c.to_dict() for c in self.coreferences],
            "unresolved_references": [u.to_dict() for u in self.unresolved_references],
            "extraction_status": self.extraction_status.value,
            "frame_confidence": self.frame_confidence.to_dict(),
            "processing_version": self.processing_version,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class SemanticEvent:
    """An event representing a semantic state change"""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: Optional[SemanticEventType] = None
    frame_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    payload: Dict[str, Any] = field(default_factory=dict)
    lecture_id: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value if self.event_type else None,
            "frame_id": self.frame_id,
            "timestamp": self.timestamp.isoformat(),
            "payload": self.payload,
            "lecture_id": self.lecture_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SemanticEvent':
        return cls(
            event_id=data.get("event_id", str(uuid.uuid4())),
            event_type=SemanticEventType(data["event_type"]) if data.get("event_type") else None,
            frame_id=data.get("frame_id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if data.get("timestamp") else datetime.now(),
            payload=data.get("payload", {}),
            lecture_id=data.get("lecture_id", "")
        )


class SemanticEventLog:
    """Append-only event log for replay and audit"""

    def __init__(self):
        self._events: List[SemanticEvent] = []
        self._event_index: Dict[str, int] = {}

    def append(self, event: SemanticEvent) -> None:
        self._events.append(event)
        self._event_index[event.event_id] = len(self._events) - 1

    def get_event(self, event_id: str) -> Optional[SemanticEvent]:
        index = self._event_index.get(event_id)
        if index is not None:
            return self._events[index]
        return None

    def get_events_since(self, timestamp: datetime) -> List[SemanticEvent]:
        return [e for e in self._events if e.timestamp >= timestamp]

    def get_events_by_type(self, event_type: SemanticEventType) -> List[SemanticEvent]:
        return [e for e in self._events if e.event_type == event_type]

    def replay(self) -> List[SemanticEvent]:
        return list(self._events)

    def clear(self) -> None:
        self._events.clear()
        self._event_index.clear()

    def __len__(self) -> int:
        return len(self._events)