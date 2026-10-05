"""Several Groq keys, daily quota handling (429 TPD body, usage ledger) and the startup quota view."""
import json
import time

import httpx

from copilot.app.main import pages_to_open, print_quota
from copilot.core.config import load_config
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig, rate_limited
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter, RouterSettings, build_router
from copilot.llm.usage import UsageLedger, key_id

GROQ_TPD_BODY = ("Rate limit reached for model `openai/gpt-oss-120b` in organization `org_x` service tier `on_demand` "
                 "on tokens per day (TPD): Limit 200000, Used 199616, Requested 2345. Please try again in 7m12.48s.")


class WallClock:
    def __init__(self, t=1_800_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def ok_body(usage=(1000, 300)):
    return {"choices": [{"message": {"content": '{"ok": true}'}}],
            "usage": {"prompt_tokens": usage[0], "completion_tokens": usage[1]}}


def clear_keys(monkeypatch):
    for i in range(1, 10):
        monkeypatch.delenv("GROQ_API_KEY" if i == 1 else f"GROQ_API_KEY_{i}", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)


def make_router(handler, usage, tpd=200000, names=("a", "b")):
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    entries = [Entry(OpenAICompatProvider(ProviderConfig(name=n, base_url=f"https://{n}.test/v1", model=f"m-{n}",
                                                         tpd=tpd), "k", client),
                     RateLimiter(rpm=100, tpm=100000), usage_key=f"{n}.test:k:m-{n}") for n in names]
    return LLMRouter(entries, RouterSettings(timeout_s=1.0), usage=usage), client


def deadline():
    return time.monotonic() + 10


# ---- keys ------------------------------------------------------------------------------------
def test_every_groq_key_gets_entries_same_model_first_then_next_model(monkeypatch):
    clear_keys(monkeypatch)
    cfg = load_config(environ={})
    clear_keys(monkeypatch)  # load_config reads .env into the environment
    monkeypatch.setenv("GROQ_API_KEY", "k1")
    monkeypatch.setenv("GROQ_API_KEY_2", "k2")
    monkeypatch.setenv("GROQ_API_KEY_4", "k4")   # gaps are fine
    monkeypatch.setenv("GROQ_API_KEY_3", "k1")   # the same key twice is used once
    router = build_router(cfg, httpx.AsyncClient())
    assert [e.name for e in router.entries] == ["groq_main", "groq_main#2", "groq_main#4",
                                                "groq_alt", "groq_alt#2", "groq_alt#4"]
    keys = [e.provider._key for e in router.entries]
    assert keys == ["k1", "k2", "k4"] * 2
    assert len({e.usage_key for e in router.entries}) == 6 and "k1" not in router.entries[0].usage_key
    assert router.entries[0].usage_key == f"api.groq.com:{key_id('k1')}:openai/gpt-oss-120b"
    assert router.entries[0].tpd == 200000


# ---- daily quota -----------------------------------------------------------------------------
def test_groq_daily_429_parsed():
    err = rate_limited(httpx.Response(429, text=GROQ_TPD_BODY, headers={"retry-after": "433"}))
    assert err.daily and err.used == 199616 and err.limit == 200000
    assert abs(err.reset_at - (time.time() + 432.48)) < 5
    minute = rate_limited(httpx.Response(429, text="tokens per minute (TPM): Limit 8000", headers={"retry-after": "7"}))
    assert not minute.daily and minute.retry_after == 7


async def test_spent_key_moves_to_next_key_and_stays_skipped_in_a_new_session(tmp_path):
    path = tmp_path / "usage.json"
    calls = []

    def handler(req):
        calls.append(req.url.host)
        if req.url.host == "a.test":
            return httpx.Response(429, text=GROQ_TPD_BODY)
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, UsageLedger(path))
    res = await router.complete([], est_tokens=500, max_tokens=200, deadline=deadline())
    assert res.entry == "b" and calls == ["a.test", "b.test"]
    await client.aclose()
    # next session: the spent key is skipped without a call (no wasted request at the start of a lecture)
    calls.clear()
    router2, client2 = make_router(handler, UsageLedger(path))
    res = await router2.complete([], est_tokens=500, max_tokens=200, deadline=deadline())
    await client2.aclose()
    assert calls == ["b.test"] and "a: skipped (daily quota spent)" in res.attempts
    q = {x["name"]: x for x in router2.quota()}
    assert q["a"]["spent"] and q["a"]["used"] == 199616 and 400 < q["a"]["free_in_s"] < 440
    assert not q["b"]["spent"] and q["b"]["used"] == 2600  # two calls of 1300


async def test_own_count_skips_a_key_before_the_server_refuses():
    usage = UsageLedger(None)
    usage.add("a.test:k:m-a", 199000)
    calls = []

    def handler(req):
        calls.append(req.url.host)
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, usage)
    res = await router.complete([], est_tokens=1500, max_tokens=400, deadline=deadline())
    await client.aclose()
    assert res.entry == "b" and calls == ["b.test"]


async def test_daily_429_without_time_blocks_for_fallback_period():
    usage = UsageLedger(None)

    def handler(req):
        if req.url.host == "a.test":
            return httpx.Response(429, text="tokens per day (TPD): Limit 200000, Used 200000")
        return httpx.Response(200, json=ok_body())

    router, client = make_router(handler, usage)
    await router.complete([], est_tokens=10, max_tokens=50, deadline=deadline())
    await client.aclose()
    assert 3500 < usage.blocked_for("a.test:k:m-a") <= 3600


# ---- ledger ----------------------------------------------------------------------------------
def test_ledger_rolling_24h_floor_expiry_and_persistence(tmp_path):
    clk = WallClock()
    path = tmp_path / "usage.json"
    led = UsageLedger(path, clk)
    led.add("k", 1000)
    clk.t += 3600
    led.add("k", 500)
    led.spent("k", used=150000, until=clk.t + 600)
    led.save()
    assert "secret" not in path.read_text()
    again = UsageLedger(path, clk)
    assert again.used("k") == 150000 and again.blocked_for("k") == 600  # server count while valid
    clk.t += 601
    assert again.used("k") == 1500 and again.blocked_for("k") == 0     # then our own count
    clk.t += 23 * 3600
    assert again.used("k") == 500                                        # the first call left the 24 h window


def test_ledger_corrupt_or_old_format_file_starts_empty(tmp_path):
    path = tmp_path / "usage.json"
    path.write_text("{not json", encoding="utf-8")
    assert UsageLedger(path).used("k") == 0
    path.write_text(json.dumps({"keys": {"x": {"buckets": {"1": [5, 1]}}}}), encoding="utf-8")
    led = UsageLedger(path)
    led.add("k", 10)
    led.save()
    assert UsageLedger(path).used("k") == 10


def test_key_id_is_not_the_key():
    assert key_id("gsk_secret_value") != "gsk_secret_value" and len(key_id("gsk_secret_value")) == 8
    assert key_id("a") != key_id("b")


# ---- startup view and auto-open --------------------------------------------------------------
def test_print_quota_lists_keys_and_minutes(capsys):
    usage = UsageLedger(None)
    usage.add("a.test:k:m-a", 120000)
    usage.spent("b.test:k:m-b", used=200000, until=time.time() + 1800)
    router, _ = make_router(lambda req: httpx.Response(200, json=ok_body()), usage)
    print_quota(router)
    out = capsys.readouterr().out
    assert "[QUOTA]" in out and "80k of 200k tokens" in out and "SPENT, free again in ~30 min" in out
    assert "enough for about 10 lecture minutes" in out


def test_print_quota_warns_when_nothing_left(capsys):
    usage = UsageLedger(None)
    usage.spent("a.test:k:m-a", used=200000, until=time.time() + 60)
    router, _ = make_router(lambda req: httpx.Response(200, json=ok_body()), usage, names=("a",))
    print_quota(router)
    assert "!! No Groq quota left" in capsys.readouterr().out


def test_pages_to_open_skips_connected_roles():
    assert pages_to_open({"control": 0, "display": 0}) == ["control", "display"]
    assert pages_to_open({"control": 1, "display": 0}) == ["display"]
    assert pages_to_open({"control": 2, "display": 1}) == []
