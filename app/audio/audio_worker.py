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

    Handles:

        microphone
            ↓
        AudioQueue
            ↓
        VAD
            ↓
        speech segmentation
            ↓
        Whisper preview/final inference
            ↓
        authoritative transcript

    Hard-split segments retain a small audio overlap. Because Whisper
    independently transcribes the overlapping audio, final transcripts
    require boundary reconciliation.
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
        # Lifecycle.
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
        # Transcript state.
        # ----------------------------------------------------------

        self.segment_id = 0
        self.authoritative_transcript = ""

        # ----------------------------------------------------------
        # Whisper execution.
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
        # ----------------------------------------------------------

        self.pending_final_jobs = deque()

        # ----------------------------------------------------------
        # Preview.
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

            "hard_split_sentence_reconciliations": 0,
            "hard_split_sentence_fallbacks": 0,
        }

    # ==========================================================
    # PRE-ROLL
    # ==========================================================

    def _remember_pre_roll(self, chunk):

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
    # TEXT HELPERS
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

    @staticmethod
    def _normalize_token(token: str):

        return token.lower().strip(
            ".,!?;:\"'()[]{}"
        )

    @classmethod
    def _normalized_tokens(cls, text: str):

        result = []

        for token in cls._tokens(text):

            normalized = (
                cls._normalize_token(token)
            )

            if normalized:
                result.append(
                    normalized
                )

        return result

    @staticmethod
    def _word_count(text: str):

        if not text:
            return 0

        return len(
            text.split()
        )

    # ==========================================================
    # SENTENCE HELPERS
    # ==========================================================

    @staticmethod
    def _sentence_end_positions(text: str):

        if not text:
            return []

        return [
            match.end()
            for match in re.finditer(
                r"[.!?](?=\s|$)",
                text,
            )
        ]

    # ==========================================================
    # TOKEN COMPATIBILITY
    # ==========================================================

    @staticmethod
    def _tokens_compatible(
        first: str,
        second: str,
    ) -> bool:

        if not first or not second:
            return False

        if first == second:
            return True

        # Conservative morphological compatibility.
        #
        # process / processes
        # model / models
        # method / methods
        if (
            len(first) >= 4
            and len(second) >= 4
            and (
                first.startswith(second)
                or second.startswith(first)
            )
        ):
            return True

        return False

    @classmethod
    def _compatible_count(
        cls,
        first_tokens,
        second_tokens,
    ) -> int:

        size = min(
            len(first_tokens),
            len(second_tokens),
        )

        count = 0

        for index in range(size):

            if cls._tokens_compatible(
                first_tokens[index],
                second_tokens[index],
            ):
                count += 1

        return count

    # ==========================================================
    # EXACT TOKEN OVERLAP
    # ==========================================================

    @classmethod
    def _find_boundary_overlap(
        cls,
        previous: str,
        current: str,
        maximum_words: int = 20,
        minimum_words: int = 3,
    ):

        previous_tokens = (
            cls._normalized_tokens(
                previous
            )
        )

        current_tokens = (
            cls._normalized_tokens(
                current
            )
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

        for size in range(
            maximum,
            minimum_words - 1,
            -1,
        ):

            if (
                previous_tokens[-size:]
                == current_tokens[:size]
            ):
                return size

        return 0

    # ==========================================================
    # HARD-SPLIT BOUNDARY MATCH
    # ==========================================================

    @classmethod
    def _find_hard_boundary_match(
        cls,
        previous: str,
        current: str,
        maximum_words: int = 8,
        minimum_words: int = 2,
    ):
        """
        Finds a local suffix/prefix match across a hard split.

        Example:

            previous:
                ... a complex process.

            current:
                complex processes requiring...

        Returns:

            (match_size, current_start)

        current_start allows the match to begin slightly inside
        the current segment.
        """

        previous_tokens = (
            cls._normalized_tokens(
                previous
            )
        )

        current_tokens = (
            cls._normalized_tokens(
                current
            )
        )

        if (
            len(previous_tokens)
            < minimum_words
            or len(current_tokens)
            < minimum_words
        ):
            return None

        previous_limit = min(
            maximum_words,
            len(previous_tokens),
        )

        current_limit = min(
            maximum_words,
            len(current_tokens),
        )

        previous_suffix = (
            previous_tokens[
                -previous_limit:
            ]
        )

        best = None

        # Only permit a very small leading region in current.
        for current_start in range(
            min(3, current_limit)
        ):

            remaining = (
                current_limit
                - current_start
            )

            maximum = min(
                maximum_words,
                len(previous_suffix),
                remaining,
            )

            for size in range(
                maximum,
                minimum_words - 1,
                -1,
            ):

                previous_part = (
                    previous_suffix[-size:]
                )

                current_part = (
                    current_tokens[
                        current_start:
                        current_start + size
                    ]
                )

                compatible = (
                    cls._compatible_count(
                        previous_part,
                        current_part,
                    )
                )

                if compatible != size:
                    continue

                candidate = (
                    size,
                    current_start,
                )

                if (
                    best is None
                    or candidate[0] > best[0]
                    or (
                        candidate[0] == best[0]
                        and candidate[1] < best[1]
                    )
                ):
                    best = candidate

        return best

    # ==========================================================
    # HARD-SPLIT SENTENCE REPAIR
    # ==========================================================

    @classmethod
    def _repair_hard_split_sentence(
        cls,
        previous: str,
        current: str,
    ):
        """
        Repairs the special case where Whisper independently
        transcribes the same boundary sentence in both hard-split
        segments.

        Example:

            previous:
                ... can still be a complex process.

            current:
                complex processes requiring a skilled practitioner.
                There is an additional risk...

        The boundary suffix from the previous transcript is replaced
        with the complete first sentence from the current transcript.

        Result:

            ... can still be a complex processes requiring a skilled
            practitioner. There is an additional risk...
        """

        previous = cls._normalize_text(
            previous
        )

        current = cls._normalize_text(
            current
        )

        if not previous or not current:
            return None

        previous_boundaries = (
            cls._sentence_end_positions(
                previous
            )
        )

        current_boundaries = (
            cls._sentence_end_positions(
                current
            )
        )

        # Segment 1 must end at a complete sentence.
        if not previous_boundaries:
            return None

        # Segment 2 must contain a complete first sentence.
        if not current_boundaries:
            return None

        previous_end = (
            previous_boundaries[-1]
        )

        current_first_end = (
            current_boundaries[0]
        )

        if previous_end != len(previous):
            return None

        current_first_sentence = (
            current[
                :current_first_end
            ].strip()
        )

        if not current_first_sentence:
            return None

        match = (
            cls._find_hard_boundary_match(
                previous,
                current_first_sentence,
                maximum_words=8,
                minimum_words=2,
            )
        )

        if match is None:
            return None

        match_size, current_start = match

        if match_size < 2:
            return None

        previous_words = cls._tokens(
            previous
        )

        current_first_words = cls._tokens(
            current_first_sentence
        )

        previous_normalized = (
            cls._normalized_tokens(
                previous
            )
        )

        current_normalized = (
            cls._normalized_tokens(
                current_first_sentence
            )
        )

        # ----------------------------------------------------------
        # Find the exact boundary suffix in previous.
        # ----------------------------------------------------------

        previous_suffix_start = (
            len(previous_normalized)
            - match_size
        )

        if previous_suffix_start <= 0:
            return None

        # ----------------------------------------------------------
        # CASE 1
        #
        # Current starts directly with the repeated boundary.
        #
        # Example:
        #
        # previous:
        #   ... a complex process.
        #
        # current:
        #   complex processes requiring...
        # ----------------------------------------------------------

        if current_start == 0:

            # Keep every previous word before the duplicated suffix.
            previous_prefix_words = (
                previous_words[
                    :previous_suffix_start
                ]
            )

            # Add the complete current sentence.
            merged_words = (
                previous_prefix_words
                + current_first_words
            )

            # Add the remainder of current after its first sentence.
            if (
                current_first_end
                < len(current)
            ):

                remainder = (
                    current[
                        current_first_end:
                    ].strip()
                )

                if remainder:

                    merged_words.extend(
                        remainder.split()
                    )

            return cls._normalize_text(
                " ".join(merged_words)
            )

        # ----------------------------------------------------------
        # CASE 2
        #
        # Current has a tiny leading fragment before the overlap.
        #
        # Example:
        #
        # previous:
        #   ... improved the state of the
        #
        # current:
        #   improve the state of the art...
        # ----------------------------------------------------------

        if current_start <= 2:

            previous_prefix_words = (
                previous_words[
                    :previous_suffix_start
                ]
            )

            current_leading_words = (
                current_first_words[
                    :current_start
                ]
            )

            current_after_match = (
                current_first_words[
                    current_start + match_size:
                ]
            )

            merged_words = (
                previous_prefix_words
                + current_leading_words
                + current_after_match
            )

            if (
                current_first_end
                < len(current)
            ):

                remainder = (
                    current[
                        current_first_end:
                    ].strip()
                )

                if remainder:

                    merged_words.extend(
                        remainder.split()
                    )

            return cls._normalize_text(
                " ".join(merged_words)
            )

        return None

    # ==========================================================
    # HARD-SPLIT RECONCILIATION
    # ==========================================================

    @classmethod
    def _reconcile_hard_split(
        cls,
        previous: str,
        current: str,
    ):
        """
        Reconcile transcripts created by a hard audio split.

        Priority:

            1. Complete sentence boundary repair.
            2. Exact token overlap.
            3. Conservative fuzzy overlap.
            4. Return None for normal fallback handling.
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

        # ----------------------------------------------------------
        # 1. Sentence-level boundary repair.
        # ----------------------------------------------------------

        repaired = (
            cls._repair_hard_split_sentence(
                previous,
                current,
            )
        )

        if repaired:
            return repaired

        # ----------------------------------------------------------
        # 2. Exact overlap.
        # ----------------------------------------------------------

        exact_overlap = (
            cls._find_boundary_overlap(
                previous,
                current,
                maximum_words=20,
                minimum_words=2,
            )
        )

        if exact_overlap >= 2:

            previous_words = cls._tokens(
                previous
            )

            current_words = cls._tokens(
                current
            )

            merged = (
                previous_words
                + current_words[
                    exact_overlap:
                ]
            )

            return cls._normalize_text(
                " ".join(merged)
            )

        # ----------------------------------------------------------
        # 3. Conservative fuzzy overlap.
        # ----------------------------------------------------------

        fuzzy_match = (
            cls._find_hard_boundary_match(
                previous,
                current,
                maximum_words=8,
                minimum_words=2,
            )
        )

        if fuzzy_match is None:
            return None

        match_size, current_start = (
            fuzzy_match
        )

        if match_size < 2:
            return None

        previous_words = cls._tokens(
            previous
        )

        current_words = cls._tokens(
            current
        )

        # Current starts exactly at the repeated boundary.
        if current_start == 0:

            merged = (
                previous_words
                + current_words[
                    match_size:
                ]
            )

            return cls._normalize_text(
                " ".join(merged)
            )

        # Current contains a very small leading fragment.
        if current_start <= 2:

            merged = (
                previous_words
                + current_words[
                    current_start + match_size:
                ]
            )

            return cls._normalize_text(
                " ".join(merged)
            )

        return None

    # ==========================================================
    # TRANSCRIPT MERGE
    # ==========================================================

    @classmethod
    def _merge_transcript(
        cls,
        previous: str,
        current: str,
        hard_split: bool = False,
    ):

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

        if hard_split:

            reconciled = (
                cls._reconcile_hard_split(
                    previous,
                    current,
                )
            )

            if reconciled:
                return reconciled

        previous_words = cls._tokens(
            previous
        )

        current_words = cls._tokens(
            current
        )

        overlap = cls._find_boundary_overlap(
            previous,
            current,
            maximum_words=20,
            minimum_words=3,
        )

        if overlap > 0:

            return " ".join(
                previous_words
                + current_words[
                    overlap:
                ]
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
    # WHISPER FINAL
    # ==========================================================

    def _run_final_transcription(
        self,
        audio,
        segment_id: int,
        hard_split: bool,
    ):

        transcript = (
            self.whisper.transcribe_audio(
                audio
            )
        )

        return {
            "kind": "final",
            "segment_id": segment_id,
            "hard_split": hard_split,
            "transcript": transcript,
        }

    # ==========================================================
    # WHISPER PREVIEW
    # ==========================================================

    def _run_preview_transcription(
        self,
        audio,
    ):

        transcript = (
            self.whisper.transcribe_audio(
                audio
            )
        )

        return {
            "kind": "preview",
            "transcript": transcript,
        }

    # ==========================================================
    # INFERENCE PUMP
    # ==========================================================

    def _pump_inference(self):

        with self.inference_lock:

            if self.inference_future is not None:
                return

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

                    hard_split = bool(
                        result.get(
                            "hard_split",
                            False,
                        )
                    )

                    previous_transcript = (
                        self.authoritative_transcript
                    )

                    if hard_split:

                        reconciled = (
                            self._reconcile_hard_split(
                                previous_transcript,
                                transcript,
                            )
                        )

                        if reconciled:

                            self.authoritative_transcript = (
                                reconciled
                            )

                            self.metrics[
                                "hard_split_sentence_reconciliations"
                            ] += 1

                        else:

                            self.authoritative_transcript = (
                                self._merge_transcript(
                                    previous_transcript,
                                    transcript,
                                    hard_split=True,
                                )
                            )

                            self.metrics[
                                "hard_split_sentence_fallbacks"
                            ] += 1

                    else:

                        self.authoritative_transcript = (
                            self._merge_transcript(
                                previous_transcript,
                                transcript,
                                hard_split=False,
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

            self._pump_inference()

    # ==========================================================
    # PREVIEW REQUEST
    # ==========================================================

    def _request_preview(self):

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

            self.pending_preview_audio = audio

            if self.inference_kind == "final":

                self.metrics[
                    "preview_skipped"
                ] += 1

                return

            self._pump_inference()

    # ==========================================================
    # FINAL JOB
    # ==========================================================

    def _submit_final(
        self,
        audio,
        hard_split: bool,
    ):

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

        audio = self.builder.snapshot()

        if audio is None or len(audio) == 0:

            self._reset_segment_state()

            return False

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

        if (
            retain_overlap
            and self.overlap_samples > 0
        ):

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

            # The retained overlap is intentionally not counted
            # as fresh speech. Otherwise the overlap-only tail could
            # immediately trigger another hard split.
            self.speech_sample_count = 0
            self.silence_sample_count = 0
            self.preview_sample_count = 0

            self.recording = True

            return True

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

        if not self.recording:

            self._remember_pre_roll(
                chunk
            )

        if is_speech:

            self.metrics[
                "speech_chunks"
            ] += 1

            if not self.recording:

                self.recording = True

                self.builder.clear()

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

        else:

            self.metrics[
                "silence_chunks"
            ] += 1

            if not self.recording:
                return

            self.builder.add_chunk(
                chunk
            )

            self.silence_sample_count += (
                chunk_samples
            )

            self.preview_sample_count += (
                chunk_samples
            )

        current_samples = (
            self.builder.sample_count()
        )

        if (
            self.recording
            and self.preview_sample_count
            >= self.preview_interval_samples
        ):

            self.preview_sample_count = 0

            self._request_preview()

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

            if self.recording:

                self._finalize_segment(
                    reason="shutdown",
                    retain_overlap=False,
                )

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

        deadline = (
            time.monotonic()
            + timeout_seconds
        )

        while (
            time.monotonic()
            < deadline
        ):

            with self.inference_lock:

                active = (
                    self.inference_future
                    is not None
                )

                pending_final = bool(
                    self.pending_final_jobs
                )

            if (
                not active
                and not pending_final
            ):
                return

            self._pump_inference()

            time.sleep(
                0.05
            )

        with self.inference_lock:

            active = (
                self.inference_future
                is not None
            )

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

            "audio_queue": (
                self.audio_queue.stats()
            ),

            "vad": (
                self.detector.get_state()
            ),
        }