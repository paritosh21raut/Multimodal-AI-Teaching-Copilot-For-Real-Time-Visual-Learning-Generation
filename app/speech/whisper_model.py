from faster_whisper import WhisperModel as FWModel
from app.utils.logger import app_logger


class WhisperModel:

    def __init__(self):
        app_logger.info("Loading Whisper Model...")

        self.model = FWModel(
            model_size_or_path="base",
            device="cpu",
            compute_type="int8"
        )

        app_logger.success("Whisper Ready")

    def transcribe(self, audio_path):
        """
        Transcribe an audio file using Faster-Whisper.
        """

        segments, info = self.model.transcribe(
            audio_path,
            language="en",      # Force English
            beam_size=5,
            vad_filter=True
        )

        transcript = ""

        for segment in segments:
            transcript += segment.text.strip() + " "

        transcript = transcript.strip()

        app_logger.info(f"Detected Language : {info.language}")
        app_logger.info(f"Language Probability : {info.language_probability:.2f}")

        return transcript