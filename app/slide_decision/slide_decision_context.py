from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional


@dataclass(frozen=True)
class SlideDecisionContext:
    """
    Immutable per-chunk input for the Phase 6 engine.

    The engine consumes this and nothing else. All upstream signals are
    resolved by the caller and projected here so the engine remains a pure
    function of its inputs.
    """

    chunk_id: str
    chunk_text: str

    # LSI
    lsi_relation: Optional[str]
    lsi_is_new_topic: bool
    lsi_is_new_subtopic: bool
    lsi_is_return: bool
    lsi_topic: Optional[str]
    lsi_similarity: Optional[float]

    # Slide state
    has_current_slide: bool
    current_slide_number: Optional[int]
    current_slide_topic: Optional[str]

    # Phase 5 (may be None if Phase 5 disabled or fail-open)
    phase5_centrality: Optional[str]
    phase5_developmental_roles: List[str] = field(default_factory=list)
    phase5_explicit_emphasis: Optional[str] = None
    phase5_confidence: Optional[float] = None

    # Phase 4 novelty signals (already resolved from ledger)
    concept_label: Optional[str] = None
    concept_first_seen: Optional[bool] = None
    concept_prior_assertions_count: Optional[int] = None

    # Decision history
    previous_decision: Optional[str] = None
    previous_topic: Optional[str] = None

    # Free-form diagnostic bag; not consulted by rules.
    extra: dict = field(default_factory=dict)