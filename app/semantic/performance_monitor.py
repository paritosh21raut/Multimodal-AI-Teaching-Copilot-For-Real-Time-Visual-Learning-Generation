"""
Performance Monitor

Tracks processing times, memory usage, and system health.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any, Tuple
import time
import threading
from collections import deque
from datetime import datetime


class PerformanceMonitor:
    """Monitors semantic intelligence performance"""
    
    def __init__(self, window_size: int = 100):
        self._lock = threading.RLock()
        
        # Timing history
        self._processing_times: deque = deque(maxlen=window_size)
        self._llm_latencies: deque = deque(maxlen=window_size)
        self._extraction_times: deque = deque(maxlen=window_size)
        
        # Statistics
        self._total_frames = 0
        self._total_llm_calls = 0
        self._total_errors = 0
        self._start_time = time.time()
        
        # Current operation tracking
        self._current_operation: Optional[str] = None
        self._operation_start: Optional[float] = None
    
    def start_operation(self, operation: str) -> None:
        """Start timing an operation"""
        with self._lock:
            self._current_operation = operation
            self._operation_start = time.time()
    
    def end_operation(self) -> Optional[float]:
        """End timing and return elapsed time"""
        with self._lock:
            if self._operation_start is None:
                return None
            
            elapsed = time.time() - self._operation_start
            self._current_operation = None
            self._operation_start = None
            
            return elapsed
    
    def record_frame_processing(self, processing_time: float) -> None:
        """Record frame processing time"""
        with self._lock:
            self._processing_times.append(processing_time)
            self._total_frames += 1
    
    def record_llm_call(self, latency: float) -> None:
        """Record LLM call latency"""
        with self._lock:
            self._llm_latencies.append(latency)
            self._total_llm_calls += 1
    
    def record_extraction(self, extraction_time: float) -> None:
        """Record extraction time"""
        with self._lock:
            self._extraction_times.append(extraction_time)
    
    def record_error(self) -> None:
        """Record an error occurrence"""
        with self._lock:
            self._total_errors += 1
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get performance statistics"""
        with self._lock:
            uptime = time.time() - self._start_time
            
            return {
                "uptime_seconds": uptime,
                "total_frames": self._total_frames,
                "total_llm_calls": self._total_llm_calls,
                "total_errors": self._total_errors,
                "frames_per_second": self._total_frames / uptime if uptime > 0 else 0,
                "average_processing_time_ms": self._average(self._processing_times) * 1000,
                "p95_processing_time_ms": self._percentile(self._processing_times, 95) * 1000,
                "p99_processing_time_ms": self._percentile(self._processing_times, 99) * 1000,
                "average_llm_latency_ms": self._average(self._llm_latencies) * 1000,
                "average_extraction_time_ms": self._average(self._extraction_times) * 1000
            }
    
    def get_health_report(self) -> Dict[str, Any]:
        """Get health report"""
        stats = self.get_statistics()
        
        health = {
            "status": "healthy",
            "issues": []
        }
        
        # Check processing time
        avg_ms = stats["average_processing_time_ms"]
        if avg_ms > 3000:
            health["status"] = "degraded"
            health["issues"].append(f"High average processing time: {avg_ms:.0f}ms")
        
        # Check error rate
        if stats["total_frames"] > 0:
            error_rate = stats["total_errors"] / stats["total_frames"]
            if error_rate > 0.1:
                health["status"] = "degraded"
                health["issues"].append(f"High error rate: {error_rate:.1%}")
        
        # Check LLM success rate
        if stats["total_llm_calls"] > 0:
            llm_latency = stats["average_llm_latency_ms"]
            if llm_latency > 5000:
                health["status"] = "degraded"
                health["issues"].append(f"High LLM latency: {llm_latency:.0f}ms")
        
        if not health["issues"]:
            health["status"] = "healthy"
        
        return health
    
    @staticmethod
    def _average(values: deque) -> float:
        """Calculate average"""
        if not values:
            return 0.0
        return sum(values) / len(values)
    
    @staticmethod
    def _percentile(values: deque, percentile: float) -> float:
        """Calculate percentile"""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * percentile / 100)
        index = min(index, len(sorted_values) - 1)
        return sorted_values[index] 