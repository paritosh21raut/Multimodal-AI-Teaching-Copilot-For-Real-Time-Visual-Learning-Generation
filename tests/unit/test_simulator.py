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
