from __future__ import annotations

import re
from threading import Lock

from app.lecture.context_buffer import (
    context_buffer,
)

from app.lecture.lecture_state import (
    lecture_state,
)

from app.lecture.slide_decision_engine import (
    SlideAction,
    SlideDecisionEngine,
)

from app.ppt.ppt_manager import (
    ppt_manager,
)

from app.dashboard.dashboard_state import (
    dashboard_state,
)

from app.knowledge.content_generator import (
    ContentGenerator,
)


class LecturePipeline:

    def __init__(self):

        self._lock = Lock()

        self.topic_detector = None

        self.content_generator = None

        self.slide_manager = None

        self.started = False

        self.slide_decision_engine = (
            SlideDecisionEngine(
                max_slide_source_words=110,
                max_updates_per_slide=3,
                min_meaningful_words=4,
            )
        )

        # ==========================================================
        # GENERATION BUFFER
        # ==========================================================

        self.pending_generation_chunks: list[str] = []

        self.pending_generation_words = 0

        self.pending_generation_sentences = 0

        self.generation_min_words = 30

        self.generation_min_sentences = 2

    # ==========================================================
    # REGISTRATION
    # ==========================================================

    def register_topic_detector(
        self,
        detector,
    ):

        self.topic_detector = detector

    def register_content_generator(
        self,
        generator,
    ):

        self.content_generator = generator

    def register_slide_manager(
        self,
        manager,
    ):

        self.slide_manager = manager

    # ==========================================================
    # START
    # ==========================================================

    def start(self):

        if self.started:
            return

        lecture_state.start_new_lecture()

        self.slide_decision_engine.reset()

        self._clear_generation_buffer()

        if ppt_manager.presentation is None:

            ppt_manager.create_new_presentation(
                lecture_state.lecture_title
            )

            ppt_manager.add_title_slide(
                lecture_state.lecture_title,
                "AI Teaching Copilot",
            )

        context_buffer.clear()

        self.started = True

        print(
            "[Pipeline] Lecture Pipeline Started"
        )

    # ==========================================================
    # GENERATION BUFFER
    # ==========================================================

    def _clear_generation_buffer(
        self,
    ):

        self.pending_generation_chunks = []

        self.pending_generation_words = 0

        self.pending_generation_sentences = 0

    @staticmethod
    def _count_words(
        text: str,
    ) -> int:

        return len(
            re.findall(
                r"\b\w+(?:[-']\w+)*\b",
                text,
            )
        )

    @staticmethod
    def _count_completed_sentences(
        text: str,
    ) -> int:

        return len(
            re.findall(
                r"[^.!?]+[.!?]+",
                text,
            )
        )

    def _add_to_generation_buffer(
        self,
        transcript: str,
    ):

        text = " ".join(
            transcript.strip().split()
        )

        if not text:
            return

        self.pending_generation_chunks.append(
            text
        )

        self.pending_generation_words += (
            self._count_words(text)
        )

        self.pending_generation_sentences += (
            self._count_completed_sentences(
                text
            )
        )

    def _generation_buffer_text(
        self,
    ) -> str:

        return " ".join(
            self.pending_generation_chunks
        ).strip()

    def _generation_buffer_ready(
        self,
    ) -> bool:

        return (
            self.pending_generation_words
            >= self.generation_min_words
            or
            self.pending_generation_sentences
            >= self.generation_min_sentences
        )

    # ==========================================================
    # SAFE SECTION HELPERS
    # ==========================================================

    @staticmethod
    def _safe_sections(
        content,
    ) -> list:

        sections = getattr(
            content,
            "sections",
            [],
        )

        if not isinstance(
            sections,
            list,
        ):
            return []

        return sections

    @staticmethod
    def _section_heading(
        section,
    ) -> str:

        if isinstance(
            section,
            dict,
        ):

            return str(
                section.get(
                    "heading",
                    "",
                )
                or ""
            ).strip()

        return str(
            getattr(
                section,
                "heading",
                "",
            )
            or ""
        ).strip()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize(
        text: str,
    ) -> str:

        return " ".join(
            str(text or "")
            .strip()
            .split()
        )

    # ==========================================================
    # STRUCTURAL FRAGMENT DETECTION
    # ==========================================================

    @staticmethod
    def _is_transition_fragment(
        text: str,
    ) -> bool:

        normalized = (
            " ".join(
                str(text or "")
                .lower()
                .strip()
                .split()
            )
        )

        if not normalized:
            return False

        transition_prefixes = (
            "now let's discuss",
            "now let us discuss",
            "now let's look at",
            "now let us look at",
            "now let's learn",
            "now let us learn",
            "now we will discuss",
            "now we'll discuss",
            "let's discuss",
            "let us discuss",
            "let's look at",
            "let us look at",
            "moving on",
            "moving on to",
            "next let's",
            "next let us",
            "next we will",
            "next we'll",
            "coming to",
            "another topic",
            "another concept",
            "another type",
        )

        for prefix in transition_prefixes:

            if normalized.startswith(
                prefix
            ):

                remaining = normalized[
                    len(prefix):
                ].strip()

                if not remaining:
                    return True

                if remaining in {
                    "the",
                    "a",
                    "an",
                    "this",
                    "these",
                    "those",
                    "next",
                    "topic",
                    "concept",
                    "type",
                    "types",
                    "following",
                }:

                    return True

                if len(
                    normalized.split()
                ) <= 5:

                    return True

        return False

    @staticmethod
    def _looks_like_topic_fragment(
        text: str,
    ) -> bool:

        normalized = (
            " ".join(
                str(text or "")
                .lower()
                .strip()
                .split()
            )
        )

        if not normalized:
            return True

        words = normalized.split()

        if len(words) <= 1:

            blocked = {
                "the",
                "a",
                "an",
                "and",
                "or",
                "of",
                "to",
                "for",
                "in",
                "on",
                "at",
                "is",
                "are",
                "was",
                "were",
                "this",
                "that",
                "these",
                "those",
                "now",
            }

            return normalized in blocked

        return False

    # ==========================================================
    # STRUCTURAL SPLITTING
    # ==========================================================

    @classmethod
    def _split_structural_units(
        cls,
        transcript: str,
    ) -> list[tuple[str, str]]:

        transcript = cls._normalize(
            transcript
        )

        if not transcript:
            return []

        try:

            raw_units = (
                ContentGenerator
                .split_major_sections(
                    transcript
                )
            )

        except Exception:

            raw_units = []

        if not isinstance(
            raw_units,
            list,
        ):

            raw_units = []

        cleaned: list[
            tuple[str, str]
        ] = []

        pending_prefix = ""

        for item in raw_units:

            if (
                not isinstance(
                    item,
                    tuple,
                )
                or len(item) != 2
            ):
                continue

            heading = cls._normalize(
                item[0]
            )

            content = cls._normalize(
                item[1]
            )

            if not content:
                continue

            # --------------------------------------------------
            # Incomplete transition.
            # --------------------------------------------------

            if cls._is_transition_fragment(
                content
            ):

                pending_prefix = cls._normalize(
                    f"{pending_prefix} {content}"
                )

                continue

            # --------------------------------------------------
            # Attach pending transition to the next
            # meaningful section.
            # --------------------------------------------------

            if pending_prefix:

                content = cls._normalize(
                    f"{pending_prefix} {content}"
                )

                pending_prefix = ""

            cleaned.append(
                (
                    heading,
                    content,
                )
            )

        # ------------------------------------------------------
        # Handle leftover transition.
        # ------------------------------------------------------

        if pending_prefix:

            if cleaned:

                heading, content = cleaned[-1]

                cleaned[-1] = (
                    heading,
                    cls._normalize(
                        f"{content} {pending_prefix}"
                    ),
                )

            else:

                return [
                    (
                        "",
                        transcript,
                    )
                ]

        # ------------------------------------------------------
        # Validate units.
        # ------------------------------------------------------

        valid_units = []

        for heading, content in cleaned:

            if not content:
                continue

            if (
                len(
                    content.split()
                ) <= 2
                and cls._looks_like_topic_fragment(
                    content
                )
            ):

                continue

            valid_units.append(
                (
                    heading,
                    content,
                )
            )

        if not valid_units:

            return [
                (
                    "",
                    transcript,
                )
            ]

        return valid_units

    # ==========================================================
    # PUBLIC PROCESS
    # ==========================================================

    def process_transcript(
        self,
        transcript: str,
    ):

        transcript = self._normalize(
            transcript
        )

        if not transcript:
            return None

        if not self.started:
            self.start()

        structural_units = (
            self._split_structural_units(
                transcript
            )
        )

        if not structural_units:

            structural_units = [
                (
                    "",
                    transcript,
                )
            ]

        results = []

        for index, (
            heading,
            unit,
        ) in enumerate(
            structural_units
        ):

            unit = self._normalize(
                unit
            )

            if not unit:
                continue

            force_create = (
                bool(heading)
                and (
                    lecture_state.has_slides()
                    or index > 0
                )
            )

            result = self._process_unit(
                transcript=unit,
                forced_heading=heading,
                force_create=force_create,
            )

            if result:

                results.append(
                    result
                )

        if len(results) == 1:
            return results[0]

        if not results:
            return None

        last = results[-1]

        return {
            **last,
            "processed_units": len(
                results
            ),
            "results": results,
        }

    # ==========================================================
    # PROCESS ONE UNIT
    # ==========================================================

    def _process_unit(
        self,
        transcript: str,
        forced_heading: str = "",
        force_create: bool = False,
    ):

        # ======================================================
        # TOPIC DETECTION
        # ======================================================

        if self.topic_detector is None:

            raise RuntimeError(
                "Topic detector is not registered."
            )

        decision = (
            self.topic_detector.process(

                latest_text=transcript,

                rolling_context=(
                    context_buffer.rolling_context()
                ),

                current_topic=(
                    lecture_state.get_current_topic()
                ),

                current_embedding=(
                    lecture_state.get_current_embedding()
                ),
            )
        )

        # ======================================================
        # IRRELEVANT
        # ======================================================

        if (
            hasattr(
                decision,
                "is_relevant",
            )
            and not decision.is_relevant
        ):

            print()

            print(
                "ANALYSIS RESULT"
            )

            print(
                "-" * 70
            )

            print(
                "Relevant      : NO"
            )

            print(
                "Action        : KEEP CURRENT SLIDE"
            )

            print(
                f"Reason        : "
                f"{decision.reason}"
            )

            print(
                "-" * 70
            )

            return {
                "is_relevant": False,
                "is_new_topic": False,
                "topic": (
                    lecture_state.get_current_topic()
                ),
                "confidence": 0.0,
                "reason": decision.reason,
                "slide_action": "IGNORE",
                "slide_number": (
                    lecture_state.current_slide_number
                    if lecture_state.has_slides()
                    else None
                ),
                "content_generated": False,
            }

        # ======================================================
        # ADD TO CONTEXT
        # ======================================================

        context_buffer.add(
            transcript
        )

        # ======================================================
        # PIPELINE-LEVEL NEW TOPIC
        #
        # A structural subtopic is a new teaching section even
        # when embedding similarity says it is related content.
        #
        # Example:
        #
        #   Microcontrollers
        #       ↓
        #   Types of Microcontrollers
        #
        # The embedding may still be highly similar, but the
        # lecture structure clearly changed.
        # ======================================================

        pipeline_new_topic = (
            bool(
                decision.is_new_topic
            )
            or bool(
                force_create
            )
        )

        # ======================================================
        # TOPIC NAME
        # ======================================================

        topic = (
            forced_heading
            or str(
                decision.topic
            )
        )

        if (
            not topic
            or topic.lower() == "none"
            or self._looks_like_topic_fragment(
                topic
            )
        ):

            if (
                lecture_state.get_current_topic()
                and not forced_heading
            ):

                topic = (
                    lecture_state.get_current_topic()
                )

            else:

                topic = transcript[:80]

        # ======================================================
        # CONFIDENCE
        # ======================================================

        if (
            lecture_state.get_current_topic()
            is None
        ):

            confidence = 1.0

        elif pipeline_new_topic:

            confidence = max(
                0.0,
                min(
                    1.0,
                    1.0
                    - float(
                        decision.similarity
                    ),
                ),
            )

        else:

            confidence = max(
                0.0,
                min(
                    1.0,
                    float(
                        decision.similarity
                    ),
                ),
            )

        # ======================================================
        # SLIDE DECISION
        # ======================================================

        current_slide_exists = (
            lecture_state.has_slides()
        )

        slide_decision = (
            self.slide_decision_engine.decide(

                transcript=transcript,

                is_new_topic=(
                    pipeline_new_topic
                ),

                current_slide_exists=(
                    current_slide_exists
                ),

                force_create=(
                    force_create
                ),

                force_reason=(
                    (
                        f"major_subtopic_detected:{topic}"
                    )
                    if force_create
                    else ""
                ),
            )
        )

        # ======================================================
        # REPORT
        # ======================================================

        print()

        print(
            "SLIDE DECISION"
        )

        print(
            "-" * 70
        )

        print(
            f"Action        : "
            f"{slide_decision.action.value.upper()}"
        )

        print(
            f"Reason        : "
            f"{slide_decision.reason}"
        )

        print(
            f"Chunk Words   : "
            f"{slide_decision.estimated_words}"
        )

        print(
            f"Slide Words   : "
            f"{slide_decision.slide_word_count}"
        )

        print(
            f"Slide Updates : "
            f"{slide_decision.update_count}"
        )

        print(
            "-" * 70
        )

        # ======================================================
        # IGNORE
        # ======================================================

        if (
            slide_decision.action
            == SlideAction.IGNORE
        ):

            return {
                "is_relevant": True,
                "is_new_topic": pipeline_new_topic,
                "topic": topic,
                "confidence": confidence,
                "reason": (
                    slide_decision.reason
                ),
                "slide_action": "IGNORE",
                "slide_number": (
                    lecture_state.current_slide_number
                    if lecture_state.has_slides()
                    else None
                ),
                "content_generated": False,
            }

        # ======================================================
        # SAME TOPIC ACCUMULATION
        # ======================================================

        if (
            slide_decision.action
            == SlideAction.UPDATE
        ):

            self._add_to_generation_buffer(
                transcript
            )

            print(
                "[Pipeline] Pending generation words:",
                self.pending_generation_words,
            )

            print(
                "[Pipeline] Pending generation sentences:",
                self.pending_generation_sentences,
            )

            if not self._generation_buffer_ready():

                lecture_state.set_current_topic(
                    topic,
                    decision.embedding,
                )

                dashboard_state.update_topic(
                    str(topic),
                    confidence,
                )

                return {
                    "is_relevant": True,
                    "is_new_topic": pipeline_new_topic,
                    "topic": str(topic),
                    "confidence": confidence,
                    "reason": (
                        slide_decision.reason
                    ),
                    "slide_action": "ACCUMULATE",
                    "slide_number": (
                        lecture_state.current_slide_number
                        if lecture_state.has_slides()
                        else None
                    ),
                    "content_generated": False,
                    "generation_pending": True,
                    "pending_words": (
                        self.pending_generation_words
                    ),
                    "pending_sentences": (
                        self.pending_generation_sentences
                    ),
                }

        # ======================================================
        # GENERATION TEXT
        # ======================================================

        if (
            slide_decision.action
            == SlideAction.CREATE
        ):

            if (
                self.pending_generation_words
                > 0
                and not force_create
            ):

                generation_text = (
                    self._generation_buffer_text()
                    + " "
                    + transcript
                )

            else:

                generation_text = transcript

        else:

            generation_text = (
                self._generation_buffer_text()
            )

        generation_text = self._normalize(
            generation_text
        )

        if not generation_text:

            generation_text = transcript

        # ======================================================
        # CREATE / UPDATE
        # ======================================================

        create_slide = (
            slide_decision.action
            == SlideAction.CREATE
        )

        if create_slide:

            slide_action = "NEW SLIDE"

            self._clear_generation_buffer()

            slide = (
                lecture_state.create_slide(
                    topic
                )
            )

        else:

            slide_action = (
                "SAME SLIDE - UPDATE"
            )

            slide = (
                lecture_state.get_current_slide()
            )

            if slide is None:

                slide_action = "NEW SLIDE"

                self._clear_generation_buffer()

                slide = (
                    lecture_state.create_slide(
                        topic
                    )
                )

                create_slide = True

        # ======================================================
        # STATE
        # ======================================================

        lecture_state.set_current_topic(
            topic,
            decision.embedding,
        )

        dashboard_state.update_topic(
            str(topic),
            confidence,
        )

        # ======================================================
        # REPORT
        # ======================================================

        print()

        print(
            "=" * 70
        )

        print(
            "LECTURE ANALYSIS REPORT"
        )

        print(
            "=" * 70
        )

        print(
            f"Input Chunk    : "
            f"{transcript}"
        )

        print(
            f"Generation Text: "
            f"{generation_text}"
        )

        print(
            f"Topic          : "
            f"{topic}"
        )

        print(
            f"Similarity     : "
            f"{decision.similarity:.3f}"
        )

        print(
            f"Confidence     : "
            f"{confidence:.3f}"
        )

        print(
            f"Embedding New  : "
            f"{decision.is_new_topic}"
        )

        print(
            f"Pipeline New   : "
            f"{pipeline_new_topic}"
        )

        print(
            f"Structural Head: "
            f"{forced_heading or '-'}"
        )

        print(
            f"Slide Decision : "
            f"{slide_action}"
        )

        print(
            f"Decision Reason: "
            f"{slide_decision.reason}"
        )

        print(
            f"Slide Number   : "
            f"{slide.slide_number}"
        )

        print(
            "-" * 70
        )

        # ======================================================
        # CONTENT GENERATION
        # ======================================================

        print(
            "Generating educational content..."
        )

        try:

            content = (
                self.content_generator.generate(

                    topic=topic,

                    context=generation_text,
                )
            )

        except Exception as error:

            print(
                "Content Generation : FAILED"
            )

            print(
                f"Error              : "
                f"{error}"
            )

            dashboard_state.set_error(
                str(error)
            )

            dashboard_state.set_pipeline(
                "Content Generation",
                "Failed",
            )

            return {
                "is_relevant": True,
                "is_new_topic": pipeline_new_topic,
                "topic": str(topic),
                "confidence": confidence,
                "slide_number": (
                    slide.slide_number
                ),
                "slide_action": slide_action,
                "content_generated": False,
            }

        # ======================================================
        # RECORD SUCCESS
        # ======================================================

        self.slide_decision_engine.record_success(
            generation_text,
            (
                SlideAction.CREATE
                if create_slide
                else SlideAction.UPDATE
            ),
        )

        self._clear_generation_buffer()

        # ======================================================
        # SAFE CONTENT EXTRACTION
        # ======================================================

        sections = (
            self._safe_sections(
                content
            )
        )

        section_headings = [
            self._section_heading(
                section
            )
            for section in sections
            if self._section_heading(
                section
            )
        ]

        bullets = getattr(
            content,
            "bullets",
            [],
        )

        title = getattr(
            content,
            "title",
            topic,
        )

        # ======================================================
        # CONTENT REPORT
        # ======================================================

        print(
            f"Content Type   : "
            f"{getattr(content, 'content_type', '')}"
        )

        print(
            f"Visual Type    : "
            f"{getattr(content, 'visual_type', '')}"
        )

        print(
            f"Title          : "
            f"{title}"
        )

        print(
            f"Bullets        : "
            f"{len(bullets)}"
        )

        print(
            "Sections       :",
            section_headings,
        )

        # ======================================================
        # DASHBOARD
        # ======================================================

        dashboard_bullets = []

        for bullet in bullets:

            text = str(
                getattr(
                    bullet,
                    "text",
                    bullet,
                )
                or ""
            )

            text = text.replace(
                "__SUBTOPIC__:",
                "",
            )

            text = text.replace(
                "__LEAD__:",
                "",
            )

            text = text.strip()

            if text:

                dashboard_bullets.append(
                    text
                )

        dashboard_state.update_slide(
            title,
            dashboard_bullets,
            slide.slide_number,
        )

        dashboard_state.set_pipeline(
            "Content Generated",
            "Generating",
        )

        # ======================================================
        # SLIDE MANAGER
        # ======================================================

        if self.slide_manager is None:

            raise RuntimeError(
                "Slide manager is not registered."
            )

        if create_slide:

            result = (
                self.slide_manager.create_slide(
                    slide,
                    content,
                )
            )

        else:

            result = (
                self.slide_manager.update_slide(
                    slide,
                    content,
                )
            )

        # ======================================================
        # RESULT
        # ======================================================

        print(
            f"Slide Generation : "
            f"{'SUCCESS' if result.success else 'FAILED'}"
        )

        print(
            f"PPT              : "
            f"{result.presentation_path or '-'}"
        )

        print(
            "=" * 70
        )

        return {
            "is_relevant": True,

            # IMPORTANT:
            # Structural subtopics are considered pipeline-level
            # new teaching topics.
            "is_new_topic": pipeline_new_topic,

            "topic": str(topic),

            "confidence": confidence,

            "slide_action": slide_action,

            "slide_decision_reason": (
                slide_decision.reason
            ),

            "slide_number": (
                slide.slide_number
            ),

            "content_generated": True,

            "title": title,

            "bullets": [
                getattr(
                    bullet,
                    "text",
                    str(bullet),
                )
                for bullet in bullets
            ],

            "sections": section_headings,

            "content_type": getattr(
                content,
                "content_type",
                "",
            ),

            "visual_type": getattr(
                content,
                "visual_type",
                "",
            ),

            "visual_reason": getattr(
                content,
                "visual_reason",
                "",
            ),

            "visual_spec": getattr(
                content,
                "visual_spec",
                {},
            ),
        }


lecture_pipeline = LecturePipeline()