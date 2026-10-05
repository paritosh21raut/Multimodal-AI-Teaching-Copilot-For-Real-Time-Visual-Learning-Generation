"""State store application of interpretations: outline, current ids, rolling memory, concerns."""
from copilot.core.bus import EventBus
from copilot.core.events import (
    Command,
    CommandReceived,
    ConcernRaised,
    InterpretationReady,
    StateChanged,
)
from copilot.core.interpretation import ConcernItem, Interpretation
from copilot.core.memory import rebuild_summary, titles_match
from copilot.core.state import MAX_SUBTOPICS, MAX_TOPICS, SUMMARY_MAX_TOKENS, LectureStateStore
from copilot.core.textutil import approx_tokens


def ready(rid, topic, subtopic="", relation="same_concept", summary="", concerns=(), provider="groq", fallback=False):
    return InterpretationReady(
        request_id=rid, segment_ids=["seg1", "seg2"], provider=provider, fallback=fallback,
        interpretation=Interpretation(topic=topic, subtopic=subtopic, relation=relation, summary_delta=summary,
                                      concerns=list(concerns)),
    )


async def run(events):
    bus = EventBus()
    store = LectureStateStore(bus, "s")
    store.attach()
    seen = []

    async def watch(e):
        seen.append(e)

    bus.subscribe("watch", watch, [StateChanged, ConcernRaised])
    for e in events:
        await bus.publish(e)
    await bus.close()
    return store, seen


def test_titles_match():
    assert titles_match("Requirements", "requirement")
    assert titles_match("Process of Photosynthesis", "Photosynthesis Process")
    assert not titles_match("Photosynthesis", "Respiration")
    assert not titles_match("Light Reactions", "Dark Reactions")
    assert titles_match("Respiration", "Respiration in Plants")
    assert not titles_match("Respiration", "Aerobic Respiration in Plants")


async def test_topics_subtopics_and_current_ids():
    store, seen = await run([
        ready("r1", "Photosynthesis", "Definition", "new_topic", "Defined photosynthesis."),
        ready("r2", "photosynthesis", "Requirements", "sibling_concept", "Listed four needs."),
        ready("r3", "Photosynthesis", "requirement", "same_concept"),
        ready("r4", "Respiration", "", "new_topic", "Started respiration."),
        ready("r5", "Football", "Weekend match", "digression", "Talked about football."),
    ])
    s = store.snapshot()
    assert [t.title for t in s.outline] == ["Photosynthesis", "Respiration"]  # digression adds nothing
    assert [x.title for x in s.outline[0].subtopics] == ["Definition", "Requirements"]
    assert s.topic(s.current_topic_id).title == "Respiration" and s.current_subtopic_id is None
    assert s.outline[0].subtopics[0].summary == "Defined photosynthesis."
    assert s.stats.llm_calls == 5 and s.last_interpretation_id == "r5"
    changes = [e.changes for e in seen if isinstance(e, StateChanged)]
    assert "topic" in changes[0] and "subtopic" in changes[1] and "topic" not in changes[2]
    assert "topic" not in changes[4]


async def test_subtopic_equal_to_topic_is_not_a_node():
    store, _ = await run([ready("r1", "Photosynthesis", "photosynthesis", "new_topic"),
                          ready("r2", "Photosynthesis", "Photosynthesis Equation", "sibling_concept")])
    assert [x.title for x in store.snapshot().outline[0].subtopics] == ["Photosynthesis Equation"]


async def test_outline_caps_bounded():
    events = [ready(f"t{i}", f"Topic {i}", f"Sub {i}", "new_topic") for i in range(MAX_TOPICS + 10)]
    events += [ready(f"s{i}", "Topic 29", f"Facet {i}", "sibling_concept") for i in range(MAX_SUBTOPICS + 5)]
    store, _ = await run(events)
    s = store.snapshot()
    assert len(s.outline) == MAX_TOPICS
    assert s.topic(s.current_topic_id).title == "Topic 29"
    assert len(s.topic(s.current_topic_id).subtopics) == MAX_SUBTOPICS
    assert s.subtopic().title == f"Facet {MAX_SUBTOPICS + 4}"


async def test_rolling_summary_replaced_and_bounded():
    events = [ready(f"r{i}", "Photosynthesis", summary=f"Sentence {i} about leaves, light, water and sugar.")
              for i in range(100)]
    store, _ = await run(events)
    s = store.snapshot()
    assert approx_tokens(s.rolling_summary) <= SUMMARY_MAX_TOKENS
    assert s.rolling_summary.endswith("Sentence 99 about leaves, light, water and sugar.")
    assert "Sentence 0 " not in s.rolling_summary
    assert len(s.summary_deltas) < 20


def test_rebuild_summary_clips_single_long_delta():
    text, kept = rebuild_summary(["word " * 500], 50)
    assert 0 < approx_tokens(text) <= 50 and len(kept) == 1


async def test_concerns_raised_and_resolved():
    c = ConcernItem(claim="Plants take in oxygen", issue="reversed", suggested_correction="CO2 in", confidence=0.9,
                    lines=[2])
    store, seen = await run([ready("r1", "Photosynthesis", concerns=[c])])
    s = store.snapshot()
    assert len(s.concerns) == 1 and s.concerns[0].segment_id == "seg2" and s.concerns[0].status == "open"
    raised = [e for e in seen if isinstance(e, ConcernRaised)]
    assert raised and raised[0].concern["claim"] == "Plants take in oxygen"

    bus = EventBus()
    store2 = LectureStateStore(bus, "s")
    store2.attach()
    await bus.publish(ready("r1", "Photosynthesis", concerns=[c]))
    await bus.drain()
    cid = store2.snapshot().concerns[0].id
    await bus.publish(CommandReceived(command=Command(kind="resolve_concern", args={"id": cid, "action": "accept"})))
    await bus.close()
    assert store2.snapshot().concerns[0].status == "accepted"


async def test_fallback_counted_and_wait_applied():
    bus = EventBus()
    store = LectureStateStore(bus, "s")
    store.attach()
    assert not await store.wait_applied("nope", timeout=0.05)
    await bus.publish(ready("r1", "Cells", provider="", fallback=True))
    assert await store.wait_applied("r1", timeout=2.0)
    await bus.close()
    s = store.snapshot()
    assert s.stats.fallbacks == 1 and s.stats.llm_calls == 0


async def test_wait_applied_released_even_if_apply_fails(monkeypatch):
    """Review fix: a failing apply must not stall the understanding worker for the full timeout."""
    bus = EventBus()
    store = LectureStateStore(bus, "s")
    store.attach()

    def broken(ev):
        raise RuntimeError("bad state")

    monkeypatch.setattr(store, "_apply_interpretation", broken)
    await bus.publish(ready("r1", "Cells"))
    assert await store.wait_applied("r1", timeout=1.0)
    await bus.close()


async def test_concern_kind_lines_and_resolution_event():
    from copilot.core.events import ConcernResolved

    c = ConcernItem(claim="6H2", issue="mis-heard", suggested_correction="6H2O", confidence=0.4, lines=[1, 2],
                    kind="transcription")
    bus = EventBus()
    store = LectureStateStore(bus, "s")
    store.attach()
    seen = []

    async def watch(e):
        seen.append(e)

    bus.subscribe("watch_resolved", watch, [ConcernResolved])
    await bus.publish(ready("r1", "Photosynthesis", concerns=[c]))
    await bus.drain()
    got = store.snapshot().concerns[0]
    assert got.kind == "transcription" and got.segment_ids == ["seg1", "seg2"] and got.request_id == "r1"
    await bus.publish(CommandReceived(command=Command(kind="resolve_concern", args={"id": got.id, "action": "keep"})))
    await bus.drain()
    assert [(e.concern_id, e.status) for e in seen] == [(got.id, "kept")]
