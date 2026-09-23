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

from app.transcript.transcript_intelligence import (
    transcript_intelligence,
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

        self.last_live_sample_count = 0

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
        # TRANSCRIPT MANAGERS
        #
        # - LiveTranscriptManager: terminal/UI display only.
        # - TranscriptIntelligence: authoritative transcript +
        #   analysis-ready chunks.
        # ==========================================================

        self.transcript_manager = (
            LiveTranscriptManager()
        )

        self.transcript_intelligence = (
            transcript_intelligence
        )

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

                self.live_executor.submit(
                    self._live_transcribe,
                    audio,
                    force,
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
        force=False,
    ):

        try:

            raw = (
                self.whisper.transcribe_audio(
                    audio
                )
            )

            if not raw:
                return

            raw = self.transcript_manager.normalize(
                raw
            )

            if not raw:
                return

            # --------------------------------------------------
            # Terminal/UI display update.
            #
            # LiveTranscriptManager still receives the raw
            # per-window Whisper output. It handles its own
            # paragraph/boundary display logic.
            # --------------------------------------------------

            self.transcript_manager.update(
                raw
            )

            # --------------------------------------------------
            # Authoritative transcript + analysis chunking.
            # --------------------------------------------------

            chunk = (
                self.transcript_intelligence
                .process(
                    raw,
                    force=force,
                )
            )

            dashboard_state.update_transcript(
                self.transcript_intelligence
                .authoritative_transcript()
            )

            sys.stdout.flush()

            if chunk is None:
                return

            self._queue_backend_analysis(
                chunk.text,
                force=chunk.is_forced,
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
        chunk_text,
        force=False,
    ):

        if not chunk_text:
            return

        with self.analysis_lock:

            if not self.running:
                return

            if (
                self.analysis_future is not None
                and not self.analysis_future.done()
            ):

                return

            try:

                self.analysis_future = (
                    self.analysis_executor.submit(
                        self._analyze_chunk,
                        chunk_text,
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

            if isinstance(
                result,
                dict,
            ):

                # ----------------------------------------------
                # Mark analyzed only when the pipeline actually
                # consumed the text (relevant or not).
                # ----------------------------------------------

                if result.get(
                    "content_generated",
                    False,
                ) or (
                    result.get("is_relevant") is False
                ):

                    self.transcript_intelligence.mark_analyzed(
                        transcript
                    )

                # ----------------------------------------------
                # New topic.
                # ----------------------------------------------

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

                    self.transcript_intelligence.start_new_topic(
                        transcript
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

                if self.detector.is_speech(
                    chunk
                ):

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

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter = 0

                    current_samples = (
                        self.builder.sample_count()
                    )

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
                            audio_window
                        )

                else:

                    if not self.recording:
                        continue

                    self.builder.add_chunk(
                        chunk
                    )

                    self.silence_counter += 1

                    if self.silence_counter >= 80:

                        app_logger.success(
                            "Speech Finished"
                        )

                        current_samples = (
                            self.builder.sample_count()
                        )

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