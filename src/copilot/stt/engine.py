"""faster-whisper wrapper with a hallucination guard (ADR-0002)."""
from __future__ import annotations

import logging
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import numpy as np

from copilot.stt.cuda_dlls import register_nvidia_dlls

log = logging.getLogger(__name__)

FILLER_HALLUCINATIONS = {
    "thank you.", "thank you", "thanks for watching!", "thanks for watching.", "thanks for watching",
    "you", "you.", "bye.", "bye!", ".", "...", "so", "so.", "okay.", "hmm.",
}


# Whisper's silence hallucinations (video outros) inside a real line (F-017 E3b, test34: "He pushes with 50N. Thank you
# for your attention.", "... into the air. you"): cut before the line reaches captions or the LLM. Only outro phrases
# and a trailing lone "thank you" / "you"; a teacher's real sentence is never cut.
_OUTRO = re.compile(r"(?:^|(?<=[.!?])\s*|\s)(?:"
                    r"(?:thanks?(?: you)?(?: so much| very much)? for (?:watching|listening|your attention)[.!]?)"
                    r"|(?:(?:and )?(?:i'?ll|i will|we'?ll|we will) see you (?:in the )?next (?:time|video|one)[.!]?)"
                    r"|(?:see you (?:in the )?next (?:time|video)[.!]?)"
                    r"|(?:i hope you (?:enjoyed|liked) (?:this|the) video[.!]?)"
                    r"|(?:(?:please )?(?:like and )?subscribe(?: to (?:my|the|our) channel)?[.!]?)"
                    r"|(?:this is the (?:last|end) (?:part )?of (?:the|this) video[.!]?)"
                    r"|(?:(?<=[.!?] )for watching[.!]?)"
                    r")(?![a-z])(?=\s*(?:[.!?]|$|(?-i:[A-Z])))", re.IGNORECASE)
_TAIL = re.compile(r"(?<=[.!?])\s*(?:(?:thank you(?: very much| so much)?|(?-i:you)|bye)[.!]?\s*)+$", re.IGNORECASE)


def strip_outros(text: str) -> str:
    """The line without Whisper's outro hallucinations ("" if nothing else was said)."""
    t = _OUTRO.sub(" ", text)
    t = _TAIL.sub("", t.strip())
    t = re.sub(r"\s+([.!?,])", lambda m: m.group(1), " ".join(t.split()))
    t = re.sub(r"^(?:[.!?,]\s*)+", "", t)
    return t.strip()


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
    words: list[tuple[str, float, float]] = field(default_factory=list)  # (word, start s, end s) when asked for
    probs: list[float] = field(default_factory=list)  # each word's probability (with `words`)


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
    if not re.search(r"[A-Za-z]{2}|\d", stripped):
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

    def transcribe(self, audio: np.ndarray, prompt: Optional[str] = None, words: bool = False) -> SttResult:
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
            without_timestamps=not words,
            word_timestamps=words,
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
        said = strip_outros(text)
        if said != text:
            log.info("STT: outro hallucination cut: %r -> %r", text, said)
        text = said
        return SttResult(
            text=text,
            confidence=math.exp(min(0.0, avg_lp)),
            no_speech_prob=no_speech,
            compression_ratio=comp,
            infer_ms=infer_ms,
            rejected=guard(text, duration, avg_lp, no_speech, comp),
            words=[(w.word.strip(), float(w.start), float(w.end)) for s in segments for w in (s.words or [])]
            if words else [],
            probs=[float(getattr(w, "probability", 1.0)) for s in segments for w in (s.words or [])] if words else [],
        )
