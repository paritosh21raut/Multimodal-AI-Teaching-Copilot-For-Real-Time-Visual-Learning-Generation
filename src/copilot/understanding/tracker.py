"""ConceptTracker: embedding-based shift score, keyphrases and discourse cue words (deterministic)."""
from __future__ import annotations

import re
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

from copilot.understanding.filter import _STOP

# Strong cues mark a likely concept boundary when they open an utterance.
STRONG_CUES = [
    "now let's", "now let us", "let's move on", "let us move on", "moving on", "the next topic", "next topic",
    "let's now", "let us now", "now we will", "now we'll", "now, the next", "now the next", "another topic",
    "let's talk about", "let us talk about", "let's look at", "let's see", "coming to",
]
WEAK_CUES = [
    "for example", "for instance", "such as", "compared to", "whereas", "while", "unlike", "is defined as",
    "is called", "are called", "means", "first", "then", "next", "finally", "after that", "because",
    "therefore", "so that", "as a result", "step", "equation", "formula", "in summary", "to summarise",
    "to summarize", "in short", "on the other hand", "different from",
]
STRONG_CUE_WINDOW = 7  # words from the utterance start

_WORD = re.compile(r"[a-z][a-z0-9'\-]*")
_KP_EXTRA_STOP = {"which", "who", "whom", "how", "why", "when", "where", "into", "about", "like", "make",
                  "makes", "made", "get", "gets", "use", "uses", "used", "using", "called", "means", "mean",
                  "happen", "happens", "comes", "come", "see", "let", "going", "learn", "things", "thing",
                  "only", "time", "way", "putting", "together", "help", "quite", "actually", "tiny", "write",
                  "four", "two", "three", "step", "presence", "plus", "gives", "take", "takes", "give",
                  "need", "needs", "important", "different", "directly", "indirectly", "eat", "us", "if",
                  "has", "have", "had", "not", "no", "more", "most", "much", "many", "other", "own",
                  "same", "than", "too", "their", "its", "put", "next", "finally", "first", "then", "word", "should", "would", "could", "may", "might", "must", "while",
                  "because", "after", "before", "during", "through", "over", "under", "between"}
_KP_STOP = _STOP | _KP_EXTRA_STOP


def find_cues(text: str) -> tuple[list[str], bool]:
    low = " " + " ".join(_WORD.findall(text.lower().replace("’", "'"))) + " "
    head = " " + " ".join(low.split()[:STRONG_CUE_WINDOW]) + " "
    strong = [c for c in STRONG_CUES if f" {c.replace(',', '')} " in head]
    weak = [c for c in WEAK_CUES if f" {c} " in low]
    found = list(dict.fromkeys(c.replace(",", "") for c in strong + weak))
    found = [c for c in found if not any(c != o and f" {c} " in f" {o} " for o in found)]  # drop sub-cues
    return found, bool(strong)


def candidate_phrases(text: str, max_n: int = 3) -> list[str]:
    """Contiguous runs of non-stop words, as 1..max_n-grams."""
    out: list[str] = []
    run: list[str] = []
    for w in _WORD.findall(text.lower()) + [""]:
        if w and w not in _KP_STOP and len(w) > 2:
            run.append(w)
            continue
        for n in range(1, max_n + 1):
            out.extend(" ".join(run[i:i + n]) for i in range(len(run) - n + 1))
        run = []
    return out


@dataclass
class TrackerSignal:
    shift_score: float
    raw_shift: float
    topic_shift: float
    keyphrases: list[str] = field(default_factory=list)
    cues: list[str] = field(default_factory=list)
    strong_cue: bool = False
    boundary: bool = False


class ConceptTracker:
    def __init__(self, shift_threshold: float = 0.75, concept_alpha: float = 0.35, topic_alpha: float = 0.1,
                 smooth: int = 2, reseed_alpha: float = 0.6, phrase_memory: int = 60) -> None:
        self.shift_threshold = shift_threshold
        self.concept_alpha = concept_alpha
        self.topic_alpha = topic_alpha
        self.reseed_alpha = reseed_alpha
        self._recent = deque(maxlen=smooth)
        self._concept: Optional[np.ndarray] = None
        self._topic: Optional[np.ndarray] = None
        self._phrase_hist: deque[list[str]] = deque(maxlen=phrase_memory)  # bounded memory
        self._phrase_df: Counter[str] = Counter()

    @staticmethod
    def _norm(v: np.ndarray) -> np.ndarray:
        n = float(np.linalg.norm(v))
        return v / n if n > 0 else v

    def update(self, text: str, vec: Optional[np.ndarray]) -> TrackerSignal:
        """Feed one content utterance and its (normalised) embedding; vec=None → cues/keyphrases only."""
        cues, strong = find_cues(text)
        if vec is None:  # embedder unavailable: degrade to cue words (logged by the service)
            return TrackerSignal(0.0, 0.0, 0.0, self._keyphrases(text), cues, strong, strong)
        if self._concept is None or self._topic is None:
            self._concept, self._topic = vec.copy(), vec.copy()
            raw = topic_shift = 0.0
        else:
            raw = 1.0 - float(np.dot(vec, self._concept))
            topic_shift = 1.0 - float(np.dot(vec, self._topic))
        self._recent.append(raw)
        smoothed = float(np.mean(self._recent))
        boundary = strong or raw >= self.shift_threshold
        a = self.reseed_alpha if boundary else self.concept_alpha
        self._concept = self._norm((1 - a) * self._concept + a * vec)
        self._topic = self._norm((1 - self.topic_alpha) * self._topic + self.topic_alpha * vec)
        if boundary:
            self._recent.clear()
            self._recent.append(raw)
        return TrackerSignal(smoothed, raw, topic_shift, self._keyphrases(text), cues, strong, boundary)

    def _keyphrases(self, text: str, k: int = 4) -> list[str]:
        phrases = list(dict.fromkeys(candidate_phrases(text)))
        if len(self._phrase_hist) == self._phrase_hist.maxlen:
            self._phrase_df.subtract(self._phrase_hist[0])
        self._phrase_hist.append(phrases)
        self._phrase_df.update(phrases)
        self._phrase_df += Counter()  # drop zero counts (keeps the counter bounded)
        # Prefer phrases that recur in the lecture, then longer ones.
        ranked = sorted(phrases, key=lambda p: (-self._phrase_df[p], -len(p.split()), phrases.index(p)))
        out: list[str] = []
        for p in ranked:
            if any(p in q or q in p for q in out):
                continue
            out.append(p)
            if len(out) == k:
                break
        return out
