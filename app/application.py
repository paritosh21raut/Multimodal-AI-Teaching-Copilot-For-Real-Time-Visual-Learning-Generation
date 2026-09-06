from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app.audio.audio_pipeline import AudioPipeline
from app.audio.live_transcript_manager import LiveTranscriptManager
from app.dashboard.dashboard_state import dashboard_state
from app.knowledge.content_generator import content_generator
from app.lecture.lecture_pipeline import lecture_pipeline
from app.ppt.ppt_manager import ppt_manager
from app.speech.transcript_intelligence import transcript_intelligence
from app.slides.slide_manager import slide_manager
from app.topics.topic_intelligence import topic_intelligence
from app.utils.logger import app_logger


class Application:

    def __init__(self):

        app_logger.info(
            "Initializing Application"
        )

        # ----------------------------------------------------------
        # Live transcript state.
        # ----------------------------------------------------------

        self.transcript_manager = (
            LiveTranscriptManager()
        )

        # ----------------------------------------------------------
        # Transcript intelligence.
        # ----------------------------------------------------------

        self.transcript_intelligence = (
            transcript_intelligence
        )

        # ----------------------------------------------------------
        # Backend analysis executor.
        # ----------------------------------------------------------

        self.analysis_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LectureAnalysis",
            )
        )

        self.analysis_future = None

        # ----------------------------------------------------------
        # Audio / STT.
        # ----------------------------------------------------------

        self.pipeline = AudioPipeline(
            on_preview_transcript=(
                self._handle_preview_transcript
            ),
            on_final_transcript=(
                self._handle_final_transcript
            ),
        )

        # ----------------------------------------------------------
        # Lecture pipeline integration.
        # ----------------------------------------------------------

        lecture_pipeline.register_topic_detector(
            topic_intelligence
        )

        lecture_pipeline.register_content_generator(
            content_generator
        )

        lecture_pipeline.register_slide_manager(
            slide_manager
        )

        # ----------------------------------------------------------
        # Presentation initialization.
        # ----------------------------------------------------------

        ppt_manager.create_new_presentation(
            "Live Lecture"
        )

        ppt_manager.add_title_slide(
            title="Live Lecture",
            subtitle="AI Teaching Copilot",
        )

        app_logger.success(
            "Lecture Pipeline Ready"
        )

    # ==========================================================
    # LIVE PREVIEW
    # ==========================================================

    def _handle_preview_transcript(
        self,
        preview_text: str,
        authoritative_transcript: str,
    ):

        preview_text = (
            preview_text or ""
        ).strip()

        authoritative_transcript = (
            authoritative_transcript or ""
        ).strip()

        if not preview_text:
            return

        if authoritative_transcript:

            display_text = (
                authoritative_transcript
                + " "
                + preview_text
            )

        else:

            display_text = preview_text

        try:

            dashboard_state.update_transcript(
                display_text
            )

        except Exception as error:

            app_logger.error(
                "Dashboard preview update failed: "
                f"{error}"
            )

    # ==========================================================
    # FINAL TRANSCRIPT
    # ==========================================================

    def _handle_final_transcript(
        self,
        segment_text: str,
        full_transcript: str,
        segment_id: int,
    ):

        if not full_transcript.strip():
            return

        # ----------------------------------------------------------
        # Authoritative Whisper transcript.
        #
        # Preview text never enters transcript intelligence or
        # lecture analysis.
        # ----------------------------------------------------------

        try:

            self.transcript_manager.update(
                full_transcript
            )

        except Exception as error:

            app_logger.error(
                "Transcript manager update failed: "
                f"{error}"
            )

        # ----------------------------------------------------------
        # Dashboard always receives authoritative STT output.
        # ----------------------------------------------------------

        try:

            dashboard_state.update_transcript(
                full_transcript
            )

        except Exception as error:

            app_logger.error(
                "Dashboard transcript update failed: "
                f"{error}"
            )

        # ----------------------------------------------------------
        # Backend analysis.
        # ----------------------------------------------------------

        self._queue_backend_analysis(
            full_transcript
        )

    # ==========================================================
    # BACKEND ANALYSIS
    # ==========================================================

    def _queue_backend_analysis(self, transcript):
        raw_chunk = self.transcript_manager.get_new_analysis_text(transcript)
        if not raw_chunk:
            return

        if (
            self.analysis_future is not None
            and not self.analysis_future.done()
        ):
            return

        context = self.transcript_manager.get_analysis_context(
            transcript=transcript,
            analysis_text=raw_chunk,
        )

        try:
            refinement = self.transcript_intelligence.refine(
                raw_chunk,
                context=context,
            )
            refined_chunk = refinement.refined_text.strip()
        except Exception as error:
            app_logger.error(
                "Transcript refinement failed: " + f"{error}"
            )
            refined_chunk = raw_chunk

        if not refined_chunk:
            return

        try:
            self.analysis_future = self.analysis_executor.submit(
                self._analyze_chunk,
                raw_chunk,
                refined_chunk,
            )
        except RuntimeError:
            pass

    # ==========================================================
    # ANALYSIS WORKER
    # ==========================================================

    def _analyze_chunk(
        self,
        raw_chunk: str,
        refined_chunk: str,
    ):

        try:

            print()

            print(
                "\n"
                + "=" * 70
            )

            print(
                "LECTURE ANALYSIS"
            )

            print(
                "=" * 70
            )

            print(
                f"Raw chunk: {raw_chunk}"
            )

            print(
                f"Refined chunk: {refined_chunk}"
            )

            print(
                "-" * 70
            )

            # ------------------------------------------------------
            # Refined transcript enters the lecture pipeline.
            # ------------------------------------------------------

            result = (
                lecture_pipeline
                .process_transcript(
                    refined_chunk
                )
            )

            if isinstance(
                result,
                dict,
            ):

                # --------------------------------------------------
                # Mark the ORIGINAL authoritative sentences as
                # analyzed.
                #
                # This is important because the manager tracks
                # authoritative Whisper text, not refined text.
                # --------------------------------------------------

                if result.get(
                    "is_relevant",
                    False,
                ):

                    self.transcript_manager.mark_analyzed(
                        raw_chunk
                    )

                # --------------------------------------------------
                # New topic boundary.
                # --------------------------------------------------

                if result.get(
                    "is_new_topic",
                    False,
                ):

                    topic = result.get(
                        "topic",
                        "",
                    )

                    self.transcript_manager.start_new_topic(
                        topic=topic,
                        boundary_text=refined_chunk,
                    )

            print(
                "=" * 70
            )

        except Exception as error:

            app_logger.error(
                "Backend analysis error: "
                f"{error}"
            )

    # ==========================================================
    # START
    # ==========================================================

    def start(self):

        app_logger.success(
            "Application Started"
        )

        try:

            self.pipeline.start()

        finally:

            try:

                self.analysis_executor.shutdown(
                    wait=False,
                    cancel_futures=True,
                )

            except Exception:
                pass