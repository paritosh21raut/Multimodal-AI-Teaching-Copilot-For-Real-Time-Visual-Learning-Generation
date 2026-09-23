from __future__ import annotations

import threading
import uuid
from typing import Any, Dict, List, Optional

from app.semantic.semantic_types import (
    SemanticAssertion,
    SemanticConcept,
    SemanticEvidence,
)


class SemanticLedger:
    """
    Thread-safe, in-memory, per-lecture semantic ledger.

    No persistence. No fixed size caps. Lifecycle is a single lecture.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

        self._concepts: Dict[str, SemanticConcept] = {}
        self._assertions: Dict[str, SemanticAssertion] = {}
        self._evidence: Dict[str, SemanticEvidence] = {}

        self._label_index: Dict[str, str] = {}
        self._lsi_node_index: Dict[str, List[str]] = {}

    # ---------------------------------------------------------- #
    # EVIDENCE
    # ---------------------------------------------------------- #

    def add_evidence(
        self,
        *,
        chunk_id: str,
        sentence_index: int,
        span_start: int,
        span_end: int,
        text: str,
        relation_to_prior: Optional[str] = None,
    ) -> str:

        with self._lock:

            evidence = SemanticEvidence(
                id=str(uuid.uuid4()),
                chunk_id=chunk_id,
                sentence_index=int(sentence_index),
                span_start=int(span_start),
                span_end=int(span_end),
                text=text,
                relation_to_prior=relation_to_prior,
            )

            self._evidence[evidence.id] = evidence

            return evidence.id

    def get_evidence(
        self, evidence_id: str
    ) -> Optional[SemanticEvidence]:
        with self._lock:
            return self._evidence.get(evidence_id)

    # ---------------------------------------------------------- #
    # CONCEPTS
    # ---------------------------------------------------------- #

    def add_concept(
        self,
        *,
        canonical_label: str,
        aliases: Optional[List[str]] = None,
        concept_type: str,
        lsi_node_id: Optional[str],
        embedding: Any,
        chunk_id: str,
        evidence_ids: Optional[List[str]] = None,
    ) -> str:

        with self._lock:

            concept = SemanticConcept(
                id=str(uuid.uuid4()),
                canonical_label=canonical_label.strip(),
                aliases=list(aliases or []),
                concept_type=concept_type,
                lsi_node_id=lsi_node_id,
                embedding=embedding,
                first_seen_chunk=chunk_id,
                last_seen_chunk=chunk_id,
                mention_count=1,
                evidence_ids=list(evidence_ids or []),
            )

            self._concepts[concept.id] = concept
            self._label_index[
                concept.canonical_label.lower()
            ] = concept.id

            if lsi_node_id:
                self._lsi_node_index.setdefault(
                    lsi_node_id, []
                ).append(concept.id)

            return concept.id

    def find_concept_by_label(
        self, label: str
    ) -> Optional[SemanticConcept]:

        if not label:
            return None

        with self._lock:

            cid = self._label_index.get(label.strip().lower())

            if cid is None:
                return None

            return self._concepts.get(cid)

    def find_concepts_by_lsi_node(
        self, node_id: Optional[str]
    ) -> List[SemanticConcept]:

        if not node_id:
            return []

        with self._lock:

            ids = self._lsi_node_index.get(node_id, [])

            return [
                self._concepts[cid]
                for cid in ids
                if cid in self._concepts
            ]

    def all_concepts(self) -> List[SemanticConcept]:

        with self._lock:
            return list(self._concepts.values())

    def get_concept(
        self, concept_id: str
    ) -> Optional[SemanticConcept]:

        with self._lock:
            return self._concepts.get(concept_id)

    def record_concept_mention(
        self,
        concept_id: str,
        chunk_id: str,
        additional_evidence_ids: Optional[List[str]] = None,
    ) -> None:

        with self._lock:

            concept = self._concepts.get(concept_id)

            if concept is None:
                return

            concept.last_seen_chunk = chunk_id
            concept.mention_count += 1

            if additional_evidence_ids:
                for eid in additional_evidence_ids:
                    if eid not in concept.evidence_ids:
                        concept.evidence_ids.append(eid)

    # ---------------------------------------------------------- #
    # ASSERTIONS
    # ---------------------------------------------------------- #

    def add_assertion(
        self,
        *,
        concept_id: str,
        information_type: str,
        semantic_role: str,
        predicate: Optional[str],
        object_concept_id: Optional[str],
        object_literal: Optional[str],
        polarity: str,
        certainty: str,
        relation_to_prior: str,
        evidence_ids: List[str],
        chunk_id: str,
        confidence_hint: float = 0.0,
    ) -> str:

        with self._lock:

            assertion = SemanticAssertion(
                id=str(uuid.uuid4()),
                concept_id=concept_id,
                information_type=information_type,
                semantic_role=semantic_role,
                predicate=predicate,
                object_concept_id=object_concept_id,
                object_literal=object_literal,
                polarity=polarity,
                certainty=certainty,
                relation_to_prior=relation_to_prior,
                evidence_ids=list(evidence_ids),
                confidence_hint=float(confidence_hint),
                created_at_chunk=chunk_id,
                last_seen_chunk=chunk_id,
                mention_count=1,
            )

            self._assertions[assertion.id] = assertion

            return assertion.id

    def all_assertions_for_concept(
        self, concept_id: str
    ) -> List[SemanticAssertion]:

        with self._lock:

            return [
                a
                for a in self._assertions.values()
                if a.concept_id == concept_id
            ]

    def all_assertions(self) -> List[SemanticAssertion]:

        with self._lock:
            return list(self._assertions.values())

    # ---------------------------------------------------------- #
    # SNAPSHOT / RESET
    # ---------------------------------------------------------- #

    def snapshot(self) -> Dict[str, Any]:

        with self._lock:

            return {
                "concepts": [
                    c.to_dict(include_embedding=False)
                    for c in self._concepts.values()
                ],
                "assertions": [
                    a.to_dict()
                    for a in self._assertions.values()
                ],
                "evidence": [
                    e.to_dict()
                    for e in self._evidence.values()
                ],
                "counts": {
                    "concepts": len(self._concepts),
                    "assertions": len(self._assertions),
                    "evidence": len(self._evidence),
                },
            }

    def reset(self) -> None:

        with self._lock:

            self._concepts.clear()
            self._assertions.clear()
            self._evidence.clear()
            self._label_index.clear()
            self._lsi_node_index.clear()