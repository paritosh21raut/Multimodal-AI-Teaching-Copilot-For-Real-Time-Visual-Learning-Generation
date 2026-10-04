import numpy as np
import pytest

from copilot.audio.segmenter import SegmenterConfig, UtteranceSegmenter

F = 512
FRAME_S = F / 16_000  # 0.032


def run(probs, cfg=SegmenterConfig(), flush=False):
    seg = UtteranceSegmenter(cfg)
    out = []
    for i, p in enumerate(probs):
        out += seg.push(np.full(F, float(i), dtype=np.float32), p)
    if flush:
        out += seg.flush()
    return seg, out


def test_single_utterance_with_preroll_and_pad():
    seg, out = run([0.0] * 20 + [0.9] * 50 + [0.0] * 30)
    assert len(out) == 1
    u = out[0]
    # 6 frames pre-roll (200 ms) + 50 speech + 6 frames pad
    assert u.start == pytest.approx((20 - 6) * FRAME_S)
    assert u.end == pytest.approx(u.start + 62 * FRAME_S)
    assert len(u.audio) == 62 * F
    # audio is contiguous and in order: frame values are their indices
    assert u.audio[0] == 14 and u.audio[-1] == 14 + 61
    assert not u.forced_split


def test_short_burst_is_dropped():
    seg, out = run([0.0] * 10 + [0.9] * 5 + [0.0] * 30)
    assert out == []
    assert seg.dropped_short == 1


def test_short_pause_does_not_split():
    # 10 frames (320 ms) of silence < 600 ms hangover → one utterance
    _, out = run([0.9] * 30 + [0.1] * 10 + [0.9] * 30 + [0.0] * 30)
    assert len(out) == 1
    assert out[0].duration == pytest.approx((70 + 6) * FRAME_S)


def test_long_pause_splits_into_two():
    _, out = run([0.9] * 30 + [0.0] * 25 + [0.9] * 30 + [0.0] * 30)
    assert len(out) == 2
    assert out[1].start > out[0].end - 1e-9


def test_hysteresis_between_thresholds_counts_as_speech():
    # 0.4 is below start (0.5) but above end (0.35): keeps an utterance alive, cannot start one
    _, out = run([0.4] * 40)
    assert out == []
    _, out = run([0.9] * 10 + [0.4] * 40 + [0.0] * 30)
    assert len(out) == 1
    assert out[0].duration >= 50 * FRAME_S


def test_max_length_forces_split_at_lowest_probability_frame():
    cfg = SegmenterConfig(max_utterance_s=6.4, split_search_s=2.0)  # 200 frames, search last ~62
    probs = [0.9] * 300
    probs[170] = 0.36  # lowest point inside the search window, still "speech"
    _, out = run(probs + [0.0] * 30, cfg)
    assert len(out) == 2
    first, second = out
    assert first.forced_split
    assert first.end == pytest.approx(171 * FRAME_S)
    assert second.start == pytest.approx(first.end)  # no audio lost between parts


def test_flush_emits_pending_speech():
    _, out = run([0.9] * 40, flush=True)
    assert len(out) == 1 and out[0].duration == pytest.approx(40 * FRAME_S)
