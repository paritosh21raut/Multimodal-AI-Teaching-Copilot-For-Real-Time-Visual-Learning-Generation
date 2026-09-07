"""
Voice Activity Detector (Silero VAD)

Production-grade VAD using Silero neural model.
Replaces energy-based detection for robust speech detection
in noisy environments.

Key features:
- Neural network based (works in noisy rooms)
- 30ms chunk processing
- Stateful (maintains hidden states for continuity)
- Low CPU overhead (<1% on modern CPU)
- Handles HVAC noise, keyboard typing, room echo
"""

from __future__ import annotations

import numpy as np
import torch

from app.utils.logger import app_logger


class VoiceDetector:
    """
    Silero VAD wrapper for lecture speech detection.
    
    Falls back to energy-based detection if Silero model
    cannot be loaded (offline, missing dependency, etc.)
    """

    def __init__(
        self,
        speech_threshold: float = 0.5,
        silence_threshold: float = 0.35,
        hangover_samples: int = 6400,  # 400ms at 16kHz
        pre_roll_samples: int = 4800,   # 300ms at 16kHz
    ):
        self.speech_threshold = float(speech_threshold)
        self.silence_threshold = float(silence_threshold)
        self.hangover_samples = int(hangover_samples)
        self.pre_roll_samples = int(pre_roll_samples)
        
        # State
        self._speech_state = False
        self._silence_count = 0
        self._speech_count = 0
        
        # Energy fallback parameters
        self._energy_speech_threshold = 0.008
        self._energy_silence_threshold = 0.005
        self._noise_floor = 0.003
        self._noise_adaptation_rate = 0.05
        
        # Load Silero VAD
        self._load_model()
    
    def _load_model(self):
        """Load Silero VAD model with fallback"""
        try:
            app_logger.info("Loading Silero VAD...")
            
            self.model, self.utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
            )
            
            self.model.eval()
            self.reset_states()
            
            app_logger.success("Silero VAD Ready")
        
        except Exception as error:
            app_logger.warning(
                f"Silero VAD failed to load: {error}. "
                "Falling back to energy-based VAD."
            )
            self.model = None
            self.utils = None
    
    def reset_states(self):
        """Reset VAD hidden states"""
        if self.model is not None and self.utils is not None:
            self._state = self.utils.init_state()
    
    def is_speech(self, audio) -> bool:
        """
        Detect speech in audio chunk.
        
        Args:
            audio: numpy array of float32 samples
            
        Returns:
            bool: True if speech detected
        """
        if self.model is None:
            return self._energy_fallback(audio)
        
        audio_array = np.asarray(audio, dtype=np.float32).reshape(-1)
        
        if audio_array.size < 512:
            return self._speech_state
        
        # Process in 512-sample windows (32ms at 16kHz)
        speech_probabilities = []
        
        for i in range(0, len(audio_array) - 511, 512):
            chunk = audio_array[i:i + 512]
            
            if chunk.size < 512:
                break
            
            with torch.no_grad():
                speech_prob = self.model(
                    torch.from_numpy(chunk),
                    16000
                ).item()
                
                speech_probabilities.append(speech_prob)
        
        if not speech_probabilities:
            return self._speech_state
        
        # Average probability
        avg_prob = sum(speech_probabilities) / len(speech_probabilities)
        
        # Apply hysteresis
        if self._speech_state:
            # Currently in speech - need lower threshold to exit
            is_speech = avg_prob >= self.silence_threshold
        else:
            # Currently in silence - need higher threshold to enter
            is_speech = avg_prob >= self.speech_threshold
        
        # Update state
        if is_speech:
            self._silence_count = 0
            self._speech_count += len(audio_array)
        else:
            self._silence_count += len(audio_array)
        
        self._speech_state = is_speech
        
        return is_speech
    
    def _energy_fallback(self, audio) -> bool:
        """Fallback to energy-based detection if Silero unavailable"""
        audio_array = np.asarray(audio, dtype=np.float32).reshape(-1)
        
        if audio_array.size == 0:
            return self._speech_state
        
        energy = float(np.mean(np.abs(audio_array)))
        
        # Adaptive thresholds
        if self._speech_state:
            threshold = max(
                self._energy_silence_threshold,
                self._noise_floor * 1.5
            )
        else:
            threshold = max(
                self._energy_speech_threshold,
                self._noise_floor * 2.5
            )
        
        is_speech = energy >= threshold
        
        # Adapt noise floor during silence
        if not is_speech:
            alpha = self._noise_adaptation_rate
            self._noise_floor = (
                (1.0 - alpha) * self._noise_floor
                + alpha * energy
            )
            self._noise_floor = max(1e-5, self._noise_floor)
        
        # Update state
        if is_speech:
            self._silence_count = 0
            self._speech_count += len(audio_array)
        else:
            self._silence_count += len(audio_array)
        
        self._speech_state = is_speech
        
        return is_speech
    
    def get_speech_probability(self, audio) -> float:
        """Get raw speech probability (for confidence scoring)"""
        if self.model is None:
            return 1.0 if self.is_speech(audio) else 0.0
        
        audio_array = np.asarray(audio, dtype=np.float32).reshape(-1)
        
        if audio_array.size < 512:
            return 0.0
        
        with torch.no_grad():
            speech_prob = self.model(
                torch.from_numpy(audio_array[:512]),
                16000
            ).item()
        
        return speech_prob
    
    @property
    def speech_state(self) -> bool:
        return self._speech_state
    
    @property
    def using_silero(self) -> bool:
        return self.model is not None
    
    def reset(self):
        self._speech_state = False
        self._silence_count = 0
        self._speech_count = 0
        self._noise_floor = 0.003
        self.reset_states()
    
    def get_state(self) -> dict:
        return {
            "speech": self._speech_state,
            "silence_count": self._silence_count,
            "speech_count": self._speech_count,
            "model": "silero_vad" if self.model else "energy_fallback",
            "noise_floor": self._noise_floor if self.model is None else None,
        }