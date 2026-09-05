from __future__ import annotations

import numpy as np


class VoiceDetector:
    """
    Lightweight adaptive energy-based voice detector.

    It intentionally remains simple because the known-good system used
    energy detection successfully in the target environment.

    Improvements:
        - adaptive noise floor
        - separate speech/noise thresholds
        - hysteresis
        - finite-input protection
        - configurable startup behavior
    """

    def __init__(
        self,
        initial_noise_floor: float = 0.003,
        minimum_threshold: float = 0.006,
        speech_multiplier: float = 2.8,
        silence_multiplier: float = 2.0,
        noise_adaptation_rate: float = 0.05,
    ):
        self.initial_noise_floor = float(initial_noise_floor)
        self.noise_floor = float(initial_noise_floor)

        self.minimum_threshold = float(minimum_threshold)

        self.speech_multiplier = float(speech_multiplier)
        self.silence_multiplier = float(silence_multiplier)

        self.noise_adaptation_rate = float(
            noise_adaptation_rate
        )

        self._speech_state = False

    @staticmethod
    def _energy(audio) -> float:

        array = np.asarray(
            audio,
            dtype=np.float32,
        )

        if array.size == 0:
            return 0.0

        if array.ndim > 1:
            array = np.mean(
                array,
                axis=1,
                dtype=np.float32,
            )

        array = array.reshape(-1)

        if not np.all(np.isfinite(array)):
            array = np.nan_to_num(
                array,
                nan=0.0,
                posinf=0.0,
                neginf=0.0,
            )

        return float(
            np.mean(
                np.abs(array),
                dtype=np.float32,
            )
        )

    def is_speech(self, audio) -> bool:

        energy = self._energy(audio)

        speech_threshold = max(
            self.minimum_threshold,
            self.noise_floor * self.speech_multiplier,
        )

        silence_threshold = max(
            self.minimum_threshold * 0.75,
            self.noise_floor * self.silence_multiplier,
        )

        if self._speech_state:

            is_speech = energy >= silence_threshold

        else:

            is_speech = energy >= speech_threshold

        # Adapt the noise floor only while the current state is silence.
        # This prevents normal speech from becoming the new noise baseline.
        if not is_speech:

            alpha = self.noise_adaptation_rate

            self.noise_floor = (
                (1.0 - alpha) * self.noise_floor
                + alpha * energy
            )

            self.noise_floor = max(
                1e-5,
                self.noise_floor,
            )

        self._speech_state = is_speech

        return is_speech

    @property
    def noise_floor(self) -> float:
        return self._noise_floor

    @noise_floor.setter
    def noise_floor(self, value: float):
        self._noise_floor = max(
            1e-5,
            float(value),
        )

    @property
    def speech_state(self) -> bool:
        return self._speech_state

    def reset(self):
        self.noise_floor = self.initial_noise_floor
        self._speech_state = False

    def get_state(self) -> dict:
        return {
            "noise_floor": self.noise_floor,
            "speech": self._speech_state,
        }