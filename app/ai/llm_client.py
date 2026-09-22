from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class LLMError(Exception):
    """Base exception for LLM layer failures."""


class LLMConfigurationError(LLMError):
    """Raised when the LLM client is not properly configured."""


class LLMRequestError(LLMError):
    """Raised when the provider request fails after retries."""


class LLMResponseError(LLMError):
    """Raised when the provider response cannot be parsed/validated."""


class LLMClient(ABC):
    """
    Provider-independent LLM interface.

    ContentGenerator depends only on this interface.
    """

    @property
    @abstractmethod
    def provider(self) -> str:
        ...

    @property
    @abstractmethod
    def model(self) -> str:
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """Return raw text completion."""

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        *,
        system: Optional[str] = None,
        schema: Optional[Dict[str, Any]] = None,
        schema_name: str = "response",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Return a JSON object validated against the supplied schema.
        Raises LLMResponseError when a safe result cannot be produced.
        """

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if a trivial successful request can be made."""