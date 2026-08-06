import sounddevice as sd
from app.utils.logger import app_logger


class Microphone:

    def __init__(self, sample_rate=16000, channels=1):
        self.sample_rate = sample_rate
        self.channels = channels

    def open_stream(self, callback):
        """
        Opens the microphone stream.
        """

        app_logger.info("Opening Microphone...")

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            callback=callback,
        )

        app_logger.success("Microphone Ready")

        return stream