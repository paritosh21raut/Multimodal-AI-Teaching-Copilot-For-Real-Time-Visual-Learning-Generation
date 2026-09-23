from __future__ import annotations

from typing import Any, List, Optional, Tuple

from app.semantic.semantic_types import (
    CandidateConcept,
    LocalExtraction,
    SentenceSpan,
)


class SemanticGate:
    """
    Decides whether a chunk is:
    - SAFE_LOCAL: deterministic extraction is available and safe.
    - QUEUE_FOR_LLM: content is ambiguous or structurally significant.
    - SKIP: content is clearly irrelevant, empty, or repetitive.

    Deterministic. No LLM calls.
    """

    def __init__(
        self,
        *,
        min_words_for_llm: int = 5,
        repeat_embedding_floor: float = 0.86,
    ) -> None:
        self._min_words_for_llm = int(min_words_for_llm)
        self._repeat_embedding_floor = float(repeat_embedding_floor)

    def decide(
        self,
        *,
        chunk_text: str,
        sentences: Tuple[SentenceSpan, ...],
        lsi_relation: Optional[str],
        local_extraction: Optional[LocalExtraction],
        candidates: List[CandidateConcept],
    ) -> str:

        text = (chunk_text or "").strip()

        # 1) Empty is always SKIP.
        if not text:
            return "SKIP"

        # 2) Irrelevant structural signal is always SKIP.
        if lsi_relation == "irrelevant":
            return "SKIP"

        # 3) Structural transitions are always worth LLM adjudication,
        #    regardless of chunk length. A new topic / subtopic / sibling
        #    / return is by definition meaningful context.
        if lsi_relation in {"new_topic", "subtopic", "sibling", "return"}:
            return "QUEUE_FOR_LLM"

        # 4) Too short to be meaningful, and no deterministic extraction
        #    is available.
        if (
            len(text.split()) < self._min_words_for_llm
            and local_extraction is None
        ):
            return "SKIP"

        # 5) Safe local deterministic extraction.
        if (
            local_extraction is not None
            and local_extraction.action == "RESOLVE"
            and local_extraction.subject
            and local_extraction.object_
        ):
            return "SAFE_LOCAL"

        # 6) If retrieval found nothing confidently relevant, still
        #    enqueue because the chunk may introduce a new concept.
        if not candidates:
            return "QUEUE_FOR_LLM"

        best = candidates[0]

        # 7) Very strong lexical + embedding match to an existing
        #    concept with no new information -> probable repetition.
        if (
            best.lexical_score >= 1.0
            and best.embedding_score >= self._repeat_embedding_floor
        ):
            return "SKIP"

        return "QUEUE_FOR_LLM"