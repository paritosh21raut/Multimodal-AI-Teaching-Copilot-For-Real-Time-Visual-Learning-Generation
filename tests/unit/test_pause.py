"""Pause (verify round 4 step C, user 2026-10-06): replaces Freeze. While the lecture is paused nothing the teacher
says is interpreted or put on a slide (a break); the teacher can still navigate and edit. Resume continues."""
import pytest
from pydantic import ValidationError

from copilot.app.main import lifecycle_for_command
from copilot.core.bus import EventBus
from copilot.core.events import (
    Command,
    DeckState,
    Lifecycle,
    LifecycleChanged,
    TranscriptFinal,
    TranscriptSegment,
)
from copilot.core.state import LectureStateStore
from copilot.understanding.service import UnderstandingService


def test_pause_and_resume_switch_only_a_running_lecture():
    assert lifecycle_for_command("pause", Lifecycle.LIVE) == Lifecycle.PAUSED
    assert lifecycle_for_command("resume", Lifecycle.PAUSED) == Lifecycle.LIVE
    assert lifecycle_for_command("pause", Lifecycle.PAUSED) is None   # already paused: no event
    assert lifecycle_for_command("resume", Lifecycle.LIVE) is None
    assert lifecycle_for_command("pause", Lifecycle.READY) is None    # not started yet
    assert lifecycle_for_command("pause", Lifecycle.ENDING) is None
    assert lifecycle_for_command("next", Lifecycle.LIVE) is None


def test_freeze_is_replaced_by_pause():
    for kind in ("freeze", "unfreeze"):
        with pytest.raises(ValidationError):
            Command(kind=kind)
    assert "frozen" not in DeckState.model_fields


async def test_speech_while_paused_is_not_interpreted():
    bus = EventBus()
    store = LectureStateStore(bus, "p")
    store.attach()
    svc = UnderstandingService(bus, store, interpreter=None, embedder=None)  # type: ignore[arg-type]
    svc.attach()

    async def say(text: str, t: float) -> None:
        await bus.publish(TranscriptFinal(segment=TranscriptSegment(text=text, start=t, end=t + 2.0, source="sim")))
        await bus.drain()

    lines = ["Photosynthesis makes glucose in the leaves.",
             "Okay everyone, the canteen opens at twelve today.",
             "Chlorophyll absorbs the light energy."]
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await say(lines[0], 0.0)
    await bus.publish(LifecycleChanged(state=Lifecycle.PAUSED))
    await say(lines[1], 3.0)
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await say(lines[2], 9.0)
    buffered = [x.text for x in svc.buffer.lines]
    await svc.stop()
    await bus.close()
    assert buffered == [lines[0], lines[2]]
    assert svc.stats.paused_segments == 1
    assert store.snapshot().stats.segments == 3  # still in the event log and the session statistics


async def test_story_lines_are_not_interpreted_but_still_classified():
    """V3 P1c (test58): while a story is open its lines are drawn and recapped by the story (47 understanding calls,
    ~100k tokens were spent on them); they are still classified (the story detector needs it)."""
    from copilot.core.events import SimulationModeChanged, UtteranceClassified

    bus = EventBus()
    store = LectureStateStore(bus, "p")
    store.attach()
    svc = UnderstandingService(bus, store, interpreter=None, embedder=None)  # type: ignore[arg-type]
    svc.attach()
    kinds = []

    async def keep(ev):
        kinds.append(ev.kind)
    bus.subscribe("t", keep, [UtteranceClassified])

    async def say(text: str, t: float) -> None:
        await bus.publish(TranscriptFinal(segment=TranscriptSegment(text=text, start=t, end=t + 2.0, source="sim")))
        await bus.drain()

    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await say("Photosynthesis makes glucose in the leaves.", 0.0)
    await bus.publish(SimulationModeChanged(on=True, template="story"))
    await say("Ravi picked up the apple and walked to the village.", 3.0)
    await bus.publish(SimulationModeChanged(on=False, template="story"))
    await say("Chlorophyll absorbs the light energy.", 9.0)
    buffered = [x.text for x in svc.buffer.lines]
    await svc.stop()
    await bus.close()
    assert buffered == ["Photosynthesis makes glucose in the leaves.", "Chlorophyll absorbs the light energy."]
    assert len(kinds) == 3 and svc.stats.story_segments == 1
