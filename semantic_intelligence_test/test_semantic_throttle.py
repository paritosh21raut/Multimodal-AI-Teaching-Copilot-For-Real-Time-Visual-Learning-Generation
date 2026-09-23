from __future__ import annotations

import time

from app.semantic.semantic_throttle import SemanticThrottle


class _FakeClock:
    def __init__(self, start: float = 0.0) -> None:
        self.now = start
    def __call__(self) -> float:
        return self.now
    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_allows_up_to_max_calls_in_window():

    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=2,
        min_interval_seconds=0.0,
        clock=clock,
    )

    assert throttle.acquire() is True
    clock.advance(1.0)
    assert throttle.acquire() is True
    clock.advance(1.0)
    assert throttle.acquire() is False


def test_window_slides():

    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=1,
        min_interval_seconds=0.0,
        clock=clock,
    )

    assert throttle.acquire() is True
    assert throttle.acquire() is False

    clock.advance(61.0)
    assert throttle.acquire() is True


def test_min_interval_enforced():

    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=100,
        min_interval_seconds=20.0,
        clock=clock,
    )

    assert throttle.acquire() is True
    clock.advance(5.0)
    assert throttle.acquire() is False

    clock.advance(16.0)  # total 21
    assert throttle.acquire() is True


def test_seconds_until_next_slot_interval_binding():

    # max_calls=2 means the window is not the binding constraint after
    # only one call. Min interval should drive the reported wait.
    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=2,
        min_interval_seconds=10.0,
        clock=clock,
    )

    assert throttle.seconds_until_next_slot() == 0.0

    throttle.acquire()
    wait = throttle.seconds_until_next_slot()
    assert 9.5 <= wait <= 10.0

    clock.advance(5.0)
    wait = throttle.seconds_until_next_slot()
    assert 4.5 <= wait <= 5.0


def test_seconds_until_next_slot_window_binding():

    # Fill the window then verify the window constraint drives the wait.
    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=2,
        min_interval_seconds=5.0,
        clock=clock,
    )

    assert throttle.acquire() is True
    clock.advance(6.0)
    assert throttle.acquire() is True

    # Two calls within 60s. Oldest ages out at t=60. Now=6. Wait ~54.
    wait = throttle.seconds_until_next_slot()
    assert 53.5 <= wait <= 54.5


def test_zero_calls_config_denies_all():

    throttle = SemanticThrottle(
        max_calls_per_minute=0,
        min_interval_seconds=0.0,
    )

    assert throttle.acquire() is False
    assert throttle.acquire() is False


def test_stats_reflect_activity():

    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=2,
        min_interval_seconds=0.0,
        clock=clock,
    )

    throttle.acquire()
    throttle.acquire()
    throttle.acquire()  # denied

    s = throttle.stats()
    assert s["allowed_total"] == 2
    assert s["denied_total"] == 1
    assert s["calls_in_window"] == 2


def test_reset_clears_state():

    clock = _FakeClock(0.0)
    throttle = SemanticThrottle(
        max_calls_per_minute=1,
        min_interval_seconds=0.0,
        clock=clock,
    )

    throttle.acquire()
    assert throttle.acquire() is False

    throttle.reset()

    assert throttle.acquire() is True