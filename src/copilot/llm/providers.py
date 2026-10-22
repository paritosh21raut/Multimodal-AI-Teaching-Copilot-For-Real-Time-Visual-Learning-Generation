"""OpenAI-compatible chat-completions client (Groq and Ollama expose /v1/chat/completions)."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

import httpx


class LLMError(Exception):
    """Base for provider failures. `retryable` = worth one more attempt on the same entry."""

    retryable = False


class Transient(LLMError):  # timeout, 5xx, dropped connection
    retryable = True


class RateLimited(LLMError):
    def __init__(self, msg: str, retry_after: Optional[float], daily: bool = False,
                 reset_at: Optional[float] = None, used: Optional[int] = None, limit: Optional[int] = None) -> None:
        super().__init__(msg)
        self.retry_after = retry_after
        self.daily = daily          # the per-day quota is spent (not a per-minute burst)
        self.reset_at = reset_at    # wall-clock time the daily quota frees up, when known
        self.used, self.limit = used, limit  # server's daily token count / limit (Groq TPD body)


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
    tpd: int = 0  # free-tier tokens per day (0 = not tracked); shown at startup, a spent entry is skipped
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


_DURATION = re.compile(r"(?:(\d+)h)?(?:(\d+)m(?!s))?(?:([\d.]+)s)?")
# Groq: "... on tokens per day (TPD): Limit 200000, Used 199616, Requested 2345. Please try again in 7m12.48s."
_GROQ_DAILY = re.compile(r"tokens per day \(TPD\): Limit (\d+), Used (\d+)", re.IGNORECASE)
_TRY_AGAIN = re.compile(r"try again in ((?:\d+h)?(?:\d+m(?!s))?(?:[\d.]+s)?)", re.IGNORECASE)


def _duration_s(text: str) -> Optional[float]:
    m = _DURATION.fullmatch(text)
    if not m or not any(m.groups()):
        return None
    h, mi, s = m.groups()
    return int(h or 0) * 3600 + int(mi or 0) * 60 + float(s or 0)


def rate_limited(resp: httpx.Response) -> RateLimited:
    """429 -> RateLimited; a Groq tokens-per-day body is recognised as a spent daily quota."""
    body = resp.text
    retry = _retry_after(resp)
    m = _GROQ_DAILY.search(body)
    if m:
        again = _TRY_AGAIN.search(body)
        wait = (_duration_s(again.group(1)) if again else None) or retry
        return RateLimited(f"429 daily token quota: used {m.group(2)}/{m.group(1)}", wait, daily=True,
                           reset_at=time.time() + wait if wait else None, used=int(m.group(2)), limit=int(m.group(1)))
    return RateLimited(f"429 {body[:200]}", retry)


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
                       temperature: float = 0.2, on_text: Optional[Callable[[str], None]] = None) -> LLMResponse:
        """One chat completion. on_text (F-015): stream it (SSE, plain text, no JSON mode) and pass each piece of
        text as it arrives; the whole text and the usage are still returned at the end."""
        body: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": min(max_tokens, self.cfg.max_output_tokens or max_tokens),
            **self.cfg.extra,
        }
        if on_text is not None:
            body["stream"] = True
        elif self.cfg.json_mode:
            body["response_format"] = {"type": "json_object"}
        headers = {"Authorization": f"Bearer {self._key}"} if self._key else {}
        url = self.cfg.base_url.rstrip("/") + "/chat/completions"
        t0 = time.perf_counter()
        to = httpx.Timeout(timeout, connect=min(timeout, 2.0))
        try:
            if on_text is not None:
                async with self._client.stream("POST", url, json=body, headers=headers, timeout=to) as resp:
                    if resp.status_code >= 400:
                        await resp.aread()
                    _check_status(resp)
                    return await _read_stream(resp, on_text, t0)
            resp = await self._client.post(url, json=body, headers=headers, timeout=to)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            # nothing listening (on Windows a refused localhost connect can surface as ConnectTimeout): cool down
            raise Unavailable(f"connect failed: {type(e).__name__}") from e
        except httpx.TimeoutException as e:
            raise Transient(f"timeout after {timeout:.1f}s ({type(e).__name__})") from e
        except httpx.HTTPError as e:  # TransportError, DecodingError, TooManyRedirects, ...
            raise Transient(f"http error: {type(e).__name__}") from e
        latency = (time.perf_counter() - t0) * 1000
        _check_status(resp)
        try:
            data = resp.json()
        except ValueError as e:
            raise InvalidOutput(f"response body is not JSON: {e}") from e
        if not isinstance(data, dict):
            raise InvalidOutput("response body is not an object")
        if data.get("error") and not data.get("choices"):  # some gateways report upstream failures as 200 + error
            raise Transient(f"error in body: {str(data['error'])[:200]}")
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise InvalidOutput(f"malformed response body: {type(e).__name__} {e}") from e
        if isinstance(content, list):  # content parts: [{"type": "text", "text": ...}]
            content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
        if not isinstance(content, str) or not content.strip():
            raise InvalidOutput("empty content")
        usage = data.get("usage") if isinstance(data.get("usage"), dict) else {}
        return _response(content, usage, resp, latency)


def _check_status(resp: httpx.Response) -> None:
    if resp.status_code == 429:
        raise rate_limited(resp)
    if resp.status_code >= 500:
        raise Transient(f"{resp.status_code} {resp.text[:200]}")
    if resp.status_code >= 400:
        if "json_validate_failed" in resp.text:
            raise InvalidOutput(f"{resp.status_code} json_validate_failed")
        raise Rejected(f"{resp.status_code} {resp.text[:300]}")


def _response(text: str, usage: dict, resp: httpx.Response, latency: float) -> LLMResponse:
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


async def _read_stream(resp: httpx.Response, on_text: Callable[[str], None], t0: float) -> LLMResponse:
    """Server-sent events of an OpenAI-compatible stream: `data: {chunk}` lines, `data: [DONE]` at the end. The usage
    comes in the last chunk (`usage`, or Groq's `x_groq.usage`). An empty answer is valid here (a streamed caller
    may ask for "nothing to change" as no output, F-015); one cut off by the token limit is not."""
    parts: list[str] = []
    usage: dict = {}
    finish = ""
    async for line in resp.aiter_lines():
        if not line.startswith("data:"):
            continue
        data = line[5:].strip()
        if data == "[DONE]":
            break
        try:
            chunk = json.loads(data)
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        if chunk.get("error") and not chunk.get("choices"):
            raise Transient(f"error in stream: {str(chunk['error'])[:200]}")
        u = chunk.get("usage") or (chunk.get("x_groq") or {}).get("usage")
        if isinstance(u, dict):
            usage = u
        for ch in chunk.get("choices") or []:
            finish = (ch or {}).get("finish_reason") or finish
            piece = ((ch or {}).get("delta") or {}).get("content")
            if isinstance(piece, str) and piece:
                parts.append(piece)
                on_text(piece)
    text = "".join(parts)
    if finish == "length" and not text.strip():
        raise InvalidOutput("the token limit ended the stream before any text")
    return _response(text, usage, resp, (time.perf_counter() - t0) * 1000)
