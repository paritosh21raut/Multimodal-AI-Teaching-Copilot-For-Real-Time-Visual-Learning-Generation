"""
Voice Activity Detector (Silero VAD - FIXED for 320-sample chunks)

Buffers audio to 512 samples before processing with Silero VAD.
"""

from __future__ import annotations

import numpy as np
import torch

from app.utils.logger import app_logger


class VoiceDetector:
    """Silero VAD wrapper with 512-sample buffering"""

    def __init__(
        self,
        speech_threshold: float = 0.5,
        silence_threshold: float = 0.35,
    ):
        self.speech_threshold = float(speech_threshold)
        self.silence_threshold = float(silence_threshold)
        
        self._speech_state = False
        self._silence_count = 0
        self._speech_count = 0
        
        # Audio buffer for accumulating to 512 samples
        self._audio_buffer = np.zeros(0, dtype=np.float32)
        self._required_samples = 512  # Silero VAD expects 512 samples
        
        # Energy fallback
        self._energy_speech_threshold = 0.008
        self._energy_silence_threshold = 0.005
        self._noise_floor = 0.003
        self._noise_adaptation_rate = 0.05
        
        self._load_model()
    
    def _load_model(self):
        """Load Silero VAD"""
        try:
            app_logger.info("Loading Silero VAD...")
            
            model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
            )
            
            self.model = model
            
            # Initialize state tensors
            # Silero VAD uses LSTM with 2 layers, 64 hidden units
            self._state_h = torch.zeros(2, 1, 64)
            self._state_c = torch.zeros(2, 1, 64)
            
            self.model.eval()
            
            app_logger.success("Silero VAD Ready")
        
        except Exception as error:
            app_logger.warning(
                f"Silero VAD failed: {error}. Using energy fallback."
            )
            self.model = None
            self._state_h = None
            self._state_c = None
    
    def reset_states(self):
        """Reset VAD hidden states"""
        if self.model is not None:
            self._state_h = torch.zeros(2, 1, 64)
            self._state_c = torch.zeros(2, 1, 64)
        self._audio_buffer = np.zeros(0, dtype=np.float32)
    
    def is_speech(self, audio) -> bool:
        """Detect speech with proper buffering"""
        if self.model is None:
            return self._energy_fallback(audio)
        
        # Flatten and convert to float32
        audio_array = np.asarray(audio, dtype=np.float32).flatten()
        
        if audio_array.size == 0:
            return self._speech_state
        
        # Append to buffer
        self._audio_buffer = np.concatenate([self._audio_buffer, audio_array])
        
        # If we don't have enough samples yet, use energy fallback
        if len(self._audio_buffer) < self._required_samples:
            # Quick energy check while buffering
            energy = float(np.mean(np.abs(audio_array)))
            return self._speech_state or energy > 0.01
        
        # Process complete 512-sample windows
        speech_probabilities = []
        
        while len(self._audio_buffer) >= self._required_samples:
            # Take first 512 samples
            chunk = self._audio_buffer[:self._required_samples]
            self._audio_buffer = self._audio_buffer[self._required_samples:]
            
            try:
                with torch.no_grad():
                    # Silero VAD expects: (batch=1, samples=512)
                    input_tensor = torch.from_numpy(chunk).unsqueeze(0)
                    
                    # Try the standard calling convention
                    result = self.model(
                        input_tensor,
                        self._state_h,
                        self._state_c,
                        16000
                    )
                    
                    if isinstance(result, tuple) and len(result) >= 3:
                        speech_prob = float(result[0].item())
                        self._state_h = result[1]
                        self._state_c = result[2]
                    elif isinstance(result, tuple):
                        speech_prob = float(result[0].item())
                    else:
                        speech_prob = float(result.item())
                    
                    speech_probabilities.append(speech_prob)
            
            except Exception:
                # On error, use energy for this chunk
                energy = float(np.mean(np.abs(chunk)))
                speech_probabilities.append(1.0 if energy > 0.01 else 0.0)
        
        if not speech_probabilities:
            return self._speech_state
        
        avg_prob = sum(speech_probabilities) / len(speech_probabilities)
        
        # Hysteresis
        if self._speech_state:
            is_speech = avg_prob >= self.silence_threshold
        else:
            is_speech = avg_prob >= self.speech_threshold
        
        if is_speech:
            self._silence_count = 0
            self._speech_count += len(audio_array)
        else:
            self._silence_count += len(audio_array)
        
        self._speech_state = is_speech
        
        return is_speech
    
    def _energy_fallback(self, audio) -> bool:
        """Energy-based fallback detection"""
        audio_array = np.asarray(audio, dtype=np.float32).flatten()
        
        if audio_array.size == 0:
            return self._speech_state
        
        energy = float(np.mean(np.abs(audio_array)))
        
        if self._speech_state:
            threshold = max(self._energy_silence_threshold, self._noise_floor * 1.5)
        else:
            threshold = max(self._energy_speech_threshold, self._noise_floor * 2.5)
        
        is_speech = energy >= threshold
        
        if not is_speech:
            alpha = self._noise_adaptation_rate
            self._noise_floor = (1.0 - alpha) * self._noise_floor + alpha * energy
            self._noise_floor = max(1e-5, self._noise_floor)
        
        if is_speech:
            self._silence_count = 0
            self._speech_count += len(audio_array)
        else:
            self._silence_count += len(audio_array)
        
        self._speech_state = is_speech
        
        return is_speech
    
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
            "buffer_size": len(self._audio_buffer),
        }