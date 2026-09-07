"""
Transcript Intelligence - FIXED

Conservative transcript refinement.
Key fixes:
1. Removed aggressive pluralization
2. Removed context-based word replacement
3. Only fixes obvious ASR errors
4. Preserves technical terminology
"""

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
    """Conservative transcript refinement layer"""

    # Fillers to remove
    _FILLER_PATTERNS = (
        r"\b(um+|uh+|er+|ah+)\b",
        r"\byou know\b",
        r"\bi mean\b",
        r"\bbasically\b",
        r"\bkind of\b",
        r"\bsort of\b",
    )

    # Generic terminology normalization (safe, domain-agnostic)
    _TERMINOLOGY = {
        "data set": "dataset",
        "fine tuned": "fine-tuned",
        "fine tuning": "fine-tuning",
        "held out": "held-out",
        "pre training": "pre-training",
        "pre trained": "pre-trained",
        "real time": "real-time",
    }

    # IMPORTANT: Removed _CONTEXT_CORRECTIONS - too aggressive
    # IMPORTANT: Removed _apply_generic_context_corrections - causes pluralization issues

    # Words that should NEVER be modified
    _PROTECTED_WORDS = {
        "this", "that", "these", "those", "there", "where",
        "which", "while", "using", "used", "uses", "model",
        "system", "method", "data", "signal", "input", "output",
        "process", "processing", "network", "networks",
        "protocol", "protocols", "connection", "connections",
        "layer", "layers", "device", "devices",
    }

    def refine(
        self,
        text: str,
        context: Optional[str] = None,
    ) -> TranscriptResult:
        """Refine transcript conservatively"""

        original_text = str(text).strip() if text else ""

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

        # 1. Remove fillers
        refined, filler_changed = self._remove_fillers(refined)
        if filler_changed:
            corrections.append(TranscriptCorrection(
                original="fillers", replacement="",
                correction_type="filler", confidence=0.99
            ))

        # 2. Remove immediate word repetitions only
        refined, repetition_changed = self._remove_immediate_repetitions(refined)
        if repetition_changed:
            corrections.append(TranscriptCorrection(
                original="repetition", replacement="deduplicated",
                correction_type="repetition", confidence=0.99
            ))

        # 3. Generic terminology normalization
        refined, term_corrections = self._normalize_terminology(refined)
        corrections.extend(term_corrections)

        # 4. Basic punctuation cleanup
        cleaned = self._clean_punctuation(refined)
        if cleaned != refined:
            corrections.append(TranscriptCorrection(
                original=refined, replacement=cleaned,
                correction_type="punctuation", confidence=0.98
            ))
            refined = cleaned

        refined = self._normalize(refined)

        return TranscriptResult(
            original_text=original_text,
            refined_text=refined,
            changed=original_text != refined,
            quality_score=self._quality_score(original_text, refined, corrections),
            corrections=corrections,
        )

    @staticmethod
    def _normalize(text: str) -> str:
        if not text:
            return ""
        return " ".join(str(text).strip().split())

    def _remove_fillers(self, text: str) -> Tuple[str, bool]:
        original = text
        for pattern in self._FILLER_PATTERNS:
            text = re.sub(pattern, " ", text, flags=re.IGNORECASE)
        text = self._normalize(text)
        return text, text != original

    @staticmethod
    def _remove_immediate_repetitions(text: str) -> Tuple[str, bool]:
        """Only remove immediate word repetitions (e.g., 'the the')"""
        if not text:
            return text, False

        changed = False
        words = text.split()
        cleaned = []

        for word in words:
            current = word.lower().strip(".,!?;:")
            if cleaned and current == cleaned[-1].lower().strip(".,!?;:"):
                changed = True
                continue
            cleaned.append(word)

        return " ".join(cleaned), changed

    def _normalize_terminology(self, text: str) -> Tuple[str, List[TranscriptCorrection]]:
        corrections = []
        refined = text

        patterns = sorted(
            self._TERMINOLOGY.items(),
            key=lambda item: len(item[0]),
            reverse=True,
        )

        for source, target in patterns:
            pattern = r"(?<!\w)" + re.escape(source) + r"(?!\w)"
            updated, count = re.subn(pattern, target, refined, flags=re.IGNORECASE)

            if count and updated != refined:
                corrections.append(TranscriptCorrection(
                    original=source, replacement=target,
                    correction_type="terminology", confidence=0.96
                ))
                refined = updated

        return refined, corrections

    @staticmethod
    def _clean_punctuation(text: str) -> str:
        if not text:
            return ""

        text = re.sub(r"\s+([,.!?;:])", r"\1", text)
        text = re.sub(r"([,.!?;:])([A-Za-z])", r"\1 \2", text)
        text = re.sub(r"\.{2,}", ".", text)
        return " ".join(text.strip().split())

    @staticmethod
    def _quality_score(original: str, refined: str, corrections: List[TranscriptCorrection]) -> float:
        if not original:
            return 0.0

        original_words = original.split()
        refined_words = refined.split()

        if not original_words:
            return 0.0

        removed_ratio = max(0.0, (len(original_words) - len(refined_words)) / len(original_words))

        score = 1.0 - removed_ratio * 0.2

        return max(0.0, min(1.0, float(score)))


transcript_intelligence = TranscriptIntelligence()