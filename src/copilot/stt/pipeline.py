"""Speech pipeline: AudioSource → SileroVad → UtteranceSegmenter → WhisperEngine → bus (F-002).

Worker threads keep the asyncio loop free:
- audio thread: VAD + segmentation for every 32 ms frame (cheap, must never stall)
- STT thread: Whisper inference, one utterance at a time
- partial thread (F-013 S1b, optional): a fast model transcribes the utterance in progress every `partial_interval_s`
  (latest snapshot only, never queued) -> TranscriptPartial with the prefix two passes agree on. It has its own
  model, so final transcripts never wait for it.
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
    TranscriptPartial,
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
PARTIAL_MIN_S = 0.8  # no partial of a shorter stretch of speech (too little for Whisper to say anything stable)
SPLIT_AFTER_WORDS = 2  # a sentence end counts once this many agreed words follow it (the speaker went on)
_PUNCT = ".,!?;:\"'"


def _norm_word(w: str) -> str:
    return w.lower().strip(_PUNCT)


def sentence_split_point(stable: str, words: list[tuple[str, float, float]]) -> Optional[float]:
    """Seconds into the utterance where its last finished sentence ends, when the agreed text goes on after it by at
    least SPLIT_AFTER_WORDS words (F-013 S1b: lines become sentences even when the speaker does not pause)."""
    n = len(stable.split())
    if n <= SPLIT_AFTER_WORDS or len(words) < n:
        return None
    for i in range(n - SPLIT_AFTER_WORDS - 1, -1, -1):
        w = words[i][0]
        if w.endswith((".", "?", "!")) and not w.endswith(("...", "..")) and len(w.rstrip(".?!")) > 1:
            return words[i][2]
    return None


def stable_sentences(stable: str, words: list[tuple[str, float, float]], start: float) -> list[tuple[str, float]]:
    """The agreed text as sentences with the lecture time each starts (word timestamps of the live pass)."""
    toks = stable.split()
    out: list[tuple[str, float]] = []
    cur: list[str] = []
    t0 = start
    for i, tok in enumerate(toks):
        if not cur:
            t0 = start + (words[i][1] if i < len(words) else (words[-1][2] if words else 0.0))
        cur.append(tok)
        if tok.endswith((".", "?", "!")):
            out.append((" ".join(cur), round(t0, 2)))
            cur = []
    if cur:
        out.append((" ".join(cur), round(t0, 2)))
    return out


def stable_prefix(previous: str, current: str, kept: str = "") -> str:
    """Local agreement: the words two consecutive hypotheses share from the start (punctuation and case ignored),
    taken from the current one. A prefix agreed earlier (`kept`) is not lost while the current hypothesis still
    starts with it."""
    a, b = previous.split(), current.split()
    n = 0
    while n < min(len(a), len(b)) and _norm_word(a[n]) == _norm_word(b[n]):
        n += 1
    k = kept.split()
    if len(k) > n and len(b) >= len(k) and all(_norm_word(x) == _norm_word(y) for x, y in zip(k, b)):
        n = len(k)
    return " ".join(b[:n])


class SpeechPipeline:
    def __init__(
        self,
        bus: EventBus,
        source: AudioSource,
        engine: WhisperEngine,
        *,
        segmenter: Optional[SegmenterConfig] = None,
        prompt: Optional[str] = None,
        partial_engine: Optional[WhisperEngine] = None,
        partial_interval_s: float = 0.8,
        split_sentences: bool = True,
    ) -> None:
        self._bus = bus
        self._source = source
        self._engine = engine
        self._seg_cfg = segmenter or SegmenterConfig()
        self._prompt = prompt
        self._vad = SileroVad()
        self._utterances: "queue.Queue[Optional[tuple[Utterance, float]]]" = queue.Queue()
        self._partial_engine = partial_engine
        self._partial_interval = partial_interval_s
        self._split_sentences = split_sentences
        self._partial_slot: Optional[tuple[int, float, np.ndarray, float]] = None  # latest snapshot only
        self._partial_lock = threading.Lock()
        self._partial_ready = threading.Event()
        self._partial_stop = False
        self._finalized = 0  # highest utterance number already transcribed (its partials are obsolete)
        self._split_request: Optional[tuple[int, float]] = None  # (utterance, seconds into it): cut at a sentence end
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._finished = asyncio.Event()
        self._threads: list[threading.Thread] = []
        self.stats = {"utterances": 0, "published": 0, "dropped": 0, "latency_ms": []}

    # ---- lifecycle -------------------------------------------------------------------------
    def set_split(self, on: bool) -> None:
        """Cut lines at sentence ends heard by the live model (F-013 performance mode "high"), or keep the speaker's
        utterances ("standard": fewer, longer lines, fewer LLM calls). Takes effect on the next partial pass."""
        self._split_sentences = bool(on)
        if not on:
            self._split_request = None

    def set_prompt(self, prompt: Optional[str]) -> None:
        """A new vocabulary prompt for the next utterances (F-013 S3: the lecture glossary grew). The final model's
        thread reads it per utterance; one reference assignment, no lock needed."""
        self._prompt = prompt

    def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._threads = [
            threading.Thread(target=self._audio_loop, name="audio-vad", daemon=True),
            threading.Thread(target=self._stt_loop, name="stt", daemon=True),
        ]
        if self._partial_engine is not None:
            self._threads.append(threading.Thread(target=self._partial_loop, name="stt-partial", daemon=True))
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
        last_partial = 0.0
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
                try:
                    done = seg.push(frame, prob)
                except Exception as e:  # a segmentation bug costs one utterance, never the lecture
                    log.exception("segmenter failed; pending utterance dropped")
                    self._publish(UtteranceDropped(start=seg.pending_start(), end=seg.clock_s(),
                                                   reason=f"segmenter_error: {e}"))
                    seg.abandon()
                    done = []
                for u in done:
                    self._utterances.put((u, time.perf_counter()))
                    backlog = self._utterances.qsize()
                    if backlog > BACKLOG_WARN:
                        log.warning("STT backlog: %d utterances pending", backlog)
                req, self._split_request = self._split_request, None
                if req is not None:
                    try:
                        u = seg.split_at(*req)
                    except Exception:
                        log.exception("sentence split failed")
                        u = None
                    if u is not None:
                        self._utterances.put((u, time.perf_counter()))
                if self._partial_engine is not None and seg.in_speech:
                    t = time.perf_counter()
                    if t - last_partial >= self._partial_interval:
                        snap = seg.snapshot()
                        if snap is not None and len(snap[2]) >= PARTIAL_MIN_S * 16_000:
                            with self._partial_lock:
                                self._partial_slot = (*snap, t)
                            self._partial_ready.set()
                            last_partial = t
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
            self._partial_stop = True
            self._partial_ready.set()

    def _partial_loop(self) -> None:
        """Latest snapshot of the utterance in progress -> TranscriptPartial. Never blocks the other threads; a failing
        pass is logged and the next snapshot is tried (the live layer is a convenience, the final text is the record)."""
        assert self._partial_engine is not None
        last_text: dict[int, str] = {}
        kept: dict[int, str] = {}
        failures = 0
        while True:
            self._partial_ready.wait()
            self._partial_ready.clear()
            if self._partial_stop:
                return
            with self._partial_lock:
                slot, self._partial_slot = self._partial_slot, None
            if slot is None:
                continue
            number, start, audio, taken = slot
            if number <= self._finalized:
                continue  # its final text is already out
            try:
                # no vocabulary prompt: it made distil-small.en ~10x slower (1.4 s instead of 0.15 s per pass with
                # the 30 study-material terms, F-013 S1b); the final text keeps it
                res = self._partial_engine.transcribe(audio, None, words=True)
            except Exception:
                failures += 1
                if failures <= 3:
                    log.exception("partial transcription failed (utterance %d)", number)
                continue
            if res.rejected or number <= self._finalized:
                continue
            stable = stable_prefix(last_text.get(number, ""), res.text, kept.get(number, ""))
            sentences = stable_sentences(stable, res.words, start)
            last_text, kept = {number: res.text}, {number: stable}  # older utterances are done
            if self._split_sentences:
                at = sentence_split_point(stable, res.words)
                if at is not None:
                    self._split_request = (number, at)
            self._publish(TranscriptPartial(utterance=number, start=round(start, 3), text=res.text, stable=stable,
                                            sentences=sentences,
                                            latency_ms=round((time.perf_counter() - taken) * 1000, 1),
                                            infer_ms=round(res.infer_ms, 1)), wait=False)

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
                self._finalized = max(self._finalized, utt.number)
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
                self._publish(TranscriptFinal(segment=segment, stt_latency_ms=round(latency_ms, 1),
                                              utterance=utt.number))
                self.stats["published"] += 1
                self.stats["latency_ms"].append(latency_ms)
        finally:
            assert self._loop is not None
            try:
                self._loop.call_soon_threadsafe(self._finished.set)
            except RuntimeError:  # loop already closed
                pass
