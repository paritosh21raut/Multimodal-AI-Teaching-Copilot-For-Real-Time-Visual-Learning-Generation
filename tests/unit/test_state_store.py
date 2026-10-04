from copilot.core.bus import EventBus
from copilot.core.events import Lifecycle, LifecycleChanged, StateChanged, TranscriptFinal, TranscriptSegment
from copilot.core.state import LectureStateStore


async def test_store_applies_events_and_versions():
    bus = EventBus()
    store = LectureStateStore(bus, "s1")
    store.attach()
    changes = []

    async def on_change(e):
        changes.append((e.version, e.changes))

    bus.subscribe("watch", on_change, [StateChanged])
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))  # no-op: same state
    await bus.publish(TranscriptFinal(segment=TranscriptSegment(text="a b c", start=0, end=2)))
    await bus.publish(TranscriptFinal(segment=TranscriptSegment(text="d e", start=2, end=3.5)))
    await bus.close()

    s = store.snapshot()
    assert s.lifecycle == Lifecycle.LIVE
    assert s.stats.segments == 2 and s.stats.words == 5
    assert s.lecture_clock_s == 3.5
    assert s.version == 3
    assert changes == [(1, ["lifecycle"]), (2, ["stats"]), (3, ["stats"])]


async def test_snapshot_is_a_copy():
    bus = EventBus()
    store = LectureStateStore(bus, "s1")
    snap = store.snapshot()
    snap.stats.words = 999
    assert store.snapshot().stats.words == 0
    await bus.close()
