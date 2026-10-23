import pytest

from copilot.core.bus import EventBus
from copilot.sim.simulator import LectureSimulator, ScriptError, parse_script, utterance_duration

SCRIPT = """
# comment
@setup subject=Biology grade=7 topic="Plant life"
@expect kind=meta
Take out your books.
[pause 2]
[pause 0.5]
@expect topic=Photosynthesis act=definition
Photosynthesis is how plants make food.
"""


def test_parse_setup_expect_and_pauses():
    s = parse_script(SCRIPT)
    assert s.setup == {"subject": "Biology", "grade": "7", "topic": "Plant life"}
    assert [u.text for u in s.utterances] == ["Take out your books.", "Photosynthesis is how plants make food."]
    assert s.utterances[0].expect == {"kind": "meta"}
    assert s.utterances[1].pause_before == 2.5
    assert s.utterances[1].expect == {"topic": "Photosynthesis", "act": "definition"}


def test_unknown_directive_and_bad_kv_raise():
    with pytest.raises(ScriptError):
        parse_script("@bogus x=1\nhello")
    with pytest.raises(ScriptError):
        parse_script("@expect novalue\nhello")


def test_duration_respects_wpm_and_minimum():
    assert utterance_duration("one two", 150, 1.0) == 1.0
    assert utterance_duration(" ".join(["w"] * 30), 150, 1.0) == pytest.approx(12.0)


async def test_timeline_is_monotonic_and_includes_pauses():
    sim = LectureSimulator(EventBus(), parse_script(SCRIPT), words_per_minute=150, min_utterance_s=1.0)
    tl = sim.timeline()
    assert tl[0].start == 0.0
    assert tl[1].start == pytest.approx(tl[0].end + 2.5)
    assert all(s.source == "sim" for s in tl)


async def test_vad_mode_publishes_voice_during_utterances_and_silence_in_pauses():
    from copilot.core.events import AudioLevel, TranscriptFinal

    bus = EventBus()
    seen = []

    async def watch(e):
        seen.append(e)

    bus.subscribe("watch", watch, [AudioLevel, TranscriptFinal])
    sim = LectureSimulator(bus, parse_script(SCRIPT), words_per_minute=150, min_utterance_s=1.0, speed=5.0, vad=True)
    await sim.run()
    await bus.drain()
    segs = sim.timeline()
    levels = [e for e in seen if isinstance(e, AudioLevel)]
    assert levels and sim.published == 2
    # the 2.5 s scripted pause between the utterances is silent; utterance time is voiced
    first_final = next(i for i, e in enumerate(seen) if isinstance(e, TranscriptFinal))
    after = [e.voice for e in seen[first_final + 1:] if isinstance(e, AudioLevel)]
    n_pause = int(2.5 / 0.2)
    assert not any(after[: n_pause - 1]) and all(after[n_pause + 1:])
    assert segs[1].start - segs[0].end == pytest.approx(2.5)


@pytest.mark.parametrize("vad", [False, True])
async def test_a_command_is_pressed_after_the_pause_not_with_the_line_before(vad):
    # C1 live run: Imagine was pressed at once after "Back to the slides." and the end cue was ignored
    import asyncio

    from copilot.core.events import CommandReceived, TranscriptFinal

    bus = EventBus()
    seen = []
    loop = asyncio.get_running_loop()

    async def watch(e):
        seen.append((type(e).__name__, loop.time()))

    bus.subscribe("watch", watch, [TranscriptFinal, CommandReceived])
    script = parse_script("Back to the slides.\n[pause 2]\n@command imagine_mode on=true\nA dog in a garden.\n"
                          "[pause 1]\n@command imagine_mode on=false\n")
    sim = LectureSimulator(bus, script, speed=10.0, vad=vad)
    await sim.run()
    await bus.drain()
    kinds = [k for k, _ in seen]
    assert kinds == ["TranscriptFinal", "CommandReceived", "TranscriptFinal", "CommandReceived"]
    assert seen[1][1] - seen[0][1] >= 0.15      # the 2 s pause (at 10x) passed before the press
    assert seen[3][1] - seen[2][1] >= 0.08      # the end press waits for the last line to be handled
