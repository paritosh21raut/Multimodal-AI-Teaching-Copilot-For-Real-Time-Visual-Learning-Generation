"""Utterance segmentation from per-frame speech probabilities (pure, deterministic)."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

SAMPLE_RATE = 16_000


@dataclass(frozen=True)
class SegmenterConfig:
    frame_samples: int = 512
    start_threshold: float = 0.5
    end_threshold: float = 0.35
    min_silence_ms: int = 600
    pad_ms: int = 200
    min_speech_ms: int = 300
    max_utterance_s: float = 15.0
    split_search_s: float = 3.0


@dataclass
class Utterance:
    audio: np.ndarray
    start: float  # lecture seconds (sample clock)
    end: float
    forced_split: bool = False

    @property
    def duration(self) -> float:
        return self.end - self.start


class UtteranceSegmenter:
    """Push (frame, prob) pairs; returns finished utterances.

    Keeps `pad_ms` of pre-roll before speech starts and ends an utterance after `min_silence_ms`
    of frames below `end_threshold` (trailing silence beyond `pad_ms` is trimmed).
    """

    def __init__(self, cfg: SegmenterConfig = SegmenterConfig()) -> None:
        self.cfg = cfg
        fs = cfg.frame_samples
        self._frame_s = fs / SAMPLE_RATE
        self._pad_frames = max(1, round(cfg.pad_ms / 1000 / self._frame_s))
        self._silence_frames = max(1, round(cfg.min_silence_ms / 1000 / self._frame_s))
        self._min_frames = max(1, round(cfg.min_speech_ms / 1000 / self._frame_s))
        self._max_frames = round(cfg.max_utterance_s / self._frame_s)
        self._search_frames = round(cfg.split_search_s / self._frame_s)
        self._clock_frames = 0  # frames seen so far
        self._preroll: list[np.ndarray] = []
        self._frames: list[np.ndarray] = []
        self._probs: list[float] = []
        self._start_frame = 0
        self._silence_run = 0
        self._speech_frames = 0
        self.in_speech = False
        self._continuation = False  # current utterance is the remainder of a forced split
        self.dropped_short = 0

    def push(self, frame: np.ndarray, prob: float) -> list[Utterance]:
        out: list[Utterance] = []
        self._clock_frames += 1
        if not self.in_speech:
            if prob >= self.cfg.start_threshold:
                self.in_speech = True
                self._frames = list(self._preroll) + [frame]
                self._probs = [0.0] * len(self._preroll) + [prob]
                self._start_frame = self._clock_frames - len(self._frames)
                self._silence_run = 0
                self._speech_frames = 1
                self._preroll = []
            else:
                self._preroll.append(frame)
                if len(self._preroll) > self._pad_frames:
                    self._preroll.pop(0)
            return out

        self._frames.append(frame)
        self._probs.append(prob)
        if prob < self.cfg.end_threshold:
            self._silence_run += 1
        else:
            self._silence_run = 0
            self._speech_frames += 1

        if self._silence_run >= self._silence_frames:
            keep = len(self._frames) - self._silence_run + self._pad_frames
            u = self._emit(keep, forced=False)
            if u:
                out.append(u)
            self._reset_after_end()
        elif len(self._frames) >= self._max_frames:
            lo = max(self._min_frames, len(self._frames) - self._search_frames)
            window = np.asarray(self._probs[lo:])
            # latest frame with the minimum probability (on flat speech this keeps pieces near max length)
            cut = lo + (len(window) - 1 - int(np.argmin(window[::-1]))) + 1
            u = self._emit(cut, forced=True)
            if u:
                out.append(u)
            # Remainder continues as the start of the next utterance.
            self._start_frame += cut
            self._frames = self._frames[cut:]
            self._probs = self._probs[cut:]
            self._speech_frames = sum(1 for p in self._probs if p >= self.cfg.end_threshold)
            self._continuation = True
        return out

    def flush(self) -> list[Utterance]:
        """End of stream: emit whatever speech is pending."""
        if not self.in_speech:
            return []
        keep = len(self._frames) - max(0, self._silence_run - self._pad_frames)
        u = self._emit(keep, forced=False)
        self._reset_after_end()
        return [u] if u else []

    def _emit(self, n_frames: int, forced: bool) -> Optional[Utterance]:
        n_frames = min(n_frames, len(self._frames))
        if self._speech_frames < self._min_frames and not forced and not self._continuation:
            self.dropped_short += 1
            return None
        audio = np.concatenate(self._frames[:n_frames]) if n_frames else np.zeros(0, np.float32)
        start = self._start_frame * self._frame_s
        return Utterance(audio=audio, start=start, end=start + n_frames * self._frame_s, forced_split=forced)

    def _reset_after_end(self) -> None:
        # The trailing silence frames become the pre-roll for the next utterance.
        tail = self._frames[-self._pad_frames:]
        self.in_speech = False
        self._continuation = False
        self._frames, self._probs = [], []
        self._silence_run = 0
        self._speech_frames = 0
        self._preroll = list(tail)
