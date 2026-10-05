"""DiscourseBuffer + Gate decisions (pure, lecture time)."""
from copilot.understanding.gate import BufferedLine, DiscourseBuffer, Gate, GateConfig


def line(i, text, start, end):
    return BufferedLine(f"s{i}", text, start, end)


TEN = "one two three four five six seven eight nine ten."


def test_empty_never_fires():
    assert Gate().check(DiscourseBuffer(), now=100.0, flushing=True) is None


def test_pause_needs_min_words_and_sentence_end():
    g, b = Gate(GateConfig(pause_min_words=12)), DiscourseBuffer()
    b.add(line(1, TEN, 0, 4))
    assert g.check(b, now=6.0) is None             # 10 words < 12
    b.add(line(2, "plants make food", 4, 5))       # 13 words, but no sentence end
    assert g.check(b, now=7.0) is None
    b.add(line(3, "using light.", 5, 6))
    assert g.check(b, now=6.5) is None             # pause 0.5 s
    assert g.check(b, now=7.3) == "pause"
    assert g.check(b, now=7.3, silence_s=0.2) is None  # VAD says the speaker is still talking


def test_words_and_max_wait():
    g, b = Gate(GateConfig(max_words=20, max_wait_s=12)), DiscourseBuffer()
    b.add(line(1, "a b c d e f.", 0, 1))
    assert g.check(b, now=1.1, silence_s=0) is None
    assert g.check(b, now=13.1, silence_s=0) == "max_wait"
    b.add(line(2, " ".join(["w"] * 20) + ".", 1, 8))
    assert g.check(b, now=8.0) == "words"


def test_boundary_sends_lines_before_the_cut_first():
    g, b = Gate(), DiscourseBuffer()
    b.add(line(1, "Chlorophyll is green.", 0, 2))
    b.add(line(2, "Now let's see the process.", 2, 4), boundary=True)
    b.add(line(3, "First light is absorbed.", 4, 6))
    assert g.check(b, now=4.0) == "boundary"
    assert [l.segment_id for l in b.take(600)] == ["s1"]
    assert not b.cut_pending
    assert [l.segment_id for l in b.lines] == ["s2", "s3"]


def test_boundary_on_first_line_is_not_a_cut():
    b = DiscourseBuffer()
    b.add(line(1, "Now let's begin with cells.", 0, 2), boundary=True)
    assert not b.cut_pending


def test_seal_and_boundaries_make_separate_units_in_order():
    """Review fix: a boundary arriving after a seal must not be lost (it used to merge two concepts)."""
    b = DiscourseBuffer()
    b.add(line(1, "x.", 0, 1))
    b.seal()
    b.seal()                                      # idempotent: no empty unit
    b.add(line(2, "y.", 1, 2))
    b.add(line(3, "z.", 2, 3), boundary=True)
    b.add(line(4, "w.", 3, 4))
    assert [l.segment_id for l in b.take(600)] == ["s1"]
    assert [l.segment_id for l in b.take(600)] == ["s2"]
    assert [l.segment_id for l in b.take(600)] == ["s3", "s4"]
    assert b.empty and not b.cut_pending


def test_random_add_seal_take_preserves_order():
    import random
    rnd = random.Random(7)
    for _ in range(300):
        b, taken, n = DiscourseBuffer(), [], 0
        for _ in range(40):
            r = rnd.random()
            if r < 0.5:
                b.add(line(n, "word " * rnd.randint(1, 30) + ".", n, n + 1), boundary=rnd.random() < 0.2)
                n += 1
            elif r < 0.65:
                b.seal()
            elif not b.empty:
                taken += b.take(rnd.choice([20, 60, 600]))
        while not b.empty:
            taken += b.take(600)
        assert [l.segment_id for l in taken] == [f"s{i}" for i in range(n)]


def test_cap_splits_in_order_without_loss():
    g, b = Gate(GateConfig(buffer_cap_tokens=30)), DiscourseBuffer()
    for i in range(10):
        b.add(line(i, "photosynthesis converts light energy into chemical energy.", i, i + 1))
    assert g.check(b, now=10.0) == "cap"
    taken = []
    while not b.empty:
        chunk = b.take(30)
        assert chunk and sum(l.tokens for l in chunk) <= 30 or len(chunk) == 1
        taken += chunk
    assert [l.segment_id for l in taken] == [f"s{i}" for i in range(10)]


def test_oversized_single_line_still_taken():
    b = DiscourseBuffer()
    b.add(line(1, " ".join(["word"] * 500), 0, 60))
    assert len(b.take(50)) == 1 and b.empty


def test_flush_fires_for_any_pending_content():
    g, b = Gate(), DiscourseBuffer()
    b.add(line(1, "short", 0, 1))
    assert g.check(b, now=1.0) is None
    assert g.check(b, now=1.0, flushing=True) == "flush"


# ---- M3 live-mic fixes: hold fragments and lone short lines (session 20261005-054752-39bc) ----

def test_max_wait_holds_a_sentence_opening_fragment_for_its_continuation():
    g, b = Gate(GateConfig(max_wait_s=12, hold_s=6)), DiscourseBuffer()
    b.add(line(1, "The chemical equation is 6CO2 plus 6H2 plus light gives us C6H12O6 plus 6O2.", 48.6, 60.5))
    b.add(line(2, "The output of this process is", 61.1, 62.9))
    assert g.check(b, now=72.9, silence_s=0.0) is None          # max_wait reached, but mid-sentence
    b.add(line(3, "The plants creates glucose for food and energy while they release oxygen.", 63.4, 73.7))
    assert g.check(b, now=74.0, silence_s=0.0) == "max_wait"     # continuation arrived: one coherent unit
    assert [l.segment_id for l in b.take(600)] == ["s1", "s2", "s3"]


def test_fragment_hold_is_bounded():
    g, b = Gate(GateConfig(max_wait_s=12, hold_s=6)), DiscourseBuffer()
    b.add(line(1, "The output of this process is", 0, 2))
    assert g.check(b, now=19.9, silence_s=10) is None
    assert g.check(b, now=20.0, silence_s=10) == "max_wait"      # 12 + 6 s: sent anyway, nothing is lost


def test_lone_short_line_is_not_sent_alone_at_max_wait():
    g, b = Gate(GateConfig(max_wait_s=12, hold_s=6)), DiscourseBuffer()
    b.add(line(1, "which comes from the Sun.", 46.2, 48.2))
    assert g.check(b, now=60.2, silence_s=0.0) is None           # speaker still talking: wait for more
    b.add(line(2, "The chemical equation is 6CO2 plus 6H2 plus light gives us glucose.", 48.6, 60.5))
    assert g.check(b, now=60.6, silence_s=0.0) == "max_wait"


def test_pause_fires_on_a_short_complete_unit_and_long_pause_on_a_tiny_one():
    g, b = Gate(), DiscourseBuffer()
    b.add(line(1, "Let's talk about how photosynthesis works.", 18.3, 21.1))   # 6 words
    assert g.check(b, now=21.5, silence_s=1.0) is None
    assert g.check(b, now=21.5, silence_s=1.3) == "pause"
    b2 = DiscourseBuffer()
    b2.add(line(1, "Why it matters?", 82.2, 83.5))                             # 3 words
    assert g.check(b2, now=84.0, silence_s=1.5) is None
    assert g.check(b2, now=86.6, silence_s=3.1) == "pause"


def test_no_pause_on_an_unfinished_sentence():
    g, b = Gate(), DiscourseBuffer()
    b.add(line(1, "Two main stages of photosynthesis are", 74.9, 77.2))
    assert g.check(b, now=80.0, silence_s=2.5) is None


def test_words_trigger_waits_for_the_sentence_end_within_bounds():
    g, b = Gate(GateConfig(max_words=20)), DiscourseBuffer()
    b.add(line(1, " ".join(["w"] * 22), 0, 5))                   # 22 words, mid-sentence
    assert g.check(b, now=5.1, silence_s=0) is None
    b.add(line(2, "and so on.", 5, 6))
    assert g.check(b, now=6.1, silence_s=0) == "words"
    b3 = DiscourseBuffer()
    b3.add(line(1, " ".join(["w"] * 30), 0, 5))                  # 1.5 x max_words: send regardless
    assert g.check(b3, now=5.1, silence_s=0) == "words"
