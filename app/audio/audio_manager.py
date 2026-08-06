import sounddevice as sd
from app.utils.logger import app_logger


class AudioManager:

    def __init__(self):

        self.sample_rate = 16000
        self.channels = 1

    def list_microphones(self):

        devices = sd.query_devices()

        app_logger.info("Available Microphones")

        for index, device in enumerate(devices):

            print(f"{index} : {device['name']}")

        return devices