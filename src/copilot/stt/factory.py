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


def make_source(config: Config, audio_file: Optional[Path], speed: float) -> AudioSource:
    if audio_file is not None:
        return WavFileSource(audio_file, speed=speed)
    device = config.get("audio", "device", "")
    if isinstance(device, str):
        device = int(device) if device.strip().isdigit() else (device.strip() or None)
    return MicSource(device=device)


def vocabulary_prompt(setup: LectureSetup, terms: Sequence[str] = ()) -> Optional[str]:
    """Short Whisper initial prompt that primes subject vocabulary; never the transcript. terms: rare words of the
    teacher's study material (F-012, notes.reference.rare_terms; ≤ 30 words, well inside Whisper's 224 tokens)."""
    parts = [p for p in (setup.subject, setup.expected_topic) if p]
    out = [f"A classroom lecture on {' - '.join(parts)}."] if parts else []
    if terms:
        out.append(f"Terms: {', '.join(terms)}.")
    return " ".join(out) or None
