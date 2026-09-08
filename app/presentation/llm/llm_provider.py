"""
LLM Provider Interface

Abstract base class for all LLM providers.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any


class LLMProvider(ABC):
    """Abstract LLM provider interface"""
    
    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        schema: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Generate structured output.
        
        Args:
            prompt: Input prompt
            schema: Expected output schema (JSON schema)
            
        Returns:
            Parsed dict or None on failure
        """
        pass
    
    @abstractmethod
    def health_check(self) -> bool:
        """Check if provider is available"""
        pass
    
    @abstractmethod
    def supports_json_schema(self) -> bool:
        """Whether provider supports native JSON schema"""
        pass
    
    @abstractmethod
    def estimated_latency_ms(self) -> int:
        """Estimated latency in milliseconds"""
        pass
    
    @abstractmethod
    def provider_name(self) -> str:
        """Provider name"""
        pass
    
    @abstractmethod
    def model_name(self) -> str:
        """Model name"""
        pass
    