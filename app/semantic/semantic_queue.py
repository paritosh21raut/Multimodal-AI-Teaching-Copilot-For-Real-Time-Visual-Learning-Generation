from __future__ import annotations

import threading
import time
from typing import List, Optional

from app.semantic.semantic_types import SemanticContextSnapshot


class SemanticQueue:
    """
    Bounded, thread-safe, in-process semantic work queue.

    Enqueue never blocks the live pipeline. Dequeue blocks until at least
    one item is available, then optionally waits up to batch_timeout for
    more items to fill the batch.
    """

    def __init__(
        self,
        *,
        max_size: int = 64,
        batch_size: int = 2,
        batch_timeout: float = 6.0,
    ) -> None:

        self._lock = threading.RLock()
        self._cv = threading.Condition(self._lock)

        self._items: List[SemanticContextSnapshot] = []

        self._max_size = int(max_size)
        self._batch_size = int(batch_size)
        self._batch_timeout = float(batch_timeout)

        self._closed = False
        self._dropped = 0
        self._enqueued = 0

    # ---------------------------------------------------------- #
    # ENQUEUE
    # ---------------------------------------------------------- #

    def put(self, snapshot: SemanticContextSnapshot) -> bool:
        with self._cv:

            if self._closed:
                return False

            accepted = True

            if len(self._items) >= self._max_size:
                self._items.pop(0)
                self._dropped += 1
                accepted = False

            self._items.append(snapshot)
            self._enqueued += 1
            self._cv.notify_all()

            return accepted

    # ---------------------------------------------------------- #
    # DEQUEUE (batched)
    # ---------------------------------------------------------- #

    def get_batch(
        self,
        *,
        timeout: Optional[float] = None,
    ) -> Optional[List[SemanticContextSnapshot]]:
        """
        Blocks until at least one item is available, then waits up to
        batch_timeout for additional items up to batch_size.

        Returns:
        - a list of items when work is available
        - None only when the queue is closed AND empty
        """

        with self._cv:

            # Block indefinitely until an item is present or queue closes.
            while not self._items and not self._closed:
                self._cv.wait()

            if self._closed and not self._items:
                return None

            batch = [self._items.pop(0)]

            deadline = time.monotonic() + self._batch_timeout

            while (
                len(batch) < self._batch_size
                and not self._closed
            ):

                remaining = deadline - time.monotonic()

                if remaining <= 0:
                    break

                if not self._items:
                    self._cv.wait(timeout=remaining)
                    continue

                batch.append(self._items.pop(0))

            return batch

    # ---------------------------------------------------------- #
    # LIFECYCLE
    # ---------------------------------------------------------- #

    def close(self) -> None:
        with self._cv:
            self._closed = True
            self._cv.notify_all()

    def clear(self) -> None:
        with self._cv:
            self._items.clear()

    # ---------------------------------------------------------- #
    # STATS
    # ---------------------------------------------------------- #

    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._items),
                "max_size": self._max_size,
                "enqueued": self._enqueued,
                "dropped": self._dropped,
                "closed": self._closed,
            }