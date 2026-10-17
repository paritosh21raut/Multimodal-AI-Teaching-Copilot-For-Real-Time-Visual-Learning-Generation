"""Build the speech pipeline from config."""
from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence

from copilot.audio.segmenter import SegmenterConfig
from copilot.audio.sources import AudioSource, MicSource, WavFileSource
from copilot.core.config import PROJECT_ROOT, Config
from copilot.core.state import LectureSetup
from copilot.stt.engine import SttConfig, WhisperEngine


def stt_config(config: Config) -> SttConfig:
    allowed = SttConfig.__dataclass_fields__.keys()
    return SttConfig(**{k: v for k, v in config.section("stt").items() if k in allowed})


def segmenter_config(config: Config) -> SegmenterConfig:
    allowed = SegmenterConfig.__dataclass_fields__.keys()
    return SegmenterConfig(**{k: v for k, v in config.section("audio").items() if k in allowed})


def make_engine(config: Config) -> WhisperEngine:
    return WhisperEngine(stt_config(config), PROJECT_ROOT)


def make_partial_engine(config: Config) -> Optional[WhisperEngine]:
    """F-013 S1b: the fast model for live partial transcripts ([stt] partial_model; "" = no partials)."""
    name = str(config.get("stt", "partial_model", "") or "").strip()
    if not name:
        return None
    cfg = stt_config(config)
    cfg.model = name
    return WhisperEngine(cfg, PROJECT_ROOT)


def make_source(config: Config, audio_file: Optional[Path], speed: float) -> AudioSource:
    if audio_file is not None:
        return WavFileSource(audio_file, speed=speed)
    device = config.get("audio", "device", "")
    if isinstance(device, str):
        device = int(device) if device.strip().isdigit() else (device.strip() or None)
    return MicSource(device=device)


PROMPT_TERM_WORDS = 60  # terms in the prompt, in words (≈ 100 tokens; Whisper keeps the last 223 prompt tokens)


def vocabulary_prompt(setup: LectureSetup, terms: Sequence[str] = ()) -> Optional[str]:
    """Short Whisper initial prompt that primes subject vocabulary; never the transcript. terms: rare words of the
    teacher's study material (F-012, notes.reference.rare_terms) and, as the lecture grows, the terms it has shown
    (F-013 S3, understanding.glossary: newest last); the newest are kept when they exceed PROMPT_TERM_WORDS."""
    parts = [p for p in (setup.subject, setup.expected_topic) if p]
    out = [f"A classroom lecture on {' - '.join(parts)}."] if parts else []
    kept: list[str] = []
    for t in reversed(list(dict.fromkeys(terms))):
        if sum(len(x.split()) for x in kept) + len(t.split()) > PROMPT_TERM_WORDS:
            break
        kept.insert(0, t)
    if kept:
        out.append(f"Terms: {', '.join(kept)}.")
    return " ".join(out) or None
