"""Audio sources producing 16 kHz mono float32 blocks of FRAME samples into a thread-safe queue."""
from __future__ import annotations

import logging
import queue
import threading
import time
import wave
from pathlib import Path
from typing import Optional, Protocol, Union

import numpy as np

from copilot.audio.segmenter import SAMPLE_RATE
from copilot.audio.vad import FRAME

log = logging.getLogger(__name__)

END = None  # sentinel put on the queue when a finite source is exhausted


def put_end(frames: "queue.Queue[Optional[np.ndarray]]") -> None:
    """Enqueue END without ever blocking (drop the oldest frame if the queue is full)."""
    while True:
        try:
            frames.put_nowait(END)
            return
        except queue.Full:
            try:
                frames.get_nowait()
            except queue.Empty:
                pass


class AudioSource(Protocol):
    frames: "queue.Queue[Optional[np.ndarray]]"

    def start(self) -> None: ...
    def stop(self) -> None: ...


class MicSource:
    def __init__(self, device: Union[int, str, None] = None, max_queue: int = 2000) -> None:
        self.device = None if device == "" else device
        self.frames: "queue.Queue[Optional[np.ndarray]]" = queue.Queue(maxsize=max_queue)
        self.overflows = 0
        self.error: Optional[str] = None
        self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME,
            device=self.device,
            callback=self._callback,
            finished_callback=self._finished,
        )
        self._stream.start()
        log.info("mic opened: %s", self._stream.device)

    def _callback(self, indata, frames, time_info, status) -> None:
        if status.input_overflow:
            self.overflows += 1
        try:
            self.frames.put_nowait(indata[:, 0].copy())
        except queue.Full:
            self.overflows += 1

    def _finished(self) -> None:
        if self._stream is not None and not self._stream.stopped:
            self.error = "input stream finished unexpectedly"
        put_end(self.frames)

    def stop(self) -> None:
        if self._stream is not None:
            stream, self._stream = self._stream, None
            stream.stop()
            stream.close()


def read_wav_mono16k(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        if w.getframerate() != SAMPLE_RATE or w.getsampwidth() != 2:
            raise ValueError(f"{path}: expected 16 kHz 16-bit PCM, got {w.getframerate()} Hz {8 * w.getsampwidth()}-bit")
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        if w.getnchannels() > 1:
            raw = raw.reshape(-1, w.getnchannels()).mean(axis=1).astype(np.int16)
    return raw.astype(np.float32) / 32768.0


class ArraySource:
    """Plays an in-memory signal as if it were a microphone (speed=0 → as fast as possible)."""

    def __init__(self, audio: np.ndarray, speed: float = 1.0, tail_silence_s: float = 1.0) -> None:
        pad = (-len(audio)) % FRAME + int(tail_silence_s * SAMPLE_RATE) // FRAME * FRAME
        self._audio = np.concatenate([audio.astype(np.float32), np.zeros(pad, np.float32)])
        self._speed = speed
        self.frames: "queue.Queue[Optional[np.ndarray]]" = queue.Queue()
        self._stop = threading.Event()
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="array-source", daemon=True)
        self._thread.start()

    def _run(self) -> None:
        frame_s = FRAME / SAMPLE_RATE
        t0 = time.perf_counter()
        for i in range(0, len(self._audio), FRAME):
            if self._stop.is_set():
                break
            if self._speed > 0:
                due = t0 + (i // FRAME) * frame_s / self._speed
                delay = due - time.perf_counter()
                if delay > 0:
                    time.sleep(delay)
            self.frames.put(self._audio[i:i + FRAME])
        put_end(self.frames)

    def stop(self) -> None:
        self._stop.set()


class WavFileSource(ArraySource):
    def __init__(self, path: Path, speed: float = 1.0) -> None:
        super().__init__(read_wav_mono16k(path), speed=speed)
