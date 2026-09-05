from __future__ import annotations

import threading
from queue import Empty, Full, Queue
from typing import Optional


class AudioQueue:
    """
    Bounded thread-safe queue for microphone audio.

    The microphone callback must never block. When the queue is full,
    the oldest chunk is discarded so the processing side remains close
    to real time instead of building an unbounded latency backlog.
    """

    def __init__(self, max_chunks: int = 500):
        if max_chunks <= 0:
            raise ValueError("max_chunks must be greater than zero")

        self._queue = Queue(maxsize=max_chunks)
        self._max_chunks = max_chunks

        self._lock = threading.Lock()

        self._total_put = 0
        self._total_get = 0
        self._dropped_chunks = 0

    def put(self, chunk) -> bool:
        """
        Non-blocking insertion.

        Returns True when the chunk was queued.
        Returns False only when the chunk itself could not be queued.
        """

        if chunk is None:
            return False

        try:
            self._queue.put_nowait(chunk)

            with self._lock:
                self._total_put += 1

            return True

        except Full:
            # Drop the oldest chunk rather than blocking the audio
            # callback or allowing unbounded latency to accumulate.
            try:
                self._queue.get_nowait()

                with self._lock:
                    self._dropped_chunks += 1

            except Empty:
                with self._lock:
                    self._dropped_chunks += 1

                return False

            try:
                self._queue.put_nowait(chunk)

                with self._lock:
                    self._total_put += 1

                return True

            except Full:
                with self._lock:
                    self._dropped_chunks += 1

                return False

    def get(self, timeout: Optional[float] = None):
        """
        Retrieves one audio chunk.

        timeout=None preserves the original blocking behavior.
        """

        if timeout is None:
            chunk = self._queue.get()

        else:
            chunk = self._queue.get(timeout=timeout)

        with self._lock:
            self._total_get += 1

        return chunk

    def get_nowait(self):
        chunk = self._queue.get_nowait()

        with self._lock:
            self._total_get += 1

        return chunk

    def empty(self) -> bool:
        return self._queue.empty()

    def size(self) -> int:
        return self._queue.qsize()

    def capacity(self) -> int:
        return self._max_chunks

    def dropped_chunks(self) -> int:
        with self._lock:
            return self._dropped_chunks

    def total_put(self) -> int:
        with self._lock:
            return self._total_put

    def total_get(self) -> int:
        with self._lock:
            return self._total_get

    def clear(self) -> None:
        while True:
            try:
                self._queue.get_nowait()

            except Empty:
                break

    def stats(self) -> dict:
        with self._lock:
            return {
                "queue_depth": self._queue.qsize(),
                "queue_capacity": self._max_chunks,
                "total_put": self._total_put,
                "total_get": self._total_get,
                "dropped_chunks": self._dropped_chunks,
            }