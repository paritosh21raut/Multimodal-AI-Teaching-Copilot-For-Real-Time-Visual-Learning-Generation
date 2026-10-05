"""Ordered LLM fall-through: Groq (every configured key) → OpenRouter (ADR-0001). Model ids live in config."""
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
from copilot.llm.usage import UsageLedger, key_id

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
    daily_block_fallback_s: float = 3600.0  # a daily 429 that does not say when the quota frees up


@dataclass
class Entry:
    provider: OpenAICompatProvider
    limiter: RateLimiter
    calls: int = 0
    failures: int = 0
    usage_key: str = ""  # "<host>:<key id>:<model>": one free-tier daily quota (Groq counts per model and key)

    @property
    def tpd(self) -> int:
        cfg = getattr(self.provider, "cfg", None)
        return getattr(cfg, "tpd", 0) or 0

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
                 on_failure: Optional[FailureHook] = None, usage: Optional[UsageLedger] = None) -> None:
        if not entries:
            raise ValueError("LLMRouter needs at least one provider entry")
        self.entries = entries
        self.settings = settings or RouterSettings()
        self.on_failure = on_failure
        self.usage = usage

    def _daily_refusal(self, entry: Entry, budget: int) -> Optional[str]:
        """Skip a spent key without a call (a 429 said so, or our count says this call would not fit)."""
        if self.usage is None or not entry.usage_key:
            return None
        if self.usage.blocked_for(entry.usage_key) > 0:
            return "daily quota spent"
        if entry.tpd and self.usage.used(entry.usage_key) + budget > entry.tpd:
            return "daily quota spent"
        return None

    def quota(self) -> list[dict]:
        """Per entry: daily tokens used/limit and whether it is spent (startup terminal view)."""
        out = []
        for e in self.entries:
            cfg = getattr(e.provider, "cfg", None)
            used = self.usage.used(e.usage_key) if self.usage is not None and e.usage_key else 0
            blocked = self.usage.blocked_for(e.usage_key) if self.usage is not None and e.usage_key else 0.0
            out.append({"name": e.name, "model": getattr(cfg, "model", ""), "tpd": e.tpd, "used": used,
                        "spent": blocked > 0 or (e.tpd > 0 and used >= e.tpd), "free_in_s": blocked})
        return out

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
            refusal = self._daily_refusal(entry, budget) or entry.limiter.admit(budget)
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
                    if isinstance(err, RateLimited) and err.daily:
                        # keep a short "try again in 32s" as is: only a missing/stale time gets the fallback block
                        now = time.time()
                        until = err.reset_at if err.reset_at and err.reset_at > now else now + st.daily_block_fallback_s
                        entry.limiter.cooldown(until - now)
                        if self.usage is not None and entry.usage_key:
                            self.usage.spent(entry.usage_key, used=err.used, until=until)
                            self.usage.save()
                    elif isinstance(err, RateLimited):
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
                if self.usage is not None and entry.usage_key:
                    self.usage.add(entry.usage_key, resp.prompt_tokens + resp.completion_tokens)
                    self.usage.save()
                if resp.remaining_tokens is not None:
                    entry.limiter.tokens.clamp(resp.remaining_tokens)
                attempts.append(f"{entry.name}: ok")
                return RouterResult(resp, entry.name, attempts)
        raise AllProvidersFailed("; ".join(attempts) or "no entries")


MAX_KEYS = 9  # GROQ_API_KEY, GROQ_API_KEY_2 ... GROQ_API_KEY_9


def api_keys(env_name: str) -> list[tuple[str, str]]:
    """(env var, key) for ENV, ENV_2 ... ENV_9 that are set; the same key listed twice is used once."""
    out: list[tuple[str, str]] = []
    for i in range(1, MAX_KEYS + 1):
        name = env_name if i == 1 else f"{env_name}_{i}"
        key = Config.secret(name)
        if key and key not in [k for _, k in out]:
            out.append((name, key))
    return out


def build_router(config: Config, client: httpx.AsyncClient, on_failure: Optional[FailureHook] = None,
                 usage: Optional[UsageLedger] = None) -> LLMRouter:
    """Entries from config [llm].order; entries whose API key is missing are left out (logged).

    An entry whose key env var has numbered siblings (GROQ_API_KEY_2, _3, ...) gets one entry per key, right after
    each other: when one key's free quota for a model is spent, the same model is used through the next key
    ("groq_main", "groq_main#2", ...), and only then the next model."""
    llm = config.section("llm")
    providers = llm.get("providers", {})
    entries: list[Entry] = []
    for name in llm.get("order", []):
        raw = dict(providers.get(name, {}))
        if not raw:
            log.warning("llm entry %r in order but not configured", name)
            continue
        base = ProviderConfig(name=name, **raw)
        if not base.api_key_env:
            keys: list[tuple[str, Optional[str]]] = [(base.api_key_env, None)]
        else:
            keys = list(api_keys(base.api_key_env))
            if not keys:
                log.warning("llm entry %s disabled: %s not set", name, base.api_key_env)
                continue
        for env, key in keys:  # "groq_main#2" uses GROQ_API_KEY_2
            suffix = env[len(base.api_key_env) + 1:]
            cfg = ProviderConfig(name=f"{name}#{suffix}" if suffix else name, **raw)
            usage_key = f"{httpx.URL(cfg.base_url).host}:{key_id(key)}:{cfg.model}"
            entries.append(Entry(OpenAICompatProvider(cfg, key, client), RateLimiter(cfg.rpm, cfg.tpm),
                                 usage_key=usage_key))
    settings = RouterSettings(**{k: llm[k] for k in RouterSettings.__dataclass_fields__ if k in llm})
    return LLMRouter(entries, settings, on_failure, usage)
