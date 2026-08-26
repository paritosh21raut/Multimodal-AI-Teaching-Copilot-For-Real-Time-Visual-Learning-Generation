from __future__ import annotations

import sys
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

        # ==========================================================
        # AUDIO
        # ==========================================================

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

        # Incrementing segment id.
        self.segment_number = 0

        # ==========================================================
        # SEGMENTATION
        # ==========================================================

        self.sample_rate = 16000

        # ----------------------------------------------------------
        # Natural pause:
        #
        # 80 audio callbacks ~= 2 seconds with the current
        # sounddevice configuration.
        # ----------------------------------------------------------

        self.pause_limit = 80

        # ----------------------------------------------------------
        # Hard maximum:
        #
        # We do not wait forever if the teacher talks continuously.
        #
        # 30 seconds keeps the segment large enough for Whisper
        # context while preventing extremely long processing.
        # ----------------------------------------------------------

        self.max_segment_seconds = 30.0

        self.max_segment_samples = int(
            self.sample_rate
            * self.max_segment_seconds
        )

        # ==========================================================
        # LIVE PREVIEW
        # ==========================================================

        # Preview is intentionally independent from the final
        # transcription.
        #
        # It is for immediate dashboard / terminal feedback only.
        # The final Whisper pass is responsible for the authoritative
        # transcript used by lecture analysis.
        #

        self.live_interval_seconds = 6.0

        self.live_interval_samples = int(
            self.sample_rate
            * self.live_interval_seconds
        )

        self.last_live_sample_count = 0

        self.live_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LiveWhisper",
            )
        )

        self.live_lock = threading.Lock()

        # ==========================================================
        # FINAL WHISPER
        # ==========================================================

        # Final transcription is allowed to run independently from
        # microphone capture.
        #
        # This executor must NOT block the audio loop.
        #
        # max_workers=1 preserves segment ordering.
        #

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

        # One analysis worker preserves lecture order.
        #
        # IMPORTANT:
        # We NEVER reject a new analysis just because this worker
        # is busy. ThreadPoolExecutor already gives us a FIFO queue.
        #

        self.analysis_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LectureAnalysis",
            )
        )

        self.analysis_lock = threading.Lock()

        # ==========================================================
        # TRANSCRIPT MANAGEMENT
        # ==========================================================

        self.transcript_manager = (
            LiveTranscriptManager()
        )

        # Authoritative transcript accumulated during the lecture.
        self.current_transcript = ""

        # Lock protecting current_transcript.
        self.transcript_lock = threading.Lock()

    # ==========================================================
    # NORMALIZATION
    # ==========================================================

    @staticmethod
    def _normalize_text(
        text: str,
    ) -> str:

        return " ".join(
            text.strip().split()
        )

    # ==========================================================
    # SPEECH STATE
    # ==========================================================

    def _start_recording(self):

        if self.recording:
            return

        self.recording = True

        self.segment_number += 1

        self.builder.clear()

        self.silence_counter = 0

        self.last_live_sample_count = 0

        dashboard_state.set_microphone(
            "Speaking"
        )

        app_logger.success(
            "Speech Started "
            f"(segment {self.segment_number})"
        )

    def _reset_speech_state(self):

        self.builder.clear()

        self.recording = False

        self.silence_counter = 0

        self.last_live_sample_count = 0

        dashboard_state.set_microphone(
            "Ready"
        )

    # ==========================================================
    # LIVE PREVIEW
    # ==========================================================

    def _submit_live_preview(
        self,
        audio,
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
                    self._run_live_preview,
                    audio,
                )

            except RuntimeError:

                return

            except Exception as error:

                app_logger.error(
                    "Live preview submit failed: "
                    f"{error}"
                )

    def _run_live_preview(
        self,
        audio,
    ):

        try:

            transcript = (
                self.whisper.transcribe_audio(
                    audio
                )
            )

            transcript = (
                self._normalize_text(
                    transcript
                )
            )

            if not transcript:
                return

            print()
            print(
                f"[Live Preview] "
                f"{transcript}"
            )

            dashboard_state.update_transcript(
                transcript
            )

            sys.stdout.flush()

        except Exception as error:

            if self.running:

                traceback.print_exc()

                app_logger.error(
                    "Live preview error: "
                    f"{error}"
                )

    # ==========================================================
    # FINAL SEGMENT SUBMISSION
    # ==========================================================

    def _submit_final_segment(
        self,
        audio,
        segment_number: int,
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
                # IMPORTANT
                #
                # Every finalized audio segment is submitted.
                #
                # Never discard it because another final Whisper
                # job is still processing.
                #
                # The single-worker executor preserves order.
                # --------------------------------------------------

                self.final_executor.submit(
                    self._run_final_whisper,
                    audio,
                    segment_number,
                )

            except RuntimeError:

                return

            except Exception as error:

                traceback.print_exc()

                app_logger.error(
                    "Final transcription submit failed: "
                    f"{error}"
                )

    # ==========================================================
    # FINAL WHISPER
    # ==========================================================

    def _run_final_whisper(
        self,
        audio,
        segment_number: int,
    ):

        try:

            app_logger.info(
                "Starting FINAL Whisper for "
                f"segment {segment_number}..."
            )

            transcript = (
                self.whisper.transcribe_audio(
                    audio
                )
            )

            transcript = (
                self._normalize_text(
                    transcript
                )
            )

            if not transcript:

                app_logger.warning(
                    "Final Whisper returned empty "
                    f"transcript for segment "
                    f"{segment_number}."
                )

                return

            app_logger.success(
                "Final full-segment transcription "
                "completed"
            )

            print()
            print(
                "=" * 70
            )
            print(
                f"FINAL TRANSCRIPT - SEGMENT "
                f"{segment_number}"
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
            # Append to authoritative lecture transcript.
            # ------------------------------------------------------

            with self.transcript_lock:

                if self.current_transcript:

                    self.current_transcript = (
                        self.current_transcript
                        + " "
                        + transcript
                    )

                else:

                    self.current_transcript = (
                        transcript
                    )

                self.current_transcript = (
                    self._normalize_text(
                        self.current_transcript
                    )
                )

                full_transcript = (
                    self.current_transcript
                )

            # ------------------------------------------------------
            # Update dashboard with the complete accumulated
            # transcript.
            # ------------------------------------------------------

            self.transcript_manager.update(
                full_transcript
            )

            dashboard_state.update_transcript(
                full_transcript
            )

            sys.stdout.flush()

            # ------------------------------------------------------
            # FINAL SEGMENT -> BACKEND ANALYSIS
            #
            # IMPORTANT:
            #
            # Every final segment is sent to the analysis queue.
            # The analysis executor serializes the work.
            #
            # No segment is dropped because Gemini/Ollama is busy.
            # ------------------------------------------------------

            self._queue_backend_analysis(
                full_transcript,
                force=True,
                segment_number=segment_number,
            )

        except Exception as error:

            if self.running:

                traceback.print_exc()

                app_logger.error(
                    "Final Whisper error for "
                    f"segment {segment_number}: "
                    f"{error}"
                )

    # ==========================================================
    # BACKEND ANALYSIS QUEUE
    # ==========================================================

    def _queue_backend_analysis(
        self,
        transcript,
        force: bool = False,
        segment_number: int | None = None,
    ):

        transcript = (
            self._normalize_text(
                transcript
            )
            if transcript
            else ""
        )

        if not transcript:
            return

        chunk = (
            self.transcript_manager
            .get_new_analysis_text(
                transcript,
                force=force,
            )
        )

        if not chunk:
            return

        with self.analysis_lock:

            if not self.running:
                return

            try:

                # --------------------------------------------------
                # IMPORTANT
                #
                # DO NOT CHECK whether another analysis is already
                # running.
                #
                # The executor itself is the queue.
                #
                # Example:
                #
                # segment 1 -> running
                # segment 2 -> queued
                # segment 3 -> queued
                # segment 4 -> queued
                #
                # Nothing is dropped.
                # --------------------------------------------------

                self.analysis_executor.submit(
                    self._analyze_chunk,
                    chunk,
                    segment_number,
                )

                if segment_number is not None:

                    app_logger.info(
                        "Lecture analysis queued for "
                        f"segment {segment_number}"
                    )

                else:

                    app_logger.info(
                        "Lecture analysis queued"
                    )

            except RuntimeError:

                return

            except Exception as error:

                traceback.print_exc()

                app_logger.error(
                    "Lecture analysis submit failed: "
                    f"{error}"
                )

    # ==========================================================
    # BACKEND ANALYSIS WORKER
    # ==========================================================

    def _analyze_chunk(
        self,
        transcript,
        segment_number: int | None = None,
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

            if segment_number is not None:

                print(
                    f"Segment       : "
                    f"{segment_number}"
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
            # Mark successful analysis.
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
                # New topic
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
    # FINALIZE CURRENT SEGMENT
    # ==========================================================

    def _finalize_current_segment(
        self,
        reason: str,
    ):

        if not self.recording:
            return

        current_samples = (
            self.builder.sample_count()
        )

        if current_samples <= 0:

            self._reset_speech_state()

            return

        audio = (
            self.builder.snapshot()
        )

        segment_number = (
            self.segment_number
        )

        app_logger.success(
            "Speech Segment Finished "
            f"({reason})"
        )

        # ------------------------------------------------------
        # Submit final Whisper asynchronously.
        #
        # Recording can immediately begin again.
        # ------------------------------------------------------

        self._submit_final_segment(
            audio,
            segment_number,
        )

        # ------------------------------------------------------
        # IMPORTANT:
        #
        # Reset only segmentation state.
        #
        # The actual audio data is already owned by the final
        # Whisper executor.
        # ------------------------------------------------------

        self._reset_speech_state()

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

                    if not self.recording:

                        self._start_recording()

                    # ------------------------------------------------
                    # Store every incoming audio chunk.
                    # ------------------------------------------------

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter = 0

                    current_samples = (
                        self.builder.sample_count()
                    )

                    # ------------------------------------------------
                    # LIVE PREVIEW WINDOW
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

                        self._submit_live_preview(
                            audio_window
                        )

                    # ------------------------------------------------
                    # HARD MAXIMUM
                    # ------------------------------------------------

                    if (
                        current_samples
                        >= self.max_segment_samples
                    ):

                        self._finalize_current_segment(
                            reason="hard_max_duration"
                        )

                # ==================================================
                # SILENCE
                # ==================================================

                else:

                    if not self.recording:

                        continue

                    # ------------------------------------------------
                    # Keep trailing silence inside the segment.
                    # ------------------------------------------------

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter += 1

                    # ------------------------------------------------
                    # NATURAL PAUSE
                    # ------------------------------------------------

                    if (
                        self.silence_counter
                        >= self.pause_limit
                    ):

                        self._finalize_current_segment(
                            reason="natural_pause"
                        )

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

        # ----------------------------------------------------------
        # Stop accepting new jobs.
        # Existing queued jobs are allowed to finish.
        # ----------------------------------------------------------

        try:

            self.live_executor.shutdown(
                wait=False,
                cancel_futures=False,
            )

        except Exception:
            pass

        try:

            self.final_executor.shutdown(
                wait=False,
                cancel_futures=False,
            )

        except Exception:
            pass

        try:

            self.analysis_executor.shutdown(
                wait=False,
                cancel_futures=False,
            )

        except Exception:
            pass

        app_logger.info(
            "Audio Worker Stop Requested"
        )