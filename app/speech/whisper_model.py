from __future__ import annotations

import threading

import numpy as np
from faster_whisper import WhisperModel as FWModel

from app.utils.logger import app_logger


class WhisperModel:
    """
    Single serialized Faster-Whisper model.

    Production configuration:

        model = small
        device = cpu
        compute_type = int8
        language = en
        beam_size = 5
        vad_filter = True

    Additional decoding safeguards are used to reduce:
        - repetitive transcription
        - hallucinated text
        - unstable long-form decoding

    Whisper execution is serialized because the same model instance
    is shared by preview and final transcription jobs.
    """

    def __init__(
        self,
        model_size: str = "small",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str = "en",
        beam_size: int = 5,
    ):

        app_logger.info(
            "Loading Whisper Model..."
        )

        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size

        app_logger.info(
            f"Whisper Model : {self.model_size}"
        )

        app_logger.info(
            f"Whisper Device : {self.device}"
        )

        app_logger.info(
            f"Whisper Compute : {self.compute_type}"
        )

        self.model = FWModel(
            model_size_or_path=model_size,
            device=device,
            compute_type=compute_type,
        )

        self._lock = threading.Lock()

        app_logger.success(
            "Whisper Ready"
        )

    @staticmethod
    def normalize_audio(
        audio_data,
    ):

        if audio_data is None:
            return None

        audio = np.asarray(
            audio_data,
            dtype=np.float32,
        )

        if audio.size == 0:
            return None

        if audio.ndim == 2:

            if audio.shape[1] == 1:

                audio = audio[:, 0]

            else:

                audio = np.mean(
                    audio,
                    axis=1,
                    dtype=np.float32,
                )

        elif audio.ndim != 1:

            audio = audio.reshape(-1)

        if not np.all(
            np.isfinite(audio)
        ):

            audio = np.nan_to_num(
                audio,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

        if audio.size == 0:
            return None

        audio = np.clip(
            audio,
            -1.0,
            1.0,
        )

        return np.ascontiguousarray(
            audio,
            dtype=np.float32,
        )

    @staticmethod
    def _clean_transcript(
        text: str,
    ):

        if not text:
            return ""

        text = " ".join(
            text.split()
        ).strip()

        if not text:
            return ""

        words = text.split()

        if len(words) < 8:
            return text

        # Detect immediate repeated phrase patterns.
        #
        # Example:
        # "the dominant sequence ... convolutional
        #  the dominant sequence ... convolutional"
        #
        # Only remove a repetition when the same phrase appears
        # immediately twice. This avoids aggressive rewriting of
        # legitimate repeated speech.
        max_pattern_words = min(
            30,
            len(words) // 2,
        )

        for pattern_size in range(
            max_pattern_words,
            2,
            -1,
        ):

            first = words[
                :pattern_size
            ]

            second = words[
                pattern_size:pattern_size * 2
            ]

            if first == second:

                words = words[
                    :pattern_size
                ] + words[
                    pattern_size * 2:
                ]

                text = " ".join(
                    words
                ).strip()

                break

        return text

    def _transcribe_array(
        self,
        audio,
    ):

        segments, info = self.model.transcribe(
            audio,
            language=self.language,
            beam_size=self.beam_size,

            # VAD prevents obvious silence regions from being
            # interpreted as speech.
            vad_filter=True,

            # Prevent Whisper from repeatedly carrying old
            # decoding context into a new transcription call.
            condition_on_previous_text=False,

            # Slightly reduce temperature-driven hallucination
            # recovery behaviour.
            temperature=0.0,

            # Suppress blank/no-speech hallucination.
            no_speech_threshold=0.6,

            # Require reasonable confidence before accepting
            # highly compressed / abnormal decoding.
            log_prob_threshold=-1.0,

            # Prevent pathological repeated n-grams.
            repetition_penalty=1.05,
        )

        transcript_parts = []

        # Faster-Whisper performs inference while
        # the generator is consumed.
        for segment in segments:

            text = segment.text.strip()

            if text:

                transcript_parts.append(
                    text
                )

        transcript = " ".join(
            transcript_parts
        ).strip()

        transcript = self._clean_transcript(
            transcript
        )

        if info is not None:

            language = getattr(
                info,
                "language",
                None,
            )

            probability = getattr(
                info,
                "language_probability",
                None,
            )

            if language is not None:

                if probability is not None:

                    app_logger.info(
                        "Detected Language : "
                        f"{language}"
                    )

                    app_logger.info(
                        "Language Probability : "
                        f"{probability:.2f}"
                    )

        return transcript

    def transcribe(
        self,
        audio_path,
    ):

        app_logger.info(
            "Starting Whisper Transcription..."
        )

        with self._lock:

            transcript = self._transcribe_array(
                audio_path
            )

        app_logger.success(
            "Whisper Transcription Completed"
        )

        return transcript

    def transcribe_audio(
        self,
        audio_data,
    ):

        audio = self.normalize_audio(
            audio_data
        )

        if audio is None:
            return ""

        with self._lock:

            return self._transcribe_array(
                audio
            )