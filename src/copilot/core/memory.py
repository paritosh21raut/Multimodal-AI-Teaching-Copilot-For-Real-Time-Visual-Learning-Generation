"""Deterministic rolling memory helpers used by the state store (bounded, independent of lecture length)."""
from __future__ import annotations

import re
from typing import Optional, Sequence

from copilot.core.textutil import approx_tokens

_WORD = re.compile(r"[a-z0-9]+")
_FILLER = {"the", "a", "an", "of", "and", "in", "to", "for", "its", "their", "how", "what"}


def title_key(title: str) -> frozenset[str]:
    words = [w for w in _WORD.findall(title.lower()) if w not in _FILLER]
    # crude plural folding so "Requirement" == "Requirements"
    return frozenset(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w for w in words)


def titles_match(a: str, b: str) -> bool:
    ka, kb = title_key(a), title_key(b)
    if not ka or not kb:
        return a.strip().lower() == b.strip().lower()
    if ka == kb:
        return True
    inter = len(ka & kb)
    if inter / len(ka | kb) >= 0.6:
        return True
    # one title extends the other by a single word: "Respiration" ~ "Respiration in Plants"
    return (ka <= kb or kb <= ka) and abs(len(ka) - len(kb)) == 1


def find_title(nodes: Sequence, title: str) -> Optional[int]:
    """Index of the node whose title matches, preferring an exact (case-insensitive) match."""
    low = title.strip().lower()
    for i, n in enumerate(nodes):
        if n.title.strip().lower() == low:
            return i
    for i, n in enumerate(nodes):
        if titles_match(n.title, title):
            return i
    return None


def evict_oldest(nodes: list, cap: int, keep_id: Optional[str]) -> None:
    """Drop least-recently-seen nodes (never `keep_id`) until len(nodes) <= cap."""
    while len(nodes) > cap:
        candidates = [n for n in nodes if n.id != keep_id]
        if not candidates:
            return
        nodes.remove(min(candidates, key=lambda n: n.last_seen))


def rebuild_summary(deltas: Sequence[str], max_tokens: int) -> tuple[str, list[str]]:
    """Newest-first fill of summary sentences within the budget. Returns (summary, kept deltas oldest→newest)."""
    kept: list[str] = []
    used = 0
    for d in reversed(deltas):
        d = d.strip()
        if not d:
            continue
        cost = approx_tokens(d)
        if used + cost > max_tokens:
            if not kept:  # a single over-long delta: keep its head so the summary is never empty
                words = d.split()
                while words and approx_tokens(" ".join(words)) > max_tokens:
                    words = words[:-1]
                kept.append(" ".join(words))
            break
        kept.append(d)
        used += cost
    kept.reverse()
    return " ".join(kept), kept
