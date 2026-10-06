"""UnderstandingService: TranscriptFinal → filter → tracker → buffer/gate → Interpreter → InterpretationReady.

Deterministic flow control lives here; the LLM only answers the Interpreter's bounded question.
One interpretation in flight at a time, and the next prompt is built only after the state store has
applied the previous result, so state is updated strictly in order.
"""
from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Optional

from copilot.core.bus import EventBus
from copilot.core.config import Config
from copilot.core.events import (
    AudioLevel,
    ConceptSignal,
    ErrorRaised,
    InterpretationReady,
    InterpretRequested,
    Lifecycle,
    LifecycleChanged,
    TranscriptFinal,
    UtteranceClassified,
    UtteranceDropped,
    new_id,
)
from copilot.core.state import LectureStateStore
from copilot.understanding.embedder import Embedder
from copilot.understanding.filter import UtteranceFilter
from copilot.understanding.gate import BufferedLine, DiscourseBuffer, Gate, GateConfig
from copilot.understanding.interpreter import (
    InterpretResult,
    Interpreter,
    InterpreterSettings,
    fallback_interpretation,
)
from copilot.understanding.prompt import BuiltPrompt, PromptBudgetError
from copilot.understanding.tracker import ConceptTracker

log = logging.getLogger(__name__)

TICK_S = 0.2
APPLY_TIMEOUT_S = 5.0
# Speech heard after the last transcript arrived is still being segmented/transcribed; its text normally
# arrives within ~0.6 s (segment end) + STT latency. Until then that speech is not counted as a pause.
PENDING_SPEECH_GRACE_S = 2.0


def vad_silence(now: float, last_voice: float, last_arrival: float, speed: float = 1.0) -> float:
    """Lecture-time silence since the last voiced frame (wall times in, see UnderstandingService._silence)."""
    silence = (now - last_voice) * speed
    if last_voice > last_arrival:
        silence -= PENDING_SPEECH_GRACE_S * speed
    return max(0.0, silence)


@dataclass
class UnderstandingSettings:
    min_call_interval_s: float = 8.0
    gate: GateConfig = field(default_factory=GateConfig)
    interpreter: InterpreterSettings = field(default_factory=InterpreterSettings)
    shift_threshold: float = 0.75
    concept_alpha: float = 0.35
    topic_alpha: float = 0.1

    @classmethod
    def from_config(cls, config: Config) -> "UnderstandingSettings":
        u = config.section("understanding")

        def pick(dc):
            return {k: u[k] for k in dc.__dataclass_fields__ if k in u}

        top = {k: u[k] for k in ("min_call_interval_s", "shift_threshold", "concept_alpha", "topic_alpha") if k in u}
        return cls(gate=GateConfig(**pick(GateConfig)), interpreter=InterpreterSettings(**pick(InterpreterSettings)), **top)


STATS_HISTORY = 1000  # bounded: recent values only, regardless of lecture length


@dataclass
class UnderstandingStats:
    requests: int = 0
    fallbacks: int = 0
    repaired: int = 0
    sent_segments: int = 0
    excluded_segments: int = 0
    paused_segments: int = 0  # said while the teacher had paused the lecture: not interpreted
    max_calls_per_minute: int = 0
    max_prompt_tokens: int = 0
    call_wall_times: deque = field(default_factory=lambda: deque(maxlen=STATS_HISTORY))  # monotonic at send
    prompt_tokens: deque = field(default_factory=lambda: deque(maxlen=STATS_HISTORY))
    latencies_ms: deque = field(default_factory=lambda: deque(maxlen=STATS_HISTORY))
    providers: dict[str, int] = field(default_factory=dict)
    reasons: dict[str, int] = field(default_factory=dict)
    _window: deque = field(default_factory=deque)  # send times within the last 60 s

    def record_call(self, t: float) -> None:
        self.call_wall_times.append(t)
        self._window.append(t)
        while self._window and self._window[0] <= t - 60.0:
            self._window.popleft()
        self.max_calls_per_minute = max(self.max_calls_per_minute, len(self._window))


class UnderstandingService:
    def __init__(
        self,
        bus: EventBus,
        store: LectureStateStore,
        interpreter: Interpreter,
        embedder: Optional[Embedder],
        settings: Optional[UnderstandingSettings] = None,
        *,
        speed: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.bus = bus
        self.store = store
        self.interpreter = interpreter
        self.embedder = embedder
        self.s = settings or UnderstandingSettings()
        self.speed = speed
        self.clock = clock
        self.filter = UtteranceFilter()
        self.tracker = ConceptTracker(self.s.shift_threshold, self.s.concept_alpha, self.s.topic_alpha)
        self.buffer = DiscourseBuffer()
        self.gate = Gate(self.s.gate)
        self.stats = UnderstandingStats()
        self._wake = asyncio.Event()
        self._in_flight = False
        self._flushing = False
        self._last_call: Optional[float] = None
        self._last_end = 0.0           # lecture time of the latest buffered line end
        self._last_arrival = clock()   # wall time it arrived
        self._last_transcript = clock()  # wall time of the latest transcript of any kind (for the VAD grace)
        self._last_voice: Optional[float] = None  # wall time of the latest AudioLevel(voice=True)
        self._embed_warned = False
        self._paused = False  # the teacher paused the lecture (a break): new speech is not interpreted
        self._tasks: list[asyncio.Task] = []

    # ---- wiring -------------------------------------------------------------------------------
    def attach(self) -> None:
        self.bus.subscribe("understanding", self._on_event,
                           [TranscriptFinal, AudioLevel, UtteranceDropped, LifecycleChanged])
        self._tasks = [
            asyncio.create_task(self._worker(), name="understanding:worker"),
            asyncio.create_task(self._ticker(), name="understanding:ticker"),
        ]

    async def flush(self, timeout: float) -> bool:
        """Interpret everything still buffered (lecture ending). True if it finished in time."""
        self._flushing = True
        self._wake.set()
        deadline = self.clock() + timeout
        while self.clock() < deadline:
            await self.bus.drain()  # transcripts already published reach the buffer first
            if self.buffer.empty and not self._in_flight:
                return True
            self._wake.set()
            await asyncio.sleep(0.05)
        log.warning("understanding flush timed out with %d buffered lines", len(self.buffer.lines))
        return False

    async def stop(self) -> None:
        if not self.buffer.empty:
            log.warning("understanding stopped with %d uninterpreted lines (still in the event log)",
                        len(self.buffer.lines))
        for t in self._tasks:
            t.cancel()
        _, pending = await asyncio.wait(self._tasks, timeout=5.0) if self._tasks else (set(), set())
        if pending:
            log.error("understanding tasks did not stop within 5 s: %s", [t.get_name() for t in pending])
        self._tasks = []

    # ---- input path ---------------------------------------------------------------------------
    def lecture_now(self) -> float:
        return self._last_end + (self.clock() - self._last_arrival) * self.speed

    def _silence(self) -> Optional[float]:
        """Speaker silence from raw VAD frames (mic/WAV path); None without audio (simulator: the gate uses
        the time since the last line ended).

        Measured from the last voiced frame, not from transcript arrival: by the time a segment's text
        arrives the speaker has already been silent for the segmenter hangover plus the STT latency, so a
        real 1.2 s pause is visible as soon as the text is in the buffer. Speech heard after the latest
        transcript arrived belongs to a segment still in transcription and only counts after a grace.
        """
        if self._last_voice is None:
            return None
        return vad_silence(self.clock(), self._last_voice, self._last_transcript, self.speed)

    async def _on_event(self, event) -> None:
        if isinstance(event, LifecycleChanged):
            # Pause (user 2026-10-06): what was said before it is still interpreted (it is buffered); what is said
            # during it never reaches the buffer, so no slide is made from it. Resume continues normally.
            self._paused = event.state == Lifecycle.PAUSED
            return
        if isinstance(event, AudioLevel):
            if event.voice:
                self._last_voice = self.clock()
            return
        # Any transcript outcome (also filtered meta lines and dropped utterances) ends the pending-speech grace.
        self._last_transcript = self.clock()
        if isinstance(event, UtteranceDropped):
            return
        assert isinstance(event, TranscriptFinal)
        if self._paused:
            self.stats.paused_segments += 1
            log.info("paused: not interpreted: %s", event.segment.text)
            return
        seg = event.segment
        c = self.filter.classify(seg.text)
        await self.bus.publish(UtteranceClassified(segment_id=seg.id, kind=c.kind, maybe_meta=c.maybe_meta, rule=c.rule))
        if not c.to_buffer:
            self.stats.excluded_segments += 1
            return
        vec = None
        if self.embedder is not None:
            try:
                vec = (await asyncio.to_thread(self.embedder.embed, [seg.text]))[0]
            except Exception as e:  # degrade to cue words; surfaced once
                if not self._embed_warned:
                    self._embed_warned = True
                    log.exception("embedding failed; concept tracking falls back to cue words")
                    await self.bus.publish(ErrorRaised(component="understanding.embedder", error=str(e)))
        sig = self.tracker.update(seg.text, vec)
        await self.bus.publish(ConceptSignal(
            segment_id=seg.id, shift_score=round(sig.shift_score, 4), topic_shift=round(sig.topic_shift, 4),
            keyphrases=sig.keyphrases, cues=sig.cues, boundary=sig.boundary,
        ))
        self.buffer.add(
            BufferedLine(seg.id, seg.text, seg.start, seg.end, c.maybe_meta, c.kind == "question_to_class"),
            boundary=sig.boundary,
        )
        self._last_end = max(self._last_end, seg.end)
        self._last_arrival = self.clock()
        self._wake.set()

    async def _ticker(self) -> None:
        while True:
            await asyncio.sleep(TICK_S)
            if not self.buffer.empty:
                self._wake.set()

    # ---- interpretation path ------------------------------------------------------------------
    async def _worker(self) -> None:
        while True:
            await self._wake.wait()
            self._wake.clear()
            try:
                await self._maybe_interpret()
            except asyncio.CancelledError:
                raise
            except Exception as e:  # never kill the worker; surface the failure
                log.exception("understanding worker failed")
                await self.bus.publish(ErrorRaised(component="understanding.worker", error=str(e)))

    async def _maybe_interpret(self) -> None:
        reason = self.gate.check(self.buffer, self.lecture_now(), self._silence(), self._flushing)
        if reason is None:
            return
        if self._last_call is not None:  # wall-clock rate floor
            wait = self._last_call + self.s.min_call_interval_s - self.clock()
            if wait > 0 and reason != "words":
                self.buffer.seal()  # a coherent unit (pause/boundary/wait) stays as-is; new text goes to the next unit
            while wait > 0:  # loop: sleep can return early by the timer granularity (~16 ms on Windows)
                await asyncio.sleep(wait)
                wait = self._last_call + self.s.min_call_interval_s - self.clock()
        lines = self.buffer.take(self.s.gate.buffer_cap_tokens)
        if not lines:
            return
        self._in_flight = True
        try:
            await self._interpret(lines, reason)
        finally:
            self._in_flight = False
            self._wake.set()  # leftovers may already satisfy the gate

    async def _interpret(self, lines: list[BufferedLine], reason: str) -> None:
        state = self.store.snapshot()
        request_id = new_id()
        seg_ids = [l.segment_id for l in lines]
        self._last_call = self.clock()
        st = self.stats
        st.requests += 1
        st.record_call(self._last_call)
        st.reasons[reason] = st.reasons.get(reason, 0) + 1
        st.sent_segments += len(seg_ids)
        try:
            prompt: Optional[BuiltPrompt] = self.interpreter.build(state, lines)
        except PromptBudgetError:
            prompt = None  # the interpreter falls back and logs why
        await self.bus.publish(InterpretRequested(request_id=request_id, reason=reason, segment_ids=seg_ids,
                                                  prompt_tokens=prompt.tokens if prompt else 0))
        try:
            res = await self.interpreter.interpret(state, lines, prompt)
        except Exception as e:  # interpret() already falls back internally; this guards against its own bugs
            log.exception("interpreter raised")
            res = InterpretResult(fallback_interpretation(state, lines), fallback=True,
                                  fallback_reason=f"interpreter raised {type(e).__name__}: {e}"[:500])
        st.prompt_tokens.append(res.prompt_tokens)
        st.max_prompt_tokens = max(st.max_prompt_tokens, res.prompt_tokens)
        st.latencies_ms.append(res.latency_ms)
        if res.fallback:
            st.fallbacks += 1
        if res.repaired:
            st.repaired += 1
        if res.provider:
            st.providers[res.provider] = st.providers.get(res.provider, 0) + 1
        await self.bus.publish(InterpretationReady(
            request_id=request_id, interpretation=res.interpretation, segment_ids=seg_ids,
            provider=res.provider, latency_ms=round(res.latency_ms, 1), fallback=res.fallback,
            fallback_reason=res.fallback_reason, slide_refs=dict(state.slide_refs),
        ))
        if not await self.store.wait_applied(request_id, APPLY_TIMEOUT_S):
            log.error("state store did not apply interpretation %s within %.0fs", request_id, APPLY_TIMEOUT_S)
