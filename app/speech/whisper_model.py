from __future__ import annotations

import numpy as np
from faster_whisper import WhisperModel as FWModel
from app.utils.logger import app_logger


class WhisperModel:

    def __init__(self):

        app_logger.info(
            "Loading Whisper Model..."
        )

        self.model = FWModel(
            model_size_or_path="base",
            device="cpu",
            compute_type="int8"
        )

        app_logger.success(
            "Whisper Ready"
        )

    def transcribe(
        self,
        audio_path
    ):

        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=5,
            vad_filter=True
        )

        transcript_parts = []

        for segment in segments:

            text = segment.text.strip()

            if text:
                transcript_parts.append(
                    text
                )

        transcript = " ".join(
            transcript_parts
        ).strip()

        app_logger.info(
            f"Detected Language : {info.language}"
        )

        app_logger.info(
            f"Language Probability : "
            f"{info.language_probability:.2f}"
        )

        return transcript

    def transcribe_audio(
        self,
        audio_data
    ):

        if audio_data is None:
            return ""

        audio = np.asarray(
            audio_data,
            dtype=np.float32
        )

        # sounddevice microphone data is normally
        # (samples, channels). Whisper VAD expects
        # a mono 1D array.
        if audio.ndim == 2:

            if audio.shape[1] == 1:

                audio = audio[:, 0]

            else:

                audio = np.mean(
                    audio,
                    axis=1
                )

        elif audio.ndim != 1:

            audio = audio.reshape(-1)

        if audio.size == 0:
            return ""

        segments, info = self.model.transcribe(
            audio,
            language="en",
            beam_size=5,
            vad_filter=True
        )

        transcript_parts = []

        for segment in segments:

            text = segment.text.strip()

            if text:
                transcript_parts.append(
                    text
                )

        transcript = " ".join(
            transcript_parts
        ).strip()

        app_logger.info(
            f"Detected Language : {info.language}"
        )

        app_logger.info(
            f"Language Probability : "
            f"{info.language_probability:.2f}"
        )

        return transcript