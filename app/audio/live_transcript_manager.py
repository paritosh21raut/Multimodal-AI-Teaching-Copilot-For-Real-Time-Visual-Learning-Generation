from __future__ import annotations

import re
import sys
import threading
from typing import Optional


class LiveTranscriptManager:
    """
    Maintains one live lecture transcript.

    Behavior:

    - Live Whisper updates one continuously growing paragraph.
    - Backend analyzes only completed meaningful sentences.
    - When a new topic is detected, the current paragraph is frozen.
    - The new topic starts a new paragraph.
    """

    def __init__(
        self,
        analysis_callback: Optional = None,
    ) -> None:

        self.analysis_callback = analysis_callback

        self.lock = threading.RLock()

        # Current Whisper output for the current speech segment.
        self.current_segment_transcript = ""

        # Paragraph currently being displayed.
        self.current_paragraph = ""

        # Completed paragraphs from previous topics.
        self.all_paragraphs = []

        # Sentences already analyzed by backend.
        self.completed_sentences = []

        # Boundary used after a topic change.
        self.current_topic_boundary = ""

        self.last_displayed = ""

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
    # FIND SUFFIX AFTER TOPIC BOUNDARY
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

        # Exact boundary.
        index = transcript.lower().find(
            boundary.lower()
        )

        if index >= 0:

            return transcript[
                index:
            ].strip()

        # Fallback: find the longest matching
        # suffix/prefix of the boundary.
        boundary_words = boundary.split()
        transcript_words = transcript.split()

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

            transcript_tail = [
                word.lower()
                for word
                in transcript_words
            ]

            for index in range(
                len(
                    transcript_tail
                ) - size + 1
            ):

                if (
                    transcript_tail[
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
    # UPDATE LIVE TRANSCRIPT
    # ==========================================================

    def update(
        self,
        transcript: str,
    ) -> str:

        transcript = self.normalize(
            transcript
        )

        if not transcript:
            return self.current_paragraph

        with self.lock:

            self.current_segment_transcript = (
                transcript
            )

            # --------------------------------------------------
            # After a topic change, only show the new topic
            # portion of the continuously growing Whisper text.
            # --------------------------------------------------

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
    # TERMINAL RENDER
    # ==========================================================

    def _render(self):

        text = self.current_paragraph.strip()

        if not text:
            return

        # One continuously changing terminal paragraph.
        sys.stdout.write(
            "\r\033[2K"
            + text
        )

        sys.stdout.flush()

        self.last_displayed = text

    # ==========================================================
    # COMPLETE CURRENT PARAGRAPH
    # ==========================================================

    def finalize_current_paragraph(self):

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
    # NEW TOPIC
    # ==========================================================

    def start_new_topic(
        self,
        topic: str,
        boundary_text: str,
    ):

        with self.lock:

            # Freeze previous topic paragraph.
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
    # EXTRACT COMPLETE SENTENCES
    # ==========================================================

    def extract_complete_sentences(
        self,
        transcript: str,
    ):

        transcript = self.normalize(
            transcript
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
    # GET NEW BACKEND CONTENT
    # ==========================================================

    def get_new_analysis_text(
        self,
        transcript: str,
        force: bool = False,
    ):

        transcript = self.normalize(
            transcript
        )

        if not transcript:
            return None

        sentences = (
            self.extract_complete_sentences(
                transcript
            )
        )

        if not sentences:
            return None

        new_sentences = []

        with self.lock:

            analyzed = {
                item.lower()
                for item
                in self.completed_sentences
            }

            for sentence in sentences:

                if sentence.lower() not in analyzed:

                    new_sentences.append(
                        sentence
                    )

        if not new_sentences:
            return None

        # --------------------------------------------------
        # Don't send tiny fragments to semantic analysis.
        # --------------------------------------------------

        word_count = sum(
            len(
                sentence.split()
            )
            for sentence
            in new_sentences
        )

        if not force and word_count < 20:
            return None

        # Maximum 4 complete sentences per analysis.
        chunk = " ".join(
            new_sentences[:4]
        ).strip()

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
            return

        with self.lock:

            for sentence in sentences:

                if sentence.lower() not in [
                    item.lower()
                    for item
                    in self.completed_sentences
                ]:

                    self.completed_sentences.append(
                        sentence
                    )

            self.completed_sentences = (
                self.completed_sentences[-100:]
            )

    # ==========================================================
    # FULL LECTURE
    # ==========================================================

    def get_full_transcript(self) -> str:

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

            self.current_topic_boundary = ""

            self.last_displayed = ""