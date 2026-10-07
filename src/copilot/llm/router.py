"""Ordered LLM fall-through over the Groq models, every configured key (ADR-0001). Model ids live in config."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Optional, Sequence

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
    switch_at: float = 0.95   # a key at this share of its daily quota counts as spent: the next key takes over
    minute_wait_s: float = 4.0  # per-minute limit hit: wait this long for the active key before borrowing the next


@dataclass
class Entry:
    provider: OpenAICompatProvider
    limiter: RateLimiter
    calls: int = 0
    failures: int = 0
    usage_key: str = ""  # "<host>:<key id>:<model>": one free-tier daily quota (Groq counts per model and key)
    env: str = ""        # the .env variable holding the key ("GROQ_API_KEY_3"); never the key itself

    @property
    def tpd(self) -> int:
        cfg = getattr(self.provider, "cfg", None)
        return getattr(cfg, "tpd", 0) or 0

    @property
    def name(self) -> str:
        return self.provider.name

    @property
    def family(self) -> str:
        """The configured model entry ("groq_main") this key-specific entry ("groq_main#3") belongs to."""
        return self.name.split("#", 1)[0]


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
        used = self.usage.used(entry.usage_key)
        if entry.tpd and (used + budget > entry.tpd or used >= entry.tpd * self.settings.switch_at):
            return "daily quota spent"
        return None

    def _ordered(self) -> list[Entry]:
        """Entries to try: model families in config order; within a family the ACTIVE key first, then the keys after
        it in .env order, wrapping around to the top (user 2026-10-06: use one key until it is spent, then the next)."""
        out: list[Entry] = []
        for fam in dict.fromkeys(e.family for e in self.entries):
            group = [e for e in self.entries if e.family == fam]
            active = self.usage.active(fam) if self.usage is not None else ""
            start = next((i for i, e in enumerate(group) if active and e.env == active), 0)
            out += group[start:] + group[:start]
        return out

    def _activate(self, entry: Entry) -> None:
        """The first key of its family with daily quota left becomes (or stays) the family's active key."""
        if self.usage is None or not entry.env or self.usage.active(entry.family) == entry.env:
            return
        before = self.usage.active(entry.family)
        self.usage.set_active(entry.family, entry.env)
        self.usage.save()
        log.warning("LLM %s now uses %s%s", entry.family, entry.env, f" ({before} is spent)" if before else "")

    def quota(self) -> list[dict]:
        """Per entry: daily tokens used/limit, spent or not, and which key each model uses now (terminal view)."""
        out = []
        for e in self._ordered():
            cfg = getattr(e.provider, "cfg", None)
            has = self.usage is not None and bool(e.usage_key)
            used = self.usage.used(e.usage_key) if has else 0
            blocked = self.usage.blocked_for(e.usage_key) if has else 0.0
            spent = blocked > 0 or (e.tpd > 0 and used >= e.tpd * self.settings.switch_at)
            free_in = self.usage.free_in(e.usage_key, int(e.tpd * self.settings.switch_at)) if has and spent \
                and e.tpd else blocked
            out.append({"name": e.name, "env": e.env, "family": e.family, "model": getattr(cfg, "model", ""),
                        "tpd": e.tpd, "used": used, "spent": spent, "free_in_s": free_in, "in_use": False})
        for fam in dict.fromkeys(q["family"] for q in out):  # the key the next call of this model goes to
            first = next((q for q in out if q["family"] == fam and not q["spent"]), None)
            if first is not None:
                first["in_use"] = True
        return out

    async def _fail(self, entry: str, error: str, will_retry: bool) -> None:
        log.warning("llm %s failed: %s%s", entry, error, " (retrying)" if will_retry else "")
        if self.on_failure is not None:
            try:
                await self.on_failure(entry, error, will_retry)
            except Exception:  # reporting must never break routing
                log.exception("llm failure hook raised")

    async def complete(self, messages: list[dict[str, str]], *, est_tokens: int, max_tokens: int,
                       deadline: float, timeout_s: Optional[float] = None) -> RouterResult:
        """Try entries in order until one returns text. `deadline` is a time.monotonic() value.
        timeout_s: per HTTP attempt instead of the live default (F-010: writing study material takes longer)."""
        st = self.settings
        if timeout_s is not None:
            from dataclasses import replace

            st = replace(st, timeout_s=timeout_s)
        attempts: list[str] = []
        budget = est_tokens + max_tokens // 2  # expected completion ≈ half the cap
        fresh: set[str] = set()  # families whose active key was settled in this call
        busy: list[Entry] = []   # skipped only for their per-minute limits: free again within seconds
        for entry in self._ordered():
            daily = self._daily_refusal(entry, budget)
            if daily is not None:
                attempts.append(f"{entry.name}: skipped ({daily})")
                continue
            owner = entry.family not in fresh  # the first key of its family with quota left: the one in use
            if owner:
                fresh.add(entry.family)
                self._activate(entry)
                # its per-minute limit is full: a short wait keeps the work on this key; only a long one borrows
                # the next key for this call (the active key stays; several keys are not drained at once)
                wait = entry.limiter.ready_in(budget)
                room = deadline - time.monotonic() - st.timeout_s
                if 0 < wait <= min(st.minute_wait_s, room):
                    await asyncio.sleep(wait + 0.05)
            refusal = entry.limiter.admit(budget)
            if refusal is not None:
                attempts.append(f"{entry.name}: skipped ({refusal})")
                if refusal in ("rpm", "tpm"):
                    busy.append(entry)
                continue
            result = await self._call(entry, messages, max_tokens, budget, deadline, attempts, st)
            if result is not None:
                return result
        # nothing could take the call now: rather than lose the content to the fallback, wait for the entry that
        # frees up first while the deadline leaves room for the call (long test 2026-10-06: 7 units lost)
        waits = sorted(((e.limiter.ready_in(budget), i, e) for i, e in enumerate(busy)), key=lambda x: x[:2])
        if waits:
            wait, _, entry = waits[0]
            room = deadline - time.monotonic() - st.timeout_s
            if wait <= room:
                log.info("llm: every model is at its per-minute limit; waiting %.1f s for %s", wait, entry.name)
                await asyncio.sleep(wait + 0.05)
                refusal = entry.limiter.admit(budget)
                if refusal is None:
                    result = await self._call(entry, messages, max_tokens, budget, deadline, attempts, st)
                    if result is not None:
                        return result
                else:
                    attempts.append(f"{entry.name}: skipped ({refusal})")
        raise AllProvidersFailed("; ".join(attempts) or "no entries")

    async def _call(self, entry: Entry, messages: list[dict[str, str]], max_tokens: int, budget: int,
                    deadline: float, attempts: list[str],
                    st: Optional[RouterSettings] = None) -> Optional[RouterResult]:
        """One admitted entry: the call with its retries. None = failed (go on to the next entry)."""
        st = st or self.settings
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
        return None


def _natural(name: str) -> tuple:
    suffix = name.rpartition("_")[2]
    return (int(suffix), "") if suffix.isdigit() else (10 ** 9, name)


def api_keys(env_name: str, order: Sequence[str] = ()) -> list[tuple[str, str]]:
    """(env var, key) for ENV and every ENV_<anything> that is set (GROQ_API_KEY_main, _2, _6 ...): first in `order`
    (the .env file's order), then the rest (ENV, then numbered, then named). The same key listed twice is used once.
    Live test 2026-10-06: the first key was named GROQ_API_KEY_main and was never used."""
    pattern = re.compile(rf"{re.escape(env_name)}(?:_\w+)?")
    names = [n for n in dict.fromkeys(order) if pattern.fullmatch(n)]
    rest = sorted((n for n in os.environ if pattern.fullmatch(n) and n not in names),
                  key=lambda n: (n != env_name, _natural(n)))
    out: list[tuple[str, str]] = []
    for name in names + rest:
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
            keys = list(api_keys(base.api_key_env, getattr(config, "env_order", [])))
            if not keys:
                log.warning("llm entry %s disabled: %s not set", name, base.api_key_env)
                continue
        for env, key in keys:  # "groq_main#2" uses GROQ_API_KEY_2
            suffix = env[len(base.api_key_env) + 1:]
            cfg = ProviderConfig(name=f"{name}#{suffix}" if suffix else name, **raw)
            usage_key = f"{httpx.URL(cfg.base_url).host}:{key_id(key)}:{cfg.model}"
            entries.append(Entry(OpenAICompatProvider(cfg, key, client), RateLimiter(cfg.rpm, cfg.tpm),
                                 usage_key=usage_key, env=env or ""))
    settings = RouterSettings(**{k: llm[k] for k in RouterSettings.__dataclass_fields__ if k in llm})
    return LLMRouter(entries, settings, on_failure, usage)
