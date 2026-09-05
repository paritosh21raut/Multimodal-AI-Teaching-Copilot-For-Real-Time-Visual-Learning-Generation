from __future__ import annotations

import threading

import sounddevice as sd

from app.audio.audio_queue import AudioQueue
from app.audio.microphone import Microphone
from app.utils.logger import app_logger


class AudioStream:
    """
    Real-time microphone capture.

    The PortAudio callback only:
        1. records callback status
        2. copies the microphone buffer
        3. places it into the bounded queue

    No Whisper, VAD, file I/O, or downstream processing occurs inside
    the callback.
    """

    def __init__(
        self,
        microphone: Microphone | None = None,
        audio_queue: AudioQueue | None = None,
    ):
        self.microphone = microphone or Microphone()
        self.audio_queue = audio_queue or AudioQueue()

        self._stream = None
        self._stop_event = threading.Event()

        self._callback_count = 0
        self._callback_status_count = 0

    def callback(self, indata, frames, time_info, status):
        """
        Extremely lightweight PortAudio callback.
        """

        if status:
            self._callback_status_count += 1

        try:
            chunk = indata.copy()

            queued = self.audio_queue.put(chunk)

            if not queued:
                self._callback_status_count += 1

            self._callback_count += 1

        except Exception:
            # Never allow callback exceptions to bring down the stream.
            self._callback_status_count += 1

    def get_queue(self) -> AudioQueue:
        return self.audio_queue

    def start(self):
        """
        Starts microphone capture and blocks until stopped.
        """

        if self._stream is not None:
            return

        self._stop_event.clear()

        app_logger.info("Starting Audio Stream...")

        try:
            with self.microphone.open_stream(self.callback) as stream:

                self._stream = stream

                app_logger.success("Audio Stream Running")

                print(
                    "\nListening... Press Ctrl + C to stop.\n"
                )

                while not self._stop_event.is_set():

                    sd.sleep(100)

        except KeyboardInterrupt:

            app_logger.warning(
                "Audio Stream Interrupted"
            )

        finally:

            self._stream = None

            app_logger.info(
                "Audio Stream Closed"
            )

    def stop(self):
        """
        Requests stream shutdown.
        """

        self._stop_event.set()

        stream = self._stream

        if stream is not None:

            try:
                stream.stop()

            except Exception:
                pass

    def stats(self) -> dict:
        return {
            "callback_count": self._callback_count,
            "callback_status_count": self._callback_status_count,
            **self.audio_queue.stats(),
        }