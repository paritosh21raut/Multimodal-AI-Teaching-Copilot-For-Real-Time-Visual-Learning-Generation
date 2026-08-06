import soundfile as sf

from app.utils.logger import app_logger


class AudioRecorder:
    """
    Saves recorded speech into a WAV file.
    """

    def save(self, audio_data, filename="outputs/temp.wav"):

        sf.write(
            filename,
            audio_data,
            16000
        )

        app_logger.success(
            f"Audio Saved -> {filename}"
        )

        return filename