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
        # LIVE TRANSCRIPTION
        # ==========================================================

        self.sample_rate = 16000

        self.live_interval_seconds = 2.0

        self.live_interval_samples = int(
            self.sample_rate
            * self.live_interval_seconds
        )

        # Number of samples already placed into the
        # Whisper processing queue for the current speech segment.
        self.last_live_sample_count = 0

        # ----------------------------------------------------------
        # IMPORTANT
        #
        # Whisper jobs are now QUEUED.
        #
        # We do NOT skip a new audio segment just because the
        # previous Whisper job is still running.
        # ----------------------------------------------------------

        self.live_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LiveWhisper",
            )
        )

        self.live_lock = threading.Lock()

        # ==========================================================
        # BACKEND ANALYSIS
        # ==========================================================

        self.analysis_executor = (
            ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="LectureAnalysis",
            )
        )

        self.analysis_future = None

        self.analysis_lock = threading.Lock()

        # ==========================================================
        # TRANSCRIPT MANAGER
        # ==========================================================

        self.transcript_manager = (
            LiveTranscriptManager()
        )

        # Complete transcript accumulated during the lecture.
        self.current_transcript = ""

    # ==========================================================
    # LIVE WHISPER QUEUE
    # ==========================================================

    def _submit_live_transcription(
        self,
        audio,
        force=False,
    ):

        if audio is None:
            return

        if len(audio) == 0:
            return

        with self.live_lock:

            if not self.running:
                return

            try:

                # --------------------------------------------------
                # ALWAYS QUEUE THE AUDIO.
                #
                # Never discard a segment because Whisper is busy.
                # --------------------------------------------------

                self.live_executor.submit(
                    self._live_transcribe,
                    audio,
                    force,
                )

            except RuntimeError:

                # Executor is shutting down.
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
        force=False,
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

            # --------------------------------------------------
            # IMPORTANT:
            #
            # Each Whisper job represents a NEW non-overlapping
            # audio window.
            #
            # Append it to the current lecture transcript instead
            # of replacing the existing transcript.
            # --------------------------------------------------

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
                self.transcript_manager
                .normalize(
                    self.current_transcript
                )
            )

            # --------------------------------------------------
            # Update single live transcript.
            # --------------------------------------------------

            self.transcript_manager.update(
                self.current_transcript
            )

            dashboard_state.update_transcript(
                self.current_transcript
            )

            sys.stdout.flush()

            # --------------------------------------------------
            # Backend analysis works independently.
            # --------------------------------------------------

            self._queue_backend_analysis(
                self.current_transcript,
                force=force,
            )

        except Exception as error:

            if self.running:

                traceback.print_exc()

                app_logger.error(
                    "Live transcription error: "
                    f"{error}"
                )

    # ==========================================================
    # BACKEND ANALYSIS
    # ==========================================================

    def _queue_backend_analysis(
        self,
        transcript,
        force=False,
    ):

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

            # --------------------------------------------------
            # Backend analysis may still be busy.
            #
            # We intentionally leave the unprocessed chunk inside
            # LiveTranscriptManager.
            #
            # The next transcript update will retry it.
            # --------------------------------------------------

            if (
                self.analysis_future is not None
                and not self.analysis_future.done()
            ):

                return

            try:

                self.analysis_future = (
                    self.analysis_executor.submit(
                        self._analyze_chunk,
                        chunk,
                    )
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

            # --------------------------------------------------
            # Mark successful analysis.
            # --------------------------------------------------

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
    # RESET SPEECH DETECTION STATE
    # ==========================================================

    def _reset_speech_state(
        self,
    ):

        self.builder.clear()

        self.recording = False

        self.silence_counter = 0

        self.last_live_sample_count = 0

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

                        dashboard_state.set_microphone(
                            "Speaking"
                        )

                        app_logger.success(
                            "Speech Started"
                        )

                    # ------------------------------------------------
                    # EVERY audio chunk is stored.
                    # ------------------------------------------------

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter = 0

                    current_samples = (
                        self.builder.sample_count()
                    )

                    # ------------------------------------------------
                    # Every ~2 seconds create ONE NEW NON-OVERLAPPING
                    # audio window.
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

                        # Mark these samples as queued BEFORE
                        # submitting, so they can never be queued
                        # twice.
                        self.last_live_sample_count = (
                            end
                        )

                        self._submit_live_transcription(
                            audio_window
                        )

                # ==================================================
                # SILENCE
                # ==================================================

                else:

                    if not self.recording:
                        continue

                    # Keep trailing silence.
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

                        current_samples = (
                            self.builder.sample_count()
                        )

                        # ------------------------------------------------
                        # Queue any final unprocessed speech.
                        # ------------------------------------------------

                        if (
                            current_samples
                            > self.last_live_sample_count
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
                                force=True,
                            )

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

            self.analysis_executor.shutdown(
                wait=False,
                cancel_futures=True,
            )

        except Exception:
            pass

        app_logger.info(
            "Audio Worker Stop Requested"
        )