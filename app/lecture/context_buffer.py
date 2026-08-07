from collections import deque
from threading import Lock
from typing import List


class ContextBuffer:
    """
    Stores the rolling transcript context for the current lecture.
    """

    def __init__(self, max_chunks: int = 20):
        self._buffer = deque(maxlen=max_chunks)
        self._lock = Lock()

    def add(self, text: str) -> None:
        text = text.strip()

        if not text:
            return

        with self._lock:
            self._buffer.append(text)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def rolling_context(self) -> str:
        with self._lock:
            return " ".join(self._buffer)

    def get_chunks(self) -> List[str]:
        with self._lock:
            return list(self._buffer)

    def size(self) -> int:
        with self._lock:
            return len(self._buffer)

    def is_empty(self) -> bool:
        with self._lock:
            return len(self._buffer) == 0


context_buffer = ContextBuffer()