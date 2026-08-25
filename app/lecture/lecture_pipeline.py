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


class LecturePipeline:

    def __init__(self):

        self._lock = Lock()

        self.topic_detector = None

        self.content_generator = None

        self.slide_manager = None

        self.started = False

        self.slide_decision_engine = (
            SlideDecisionEngine(
                max_slide_source_words=120,
                max_updates_per_slide=4,
                min_meaningful_words=4,
            )
        )

        # ==========================================================
        # LLM GENERATION AGGREGATION
        # ==========================================================

        self.pending_generation_chunks: list[str] = []

        self.pending_generation_words = 0

        self.pending_generation_sentences = 0

        self.generation_min_words = 35

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

    def _clear_generation_buffer(self):

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
            self._count_completed_sentences(text)
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
    # PROCESS
    # ==========================================================

    def process_transcript(
        self,
        transcript: str,
    ):

        transcript = transcript.strip()

        if not transcript:
            return None

        if not self.started:
            self.start()

        # ======================================================
        # SEMANTIC TOPIC ANALYSIS
        # ======================================================

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
        # IRRELEVANT SPEECH
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
        # ADD RELEVANT SPEECH TO CONTEXT
        # ======================================================

        context_buffer.add(
            transcript
        )

        # ======================================================
        # CONFIDENCE
        # ======================================================

        if (
            lecture_state.get_current_topic()
            is None
        ):

            confidence = 1.0

        elif decision.is_new_topic:

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
                    decision.is_new_topic
                ),

                current_slide_exists=(
                    current_slide_exists
                ),
            )
        )

        # ======================================================
        # REPORT DECISION
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

            print(
                "Action        : KEEP CURRENT SLIDE"
            )

            return {
                "is_relevant": True,
                "is_new_topic": False,
                "topic": (
                    lecture_state.get_current_topic()
                ),
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
        # NEW TOPIC / EXPLICIT SLIDE
        # Always generate immediately.
        # ======================================================

        force_generation = (
            slide_decision.action
            == SlideAction.CREATE
        )

        # ======================================================
        # SAME TOPIC
        # Accumulate before calling the LLM.
        # ======================================================

        if (
            slide_decision.action
            == SlideAction.UPDATE
        ):

            self._add_to_generation_buffer(
                transcript
            )

            print(
                f"[Pipeline] Pending generation "
                f"words: "
                f"{self.pending_generation_words}"
            )

            print(
                f"[Pipeline] Pending sentences: "
                f"{self.pending_generation_sentences}"
            )

            if not self._generation_buffer_ready():

                lecture_state.set_current_topic(
                    decision.topic,
                    decision.embedding,
                )

                dashboard_state.update_topic(
                    str(
                        decision.topic
                    ),
                    confidence,
                )

                current_slide_number = (
                    lecture_state.current_slide_number
                    if lecture_state.has_slides()
                    else None
                )

                print(
                    "[Pipeline] "
                    "Same-topic content accumulated. "
                    "Waiting for more meaningful content "
                    "before LLM generation."
                )

                return {
                    "is_relevant": True,
                    "is_new_topic": False,
                    "topic": str(
                        decision.topic
                    ),
                    "confidence": confidence,
                    "reason": slide_decision.reason,
                    "slide_action": "ACCUMULATE",
                    "slide_number": current_slide_number,
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
        # BUILD GENERATION CONTEXT
        # ======================================================

        if force_generation:

            if decision.is_new_topic:

                generation_text = transcript

            else:

                generation_text = (
                    self._generation_buffer_text()
                    or transcript
                )

        else:

            generation_text = (
                self._generation_buffer_text()
            )

        if not generation_text:

            generation_text = transcript

        # ======================================================
        # CREATE / UPDATE SLIDE
        # ======================================================

        if force_generation:

            slide_action = "NEW SLIDE"

            self._clear_generation_buffer()

            slide = (
                lecture_state.create_slide(
                    decision.topic
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
                        decision.topic
                    )
                )

                force_generation = True

        lecture_state.set_current_topic(
            decision.topic,
            decision.embedding,
        )

        # ======================================================
        # ANALYSIS REPORT
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
            f"{decision.topic}"
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
            f"New Topic      : "
            f"{decision.is_new_topic}"
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

        dashboard_state.update_topic(
            str(
                decision.topic
            ),
            confidence,
        )

        # ======================================================
        # LLM GENERATION
        # ======================================================

        print(
            "Generating educational content..."
        )

        try:

            content = (
                self.content_generator.generate(

                    topic=(
                        decision.topic
                    ),

                    context=(
                        context_buffer
                        .rolling_context()
                    ),
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
                "is_new_topic": (
                    decision.is_new_topic
                ),
                "topic": str(
                    decision.topic
                ),
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
                if force_generation
                else SlideAction.UPDATE
            ),
        )

        self._clear_generation_buffer()

        # ======================================================
        # CONTENT REPORT
        # ======================================================

        print(
            f"Content Type   : "
            f"{content.content_type}"
        )

        print(
            f"Visual Type    : "
            f"{content.visual_type}"
        )

        print(
            f"Visual Reason  : "
            f"{content.visual_reason}"
        )

        print(
            f"Visual Spec    : "
            f"{content.visual_spec}"
        )

        print(
            f"Title          : "
            f"{content.title}"
        )

        print(
            f"Bullets        : "
            f"{len(content.bullets)}"
        )

        # ======================================================
        # DASHBOARD
        # ======================================================

        dashboard_state.update_slide(
            content.title,
            [
                bullet.text
                for bullet
                in content.bullets
            ],
            slide.slide_number,
        )

        dashboard_state.set_pipeline(
            "Content Generated",
            "Generating",
        )

        # ======================================================
        # SLIDE MANAGER
        # ======================================================

        if force_generation:

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

            "is_new_topic": (
                decision.is_new_topic
            ),

            "topic": str(
                decision.topic
            ),

            "confidence": confidence,

            "slide_action": slide_action,

            "slide_decision_reason": (
                slide_decision.reason
            ),

            "slide_number": (
                slide.slide_number
            ),

            "content_generated": True,

            "title": content.title,

            "bullets": [
                bullet.text
                for bullet
                in content.bullets
            ],

            "content_type": (
                content.content_type
            ),

            "visual_type": (
                content.visual_type
            ),

            "visual_reason": (
                content.visual_reason
            ),

            "visual_spec": (
                content.visual_spec
            ),
        }


lecture_pipeline = LecturePipeline()