from __future__ import annotations

import re
import sys
import threading
from typing import Optional


class LiveTranscriptManager:
    """
    Maintains the lecture transcript and semantic-analysis queue.

    Important design:

    1. Live Whisper output is only a preview.
    2. Final Whisper output is the authoritative transcript.
    3. Previously analyzed content is remembered.
    4. New analysis waits for enough meaningful context.
    5. We do not throw away transcript just because the LLM is busy.
    """

    def __init__(
        self,
        analysis_callback: Optional = None,
    ) -> None:

        self.analysis_callback = (
            analysis_callback
        )

        self.lock = (
            threading.RLock()
        )

        # ==========================================================
        # DISPLAY
        # ==========================================================

        self.current_segment_transcript = ""

        self.current_paragraph = ""

        self.all_paragraphs = []

        # ==========================================================
        # ANALYSIS MEMORY
        # ==========================================================

        self.completed_sentences = []

        self.pending_analysis_text = []

        self.last_displayed = ""

        # ==========================================================
        # TOPIC BOUNDARY
        # ==========================================================

        self.current_topic_boundary = ""

        # ==========================================================
        # SEMANTIC CHUNKING
        # ==========================================================

        # Do not send tiny fragments to the semantic model.
        self.min_analysis_words = 45

        # Once we have this much material, send it to analysis.
        self.max_analysis_words = 140

    # ==========================================================
    # NORMALIZE
    # ==========================================================

    @staticmethod
    def normalize(
        text: str,
    ) -> str:

        return " ".join(
            text.strip().split()
        )

    # ==========================================================
    # WORD COUNT
    # ==========================================================

    @staticmethod
    def word_count(
        text: str,
    ) -> int:

        return len(
            re.findall(
                r"\b\w+(?:[-']\w+)*\b",
                text,
            )
        )

    # ==========================================================
    # SENTENCES
    # ==========================================================

    def extract_complete_sentences(
        self,
        transcript: str,
    ):

        transcript = (
            self.normalize(
                transcript
            )
        )

        if not transcript:
            return []

        matches = re.findall(
            r"[^.!?]+[.!?]+",
            transcript,
        )

        return [
            self.normalize(
                sentence
            )
            for sentence in matches
            if self.normalize(
                sentence
            )
        ]

    # ==========================================================
    # SUFFIX AFTER TOPIC BOUNDARY
    # ==========================================================

    @staticmethod
    def _suffix_after_boundary(
        transcript: str,
        boundary: str,
    ) -> str:

        transcript = " ".join(
            transcript.strip().split()
        )

        boundary = " ".join(
            boundary.strip().split()
        )

        if not transcript:
            return ""

        if not boundary:
            return transcript

        index = (
            transcript.lower().find(
                boundary.lower()
            )
        )

        if index >= 0:

            return transcript[
                index:
            ].strip()

        boundary_words = (
            boundary.split()
        )

        transcript_words = (
            transcript.split()
        )

        max_words = min(
            len(boundary_words),
            len(transcript_words),
        )

        for size in range(
            max_words,
            3,
            -1,
        ):

            boundary_tail = [
                word.lower()
                for word
                in boundary_words[
                    -size:
                ]
            ]

            transcript_lower = [
                word.lower()
                for word
                in transcript_words
            ]

            for index in range(
                len(
                    transcript_lower
                )
                - size
                + 1
            ):

                if (
                    transcript_lower[
                        index:index + size
                    ]
                    == boundary_tail
                ):

                    return " ".join(
                        transcript_words[
                            index:
                        ]
                    )

        return transcript

    # ==========================================================
    # LIVE DISPLAY
    # ==========================================================

    def update(
        self,
        transcript: str,
    ) -> str:

        transcript = (
            self.normalize(
                transcript
            )
        )

        if not transcript:
            return (
                self.current_paragraph
            )

        with self.lock:

            self.current_segment_transcript = (
                transcript
            )

            if self.current_topic_boundary:

                paragraph = (
                    self._suffix_after_boundary(
                        transcript,
                        self.current_topic_boundary,
                    )
                )

            else:

                paragraph = transcript

            if paragraph:

                self.current_paragraph = (
                    paragraph
                )

            self._render()

            return self.current_paragraph

    # ==========================================================
    # RENDER
    # ==========================================================

    def _render(self):

        text = (
            self.current_paragraph
            .strip()
        )

        if not text:
            return

        sys.stdout.write(
            "\r\033[2K"
            + text
        )

        sys.stdout.flush()

        self.last_displayed = text

    # ==========================================================
    # FINALIZE PARAGRAPH
    # ==========================================================

    def finalize_current_paragraph(
        self,
    ):

        with self.lock:

            if not self.current_paragraph.strip():
                return

            self.all_paragraphs.append(
                self.current_paragraph.strip()
            )

            print()

            self.current_paragraph = ""

            self.current_topic_boundary = ""

            self.last_displayed = ""

    # ==========================================================
    # START NEW TOPIC
    # ==========================================================

    def start_new_topic(
        self,
        topic: str,
        boundary_text: str,
    ):

        with self.lock:

            if self.current_paragraph.strip():

                self.all_paragraphs.append(
                    self.current_paragraph.strip()
                )

            print()
            print()
            print(
                "=" * 70
            )
            print(
                f"NEW TOPIC: {topic}"
            )
            print(
                "=" * 70
            )

            self.current_topic_boundary = (
                self.normalize(
                    boundary_text
                )
            )

            self.current_paragraph = (
                self.current_topic_boundary
            )

            self.last_displayed = ""

            self._render()

    # ==========================================================
    # FIND NEW ANALYSIS CONTENT
    # ==========================================================

    def get_new_analysis_text(
        self,
        transcript: str,
        force: bool = False,
    ):

        transcript = (
            self.normalize(
                transcript
            )
        )

        if not transcript:
            return None

        # ----------------------------------------------------------
        # Extract sentences from the FINAL transcript.
        # ----------------------------------------------------------

        sentences = (
            self.extract_complete_sentences(
                transcript
            )
        )

        # A transcript without punctuation can still be useful.
        # The final Whisper output should not be discarded.
        if not sentences:

            if force:

                return transcript

            if (
                self.word_count(transcript)
                >= self.min_analysis_words
            ):

                return transcript

            return None

        # ----------------------------------------------------------
        # Already analyzed?
        # ----------------------------------------------------------

        with self.lock:

            analyzed = {
                item.lower()
                for item
                in self.completed_sentences
            }

        new_sentences = []

        for sentence in sentences:

            if (
                sentence.lower()
                not in analyzed
            ):

                new_sentences.append(
                    sentence
                )

        if not new_sentences:
            return None

        # ----------------------------------------------------------
        # Build one coherent semantic chunk.
        # ----------------------------------------------------------

        selected = []

        total_words = 0

        for sentence in new_sentences:

            words = self.word_count(
                sentence
            )

            # Always include at least one sentence.
            if not selected:

                selected.append(
                    sentence
                )

                total_words += words

                continue

            # Don't exceed normal semantic context.
            if (
                total_words + words
                > self.max_analysis_words
            ):

                break

            selected.append(
                sentence
            )

            total_words += words

        chunk = self.normalize(
            " ".join(selected)
        )

        # ----------------------------------------------------------
        # Do not submit fragments too early.
        # ----------------------------------------------------------

        if (
            not force
            and total_words
            < self.min_analysis_words
        ):

            return None

        return chunk or None

    # ==========================================================
    # MARK ANALYZED
    # ==========================================================

    def mark_analyzed(
        self,
        text: str,
    ):

        sentences = (
            self.extract_complete_sentences(
                text
            )
        )

        if not sentences:

            sentence = self.normalize(
                text
            )

            if not sentence:
                return

            sentences = [
                sentence
            ]

        with self.lock:

            existing = {
                item.lower()
                for item
                in self.completed_sentences
            }

            for sentence in sentences:

                normalized = (
                    self.normalize(
                        sentence
                    )
                )

                if (
                    normalized
                    and normalized.lower()
                    not in existing
                ):

                    self.completed_sentences.append(
                        normalized
                    )

                    existing.add(
                        normalized.lower()
                    )

            # Keep memory bounded.
            self.completed_sentences = (
                self.completed_sentences[-200:]
            )

    # ==========================================================
    # FULL TRANSCRIPT
    # ==========================================================

    def get_full_transcript(
        self,
    ) -> str:

        with self.lock:

            paragraphs = list(
                self.all_paragraphs
            )

            if self.current_paragraph.strip():

                paragraphs.append(
                    self.current_paragraph.strip()
                )

            return "\n\n".join(
                paragraph
                for paragraph
                in paragraphs
                if paragraph
            )

    # ==========================================================
    # RESET
    # ==========================================================

    def reset(self):

        with self.lock:

            self.current_segment_transcript = ""

            self.current_paragraph = ""

            self.all_paragraphs.clear()

            self.completed_sentences.clear()

            self.pending_analysis_text.clear()

            self.current_topic_boundary = ""

            self.last_displayed = ""