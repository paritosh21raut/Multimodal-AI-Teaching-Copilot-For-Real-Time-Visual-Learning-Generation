from app.audio.audio_stream import AudioStream
from app.audio.audio_worker import AudioWorker


class AudioPipeline:

    def __init__(self):

        self.stream = AudioStream()

        self.worker = AudioWorker(
            self.stream.get_queue()
        )

    def start(self):

        self.worker.start()

        self.stream.start()