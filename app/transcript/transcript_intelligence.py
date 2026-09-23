from __future__ import annotations

import re
import threading
from dataclasses import dataclass
from typing import List, Optional


_WHITESPACE_RE = re.compile(r"\s+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")

_FILLER_TOKENS = {
    "uh",
    "um",
    "erm",
    "ah",
    "hmm",
    "mm",
}

_NOISE_ONLY_WORDS = {
    "and",
    "so",
    "okay",
    "ok",
    "yes",
    "yeah",
    "this",
    "that",
    "the",
    "a",
    "an",
    "but",
    "or",
    "then",
    "there",
    "here",
}


@dataclass
class AnalysisChunk:
    """Analysis-ready text produced by TranscriptIntelligence."""

    text: str
    sentence_count: int
    is_forced: bool


class TranscriptIntelligence:
    """
    Cleans raw Whisper output and produces analysis-ready chunks.

    Two distinct outputs are maintained:

    - authoritative transcript: chronological, close to what Whisper
      produced, only lightly normalized.
    - analysis chunks: only meaningful, non-duplicate material that is
      safe to send downstream.

    Thread-safe.
    """

    def __init__(
        self,
        min_words_per_chunk: int = 20,
        max_sentences_per_chunk: int = 4,
    ) -> None:

        self._min_words = int(min_words_per_chunk)
        self._max_sentences = int(max_sentences_per_chunk)

        self._lock = threading.RLock()

        # Authoritative transcript for the current lecture.
        self._paragraphs: List[str] = []
        self._current = ""

        # Sentences already dispatched downstream.
        self._analyzed: List[str] = []
        self._analyzed_set = set()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def normalize_whitespace(text: str) -> str:

        if not text:
            return ""

        return _WHITESPACE_RE.sub(" ", text).strip()

    @classmethod
    def clean_asr(cls, text: str) -> str:

        text = cls.normalize_whitespace(text)

        if not text:
            return ""

        text = re.sub(
            r"\b(\w+)(\s+\1\b)+",
            r"\1",
            text,
            flags=re.IGNORECASE,
        )

        tokens = text.split()
        cleaned_tokens = []

        for token in tokens:

            bare = token.strip(".,!?;:").lower()

            if bare in _FILLER_TOKENS:
                continue

            cleaned_tokens.append(token)

        text = " ".join(cleaned_tokens)

        text = re.sub(r"\s+([,.!?;:])", r"\1", text)

        return text.strip()

    @staticmethod
    def split_sentences(text: str) -> List[str]:

        if not text:
            return []

        parts = _SENTENCE_SPLIT_RE.split(text)

        return [
            part.strip()
            for part in parts
            if part.strip()
        ]

    # ==========================================================
    # INCREMENTAL WHISPER DELTA
    # ==========================================================

    @staticmethod
    def extract_new_suffix(
        previous: str,
        current: str,
    ) -> str:

        previous = TranscriptIntelligence.normalize_whitespace(previous)
        current = TranscriptIntelligence.normalize_whitespace(current)

        if not previous:
            return current

        if not current:
            return ""

        if current == previous:
            return ""

        if current.startswith(previous):

            return current[len(previous):].strip()

        prev_words = previous.split()
        curr_words = current.split()

        max_overlap = min(len(prev_words), len(curr_words))

        for size in range(max_overlap, 0, -1):

            if prev_words[-size:] == curr_words[:size]:

                return " ".join(curr_words[size:]).strip()

        return current

    # ==========================================================
    # PUBLIC PROCESSING
    # ==========================================================

    def process(
        self,
        raw_transcript: str,
        *,
        force: bool = False,
    ) -> Optional[AnalysisChunk]:

        cleaned = self.clean_asr(raw_transcript)

        if not cleaned:
            return None

        with self._lock:

            new_text = self.extract_new_suffix(
                self._current,
                cleaned,
            )

            if new_text:

                if self._current:
                    self._current = (
                        self._current + " " + new_text
                    )
                else:
                    self._current = new_text

                self._current = self.normalize_whitespace(
                    self._current
                )

            # --------------------------------------------------
            # Candidate sentences: any sentence in the current
            # paragraph that has not yet been dispatched.
            # --------------------------------------------------

            sentences = self.split_sentences(
                self._current
            )

            if not sentences:
                return None

            pending: List[str] = []

            for sentence in sentences:

                key = sentence.lower()

                if key in self._analyzed_set:
                    continue

                # Non-forced path only accepts complete sentences.
                if not force and sentence[-1] not in ".!?":
                    continue

                pending.append(sentence)

            if not pending:
                return None

            # --------------------------------------------------
            # A trailing incomplete sentence is only eligible when
            # force=True. If it is excluded, we must not include it
            # in the emitted chunk so it can be re-emitted later.
            # --------------------------------------------------

            if not force:

                if pending[-1][-1] not in ".!?":
                    pending = pending[:-1]

                if not pending:
                    return None

            total_words = sum(
                len(sentence.split())
                for sentence in pending
            )

            if (
                not force
                and total_words < self._min_words
            ):
                return None

            chunk_sentences = pending[
                : self._max_sentences
            ]

            chunk_text = " ".join(
                chunk_sentences
            ).strip()

            if not chunk_text:
                return None

            if self._is_noise_only(chunk_text):
                return None

            return AnalysisChunk(
                text=chunk_text,
                sentence_count=len(chunk_sentences),
                is_forced=force,
            )

    def mark_analyzed(self, text: str) -> None:

        if not text:
            return

        sentences = self.split_sentences(
            self.clean_asr(text)
        )

        if not sentences:
            return

        with self._lock:

            for sentence in sentences:

                key = sentence.lower()

                if key in self._analyzed_set:
                    continue

                self._analyzed.append(sentence)
                self._analyzed_set.add(key)

            if len(self._analyzed) > 200:

                overflow = (
                    len(self._analyzed) - 200
                )

                removed = self._analyzed[:overflow]

                self._analyzed = self._analyzed[overflow:]

                for sentence in removed:
                    self._analyzed_set.discard(
                        sentence.lower()
                    )

    # ==========================================================
    # PARAGRAPH LIFECYCLE
    # ==========================================================

    def finalize_paragraph(self) -> None:

        with self._lock:

            if not self._current.strip():
                return

            self._paragraphs.append(
                self._current.strip()
            )

            self._current = ""

    def start_new_topic(self, boundary_text: str) -> None:

        self.finalize_paragraph()

        boundary = self.clean_asr(
            boundary_text or ""
        )

        with self._lock:

            if boundary:
                self._current = boundary

    # ==========================================================
    # ACCESSORS
    # ==========================================================

    def authoritative_transcript(self) -> str:

        with self._lock:

            parts = list(self._paragraphs)

            if self._current.strip():
                parts.append(self._current.strip())

            return "\n\n".join(parts)

    def current_paragraph(self) -> str:

        with self._lock:
            return self._current

    def reset(self) -> None:

        with self._lock:

            self._paragraphs.clear()
            self._current = ""
            self._analyzed.clear()
            self._analyzed_set.clear()

    # ==========================================================
    # HELPERS
    # ==========================================================

    @staticmethod
    def _is_noise_only(text: str) -> bool:

        tokens = [
            token.strip(".,!?;:").lower()
            for token in text.split()
        ]

        tokens = [
            token
            for token in tokens
            if token
        ]

        if not tokens:
            return True

        return all(
            token in _NOISE_ONLY_WORDS
            or token in _FILLER_TOKENS
            for token in tokens
        )


transcript_intelligence = TranscriptIntelligence()