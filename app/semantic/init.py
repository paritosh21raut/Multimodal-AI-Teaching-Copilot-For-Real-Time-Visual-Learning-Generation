"""
Semantic Intelligence Subsystem

Evidence-grounded, incremental semantic compiler for lecture transcripts.
"""

from .semantic_models import (
    SemanticFrame,
    SemanticEvent,
    SemanticEventLog,
    Concept,
    Proposition,
    Relation,
    EvidenceSpan,
    Mention,
    InstructionalAct,
    Coreference,
    UnresolvedReference,
    Confidence,
    GroundingStatus,
    ExtractionStatus,
    PropositionLifecycle,
    RelationType,
    InstructionalActType,
    SemanticEventType
)

from .semantic_state import SemanticState
from .evidence import EvidenceManager

__version__ = "0.1.0"

__all__ = [
    "SemanticFrame",
    "SemanticEvent",
    "SemanticEventLog",
    "Concept",
    "Proposition",
    "Relation",
    "EvidenceSpan",
    "Mention",
    "InstructionalAct",
    "Coreference",
    "UnresolvedReference",
    "Confidence",
    "GroundingStatus",
    "ExtractionStatus",
    "PropositionLifecycle",
    "RelationType",
    "InstructionalActType",
    "SemanticEventType",
    "SemanticState",
    "EvidenceManager"
]