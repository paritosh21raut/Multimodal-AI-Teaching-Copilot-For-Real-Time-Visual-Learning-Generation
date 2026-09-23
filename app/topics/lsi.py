from __future__ import annotations

import re
import threading
from typing import Any, Dict, List, Optional, Tuple

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim

from app.topics.lecture_structure import (
    LectureStructureRegistry,
    StructureDecision,
    StructureNode,
    StructureRelation,
)
from app.topics.structural_reasoner import (
    NodeView,
    StructuralProposal,
    StructuralReasoner,
    StructuralReasonerError,
)


_NEW_TOPIC_PHRASES = (
    "now let's discuss",
    "now let us discuss",
    "now let's look at",
    "now let us look at",
    "now let's learn",
    "now let us learn",
    "now we will discuss",
    "now we'll discuss",
    "now we discuss",
    "next let's discuss",
    "next let us discuss",
    "next we will discuss",
    "next we'll discuss",
    "moving on to",
    "moving on",
    "let's discuss",
    "let us discuss",
    "let's look at",
    "let us look at",
    "another topic",
    "another type",
    "another concept",
)

_RETURN_PHRASES = (
    "coming back to",
    "coming back",
    "returning to",
    "back to",
    "as i mentioned",
    "as we discussed",
    "as we saw",
    "recall that",
    "remember that",
    "earlier we discussed",
    "going back to",
)


_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    parts = _SENTENCE_SPLIT_RE.split(text.strip())
    out: List[str] = []
    for part in parts:
        cleaned = " ".join(part.split()).strip()
        if cleaned:
            out.append(cleaned)
    return out


_FRAMING_PATTERNS = (
    r"let's\s+talk\s+about",
    r"let\s+us\s+talk\s+about",
    r"let's\s+discuss",
    r"let\s+us\s+discuss",
    r"let's\s+look\s+at",
    r"let\s+us\s+look\s+at",
    r"let's\s+examine",
    r"let\s+us\s+examine",
    r"let's\s+consider",
    r"let\s+us\s+consider",
    r"we\s+are\s+going\s+to\s+learn\s+about",
    r"we'?re\s+going\s+to\s+learn\s+about",
    r"we\s+are\s+going\s+to\s+discuss",
    r"we'?re\s+going\s+to\s+discuss",
    r"we\s+will\s+learn\s+about",
    r"we\s+will\s+discuss",
    r"we\s+will\s+study",
    r"today\s+we\s+will\s+learn\s+about",
    r"today\s+we\s+will\s+discuss",
    r"today\s+we\s+will\s+study",
    r"today\s+we\s+are\s+going\s+to\s+learn\s+about",
    r"today\s+we\s+are\s+going\s+to\s+discuss",
    r"today\s+we'?ll\s+learn\s+about",
    r"today\s+we'?ll\s+discuss",
    r"let's\s+learn\s+about",
    r"let\s+us\s+learn\s+about",
    r"now\s+let's\s+learn\s+about",
    r"now\s+let\s+us\s+learn\s+about",
    r"talk\s+about",
    r"discuss",
    r"learn\s+about",
    r"examine",
)

_LEADING_NOISE_TOKENS = {
    "everyone", "so", "okay", "ok", "now", "alright", "well",
    "hi", "hello", "hey", "level", "even", "um", "uh", "erm",
    "ah", "hmm",
}

_STOP_BOUNDARY_RE = re.compile(
    r"[,;:!?]|\b(?:and|is|are|was|were|has|have|had|which|that|because|since|with|where)\b",
    flags=re.IGNORECASE,
)


def normalize_structure_label(text: str, fallback: Optional[str] = None) -> str:
    if not text or not text.strip():
        return fallback or ""

    cleaned = " ".join(text.strip().split())
    cleaned = re.sub(r"^[.!?;:,\-]+", "", cleaned).strip()

    tokens = cleaned.split()
    start_index = 0
    while start_index < len(tokens):
        bare = tokens[start_index].strip(".,!?;:").lower()
        if bare in _LEADING_NOISE_TOKENS:
            start_index += 1
            continue
        break

    trimmed = " ".join(tokens[start_index:]).strip()
    if not trimmed:
        trimmed = cleaned

    head_tokens = trimmed.split()[:12]
    head = " ".join(head_tokens)

    framing_match = None
    for pattern in _FRAMING_PATTERNS:
        match = re.search(pattern, head, flags=re.IGNORECASE)
        if match:
            framing_match = match
            break

    if framing_match is not None:
        tail = head[framing_match.end():].strip()
    else:
        tail = trimmed

    tail = re.split(_STOP_BOUNDARY_RE, tail, maxsplit=1)[0].strip()
    tail = re.sub(r"[.!?]+$", "", tail).strip(" ,;:-")

    if tail:
        words = tail.split()
        if len(words) > 5:
            tail = " ".join(words[:5])

    if not tail:
        words = trimmed.split()
        words = [
            w for w in words
            if w.strip(".,!?;:").lower() not in _LEADING_NOISE_TOKENS
        ]
        if not words:
            return fallback or ""
        tail = " ".join(words[:5])

    tail = tail.strip()
    if not tail:
        return fallback or ""

    return tail[0].upper() + tail[1:]


_ALLOWED_RELATIONS = [
    StructureRelation.CONTINUATION.value,
    StructureRelation.DETAIL.value,
    StructureRelation.SUBTOPIC.value,
    StructureRelation.SIBLING.value,
    StructureRelation.NEW_TOPIC.value,
    StructureRelation.RETURN.value,
    StructureRelation.RELATED.value,
    StructureRelation.IRRELEVANT.value,
]


class LectureStructureIntelligence:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        *,
        reasoner: Optional[StructuralReasoner] = None,
        continue_threshold: float = 0.45,
        related_floor: float = 0.30,
        return_floor: float = 0.55,
        top_k_candidates: int = 5,
        max_nodes: int = 200,
        embedding_model: Optional[SentenceTransformer] = None,
    ) -> None:

        self._model = (
            embedding_model
            if embedding_model is not None
            else SentenceTransformer(model_name)
        )

        self._reasoner = reasoner
        self._continue_threshold = float(continue_threshold)
        self._related_floor = float(related_floor)
        self._return_floor = float(return_floor)
        self._top_k_candidates = int(top_k_candidates)

        self._registry = LectureStructureRegistry(max_nodes=max_nodes)
        self._current_node_id: Optional[str] = None
        self._lock = threading.RLock()

    def reset(self) -> None:
        with self._lock:
            self._registry.clear()
            self._current_node_id = None

    def process(
        self,
        latest_text: str,
        rolling_context: str = "",
        current_topic: Optional[str] = None,
        current_embedding: Any = None,
    ) -> StructureDecision:

        text = (latest_text or "").strip()

        if not text:
            return StructureDecision(
                relation=StructureRelation.IRRELEVANT,
                current_node_id=self._current_node_id,
                detected_node_id=None,
                parent_node_id=None,
                depth=0,
                topic_label=current_topic or "",
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=1.0,
                confidence=0.0,
                reason="empty_text",
                evidence={},
            )

        with self._lock:

            chunk_embedding = self._embed(text)
            sentences = _split_sentences(text)
            sentence_embeddings = [self._embed(s) for s in sentences]
            chunk_index = self._registry.next_chunk_index()

            if self._registry.is_empty():
                label = normalize_structure_label(text, fallback=text)
                node = self._registry.add_root(
                    name=label,
                    embedding=chunk_embedding,
                    chunk_index=chunk_index,
                )
                self._registry.record_visit(
                    node.id,
                    chunk_index,
                    evidence_text=text,
                    relation=StructureRelation.NEW_TOPIC.value,
                )
                self._current_node_id = node.id
                return StructureDecision(
                    relation=StructureRelation.NEW_TOPIC,
                    current_node_id=node.id,
                    detected_node_id=node.id,
                    parent_node_id=None,
                    depth=0,
                    topic_label=node.name,
                    is_new_topic=True,
                    is_new_subtopic=False,
                    is_return=False,
                    similarity=1.0,
                    confidence=1.0,
                    reason="initial_topic",
                    evidence={
                        "chunk_index": chunk_index,
                        "sentence_count": len(sentences),
                    },
                )

            current = self._registry.get(self._current_node_id)
            parent = (
                self._registry.get(current.parent_id)
                if current is not None
                else None
            )

            sim_current = (
                self._cos(chunk_embedding, current.embedding)
                if current is not None
                else 0.0
            )
            sim_current_sent = self._best_sentence_similarity(
                sentence_embeddings, current
            )
            sim_current_evidence = max(sim_current, sim_current_sent)

            sim_parent = (
                self._cos(chunk_embedding, parent.embedding)
                if parent is not None
                else 0.0
            )
            sim_parent_sent = self._best_sentence_similarity(
                sentence_embeddings, parent
            )
            sim_parent_evidence = max(sim_parent, sim_parent_sent)

            has_new_topic_phrase = self._is_explicit_transition(text)
            has_return_phrase = self._has_phrase(text, _RETURN_PHRASES)

            candidate_nodes, best_other_node, sim_other = self._build_candidates(
                chunk_embedding=chunk_embedding,
                sentence_embeddings=sentence_embeddings,
                current=current,
            )

            evidence: Dict[str, Any] = {
                "chunk_index": chunk_index,
                "sentence_count": len(sentences),
                "sim_current": round(sim_current, 4),
                "sim_current_sent": round(sim_current_sent, 4),
                "sim_parent": round(sim_parent, 4),
                "sim_parent_sent": round(sim_parent_sent, 4),
                "sim_other": round(sim_other, 4),
                "has_new_topic_phrase": has_new_topic_phrase,
                "has_return_phrase": has_return_phrase,
            }

            fast = self._fast_path(
                text=text,
                chunk_index=chunk_index,
                current=current,
                parent=parent,
                sim_current_evidence=sim_current_evidence,
                sim_parent_evidence=sim_parent_evidence,
                sim_other=sim_other,
                best_other_node=best_other_node,
                has_new_topic_phrase=has_new_topic_phrase,
                has_return_phrase=has_return_phrase,
                evidence=evidence,
                chunk_embedding=chunk_embedding,
            )

            if fast is not None:
                return fast

            if self._reasoner is None:
                return self._fallback(
                    text=text,
                    chunk_index=chunk_index,
                    current=current,
                    sim_current_evidence=sim_current_evidence,
                    has_new_topic_phrase=has_new_topic_phrase,
                    best_other_node=best_other_node,
                    sim_other=sim_other,
                    has_return_phrase=has_return_phrase,
                    reason="no_reasoner",
                    evidence=evidence,
                )

            node_views = [self._to_node_view(n) for n in candidate_nodes]

            allow_return = (
                has_return_phrase
                and best_other_node is not None
                and sim_other >= self._return_floor
            )
            allow_new_root = True

            try:
                proposal = self._reasoner.reason(
                    chunk_text=text,
                    context=rolling_context or "",
                    current_node=(
                        self._to_node_view(current)
                        if current is not None
                        else None
                    ),
                    candidate_nodes=node_views,
                    allowed_relations=list(_ALLOWED_RELATIONS),
                    allow_return=allow_return,
                    allow_new_root=allow_new_root,
                )
            except StructuralReasonerError as error:
                return self._fallback(
                    text=text,
                    chunk_index=chunk_index,
                    current=current,
                    sim_current_evidence=sim_current_evidence,
                    has_new_topic_phrase=has_new_topic_phrase,
                    best_other_node=best_other_node,
                    sim_other=sim_other,
                    has_return_phrase=has_return_phrase,
                    reason=f"reasoner_error:{error}",
                    evidence=evidence,
                )

            validated = self._validate_proposal(
                proposal=proposal,
                current=current,
                candidate_nodes=candidate_nodes,
                allow_return=allow_return,
                allow_new_root=allow_new_root,
            )

            if validated is None:
                return self._fallback(
                    text=text,
                    chunk_index=chunk_index,
                    current=current,
                    sim_current_evidence=sim_current_evidence,
                    has_new_topic_phrase=has_new_topic_phrase,
                    best_other_node=best_other_node,
                    sim_other=sim_other,
                    has_return_phrase=has_return_phrase,
                    reason="proposal_rejected",
                    evidence=evidence,
                )

            return self._commit(
                text=text,
                chunk_index=chunk_index,
                chunk_embedding=chunk_embedding,
                current=current,
                proposal=proposal,
                validated=validated,
                evidence=evidence,
            )

    def _fast_path(
        self,
        *,
        text: str,
        chunk_index: int,
        current: Optional[StructureNode],
        parent: Optional[StructureNode],
        sim_current_evidence: float,
        sim_parent_evidence: float,
        sim_other: float,
        best_other_node: Optional[StructureNode],
        has_new_topic_phrase: bool,
        has_return_phrase: bool,
        evidence: Dict[str, Any],
        chunk_embedding,
    ) -> Optional[StructureDecision]:

        if current is None:
            return None

        if (
            has_return_phrase
            and best_other_node is not None
            and sim_other >= self._return_floor
        ):
            return self._emit_return(
                node=best_other_node,
                chunk_index=chunk_index,
                text=text,
                similarity=sim_other,
                reason="return_phrase_match",
                evidence=evidence,
            )

        if has_new_topic_phrase:
            return self._emit_new_root(
                text=text,
                chunk_index=chunk_index,
                chunk_embedding=chunk_embedding,
                similarity=sim_current_evidence,
                reason="explicit_topic_transition",
                evidence=evidence,
            )

        if sim_current_evidence >= self._continue_threshold:
            self._registry.record_visit(
                current.id,
                chunk_index,
                evidence_text=text,
                relation=StructureRelation.CONTINUATION.value,
            )
            return StructureDecision(
                relation=StructureRelation.CONTINUATION,
                current_node_id=current.id,
                detected_node_id=current.id,
                parent_node_id=current.parent_id,
                depth=current.depth,
                topic_label=current.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=sim_current_evidence,
                confidence=sim_current_evidence,
                reason="relevant_continuation",
                evidence=evidence,
            )

        if (
            parent is not None
            and sim_parent_evidence >= self._continue_threshold
            and sim_current_evidence < self._continue_threshold
        ):
            self._registry.record_visit(
                current.id,
                chunk_index,
                evidence_text=text,
                relation=StructureRelation.DETAIL.value,
            )
            return StructureDecision(
                relation=StructureRelation.DETAIL,
                current_node_id=current.id,
                detected_node_id=current.id,
                parent_node_id=current.parent_id,
                depth=current.depth,
                topic_label=current.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=sim_current_evidence,
                confidence=sim_parent_evidence,
                reason="detail_within_parent",
                evidence=evidence,
            )

        return None

    def _fallback(
        self,
        *,
        text: str,
        chunk_index: int,
        current: Optional[StructureNode],
        sim_current_evidence: float,
        has_new_topic_phrase: bool,
        best_other_node: Optional[StructureNode],
        sim_other: float,
        has_return_phrase: bool,
        reason: str,
        evidence: Dict[str, Any],
    ) -> StructureDecision:

        if has_new_topic_phrase:
            return self._emit_new_root(
                text=text,
                chunk_index=chunk_index,
                chunk_embedding=None,
                similarity=sim_current_evidence,
                reason=f"fallback:{reason}|explicit_new_topic",
                evidence=evidence,
            )

        if (
            has_return_phrase
            and best_other_node is not None
            and sim_other >= self._return_floor
        ):
            return self._emit_return(
                node=best_other_node,
                chunk_index=chunk_index,
                text=text,
                similarity=sim_other,
                reason=f"fallback:{reason}|explicit_return",
                evidence=evidence,
            )

        if (
            current is not None
            and sim_current_evidence >= self._related_floor
        ):
            self._registry.record_visit(
                current.id,
                chunk_index,
                evidence_text=text,
                relation=StructureRelation.RELATED.value,
            )
            return StructureDecision(
                relation=StructureRelation.RELATED,
                current_node_id=current.id,
                detected_node_id=current.id,
                parent_node_id=current.parent_id,
                depth=current.depth,
                topic_label=current.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=sim_current_evidence,
                confidence=sim_current_evidence,
                reason=f"fallback:{reason}|related",
                evidence=evidence,
            )

        return StructureDecision(
            relation=StructureRelation.IRRELEVANT,
            current_node_id=(
                current.id if current is not None else None
            ),
            detected_node_id=None,
            parent_node_id=None,
            depth=0,
            topic_label=(current.name if current is not None else ""),
            is_new_topic=False,
            is_new_subtopic=False,
            is_return=False,
            similarity=sim_current_evidence,
            confidence=max(0.0, 1.0 - sim_current_evidence),
            reason=f"fallback:{reason}|irrelevant",
            evidence=evidence,
        )

    def _validate_proposal(
        self,
        *,
        proposal: StructuralProposal,
        current: Optional[StructureNode],
        candidate_nodes: List[StructureNode],
        allow_return: bool,
        allow_new_root: bool,
    ) -> Optional[Dict[str, Any]]:

        # ---------------------------------------------------------
        # STEP 1 — Normalize.
        #
        # The reasoner's proposal is a *proposal*. Before applying
        # relation-specific rules, apply collapse rules that are
        # independent of what the reasoner supplied. In particular:
        #
        #   SIBLING at root level  ->  NEW_TOPIC
        #
        # When that collapse happens, the peer-target the reasoner
        # supplied under SIBLING semantics is no longer meaningful.
        # NEW_TOPIC creates a fresh root; it does not target an
        # existing node.
        # ---------------------------------------------------------

        relation = (proposal.relation or "").strip().lower()

        if relation not in _ALLOWED_RELATIONS:
            return None

        target_id = proposal.target_node_id
        concept_label = (proposal.concept_label or "").strip()

        if relation == StructureRelation.SIBLING.value:

            if current is None:
                return None

            if current.parent_id is None:
                # E9: collapse SIBLING at root to NEW_TOPIC.
                # The supplied target refers to the peer *root*, which
                # NEW_TOPIC does not use. Drop it.
                relation = StructureRelation.NEW_TOPIC.value
                target_id = None

        # ---------------------------------------------------------
        # STEP 2 — Relation-specific rules on the normalized values.
        # ---------------------------------------------------------

        if relation == StructureRelation.RETURN.value and not allow_return:
            return None

        if (
            relation == StructureRelation.NEW_TOPIC.value
            and not allow_new_root
        ):
            return None

        candidate_ids = {node.id for node in candidate_nodes}

        if relation in (
            StructureRelation.CONTINUATION.value,
            StructureRelation.DETAIL.value,
            StructureRelation.RELATED.value,
            StructureRelation.RETURN.value,
        ):
            if not target_id or target_id not in candidate_ids:
                return None

        if relation == StructureRelation.SUBTOPIC.value:
            if not target_id or target_id not in candidate_ids:
                return None
            if not concept_label:
                return None

        if relation == StructureRelation.SIBLING.value:
            # At this point SIBLING only remains when current is non-root.
            if not concept_label:
                return None

        if relation == StructureRelation.NEW_TOPIC.value:
            if target_id is not None:
                return None
            if not concept_label:
                return None

        if concept_label and len(concept_label.split()) > 6:
            return None

        parent_id_for_label: Optional[str] = None

        if relation == StructureRelation.SUBTOPIC.value:
            parent_id_for_label = (
                current.parent_id
                if current is not None and current.parent_id is not None
                else (current.id if current is not None else None)
            )
        elif relation == StructureRelation.SIBLING.value:
            parent_id_for_label = (
                current.parent_id if current is not None else None
            )

        if concept_label and parent_id_for_label is not None:
            if self._registry.label_exists_among_siblings(
                parent_id_for_label, concept_label
            ):
                return None

        return {
            "relation": relation,
            "target_node_id": target_id,
            "concept_label": concept_label or None,
        }

    def _commit(
        self,
        *,
        text: str,
        chunk_index: int,
        chunk_embedding,
        current: Optional[StructureNode],
        proposal: StructuralProposal,
        validated: Dict[str, Any],
        evidence: Dict[str, Any],
    ) -> StructureDecision:

        relation = validated["relation"]
        target_id = validated["target_node_id"]
        concept_label = validated["concept_label"]

        evidence = dict(evidence)
        evidence["proposal_source"] = proposal.source
        evidence["proposal_reason"] = proposal.reason

        if relation == StructureRelation.NEW_TOPIC.value:
            node = self._registry.add_root(
                name=concept_label,
                embedding=(
                    chunk_embedding
                    if chunk_embedding is not None
                    else self._embed(text)
                ),
                chunk_index=chunk_index,
            )
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.NEW_TOPIC,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=None,
                depth=0,
                topic_label=node.name,
                is_new_topic=True,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_new_topic",
                evidence=evidence,
            )

        if relation == StructureRelation.SUBTOPIC.value:
            if current is None:
                return self._fallback_empty(text, evidence)
            parent_id = (
                current.parent_id
                if current.parent_id is not None
                else current.id
            )
            node = self._registry.add_child(
                parent_id=parent_id,
                name=concept_label,
                embedding=(
                    chunk_embedding
                    if chunk_embedding is not None
                    else self._embed(text)
                ),
                chunk_index=chunk_index,
            )
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.SUBTOPIC,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=False,
                is_new_subtopic=True,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_subtopic",
                evidence=evidence,
            )

        if relation == StructureRelation.SIBLING.value:
            if current is None or current.parent_id is None:
                return self._fallback_empty(text, evidence)
            node = self._registry.add_child(
                parent_id=current.parent_id,
                name=concept_label,
                embedding=(
                    chunk_embedding
                    if chunk_embedding is not None
                    else self._embed(text)
                ),
                chunk_index=chunk_index,
            )
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.SIBLING,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=True,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_sibling",
                evidence=evidence,
            )

        if relation == StructureRelation.RETURN.value:
            node = self._registry.get(target_id)
            if node is None:
                return self._fallback_empty(text, evidence)
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.RETURN,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=True,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_return",
                evidence=evidence,
            )

        if relation == StructureRelation.CONTINUATION.value:
            node = self._registry.get(target_id)
            if node is None:
                return self._fallback_empty(text, evidence)
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.CONTINUATION,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_continuation",
                evidence=evidence,
            )

        if relation == StructureRelation.DETAIL.value:
            node = self._registry.get(target_id)
            if node is None:
                return self._fallback_empty(text, evidence)
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            self._current_node_id = node.id
            return StructureDecision(
                relation=StructureRelation.DETAIL,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_detail",
                evidence=evidence,
            )

        if relation == StructureRelation.RELATED.value:
            node = self._registry.get(target_id)
            if node is None:
                return self._fallback_empty(text, evidence)
            self._registry.record_visit(
                node.id,
                chunk_index,
                evidence_text=text,
                relation=relation,
            )
            return StructureDecision(
                relation=StructureRelation.RELATED,
                current_node_id=node.id,
                detected_node_id=node.id,
                parent_node_id=node.parent_id,
                depth=node.depth,
                topic_label=node.name,
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_related",
                evidence=evidence,
            )

        if relation == StructureRelation.IRRELEVANT.value:
            return StructureDecision(
                relation=StructureRelation.IRRELEVANT,
                current_node_id=self._current_node_id,
                detected_node_id=None,
                parent_node_id=None,
                depth=0,
                topic_label=(
                    current.name if current is not None else ""
                ),
                is_new_topic=False,
                is_new_subtopic=False,
                is_return=False,
                similarity=proposal.confidence,
                confidence=proposal.confidence,
                reason="reasoner_irrelevant",
                evidence=evidence,
            )

        return self._fallback_empty(text, evidence)

    def _emit_return(
        self,
        *,
        node: StructureNode,
        chunk_index: int,
        text: str,
        similarity: float,
        reason: str,
        evidence: Dict[str, Any],
    ) -> StructureDecision:
        self._registry.record_visit(
            node.id,
            chunk_index,
            evidence_text=text,
            relation=StructureRelation.RETURN.value,
        )
        self._current_node_id = node.id
        return StructureDecision(
            relation=StructureRelation.RETURN,
            current_node_id=node.id,
            detected_node_id=node.id,
            parent_node_id=node.parent_id,
            depth=node.depth,
            topic_label=node.name,
            is_new_topic=False,
            is_new_subtopic=False,
            is_return=True,
            similarity=similarity,
            confidence=similarity,
            reason=reason,
            evidence=evidence,
        )

    def _emit_new_root(
        self,
        *,
        text: str,
        chunk_index: int,
        chunk_embedding,
        similarity: float,
        reason: str,
        evidence: Dict[str, Any],
    ) -> StructureDecision:
        label = normalize_structure_label(text, fallback=text)
        embedding = (
            chunk_embedding
            if chunk_embedding is not None
            else self._embed(text)
        )
        node = self._registry.add_root(
            name=label,
            embedding=embedding,
            chunk_index=chunk_index,
        )
        self._registry.record_visit(
            node.id,
            chunk_index,
            evidence_text=text,
            relation=StructureRelation.NEW_TOPIC.value,
        )
        self._current_node_id = node.id
        return StructureDecision(
            relation=StructureRelation.NEW_TOPIC,
            current_node_id=node.id,
            detected_node_id=node.id,
            parent_node_id=None,
            depth=0,
            topic_label=node.name,
            is_new_topic=True,
            is_new_subtopic=False,
            is_return=False,
            similarity=similarity,
            confidence=1.0,
            reason=reason,
            evidence=evidence,
        )

    def _fallback_empty(
        self, text: str, evidence: Dict[str, Any]
    ) -> StructureDecision:
        return StructureDecision(
            relation=StructureRelation.IRRELEVANT,
            current_node_id=self._current_node_id,
            detected_node_id=None,
            parent_node_id=None,
            depth=0,
            topic_label="",
            is_new_topic=False,
            is_new_subtopic=False,
            is_return=False,
            similarity=0.0,
            confidence=0.0,
            reason="commit_fallback_empty",
            evidence=evidence,
        )

    def _build_candidates(
        self,
        *,
        chunk_embedding,
        sentence_embeddings: List[Any],
        current: Optional[StructureNode],
    ) -> Tuple[List[StructureNode], Optional[StructureNode], float]:

        candidates: List[StructureNode] = []
        seen: set = set()

        def push(node: Optional[StructureNode]) -> None:
            if node is None:
                return
            if node.id in seen:
                return
            seen.add(node.id)
            candidates.append(node)

        push(current)

        if current is not None:
            push(self._registry.get(current.parent_id))
            for sibling in self._registry.siblings_of(current.id):
                push(sibling)
            for child in self._registry.children_of(current.id):
                push(child)

        scored: List[Tuple[StructureNode, float]] = []

        for node in self._registry.all_nodes():
            chunk_sim = self._cos(chunk_embedding, node.embedding)
            sent_sim = self._best_sentence_similarity(
                sentence_embeddings, node
            )
            scored.append((node, max(chunk_sim, sent_sim)))

        scored.sort(key=lambda pair: pair[1], reverse=True)

        best_other_node: Optional[StructureNode] = None
        best_other_sim = 0.0

        for node, sim in scored:
            if current is not None and node.id == current.id:
                continue
            if best_other_node is None:
                best_other_node = node
                best_other_sim = sim
            if node.id not in seen:
                push(node)
            if len(candidates) >= self._top_k_candidates + 6:
                break

        return candidates, best_other_node, best_other_sim

    def _to_node_view(
        self, node: Optional[StructureNode]
    ) -> Optional[NodeView]:
        if node is None:
            return None
        parent = self._registry.get(node.parent_id)
        children = self._registry.children_of(node.id)
        child_labels = tuple(child.name for child in children[:6])
        return NodeView(
            id=node.id,
            label=node.name,
            parent_id=node.parent_id,
            parent_label=parent.name if parent is not None else None,
            depth=node.depth,
            child_labels=child_labels,
            mention_count=node.mention_count,
            last_chunk_index=node.last_chunk_index,
        )

    def _embed(self, text: str):
        return self._model.encode(text, convert_to_tensor=True)

    @staticmethod
    def _cos(a, b) -> float:
        try:
            return float(cos_sim(a, b).item())
        except Exception:
            return 0.0

    def _best_sentence_similarity(
        self,
        sentence_embeddings: List[Any],
        node: Optional[StructureNode],
    ) -> float:
        if node is None or not sentence_embeddings:
            return 0.0
        return max(
            self._cos(emb, node.embedding)
            for emb in sentence_embeddings
        )

    @staticmethod
    def _has_phrase(text: str, phrases) -> bool:
        lowered = " ".join(text.lower().split())
        return any(phrase in lowered for phrase in phrases)

    @staticmethod
    def _is_explicit_transition(text: str) -> bool:
        if not text:
            return False
        tokens = " ".join(text.lower().split()).split()
        head = " ".join(tokens[:6])
        return any(phrase in head for phrase in _NEW_TOPIC_PHRASES)