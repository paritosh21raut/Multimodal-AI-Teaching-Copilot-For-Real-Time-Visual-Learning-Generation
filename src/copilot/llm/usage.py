"""Daily LLM token usage per (API key, model) over a rolling 24 h, persisted across runs (`data/llm_usage.json`).

Groq's free tier allows 200k tokens/day per model and key, but reports the daily count only in a 429 body. This
ledger counts what the app used, adopts the server's count when a 429 states it, and remembers a spent quota until
the server frees it. It is shown in the terminal at startup and lets the router skip a spent key without a call.
Keys are stored by a short hash of the API key, never the key itself.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

log = logging.getLogger(__name__)

WINDOW_S = 24 * 3600.0
BUCKET_S = 60.0  # stored per minute: bounded (<= 1440 buckets per key) whatever the call rate


def key_id(api_key: Optional[str]) -> str:
    """Stable, non-secret identity of an API key (a key swapped in .env starts a fresh count)."""
    return hashlib.sha256((api_key or "").encode()).hexdigest()[:8] if api_key else "nokey"


@dataclass
class _Usage:
    buckets: dict[int, int] = field(default_factory=dict)  # minute -> tokens (our own calls)
    floor: int = 0               # server's daily count (429 body) ...
    floor_until: float = 0.0     # ... valid until the quota frees up (wall time)
    blocked_until: float = 0.0   # a 429 said the daily quota is spent


class UsageLedger:
    def __init__(self, path: Optional[Path] = None, clock: Callable[[], float] = time.time) -> None:
        self.path = path
        self._clock = clock
        self._data: dict[str, _Usage] = {}
        self._save_failed = False
        if path is not None:
            self._data = self._load(path)

    def _load(self, path: Path) -> dict[str, _Usage]:
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, ValueError) as e:  # a corrupt ledger only costs the history, never the lecture
            log.warning("LLM usage file %s unreadable (%s); starting empty", path, e)
            return {}
        out: dict[str, _Usage] = {}
        entries = raw.get("usage") if isinstance(raw, dict) else None
        for key, v in (entries if isinstance(entries, dict) else {}).items():
            try:
                out[key] = _Usage({int(m): int(t) for m, t in (v.get("buckets") or {}).items()},
                                  int(v.get("floor") or 0), float(v.get("floor_until") or 0.0),
                                  float(v.get("blocked_until") or 0.0))
            except (TypeError, ValueError, AttributeError):
                log.warning("LLM usage file: skipped malformed entry %r", key)
        return out

    def save(self) -> None:
        if self.path is None:
            return
        oldest = int((self._clock() - WINDOW_S) // BUCKET_S)
        data = {"usage": {key: {"buckets": {str(m): t for m, t in u.buckets.items() if m > oldest},
                                "floor": u.floor, "floor_until": u.floor_until, "blocked_until": u.blocked_until}
                          for key, u in self._data.items()}}
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp.write_text(json.dumps(data), encoding="utf-8")
            os.replace(tmp, self.path)
            self._save_failed = False
        except OSError:
            if not self._save_failed:  # logged once per failure streak; the lecture goes on
                self._save_failed = True
                log.exception("could not save LLM usage to %s", self.path)

    def add(self, key: str, tokens: int) -> None:
        u = self._data.setdefault(key, _Usage())
        m = int(self._clock() // BUCKET_S)
        u.buckets[m] = u.buckets.get(m, 0) + tokens

    def used(self, key: str) -> int:
        """Tokens used in the last 24 h: our own count, or the server's while it is valid, if higher."""
        u = self._data.get(key)
        if u is None:
            return 0
        now = self._clock()
        oldest = (now - WINDOW_S) // BUCKET_S
        own = sum(t for m, t in u.buckets.items() if m > oldest)
        return max(own, u.floor) if u.floor_until > now else own

    def spent(self, key: str, *, used: Optional[int], until: float) -> None:
        """A 429 said the daily quota is spent: blocked (and the server's count adopted) until it frees up."""
        u = self._data.setdefault(key, _Usage())
        u.blocked_until = max(u.blocked_until, until)
        if used:
            u.floor, u.floor_until = used, until

    def blocked_for(self, key: str) -> float:
        u = self._data.get(key)
        return max(0.0, u.blocked_until - self._clock()) if u else 0.0
