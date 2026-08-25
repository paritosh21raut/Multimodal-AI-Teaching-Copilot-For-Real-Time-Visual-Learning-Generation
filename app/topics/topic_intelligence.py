from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from sentence_transformers import SentenceTransformer
from sentence_transformers.util import cos_sim


@dataclass
class TopicDecision:
    topic: str
    embedding: object

    is_relevant: bool
    is_new_topic: bool

    similarity: float
    confidence: float

    reason: str


class TopicIntelligence:

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        new_topic_threshold: float = 0.55,
        irrelevant_threshold: float = 0.30,
    ):

        print(
            "[Topic] Loading embedding model..."
        )

        self.model = SentenceTransformer(
            model_name
        )

        self.new_topic_threshold = (
            new_topic_threshold
        )

        self.irrelevant_threshold = (
            irrelevant_threshold
        )

        print(
            "[Topic] Ready"
        )

    # ==========================================================
    # TRANSITION DETECTION
    # ==========================================================

    @staticmethod
    def _has_transition_signal(
        text: str,
    ) -> bool:

        text = " ".join(
            text.lower().split()
        )

        transition_phrases = (
            "now let's discuss",
            "now let us discuss",
            "now let's look at",
            "now let us look at",
            "now let's learn",
            "now let us learn",
            "now we will discuss",
            "now we'll discuss",
            "now we discuss",
            "let's discuss",
            "let us discuss",
            "let's look at",
            "let us look at",
            "let's learn about",
            "let us learn about",
            "moving on to",
            "moving on",
            "next let's discuss",
            "next let us discuss",
            "next we will discuss",
            "next we'll discuss",
            "another topic",
            "another type",
            "another concept",
            "finally",
            "coming to",
        )

        return any(
            phrase in text
            for phrase in transition_phrases
        )

    # ==========================================================
    # CLEAN TOPIC
    # ==========================================================

    @staticmethod
    def _clean_topic_text(
        text: str,
    ) -> str:

        text = " ".join(
            text.strip().split()
        )

        if not text:
            return ""

        # ------------------------------------------------------
        # Explicit opening/topic phrases
        # ------------------------------------------------------

        patterns = (
            r"^today\s+we\s+will\s+learn\s+about\s+(.+)$",
            r"^today\s+we'?ll\s+learn\s+about\s+(.+)$",
            r"^we\s+will\s+learn\s+about\s+(.+)$",
            r"^we'?ll\s+learn\s+about\s+(.+)$",
            r"^let'?s\s+learn\s+about\s+(.+)$",
            r"^let\s+us\s+learn\s+about\s+(.+)$",
            r"^now\s+let'?s\s+learn\s+about\s+(.+)$",
            r"^now\s+let\s+us\s+learn\s+about\s+(.+)$",
        )

        for pattern in patterns:

            match = re.match(
                pattern,
                text,
                flags=re.IGNORECASE,
            )

            if match:

                text = match.group(1).strip()

                break

        # ------------------------------------------------------
        # Remove transition phrases
        # ------------------------------------------------------

        transition_patterns = (
            r"^now\s+let'?s\s+discuss\s+",
            r"^now\s+let\s+us\s+discuss\s+",
            r"^now\s+let'?s\s+look\s+at\s+",
            r"^now\s+let\s+us\s+look\s+at\s+",
            r"^let'?s\s+discuss\s+",
            r"^let\s+us\s+discuss\s+",
            r"^let'?s\s+look\s+at\s+",
            r"^let\s+us\s+look\s+at\s+",
            r"^moving\s+on\s+to\s+",
            r"^moving\s+on\s+",
            r"^next\s+",
            r"^coming\s+to\s+",
        )

        for pattern in transition_patterns:

            text = re.sub(
                pattern,
                "",
                text,
                count=1,
                flags=re.IGNORECASE,
            )

        # ------------------------------------------------------
        # Keep only the topic phrase before explanation.
        # ------------------------------------------------------

        # First sentence/clause only.
        text = re.split(
            r"[.!?]",
            text,
            maxsplit=1,
        )[0]

        text = re.split(
            r"\b(?:which|that|because|since)\b",
            text,
            maxsplit=1,
            flags=re.IGNORECASE,
        )[0]

        # Remove leading "the".
        text = re.sub(
            r"^the\s+",
            "",
            text,
            flags=re.IGNORECASE,
        )

        text = text.strip(
            " ,:-"
        )

        if not text:
            return ""

        return (
            text[0].upper()
            + text[1:]
        )

    # ==========================================================
    # TOPIC NAME
    # ==========================================================

    def _extract_topic_name(
        self,
        text: str,
        fallback: Optional[str] = None,
    ) -> str:

        topic = self._clean_topic_text(
            text
        )

        if topic:
            return topic

        return fallback or text

    # ==========================================================
    # PROCESS
    # ==========================================================

    def process(
        self,
        latest_text: str,
        rolling_context: str,
        current_topic: Optional[str],
        current_embedding,
    ) -> TopicDecision:

        print(
            "[Topic] process() called"
        )

        text = latest_text.strip()

        if not text:

            return TopicDecision(
                topic=current_topic or "",
                embedding=current_embedding,
                is_relevant=False,
                is_new_topic=False,
                similarity=1.0,
                confidence=0.0,
                reason="empty_text",
            )

        print(
            "[Topic] Encoding transcript..."
        )

        embedding = self.model.encode(
            text,
            convert_to_tensor=True,
        )

        print(
            "[Topic] Transcript encoded"
        )

        transition_signal = (
            self._has_transition_signal(
                text
            )
        )

        # ==========================================================
        # FIRST TOPIC
        # ==========================================================

        if current_embedding is None:

            topic = self._extract_topic_name(
                text
            )

            return TopicDecision(
                topic=topic,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=True,
                similarity=1.0,
                confidence=1.0,
                reason="initial_topic",
            )

        # ==========================================================
        # SIMILARITY
        # ==========================================================

        similarity = float(
            cos_sim(
                current_embedding,
                embedding,
            ).item()
        )

        # ==========================================================
        # EXPLICIT NEW TOPIC
        # ==========================================================

        if transition_signal:

            topic = self._extract_topic_name(
                text
            )

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | NEW TOPIC"
            )

            return TopicDecision(
                topic=topic,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=True,
                similarity=similarity,
                confidence=max(
                    0.0,
                    min(
                        1.0,
                        1.0 - similarity,
                    ),
                ),
                reason="explicit_topic_transition",
            )

        # ==========================================================
        # SAME TOPIC
        # ==========================================================

        if (
            similarity
            >= self.new_topic_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | CONTINUE"
            )

            return TopicDecision(
                topic=current_topic or text,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=similarity,
                reason="relevant_continuation",
            )

        # ==========================================================
        # RELATED CONTENT
        # ==========================================================

        if (
            similarity
            >= self.irrelevant_threshold
        ):

            print(
                f"[Topic] Similarity = "
                f"{similarity:.3f} | RELATED"
            )

            return TopicDecision(
                topic=current_topic or text,
                embedding=embedding,
                is_relevant=True,
                is_new_topic=False,
                similarity=similarity,
                confidence=similarity,
                reason="related_content",
            )

        # ==========================================================
        # IRRELEVANT
        # ==========================================================

        print(
            f"[Topic] Similarity = "
            f"{similarity:.3f} | IRRELEVANT"
        )

        return TopicDecision(
            topic=current_topic or text,
            embedding=current_embedding,
            is_relevant=False,
            is_new_topic=False,
            similarity=similarity,
            confidence=max(
                0.0,
                1.0 - similarity,
            ),
            reason="irrelevant_speech",
        )


topic_intelligence = TopicIntelligence()