"""faster-whisper wrapper with a hallucination guard (ADR-0002)."""
from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np

from copilot.stt.cuda_dlls import register_nvidia_dlls

log = logging.getLogger(__name__)

FILLER_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching!", "thanks for watching.", "thanks for watching",
    "you", "you.", "bye.", "bye!", ".", "...", "so", "so.", "okay.", "hmm.",
}


@dataclass
class SttConfig:
    model: str = "medium.en"
    device: str = "cuda"
    compute_type: str = "int8_float16"
    beam_size: int = 1
    download_root: str = "models/whisper"
    language: str = "en"


@dataclass
class SttResult:
    text: str
    confidence: float  # exp(mean avg_logprob), 0..1
    no_speech_prob: float
    compression_ratio: float
    infer_ms: float
    rejected: Optional[str] = None  # reason, if the guard rejected it


def guard(text: str, duration_s: float, avg_logprob: float, no_speech_prob: float, compression_ratio: float) -> Optional[str]:
    """Return a rejection reason, or None when the transcript looks real."""
    stripped = text.strip()
    if not stripped:
        return "empty"
    if no_speech_prob > 0.6 and avg_logprob < -1.0:
        return "no_speech"
    if compression_ratio > 2.4:
        return "repetitive"
    if stripped.lower() in FILLER_HALLUCINATIONS and duration_s < 3.0:
        return "filler_hallucination"
    return None


class WhisperEngine:
    def __init__(self, cfg: SttConfig, root: Path) -> None:
        self.cfg = cfg
        self._root = root
        self._model = None

    def load(self) -> float:
        """Load the model and warm it up. Returns seconds taken."""
        t0 = time.perf_counter()
        if self.cfg.device == "cuda":
            register_nvidia_dlls()
        from faster_whisper import WhisperModel

        self._model = WhisperModel(
            self.cfg.model,
            device=self.cfg.device,
            compute_type=self.cfg.compute_type,
            download_root=str(self._root / self.cfg.download_root),
        )
        self.transcribe(np.zeros(16_000, dtype=np.float32))  # warm-up (CUDA kernels, allocator)
        return time.perf_counter() - t0

    def transcribe(self, audio: np.ndarray, prompt: Optional[str] = None) -> SttResult:
        if self._model is None:
            raise RuntimeError("WhisperEngine.load() not called")
        t0 = time.perf_counter()
        segments, _info = self._model.transcribe(
            audio,
            language=self.cfg.language,
            beam_size=self.cfg.beam_size,
            condition_on_previous_text=False,
            initial_prompt=prompt or None,
            vad_filter=False,  # we already segmented with VAD
            without_timestamps=True,
        )
        segments = list(segments)
        infer_ms = (time.perf_counter() - t0) * 1000
        text = " ".join(s.text.strip() for s in segments).strip()
        if segments:
            weights = [max(1, len(s.tokens)) for s in segments]
            avg_lp = sum(s.avg_logprob * w for s, w in zip(segments, weights)) / sum(weights)
            no_speech = max(s.no_speech_prob for s in segments)
            comp = max(s.compression_ratio for s in segments)
        else:
            avg_lp, no_speech, comp = -10.0, 1.0, 0.0
        duration = len(audio) / 16_000
        return SttResult(
            text=text,
            confidence=math.exp(min(0.0, avg_lp)),
            no_speech_prob=no_speech,
            compression_ratio=comp,
            infer_ms=infer_ms,
            rejected=guard(text, duration, avg_lp, no_speech, comp),
        )
