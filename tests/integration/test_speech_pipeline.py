"""Real audio path: WAV → ArraySource → Silero VAD → segmenter → faster-whisper → bus (F-002).

Needs the GPU (or stt.device=cpu) and a downloaded model, so it is marked slow:
    .venv/Scripts/python -m pytest -m slow tests/integration/test_speech_pipeline.py
"""
import re
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
import pytest

from copilot.audio.sources import ArraySource, read_wav_mono16k
from copilot.core.bus import EventBus
from copilot.core.config import load_config
from copilot.core.events import TranscriptFinal, UtteranceDropped
from copilot.stt.factory import make_engine, segmenter_config
from copilot.stt.pipeline import SpeechPipeline

AUDIO = Path(__file__).parents[1] / "fixtures" / "audio"
pytestmark = pytest.mark.slow


def words(text: str) -> list[str]:
    return re.findall(r"[a-z]+", text.lower().replace("-", ""))  # "by-product" == "byproduct"


@pytest.fixture(scope="module")
def engine():
    eng = make_engine(load_config(environ={}))
    eng.load()
    return eng


async def run_pipeline(engine, audio: np.ndarray):
    bus = EventBus()
    finals, dropped = [], []

    async def collect(e):
        (finals if isinstance(e, TranscriptFinal) else dropped).append(e)

    bus.subscribe("collect", collect, [TranscriptFinal, UtteranceDropped])
    pipe = SpeechPipeline(bus, ArraySource(audio, speed=0), engine, segmenter=segmenter_config(load_config(environ={})))
    pipe.start()
    await pipe.wait_finished()
    await bus.close()
    return finals, dropped, pipe


async def test_tts_lecture_is_segmented_and_transcribed(engine):
    audio = read_wav_mono16k(AUDIO / "photosynthesis_tts.wav")
    expected = [l.strip() for l in (AUDIO / "photosynthesis_tts.txt").read_text(encoding="utf-8-sig").splitlines() if l.strip()]
    finals, dropped, _ = await run_pipeline(engine, audio)

    # one utterance per sentence (1.5 s pauses > 600 ms hangover)
    assert len(finals) == len(expected), [f.segment.text for f in finals]
    for f, ref in zip(finals, expected):
        ratio = SequenceMatcher(None, words(f.segment.text), words(ref)).ratio()
        assert ratio >= 0.9, (f.segment.text, ref)
    starts = [f.segment.start for f in finals]
    assert starts == sorted(starts)
    assert all(f.segment.end <= len(audio) / 16_000 + 1.1 for f in finals)
    assert not dropped


async def test_silence_and_noise_produce_no_transcript(engine):
    rng = np.random.default_rng(0)
    audio = np.concatenate([np.zeros(16_000 * 3, np.float32), (rng.standard_normal(16_000 * 3) * 0.003).astype(np.float32)])
    finals, _, _ = await run_pipeline(engine, audio)
    assert finals == []
