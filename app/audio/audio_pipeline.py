from __future__ import annotations

from app.audio.audio_stream import AudioStream
from app.audio.audio_worker import AudioWorker


class AudioPipeline:
    """
    Coordinates microphone capture and audio/STT processing.

    The pipeline itself has no dependency on lecture generation,
    dashboards, LLMs, slides, or PPT.
    """

    def __init__(
        self,
        on_preview_transcript=None,
        on_final_transcript=None,
    ):

        self.stream = AudioStream()

        self.worker = AudioWorker(
            self.stream.get_queue(),
            on_preview_transcript=(
                on_preview_transcript
            ),
            on_final_transcript=(
                on_final_transcript
            ),
        )

        self._started = False

    def start(self):

        if self._started:
            return

        self._started = True

        self.worker.start()

        try:

            self.stream.start()

        finally:

            self.stop()

    def stop(self):

        if not self._started:
            return

        self.stream.stop()

        self.worker.stop()

        if (
            self.worker.is_alive()
            and self.worker
            is not __import__(
                "threading"
            ).current_thread()
        ):

            self.worker.join(
                timeout=25.0
            )

        self._started = False

    def get_transcript(self) -> str:

        return self.worker.get_full_transcript()

    def get_metrics(self) -> dict:

        return self.worker.get_metrics()