"""
Semantic Intelligence Subsystem

Evidence-grounded, incremental semantic compiler for lecture transcripts.
"""

from .semantic_models import (
    SemanticFrame,
    SemanticEvent,
    SemanticEventLog,
    Concept,
    ConceptRef,
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
from .mention_extractor import MentionExtractor
from .proposition_extractor import PropositionExtractor
from .relation_normalizer import RelationNormalizer
from .instructional_detector import InstructionalDetector
from .concept_registry import ConceptRegistry, ResolutionResult
from .entity_resolver import EntityResolver
from .semantic_memory import SemanticMemory, ActiveContext, TopicMemory
from .semantic_intelligence import SemanticIntelligence

__version__ = "0.3.0"

__all__ = [
    # Models
    "SemanticFrame",
    "SemanticEvent",
    "SemanticEventLog",
    "Concept",
    "ConceptRef",
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
    # State
    "SemanticState",
    # Managers
    "EvidenceManager",
    # Extractors
    "MentionExtractor",
    "PropositionExtractor",
    "RelationNormalizer",
    "InstructionalDetector",
    # Phase 2
    "ConceptRegistry",
    "ResolutionResult",
    "EntityResolver",
    "SemanticMemory",
    "ActiveContext",
    "TopicMemory",
    # Main
    "SemanticIntelligence"
]