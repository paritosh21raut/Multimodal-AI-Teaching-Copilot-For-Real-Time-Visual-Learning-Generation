from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class Emphasis(str, Enum):
    YES = "YES"
    NO = "NO"
    UNCERTAIN = "UNCERTAIN"


class Centrality(str, Enum):
    CORE = "CORE"
    SUPPORTING = "SUPPORTING"
    INCIDENTAL = "INCIDENTAL"
    UNCERTAIN = "UNCERTAIN"


class DevelopmentalRole(str, Enum):
    INTRODUCTION = "INTRODUCTION"
    DEFINITION = "DEFINITION"
    PROPERTY = "PROPERTY"
    RELATIONSHIP = "RELATIONSHIP"
    MECHANISM = "MECHANISM"
    PROCEDURE = "PROCEDURE"
    EXAMPLE = "EXAMPLE"
    APPLICATION = "APPLICATION"
    EXCEPTION = "EXCEPTION"
    SYNTHESIS = "SYNTHESIS"
    META = "META"
    UNKNOWN = "UNKNOWN"


class ProcessingPath(str, Enum):
    LOCAL = "LOCAL"
    LLM = "LLM"
    ABSTAINED = "ABSTAINED"


@dataclass
class ImportanceDepthResult:
    """
    Phase 5 output for one chunk. Structured instructional metadata.

    NOTE: `confidence` is an internal heuristic indicator, NOT a calibrated
    probability. It is provided only for downstream ordering/gating and must
    never be presented to users as a probability.
    """

    chunk_id: str
    assertion_id: Optional[str]
    explicit_emphasis: str
    emphasis_evidence: Optional[str]
    structural_centrality: str
    developmental_roles: List[str] = field(default_factory=list)
    confidence: float = 0.0
    reason: str = ""
    processing_path: str = ProcessingPath.LOCAL.value

    def to_dict(self) -> dict:
        return {
            "chunk_id": self.chunk_id,
            "assertion_id": self.assertion_id,
            "explicit_emphasis": self.explicit_emphasis,
            "emphasis_evidence": self.emphasis_evidence,
            "structural_centrality": self.structural_centrality,
            "developmental_roles": list(self.developmental_roles),
            "confidence": float(self.confidence),
            "reason": self.reason,
            "processing_path": self.processing_path,
        }


def is_valid_emphasis(value: str) -> bool:
    return value in {e.value for e in Emphasis}


def is_valid_centrality(value: str) -> bool:
    return value in {c.value for c in Centrality}


def is_valid_developmental_role(value: str) -> bool:
    return value in {r.value for r in DevelopmentalRole}