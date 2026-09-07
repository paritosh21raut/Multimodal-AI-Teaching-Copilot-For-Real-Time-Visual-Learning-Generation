"""
Audio Quality Monitor

Monitors audio input quality and detects common microphone issues:
- Clipping (signal too loud)
- Low volume (signal too quiet)
- DC offset (hardware issue)
- Silence ratio (no speech)

Provides real-time quality metrics for dashboard and downstream systems.
"""

from __future__ import annotations

from collections import deque
from typing import Dict, Any

import numpy as np

from app.utils.logger import app_logger


class AudioQualityMonitor:
    """
    Real-time audio quality analyzer.
    
    Tracks:
    - RMS energy (dB)
    - Peak amplitude
    - Clipping events
    - DC offset
    - Silence ratio
    - Overall quality assessment
    """

    def __init__(
        self,
        history_size: int = 100,
        clip_threshold: float = 0.98,
        low_rms_db: float = -40.0,
        high_rms_db: float = -5.0,
        dc_offset_threshold: float = 0.01,
    ):
        self.history_size = int(history_size)
        self.clip_threshold = float(clip_threshold)
        self.low_rms_db = float(low_rms_db)
        self.high_rms_db = float(high_rms_db)
        self.dc_offset_threshold = float(dc_offset_threshold)
        
        # History buffers
        self._rms_history = deque(maxlen=history_size)
        self._peak_history = deque(maxlen=history_size)
        self._dc_history = deque(maxlen=history_size)
        
        # Statistics
        self._total_chunks = 0
        self._clipping_count = 0
        self._low_volume_count = 0
        self._high_volume_count = 0
        self._dc_offset_count = 0
        self._silence_count = 0
        
        # Current state
        self._current_quality = "unknown"
    
    def analyze(self, audio_chunk) -> Dict[str, Any]:
        """
        Analyze an audio chunk and return quality metrics.
        
        Args:
            audio_chunk: numpy array of float32 samples
            
        Returns:
            Dict with quality metrics
        """
        if audio_chunk is None:
            return self._empty_metrics()
        
        audio = np.asarray(audio_chunk, dtype=np.float32).reshape(-1)
        
        if audio.size == 0:
            return self._empty_metrics()
        
        self._total_chunks += 1
        
        # Calculate metrics
        rms = float(np.sqrt(np.mean(audio ** 2))) if audio.size > 0 else 0.0
        peak = float(np.max(np.abs(audio))) if audio.size > 0 else 0.0
        dc_offset = float(np.mean(audio)) if audio.size > 0 else 0.0
        
        # Convert RMS to dB
        rms_db = 20 * np.log10(rms) if rms > 1e-10 else -60.0
        
        # Check clipping
        is_clipped = peak >= self.clip_threshold
        if is_clipped:
            self._clipping_count += 1
        
        # Check volume levels
        is_low_volume = rms_db < self.low_rms_db and rms_db > -60.0
        is_high_volume = rms_db > self.high_rms_db
        
        if is_low_volume:
            self._low_volume_count += 1
        if is_high_volume:
            self._high_volume_count += 1
        
        # Check DC offset
        has_dc_offset = abs(dc_offset) > self.dc_offset_threshold
        if has_dc_offset:
            self._dc_offset_count += 1
        
        # Check silence
        is_silence = rms_db < -50.0
        if is_silence:
            self._silence_count += 1
        
        # Update history
        self._rms_history.append(rms_db)
        self._peak_history.append(peak)
        self._dc_history.append(dc_offset)
        
        # Determine overall quality
        quality = self._assess_quality(
            rms_db,
            is_clipped,
            is_low_volume,
            is_high_volume,
            has_dc_offset,
        )
        
        self._current_quality = quality
        
        return {
            "rms_db": round(rms_db, 2),
            "peak": round(peak, 4),
            "dc_offset": round(dc_offset, 6),
            "clipped": is_clipped,
            "low_volume": is_low_volume,
            "high_volume": is_high_volume,
            "has_dc_offset": has_dc_offset,
            "is_silence": is_silence,
            "quality": quality,
        }
    
    def _assess_quality(
        self,
        rms_db: float,
        is_clipped: bool,
        is_low_volume: bool,
        is_high_volume: bool,
        has_dc_offset: bool,
    ) -> str:
        """Determine overall quality level"""
        if is_clipped:
            return "clipping"
        elif is_low_volume:
            return "too_quiet"
        elif is_high_volume:
            return "too_loud"
        elif has_dc_offset:
            return "dc_offset"
        elif rms_db < -50.0:
            return "silence"
        elif -30.0 <= rms_db <= -10.0:
            return "good"
        elif -40.0 <= rms_db < -30.0:
            return "acceptable"
        else:
            return "marginal"
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get cumulative quality statistics"""
        total = max(1, self._total_chunks)
        
        avg_rms = (
            sum(self._rms_history) / len(self._rms_history)
            if self._rms_history else -60.0
        )
        
        avg_peak = (
            sum(self._peak_history) / len(self._peak_history)
            if self._peak_history else 0.0
        )
        
        avg_dc = (
            sum(self._dc_history) / len(self._dc_history)
            if self._dc_history else 0.0
        )
        
        return {
            "total_chunks": self._total_chunks,
            "clipping_ratio": round(self._clipping_count / total, 4),
            "low_volume_ratio": round(self._low_volume_count / total, 4),
            "high_volume_ratio": round(self._high_volume_count / total, 4),
            "dc_offset_ratio": round(self._dc_offset_count / total, 4),
            "silence_ratio": round(self._silence_count / total, 4),
            "avg_rms_db": round(avg_rms, 2),
            "avg_peak": round(avg_peak, 4),
            "avg_dc_offset": round(avg_dc, 6),
            "current_quality": self._current_quality,
        }
    
    def _empty_metrics(self) -> Dict[str, Any]:
        """Return empty metrics for invalid input"""
        return {
            "rms_db": -60.0,
            "peak": 0.0,
            "dc_offset": 0.0,
            "clipped": False,
            "low_volume": False,
            "high_volume": False,
            "has_dc_offset": False,
            "is_silence": True,
            "quality": "silence",
        }
    
    def reset(self) -> None:
        """Reset all statistics"""
        self._rms_history.clear()
        self._peak_history.clear()
        self._dc_history.clear()
        self._total_chunks = 0
        self._clipping_count = 0
        self._low_volume_count = 0
        self._high_volume_count = 0
        self._dc_offset_count = 0
        self._silence_count = 0
        self._current_quality = "unknown"