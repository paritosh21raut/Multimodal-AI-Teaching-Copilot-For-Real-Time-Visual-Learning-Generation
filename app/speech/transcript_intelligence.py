from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import List, Optional, Tuple


@dataclass
class TranscriptCorrection:
    original: str
    replacement: str
    correction_type: str
    confidence: float


@dataclass
class TranscriptResult:
    original_text: str
    refined_text: str
    changed: bool
    quality_score: float
    corrections: List[TranscriptCorrection]


class TranscriptIntelligence:
    """
    Generic transcript refinement layer between Whisper
    and lecture-level semantic intelligence.

    This component is intentionally topic-agnostic.

    Responsibilities:

        Whisper transcript
            ↓
        normalization
            ↓
        filler removal
            ↓
        repetition cleanup
            ↓
        boundary/context repair
            ↓
        generic terminology normalization
            ↓
        context-aware spelling correction
            ↓
        punctuation cleanup
            ↓
        quality estimation

    It does NOT contain knowledge about a specific lecture topic.
    """

    # ==========================================================
    # FILLERS
    # ==========================================================

    _FILLER_PATTERNS = (
        r"\b(um+|uh+|er+|ah+)\b",
        r"\byou know\b",
        r"\bi mean\b",
        r"\bbasically\b",
        r"\bkind of\b",
        r"\bsort of\b",
    )

    # ==========================================================
    # GENERIC TERMINOLOGY NORMALIZATION
    # ==========================================================

    _TERMINOLOGY = {
        "data set": "dataset",
        "fine tuned": "fine-tuned",
        "fine tuning": "fine-tuning",
        "held out": "held-out",
        "pre training": "pre-training",
        "pre trained": "pre-trained",
        "high quality": "high-quality",
        "real time": "real-time",
    }

    # ==========================================================
    # GENERIC CONTEXTUAL CORRECTIONS
    # ==========================================================

    _CONTEXT_CORRECTIONS = {
        "hideout data": "held-out data",
        "hide out data": "held-out data",
        "training data set": "training dataset",
        "same data set": "same dataset",
        "other data sets": "other datasets",
        "fine tuning": "fine-tuning",
        "fine tuned": "fine-tuned",
        "pre trained": "pre-trained",
        "pre training": "pre-training",
    }

    # ==========================================================
    # GENERIC WORD-LEVEL CORRECTION PARAMETERS
    # ==========================================================

    _MIN_CONTEXT_WORD_LENGTH = 4
    _MIN_WORD_SIMILARITY = 0.86
    _MIN_CONTEXT_SUPPORT = 0.80

    # Words that should never be automatically rewritten merely
    # because a similar word appears in the context.
    _PROTECTED_WORDS = {
        "this",
        "that",
        "these",
        "those",
        "there",
        "where",
        "which",
        "while",
        "using",
        "used",
        "uses",
        "model",
        "system",
        "method",
        "data",
        "signal",
        "input",
        "output",
        "process",
        "processing",
    }

    # ==========================================================
    # PUBLIC API
    # ==========================================================

    def refine(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> TranscriptResult:

        original_text = (
            str(text).strip()
            if text is not None
            else ""
        )

        if not original_text:
            return TranscriptResult(
                original_text="",
                refined_text="",
                changed=False,
                quality_score=0.0,
                corrections=[],
            )

        refined = self._normalize(original_text)

        corrections: List[TranscriptCorrection] = []

        if refined != original_text:
            corrections.append(
                TranscriptCorrection(
                    original=original_text,
                    replacement=refined,
                    correction_type="whitespace",
                    confidence=1.0,
                )
            )

        refined, filler_changed = self._remove_fillers(
            refined
        )

        if filler_changed:
            corrections.append(
                TranscriptCorrection(
                    original="speech fillers",
                    replacement="",
                    correction_type="filler",
                    confidence=0.99,
                )
            )

        refined, repetition_changed = (
            self._remove_repetitions(refined)
        )

        if repetition_changed:
            corrections.append(
                TranscriptCorrection(
                    original="repeated speech",
                    replacement="deduplicated speech",
                    correction_type="repetition",
                    confidence=0.99,
                )
            )

        if context:
            refined, boundary_corrections = (
                self._repair_context(
                    refined,
                    context,
                )
            )
            corrections.extend(boundary_corrections)

        refined, terminology_corrections = (
            self._normalize_terminology(refined)
        )
        corrections.extend(terminology_corrections)

        if context:
            refined, contextual_corrections = (
                self._apply_context_corrections(
                    refined,
                    context,
                )
            )
            corrections.extend(contextual_corrections)

            refined, spelling_corrections = (
                self._apply_generic_context_corrections(
                    refined,
                    context,
                )
            )
            corrections.extend(spelling_corrections)

        cleaned = self._clean_punctuation(refined)

        if cleaned != refined:
            corrections.append(
                TranscriptCorrection(
                    original=refined,
                    replacement=cleaned,
                    correction_type="punctuation",
                    confidence=0.98,
                )
            )

            refined = cleaned

        refined = self._normalize(refined)

        return TranscriptResult(
            original_text=original_text,
            refined_text=refined,
            changed=original_text != refined,
            quality_score=self._quality_score(
                original_text,
                refined,
                corrections,
            ),
            corrections=corrections,
        )

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""

        return " ".join(
            str(text)
            .strip()
            .split()
        )

    # ==========================================================
    # FILLERS
    # ==========================================================

    def _remove_fillers(
        self,
        text: str,
    ) -> Tuple[str, bool]:

        original = text

        for pattern in self._FILLER_PATTERNS:
            text = re.sub(
                pattern,
                " ",
                text,
                flags=re.IGNORECASE,
            )

        text = self._normalize(text)

        return text, text != original

    # ==========================================================
    # REPETITIONS
    # ==========================================================

    @staticmethod
    def _remove_repetitions(
        text: str,
    ) -> Tuple[str, bool]:

        if not text:
            return text, False

        changed = False

        words = text.split()
        cleaned_words = []

        for word in words:
            current = word.lower().strip(
                ".,!?;:"
            )

            if (
                cleaned_words
                and current
                == cleaned_words[-1]
                .lower()
                .strip(".,!?;:")
            ):
                changed = True
                continue

            cleaned_words.append(word)

        text = " ".join(cleaned_words)

        sentences = re.split(
            r"(?<=[.!?])\s+",
            text.strip(),
        )

        if len(sentences) > 1:
            cleaned_sentences = []

            for sentence in sentences:
                normalized_sentence = re.sub(
                    r"[^a-z0-9]+",
                    " ",
                    sentence.lower(),
                ).strip()

                if not normalized_sentence:
                    continue

                if cleaned_sentences:
                    previous = re.sub(
                        r"[^a-z0-9]+",
                        " ",
                        cleaned_sentences[-1].lower(),
                    ).strip()

                    if normalized_sentence == previous:
                        changed = True
                        continue

                cleaned_sentences.append(sentence)

            text = " ".join(cleaned_sentences)

        words = text.split()

        while len(words) >= 6:
            removed = False

            max_phrase_size = min(
                30,
                len(words) // 2,
            )

            for size in range(
                max_phrase_size,
                2,
                -1,
            ):
                first = [
                    word.lower().strip(
                        ".,!?;:"
                    )
                    for word in words[:size]
                ]

                second = [
                    word.lower().strip(
                        ".,!?;:"
                    )
                    for word in words[
                        size:size * 2
                    ]
                ]

                if first == second:
                    words = (
                        words[:size]
                        + words[size * 2:]
                    )

                    changed = True
                    removed = True
                    break

            if not removed:
                break

        return " ".join(words), changed

    # ==========================================================
    # BOUNDARY REPAIR
    # ==========================================================

    def _repair_context(
        self,
        text: str,
        context: str,
    ) -> Tuple[str, List[TranscriptCorrection]]:

        corrections = []

        if not text or not context:
            return text, corrections

        context = self._normalize(context)
        text = self._normalize(text)

        context_words = context.split()
        text_words = text.split()

        if not context_words or not text_words:
            return text, corrections

        max_window = min(
            20,
            len(context_words),
            len(text_words),
        )

        best_size = 0

        for size in range(
            max_window,
            2,
            -1,
        ):
            previous = [
                self._word_key(word)
                for word in context_words[-size:]
            ]

            current = [
                self._word_key(word)
                for word in text_words[:size]
            ]

            similarity = SequenceMatcher(
                None,
                previous,
                current,
            ).ratio()

            if similarity >= 0.82:
                best_size = size
                break

        if best_size < 3:
            return text, corrections

        overlap = " ".join(
            text_words[:best_size]
        )

        remaining = " ".join(
            text_words[best_size:]
        )

        if remaining:
            corrections.append(
                TranscriptCorrection(
                    original=overlap,
                    replacement="",
                    correction_type="boundary_overlap",
                    confidence=0.90,
                )
            )

            return remaining, corrections

        return text, corrections

    @staticmethod
    def _word_key(word: str) -> str:
        return re.sub(
            r"[^a-z0-9]+",
            "",
            word.lower(),
        )

    # ==========================================================
    # TERMINOLOGY
    # ==========================================================

    def _normalize_terminology(
        self,
        text: str,
    ) -> Tuple[str, List[TranscriptCorrection]]:

        corrections = []

        if not text:
            return text, corrections

        refined = text

        patterns = sorted(
            self._TERMINOLOGY.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for source, target in patterns:
            pattern = (
                r"(?<!\w)"
                + re.escape(source)
                + r"(?!\w)"
            )

            updated, count = re.subn(
                pattern,
                target,
                refined,
                flags=re.IGNORECASE,
            )

            if count and updated != refined:
                corrections.append(
                    TranscriptCorrection(
                        original=source,
                        replacement=target,
                        correction_type="terminology",
                        confidence=0.96,
                    )
                )

                refined = updated

        return refined, corrections

    # ==========================================================
    # CONTEXTUAL PHRASE CORRECTIONS
    # ==========================================================

    def _apply_context_corrections(
        self,
        text: str,
        context: Optional[str],
    ) -> Tuple[str, List[TranscriptCorrection]]:

        corrections = []

        if not text:
            return text, corrections

        refined = text

        for source, target in sorted(
            self._CONTEXT_CORRECTIONS.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        ):
            pattern = (
                r"(?<!\w)"
                + re.escape(source)
                + r"(?!\w)"
            )

            matches = list(
                re.finditer(
                    pattern,
                    refined,
                    flags=re.IGNORECASE,
                )
            )

            if not matches:
                continue

            confidence = self._correction_confidence(
                source,
                target,
                context,
            )

            if confidence < 0.85:
                continue

            updated, count = re.subn(
                pattern,
                target,
                refined,
                flags=re.IGNORECASE,
            )

            if count and updated != refined:
                corrections.append(
                    TranscriptCorrection(
                        original=matches[0].group(0),
                        replacement=target,
                        correction_type="contextual",
                        confidence=confidence,
                    )
                )

                refined = updated

        return refined, corrections

    @staticmethod
    def _correction_confidence(
        source: str,
        target: str,
        context: Optional[str],
    ) -> float:

        if not context:
            return 0.86

        context_lower = context.lower()

        if target.lower() in context_lower:
            return 0.97

        if source.lower() in context_lower:
            return 0.90

        return 0.86

    # ==========================================================
    # GENERIC CONTEXT-AWARE WORD CORRECTION
    # ==========================================================

    def _apply_generic_context_corrections(
        self,
        text: str,
        context: str,
    ) -> Tuple[str, List[TranscriptCorrection]]:

        corrections: List[TranscriptCorrection] = []

        if not text or not context:
            return text, corrections

        refined = text

        transcript_tokens = self._word_tokens(refined)
        context_tokens = self._word_tokens(context)

        if not transcript_tokens or not context_tokens:
            return refined, corrections

        context_candidates = self._build_context_candidates(
            context_tokens
        )

        if not context_candidates:
            return refined, corrections

        words = refined.split()
        changed = False

        for index, word in enumerate(words):
            token = self._word_key(word)

            if not token:
                continue

            if len(token) < self._MIN_CONTEXT_WORD_LENGTH:
                continue

            if token in self._PROTECTED_WORDS:
                continue

            if token in context_candidates:
                continue

            candidate = self._find_best_context_candidate(
                token,
                context_candidates,
            )

            if candidate is None:
                continue

            replacement, confidence = candidate

            if confidence < self._MIN_CONTEXT_SUPPORT:
                continue

            original_word = word

            replacement = self._preserve_word_punctuation(
                original_word,
                replacement,
            )

            if replacement == original_word:
                continue

            words[index] = replacement
            changed = True

            corrections.append(
                TranscriptCorrection(
                    original=token,
                    replacement=replacement.strip(".,!?;:"),
                    correction_type="contextual_spelling",
                    confidence=confidence,
                )
            )

        if changed:
            refined = " ".join(words)

        return refined, corrections

    @staticmethod
    def _word_tokens(text: str) -> List[str]:
        return re.findall(
            r"[A-Za-z][A-Za-z'-]*",
            text.lower(),
        )

    @staticmethod
    def _build_context_candidates(
        tokens: List[str],
    ) -> set[str]:

        candidates = set()

        for token in tokens:
            normalized = re.sub(
                r"[^a-z]",
                "",
                token.lower(),
            )

            if len(normalized) >= 4:
                candidates.add(normalized)

        return candidates

    def _find_best_context_candidate(
        self,
        token: str,
        candidates: set[str],
    ) -> Optional[Tuple[str, float]]:

        normalized_token = re.sub(
            r"[^a-z]",
            "",
            token.lower(),
        )

        if not normalized_token:
            return None

        best_candidate = None
        best_similarity = 0.0

        for candidate in candidates:
            if candidate == normalized_token:
                continue

            if len(candidate) < self._MIN_CONTEXT_WORD_LENGTH:
                continue

            length_difference = abs(
                len(candidate)
                - len(normalized_token)
            )

            if length_difference > 3:
                continue

            similarity = SequenceMatcher(
                None,
                normalized_token,
                candidate,
            ).ratio()

            if similarity > best_similarity:
                best_similarity = similarity
                best_candidate = candidate

        
        if best_candidate is None:
            return None

        if best_similarity >= self._MIN_WORD_SIMILARITY:
            return (
                best_candidate,
                best_similarity,
            )

        if (
            self._edit_distance(
                normalized_token,
                best_candidate,
            ) <= 1
            and min(
                len(normalized_token),
                len(best_candidate),
            ) >= 5
        ):
            confidence = min(
                0.96,
                best_similarity + 0.10,
            )

            return (
                best_candidate,
                confidence,
            )

        return None

    @staticmethod
    def _preserve_word_punctuation(
        original: str,
        replacement: str,
    ) -> str:

        prefix = re.match(
            r"^[^A-Za-z]*",
            original,
        )

        suffix = re.search(
            r"[^A-Za-z]*$",
            original,
        )

        prefix_text = (
            prefix.group(0)
            if prefix
            else ""
        )

        suffix_text = (
            suffix.group(0)
            if suffix
            else ""
        )

        if original[:1].isupper():
            replacement = replacement.capitalize()

        return (
            prefix_text
            + replacement
            + suffix_text
        )

    # ==========================================================
    # PUNCTUATION
    # ==========================================================

    @staticmethod
    def _clean_punctuation(
        text: str,
    ) -> str:

        if not text:
            return ""

        text = re.sub(
            r"\s+([,.!?;:])",
            r"\1",
            text,
        )

        text = re.sub(
            r"([,.!?;:])([A-Za-z])",
            r"\1 \2",
            text,
        )

        text = re.sub(
            r"\.{2,}",
            ".",
            text,
        )

        return " ".join(
            text.strip().split()
        )

    # ==========================================================
    # QUALITY SCORE
    # ==========================================================

    @staticmethod
    def _quality_score(
        original: str,
        refined: str,
        corrections: List[TranscriptCorrection],
    ) -> float:

        if not original:
            return 0.0

        original_words = original.split()
        refined_words = refined.split()

        if not original_words:
            return 0.0

        removed_ratio = max(
            0.0,
            (
                len(original_words)
                - len(refined_words)
            )
            / len(original_words),
        )

        low_confidence = [
            correction
            for correction in corrections
            if correction.confidence < 0.90
        ]

        contextual_corrections = [
            correction
            for correction in corrections
            if correction.correction_type
            in {
                "contextual",
                "contextual_spelling",
            }
        ]

        correction_penalty = min(
            0.25,
            len(low_confidence) * 0.03,
        )

        contextual_bonus = min(
            0.03,
            len(contextual_corrections) * 0.005,
        )

        score = (
            1.0
            - removed_ratio * 0.30
            - correction_penalty
            + contextual_bonus
        )

        return max(
            0.0,
            min(
                1.0,
                float(score),
            ),
        )

    @staticmethod
    def _edit_distance(
        first: str,
        second: str,
    ) -> int:

        if first == second:
            return 0

        if not first:
            return len(second)

        if not second:
            return len(first)

        previous = list(range(len(second) + 1))

        for i, char_first in enumerate(first, start=1):
            current = [i]

            for j, char_second in enumerate(
                second,
                start=1,
            ):
                insertion = current[j - 1] + 1
                deletion = previous[j] + 1
                substitution = (
                    previous[j - 1]
                    + (char_first != char_second)
                )

                current.append(
                    min(
                        insertion,
                        deletion,
                        substitution,
                    )
                )

            previous = current

        return previous[-1]


transcript_intelligence = TranscriptIntelligence()