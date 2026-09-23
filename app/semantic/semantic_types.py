from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


# ==========================================================
# CLOSED VOCABULARIES
# ==========================================================

class InformationType(str, Enum):
    DEFINITION = "DEFINITION"
    FORMULA = "FORMULA"
    EXAMPLE = "EXAMPLE"
    COMPARISON = "COMPARISON"
    PROCESS = "PROCESS"
    CLASSIFICATION = "CLASSIFICATION"
    HIERARCHY = "HIERARCHY"
    ARCHITECTURE = "ARCHITECTURE"
    CAUSE_EFFECT = "CAUSE_EFFECT"
    TIMELINE = "TIMELINE"
    PROCEDURE = "PROCEDURE"
    PRINCIPLE = "PRINCIPLE"
    FACT = "FACT"
    EXPLANATION = "EXPLANATION"
    NORMAL_EXPLANATORY_CONTENT = "NORMAL_EXPLANATORY_CONTENT"
    QUESTION = "QUESTION"
    ANSWER = "ANSWER"
    UNKNOWN = "UNKNOWN"


class ConceptType(str, Enum):
    ENTITY = "entity"
    CLASS = "class"
    PROCESS = "process"
    QUANTITY = "quantity"
    UNKNOWN = "unknown"


class SemanticRole(str, Enum):
    CORE_CONCEPT = "core_concept"
    SUPPORTING_DETAIL = "supporting_detail"
    EXAMPLE = "example"
    DEFINITION = "definition"
    PROPERTY = "property"
    NAMED_TERM = "named_term"
    UNKNOWN = "unknown"


class Polarity(str, Enum):
    POSITIVE = "positive"
    NEGATED = "negated"


class Certainty(str, Enum):
    ASSERTED = "asserted"
    UNCERTAIN = "uncertain"
    CORRECTED = "corrected"


class RelationToPrior(str, Enum):
    NEW = "new"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    REFINES = "refines"


class ProcessingPath(str, Enum):
    LOCAL = "local"
    LLM = "llm"
    LLM_FALLBACK = "llm_fallback"
    SKIPPED = "skipped"


class Source(str, Enum):
    TEACHER_TRANSCRIPT = "teacher_transcript"


# ==========================================================
# PERSISTENT RECORDS (ledger)
# ==========================================================

@dataclass
class SemanticEvidence:
    id: str
    chunk_id: str
    sentence_index: int
    span_start: int
    span_end: int
    text: str
    source: str = Source.TEACHER_TRANSCRIPT.value
    relation_to_prior: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "chunk_id": self.chunk_id,
            "sentence_index": self.sentence_index,
            "span_start": self.span_start,
            "span_end": self.span_end,
            "text": self.text,
            "source": self.source,
            "relation_to_prior": self.relation_to_prior,
        }


@dataclass
class SemanticConcept:
    id: str
    canonical_label: str
    aliases: List[str] = field(default_factory=list)
    concept_type: str = ConceptType.UNKNOWN.value
    lsi_node_id: Optional[str] = None
    embedding: Any = None
    first_seen_chunk: str = ""
    last_seen_chunk: str = ""
    mention_count: int = 1
    evidence_ids: List[str] = field(default_factory=list)

    def to_dict(self, include_embedding: bool = False) -> Dict[str, Any]:
        d = {
            "id": self.id,
            "canonical_label": self.canonical_label,
            "aliases": list(self.aliases),
            "concept_type": self.concept_type,
            "lsi_node_id": self.lsi_node_id,
            "first_seen_chunk": self.first_seen_chunk,
            "last_seen_chunk": self.last_seen_chunk,
            "mention_count": self.mention_count,
            "evidence_ids": list(self.evidence_ids),
        }
        if include_embedding:
            d["embedding"] = self.embedding
        return d


@dataclass
class SemanticAssertion:
    id: str
    concept_id: str
    information_type: str = InformationType.UNKNOWN.value
    semantic_role: str = SemanticRole.UNKNOWN.value
    predicate: Optional[str] = None
    object_concept_id: Optional[str] = None
    object_literal: Optional[str] = None
    polarity: str = Polarity.POSITIVE.value
    certainty: str = Certainty.ASSERTED.value
    relation_to_prior: str = RelationToPrior.NEW.value
    evidence_ids: List[str] = field(default_factory=list)
    source: str = Source.TEACHER_TRANSCRIPT.value
    confidence_hint: float = 0.0
    created_at_chunk: str = ""
    last_seen_chunk: str = ""
    mention_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "concept_id": self.concept_id,
            "information_type": self.information_type,
            "semantic_role": self.semantic_role,
            "predicate": self.predicate,
            "object_concept_id": self.object_concept_id,
            "object_literal": self.object_literal,
            "polarity": self.polarity,
            "certainty": self.certainty,
            "relation_to_prior": self.relation_to_prior,
            "evidence_ids": list(self.evidence_ids),
            "source": self.source,
            "confidence_hint": self.confidence_hint,
            "created_at_chunk": self.created_at_chunk,
            "last_seen_chunk": self.last_seen_chunk,
            "mention_count": self.mention_count,
        }


# ==========================================================
# TRANSIENT / PROPOSAL-LEVEL TYPES
# ==========================================================

@dataclass(frozen=True)
class SentenceSpan:
    index: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class CandidateConcept:
    """
    A retrieval candidate: an existing concept OR a pure hint (label only).
    For existing concepts, concept_id is set. For label-only hints,
    concept_id is None.
    """
    concept_id: Optional[str]
    label: str
    embedding_score: float
    lexical_score: float
    lsi_proximity: int  # 0 = current node, 1 = parent/sibling/child, 2+ = farther


@dataclass
class ConceptProposal:
    tmp_id: str
    canonical_label: str
    aliases: List[str] = field(default_factory=list)
    concept_type: str = ConceptType.UNKNOWN.value
    existing_concept_id: Optional[str] = None


@dataclass
class RelationProposal:
    subject_tmp_id: str
    predicate: str
    object_tmp_id: Optional[str] = None
    object_literal: Optional[str] = None
    polarity: str = Polarity.POSITIVE.value
    certainty: str = Certainty.ASSERTED.value
    relation_to_prior: str = RelationToPrior.NEW.value
    information_type: str = InformationType.UNKNOWN.value
    semantic_role: str = SemanticRole.UNKNOWN.value
    sentence_index: int = 0
    span_start: int = 0
    span_end: int = 0
    confidence_hint: float = 0.0


@dataclass
class SemanticProposal:
    """
    Output of a SemanticReasoner (LLM or mock). Not authoritative.
    """
    concepts: List[ConceptProposal] = field(default_factory=list)
    relations: List[RelationProposal] = field(default_factory=list)
    notes: str = ""
    source: str = "reasoner"


@dataclass
class LocalExtraction:
    """
    Output of the deterministic narrow local resolver. If action is
    ABSTAIN, extraction is None.
    """
    action: str  # "RESOLVE" | "ABSTAIN"
    kind: Optional[str] = None
    subject: Optional[str] = None
    object_: Optional[str] = None
    predicate: Optional[str] = None
    information_type: str = InformationType.UNKNOWN.value


@dataclass(frozen=True)
class SemanticContextSnapshot:
    """
    Immutable snapshot enqueued for asynchronous processing.

    Contains:
    - chunk identity and raw text
    - sentence spans (computed deterministically at enqueue time)
    - structural metadata copied from LSI (immutable snapshot)
    - retrieval candidates computed synchronously (cheap)
    - local extraction result (or None)
    - a routing decision: SAFE_LOCAL | QUEUE_FOR_LLM | SKIP
    """
    chunk_id: str
    chunk_text: str
    sentences: Tuple[SentenceSpan, ...]

    lsi_relation: Optional[str]
    lsi_node_id: Optional[str]
    lsi_node_label: Optional[str]
    lsi_parent_node_id: Optional[str]
    lsi_parent_label: Optional[str]
    lsi_depth: Optional[int]

    recent_concept_labels: Tuple[str, ...]
    candidates: Tuple[CandidateConcept, ...]

    local_extraction: Optional[LocalExtraction]
    gate_decision: str  # "SAFE_LOCAL" | "QUEUE_FOR_LLM" | "SKIP"

    rolling_context: str = ""


def is_valid_information_type(value: str) -> bool:
    return value in {t.value for t in InformationType}


def is_valid_concept_type(value: str) -> bool:
    return value in {t.value for t in ConceptType}


def is_valid_semantic_role(value: str) -> bool:
    return value in {r.value for r in SemanticRole}


def is_valid_polarity(value: str) -> bool:
    return value in {p.value for p in Polarity}


def is_valid_certainty(value: str) -> bool:
    return value in {c.value for c in Certainty}


def is_valid_relation_to_prior(value: str) -> bool:
    return value in {r.value for r in RelationToPrior}