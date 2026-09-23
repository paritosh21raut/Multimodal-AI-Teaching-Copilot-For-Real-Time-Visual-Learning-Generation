from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class StructureRelation(str, Enum):
    CONTINUATION = "continuation"
    DETAIL = "detail"
    SUBTOPIC = "subtopic"
    SIBLING = "sibling"
    NEW_TOPIC = "new_topic"
    RETURN = "return"
    RELATED = "related"
    IRRELEVANT = "irrelevant"


@dataclass
class StructureNode:
    id: str
    name: str
    parent_id: Optional[str]
    depth: int
    embedding: Any
    first_chunk_index: int
    last_chunk_index: int
    mention_count: int = 1
    evidence: List[str] = field(default_factory=list)
    children_ids: List[str] = field(default_factory=list)
    relation_history: List[str] = field(default_factory=list)


@dataclass
class StructureDecision:
    relation: StructureRelation
    current_node_id: Optional[str]
    detected_node_id: Optional[str]
    parent_node_id: Optional[str]
    depth: int
    topic_label: str
    is_new_topic: bool
    is_new_subtopic: bool
    is_return: bool
    similarity: float
    confidence: float
    reason: str
    evidence: Dict[str, Any] = field(default_factory=dict)


class LectureStructureRegistry:

    def __init__(self, max_nodes: int = 200) -> None:
        self._lock = threading.RLock()
        self._nodes: Dict[str, StructureNode] = {}
        self._max_nodes = int(max_nodes)
        self._chunk_counter = 0

    def next_chunk_index(self) -> int:
        with self._lock:
            self._chunk_counter += 1
            return self._chunk_counter

    def is_empty(self) -> bool:
        with self._lock:
            return not self._nodes

    def size(self) -> int:
        with self._lock:
            return len(self._nodes)

    def get(self, node_id: Optional[str]) -> Optional[StructureNode]:
        if not node_id:
            return None
        with self._lock:
            return self._nodes.get(node_id)

    def all_nodes(self) -> List[StructureNode]:
        with self._lock:
            return list(self._nodes.values())

    def roots(self) -> List[StructureNode]:
        with self._lock:
            return [
                node for node in self._nodes.values()
                if node.parent_id is None
            ]

    def children_of(
        self, node_id: Optional[str]
    ) -> List[StructureNode]:
        if not node_id:
            return []
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return []
            return [
                self._nodes[child_id]
                for child_id in node.children_ids
                if child_id in self._nodes
            ]

    def siblings_of(
        self, node_id: Optional[str]
    ) -> List[StructureNode]:
        node = self.get(node_id)
        if node is None:
            return []
        if node.parent_id is None:
            return [
                other for other in self.roots()
                if other.id != node.id
            ]
        return [
            other for other in self.children_of(node.parent_id)
            if other.id != node.id
        ]

    def label_exists_among_siblings(
        self, parent_id: Optional[str], label: str
    ) -> bool:
        if not label:
            return False
        candidate = label.strip().lower()
        with self._lock:
            if parent_id is None:
                peers = [
                    node for node in self._nodes.values()
                    if node.parent_id is None
                ]
            else:
                parent = self._nodes.get(parent_id)
                if parent is None:
                    return False
                peers = [
                    self._nodes[cid]
                    for cid in parent.children_ids
                    if cid in self._nodes
                ]
            return any(
                peer.name.strip().lower() == candidate
                for peer in peers
            )

    def add_root(
        self, name: str, embedding: Any, chunk_index: int
    ) -> StructureNode:
        node = StructureNode(
            id=str(uuid.uuid4()),
            name=name,
            parent_id=None,
            depth=0,
            embedding=embedding,
            first_chunk_index=chunk_index,
            last_chunk_index=chunk_index,
        )
        with self._lock:
            self._nodes[node.id] = node
            self._maybe_evict()
        return node

    def add_child(
        self,
        parent_id: str,
        name: str,
        embedding: Any,
        chunk_index: int,
    ) -> StructureNode:
        with self._lock:
            parent = self._nodes.get(parent_id)
            if parent is None:
                return self.add_root(
                    name=name,
                    embedding=embedding,
                    chunk_index=chunk_index,
                )
            node = StructureNode(
                id=str(uuid.uuid4()),
                name=name,
                parent_id=parent.id,
                depth=parent.depth + 1,
                embedding=embedding,
                first_chunk_index=chunk_index,
                last_chunk_index=chunk_index,
            )
            self._nodes[node.id] = node
            parent.children_ids.append(node.id)
            self._maybe_evict()
            return node

    def record_visit(
        self,
        node_id: str,
        chunk_index: int,
        evidence_text: Optional[str] = None,
        relation: Optional[str] = None,
        evidence_max: int = 20,
        relation_history_max: int = 10,
    ) -> None:
        with self._lock:
            node = self._nodes.get(node_id)
            if node is None:
                return
            node.last_chunk_index = chunk_index
            node.mention_count += 1
            if evidence_text:
                node.evidence.append(evidence_text)
                if len(node.evidence) > evidence_max:
                    node.evidence = node.evidence[-evidence_max:]
            if relation:
                node.relation_history.append(relation)
                if len(node.relation_history) > relation_history_max:
                    node.relation_history = node.relation_history[
                        -relation_history_max:
                    ]

    def _maybe_evict(self) -> None:
        if len(self._nodes) <= self._max_nodes:
            return
        leaves = [
            node for node in self._nodes.values()
            if not node.children_ids
        ]
        if not leaves:
            return
        leaves.sort(key=lambda n: n.last_chunk_index)
        overflow = len(self._nodes) - self._max_nodes
        for node in leaves[:overflow]:
            self._nodes.pop(node.id, None)
            if node.parent_id:
                parent = self._nodes.get(node.parent_id)
                if parent and node.id in parent.children_ids:
                    parent.children_ids.remove(node.id)

    def clear(self) -> None:
        with self._lock:
            self._nodes.clear()
            self._chunk_counter = 0