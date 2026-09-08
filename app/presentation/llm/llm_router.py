"""
LLM Router

Routes LLM requests to best available provider.
Priority: Groq (fast) → Deterministic (always works)
"""

from __future__ import annotations

from typing import Dict, List, Optional, Any
import threading

from .llm_provider import LLMProvider
from .groq_provider import GroqProvider
from .deterministic_provider import DeterministicProvider


class LLMRouter:
    """
    Routes LLM requests to providers.
    
    Priority:
    1. Groq (if available and fast)
    2. Deterministic (always works)
    """
    
    def __init__(self):
        self._lock = threading.RLock()
        
        # Initialize providers
        self._providers: List[LLMProvider] = [
            GroqProvider(),
            DeterministicProvider(),
        ]
        
        # Track failures
        self._provider_failures: Dict[str, int] = {}
        self._max_failures = 3
    
    def generate_structured(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate structured output from best available provider.
        
        Returns:
            Dict (never None - deterministic always succeeds)
        """
        with self._lock:
            for provider in self._providers:
                if not provider.health_check():
                    continue
                
                # Check failure count
                failures = self._provider_failures.get(
                    provider.provider_name(), 0
                )
                if failures >= self._max_failures:
                    continue
                
                result = provider.generate_structured(prompt, schema)
                
                if result is not None:
                    # Reset failures on success
                    self._provider_failures[provider.provider_name()] = 0
                    return result
                else:
                    # Track failure
                    self._provider_failures[provider.provider_name()] = (
                        self._provider_failures.get(provider.provider_name(), 0) + 1
                    )
            
            # Fallback: use deterministic directly
            deterministic = DeterministicProvider()
            return deterministic.generate_structured(prompt, schema) or {
                "title": "Lecture",
                "bullets": [],
                "content_type": "explanation",
                "visual_type": "none",
            }
    
    def get_provider_status(self) -> Dict[str, Any]:
        """Get status of all providers"""
        status = {}
        
        for provider in self._providers:
            status[provider.provider_name()] = {
                "healthy": provider.health_check(),
                "model": provider.model_name(),
                "latency_ms": provider.estimated_latency_ms(),
                "failures": self._provider_failures.get(
                    provider.provider_name(), 0
                ),
            }
        
        return status
    
    def reset_failures(self):
        """Reset failure counts"""
        with self._lock:
            self._provider_failures.clear()