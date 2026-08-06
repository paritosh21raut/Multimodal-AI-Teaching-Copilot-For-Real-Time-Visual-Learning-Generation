from collections import deque


class AudioBuffer:
    """
    Stores incoming audio chunks in memory.
    """

    def __init__(self, max_chunks=500):

        self.buffer = deque(maxlen=max_chunks)

    def add_chunk(self, chunk):

        self.buffer.append(chunk)

    def clear(self):

        self.buffer.clear()

    def get_chunks(self):

        return list(self.buffer)

    def size(self):

        return len(self.buffer)

    def is_empty(self):

        return len(self.buffer) == 0