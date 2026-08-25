from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class SlideAction(str, Enum):
    IGNORE = "ignore"
    CREATE = "create"
    UPDATE = "update"


@dataclass(frozen=True)
class SlideDecision:
    action: SlideAction
    reason: str
    meaningful: bool
    estimated_words: int
    slide_word_count: int
    update_count: int


class SlideDecisionEngine:
    """
    Deterministic pre-LLM decision layer.

    It decides whether a meaningful lecture chunk should:
    - be ignored,
    - create a new slide,
    - update the current slide.

    It does NOT call an LLM.
    """

    _FILLER_PATTERNS = (
        r"^(okay|ok|alright|right|yes|yeah|hmm|um|uh|so|well)\.?$",
        r"^(let me see|let me check|give me a second|one second)\.?$",
        r"^(i don't know|i am not sure|i'm not sure)\.?$",
        r"^(sorry|i'm sorry|excuse me)\.?$",
        r"^(can you hear me|is this working)\.?$",
        r"^(as i said|as we said|you know|you see)\.?$",
    )

    _SLIDE_BREAK_PATTERNS = (
        "next slide",
        "let's move to",
        "let us move to",
        "moving on to",
        "moving on",
        "next we will",
        "next we'll",
        "next let us",
        "next let's",
        "now let's discuss",
        "now let us discuss",
        "now let's learn",
        "now let us learn",
        "now let's look at",
        "now let us look at",
        "another topic",
        "another concept",
        "another type",
        "coming to",
    )

    _LOW_VALUE_PREFIXES = (
        "i forgot",
        "i have to check",
        "i need to check",
        "let me check",
        "i don't remember",
        "i do not remember",
        "i was saying",
        "where was i",
        "what was i saying",
    )

    def __init__(
        self,
        max_slide_source_words: int = 120,
        max_updates_per_slide: int = 4,
        min_meaningful_words: int = 4,
    ) -> None:

        self.max_slide_source_words = (
            max_slide_source_words
        )

        self.max_updates_per_slide = (
            max_updates_per_slide
        )

        self.min_meaningful_words = (
            min_meaningful_words
        )

        self.reset()

    # ==========================================================
    # RESET
    # ==========================================================

    def reset(self) -> None:

        self.slide_word_count = 0

        self.update_count = 0

        self.last_chunk_key: Optional[str] = None

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        return " ".join(
            text.lower().strip().split()
        )

    @staticmethod
    def _word_count(
        text: str,
    ) -> int:

        return len(
            re.findall(
                r"\b\w+(?:[-']\w+)*\b",
                text,
            )
        )

    def _is_filler(
        self,
        text: str,
    ) -> bool:

        normalized = self._normalize(
            text
        )

        for pattern in self._FILLER_PATTERNS:

            if re.fullmatch(
                pattern,
                normalized,
                flags=re.IGNORECASE,
            ):

                return True

        return False

    def _is_low_value(
        self,
        text: str,
    ) -> bool:

        normalized = self._normalize(
            text
        )

        if not normalized:
            return True

        if self._is_filler(
            normalized
        ):
            return True

        if (
            len(
                normalized.split()
            )
            < self.min_meaningful_words
        ):
            return True

        return normalized.startswith(
            self._LOW_VALUE_PREFIXES
        )

    def _has_slide_break_signal(
        self,
        text: str,
    ) -> bool:

        normalized = self._normalize(
            text
        )

        return any(
            phrase in normalized
            for phrase
            in self._SLIDE_BREAK_PATTERNS
        )

    # ==========================================================
    # DECISION
    # ==========================================================

    def decide(
        self,
        transcript: str,
        is_new_topic: bool,
        current_slide_exists: bool,
    ) -> SlideDecision:

        text = " ".join(
            transcript.strip().split()
        )

        words = self._word_count(
            text
        )

        if not text:

            return SlideDecision(
                action=SlideAction.IGNORE,
                reason="empty_chunk",
                meaningful=False,
                estimated_words=0,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        chunk_key = self._normalize(
            text
        )

        if (
            chunk_key
            == self.last_chunk_key
        ):

            return SlideDecision(
                action=SlideAction.IGNORE,
                reason="duplicate_chunk",
                meaningful=False,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if self._is_low_value(
            text
        ):

            return SlideDecision(
                action=SlideAction.IGNORE,
                reason="low_value_speech",
                meaningful=False,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if not current_slide_exists:

            return SlideDecision(
                action=SlideAction.CREATE,
                reason="first_meaningful_slide_content",
                meaningful=True,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if is_new_topic:

            return SlideDecision(
                action=SlideAction.CREATE,
                reason="new_topic_detected",
                meaningful=True,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if self._has_slide_break_signal(
            text
        ):

            return SlideDecision(
                action=SlideAction.CREATE,
                reason="explicit_slide_transition",
                meaningful=True,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if (
            self.slide_word_count > 0
            and (
                self.slide_word_count
                + words
                > self.max_slide_source_words
            )
        ):

            return SlideDecision(
                action=SlideAction.CREATE,
                reason="current_slide_capacity_reached",
                meaningful=True,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        if (
            self.update_count
            >= self.max_updates_per_slide
        ):

            return SlideDecision(
                action=SlideAction.CREATE,
                reason="maximum_updates_for_slide_reached",
                meaningful=True,
                estimated_words=words,
                slide_word_count=self.slide_word_count,
                update_count=self.update_count,
            )

        return SlideDecision(
            action=SlideAction.UPDATE,
            reason="meaningful_same_topic_content",
            meaningful=True,
            estimated_words=words,
            slide_word_count=self.slide_word_count,
            update_count=self.update_count,
        )

    # ==========================================================
    # RECORD SUCCESS
    # ==========================================================

    def record_success(
        self,
        transcript: str,
        action: SlideAction,
    ) -> None:

        text = " ".join(
            transcript.strip().split()
        )

        if not text:
            return

        self.last_chunk_key = (
            self._normalize(text)
        )

        words = self._word_count(
            text
        )

        if action == SlideAction.CREATE:

            self.slide_word_count = words

            self.update_count = 0

            return

        if action == SlideAction.UPDATE:

            self.slide_word_count += words

            self.update_count += 1