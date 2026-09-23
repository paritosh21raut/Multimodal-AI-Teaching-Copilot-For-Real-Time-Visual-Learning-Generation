from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass(frozen=True)
class NodeView:
    id: str
    label: str
    parent_id: Optional[str]
    parent_label: Optional[str]
    depth: int
    child_labels: Tuple[str, ...]
    mention_count: int
    last_chunk_index: int


@dataclass
class StructuralProposal:
    relation: str
    target_node_id: Optional[str]
    concept_label: Optional[str]
    confidence: float
    reason: str
    source: str = "reasoner"
    raw: Dict[str, Any] = field(default_factory=dict)


class StructuralReasonerError(Exception):
    pass


class StructuralReasoner(ABC):

    @abstractmethod
    def reason(
        self,
        *,
        chunk_text: str,
        context: str,
        current_node: Optional[NodeView],
        candidate_nodes: List[NodeView],
        allowed_relations: List[str],
        allow_return: bool,
        allow_new_root: bool,
    ) -> StructuralProposal:
        ...