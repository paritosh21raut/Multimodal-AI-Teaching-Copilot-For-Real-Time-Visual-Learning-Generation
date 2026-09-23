from __future__ import annotations

import uuid
from typing import Any, List, Optional, Tuple

from sentence_transformers.util import cos_sim

from app.semantic.local_pass import split_sentences
from app.semantic.semantic_types import (
    CandidateConcept,
    SemanticContextSnapshot,
)


_LEXICAL_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "of", "for",
    "in", "on", "at", "to", "from", "with", "by", "as", "is", "are",
    "was", "were", "be", "been", "being", "has", "have", "had", "does",
    "do", "did", "it", "its", "this", "that", "these", "those", "which",
    "who", "whom", "whose", "there", "here", "so", "we", "you", "they",
    "he", "she", "i", "us", "them",
}


def new_chunk_id() -> str:
    return str(uuid.uuid4())


def _lexical_tokens(text: str) -> List[str]:
    tokens = []
    for raw in text.lower().split():
        tok = raw.strip(".,;:!?()[]{}\"'").strip()
        if not tok:
            continue
        if tok in _LEXICAL_STOPWORDS:
            continue
        tokens.append(tok)
    return tokens


def _lexical_overlap_score(
    query_tokens: List[str],
    target_label: str,
) -> float:
    if not query_tokens or not target_label:
        return 0.0
    target_tokens = set(_lexical_tokens(target_label))
    if not target_tokens:
        return 0.0
    hits = sum(1 for t in query_tokens if t in target_tokens)
    return hits / max(len(target_tokens), 1)


class SemanticContextBuilder:
    """
    Builds an immutable SemanticContextSnapshot for the async worker.

    Responsibilities:
    - assign chunk_id
    - split into sentence spans (deterministic)
    - copy LSI structural metadata
    - retrieve candidate concepts (embedding + lexical)
    - pre-compute local extraction result
    - classify the chunk for the gate
    """

    def __init__(
        self,
        *,
        embedding_model,
        ledger,
        lsi_registry_getter,
        gate,
        max_candidates: int = 5,
    ) -> None:
        self._model = embedding_model
        self._ledger = ledger
        self._get_lsi_node = lsi_registry_getter
        self._gate = gate
        self._max_candidates = int(max_candidates)

    # -------------------------------------------------------- #
    # PUBLIC
    # -------------------------------------------------------- #

    def build(
        self,
        *,
        chunk_text: str,
        lsi_relation: Optional[str],
        lsi_node_id: Optional[str],
        lsi_node_label: Optional[str],
        lsi_parent_node_id: Optional[str],
        lsi_parent_label: Optional[str],
        lsi_depth: Optional[int],
        rolling_context: str = "",
    ) -> SemanticContextSnapshot:

        chunk_text = chunk_text or ""
        chunk_id = new_chunk_id()

        sentences = tuple(split_sentences(chunk_text))

        candidates = self._retrieve_candidates(
            sentences=sentences,
            lsi_node_id=lsi_node_id,
            lsi_parent_node_id=lsi_parent_node_id,
        )

        recent_labels = self._recent_concept_labels(limit=8)

        # Local extraction: try each sentence; first RESOLVE wins.
        from app.semantic.local_pass import resolve_local

        local_extraction = None
        for span in sentences:
            extraction = resolve_local(span.text)
            if extraction.action == "RESOLVE":
                local_extraction = extraction
                break

        gate_decision = self._gate.decide(
            chunk_text=chunk_text,
            sentences=sentences,
            lsi_relation=lsi_relation,
            local_extraction=local_extraction,
            candidates=candidates,
        )

        return SemanticContextSnapshot(
            chunk_id=chunk_id,
            chunk_text=chunk_text,
            sentences=sentences,
            lsi_relation=lsi_relation,
            lsi_node_id=lsi_node_id,
            lsi_node_label=lsi_node_label,
            lsi_parent_node_id=lsi_parent_node_id,
            lsi_parent_label=lsi_parent_label,
            lsi_depth=lsi_depth,
            recent_concept_labels=tuple(recent_labels),
            candidates=tuple(candidates),
            local_extraction=local_extraction,
            gate_decision=gate_decision,
            rolling_context=rolling_context or "",
        )

    # -------------------------------------------------------- #
    # RETRIEVAL
    # -------------------------------------------------------- #

    def _retrieve_candidates(
        self,
        *,
        sentences: Tuple,
        lsi_node_id: Optional[str],
        lsi_parent_node_id: Optional[str],
    ) -> List[CandidateConcept]:

        concepts = self._ledger.all_concepts()
        if not concepts:
            return []

        if not sentences:
            return []

        # Use the whole chunk as a single query for retrieval scoring.
        query_text = " ".join(span.text for span in sentences).strip()
        if not query_text:
            return []

        query_embedding = self._model.encode(
            query_text, convert_to_tensor=True
        )
        query_tokens = _lexical_tokens(query_text)

        scored: List[CandidateConcept] = []

        for concept in concepts:

            embedding_score = 0.0
            if concept.embedding is not None:
                try:
                    embedding_score = float(
                        cos_sim(query_embedding, concept.embedding).item()
                    )
                except Exception:
                    embedding_score = 0.0

            lexical_score = _lexical_overlap_score(
                query_tokens, concept.canonical_label
            )

            proximity = self._lsi_proximity(
                concept.lsi_node_id,
                lsi_node_id,
                lsi_parent_node_id,
            )

            scored.append(
                CandidateConcept(
                    concept_id=concept.id,
                    label=concept.canonical_label,
                    embedding_score=round(embedding_score, 4),
                    lexical_score=round(lexical_score, 4),
                    lsi_proximity=proximity,
                )
            )

        # Ranking: lexical first (exact-label matches dominate),
        # then embedding, with LSI proximity as a tiebreak signal.
        def rank_key(c: CandidateConcept):
            return (
                -c.lexical_score,
                -c.embedding_score,
                c.lsi_proximity,
            )

        scored.sort(key=rank_key)

        return scored[: self._max_candidates]

    @staticmethod
    def _lsi_proximity(
        concept_node_id: Optional[str],
        current_node_id: Optional[str],
        parent_node_id: Optional[str],
    ) -> int:
        if not concept_node_id:
            return 99
        if current_node_id and concept_node_id == current_node_id:
            return 0
        if parent_node_id and concept_node_id == parent_node_id:
            return 1
        return 2

    def _recent_concept_labels(self, *, limit: int) -> List[str]:

        concepts = self._ledger.all_concepts()

        concepts_sorted = sorted(
            concepts,
            key=lambda c: c.last_seen_chunk or "",
            reverse=True,
        )

        return [c.canonical_label for c in concepts_sorted[:limit]]