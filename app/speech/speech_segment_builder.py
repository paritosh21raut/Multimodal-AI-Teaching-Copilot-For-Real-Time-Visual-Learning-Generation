from __future__ import annotations

import numpy as np


class SpeechSegmentBuilder:

    def __init__(self):

        self.buffer = []

    # ==========================================================
    # ADD
    # ==========================================================

    def add_chunk(
        self,
        chunk,
    ):

        self.buffer.append(
            chunk
        )

    # ==========================================================
    # CLEAR
    # ==========================================================

    def clear(self):

        self.buffer = []

    # ==========================================================
    # FULL AUDIO
    # ==========================================================

    def get_audio(self):

        if not self.buffer:
            return None

        return np.concatenate(
            self.buffer,
            axis=0,
        )

    # ==========================================================
    # SNAPSHOT
    # ==========================================================

    def snapshot(self):

        if not self.buffer:
            return None

        return np.concatenate(
            list(self.buffer),
            axis=0,
        )

    # ==========================================================
    # SAMPLE COUNT
    # ==========================================================

    def sample_count(self):

        if not self.buffer:
            return 0

        return sum(
            len(chunk)
            for chunk in self.buffer
        )

    # ==========================================================
    # SIZE
    # ==========================================================

    def size(self):

        return len(
            self.buffer
        )

    # ==========================================================
    # EMPTY
    # ==========================================================

    def is_empty(self):

        return not self.buffer