"""Quiz points (F-011): a correct answer earns 1000 when instant, down to 700 at the buzzer; wrong / none: 0.
User: correct + faster earns more, correct + slower slightly less. A test scores 1 per correct answer (model.py)."""
from __future__ import annotations

MAX_POINTS = 1000
SLOW_SHARE = 0.3  # the share of the points a correct answer loses when given at the last moment


def quiz_points(correct: bool, seconds_taken: float, limit_s: float) -> int:
    if not correct:
        return 0
    frac = min(1.0, max(0.0, seconds_taken / limit_s)) if limit_s > 0 else 0.0
    return round(MAX_POINTS * (1 - SLOW_SHARE * frac))
