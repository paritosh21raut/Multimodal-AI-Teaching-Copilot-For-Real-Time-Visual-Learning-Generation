"""Speech pipeline: AudioSource → SileroVad → UtteranceSegmenter → WhisperEngine → bus (F-002).

Two worker threads keep the asyncio loop free:
- audio thread: VAD + segmentation for every 32 ms frame (cheap, must never stall)
- STT thread: Whisper inference, one utterance at a time
"""
from __future__ import annotations

import asyncio
import logging
import queue
import threading
import time
from typing import Optional

import numpy as np

from copilot.audio.segmenter import SegmenterConfig, Utterance, UtteranceSegmenter
from copilot.audio.sources import END, AudioSource, put_end
from copilot.audio.vad import SileroVad
from copilot.core.bus import EventBus
from copilot.core.events import (
    AudioDeviceLost,
    AudioLevel,
    Event,
    TranscriptFinal,
    TranscriptSegment,
    UtteranceDropped,
)
from copilot.stt.engine import WhisperEngine

log = logging.getLogger(__name__)

LEVEL_INTERVAL_S = 0.2
BACKLOG_WARN = 3
NO_AUDIO_WATCHDOG_S = 3.0  # no frames at all for this long -> device presumed lost
STOP_TIMEOUT_S = 15.0
PUBLISH_TIMEOUT_S = 10.0


class SpeechPipeline:
    def __init__(
        self,
        bus: EventBus,
        source: AudioSource,
        engine: WhisperEngine,
        *,
        segmenter: Optional[SegmenterConfig] = None,
        prompt: Optional[str] = None,
    ) -> None:
        self._bus = bus
        self._source = source
        self._engine = engine
        self._seg_cfg = segmenter or SegmenterConfig()
        self._prompt = prompt
        self._vad = SileroVad()
        self._utterances: "queue.Queue[Optional[tuple[Utterance, float]]]" = queue.Queue()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._finished = asyncio.Event()
        self._threads: list[threading.Thread] = []
        self.stats = {"utterances": 0, "published": 0, "dropped": 0, "latency_ms": []}

    # ---- lifecycle -------------------------------------------------------------------------
    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._threads = [
            threading.Thread(target=self._audio_loop, name="audio-vad", daemon=True),
            threading.Thread(target=self._stt_loop, name="stt", daemon=True),
        ]
        for t in self._threads:
            t.start()
        try:
            self._source.start()
        except Exception:
            put_end(self._source.frames)  # let both threads exit; wait_finished() resolves
            raise

    async def wait_finished(self) -> None:
        """Resolves when a finite source is exhausted and every utterance has been transcribed."""
        await self._finished.wait()

    async def stop(self) -> None:
        """Idempotent; safe before start(). Waits (bounded) for the in-flight utterance to finish."""
        if self._loop is None:
            return
        self._source.stop()
        put_end(self._source.frames)  # unblock the audio thread even if the source didn't
        try:
            await asyncio.wait_for(self._finished.wait(), timeout=STOP_TIMEOUT_S)
        except asyncio.TimeoutError:
            log.error("speech pipeline did not stop within %.0f s", STOP_TIMEOUT_S)

    # ---- threads ---------------------------------------------------------------------------
    def _publish(self, event: Event, wait: bool = True) -> None:
        assert self._loop is not None
        try:
            fut = asyncio.run_coroutine_threadsafe(self._bus.publish(event), self._loop)
            if wait:
                fut.result(timeout=PUBLISH_TIMEOUT_S)  # preserves ordering of transcript events
        except Exception as e:  # loop closing/closed or bus stuck: never hang a worker thread
            log.warning("could not publish %s: %s", event.type, e)

    def _audio_loop(self) -> None:
        seg = UtteranceSegmenter(self._seg_cfg)
        last_level = 0.0
        sq_sum, n = 0.0, 0
        voice = False
        silent_warned = False
        try:
            while True:
                try:
                    frame = self._source.frames.get(timeout=NO_AUDIO_WATCHDOG_S)
                except queue.Empty:
                    if not silent_warned:
                        silent_warned = True
                        self._publish(AudioDeviceLost(detail=f"no audio frames for {NO_AUDIO_WATCHDOG_S:.0f} s"))
                    continue
                silent_warned = False
                if frame is END:
                    for u in seg.flush():
                        self._utterances.put((u, time.perf_counter()))
                    break
                prob = self._vad(frame)
                voice = voice or prob >= self._seg_cfg.end_threshold
                for u in seg.push(frame, prob):
                    self._utterances.put((u, time.perf_counter()))
                    backlog = self._utterances.qsize()
                    if backlog > BACKLOG_WARN:
                        log.warning("STT backlog: %d utterances pending", backlog)
                sq_sum += float(np.mean(frame * frame))
                n += 1
                now = time.perf_counter()
                if now - last_level >= LEVEL_INTERVAL_S:
                    self._publish(AudioLevel(rms=(sq_sum / n) ** 0.5, speaking=seg.in_speech, voice=voice),
                                  wait=False)
                    last_level, sq_sum, n, voice = now, 0.0, 0, False
            error = getattr(self._source, "error", None)
            if error:
                self._publish(AudioDeviceLost(detail=error))
        except Exception as e:  # surface, never die silently
            log.exception("audio thread failed")
            self._publish(AudioDeviceLost(detail=f"audio thread failed: {e}"))
        finally:
            self._utterances.put(None)

    def _stt_loop(self) -> None:
        try:
            while True:
                item = self._utterances.get()
                if item is None:
                    break
                utt, detected_at = item
                self.stats["utterances"] += 1
                try:
                    res = self._engine.transcribe(utt.audio, self._prompt)
                except Exception as e:
                    log.exception("STT failed for utterance %.1f-%.1f", utt.start, utt.end)
                    self._publish(UtteranceDropped(start=utt.start, end=utt.end, reason=f"stt_error: {e}"))
                    self.stats["dropped"] += 1
                    continue
                latency_ms = (time.perf_counter() - detected_at) * 1000
                if res.rejected:
                    self.stats["dropped"] += 1
                    self._publish(UtteranceDropped(start=utt.start, end=utt.end, reason=res.rejected, text=res.text))
                    continue
                segment = TranscriptSegment(
                    text=res.text,
                    start=round(utt.start, 3),
                    end=round(utt.end, 3),
                    confidence=round(res.confidence, 3),
                    source="mic",
                )
                self._publish(TranscriptFinal(segment=segment, stt_latency_ms=round(latency_ms, 1)))
                self.stats["published"] += 1
                self.stats["latency_ms"].append(latency_ms)
        finally:
            assert self._loop is not None
            try:
                self._loop.call_soon_threadsafe(self._finished.set)
            except RuntimeError:  # loop already closed
                pass
