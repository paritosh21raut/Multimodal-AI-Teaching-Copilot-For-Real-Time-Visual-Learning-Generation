from __future__ import annotations

from abc import ABC, abstractmethod

from app.semantic.semantic_types import (
    CandidateConcept,
    SemanticContextSnapshot,
    SemanticProposal,
)


class SemanticReasonerError(Exception):
    """Raised by a SemanticReasoner when no valid proposal can be produced."""


class SemanticReasoner(ABC):
    """
    Provider-independent semantic adjudication interface.

    Implementations may call an LLM, a local model, or return deterministic
    proposals. SemanticIntelligence depends only on this interface.
    """

    @abstractmethod
    def reason(
        self,
        *,
        snapshot: SemanticContextSnapshot,
        candidate_concepts: list[CandidateConcept],
    ) -> SemanticProposal:
        ...