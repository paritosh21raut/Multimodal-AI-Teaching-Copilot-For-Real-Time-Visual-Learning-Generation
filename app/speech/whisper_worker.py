from __future__ import annotations

from app.speech.whisper_model import WhisperModel
from app.utils.logger import app_logger


class WhisperWorker:
    """
    Thin serialized interface around the production
    Faster-Whisper small model.
    """

    def __init__(self):

        self.model = WhisperModel(
            model_size="small",
            device="cpu",
            compute_type="int8",
            language="en",
            beam_size=5,
        )

    def transcribe(
        self,
        audio_path,
    ):

        app_logger.info(
            "Starting Whisper Transcription..."
        )

        text = self.model.transcribe(
            audio_path
        )

        app_logger.success(
            "Transcription Completed"
        )

        return text

    def transcribe_audio(
        self,
        audio_data,
    ):

        app_logger.info(
            "Starting Live Whisper Transcription..."
        )

        text = self.model.transcribe_audio(
            audio_data
        )

        app_logger.success(
            "Live Transcription Completed"
        )

        return text