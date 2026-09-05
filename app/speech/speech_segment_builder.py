from __future__ import annotations

from collections import deque
from typing import Iterable

import numpy as np


class SpeechSegmentBuilder:
    """
    Efficient audio segment accumulator.

    Audio chunks remain individually stored while being accumulated.
    Full concatenation happens only when a snapshot/final segment is
    actually required.
    """

    def __init__(self):
        self.buffer = deque()
        self._sample_count = 0

    def add_chunk(self, chunk):

        if chunk is None:
            return

        array = np.asarray(
            chunk,
            dtype=np.float32,
        )

        if array.size == 0:
            return

        if array.ndim == 1:
            array = array.reshape(-1, 1)

        elif array.ndim != 2:
            array = array.reshape(-1, 1)

        if not np.all(np.isfinite(array)):

            array = np.nan_to_num(
                array,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

        self.buffer.append(array)

        self._sample_count += len(array)

    def extend(self, chunks: Iterable):

        for chunk in chunks:
            self.add_chunk(chunk)

    def clear(self):

        self.buffer.clear()
        self._sample_count = 0

    def get_audio(self):

        return self.snapshot()

    def snapshot(self):

        if not self.buffer:
            return None

        audio = np.concatenate(
            tuple(self.buffer),
            axis=0,
        )

        return np.asarray(
            audio,
            dtype=np.float32,
        )

    def tail(self, samples: int):

        if samples <= 0 or self._sample_count == 0:
            return None

        if samples >= self._sample_count:
            return self.snapshot()

        remaining = samples
        pieces = []

        for chunk in reversed(self.buffer):

            if remaining <= 0:
                break

            chunk_samples = len(chunk)

            if chunk_samples <= remaining:

                pieces.append(chunk)
                remaining -= chunk_samples

            else:

                pieces.append(
                    chunk[-remaining:]
                )

                remaining = 0

        pieces.reverse()

        return np.concatenate(
            pieces,
            axis=0,
        ).astype(
            np.float32,
            copy=False,
        )

    def replace_with_tail(self, samples: int):

        tail_audio = self.tail(samples)

        self.clear()

        if tail_audio is not None:
            self.add_chunk(tail_audio)

        return tail_audio

    def sample_count(self) -> int:
        return self._sample_count

    def duration_seconds(
        self,
        sample_rate: int = 16000,
    ) -> float:

        if sample_rate <= 0:
            return 0.0

        return self._sample_count / float(
            sample_rate
        )

    def size(self):
        return len(self.buffer)

    def is_empty(self):
        return not self.buffer