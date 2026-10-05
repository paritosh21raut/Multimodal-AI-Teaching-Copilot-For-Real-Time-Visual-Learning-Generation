"""UtteranceFilter + ConceptTracker (deterministic parts)."""
from pathlib import Path

import numpy as np
import pytest

from copilot.sim.simulator import parse_script
from copilot.understanding.filter import UtteranceFilter
from copilot.understanding.tracker import ConceptTracker, candidate_phrases, find_cues

FIXTURE = Path(__file__).parents[1] / "fixtures" / "lectures" / "photosynthesis.txt"


def test_fixture_labelled_lines():
    """@expect kind=meta lines are excluded; every other fixture line reaches the buffer."""
    f = UtteranceFilter()
    for u in parse_script(FIXTURE).utterances:
        c = f.classify(u.text)
        if u.expect.get("kind") == "meta":
            assert not c.to_buffer, (u.text, c)
        else:
            assert c.to_buffer, (u.text, c)


@pytest.mark.parametrize("text,kind", [
    ("Okay.", "filler"),
    ("Um, so, right.", "filler"),
    ("Please open your notebooks to page 42.", "classroom_management"),
    ("Silence please, sit down.", "classroom_management"),
    ("Can everyone see this?", "meta"),
    ("Any questions?", "question_to_class"),
])
def test_non_content_classes(text, kind):
    assert UtteranceFilter().classify(text).kind == kind


def test_content_with_meta_phrase_is_kept_and_flagged():
    c = UtteranceFilter().classify("As you can see on the board, chlorophyll absorbs red and blue light strongly.")
    assert c.kind == "content" and c.maybe_meta and c.to_buffer


def test_content_question_is_buffered():
    c = UtteranceFilter().classify("Can anyone tell me why leaves are green and what pigment causes it?")
    assert c.to_buffer and not c.maybe_meta


def test_cues_strong_only_at_start():
    cues, strong = find_cues("Now let's see how the process happens step by step.")
    assert strong and "now let's" in cues and "step" in cues
    cues, strong = find_cues("Plants grow well, and after a long while now let's say they flower.")
    assert not strong


def test_cue_duplicates_collapsed():
    cues, strong = find_cues("Now, the next topic is respiration, which is different from photosynthesis.")
    assert strong
    assert "next topic" not in cues and "the next topic" in cues  # sub-cue dropped
    assert "different from" in cues


def test_candidate_phrases_skip_stop_words():
    ph = candidate_phrases("Carbon dioxide enters the leaves through stomata.")
    assert "carbon dioxide" in ph and "stomata" in ph and "the" not in ph


def _unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


def test_shift_score_and_boundary():
    t = ConceptTracker(shift_threshold=0.75)
    a = t.update("Photosynthesis makes food.", _unit(1, 0, 0))
    assert a.shift_score == 0.0 and not a.boundary
    b = t.update("Plants use light for photosynthesis.", _unit(0.95, 0.3, 0))
    assert b.raw_shift < 0.1 and not b.boundary
    c = t.update("Volcanoes erupt magma.", _unit(0, 0, 1))
    assert c.raw_shift > 0.75 and c.boundary
    # smoothing window restarts at a boundary, so the next on-topic line is not penalised by the old concept
    d = t.update("Lava cools into rock.", _unit(0.1, 0, 1))
    assert d.raw_shift < 0.5


def test_tracker_without_embedding_uses_cues():
    t = ConceptTracker()
    s = t.update("Now let's move on to respiration.", None)
    assert s.boundary and s.shift_score == 0.0
    assert not t.update("Respiration releases energy.", None).boundary


def test_keyphrase_memory_is_bounded():
    t = ConceptTracker(phrase_memory=5)
    for i in range(50):
        t.update(f"term{i} appears here with word{i}", None)
    assert len(t._phrase_hist) == 5
    assert all(v > 0 for v in t._phrase_df.values())
    assert len(t._phrase_df) <= 5 * 10


def test_short_facet_question_is_a_strong_cue():
    for q in ("Why is photosynthesis important for us?", "Why it matters?", "How does it work?",
              "What does a plant need?"):
        cues, strong = find_cues(q)
        assert strong and "facet question" in cues, q
    for q in ("Why do you think the leaves of most plants turn towards the window in our classroom?",
              "Plants need light, why?", "What a plant needs is light."):
        assert not find_cues(q)[1], q
