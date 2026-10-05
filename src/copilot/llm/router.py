"""Ordered LLM fall-through: Groq → OpenRouter → Ollama (ADR-0001). Model ids live in config."""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional

import httpx

from copilot.core.config import Config
from copilot.llm.providers import (
    LLMError,
    LLMResponse,
    OpenAICompatProvider,
    ProviderConfig,
    RateLimited,
    Rejected,
    Transient,
    Unavailable,
)
from copilot.llm.ratelimit import RateLimiter

log = logging.getLogger(__name__)

FailureHook = Callable[[str, str, bool], Awaitable[None]]  # (entry, error, will_retry)


class AllProvidersFailed(Exception):
    pass


@dataclass
class RouterSettings:
    timeout_s: float = 6.0
    retries: int = 1
    cooldown_429_s: float = 20.0
    cooldown_unavailable_s: float = 60.0
    cooldown_rejected_s: float = 300.0


@dataclass
class Entry:
    provider: OpenAICompatProvider
    limiter: RateLimiter
    calls: int = 0
    failures: int = 0

    @property
    def name(self) -> str:
        return self.provider.name


@dataclass
class RouterResult:
    response: LLMResponse
    entry: str
    attempts: list[str] = field(default_factory=list)  # "<entry>: <outcome>" for every entry tried


class LLMRouter:
    def __init__(self, entries: list[Entry], settings: Optional[RouterSettings] = None,
                 on_failure: Optional[FailureHook] = None) -> None:
        if not entries:
            raise ValueError("LLMRouter needs at least one provider entry")
        self.entries = entries
        self.settings = settings or RouterSettings()
        self.on_failure = on_failure

    async def _fail(self, entry: str, error: str, will_retry: bool) -> None:
        log.warning("llm %s failed: %s%s", entry, error, " (retrying)" if will_retry else "")
        if self.on_failure is not None:
            try:
                await self.on_failure(entry, error, will_retry)
            except Exception:  # reporting must never break routing
                log.exception("llm failure hook raised")

    async def complete(self, messages: list[dict[str, str]], *, est_tokens: int, max_tokens: int,
                       deadline: float) -> RouterResult:
        """Try entries in order until one returns text. `deadline` is a time.monotonic() value."""
        st = self.settings
        attempts: list[str] = []
        for entry in self.entries:
            budget = est_tokens + max_tokens // 2  # expected completion ≈ half the cap
            refusal = entry.limiter.admit(budget)
            if refusal is not None:
                attempts.append(f"{entry.name}: skipped ({refusal})")
                continue
            for attempt in range(st.retries + 1):
                remaining = deadline - time.monotonic()
                if remaining < 0.5:
                    attempts.append(f"{entry.name}: deadline")
                    raise AllProvidersFailed("deadline exceeded; " + "; ".join(attempts))
                if attempt > 0:
                    entry.limiter.requests.take(1)  # every HTTP attempt counts against the entry's RPM
                entry.calls += 1
                limit = min(st.timeout_s, remaining)
                err: Optional[LLMError] = None
                try:
                    # httpx timeouts are per phase (a trickling body resets them): enforce a hard total limit
                    resp = await asyncio.wait_for(
                        entry.provider.complete(messages, max_tokens=max_tokens, timeout=limit), timeout=limit + 0.5
                    )
                except asyncio.TimeoutError:
                    err = Transient(f"no complete response within {limit + 0.5:.1f}s")
                except LLMError as e:
                    err = e
                if err is not None:
                    entry.failures += 1
                    retry = err.retryable and attempt < st.retries
                    await self._fail(entry.name, str(err), retry)
                    attempts.append(f"{entry.name}: {type(err).__name__}")
                    if isinstance(err, RateLimited):
                        entry.limiter.cooldown(err.retry_after or st.cooldown_429_s)
                    elif isinstance(err, Unavailable):
                        entry.limiter.cooldown(st.cooldown_unavailable_s)
                    elif isinstance(err, Rejected):
                        entry.limiter.cooldown(st.cooldown_rejected_s)
                    if retry:
                        continue
                    break  # next entry (InvalidOutput: the next model may do better, no cooldown)
                if resp.prompt_tokens or resp.completion_tokens:
                    entry.limiter.correct_tokens(budget, resp.prompt_tokens + resp.completion_tokens)
                if resp.remaining_tokens is not None:
                    entry.limiter.tokens.clamp(resp.remaining_tokens)
                attempts.append(f"{entry.name}: ok")
                return RouterResult(resp, entry.name, attempts)
        raise AllProvidersFailed("; ".join(attempts) or "no entries")


def build_router(config: Config, client: httpx.AsyncClient, on_failure: Optional[FailureHook] = None) -> LLMRouter:
    """Entries from config [llm].order; entries whose API key is missing are left out (logged)."""
    llm = config.section("llm")
    providers = llm.get("providers", {})
    entries: list[Entry] = []
    for name in llm.get("order", []):
        raw = dict(providers.get(name, {}))
        if not raw:
            log.warning("llm entry %r in order but not configured", name)
            continue
        cfg = ProviderConfig(name=name, **raw)
        key = Config.secret(cfg.api_key_env) if cfg.api_key_env else None
        if cfg.api_key_env and not key:
            log.warning("llm entry %s disabled: %s not set", name, cfg.api_key_env)
            continue
        entries.append(Entry(OpenAICompatProvider(cfg, key, client), RateLimiter(cfg.rpm, cfg.tpm)))
    settings = RouterSettings(**{k: llm[k] for k in RouterSettings.__dataclass_fields__ if k in llm})
    return LLMRouter(entries, settings, on_failure)
