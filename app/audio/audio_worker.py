from __future__ import annotations

import os
import re
import tempfile
import threading
import time
import traceback
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor

from app.audio.audio_queue import AudioQueue
from app.audio.voice_detector import VoiceDetector
from app.speech.speech_segment_builder import SpeechSegmentBuilder
from app.speech.whisper_worker import WhisperWorker
from app.utils.logger import app_logger


class AudioWorker(threading.Thread):
    """
    Continuous production audio/STT worker.

    Pipeline:

        microphone
            ↓
        AudioQueue
            ↓
        VAD
            ↓
        speech accumulation
            ↓
        endpointing
            ↓
        preview / final Whisper scheduling
            ↓
        authoritative ordered transcript

    This class intentionally has no dependency on:

        Gemini
        Ollama
        Lecture Pipeline
        Dashboard
        Slides
        PPT generation

    Design priorities:

        1. Do not deadlock.
        2. Do not intentionally discard finalized speech.
        3. Preserve final transcript ordering.
        4. Keep Whisper execution serialized.
        5. Keep preview work replaceable.
        6. Support continuous speech with hard boundaries.
        7. Preserve a small overlap at hard boundaries.
        8. Drain already-captured audio during shutdown.
        9. Persist the authoritative transcript atomically.
    """

    def __init__(
        self,
        audio_queue: AudioQueue,
        on_preview_transcript=None,
        on_final_transcript=None,
        sample_rate: int = 16000,
        silence_duration_seconds: float = 1.2,
        minimum_speech_seconds: float = 0.3,
        maximum_segment_seconds: float = 30.0,
        overlap_seconds: float = 1.0,
        pre_roll_seconds: float = 0.25,
        preview_interval_seconds: float = 3.0,
        preview_window_seconds: float = 12.0,
        max_pending_final_jobs: int = 4,
        transcript_path: str = (
            "outputs/transcripts/live_transcript.txt"
        ),
    ):

        super().__init__(
            daemon=True,
            name="AudioWorker",
        )

        self.audio_queue = audio_queue

        self.on_preview_transcript = (
            on_preview_transcript
        )

        self.on_final_transcript = (
            on_final_transcript
        )

        self.sample_rate = int(sample_rate)

        self.silence_samples = max(
            1,
            int(
                self.sample_rate
                * silence_duration_seconds
            ),
        )

        self.minimum_speech_samples = max(
            1,
            int(
                self.sample_rate
                * minimum_speech_seconds
            ),
        )

        self.maximum_segment_samples = max(
            self.minimum_speech_samples,
            int(
                self.sample_rate
                * maximum_segment_seconds
            ),
        )

        self.overlap_samples = max(
            0,
            int(
                self.sample_rate
                * overlap_seconds
            ),
        )

        self.pre_roll_samples = max(
            0,
            int(
                self.sample_rate
                * pre_roll_seconds
            ),
        )

        self.preview_interval_samples = max(
            1,
            int(
                self.sample_rate
                * preview_interval_seconds
            ),
        )

        self.preview_window_samples = max(
            1,
            int(
                self.sample_rate
                * preview_window_seconds
            ),
        )

        self.max_pending_final_jobs = max(
            1,
            int(max_pending_final_jobs),
        )

        self.transcript_path = transcript_path

        # ----------------------------------------------------------
        # Production components.
        # ----------------------------------------------------------

        self.detector = VoiceDetector()

        self.builder = SpeechSegmentBuilder()

        self.whisper = WhisperWorker()

        # ----------------------------------------------------------
        # Worker lifecycle.
        # ----------------------------------------------------------

        self.running = True
        self.stop_requested = False

        self._stop_event = threading.Event()

        # ----------------------------------------------------------
        # Speech state.
        # ----------------------------------------------------------

        self.recording = False

        self.silence_sample_count = 0
        self.speech_sample_count = 0
        self.preview_sample_count = 0

        self.pre_roll = deque()
        self.pre_roll_sample_count = 0

        # ----------------------------------------------------------
        # Segment ordering.
        #
        # segment_id is assigned when a final segment is created.
        # Final jobs are always processed in this order.
        # ----------------------------------------------------------

        self.segment_id = 0

        self.authoritative_transcript = ""

        # ----------------------------------------------------------
        # Whisper execution.
        #
        # IMPORTANT:
        #
        # RLock is intentional.
        #
        # _submit_final() / _request_preview() may call
        # _pump_inference() while already holding this lock.
        #
        # A normal Lock would deadlock.
        # ----------------------------------------------------------

        self.inference_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="Whisper",
        )

        self.inference_lock = threading.RLock()

        self.inference_future: Future | None = None
        self.inference_kind = None
        self.inference_metadata = None

        # ----------------------------------------------------------
        # Final jobs.
        #
        # Do NOT use deque(maxlen=...) here.
        #
        # A bounded deque silently evicts an older final job when
        # full, which means speech can disappear.
        #
        # The configured limit is used as a diagnostic threshold,
        # not as a data-loss mechanism.
        # ----------------------------------------------------------

        self.pending_final_jobs = deque()

        # ----------------------------------------------------------
        # Preview:
        #
        # Only the newest preview matters.
        # ----------------------------------------------------------

        self.pending_preview_audio = None

        # ----------------------------------------------------------
        # Persistence.
        # ----------------------------------------------------------

        self._persist_lock = threading.Lock()

        # ----------------------------------------------------------
        # Metrics.
        # ----------------------------------------------------------

        self.metrics = {
            "chunks_processed": 0,
            "speech_chunks": 0,
            "silence_chunks": 0,

            "segments_finalized": 0,
            "natural_endpoints": 0,
            "hard_splits": 0,
            "short_segments_discarded": 0,

            "preview_requests": 0,
            "preview_submitted": 0,
            "preview_skipped": 0,
            "preview_completed": 0,

            "final_jobs_submitted": 0,
            "final_jobs_completed": 0,
            "final_jobs_failed": 0,
            "final_jobs_overflow": 0,

            "transcription_failures": 0,
            "transcript_characters": 0,

            "hard_split_overlap_samples": 0,
            "shutdown_queue_drained": 0,
        }

    # ==========================================================
    # QUEUE / PRE-ROLL HELPERS
    # ==========================================================

    def _remember_pre_roll(self, chunk):
        """
        Keep only the latest pre-roll audio while not recording.
        """

        if chunk is None:
            return

        self.pre_roll.append(chunk)

        self.pre_roll_sample_count += len(chunk)

        while (
            self.pre_roll_sample_count
            > self.pre_roll_samples
            and self.pre_roll
        ):
            old = self.pre_roll.popleft()

            self.pre_roll_sample_count -= len(old)

    def _clear_pre_roll(self):
        self.pre_roll.clear()
        self.pre_roll_sample_count = 0

    # ==========================================================
    # TRANSCRIPT MERGING
    # ==========================================================

    @staticmethod
    def _normalize_text(text: str) -> str:
        if not text:
            return ""

        return " ".join(
            str(text).strip().split()
        )

    @staticmethod
    def _tokens(text: str):
        if not text:
            return []

        return re.findall(
            r"\S+",
            text,
        )

    @classmethod
    def _find_boundary_overlap(
        cls,
        previous: str,
        current: str,
        maximum_words: int = 20,
        minimum_words: int = 3,
    ):
        """
        Find an exact token overlap at the previous/current boundary.

        Example:

            previous:
                ... neural networks use

            current:
                neural networks use transformer models

        Returns 3.
        """

        previous_tokens = cls._tokens(
            previous
        )

        current_tokens = cls._tokens(
            current
        )

        if (
            len(previous_tokens)
            < minimum_words
            or len(current_tokens)
            < minimum_words
        ):
            return 0

        maximum = min(
            maximum_words,
            len(previous_tokens),
            len(current_tokens),
        )

        previous_lower = [
            token.lower().strip(
                ".,!?;:\"'()[]{}"
            )
            for token in previous_tokens
        ]

        current_lower = [
            token.lower().strip(
                ".,!?;:\"'()[]{}"
            )
            for token in current_tokens
        ]

        for size in range(
            maximum,
            minimum_words - 1,
            -1,
        ):
            if (
                previous_lower[-size:]
                == current_lower[:size]
            ):
                return size

        return 0

    @classmethod
    def _merge_transcript(
        cls,
        previous: str,
        current: str,
    ) -> str:
        """
        Merge a new authoritative final transcript into the existing
        transcript while removing exact boundary duplication.
        """

        previous = cls._normalize_text(
            previous
        )

        current = cls._normalize_text(
            current
        )

        if not previous:
            return current

        if not current:
            return previous

        previous_tokens = cls._tokens(
            previous
        )

        current_tokens = cls._tokens(
            current
        )

        overlap = cls._find_boundary_overlap(
            previous,
            current,
        )

        if overlap > 0:
            merged_tokens = (
                previous_tokens
                + current_tokens[overlap:]
            )

            return " ".join(
                merged_tokens
            )

        return (
            previous
            + " "
            + current
        )

    # ==========================================================
    # PERSISTENCE
    # ==========================================================

    def _persist_transcript(self):
        """
        Atomically persist the authoritative transcript.

        Write temporary file → flush → fsync → replace.
        """

        path = os.path.abspath(
            self.transcript_path
        )

        directory = os.path.dirname(
            path
        )

        os.makedirs(
            directory,
            exist_ok=True,
        )

        with self._persist_lock:

            temporary_path = None

            try:

                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    dir=directory,
                    prefix=".transcript-",
                    suffix=".tmp",
                    delete=False,
                ) as file:

                    temporary_path = file.name

                    file.write(
                        self.authoritative_transcript
                    )

                    file.flush()

                    os.fsync(
                        file.fileno()
                    )

                os.replace(
                    temporary_path,
                    path,
                )

            except Exception as error:

                if (
                    temporary_path
                    and os.path.exists(
                        temporary_path
                    )
                ):
                    try:
                        os.remove(
                            temporary_path
                        )
                    except Exception:
                        pass

                app_logger.error(
                    "Transcript persistence failed: "
                    f"{error}"
                )

    # ==========================================================
    # FINAL TRANSCRIPTION
    # ==========================================================

    def _run_final_transcription(
        self,
        audio,
        segment_id: int,
        hard_split: bool,
    ):
        """
        Worker-thread Whisper execution for final audio.
        """

        transcript = self.whisper.transcribe_audio(
            audio
        )

        return {
            "kind": "final",
            "segment_id": segment_id,
            "hard_split": hard_split,
            "transcript": transcript,
        }

    # ==========================================================
    # PREVIEW TRANSCRIPTION
    # ==========================================================

    def _run_preview_transcription(
        self,
        audio,
    ):
        """
        Worker-thread Whisper execution for preview audio.
        """

        transcript = self.whisper.transcribe_audio(
            audio
        )

        return {
            "kind": "preview",
            "transcript": transcript,
        }

    # ==========================================================
    # INFERENCE PUMP
    # ==========================================================

    def _pump_inference(self):
        """
        Start the next Whisper job if no job is currently running.

        Priority:

            1. final
            2. newest preview

        Only one Whisper job is executed at a time.
        """

        with self.inference_lock:

            if self.inference_future is not None:
                return

            # --------------------------------------------------
            # Final jobs always have priority.
            # --------------------------------------------------

            if self.pending_final_jobs:

                job = (
                    self.pending_final_jobs.popleft()
                )

                try:

                    future = (
                        self.inference_executor.submit(
                            self._run_final_transcription,
                            job["audio"],
                            job["segment_id"],
                            job["hard_split"],
                        )
                    )

                except RuntimeError as error:

                    # Executor has already been shut down.
                    #
                    # Put the job back so it is not silently lost.
                    self.pending_final_jobs.appendleft(
                        job
                    )

                    app_logger.error(
                        "Unable to submit final Whisper job: "
                        f"{error}"
                    )

                    return

                self.inference_future = future
                self.inference_kind = "final"
                self.inference_metadata = job

                self.metrics[
                    "final_jobs_submitted"
                ] += 1

                future.add_done_callback(
                    self._inference_completed
                )

                return

            # --------------------------------------------------
            # Only newest preview is retained.
            # --------------------------------------------------

            if self.pending_preview_audio is not None:

                audio = (
                    self.pending_preview_audio
                )

                self.pending_preview_audio = None

                try:

                    future = (
                        self.inference_executor.submit(
                            self._run_preview_transcription,
                            audio,
                        )
                    )

                except RuntimeError as error:

                    self.pending_preview_audio = audio

                    app_logger.error(
                        "Unable to submit preview Whisper job: "
                        f"{error}"
                    )

                    return

                self.inference_future = future
                self.inference_kind = "preview"
                self.inference_metadata = None

                self.metrics[
                    "preview_submitted"
                ] += 1

                future.add_done_callback(
                    self._inference_completed
                )

    # ==========================================================
    # INFERENCE COMPLETION
    # ==========================================================

    def _inference_completed(
        self,
        future: Future,
    ):
        """
        Called by the Whisper executor when a transcription finishes.
        """

        with self.inference_lock:

            kind = self.inference_kind
            metadata = self.inference_metadata

            self.inference_future = None
            self.inference_kind = None
            self.inference_metadata = None

        try:

            result = future.result()

            if kind == "preview":

                self.metrics[
                    "preview_completed"
                ] += 1

                transcript = self._normalize_text(
                    result.get(
                        "transcript",
                        "",
                    )
                )

                if (
                    transcript
                    and self.on_preview_transcript
                ):

                    try:

                        self.on_preview_transcript(
                            transcript,
                            self.authoritative_transcript,
                        )

                    except Exception as error:

                        app_logger.error(
                            "Preview callback failed: "
                            f"{error}"
                        )

            elif kind == "final":

                self.metrics[
                    "final_jobs_completed"
                ] += 1

                transcript = self._normalize_text(
                    result.get(
                        "transcript",
                        "",
                    )
                )

                if transcript:

                    self.authoritative_transcript = (
                        self._merge_transcript(
                            self.authoritative_transcript,
                            transcript,
                        )
                    )

                    self.metrics[
                        "transcript_characters"
                    ] = len(
                        self.authoritative_transcript
                    )

                    self._persist_transcript()

                    if self.on_final_transcript:

                        try:

                            self.on_final_transcript(
                                transcript,
                                self.authoritative_transcript,
                                result.get(
                                    "segment_id"
                                ),
                            )

                        except Exception as error:

                            app_logger.error(
                                "Final transcript callback failed: "
                                f"{error}"
                            )

        except Exception as error:

            self.metrics[
                "transcription_failures"
            ] += 1

            if kind == "final":

                self.metrics[
                    "final_jobs_failed"
                ] += 1

            app_logger.error(
                "Whisper inference failed: "
                f"{error}"
            )

            traceback.print_exc()

        finally:

            # --------------------------------------------------
            # The current job is finished.
            #
            # Immediately schedule the next final/preview job.
            # --------------------------------------------------

            self._pump_inference()

    # ==========================================================
    # PREVIEW REQUEST
    # ==========================================================

    def _request_preview(self):
        """
        Request a preview of the most recent speech window.

        Preview jobs are intentionally replaceable.
        Final jobs are never replaced by previews.
        """

        if not self.recording:
            return

        audio = self.builder.tail(
            self.preview_window_samples
        )

        if audio is None or len(audio) == 0:
            return

        self.metrics[
            "preview_requests"
        ] += 1

        with self.inference_lock:

            # --------------------------------------------------
            # Replace old preview with newest preview.
            # --------------------------------------------------

            self.pending_preview_audio = audio

            # --------------------------------------------------
            # If final inference is currently running, leave the
            # preview pending. It will run after final jobs.
            # --------------------------------------------------

            if self.inference_kind == "final":

                self.metrics[
                    "preview_skipped"
                ] += 1

                return

            # --------------------------------------------------
            # Otherwise immediately pump inference.
            #
            # RLock prevents deadlock here.
            # --------------------------------------------------

            self._pump_inference()

    # ==========================================================
    # FINAL JOB
    # ==========================================================

    def _submit_final(
        self,
        audio,
        hard_split: bool,
    ):
        """
        Queue a final Whisper job.

        Final jobs are never silently dropped.

        max_pending_final_jobs is treated as a pressure threshold
        rather than a hard data-loss limit.
        """

        if audio is None or len(audio) == 0:
            return False

        self.segment_id += 1

        job = {
            "audio": audio,
            "segment_id": self.segment_id,
            "hard_split": hard_split,
        }

        with self.inference_lock:

            if (
                len(self.pending_final_jobs)
                >= self.max_pending_final_jobs
            ):

                self.metrics[
                    "final_jobs_overflow"
                ] += 1

                app_logger.warning(
                    "Final Whisper backlog exceeded configured "
                    "threshold. Retaining audio instead of "
                    "dropping the final segment. "
                    f"Pending jobs: "
                    f"{len(self.pending_final_jobs)}"
                )

            self.pending_final_jobs.append(
                job
            )

            # RLock prevents deadlock.
            self._pump_inference()

        return True

    # ==========================================================
    # FINALIZE SEGMENT
    # ==========================================================

    def _finalize_segment(
        self,
        reason: str,
        retain_overlap: bool = False,
    ):
        """
        Finalize the current speech segment.

        For a hard split:

            segment A
                ↓
            final Whisper job
                +
            retain last overlap window
                ↓
            continue recording as segment B

        For a natural endpoint:

            finalize
                ↓
            completely reset speech state
        """

        audio = self.builder.snapshot()

        if audio is None or len(audio) == 0:

            self._reset_segment_state()

            return False

        # ------------------------------------------------------
        # Do not send extremely short segments to Whisper.
        # ------------------------------------------------------

        if (
            self.speech_sample_count
            < self.minimum_speech_samples
        ):

            self.metrics[
                "short_segments_discarded"
            ] += 1

            self._reset_segment_state()

            return False

        hard_split = (
            reason == "hard_split"
        )

        self.metrics[
            "segments_finalized"
        ] += 1

        if reason == "natural_endpoint":

            self.metrics[
                "natural_endpoints"
            ] += 1

        elif hard_split:

            self.metrics[
                "hard_splits"
            ] += 1

        submitted = self._submit_final(
            audio,
            hard_split=hard_split,
        )

        if not submitted:

            app_logger.error(
                "Final segment could not be submitted."
            )

            self._reset_segment_state()

            return False

        # ------------------------------------------------------
        # Hard split:
        #
        # Retain only the tail of the segment.
        #
        # The retained overlap is NOT treated as new speech.
        # New speech must arrive before another finalization.
        # ------------------------------------------------------

        if retain_overlap and self.overlap_samples > 0:

            overlap_samples = min(
                self.overlap_samples,
                len(audio),
            )

            self.builder.replace_with_tail(
                overlap_samples
            )

            self.metrics[
                "hard_split_overlap_samples"
            ] += overlap_samples

            # --------------------------------------------------
            # Important:
            #
            # The overlap itself must not satisfy the minimum
            # speech requirement for a future standalone segment.
            #
            # New speech after the boundary will increase this
            # counter.
            # --------------------------------------------------

            self.speech_sample_count = 0

            self.silence_sample_count = 0
            self.preview_sample_count = 0

            self.recording = True

            return True

        # ------------------------------------------------------
        # Natural endpoint / shutdown.
        # ------------------------------------------------------

        self._reset_segment_state()

        return True

    # ==========================================================
    # RESET
    # ==========================================================

    def _reset_segment_state(self):

        self.builder.clear()

        self.recording = False

        self.silence_sample_count = 0
        self.speech_sample_count = 0
        self.preview_sample_count = 0

        self._clear_pre_roll()

    # ==========================================================
    # PROCESS CHUNK
    # ==========================================================

    def _process_chunk(
        self,
        chunk,
    ):
        """
        Process exactly one microphone chunk.
        """

        if chunk is None:
            return

        chunk_samples = len(chunk)

        if chunk_samples <= 0:
            return

        self.metrics[
            "chunks_processed"
        ] += 1

        is_speech = self.detector.is_speech(
            chunk
        )

        # ------------------------------------------------------
        # Not currently recording.
        #
        # Maintain pre-roll so initial phonemes are less likely
        # to be cut off.
        # ------------------------------------------------------

        if not self.recording:

            self._remember_pre_roll(
                chunk
            )

        # ======================================================
        # SPEECH
        # ======================================================

        if is_speech:

            self.metrics[
                "speech_chunks"
            ] += 1

            if not self.recording:

                self.recording = True

                self.builder.clear()

                # --------------------------------------------------
                # Add pre-roll before the first speech chunk.
                # --------------------------------------------------

                if self.pre_roll:

                    self.builder.extend(
                        self.pre_roll
                    )

                self._clear_pre_roll()

                self.silence_sample_count = 0
                self.speech_sample_count = 0
                self.preview_sample_count = 0

                app_logger.info(
                    "Speech Started"
                )

            self.builder.add_chunk(
                chunk
            )

            self.speech_sample_count += (
                chunk_samples
            )

            self.silence_sample_count = 0

            self.preview_sample_count += (
                chunk_samples
            )

        # ======================================================
        # SILENCE
        # ======================================================

        else:

            self.metrics[
                "silence_chunks"
            ] += 1

            if not self.recording:
                return

            # --------------------------------------------------
            # Keep trailing silence so endpointing has context.
            # --------------------------------------------------

            self.builder.add_chunk(
                chunk
            )

            self.silence_sample_count += (
                chunk_samples
            )

            self.preview_sample_count += (
                chunk_samples
            )

        # ------------------------------------------------------
        # Current segment length.
        # ------------------------------------------------------

        current_samples = (
            self.builder.sample_count()
        )

        # ======================================================
        # LIVE PREVIEW
        # ======================================================

        if (
            self.recording
            and self.preview_sample_count
            >= self.preview_interval_samples
        ):

            self.preview_sample_count = 0

            self._request_preview()

        # ======================================================
        # HARD MAXIMUM
        # ======================================================

        if (
            self.recording
            and current_samples
            >= self.maximum_segment_samples
        ):

            app_logger.info(
                "Maximum speech segment reached. "
                "Creating hard boundary."
            )

            self._finalize_segment(
                reason="hard_split",
                retain_overlap=True,
            )

            return

        # ======================================================
        # NATURAL ENDPOINT
        # ======================================================

        if (
            self.recording
            and self.silence_sample_count
            >= self.silence_samples
        ):

            app_logger.info(
                "Speech Finished"
            )

            self._finalize_segment(
                reason="natural_endpoint",
                retain_overlap=False,
            )

    # ==========================================================
    # RUN
    # ==========================================================

    def run(self):

        app_logger.success(
            "Audio Worker Started"
        )

        try:

            while True:

                # --------------------------------------------------
                # Continue draining the queue after stop is requested.
                #
                # This preserves audio that was already captured by
                # the microphone callback.
                # --------------------------------------------------

                if (
                    self.stop_requested
                    and self.audio_queue.empty()
                ):

                    break

                try:

                    chunk = self.audio_queue.get(
                        timeout=0.05
                    )

                except Exception:

                    continue

                try:

                    self._process_chunk(
                        chunk
                    )

                    if self.stop_requested:

                        self.metrics[
                            "shutdown_queue_drained"
                        ] += 1

                except Exception as error:

                    app_logger.error(
                        "Audio worker chunk error: "
                        f"{error}"
                    )

                    traceback.print_exc()

            # ======================================================
            # FLUSH ACTIVE SEGMENT
            # ======================================================

            if self.recording:

                self._finalize_segment(
                    reason="shutdown",
                    retain_overlap=False,
                )

            # ======================================================
            # WAIT FOR WHISPER
            # ======================================================

            self._wait_for_inference(
                timeout_seconds=20.0
            )

        except Exception as error:

            app_logger.error(
                "Audio worker fatal error: "
                f"{error}"
            )

            traceback.print_exc()

        finally:

            self.running = False

            try:

                self.inference_executor.shutdown(
                    wait=True,
                    cancel_futures=False,
                )

            except Exception as error:

                app_logger.error(
                    "Whisper executor shutdown failed: "
                    f"{error}"
                )

            app_logger.info(
                "Audio Worker Stopped"
            )

    # ==========================================================
    # WAIT FOR INFERENCE
    # ==========================================================

    def _wait_for_inference(
        self,
        timeout_seconds: float,
    ):
        """
        Wait for all currently queued final transcription jobs.

        Preview work is secondary to final transcription.
        """

        deadline = (
            time.monotonic()
            + timeout_seconds
        )

        while time.monotonic() < deadline:

            with self.inference_lock:

                active = (
                    self.inference_future
                    is not None
                )

                pending_final = bool(
                    self.pending_final_jobs
                )

            if not active and not pending_final:

                # --------------------------------------------------
                # A preview may still be pending.
                # It is intentionally not required for authoritative
                # transcript completion.
                # --------------------------------------------------

                return

            self._pump_inference()

            time.sleep(0.05)

        with self.inference_lock:

            active = self.inference_future is not None

            pending = len(
                self.pending_final_jobs
            )

        if active or pending:

            app_logger.warning(
                "Whisper inference did not fully drain "
                "before shutdown timeout. "
                f"active={active}, "
                f"pending_final_jobs={pending}"
            )

    # ==========================================================
    # STOP
    # ==========================================================

    def stop(self):

        if self.stop_requested:
            return

        self.stop_requested = True

        self._stop_event.set()

        app_logger.info(
            "Audio Worker Stop Requested"
        )

    # ==========================================================
    # TRANSCRIPT
    # ==========================================================

    def get_full_transcript(self) -> str:

        return self.authoritative_transcript

    # ==========================================================
    # METRICS
    # ==========================================================

    def get_metrics(self) -> dict:
        """
        Return a thread-safe diagnostic snapshot.
        """

        with self.inference_lock:

            active_kind = (
                self.inference_kind
            )

            pending_final = len(
                self.pending_final_jobs
            )

            preview_pending = (
                self.pending_preview_audio
                is not None
            )

        return {
            **self.metrics,

            "active_inference": active_kind,

            "pending_final_jobs": pending_final,

            "preview_pending": preview_pending,

            "audio_queue": self.audio_queue.stats(),

            "vad": self.detector.get_state(),
        }