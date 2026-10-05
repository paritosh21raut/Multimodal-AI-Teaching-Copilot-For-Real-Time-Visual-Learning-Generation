"""Simulator → bus → UnderstandingService → state store, with only the HTTP boundary mocked."""
import json
import re
import zlib
from pathlib import Path

import httpx
import numpy as np

from copilot.core.bus import EventBus
from copilot.core.events import (
    ConceptSignal,
    InterpretationReady,
    InterpretRequested,
    TranscriptFinal,
    UtteranceClassified,
)
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter, RouterSettings
from copilot.sim.simulator import LectureSimulator, parse_script
from copilot.understanding.gate import GateConfig
from copilot.understanding.interpreter import Interpreter, InterpreterSettings
from copilot.understanding.service import UnderstandingService, UnderstandingSettings

FIXTURE = Path(__file__).parents[1] / "fixtures" / "lectures" / "photosynthesis.txt"
SPEED = 40.0
LECTURE_INTERVAL_S = 8.0  # the production rate floor, expressed in lecture time


class HashEmbedder:
    """Deterministic bag-of-words embedding (test double for MiniLM at the model boundary)."""

    def embed(self, texts):
        out = np.zeros((len(texts), 64), dtype=np.float32)
        for i, t in enumerate(texts):
            for w in re.findall(r"[a-z]+", t.lower()):
                out[i, zlib.crc32(w.encode()) % 64] += 1.0
            out[i] /= max(np.linalg.norm(out[i]), 1e-9)
        return out


class FakeLLM:
    """Answers like a model would: topic from the new lines, wrong-oxygen claim flagged."""

    def __init__(self, fail_first=0):
        self.requests = []
        self.fail_first = fail_first

    def __call__(self, req: httpx.Request):
        body = json.loads(req.content)
        user = body["messages"][1]["content"]
        self.requests.append(user)
        if len(self.requests) <= self.fail_first:
            return httpx.Response(503, text="overloaded")
        new = user.split("NEW LINES:\n", 1)[1]
        lines = re.findall(r"^\[(\d+)\][^\n]*", new, re.M)
        respiration = "respiration" in new.lower()
        concerns = []
        for m in re.finditer(r"^\[(\d+)\] Plants take in oxygen during photosynthesis", new, re.M):
            concerns.append({"claim": "Plants take in oxygen during photosynthesis", "issue": "reversed",
                             "suggested_correction": "Plants take in carbon dioxide", "confidence": 0.95,
                             "lines": [int(m.group(1))]})
        out = {
            "topic": "Respiration" if respiration else "Photosynthesis",
            "subtopic": "Comparison" if respiration else "",
            "relation": "new_topic" if respiration or "CURRENT: (none yet)" in user else "same_concept",
            "acts": [{"act": "explanation", "lines": [int(x) for x in lines], "items": {"points": ["p"]}}],
            "representation_hint": "key_points", "concerns": concerns,
            "summary_delta": f"Covered {len(lines)} lines.",
        }
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(out)}}],
                                         "usage": {"prompt_tokens": 900, "completion_tokens": 200}})


async def run_lecture(fake: FakeLLM):
    script = parse_script(FIXTURE)
    bus = EventBus()
    bus.session_id = "it"
    store = LectureStateStore(bus, "it", LectureSetup(subject="Biology", grade_level="7",
                                                      expected_topic="Photosynthesis"))
    store.attach()
    client = httpx.AsyncClient(transport=httpx.MockTransport(fake))
    entries = [Entry(OpenAICompatProvider(ProviderConfig(name=n, base_url=f"https://{n}.test/v1", model="m"), "k",
                                          client), RateLimiter(100, 100000)) for n in ("main", "alt")]
    router = LLMRouter(entries, RouterSettings(timeout_s=2.0, retries=0))
    settings = UnderstandingSettings(min_call_interval_s=LECTURE_INTERVAL_S / SPEED, gate=GateConfig(),
                                     interpreter=InterpreterSettings())
    svc = UnderstandingService(bus, store, Interpreter(router, settings.interpreter), HashEmbedder(), settings,
                               speed=SPEED)
    events = []

    async def record(e):
        events.append(e)

    bus.subscribe("rec", record, [TranscriptFinal, UtteranceClassified, ConceptSignal, InterpretRequested,
                                  InterpretationReady])
    svc.attach()
    await LectureSimulator(bus, script, speed=SPEED).run()
    assert await svc.flush(timeout=20.0)
    await svc.stop()
    await bus.close()
    await client.aclose()
    return script, store, svc, events


async def test_every_content_segment_sent_once_in_order():
    fake = FakeLLM()
    script, store, svc, events = await run_lecture(fake)
    finals = [e.segment for e in events if isinstance(e, TranscriptFinal)]
    kinds = {e.segment_id: e.kind for e in events if isinstance(e, UtteranceClassified)}
    content_ids = [s.id for s in finals if kinds[s.id] in ("content", "question_to_class")]
    meta_ids = {s.id for s in finals if s.id not in content_ids}

    sent = [sid for e in events if isinstance(e, InterpretRequested) for sid in e.segment_ids]
    assert sent == content_ids                       # nothing lost, nothing duplicated, in order
    assert meta_ids and not (meta_ids & set(sent))   # classroom talk never reaches the LLM
    for text in ("take out your science books", "Look at the screen"):
        assert not any(text in r for r in fake.requests)

    readies = [e for e in events if isinstance(e, InterpretationReady)]
    reqs = [e for e in events if isinstance(e, InterpretRequested)]
    assert [r.request_id for r in readies] == [r.request_id for r in reqs]
    assert all(r.segment_ids == q.segment_ids for r, q in zip(readies, reqs))
    assert len({e.segment_id for e in events if isinstance(e, ConceptSignal)}) == len(content_ids)


async def test_rate_budget_and_state():
    fake = FakeLLM()
    script, store, svc, events = await run_lecture(fake)
    st = svc.stats
    # The rule is a wall-clock rate; here one lecture minute lasts 60/SPEED wall seconds. Count sends in every
    # such window (measuring per lecture-minute mixed clocks and counted post-lecture flush calls).
    times = list(st.call_wall_times)
    window = 60.0 / SPEED
    assert max(sum(1 for u in times if t <= u < t + window) for t in times) <= 8
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert all(g >= LECTURE_INTERVAL_S / SPEED for g in gaps), gaps  # rate floor, measured on the same clock
    assert st.max_prompt_tokens <= 2600 and st.fallbacks == 0
    # every prompt is bounded: no request contains the whole transcript
    assert all(r.count("\n[") <= 12 for r in fake.requests)

    s = store.snapshot()
    assert [t.title for t in s.outline] == ["Photosynthesis", "Respiration"]
    assert s.topic(s.current_topic_id).title == "Respiration"
    assert len(s.concerns) == 1 and "oxygen" in s.concerns[0].claim
    assert s.stats.llm_calls == st.requests
    # later prompts carry the rolling memory, not old transcript lines
    assert "RECENT SUMMARY: Covered" in fake.requests[-1]
    assert "Good morning" not in "".join(fake.requests)


async def test_provider_outage_falls_through_to_second_entry():
    fake = FakeLLM(fail_first=1)
    _, store, svc, _ = await run_lecture(fake)
    assert svc.stats.fallbacks == 0
    assert svc.stats.providers.get("alt", 0) >= 1


async def test_interpreter_crash_still_yields_ready_for_every_segment(monkeypatch):
    """Review fix: an unexpected exception inside interpretation must not lose the taken lines."""
    from copilot.understanding import interpreter as interp_mod

    calls = {"n": 0}
    real = interp_mod.parse_interpretation

    def flaky(text):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return real(text)

    monkeypatch.setattr(interp_mod, "parse_interpretation", flaky)
    _, store, svc, events = await run_lecture(FakeLLM())
    sent = [sid for e in events if isinstance(e, InterpretRequested) for sid in e.segment_ids]
    ready = [sid for e in events if isinstance(e, InterpretationReady) for sid in e.segment_ids]
    assert ready == sent and svc.stats.fallbacks == 1
