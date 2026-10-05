"""Small text helpers shared across packages."""
from __future__ import annotations

import math
import re

_SENT_END = re.compile(r"[.!?][\"')\]]*$")


def approx_tokens(text: str) -> int:
    """Conservative token estimate for budget enforcement (no model tokenizer needed).

    max(chars / 4, words * 1.35) over-estimates typical BPE counts for English, so a prompt
    within the estimated budget is within the real one.
    """
    if not text:
        return 0
    return math.ceil(max(len(text) / 4.0, len(text.split()) * 1.35))


def ends_sentence(text: str) -> bool:
    return bool(_SENT_END.search(text.strip()))


def word_count(text: str) -> int:
    return len(text.split())
