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


def is_child_facet(facet: str, of: str) -> bool:
    """F-013 S2: a qualified kind of a subtopic is its child: "Intellectual Causes" of "Causes", "Sexual Reproduction"
    of "Reproduction", "Inner Planets" of "Planets". Not "Respiration in Plants" (a facet of respiration) or "Types
    of Bonds" (the same set named in full): the qualifier comes before the head noun. A parent named with its subject
    counts by its head: "Political Causes" of "Causes of French Revolution" (live S2 check, 2026-10-16)."""
    o = f" {of.lower()} "
    head = o.split(" of ")[0].strip() if " of " in o else of.lower()
    a, b = facet.lower().split(), head.split()
    if not b or len(a) <= len(b) or len(a) > len(b) + 2 or " of " in f" {facet.lower()} ":
        return False
    fold = lambda w: w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w  # noqa: E731
    return [fold(w) for w in a[-len(b):]] == [fold(w) for w in b] and not set(a[:-len(b)]) & {"and", "&", "or", "vs"}


def same_title(a: str, b: str) -> bool:
    """titles_match without its one-extra-word leniency for a narrower kind: "Intellectual Causes" is not "Causes",
    "Causes of French Revolution" is not "French Revolution" (F-013 S2: a child is not its parent)."""
    if not titles_match(a, b):
        return False
    ka, kb = title_key(a), title_key(b)
    if ka == kb or not ka or not kb:
        return True
    return not (is_child_facet(a, b) or is_child_facet(b, a) or (ka < kb or kb < ka))


def short_name(name: str, topic: str) -> str:
    """A subtopic name without the topic the crumb already shows: "Causes of French Revolution" -> "Causes",
    "French Revolution Stages" -> "Stages" (unchanged when nothing else would be left)."""
    t = " ".join(topic.split())
    s = re.sub(rf"\s+(?:of|in|for|during)\s+(?:the\s+)?{re.escape(t)}$", "", " ".join(name.split()),
               flags=re.IGNORECASE) if t else name
    if t and s.lower().startswith(t.lower() + " "):
        s = s[len(t) + 1:]
    s = s.strip(" ,:-") or name
    return s[:1].upper() + s[1:]


def same_subject(a: str, b: str, topic: str) -> bool:
    """same_title, also when one names the topic too ("Causes of French Revolution" / "Causes")."""
    if same_title(a, b):
        return True
    kt = title_key(topic)
    ka, kb = title_key(a) - kt, title_key(b) - kt
    return bool(ka) and ka == kb


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
