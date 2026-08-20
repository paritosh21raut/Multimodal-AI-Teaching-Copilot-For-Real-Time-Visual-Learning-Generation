from __future__ import annotations

from threading import Lock

from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_state import lecture_state
from app.ppt.ppt_manager import ppt_manager
from app.dashboard.dashboard_state import dashboard_state

class LecturePipeline:

    def __init__(self):

        self._lock = Lock()

        self.topic_detector = None
        self.content_generator = None
        self.slide_manager = None

        self.started = False

    # ---------------------------------------------------------

    def register_topic_detector(self, detector):

        self.topic_detector = detector

    def register_content_generator(self, generator):

        self.content_generator = generator

    def register_slide_manager(self, manager):

        self.slide_manager = manager

    # ---------------------------------------------------------

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
                "AI Teaching Copilot"
            )

        context_buffer.clear()

        self.started = True

        print("[Pipeline] Started")

    # ---------------------------------------------------------

    def process_transcript(self, transcript: str):

        print("[Pipeline] Entered process_transcript")

        transcript = transcript.strip()

        if not transcript:
            print("[Pipeline] Empty transcript")
            return

        if not self.started:
            print("[Pipeline] Starting lecture")
            self.start()

        print("[Pipeline] Adding context")
        context_buffer.add(transcript)

        print("[Pipeline] Before topic detection")

        decision = self.topic_detector.process(
            latest_text=transcript,
            rolling_context=context_buffer.rolling_context(),
            current_topic=lecture_state.get_current_topic(),
            current_embedding=lecture_state.get_current_embedding(),
        )

        print("[Pipeline] After topic detection")

        if decision.is_new_topic:

            print("[Pipeline] Creating new slide")

            slide = lecture_state.create_slide(
                decision.topic
            )

        else:

            print("[Pipeline] Updating existing slide")

            lecture_state.update_current_slide()

            slide = lecture_state.get_current_slide()

        lecture_state.set_current_topic(
            decision.topic,
            decision.embedding,
        )

        print("[Pipeline] Generating content")

        content = self.content_generator.generate(
            topic=decision.topic,
            context=context_buffer.rolling_context(),
        )

        dashboard_state.update_transcript(
    transcript
)

        dashboard_state.update_topic(
            (
                decision.topic.name
                if hasattr(decision.topic, "name")
                else str(decision.topic)
            ),
            getattr(
                decision,
                "confidence",
                None,
            ),
        )

        dashboard_state.update_slide(
            content.title,
            [
                bullet.text
                for bullet in content.bullets
            ],
            slide.slide_number,
        )

        dashboard_state.set_pipeline(
            "Content Generated",
            "Generating",
        )

        print("[Pipeline] Sending to SlideManager")

        if decision.is_new_topic:

            self.slide_manager.create_slide(
                slide,
                content,
            )

        else:

            self.slide_manager.update_slide(
                slide,
                content,
            )

        print("[Pipeline] Finished")


lecture_pipeline = LecturePipeline()