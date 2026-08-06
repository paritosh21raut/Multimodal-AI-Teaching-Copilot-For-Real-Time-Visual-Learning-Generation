from collections import deque

from app.utils.logger import app_logger


class SpeechSegmenter:
    """
    Collects audio chunks and groups them into
    complete speech segments.
    """

    def __init__(self, max_chunks=50):

        self.segment = deque(maxlen=max_chunks)

    def add_chunk(self, chunk):

        self.segment.append(chunk)

    def get_segment(self):

        return list(self.segment)

    def clear(self):

        self.segment.clear()

    def size(self):

        return len(self.segment)

    def is_empty(self):

        return len(self.segment) == 0

    def finalize_segment(self):

        app_logger.info(
            f"Speech Segment Created ({len(self.segment)} chunks)"
        )

        segment = list(self.segment)

        self.clear()

        return segment