"""Regression tests for bugs found in the independent M1 review."""
import asyncio

import numpy as np
import pytest

from copilot.audio.segmenter import SegmenterConfig, UtteranceSegmenter
from copilot.audio.sources import ArraySource, MicSource
from copilot.core.bus import EventBus
from copilot.core.config import Config
from copilot.core.events import AudioDeviceLost
from copilot.stt.engine import SttResult
from copilot.stt.factory import make_source
from copilot.stt.pipeline import SpeechPipeline

F = 512


def test_forced_split_remainder_shorter_than_min_speech_is_kept():
    cfg = SegmenterConfig(max_utterance_s=6.4, split_search_s=2.0)  # 200-frame max
    probs = [0.9] * 196 + [0.36] + [0.9] * 6 + [0.0] * 30  # dip near the end → 6-frame remainder
    seg = UtteranceSegmenter(cfg)
    out = []
    for i, p in enumerate(probs):
        out += seg.push(np.full(F, float(i), np.float32), p)
    assert len(out) == 2
    assert seg.dropped_short == 0
    total = sum(len(u.audio) for u in out)
    assert total >= (196 + 1 + 6) * F  # no speech frames lost


def test_flat_speech_forced_split_happens_near_max_length():
    cfg = SegmenterConfig(max_utterance_s=6.4, split_search_s=2.0)
    seg = UtteranceSegmenter(cfg)
    out = []
    for i in range(260):
        out += seg.push(np.zeros(F, np.float32), 0.9)
    assert out and out[0].forced_split
    assert out[0].duration == pytest.approx(200 * F / 16_000)


class StubEngine:
    def transcribe(self, audio, prompt=None):
        return SttResult(text="hello", confidence=1.0, no_speech_prob=0.0, compression_ratio=1.0, infer_ms=1.0)


async def test_stop_before_start_returns_immediately():
    pipe = SpeechPipeline(EventBus(), ArraySource(np.zeros(F * 4, np.float32), speed=0), StubEngine())
    await asyncio.wait_for(pipe.stop(), timeout=1)


class FailingSource(ArraySource):
    def start(self):
        raise RuntimeError("mic unavailable")


async def test_source_start_failure_does_not_leave_threads_hanging():
    bus = EventBus()
    pipe = SpeechPipeline(bus, FailingSource(np.zeros(F, np.float32)), StubEngine())
    with pytest.raises(RuntimeError):
        pipe.start()
    await asyncio.wait_for(pipe.wait_finished(), timeout=3)
    await asyncio.wait_for(pipe.stop(), timeout=3)
    await bus.close()


class SilentSource(ArraySource):
    """Started but never delivers frames (e.g. an unplugged mic on Windows)."""

    def start(self):
        pass


async def test_watchdog_reports_device_lost_when_no_frames(monkeypatch):
    monkeypatch.setattr("copilot.stt.pipeline.NO_AUDIO_WATCHDOG_S", 0.2)
    bus = EventBus()
    lost = []

    async def on_lost(e):
        lost.append(e)

    bus.subscribe("lost", on_lost, [AudioDeviceLost])
    pipe = SpeechPipeline(bus, SilentSource(np.zeros(F, np.float32)), StubEngine())
    pipe.start()
    await asyncio.sleep(0.6)
    await pipe.stop()
    await bus.close()
    assert len(lost) == 1  # reported once, not every timeout


@pytest.mark.parametrize("raw,expected", [("", None), ("0", 0), ("7", 7), ("Microphone Array", "Microphone Array")])
def test_mic_device_config_parsing(raw, expected):
    src = make_source(Config({"audio": {"device": raw}}), None, 1.0)
    assert isinstance(src, MicSource)
    assert src.device == expected
