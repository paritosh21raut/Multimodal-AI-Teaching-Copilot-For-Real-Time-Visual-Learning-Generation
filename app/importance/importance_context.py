from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass(frozen=True)
class ImportanceContext:
    """
    Immutable per-chunk input for Phase 5.

    Built synchronously at enqueue time (cheap). Contains ONLY data Phase 5
    is allowed to consume:
    - chunk text and rolling transcript context
    - LSI structural context (as context, never as authority)
    - prior concept labels observed in the transcript (from Phase 4 ledger,
      used as supporting evidence, not authority)
    - optional pre-computed local extraction from Phase 4
    """

    chunk_id: str
    chunk_text: str
    rolling_context: str

    lsi_relation: Optional[str]
    lsi_node_id: Optional[str]
    lsi_node_label: Optional[str]
    lsi_parent_node_id: Optional[str]
    lsi_parent_label: Optional[str]
    lsi_depth: Optional[int]

    concept_under_annotation: Optional[str]

    prior_concept_labels: Tuple[str, ...]
    prior_assertions_for_concept: Tuple[str, ...]
    concept_mention_count: int
    concept_first_seen: bool

    current_assertion: Optional[dict] = None

    recent_concept_labels: Tuple[str, ...] = field(default_factory=tuple)
    candidate_labels: Tuple[str, ...] = field(default_factory=tuple)