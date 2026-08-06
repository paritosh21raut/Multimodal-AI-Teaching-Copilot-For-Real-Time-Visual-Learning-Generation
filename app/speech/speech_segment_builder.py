import numpy as np


class SpeechSegmentBuilder:

    def __init__(self):

        self.buffer = []

    def add_chunk(self, chunk):

        self.buffer.append(chunk)

    def clear(self):

        self.buffer = []

    def get_audio(self):

        if len(self.buffer) == 0:
            return None

        return np.concatenate(
            self.buffer,
            axis=0
        )