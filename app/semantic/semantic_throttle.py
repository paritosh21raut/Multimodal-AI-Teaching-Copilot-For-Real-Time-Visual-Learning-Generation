from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Optional


class SemanticThrottle:
    """
    Bounded, thread-safe throttle for semantic LLM calls.

    Two constraints apply simultaneously:
    - at most `max_calls_per_minute` calls in the trailing 60 seconds
    - at least `min_interval_seconds` between consecutive calls

    A call is allowed only when both constraints are satisfied.

    This throttle is used ONLY by the semantic sidecar. It does not affect
    LSI, ContentGenerator, or the live pipeline.
    """

    WINDOW_SECONDS = 60.0

    def __init__(
        self,
        *,
        max_calls_per_minute: int = 2,
        min_interval_seconds: float = 20.0,
        clock=time.monotonic,
    ) -> None:

        self._lock = threading.RLock()

        self._max_calls = int(max_calls_per_minute)
        self._min_interval = float(min_interval_seconds)

        self._recent: Deque[float] = deque()
        self._last_call: Optional[float] = None

        self._clock = clock

        # Observability counters
        self._allowed_total = 0
        self._denied_total = 0

    # ---------------------------------------------------------- #
    # ACQUIRE
    # ---------------------------------------------------------- #

    def acquire(self) -> bool:
        """
        Attempt to reserve a semantic LLM call slot.

        Returns True and records the reservation if allowed.
        Returns False without recording if denied.
        """

        with self._lock:

            now = self._clock()

            self._prune(now)

            if self._max_calls <= 0:
                self._denied_total += 1
                return False

            if len(self._recent) >= self._max_calls:
                self._denied_total += 1
                return False

            if (
                self._last_call is not None
                and (now - self._last_call) < self._min_interval
            ):
                self._denied_total += 1
                return False

            self._recent.append(now)
            self._last_call = now
            self._allowed_total += 1

            return True

    # ---------------------------------------------------------- #
    # INTROSPECTION
    # ---------------------------------------------------------- #

    def seconds_until_next_slot(self) -> float:
        """
        Return how many seconds the caller should wait before the next
        acquire() is likely to succeed. 0.0 if a slot is available now.
        """

        with self._lock:

            now = self._clock()

            self._prune(now)

            if self._max_calls <= 0:
                return float("inf")

            if len(self._recent) >= self._max_calls:
                # Wait until the oldest call ages out of the window.
                oldest = self._recent[0]
                return max(0.0, self.WINDOW_SECONDS - (now - oldest))

            if self._last_call is not None:
                since = now - self._last_call
                if since < self._min_interval:
                    return max(0.0, self._min_interval - since)

            return 0.0

    def stats(self) -> dict:
        with self._lock:
            return {
                "max_calls_per_minute": self._max_calls,
                "min_interval_seconds": self._min_interval,
                "calls_in_window": len(self._recent),
                "allowed_total": self._allowed_total,
                "denied_total": self._denied_total,
                "seconds_until_next_slot": self.seconds_until_next_slot(),
            }

    def reset(self) -> None:
        with self._lock:
            self._recent.clear()
            self._last_call = None
            self._allowed_total = 0
            self._denied_total = 0

    # ---------------------------------------------------------- #
    # INTERNAL
    # ---------------------------------------------------------- #

    def _prune(self, now: float) -> None:
        cutoff = now - self.WINDOW_SECONDS
        while self._recent and self._recent[0] < cutoff:
            self._recent.popleft()