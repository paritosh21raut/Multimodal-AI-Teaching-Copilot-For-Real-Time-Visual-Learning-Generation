from __future__ import annotations

from threading import Lock

from app.lecture.context_buffer import (
    context_buffer,
)

from app.lecture.lecture_state import (
    lecture_state,
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

        # ----------------------------------------------------------
        # Semantic topic analysis
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Irrelevant speech
        # ----------------------------------------------------------

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
                f"Reason        : {decision.reason}"
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
            }

        # ----------------------------------------------------------
        # Add only relevant speech to lecture context
        # ----------------------------------------------------------

        context_buffer.add(
            transcript
        )

        # ----------------------------------------------------------
        # Confidence
        # ----------------------------------------------------------

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
                    1.0 - float(
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

        # ----------------------------------------------------------
        # Slide decision
        # ----------------------------------------------------------

        if decision.is_new_topic:

            slide_action = (
                "NEW SLIDE"
            )

            slide = (
                lecture_state.create_slide(
                    decision.topic
                )
            )

        else:

            slide_action = (
                "SAME SLIDE - UPDATE"
            )

            lecture_state.update_current_slide()

            slide = (
                lecture_state.get_current_slide()
            )

        lecture_state.set_current_topic(
            decision.topic,
            decision.embedding,
        )

        # ----------------------------------------------------------
        # Analysis report
        # ----------------------------------------------------------

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
            f"Input Chunk    : {transcript}"
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
            f"Slide Number   : "
            f"{slide.slide_number}"
        )

        print(
            f"Reason         : "
            f"{decision.reason}"
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

        # ----------------------------------------------------------
        # Generate structured slide content
        # ----------------------------------------------------------

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
                f"Error              : {error}"
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
                "content_generated": False,
            }

        # ----------------------------------------------------------
        # Content intelligence report
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Dashboard
        # ----------------------------------------------------------

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

        # ----------------------------------------------------------
        # Existing PPT/SlideManager
        # ----------------------------------------------------------

        if decision.is_new_topic:

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