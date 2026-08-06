import sounddevice as sd

from app.audio.microphone import Microphone
from app.audio.audio_queue import AudioQueue
from app.utils.logger import app_logger


class AudioStream:

    def __init__(self):

        self.microphone = Microphone()

        self.audio_queue = AudioQueue()

    def callback(self, indata, frames, time, status):

        if status:
            app_logger.warning(status)

        # Store audio chunk inside queue
        self.audio_queue.put(indata.copy())

    def get_queue(self):

        return self.audio_queue

    def start(self):

        app_logger.info("Starting Audio Stream...")

        with self.microphone.open_stream(self.callback):

            app_logger.success("Audio Stream Running")

            print("\nListening... Press Ctrl + C to stop.\n")

            try:

                while True:

                    sd.sleep(100)

            except KeyboardInterrupt:

                app_logger.warning("Audio Stream Stopped")