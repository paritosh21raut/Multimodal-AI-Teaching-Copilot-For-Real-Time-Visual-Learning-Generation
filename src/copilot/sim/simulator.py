"""Lecture simulator: a script file → timed TranscriptFinal events (spec: docs/specs/F-001-foundation.md).

Stands in for audio capture + STT so the rest of the pipeline can be tested without a microphone.
"""
from __future__ import annotations

import asyncio
import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Union

from copilot.core.bus import EventBus
from copilot.core.events import AudioLevel, TranscriptFinal, TranscriptSegment

VAD_TICK_S = 0.2        # lecture seconds between simulated AudioLevel events (as the mic pipeline, ~5 Hz)
MIN_VAD_TICK_WALL_S = 0.02

_PAUSE = re.compile(r"^\[pause\s+([0-9.]+)\]$", re.IGNORECASE)


@dataclass
class ScriptUtterance:
    text: str
    pause_before: float = 0.0
    expect: dict[str, str] = field(default_factory=dict)
    line_no: int = 0


@dataclass
class LectureScript:
    setup: dict[str, str]
    utterances: list[ScriptUtterance]


class ScriptError(ValueError):
    pass


def _parse_kv(text: str, line_no: int) -> dict[str, str]:
    out: dict[str, str] = {}
    for token in shlex.split(text):
        if "=" not in token:
            raise ScriptError(f"line {line_no}: expected key=value, got {token!r}")
        k, v = token.split("=", 1)
        out[k.strip()] = v.strip()
    return out


def parse_script(source: Union[str, Path]) -> LectureScript:
    text = Path(source).read_text(encoding="utf-8") if isinstance(source, Path) else source
    setup: dict[str, str] = {}
    utterances: list[ScriptUtterance] = []
    pending_pause = 0.0
    pending_expect: dict[str, str] = {}
    for line_no, raw in enumerate(text.splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("@setup"):
            setup.update(_parse_kv(line[len("@setup"):], line_no))
            continue
        if line.startswith("@expect"):
            pending_expect.update(_parse_kv(line[len("@expect"):], line_no))
            continue
        if line.startswith("@"):
            raise ScriptError(f"line {line_no}: unknown directive {line.split()[0]}")
        m = _PAUSE.match(line)
        if m:
            pending_pause += float(m.group(1))
            continue
        utterances.append(ScriptUtterance(line, pending_pause, pending_expect, line_no))
        pending_pause, pending_expect = 0.0, {}
    return LectureScript(setup, utterances)


def utterance_duration(text: str, wpm: float, min_s: float) -> float:
    return max(min_s, len(text.split()) / wpm * 60.0)


class LectureSimulator:
    """Publishes each utterance as TranscriptFinal at the moment its speech would end.

    speed > 1 compresses wall-clock time; segment timestamps stay in lecture time.
    """

    def __init__(
        self,
        bus: EventBus,
        script: LectureScript,
        *,
        words_per_minute: float = 150.0,
        min_utterance_s: float = 1.0,
        speed: float = 1.0,
        vad: bool = False,
    ) -> None:
        """vad: also publish AudioLevel(voice=...) while an utterance is being "spoken", like the mic pipeline,
        so pause detection sees the speaker talking between transcripts (a transcript arrives at its end)."""
        if speed <= 0:
            raise ValueError("speed must be > 0")
        self._bus = bus
        self._script = script
        self._wpm = words_per_minute
        self._min_s = min_utterance_s
        self._speed = speed
        self._vad = vad
        self.published = 0

    def timeline(self) -> list[TranscriptSegment]:
        t = 0.0
        segments = []
        for u in self._script.utterances:
            t += u.pause_before
            dur = utterance_duration(u.text, self._wpm, self._min_s)
            segments.append(
                TranscriptSegment(text=u.text, start=t, end=t + dur, source="sim", expect=u.expect)
            )
            t += dur
        return segments

    async def run(self, stop: Optional[asyncio.Event] = None) -> None:
        clock = 0.0
        for seg in self.timeline():
            if self._vad:
                if await self._speak(clock, seg, stop):
                    return
                clock = seg.end
            else:
                wait = (seg.end - clock) / self._speed
                clock = seg.end
                if await self._sleep(wait, stop):
                    return
            await self._bus.publish(TranscriptFinal(segment=seg))
            self.published += 1

    async def _sleep(self, wait: float, stop: Optional[asyncio.Event]) -> bool:
        """Sleep wall time; True if a stop was requested."""
        if stop is None:
            await asyncio.sleep(max(0.0, wait))
            return False
        try:
            await asyncio.wait_for(stop.wait(), timeout=max(0.0, wait))
            return True
        except asyncio.TimeoutError:
            return False

    async def _speak(self, clock: float, seg: TranscriptSegment, stop: Optional[asyncio.Event]) -> bool:
        """Advance from `clock` to seg.end, publishing simulated VAD levels: silence before seg.start, voice after."""
        tick = max(VAD_TICK_S, MIN_VAD_TICK_WALL_S * self._speed)
        loop = asyncio.get_running_loop()
        t0_wall, t0 = loop.time(), clock
        while clock < seg.end:
            clock = min(seg.end, clock + tick)
            if await self._sleep(t0_wall + (clock - t0) / self._speed - loop.time(), stop):
                return True
            voice = seg.start < clock < seg.end or (clock == seg.end and seg.end > seg.start)
            await self._bus.publish(AudioLevel(rms=0.05 if voice else 0.001, speaking=voice, voice=voice))
        return False
