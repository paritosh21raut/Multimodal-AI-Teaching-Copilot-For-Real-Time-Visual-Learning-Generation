from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from app.audio.voice_detector import VoiceDetector
from app.audio.audio_recorder import AudioRecorder
from app.speech.speech_segment_builder import SpeechSegmentBuilder
from app.speech.whisper_worker import WhisperWorker

from app.audio.live_transcript_manager import (
    LiveTranscriptManager,
)

from app.utils.logger import app_logger

from app.lecture.lecture_pipeline import (
    lecture_pipeline,
)

from app.dashboard.dashboard_state import (
    dashboard_state,
)


class AudioWorker(threading.Thread):

    def __init__(
        self,
        audio_queue,
    ):

        super().__init__(
            daemon=True
        )

        self.audio_queue = audio_queue

        self.detector = VoiceDetector()

        self.builder = (
            SpeechSegmentBuilder()
        )

        self.recorder = (
            AudioRecorder()
        )

        self.whisper = (
            WhisperWorker()
        )

        self.recording = False

        self.silence_counter = 0

        self.running = True

        # ==========================================================
        # LIVE WHISPER PREVIEW
        # ==========================================================

        self.sample_rate = 16000

        self.live_interval_seconds = 4.0

        self.live_interval_samples = int(
            self.sample_rate
            * self.live_interval_seconds
        )

        self.last_live_sample_count = 0

        # ----------------------------------------------------------
        # Live previews are intentionally serialized.
        #
        # They are NOT used for backend analysis.
        # ----------------------------------------------------------

        self.live_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LiveWhisper",
            )
        )

        self.live_lock = threading.Lock()

        # ==========================================================
        # FINAL WHISPER
        #
        # IMPORTANT:
        #
        # Final transcription gets the ENTIRE speech segment.
        #
        # This restores the old Dashboard V2 behavior where Whisper
        # had the complete context of what the teacher said.
        # ==========================================================

        self.final_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="FinalWhisper",
            )
        )

        self.final_lock = threading.Lock()

        # ==========================================================
        # BACKEND ANALYSIS
        # ==========================================================

        self.analysis_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LectureAnalysis",
            )
        )

        self.analysis_lock = threading.Lock()

        # ==========================================================
        # TRANSCRIPT MANAGER
        # ==========================================================

        self.transcript_manager = (
            LiveTranscriptManager()
        )

        # ==========================================================
        # LECTURE TRANSCRIPT STATE
        # ==========================================================

        # One entry per speech segment.
        #
        # Live Whisper temporarily fills the segment.
        # Final Whisper replaces it with the accurate full-segment
        # transcript.
        #
        # This prevents duplicate text.
        # ==========================================================

        self.segment_lock = threading.RLock()

        self.segment_counter = 0

        self.active_segment_id = None

        self.segment_transcripts = {}

        self.segment_order = []

        self.current_transcript = ""

    # ==========================================================
    # SEGMENT STATE
    # ==========================================================

    def _start_new_segment(self):

        with self.segment_lock:

            self.segment_counter += 1

            segment_id = (
                self.segment_counter
            )

            self.active_segment_id = (
                segment_id
            )

            self.segment_transcripts[
                segment_id
            ] = ""

            self.segment_order.append(
                segment_id
            )

            return segment_id

    def _set_segment_transcript(
        self,
        segment_id,
        transcript,
    ):

        transcript = (
            self.transcript_manager
            .normalize(
                transcript
            )
        )

        with self.segment_lock:

            if segment_id not in (
                self.segment_transcripts
            ):
                return

            self.segment_transcripts[
                segment_id
            ] = transcript

            self.current_transcript = (
                self._build_full_transcript()
            )

    def _build_full_transcript(
        self,
    ) -> str:

        with self.segment_lock:

            texts = []

            for segment_id in (
                self.segment_order
            ):

                text = (
                    self.segment_transcripts
                    .get(
                        segment_id,
                        "",
                    )
                    .strip()
                )

                if text:
                    texts.append(
                        text
                    )

            return " ".join(
                texts
            ).strip()

    def _get_active_segment_id(
        self,
    ):

        with self.segment_lock:

            return self.active_segment_id

    # ==========================================================
    # LIVE WHISPER SUBMISSION
    # ==========================================================

    def _submit_live_transcription(
        self,
        audio,
        segment_id,
    ):

        if audio is None:
            return

        if len(audio) == 0:
            return

        with self.live_lock:

            if not self.running:
                return

            try:

                self.live_executor.submit(
                    self._live_transcribe,
                    audio,
                    segment_id,
                )

            except RuntimeError:

                return

            except Exception as error:

                app_logger.error(
                    "Live transcription submit failed: "
                    f"{error}"
                )

    # ==========================================================
    # LIVE WHISPER
    # ==========================================================

    def _live_transcribe(
        self,
        audio,
        segment_id,
    ):

        try:

            transcript = (
                self.whisper.transcribe_audio(
                    audio
                )
            )

            if not transcript:
                return

            transcript = (
                self.transcript_manager
                .normalize(
                    transcript
                )
            )

            if not transcript:
                return

            # ------------------------------------------------------
            # IMPORTANT:
            #
            # Live Whisper is only a PREVIEW.
            #
            # It never triggers Topic Intelligence,
            # Gemini, Ollama or PPT generation.
            # ------------------------------------------------------

            self._set_segment_transcript(
                segment_id,
                transcript,
            )

            full_transcript = (
                self.current_transcript
            )

            self.transcript_manager.update(
                full_transcript
            )

            dashboard_state.update_transcript(
                full_transcript
            )

        except Exception as error:

            if self.running:

                traceback.print_exc()

                app_logger.error(
                    "Live transcription error: "
                    f"{error}"
                )

    # ==========================================================
    # FINAL WHISPER SUBMISSION
    # ==========================================================

    def _submit_final_transcription(
        self,
        audio,
        segment_id,
    ):

        if audio is None:
            return

        if len(audio) == 0:
            return

        with self.final_lock:

            if not self.running:
                return

            try:

                # --------------------------------------------------
                # IMPORTANT:
                #
                # Every completed speech segment gets its own final
                # Whisper job.
                #
                # Nothing is discarded because another final job
                # may already be running.
                # --------------------------------------------------

                self.final_executor.submit(
                    self._final_transcribe,
                    audio,
                    segment_id,
                )

            except RuntimeError:

                return

            except Exception as error:

                app_logger.error(
                    "Final transcription submit failed: "
                    f"{error}"
                )

    # ==========================================================
    # FINAL WHISPER
    # ==========================================================

    def _final_transcribe(
        self,
        audio,
        segment_id,
    ):

        try:

            app_logger.info(
                "Starting FINAL full-segment Whisper..."
            )

            transcript = (
                self.whisper.transcribe_audio(
                    audio
                )
            )

            transcript = (
                self.transcript_manager
                .normalize(
                    transcript
                )
            )

            if not transcript:

                app_logger.warning(
                    "Final Whisper returned empty transcript."
                )

                return

            app_logger.success(
                "Final full-segment transcription completed"
            )

            # ------------------------------------------------------
            # Replace the live preview with the accurate
            # full-segment transcript.
            #
            # This is the critical part.
            # ------------------------------------------------------

            self._set_segment_transcript(
                segment_id,
                transcript,
            )

            full_transcript = (
                self.current_transcript
            )

            self.transcript_manager.update(
                full_transcript
            )

            dashboard_state.update_transcript(
                full_transcript
            )

            print()
            print(
                "=" * 70
            )

            print(
                "FINAL TRANSCRIPT"
            )

            print(
                "=" * 70
            )

            print(
                transcript
            )

            print(
                "=" * 70
            )

            # ------------------------------------------------------
            # ONLY FINAL TRANSCRIPT GOES TO BACKEND ANALYSIS.
            #
            # This is what restores the old accurate behavior.
            # ------------------------------------------------------

            self._queue_backend_analysis(
                transcript
            )

        except Exception as error:

            if self.running:

                traceback.print_exc()

                app_logger.error(
                    "Final Whisper error: "
                    f"{error}"
                )

    # ==========================================================
    # BACKEND ANALYSIS
    # ==========================================================

    def _queue_backend_analysis(
        self,
        transcript,
    ):

        transcript = (
            self.transcript_manager
            .normalize(
                transcript
            )
        )

        if not transcript:
            return

        with self.analysis_lock:

            if not self.running:
                return

            try:

                # --------------------------------------------------
                # DO NOT DROP ANALYSIS because another analysis is
                # running.
                #
                # ThreadPoolExecutor queues completed speech
                # segments automatically.
                # --------------------------------------------------

                self.analysis_executor.submit(
                    self._analyze_chunk,
                    transcript,
                )

            except RuntimeError:

                return

    # ==========================================================
    # BACKEND ANALYSIS WORKER
    # ==========================================================

    def _analyze_chunk(
        self,
        transcript,
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
                f"Analyzing: {transcript}"
            )

            print(
                "-" * 70
            )

            result = (
                lecture_pipeline
                .process_transcript(
                    transcript
                )
            )

            # ------------------------------------------------------
            # Record that this finalized speech segment was handled.
            # ------------------------------------------------------

            if isinstance(
                result,
                dict,
            ):

                if result.get(
                    "is_relevant",
                    False,
                ):

                    self.transcript_manager.mark_analyzed(
                        transcript
                    )

                # --------------------------------------------------
                # Topic transition
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
                        boundary_text=transcript,
                    )

            print(
                "=" * 70
            )

        except Exception as error:

            traceback.print_exc()

            app_logger.error(
                "Backend analysis error: "
                f"{error}"
            )

    # ==========================================================
    # RESET SPEECH DETECTION STATE
    # ==========================================================

    def _reset_speech_state(
        self,
    ):

        self.builder.clear()

        self.recording = False

        self.silence_counter = 0

        self.last_live_sample_count = 0

        self.active_segment_id = None

        dashboard_state.set_microphone(
            "Ready"
        )

    # ==========================================================
    # AUDIO LOOP
    # ==========================================================

    def run(self):

        app_logger.success(
            "Audio Worker Started"
        )

        while self.running:

            try:

                if self.audio_queue.empty():

                    time.sleep(
                        0.01
                    )

                    continue

                chunk = (
                    self.audio_queue.get()
                )

                # ==================================================
                # SPEECH
                # ==================================================

                if self.detector.is_speech(
                    chunk
                ):

                    # ------------------------------------------------
                    # Speech begins.
                    # ------------------------------------------------

                    if not self.recording:

                        self.recording = True

                        self.builder.clear()

                        self.silence_counter = 0

                        self.last_live_sample_count = 0

                        segment_id = (
                            self._start_new_segment()
                        )

                        dashboard_state.set_microphone(
                            "Speaking"
                        )

                        app_logger.success(
                            f"Speech Started "
                            f"(segment {segment_id})"
                        )

                    # ------------------------------------------------
                    # Every incoming chunk is preserved.
                    # ------------------------------------------------

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter = 0

                    current_samples = (
                        self.builder.sample_count()
                    )

                    # ------------------------------------------------
                    # LIVE PREVIEW
                    #
                    # Every ~4 seconds.
                    # These windows are NON-OVERLAPPING and are only
                    # for immediate transcript display.
                    # ------------------------------------------------

                    if (
                        current_samples
                        - self.last_live_sample_count
                        >= self.live_interval_samples
                    ):

                        full_audio = (
                            self.builder.snapshot()
                        )

                        start = (
                            self.last_live_sample_count
                        )

                        end = (
                            current_samples
                        )

                        audio_window = (
                            full_audio[
                                start:end
                            ]
                        )

                        self.last_live_sample_count = (
                            end
                        )

                        self._submit_live_transcription(
                            audio_window,
                            segment_id,
                        )

                # ==================================================
                # SILENCE
                # ==================================================

                else:

                    if not self.recording:

                        continue

                    # ------------------------------------------------
                    # Preserve trailing silence.
                    # ------------------------------------------------

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter += 1

                    # ------------------------------------------------
                    # Around 2 seconds of silence.
                    # ------------------------------------------------

                    if self.silence_counter >= 80:

                        app_logger.success(
                            "Speech Finished"
                        )

                        segment_id = (
                            self._get_active_segment_id()
                        )

                        current_samples = (
                            self.builder.sample_count()
                        )

                        # ------------------------------------------------
                        # CRITICAL:
                        #
                        # Capture the ENTIRE speech segment.
                        #
                        # Do NOT send only the remaining 2-4 seconds.
                        # ------------------------------------------------

                        full_audio = (
                            self.builder.snapshot()
                        )

                        # ------------------------------------------------
                        # Queue final full-segment Whisper before clearing
                        # the speech state.
                        # ------------------------------------------------

                        if (
                            full_audio is not None
                            and len(full_audio) > 0
                            and segment_id is not None
                        ):

                            self._submit_final_transcription(
                                full_audio,
                                segment_id,
                            )

                        # ------------------------------------------------
                        # We can immediately start accepting new speech.
                        #
                        # Final Whisper runs independently.
                        # No audio is lost while it processes.
                        # ------------------------------------------------

                        self._reset_speech_state()

            except Exception as error:

                if self.running:

                    traceback.print_exc()

                    app_logger.error(
                        "Audio worker error: "
                        f"{error}"
                    )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(self):

        if not self.running:

            return

        self.running = False

        dashboard_state.set_microphone(
            "Stopping"
        )

        try:

            self.live_executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

        except Exception:
            pass

        try:

            self.final_executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

        except Exception:
            pass

        try:

            self.analysis_executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

        except Exception:
            pass

        app_logger.info(
            "Audio Worker Stop Requested"
        )