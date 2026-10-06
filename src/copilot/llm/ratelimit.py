"""Per-provider-entry rate limiting: RPM + TPM token buckets and a cooldown after 429s/outages."""
from __future__ import annotations

import time
from typing import Callable, Optional

Clock = Callable[[], float]


class TokenBucket:
    """Continuous-refill bucket: `capacity` units per 60 s."""

    def __init__(self, per_minute: float, clock: Clock = time.monotonic) -> None:
        self.capacity = float(per_minute)
        self._rate = per_minute / 60.0
        self._tokens = float(per_minute)
        self._clock = clock
        self._t = clock()

    def _refill(self) -> None:
        now = self._clock()
        self._tokens = min(self.capacity, self._tokens + (now - self._t) * self._rate)
        self._t = now

    def available(self) -> float:
        self._refill()
        return self._tokens

    def can_take(self, n: float) -> bool:
        return self.available() >= min(n, self.capacity)

    def wait_for(self, n: float) -> float:
        """Seconds until `n` units (capped at the capacity) are available."""
        missing = min(n, self.capacity) - self.available()
        return max(0.0, missing / self._rate) if self._rate > 0 else (0.0 if missing <= 0 else float("inf"))

    def take(self, n: float) -> None:
        self._refill()
        self._tokens -= n  # may go negative after an underestimate; refill pays it back

    def clamp(self, remaining: float) -> None:
        """Sync with the server's view (e.g. x-ratelimit-remaining-tokens)."""
        self._refill()
        self._tokens = min(self._tokens, remaining)


class RateLimiter:
    def __init__(self, rpm: float, tpm: float, clock: Clock = time.monotonic) -> None:
        self._clock = clock
        self.requests = TokenBucket(rpm, clock)
        self.tokens = TokenBucket(tpm, clock)
        self._cooldown_until = 0.0

    def admit(self, est_tokens: int) -> Optional[str]:
        """None if a call may be made now (and reserve it); otherwise the reason it may not."""
        now = self._clock()
        if now < self._cooldown_until:
            return f"cooldown {self._cooldown_until - now:.0f}s"
        if not self.requests.can_take(1):
            return "rpm"
        if not self.tokens.can_take(est_tokens):
            return "tpm"
        self.requests.take(1)
        self.tokens.take(est_tokens)
        return None

    def ready_in(self, est_tokens: int) -> float:
        """Seconds until admit() would accept this call (inf while cooling down after a 429/outage)."""
        if self._clock() < self._cooldown_until:
            return float("inf")
        return max(self.requests.wait_for(1), self.tokens.wait_for(est_tokens))

    def cooldown(self, seconds: float) -> None:
        self._cooldown_until = max(self._cooldown_until, self._clock() + seconds)

    def correct_tokens(self, estimated: int, actual: int) -> None:
        """Charge the difference once real usage is known."""
        self.tokens.take(actual - estimated)
