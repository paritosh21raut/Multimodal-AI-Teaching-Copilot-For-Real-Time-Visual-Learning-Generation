from __future__ import annotations

import threading
from typing import List, Optional

from app.slide_decision.slide_decision_context import SlideDecisionContext
from app.slide_decision.slide_decision_types import (
    SlideDecisionAction,
    SlideDecisionResult,
)
from app.utils.logger import app_logger


# ---------------------------------------------------------- #
# CONSTANTS
# ---------------------------------------------------------- #

_CONTINUATION_LSI = frozenset({"continuation", "detail", "related", "return"})
_STRUCTURAL_TRANSITION_LSI = frozenset({"new_topic", "subtopic", "sibling"})

# Similarity threshold used by R8 branch (b). Derived from existing LSI
# thresholds in configs/config.yaml; not tuned here.
_R8_SIMILARITY_CEILING = 0.65

_META_ROLE = "META"
_UNKNOWN_ROLE = "UNKNOWN"
_INCIDENTAL = "INCIDENTAL"
_CORE = "CORE"
_SUPPORTING = "SUPPORTING"


class SlideDecisionEngine:
    """
    Phase 6 Slide Decision Intelligence.

    Pure, deterministic, fail-open. Consumes SlideDecisionContext and
    returns SlideDecisionResult. Never raises out of `decide()`. Never
    calls an LLM. Never touches slide state, content generation, or the
    PPT renderer.

    Rule order (effective):
        R0  fail-open wrapper
        R1  empty / invalid input
        R2  LSI irrelevant
        R3  incidental / meta
        R4  first slide
        R6  substantive new topic
        R7  explicit subtopic introduction
        R8  meaningful conceptual novelty / new unit
        R9  develops current unit
        R10 fallback

    R5 (duplicate_or_redundant) was removed because we do not have
    reliable slide-content/concept-level duplicate detection. Genuine
    repeated content conservatively yields UPDATE_CURRENT_SLIDE.
    """

    def __init__(self, *, enabled: bool = True) -> None:
        self._enabled = bool(enabled)
        self._lock = threading.RLock()
        self._last_decision: Optional[str] = None
        self._last_topic: Optional[str] = None

    # ------------------------------------------------------ #
    # LIFECYCLE
    # ------------------------------------------------------ #

    def reset(self) -> None:
        with self._lock:
            self._last_decision = None
            self._last_topic = None

    # ------------------------------------------------------ #
    # ENTRY POINT
    # ------------------------------------------------------ #

    def decide(self, context: SlideDecisionContext) -> SlideDecisionResult:
        """
        Fail-open. Any internal error returns a safe result. This method
        must never raise, regardless of what `context` is.
        """
        if not self._enabled:
            return self._safe_default(context, reason="engine_disabled")

        try:
            result = self._decide_inner(context)
        except Exception as error:
            app_logger.warning(
                f"[SlideDecisionEngine] decide failed (fail-open): {error}"
            )
            try:
                return self._safe_default(
                    context,
                    reason=f"engine_exception:{type(error).__name__}",
                )
            except Exception as nested:
                # The fallback must never itself raise.
                app_logger.warning(
                    "[SlideDecisionEngine] safe_default failed: "
                    f"{nested}"
                )
                return SlideDecisionResult(
                    decision=SlideDecisionAction.KEEP_CURRENT_SLIDE.value,
                    reason="engine_catastrophic_fallback",
                    confidence_hint=0.0,
                )

        try:
            self._record(result, context)
        except Exception:
            pass
        return result

    # ------------------------------------------------------ #
    # SAFE DEFAULT (defensive; must not raise)
    # ------------------------------------------------------ #

    @staticmethod
    def _safe_default(
        context: object, *, reason: str
    ) -> SlideDecisionResult:
        has_slide = bool(getattr(context, "has_current_slide", False))
        lsi_new_topic = bool(getattr(context, "lsi_is_new_topic", False))

        if has_slide:
            action = SlideDecisionAction.KEEP_CURRENT_SLIDE.value
        elif lsi_new_topic:
            action = SlideDecisionAction.NEW_SLIDE.value
        else:
            action = SlideDecisionAction.UPDATE_CURRENT_SLIDE.value

        roles = getattr(context, "phase5_developmental_roles", []) or []
        try:
            roles = list(roles)
        except Exception:
            roles = []

        return SlideDecisionResult(
            decision=action,
            reason=reason,
            confidence_hint=0.0,
            current_slide_id=getattr(context, "current_slide_number", None),
            current_slide_topic=getattr(context, "current_slide_topic", None),
            target_topic=getattr(context, "lsi_topic", None),
            lsi_relation=getattr(context, "lsi_relation", None),
            lsi_is_new_topic=lsi_new_topic,
            lsi_is_new_subtopic=bool(
                getattr(context, "lsi_is_new_subtopic", False)
            ),
            lsi_similarity=getattr(context, "lsi_similarity", None),
            concept_label=getattr(context, "concept_label", None),
            concept_first_seen=getattr(context, "concept_first_seen", None),
            concept_prior_assertions_count=getattr(
                context, "concept_prior_assertions_count", None
            ),
            centrality=getattr(context, "phase5_centrality", None),
            developmental_roles=roles,
            explicit_emphasis=getattr(
                context, "phase5_explicit_emphasis", None
            ),
            previous_decision=getattr(context, "previous_decision", None),
            signals={"safe_default": True},
        )

    # ------------------------------------------------------ #
    # INNER
    # ------------------------------------------------------ #

    def _decide_inner(
        self, context: SlideDecisionContext
    ) -> SlideDecisionResult:

        base = self._base_result(context)

        # R1 — empty / invalid input.
        chunk_text = getattr(context, "chunk_text", "") or ""
        if not chunk_text.strip():
            return self._emit(
                base, SlideDecisionAction.KEEP_CURRENT_SLIDE,
                "empty_or_invalid",
            )

        # R2 — LSI irrelevant.
        if getattr(context, "lsi_relation", None) == "irrelevant":
            return self._emit(
                base, SlideDecisionAction.KEEP_CURRENT_SLIDE,
                "lsi_irrelevant",
            )

        # R3 — incidental or meta content.
        if getattr(context, "phase5_centrality", None) == _INCIDENTAL:
            return self._emit(
                base, SlideDecisionAction.KEEP_CURRENT_SLIDE,
                "incidental_content",
            )

        roles = set(
            getattr(context, "phase5_developmental_roles", None) or []
        )
        if _META_ROLE in roles:
            return self._emit(
                base, SlideDecisionAction.KEEP_CURRENT_SLIDE,
                "meta_content",
            )

        # R4 — first slide.
        if (
            not getattr(context, "has_current_slide", False)
            and getattr(context, "lsi_is_new_topic", False)
        ):
            return self._emit(
                base, SlideDecisionAction.NEW_SLIDE, "first_slide"
            )

        # R6 — substantive new topic.
        if self._is_substantive_new_topic(context):
            return self._emit(
                base, SlideDecisionAction.NEW_SLIDE,
                "substantive_new_topic",
            )

        # R7 — explicit subtopic introduction.
        if (
            getattr(context, "lsi_relation", None) == "subtopic"
            and getattr(context, "lsi_is_new_subtopic", False)
            and getattr(context, "phase5_centrality", None) == _CORE
        ):
            return self._emit(
                base, SlideDecisionAction.NEW_SLIDE,
                "explicit_subtopic_introduction",
            )

        # R8 — revised: meaningful novelty that begins a new unit.
        if self._is_novel_new_unit(context):
            return self._emit(
                base, SlideDecisionAction.NEW_SLIDE,
                "novel_concept_new_unit",
            )

        # R9 — develops the current unit.
        if self._develops_current_unit(context):
            return self._emit(
                base, SlideDecisionAction.UPDATE_CURRENT_SLIDE,
                "develops_current_unit",
            )

        # R10 — fallback.
        return self._emit(
            base, SlideDecisionAction.KEEP_CURRENT_SLIDE,
            "no_strong_signal",
        )

    # ------------------------------------------------------ #
    # RULE HELPERS
    # ------------------------------------------------------ #

    @staticmethod
    def _is_substantive_new_topic(context: SlideDecisionContext) -> bool:
        rel = getattr(context, "lsi_relation", None)
        if rel not in {"new_topic", "sibling"}:
            return False
        has_slide = bool(getattr(context, "has_current_slide", False))
        topic = getattr(context, "lsi_topic", None)
        cur_topic = getattr(context, "current_slide_topic", None)
        if has_slide and topic == cur_topic:
            return False
        centrality = getattr(context, "phase5_centrality", None)
        if centrality is None:
            return False
        if centrality == _INCIDENTAL:
            return False
        roles = getattr(context, "phase5_developmental_roles", None) or []
        if not roles or roles == [_UNKNOWN_ROLE]:
            return False
        return True

    @staticmethod
    def _is_novel_new_unit(context: SlideDecisionContext) -> bool:
        if not getattr(context, "concept_label", None):
            return False
        if getattr(context, "concept_first_seen", None) is not True:
            return False
        if (getattr(context, "concept_prior_assertions_count", None) or 0) != 0:
            return False

        # Topic must have moved off the current slide's topic.
        has_slide = bool(getattr(context, "has_current_slide", False))
        topic = getattr(context, "lsi_topic", None)
        cur_topic = getattr(context, "current_slide_topic", None)
        if has_slide and topic == cur_topic:
            return False

        rel = getattr(context, "lsi_relation", None)

        # Structural corroboration (a): LSI transition.
        if rel in _STRUCTURAL_TRANSITION_LSI:
            return True

        # Structural corroboration (b): CORE continuation with similarity
        # below the ceiling and topic separation (already required above).
        if (
            rel == "continuation"
            and getattr(context, "phase5_centrality", None) == _CORE
        ):
            sim = getattr(context, "lsi_similarity", None)
            if sim is not None and sim < _R8_SIMILARITY_CEILING:
                return True

        return False

    @staticmethod
    def _develops_current_unit(context: SlideDecisionContext) -> bool:
        if not getattr(context, "has_current_slide", False):
            return False
        centrality = getattr(context, "phase5_centrality", None)
        if centrality is None:
            return False
        if centrality not in {_SUPPORTING, _CORE}:
            return False
        rel = getattr(context, "lsi_relation", None)
        if rel in _CONTINUATION_LSI:
            return True
        if rel in {"new_topic", "sibling"} and (
            getattr(context, "lsi_topic", None)
            == getattr(context, "current_slide_topic", None)
        ):
            return True
        return False

    # ------------------------------------------------------ #
    # RESULT BUILDING
    # ------------------------------------------------------ #

    @staticmethod
    def _base_result(
        context: SlideDecisionContext,
    ) -> SlideDecisionResult:
        roles = getattr(context, "phase5_developmental_roles", []) or []
        try:
            roles = list(roles)
        except Exception:
            roles = []

        return SlideDecisionResult(
            decision=SlideDecisionAction.KEEP_CURRENT_SLIDE.value,
            reason="unset",
            confidence_hint=0.0,
            current_slide_id=getattr(context, "current_slide_number", None),
            current_slide_topic=getattr(context, "current_slide_topic", None),
            target_topic=getattr(context, "lsi_topic", None),
            lsi_relation=getattr(context, "lsi_relation", None),
            lsi_is_new_topic=bool(
                getattr(context, "lsi_is_new_topic", False)
            ),
            lsi_is_new_subtopic=bool(
                getattr(context, "lsi_is_new_subtopic", False)
            ),
            lsi_similarity=getattr(context, "lsi_similarity", None),
            concept_label=getattr(context, "concept_label", None),
            concept_first_seen=getattr(context, "concept_first_seen", None),
            concept_prior_assertions_count=getattr(
                context, "concept_prior_assertions_count", None
            ),
            centrality=getattr(context, "phase5_centrality", None),
            developmental_roles=roles,
            explicit_emphasis=getattr(
                context, "phase5_explicit_emphasis", None
            ),
            previous_decision=getattr(context, "previous_decision", None),
        )

    @staticmethod
    def _emit(
        base: SlideDecisionResult,
        action: SlideDecisionAction,
        reason: str,
    ) -> SlideDecisionResult:
        base.decision = action.value
        base.reason = reason
        base.confidence_hint = _confidence_for(action, reason)
        base.signals = {"rule": reason}
        return base

    # ------------------------------------------------------ #
    # BOOKKEEPING
    # ------------------------------------------------------ #

    def _record(
        self, result: SlideDecisionResult, context: SlideDecisionContext
    ) -> None:
        with self._lock:
            self._last_decision = result.decision
            self._last_topic = getattr(context, "lsi_topic", None)

    def last_decision(self) -> Optional[str]:
        with self._lock:
            return self._last_decision

    def last_topic(self) -> Optional[str]:
        with self._lock:
            return self._last_topic


def _confidence_for(action: SlideDecisionAction, reason: str) -> float:
    # Internal heuristic, not calibrated. Documented in the dataclass.
    if action == SlideDecisionAction.NEW_SLIDE:
        return 0.8
    if action == SlideDecisionAction.UPDATE_CURRENT_SLIDE:
        return 0.75
    if action == SlideDecisionAction.KEEP_CURRENT_SLIDE:
        if reason in {
            "empty_or_invalid",
            "lsi_irrelevant",
            "incidental_content",
            "meta_content",
        }:
            return 0.85
        return 0.6
    return 0.0


slide_decision_engine = SlideDecisionEngine()