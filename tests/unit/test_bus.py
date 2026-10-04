import asyncio

import pytest

from copilot.core.bus import EventBus
from copilot.core.events import Lifecycle, LifecycleChanged, TranscriptFinal, TranscriptSegment


def seg(text: str, i: int = 0) -> TranscriptFinal:
    return TranscriptFinal(segment=TranscriptSegment(text=text, start=i, end=i + 1))


async def test_fanout_preserves_order_per_subscriber():
    bus = EventBus()
    a, b = [], []

    async def ha(e):
        a.append(e.segment.text)

    async def hb(e):
        await asyncio.sleep(0.001)  # slower subscriber
        b.append(e.segment.text)

    bus.subscribe("a", ha, [TranscriptFinal])
    bus.subscribe("b", hb, [TranscriptFinal])
    for i in range(20):
        await bus.publish(seg(str(i), i))
    await bus.close()
    assert a == [str(i) for i in range(20)]
    assert b == a


async def test_type_filtering_and_wildcard():
    bus = EventBus()
    only_tf, everything = [], []

    async def h1(e):
        only_tf.append(e.type)

    async def h2(e):
        everything.append(e.type)

    bus.subscribe("tf", h1, [TranscriptFinal])
    bus.subscribe("all", h2)
    await bus.publish(LifecycleChanged(state=Lifecycle.READY))
    await bus.publish(seg("x"))
    await bus.close()
    assert only_tf == ["TranscriptFinal"]
    assert everything == ["LifecycleChanged", "TranscriptFinal"]


async def test_drop_oldest_overflow_keeps_latest():
    bus = EventBus()
    got = []
    gate = asyncio.Event()

    async def slow(e):
        await gate.wait()
        got.append(e.segment.text)

    sub = bus.subscribe("slow", slow, [TranscriptFinal], queue_size=2, overflow="drop_oldest")
    await bus.publish(seg("0"))
    await asyncio.sleep(0)  # consumer takes "0" and blocks on the gate
    for i in range(1, 6):
        await bus.publish(seg(str(i)))
    gate.set()
    await bus.close()
    assert got == ["0", "4", "5"]
    assert sub.dropped == 3


async def test_failing_handler_does_not_kill_bus():
    bus = EventBus()
    got = []

    async def flaky(e):
        if e.segment.text == "bad":
            raise RuntimeError("boom")
        got.append(e.segment.text)

    bus.subscribe("flaky", flaky, [TranscriptFinal])
    for t in ("ok1", "bad", "ok2"):
        await bus.publish(seg(t))
    await bus.close()
    assert got == ["ok1", "ok2"]


async def test_session_id_stamped_and_closed_bus_rejects_subscribe():
    bus = EventBus()
    bus.session_id = "s1"
    got = []

    async def h(e):
        got.append(e.session_id)

    bus.subscribe("h", h)
    await bus.publish(seg("x"))
    await bus.close()
    assert got == ["s1"]
    with pytest.raises(RuntimeError):
        bus.subscribe("late", h)
