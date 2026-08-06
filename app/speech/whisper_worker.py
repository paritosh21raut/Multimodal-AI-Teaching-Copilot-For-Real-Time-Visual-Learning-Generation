from app.speech.whisper_model import WhisperModel
from app.utils.logger import app_logger


class WhisperWorker:

    def __init__(self):
        self.model = WhisperModel()

    def transcribe(self, audio_path):

        app_logger.info("Starting Whisper Transcription...")

        text = self.model.transcribe(audio_path)

        app_logger.success("Transcription Completed")

        return text