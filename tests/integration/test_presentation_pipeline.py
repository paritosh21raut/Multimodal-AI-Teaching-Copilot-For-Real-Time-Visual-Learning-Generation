"""Simulator (with VAD) → understanding (HTTP mocked) → state store → presentation engine → deck (F-005)."""
import json
import re
from pathlib import Path

import httpx

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, Lifecycle, LifecycleChanged
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.llm.providers import OpenAICompatProvider, ProviderConfig
from copilot.llm.ratelimit import RateLimiter
from copilot.llm.router import Entry, LLMRouter, RouterSettings
from copilot.presentation.deck import Deck
from copilot.presentation.engine import PresentationEngine, PresentationSettings
from copilot.sim.simulator import LectureSimulator, parse_script
from copilot.understanding.interpreter import Interpreter
from copilot.understanding.service import UnderstandingService, UnderstandingSettings
from tests.integration.test_understanding_pipeline import HashEmbedder

FIXTURE = Path(__file__).parents[1] / "fixtures" / "lectures" / "photosynthesis.txt"
SPEED = 30.0
WRONG = "Plants take in oxygen during photosynthesis"


def facet(line: str) -> tuple[str, str]:
    low = line.lower()
    if "respiration" in low:
        return "Respiration", "Comparison"
    if any(w in low for w in ("important", "food we eat", "breathe")):
        return "Photosynthesis", "Importance"
    if any(w in low for w in ("step", "first,", "then ", "next,", "finally", "equation", "take in oxygen")):
        return "Photosynthesis", "Process"
    if any(w in low for w in ("needs", "absorbed", "enters", "pigment")):
        return "Photosynthesis", "Requirements"
    return "Photosynthesis", "Definition"


class SlideLLM:
    """Answers like the real model on this fixture: facet from keywords, process steps, the wrong claim flagged."""

    def __call__(self, req: httpx.Request):
        user = json.loads(req.content)["messages"][1]["content"]
        cur = re.search(r"CURRENT: topic=([^;\n]+); subtopic=([^\n]+)", user)
        lines = re.findall(r"^\[(\d+)\][^\n]*? ([^\[\n]+)$", user.split("NEW LINES:\n", 1)[1], re.M)
        topic, sub = facet(lines[-1][1])
        acts, concerns = [], []
        for n, text in lines:
            n = int(n)
            t, s = facet(text)
            if s == "Process" and "equation" not in text.lower() and WRONG not in text:
                acts.append({"act": "process", "lines": [n], "items": {"steps": [text[:60]]}})
            elif "equation" in text.lower():
                acts.append({"act": "formula", "lines": [n], "items": {"formula": {
                    "expression": "carbon dioxide + water -> glucose + oxygen", "variables": []}}})
            else:
                acts.append({"act": "explanation", "lines": [n], "items": {"points": [text[:60]]}})
            if WRONG in text:
                concerns.append({"claim": text, "issue": "reversed", "confidence": 0.95, "lines": [n],
                                 "suggested_correction": "Plants take in carbon dioxide and give out oxygen"})
        same_topic = cur and cur.group(1).strip() == topic
        relation = ("same_concept" if same_topic and cur.group(2).strip() == sub
                    else "sibling_concept" if same_topic else "new_topic")
        out = {"topic": topic, "subtopic": sub, "relation": relation, "acts": acts, "concerns": concerns,
               "representation_hint": "key_points", "summary_delta": f"{sub}."}
        return httpx.Response(200, json={"choices": [{"message": {"content": json.dumps(out)}}],
                                         "usage": {"prompt_tokens": 900, "completion_tokens": 200}})


async def test_fixture_lecture_builds_a_continuity_aware_deck():
    script = parse_script(FIXTURE)
    bus = EventBus()
    store = LectureStateStore(bus, "it", LectureSetup(subject="Biology", grade_level="7",
                                                      expected_topic="Photosynthesis"))
    store.attach()
    deck = Deck(bus)
    deck.attach()
    client = httpx.AsyncClient(transport=httpx.MockTransport(SlideLLM()))
    router = LLMRouter([Entry(OpenAICompatProvider(ProviderConfig(name="m", base_url="https://m.test/v1", model="m"),
                                                   "k", client), RateLimiter(1000, 10**6))],
                       RouterSettings(timeout_s=2.0, retries=0))
    settings = UnderstandingSettings(min_call_interval_s=8.0 / SPEED)
    svc = UnderstandingService(bus, store, Interpreter(router, settings.interpreter), HashEmbedder(), settings,
                               speed=SPEED)
    eng = PresentationEngine(bus, store, deck, PresentationSettings(min_dwell_s=15.0), speed=SPEED)
    svc.attach()
    eng.attach()
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await LectureSimulator(bus, script, speed=SPEED, vad=True).run()
    assert await svc.flush(timeout=20.0)
    await bus.drain()
    await eng.flush_pending()

    titles = [s.title for s in deck.slides]
    assert titles[0] == "Photosynthesis" and deck.slides[0].layout == "title"
    order = ["What is photosynthesis?", "What photosynthesis needs", "How photosynthesis works",
             "Why photosynthesis matters", "Comparison of Respiration"]
    positions = [next(i for i, t in enumerate(titles) if t.startswith(o)) for o in order]
    assert positions == sorted(positions), titles                    # facets in lecture order
    assert any(s.layout == "process_flow" for s in deck.slides)
    shown = json.dumps([s.model_dump() for s in deck.slides])
    assert WRONG not in shown                                        # held for the teacher
    for meta in ("science books", "Look at the screen"):
        assert meta not in shown
    # teacher keeps the statement as said: it appears on the slide it belonged to
    cid = store.snapshot().concerns[0].id
    await bus.publish(CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": "keep"})))
    await bus.drain()
    assert WRONG in json.dumps([s.model_dump() for s in deck.slides])
    assert len(titles) <= 9, titles                                  # a new concept is not a new slide
    await eng.stop()
    await svc.stop()
    await bus.close()
    await client.aclose()
