"""Rate limiter + router fall-through over real httpx with a mocked transport (the network is the boundary)."""
import json
import time

import httpx
import pytest

from copilot.core.config import load_config
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter, TokenBucket
from copilot.llm.router import AllProvidersFailed, Entry, LLMRouter, RouterSettings, build_router


class FakeClock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_token_bucket_refills_continuously():
    clk = FakeClock()
    b = TokenBucket(60, clk)
    b.take(60)
    assert not b.can_take(1)
    clk.t += 1.0
    assert b.can_take(1) and not b.can_take(2)
    clk.t += 120
    assert b.available() == 60  # capped


def test_limiter_rpm_tpm_cooldown():
    clk = FakeClock()
    rl = RateLimiter(rpm=2, tpm=1000, clock=clk)
    assert rl.admit(400) is None
    assert rl.admit(400) is None
    assert rl.admit(10) == "rpm"
    clk.t += 60
    assert rl.admit(900) is None  # both buckets refilled after a minute
    rl2 = RateLimiter(rpm=100, tpm=1000, clock=clk)
    assert rl2.admit(900) is None
    assert rl2.admit(900) == "tpm"
    rl2.cooldown(30)
    clk.t += 120
    assert rl2.admit(10) is None
    rl2.cooldown(30)
    assert rl2.admit(10).startswith("cooldown")


def ok_body(content='{"ok": true}', usage=(100, 50)):
    return {"choices": [{"message": {"content": content}}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}


def make_router(handler, names=("a", "b"), settings=None, failures=None):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    entries = [
        Entry(OpenAICompatProvider(ProviderConfig(name=n, base_url=f"https://{n}.test/v1", model=f"m-{n}"), "k", client),
              RateLimiter(rpm=100, tpm=100000))
        for n in names
    ]

    async def on_failure(entry, error, will_retry):
        if failures is not None:
            failures.append((entry, error.split()[0], will_retry))

    return LLMRouter(entries, settings or RouterSettings(timeout_s=1.0), on_failure), client


def deadline(s=10.0):
    return time.monotonic() + s


async def test_first_provider_ok_sends_openai_body():
    seen = []

    def handler(req: httpx.Request):
        seen.append((req.url.host, json.loads(req.content), req.headers.get("authorization")))
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler)
    res = await router.complete([{"role": "user", "content": "hi"}], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert res.entry == "a" and res.response.text == '{"ok": true}'
    host, body, auth = seen[0]
    assert host == "a.test" and body["model"] == "m-a" and body["response_format"] == {"type": "json_object"}
    assert auth == "Bearer k"


async def test_429_cools_down_and_falls_through():
    calls = []
    failures = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.test":
            return httpx.Response(429, headers={"retry-after": "30"}, text="rate limited")
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, failures=failures)
    res = await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    assert res.entry == "b" and calls == ["a.test", "b.test"]  # 429 is not retried on the same entry
    assert failures == [("a", "429", False)]
    # a is cooling down: the next call goes straight to b
    calls.clear()
    res = await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert calls == ["b.test"] and any("skipped (cooldown" in a for a in res.attempts)


async def test_timeout_retried_once_then_next():
    calls = []
    failures = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.test":
            raise httpx.ReadTimeout("slow", request=req)
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, failures=failures)
    res = await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert calls == ["a.test", "a.test", "b.test"] and res.entry == "b"
    assert [f[2] for f in failures] == [True, False]


async def test_connect_error_unavailable_and_5xx():
    def handler(req):
        if req.url.host == "a.test":
            raise httpx.ConnectError("refused", request=req)
        return httpx.Response(503, text="overloaded")

    router, client = make_router(handler)
    with pytest.raises(AllProvidersFailed) as ei:
        await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    msg = str(ei.value)
    assert "a: Unavailable" in msg and msg.count("b: Transient") == 2


async def test_json_validate_failed_falls_through_without_cooldown():
    calls = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.test" and len(calls) == 1:
            return httpx.Response(400, json={"error": {"code": "json_validate_failed"}})
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler)
    assert (await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())).entry == "b"
    assert (await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())).entry == "a"
    await client.aclose()


async def test_empty_content_is_invalid_output():
    def handler(req):
        if req.url.host == "a.test":
            return httpx.Response(200, json=ok_body(content=""))
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler)
    assert (await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())).entry == "b"
    await client.aclose()


async def test_deadline_respected():
    def handler(req):
        raise AssertionError("must not be called")

    router, client = make_router(handler)
    with pytest.raises(AllProvidersFailed, match="deadline"):
        await router.complete([], est_tokens=10, max_tokens=50, deadline=time.monotonic() + 0.1)
    await client.aclose()


async def test_tpm_skips_entry_and_server_header_clamps():
    def handler(req):
        return httpx.Response(200, json=ok_body(usage=(500, 100)), headers={"x-ratelimit-remaining-tokens": "50"})

    router, client = make_router(handler)
    r1 = await router.complete([], est_tokens=500, max_tokens=200, deadline=deadline())
    assert r1.entry == "a"
    # the server said only 50 tokens remain on a → the next 500-token call is routed to b
    r2 = await router.complete([], est_tokens=500, max_tokens=200, deadline=deadline())
    await client.aclose()
    assert r2.entry == "b" and "a: skipped (tpm)" in r2.attempts


def test_build_router_from_config_skips_missing_keys(monkeypatch):
    cfg = load_config(environ={})
    monkeypatch.setenv("GROQ_API_KEY", "x")
    for i in range(2, 10):  # extra keys in .env would add entries (tests/unit/test_llm_keys_usage.py)
        monkeypatch.delenv(f"GROQ_API_KEY_{i}", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    router = build_router(cfg, httpx.AsyncClient())
    names = [e.name for e in router.entries]
    assert names == ["groq_main", "groq_alt"]  # Ollama is opt-in only (verify round 6)
    assert router.entries[0].provider.cfg.extra["reasoning_effort"] == "low"
    assert router.settings.timeout_s == 6.0 and router.settings.retries == 1
    assert router.entries[1].provider.cfg.max_output_tokens == 900


async def test_entry_output_cap_applied():
    bodies = []

    def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json=ok_body())

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    p = OpenAICompatProvider(ProviderConfig(name="q", base_url="https://q.test/v1", model="m", max_output_tokens=900),
                             "k", client)
    await p.complete([], max_tokens=1400, timeout=1.0)
    await client.aclose()
    assert bodies[0]["max_tokens"] == 900


@pytest.mark.parametrize("body", [
    {"choices": [{"message": None}]},
    {"choices": []},
    {"error": {"message": "upstream down"}},
    ["not", "an", "object"],
])
async def test_malformed_bodies_fall_through(body):
    def handler(req):
        if req.url.host == "a.test":
            return httpx.Response(200, json=body)
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, settings=RouterSettings(timeout_s=1.0, retries=0))
    assert (await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())).entry == "b"
    await client.aclose()


async def test_content_parts_list_is_joined():
    def handler(req):
        return httpx.Response(200, json={"choices": [{"message": {"content": [
            {"type": "text", "text": '{"a":'}, {"type": "text", "text": " 1}"}]}}]})

    router, client = make_router(handler)
    assert (await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())).response.text == '{"a": 1}'
    await client.aclose()


async def test_hard_total_timeout_and_rpm_per_attempt():
    """Review fix: httpx timeouts are per phase; the router enforces a total limit per attempt."""
    import asyncio

    from copilot.llm.providers import LLMResponse

    class Trickle:
        name = "slow"

        async def complete(self, messages, *, max_tokens, timeout):
            await asyncio.sleep(30)  # e.g. keep-alive bytes keep the read timer alive
            return LLMResponse("never")

    limiter = RateLimiter(rpm=10, tpm=100000, clock=lambda: 0.0)  # frozen: no refill during the test
    router = LLMRouter([Entry(Trickle(), limiter)], RouterSettings(timeout_s=0.3, retries=1))
    t0 = time.monotonic()
    with pytest.raises(AllProvidersFailed):
        await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    assert time.monotonic() - t0 < 3.0
    assert limiter.requests.available() == 8  # both attempts charged


async def test_connect_timeout_counts_as_unavailable():
    """Verify lecture 20261005-110717-dc56: Ollama not running surfaced as ConnectTimeout on Windows and was retried
    (2 x 2 s) on every unit instead of cooling down."""
    def handler(req):
        if req.url.host == "a.test":
            raise httpx.ConnectTimeout("no answer", request=req)
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler)
    res = await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert res.entry == "b"
    assert (router.entries[0].limiter.admit(10) or "").startswith("cooldown")  # not retried, cooled down
