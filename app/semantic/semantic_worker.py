from __future__ import annotations

import threading
import time
from typing import Any, List, Optional

from app.semantic.local_pass import resolve_local
from app.semantic.semantic_reasoner import (
    SemanticReasoner,
    SemanticReasonerError,
)
from app.semantic.semantic_queue import SemanticQueue
from app.semantic.semantic_throttle import SemanticThrottle
from app.semantic.semantic_types import (
    CandidateConcept,
    Certainty,
    ConceptProposal,
    ConceptType,
    InformationType,
    LocalExtraction,
    Polarity,
    RelationProposal,
    RelationToPrior,
    SemanticContextSnapshot,
    SemanticProposal,
    SemanticRole,
    SentenceSpan,
    is_valid_certainty,
    is_valid_concept_type,
    is_valid_information_type,
    is_valid_polarity,
    is_valid_relation_to_prior,
    is_valid_semantic_role,
)
from app.utils.logger import app_logger


_BACKOFF_SEQUENCE = (5.0, 10.0, 20.0, 40.0, 60.0)
_MAX_RETRIES = 3


class SemanticWorker(threading.Thread):

    def __init__(
        self,
        *,
        queue: SemanticQueue,
        ledger,
        reasoner: Optional[SemanticReasoner],
        embedding_model,
        lsi_registry_getter,
        fallback_reasoner: Optional[SemanticReasoner] = None,
        throttle: Optional[SemanticThrottle] = None,
        name: str = "SemanticWorker",
    ) -> None:

        super().__init__(name=name, daemon=True)

        self._queue = queue
        self._ledger = ledger
        self._reasoner = reasoner
        self._fallback_reasoner = fallback_reasoner
        self._model = embedding_model
        self._get_lsi_node = lsi_registry_getter
        self._throttle = throttle

        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()
        self._queue.close()

    def run(self) -> None:

        app_logger.info("[SemanticWorker] started")

        while not self._stop_event.is_set():

            try:
                batch = self._queue.get_batch()
                if batch is None:
                    break
                self._process_batch(batch)
            except Exception as error:
                app_logger.warning(
                    f"[SemanticWorker] unexpected batch loop error: {error}"
                )
                time.sleep(0.5)
                continue

        app_logger.info("[SemanticWorker] stopped")

    # ---------------------------------------------------------- #
    # BATCH PROCESSING
    # ---------------------------------------------------------- #

    def _process_batch(
        self, batch: List[SemanticContextSnapshot]
    ) -> None:

        local_only = [
            s for s in batch if s.gate_decision == "SAFE_LOCAL"
        ]
        llm_work = [
            s for s in batch if s.gate_decision == "QUEUE_FOR_LLM"
        ]

        for snapshot in local_only:
            try:
                self._commit_local(snapshot)
            except Exception as error:
                app_logger.warning(
                    f"[SemanticWorker] local commit failed: {error}"
                )

        for snapshot in llm_work:
            if self._stop_event.is_set():
                return
            self._process_single_llm(snapshot)

    def _process_single_llm(
        self, snapshot: SemanticContextSnapshot
    ) -> None:

        if self._throttle is not None:
            if not self._throttle.acquire():
                # Defer: requeue the snapshot and continue.
                wait = self._throttle.seconds_until_next_slot()
                app_logger.info(
                    "[SemanticWorker] throttled; deferring snapshot "
                    f"chunk_id={snapshot.chunk_id} wait={wait:.1f}s"
                )
                # Best-effort requeue. If the queue is full, the queue
                # itself decides which item to drop.
                self._queue.put(snapshot)
                # Sleep a short interval to avoid a busy loop when the
                # queue contains only deferred items.
                time.sleep(min(max(wait, 0.25), 2.0))
                return

        proposal, used_fallback = self._call_reasoner_with_backoff(
            snapshot
        )

        if proposal is None:
            app_logger.info(
                "[SemanticWorker] dropping snapshot after retries "
                f"chunk_id={snapshot.chunk_id}"
            )
            return

        self._commit_llm(snapshot, proposal, used_fallback)

    # ---------------------------------------------------------- #
    # REASONER INVOCATION
    # ---------------------------------------------------------- #

    def _call_reasoner_with_backoff(
        self, snapshot: SemanticContextSnapshot
    ) -> tuple[Optional[SemanticProposal], bool]:

        if self._reasoner is None and self._fallback_reasoner is None:
            return None, False

        last_error: Optional[Exception] = None
        attempt = 0
        tried_fallback = False

        while attempt <= _MAX_RETRIES:

            if tried_fallback and self._fallback_reasoner is not None:
                reasoner = self._fallback_reasoner
                using_fallback = True
            elif self._reasoner is not None:
                reasoner = self._reasoner
                using_fallback = False
            elif self._fallback_reasoner is not None:
                reasoner = self._fallback_reasoner
                using_fallback = True
            else:
                return None, False

            try:
                proposal = reasoner.reason(
                    snapshot=snapshot,
                    candidate_concepts=list(snapshot.candidates),
                )
                return proposal, using_fallback

            except SemanticReasonerError as error:

                last_error = error
                reason = str(error).lower()
                is_rate_limit = "429" in reason or "rate limit" in reason

                if (
                    is_rate_limit
                    and not using_fallback
                    and self._fallback_reasoner is not None
                    and not tried_fallback
                ):
                    tried_fallback = True
                    app_logger.info(
                        "[SemanticWorker] primary rate-limited; "
                        "retrying with fallback model for this call"
                    )
                    continue

                delay = self._backoff_delay(attempt, reason)

                app_logger.warning(
                    "[SemanticWorker] reasoner failure "
                    f"attempt={attempt + 1}/{_MAX_RETRIES + 1} "
                    f"delay={delay:.1f}s error={error}"
                )

                attempt += 1
                if attempt > _MAX_RETRIES:
                    break
                if self._stop_event.is_set():
                    break
                time.sleep(delay)

        app_logger.warning(
            f"[SemanticWorker] reasoner exhausted retries: {last_error}"
        )
        return None, False

    @staticmethod
    def _backoff_delay(attempt: int, error_reason: str) -> float:
        import re
        m = re.search(
            r"retry[-_ ]after[^0-9]*([0-9]+(?:\.[0-9]+)?)",
            error_reason,
        )
        if m:
            try:
                return max(1.0, float(m.group(1)))
            except ValueError:
                pass
        idx = min(attempt, len(_BACKOFF_SEQUENCE) - 1)
        return _BACKOFF_SEQUENCE[idx]

    # ---------------------------------------------------------- #
    # COMMIT — LOCAL
    # ---------------------------------------------------------- #

    def _commit_local(
        self, snapshot: SemanticContextSnapshot
    ) -> None:

        extraction = snapshot.local_extraction
        if extraction is None or extraction.action != "RESOLVE":
            return
        if not extraction.subject or not extraction.object_:
            return

        span = self._span_for_extraction(snapshot, extraction)
        if span is None:
            app_logger.warning(
                "[SemanticWorker] local extraction has no matching span; "
                f"chunk_id={snapshot.chunk_id}"
            )
            return

        evidence_id = self._ledger.add_evidence(
            chunk_id=snapshot.chunk_id,
            sentence_index=span.index,
            span_start=span.start,
            span_end=span.end,
            text=span.text,
            relation_to_prior=RelationToPrior.NEW.value,
        )

        subject_concept_id = self._ensure_concept(
            label=extraction.subject,
            concept_type=ConceptType.ENTITY.value,
            lsi_node_id=snapshot.lsi_node_id,
            chunk_id=snapshot.chunk_id,
            evidence_ids=[evidence_id],
        )

        object_concept_id: Optional[str] = None
        object_literal: Optional[str] = None

        if extraction.kind in ("definition", "alias"):
            object_concept_id = self._ensure_concept(
                label=extraction.object_,
                concept_type=ConceptType.UNKNOWN.value,
                lsi_node_id=snapshot.lsi_node_id,
                chunk_id=snapshot.chunk_id,
                evidence_ids=[evidence_id],
            )
        else:
            object_literal = extraction.object_

        predicate = extraction.predicate or "related_to"

        info_type = extraction.information_type
        if not is_valid_information_type(info_type):
            info_type = InformationType.UNKNOWN.value

        self._ledger.add_assertion(
            concept_id=subject_concept_id,
            information_type=info_type,
            semantic_role=SemanticRole.CORE_CONCEPT.value,
            predicate=predicate,
            object_concept_id=object_concept_id,
            object_literal=object_literal,
            polarity=Polarity.POSITIVE.value,
            certainty=Certainty.ASSERTED.value,
            relation_to_prior=RelationToPrior.NEW.value,
            evidence_ids=[evidence_id],
            chunk_id=snapshot.chunk_id,
            confidence_hint=1.0,
        )

    @staticmethod
    def _span_for_extraction(
        snapshot: SemanticContextSnapshot,
        extraction: LocalExtraction,
    ) -> Optional[SentenceSpan]:

        for span in snapshot.sentences:
            candidate = resolve_local(span.text)
            if (
                candidate.action == "RESOLVE"
                and candidate.subject == extraction.subject
                and candidate.object_ == extraction.object_
                and candidate.predicate == extraction.predicate
            ):
                return span

        return snapshot.sentences[0] if snapshot.sentences else None

    # ---------------------------------------------------------- #
    # COMMIT — LLM
    # ---------------------------------------------------------- #

    def _commit_llm(
        self,
        snapshot: SemanticContextSnapshot,
        proposal: SemanticProposal,
        used_fallback: bool,
    ) -> None:

        tmp_to_concept: dict[str, str] = {}

        for concept_proposal in proposal.concepts:

            if not is_valid_concept_type(concept_proposal.concept_type):
                app_logger.warning(
                    "[SemanticWorker] rejected concept with invalid type: "
                    f"{concept_proposal.concept_type}"
                )
                continue

            existing_id = concept_proposal.existing_concept_id

            if existing_id is None:
                existing = self._ledger.find_concept_by_label(
                    concept_proposal.canonical_label
                )
                if existing is not None:
                    existing_id = existing.id

            if existing_id is not None:
                tmp_to_concept[concept_proposal.tmp_id] = existing_id
                self._ledger.record_concept_mention(
                    existing_id, snapshot.chunk_id
                )
                continue

            embedding = None
            try:
                embedding = self._model.encode(
                    concept_proposal.canonical_label,
                    convert_to_tensor=True,
                )
            except Exception:
                embedding = None

            new_id = self._ledger.add_concept(
                canonical_label=concept_proposal.canonical_label,
                aliases=list(concept_proposal.aliases),
                concept_type=concept_proposal.concept_type,
                lsi_node_id=snapshot.lsi_node_id,
                embedding=embedding,
                chunk_id=snapshot.chunk_id,
                evidence_ids=[],
            )
            tmp_to_concept[concept_proposal.tmp_id] = new_id

        for rel in proposal.relations:

            subject_id = tmp_to_concept.get(rel.subject_tmp_id)
            if subject_id is None:
                app_logger.warning(
                    "[SemanticWorker] relation references unknown subject: "
                    f"{rel.subject_tmp_id}"
                )
                continue

            object_id: Optional[str] = None
            object_literal: Optional[str] = None

            if rel.object_tmp_id:
                object_id = tmp_to_concept.get(rel.object_tmp_id)
                if object_id is None:
                    app_logger.warning(
                        "[SemanticWorker] relation references unknown object: "
                        f"{rel.object_tmp_id}"
                    )
                    continue
            else:
                object_literal = rel.object_literal

            evidence_id = self._validate_and_add_evidence(
                snapshot=snapshot,
                relation=rel,
            )
            if evidence_id is None:
                app_logger.warning(
                    "[SemanticWorker] rejected relation with invalid evidence: "
                    f"{rel.predicate}"
                )
                continue

            info_type = (
                rel.information_type
                if is_valid_information_type(rel.information_type)
                else InformationType.UNKNOWN.value
            )
            role = (
                rel.semantic_role
                if is_valid_semantic_role(rel.semantic_role)
                else SemanticRole.UNKNOWN.value
            )
            polarity = (
                rel.polarity
                if is_valid_polarity(rel.polarity)
                else Polarity.POSITIVE.value
            )
            certainty = (
                rel.certainty
                if is_valid_certainty(rel.certainty)
                else Certainty.ASSERTED.value
            )
            rtp = (
                rel.relation_to_prior
                if is_valid_relation_to_prior(rel.relation_to_prior)
                else RelationToPrior.NEW.value
            )

            self._ledger.add_assertion(
                concept_id=subject_id,
                information_type=info_type,
                semantic_role=role,
                predicate=rel.predicate,
                object_concept_id=object_id,
                object_literal=object_literal,
                polarity=polarity,
                certainty=certainty,
                relation_to_prior=rtp,
                evidence_ids=[evidence_id],
                chunk_id=snapshot.chunk_id,
                confidence_hint=float(rel.confidence_hint),
            )

        if used_fallback:
            app_logger.info(
                "[SemanticWorker] committed proposal via fallback reasoner "
                f"chunk_id={snapshot.chunk_id}"
            )

    # ---------------------------------------------------------- #
    # EVIDENCE VALIDATION
    # ---------------------------------------------------------- #

    def _validate_and_add_evidence(
        self,
        *,
        snapshot: SemanticContextSnapshot,
        relation: RelationProposal,
    ) -> Optional[str]:

        sentences = snapshot.sentences
        if not sentences:
            return None

        si = relation.sentence_index
        if not isinstance(si, int) or si < 0 or si >= len(sentences):
            return None

        span = sentences[si]

        start = relation.span_start
        end = relation.span_end

        if (
            not isinstance(start, int)
            or not isinstance(end, int)
            or start < 0
            or end > len(snapshot.chunk_text)
            or start >= end
        ):
            return None

        extracted = snapshot.chunk_text[start:end].strip()
        if not extracted:
            return None

        sentence_start = snapshot.chunk_text.find(span.text)
        if sentence_start < 0:
            sentence_start = span.start

        sentence_end = sentence_start + len(span.text)

        if end <= sentence_start or start >= sentence_end:
            return None

        return self._ledger.add_evidence(
            chunk_id=snapshot.chunk_id,
            sentence_index=si,
            span_start=start,
            span_end=end,
            text=extracted,
            relation_to_prior=relation.relation_to_prior,
        )

    # ---------------------------------------------------------- #
    # CONCEPT HELPERS
    # ---------------------------------------------------------- #

    def _ensure_concept(
        self,
        *,
        label: str,
        concept_type: str,
        lsi_node_id: Optional[str],
        chunk_id: str,
        evidence_ids: list,
    ) -> str:

        label = (label or "").strip()

        existing = self._ledger.find_concept_by_label(label)
        if existing is not None:
            self._ledger.record_concept_mention(
                existing.id, chunk_id, evidence_ids
            )
            return existing.id

        embedding = None
        try:
            embedding = self._model.encode(
                label, convert_to_tensor=True
            )
        except Exception:
            embedding = None

        return self._ledger.add_concept(
            canonical_label=label,
            aliases=[],
            concept_type=concept_type,
            lsi_node_id=lsi_node_id,
            embedding=embedding,
            chunk_id=chunk_id,
            evidence_ids=list(evidence_ids),
        )