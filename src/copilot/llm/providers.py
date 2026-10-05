"""OpenAI-compatible chat-completions client (Groq, OpenRouter and Ollama all expose /v1/chat/completions)."""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx


class LLMError(Exception):
    """Base for provider failures. `retryable` = worth one more attempt on the same entry."""

    retryable = False


class Transient(LLMError):  # timeout, 5xx, dropped connection
    retryable = True


class RateLimited(LLMError):
    def __init__(self, msg: str, retry_after: Optional[float]) -> None:
        super().__init__(msg)
        self.retry_after = retry_after


class Unavailable(LLMError):  # cannot connect (e.g. Ollama not installed / offline)
    pass


class Rejected(LLMError):  # 4xx other than 429: auth, bad model, context too long
    pass


class InvalidOutput(LLMError):  # the provider could not produce valid JSON (e.g. Groq json_validate_failed)
    pass


@dataclass
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key_env: str = ""
    rpm: float = 30
    tpm: float = 8000
    json_mode: bool = True
    max_output_tokens: Optional[int] = None  # per-model cap (e.g. Groq qwen: 1000 output tokens/min)
    extra: dict[str, Any] = field(default_factory=dict)  # provider-specific body params


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: float = 0.0
    remaining_tokens: Optional[float] = None  # from x-ratelimit-remaining-tokens


def _retry_after(resp: httpx.Response) -> Optional[float]:
    raw = resp.headers.get("retry-after")
    try:
        return float(raw) if raw is not None else None
    except ValueError:
        return None


def _int(v: Any) -> int:
    try:
        return int(v or 0)
    except (TypeError, ValueError):
        return 0


class OpenAICompatProvider:
    def __init__(self, cfg: ProviderConfig, api_key: Optional[str], client: httpx.AsyncClient) -> None:
        self.cfg = cfg
        self._key = api_key
        self._client = client

    @property
    def name(self) -> str:
        return self.cfg.name

    async def complete(self, messages: list[dict[str, str]], *, max_tokens: int, timeout: float,
                       temperature: float = 0.2) -> LLMResponse:
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(max_tokens, self.cfg.max_output_tokens or max_tokens),
            **self.cfg.extra,
        }
        if self.cfg.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        t0 = time.perf_counter()
        try:
            resp = await self._client.post(
                url, json=body, headers=headers,
                timeout=httpx.Timeout(timeout, connect=min(timeout, 2.0)),
            )
        except httpx.ConnectError as e:
            raise Unavailable(f"connect failed: {type(e).__name__}") from e
        except httpx.TimeoutException as e:
            raise Transient(f"timeout after {timeout:.1f}s ({type(e).__name__})") from e
        except httpx.HTTPError as e:  # TransportError, DecodingError, TooManyRedirects, ...
            raise Transient(f"http error: {type(e).__name__}") from e
        latency = (time.perf_counter() - t0) * 1000

        if resp.status_code == 429:
            raise RateLimited(f"429 {resp.text[:200]}", _retry_after(resp))
        if resp.status_code >= 500:
            raise Transient(f"{resp.status_code} {resp.text[:200]}")
        if resp.status_code >= 400:
            if "json_validate_failed" in resp.text:
                raise InvalidOutput(f"{resp.status_code} json_validate_failed")
            raise Rejected(f"{resp.status_code} {resp.text[:300]}")
        try:
            data = resp.json()
        except ValueError as e:
            raise InvalidOutput(f"response body is not JSON: {e}") from e
        if not isinstance(data, dict):
            raise InvalidOutput("response body is not an object")
        if data.get("error") and not data.get("choices"):  # OpenRouter reports upstream failures as 200 + error
            raise Transient(f"error in body: {str(data['error'])[:200]}")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise InvalidOutput(f"malformed response body: {type(e).__name__} {e}") from e
        if isinstance(content, list):  # content parts: [{"type": "text", "text": ...}]
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not isinstance(content, str) or not content.strip():
            raise InvalidOutput("empty content")
        text = content
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        remaining = resp.headers.get("x-ratelimit-remaining-tokens")
        try:
            remaining_f = float(remaining) if remaining is not None else None
        except ValueError:
            remaining_f = None
        return LLMResponse(
            text=text,
            prompt_tokens=_int(usage.get("prompt_tokens")),
            completion_tokens=_int(usage.get("completion_tokens")),
            latency_ms=latency,
            remaining_tokens=remaining_f,
        )
