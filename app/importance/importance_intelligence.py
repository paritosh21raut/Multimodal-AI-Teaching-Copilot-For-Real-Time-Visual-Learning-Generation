from __future__ import annotations

import threading
import uuid
from typing import Any, List, Optional

from app.importance.developmental_role import order_roles
from app.importance.importance_context import ImportanceContext
from app.importance.importance_types import (
    Centrality,
    Emphasis,
    ImportanceDepthResult,
    ProcessingPath,
)
from app.importance.local_importance import (
    classify_structural_centrality,
    confidence_for,
    detect_developmental_roles,
    detect_explicit_emphasis,
)
from app.utils.logger import app_logger


class ImportanceIntelligence:
    """
    Phase 5 — Importance / Depth Intelligence.

    Synchronous, local-first, fail-open. Produces structured instructional
    metadata per chunk. Does NOT decide slides, does NOT modify transcript,
    does NOT modify LSI, does NOT modify Phase 4.

    LLM path is stubbed behind `_llm_fallback` and currently returns None.
    The local result always stands.
    """

    def __init__(
        self,
        *,
        context_buffer=None,
        semantic_ledger=None,
        enabled: bool = True,
    ) -> None:
        self._enabled = bool(enabled)
        self._context_buffer = context_buffer
        self._semantic_ledger = semantic_ledger

        self._lock = threading.RLock()
        self._results: List[ImportanceDepthResult] = []
        self._max_results = 512

    # ---------------------------------------------------------- #
    # LIFECYCLE
    # ---------------------------------------------------------- #

    def reset(self) -> None:
        with self._lock:
            self._results.clear()

    # ---------------------------------------------------------- #
    # ENTRY POINT
    # ---------------------------------------------------------- #

    def evaluate(
        self,
        *,
        chunk_text: str,
        topic_decision: Any,
    ) -> Optional[ImportanceDepthResult]:
        """
        Fail-open. On any internal error, returns None and logs a warning.
        The lecture pipeline continues.
        """
        if not self._enabled:
            return None

        try:
            context = self._build_context(
                chunk_text=chunk_text,
                topic_decision=topic_decision,
            )
            result = self._analyze(context)
            self._record(result)
            return result
        except Exception as error:
            app_logger.warning(
                f"[ImportanceIntelligence] evaluate failed (fail-open): {error}"
            )
            return None

    # ---------------------------------------------------------- #
    # CONTEXT
    # ---------------------------------------------------------- #

    def _build_context(
        self,
        *,
        chunk_text: str,
        topic_decision: Any,
    ) -> ImportanceContext:

        chunk_id = str(uuid.uuid4())
        text = (chunk_text or "").strip()

        rolling_context = ""
        if self._context_buffer is not None:
            try:
                rolling_context = self._context_buffer.rolling_context()
            except Exception:
                rolling_context = ""

        relation = getattr(topic_decision, "relation", None)
        node_id = getattr(topic_decision, "node_id", None)
        node_label = getattr(topic_decision, "topic", None)
        parent_id = getattr(topic_decision, "parent_node_id", None)
        depth = getattr(topic_decision, "depth", None)

        concept_label = self._guess_concept_label(text)

        prior_assertions: List[str] = []
        mention_count = 0
        first_seen = True

        if self._semantic_ledger is not None and concept_label:
            try:
                concept = self._semantic_ledger.find_concept_by_label(
                    concept_label
                )
                if concept is not None:
                    mention_count = int(concept.mention_count or 0)
                    first_seen = mention_count <= 1
                    assertions = (
                        self._semantic_ledger.all_assertions_for_concept(
                            concept.id
                        )
                    )
                    prior_assertions = [
                        (a.object_literal or a.predicate or "")
                        for a in assertions
                        if (a.object_literal or a.predicate)
                    ]
            except Exception:
                pass

        recent: List[str] = []
        if self._semantic_ledger is not None:
            try:
                concepts = self._semantic_ledger.all_concepts()
                concepts_sorted = sorted(
                    concepts,
                    key=lambda c: c.last_seen_chunk or "",
                    reverse=True,
                )
                recent = [c.canonical_label for c in concepts_sorted[:8]]
            except Exception:
                recent = []

        return ImportanceContext(
            chunk_id=chunk_id,
            chunk_text=text,
            rolling_context=rolling_context,
            lsi_relation=relation,
            lsi_node_id=node_id,
            lsi_node_label=node_label,
            lsi_parent_node_id=parent_id,
            lsi_parent_label=None,
            lsi_depth=depth,
            concept_under_annotation=concept_label,
            prior_concept_labels=tuple(recent),
            prior_assertions_for_concept=tuple(prior_assertions),
            concept_mention_count=mention_count,
            concept_first_seen=first_seen,
            current_assertion=None,
            recent_concept_labels=tuple(recent),
            candidate_labels=tuple(recent),
        )

    @staticmethod
    def _guess_concept_label(text: str) -> Optional[str]:
        """
        Very narrow noun-phrase guess for the subject of the chunk.
        Used only as a lookup key into the Phase 4 ledger. Never used
        as sole evidence for CORE.
        """
        if not text:
            return None
        lowered = " ".join(text.lower().split())
        for lead in ("the ", "a ", "an ", "this ", "these ", "those "):
            if lowered.startswith(lead):
                lowered = lowered[len(lead):]
                break
        tokens = lowered.split()[:3]
        if not tokens:
            return None
        guess = " ".join(t.strip(".,;:!?()[]{}\"'") for t in tokens).strip()
        return guess or None

    # ---------------------------------------------------------- #
    # ANALYSIS
    # ---------------------------------------------------------- #

    def _analyze(
        self, context: ImportanceContext
    ) -> ImportanceDepthResult:

        text = context.chunk_text

        emphasis, evidence = detect_explicit_emphasis(text)

        roles = order_roles(
            detect_developmental_roles(
                text, lsi_relation=context.lsi_relation
            )
        )

        centrality, reason = classify_structural_centrality(
            text=text,
            concept_label=context.concept_under_annotation,
            concept_first_seen=context.concept_first_seen,
            concept_mention_count=context.concept_mention_count,
            prior_assertions_for_concept=context.prior_assertions_for_concept,
            lsi_relation=context.lsi_relation,
            lsi_node_id=context.lsi_node_id,
        )

        if "META" in roles and centrality != Centrality.INCIDENTAL.value:
            centrality = Centrality.INCIDENTAL.value
            reason = "meta_statement_override"

        llm_result = self._llm_fallback(context)
        if llm_result is not None:
            pass

        confidence = confidence_for(
            centrality=centrality,
            roles=roles,
            emphasis=emphasis,
        )

        return ImportanceDepthResult(
            chunk_id=context.chunk_id,
            assertion_id=None,
            explicit_emphasis=emphasis,
            emphasis_evidence=evidence,
            structural_centrality=centrality,
            developmental_roles=roles,
            confidence=confidence,
            reason=reason,
            processing_path=ProcessingPath.LOCAL.value,
        )

    def _llm_fallback(
        self, context: ImportanceContext
    ) -> Optional[ImportanceDepthResult]:
        return None

    # ---------------------------------------------------------- #
    # BOOKKEEPING
    # ---------------------------------------------------------- #

    def _record(self, result: ImportanceDepthResult) -> None:
        with self._lock:
            self._results.append(result)
            if len(self._results) > self._max_results:
                self._results = self._results[-self._max_results:]

    def latest(self) -> Optional[ImportanceDepthResult]:
        with self._lock:
            return self._results[-1] if self._results else None

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "count": len(self._results),
                "results": [r.to_dict() for r in self._results],
            }


importance_intelligence = ImportanceIntelligence()