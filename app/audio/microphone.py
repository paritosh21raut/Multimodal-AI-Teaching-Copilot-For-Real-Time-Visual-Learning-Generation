from __future__ import annotations

from typing import Optional

import sounddevice as sd

from app.utils.logger import app_logger


class Microphone:
    """
    Owns microphone stream configuration.

    The stream callback is intentionally kept outside this class so the
    audio processing pipeline can remain independent from hardware code.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        channels: int = 1,
        blocksize: int = 320,
        device: Optional[int | str] = None,
    ):
        if sample_rate <= 0:
            raise ValueError("sample_rate must be greater than zero")

        if channels <= 0:
            raise ValueError("channels must be greater than zero")

        if blocksize <= 0:
            raise ValueError("blocksize must be greater than zero")

        self.sample_rate = sample_rate
        self.channels = channels
        self.blocksize = blocksize
        self.device = device

    def open_stream(self, callback):
        """
        Opens a 16 kHz mono float32 microphone stream.

        320 samples correspond to approximately 20 ms at 16 kHz.
        """

        app_logger.info("Opening Microphone...")

        stream = sd.InputStream(
            samplerate=self.sample_rate,
            blocksize=self.blocksize,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            latency="low",
            callback=callback,
        )

        app_logger.success("Microphone Ready")

        return stream

    @staticmethod
    def list_devices():
        return sd.query_devices()