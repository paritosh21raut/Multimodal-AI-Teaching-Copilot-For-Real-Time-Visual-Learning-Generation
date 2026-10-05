"""Photosynthesis fixture through the real understanding stack and the real Groq/OpenRouter APIs (opt-in).

Run: .venv/Scripts/python -m pytest -m live_llm tests/e2e/test_understanding_live.py -s
Takes ~2 minutes (lecture played at ×2; the production rate floor is scaled to lecture time).
"""
from pathlib import Path

import httpx
import pytest

from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT, load_config
from copilot.core.events import InterpretationReady, InterpretRequested, TranscriptFinal, UtteranceClassified
from copilot.core.memory import titles_match
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.llm.router import build_router
from copilot.sim.simulator import LectureSimulator, parse_script
from copilot.understanding.embedder import MiniLmEmbedder
from copilot.understanding.interpreter import Interpreter
from copilot.understanding.service import UnderstandingService, UnderstandingSettings

pytestmark = pytest.mark.live_llm
FIXTURE = Path(__file__).parents[1] / "fixtures" / "lectures" / "photosynthesis.txt"
SPEED = 2.0


async def test_photosynthesis_live():
    config = load_config()
    script = parse_script(FIXTURE)
    bus = EventBus()
    store = LectureStateStore(bus, "live", LectureSetup(subject="Biology", grade_level="7",
                                                        expected_topic="Photosynthesis"))
    store.attach()
    emb = MiniLmEmbedder(PROJECT_ROOT / "models" / "minilm")
    emb.load()
    settings = UnderstandingSettings.from_config(config)
    settings.min_call_interval_s /= SPEED
    events = []

    async def rec(e):
        events.append(e)

    bus.subscribe("rec", rec, [TranscriptFinal, UtteranceClassified, InterpretRequested, InterpretationReady])
    async with httpx.AsyncClient() as client:
        router = build_router(config, client)
        assert router.entries, "no LLM keys configured"
        svc = UnderstandingService(bus, store, Interpreter(router, settings.interpreter), emb, settings, speed=SPEED)
        svc.attach()
        await LectureSimulator(bus, script, speed=SPEED).run()
        assert await svc.flush(timeout=90)
        await svc.stop()
    await bus.close()

    readies = [e for e in events if isinstance(e, InterpretationReady)]
    for r in readies:
        it = r.interpretation
        print(f"{it.topic} > {it.subtopic} ({it.relation}) {[a.act for a in it.acts]} via {r.provider or 'FALLBACK'}")
    s = store.snapshot()
    st = svc.stats
    assert st.fallbacks <= 1
    assert max(st.prompt_tokens) <= settings.interpreter.prompt_budget_tokens
    lecture_min = max(e.segment.end for e in events if isinstance(e, TranscriptFinal)) / 60
    assert st.requests / lecture_min <= 8.0

    titles = [t.title for t in s.outline]
    assert any(titles_match(t, "Photosynthesis") for t in titles)
    assert any(titles_match(t, "Respiration") for t in titles)
    assert titles_match(s.topic(s.current_topic_id).title, "Respiration")
    photo = next(t for t in s.outline if titles_match(t.title, "Photosynthesis"))
    subs = " ".join(x.title.lower() for x in photo.subtopics)
    assert "process" in subs and "importance" in subs, subs
    assert any("oxygen" in c.claim.lower() for c in s.concerns), s.concerns
    # classroom talk never sent
    kinds = {e.segment_id: e.kind for e in events if isinstance(e, UtteranceClassified)}
    sent = {sid for e in events if isinstance(e, InterpretRequested) for sid in e.segment_ids}
    assert not any(kinds[sid] in ("classroom_management", "meta", "filler") for sid in sent)
