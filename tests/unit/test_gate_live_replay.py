"""Replay of the real-mic M3 session 20261005-054752-39bc through the gate with VAD-based silence.

Segment texts, lecture times and STT latencies are copied from that session's event log. The replay models the
live path: VAD voice during each segment, text arriving after the segmenter hangover (0.4 s past `end`, which
already includes 0.2 s pad) plus the logged STT latency, an 8 s call-rate floor with sealing, and 1.5 s per
interpretation. It reproduces the service's control flow (_maybe_interpret) on a simulated clock.
"""
from copilot.understanding.gate import BufferedLine, DiscourseBuffer, Gate, GateConfig
from copilot.understanding.service import vad_silence

SESSION = [  # (text, start, end, stt_latency_ms)
    ("Hello everyone, today we will learn about photosynthesis. Photosynthesis is the biological process where "
     "plants, algae and some bacteria convert sunlight, water and carbon dioxide into glucose and oxygen.",
     0.352, 14.08, 865),
    ("It is the process by which green plants prepare their food.", 14.304, 17.472, 611),
    ("Let's talk about how photosynthesis works.", 18.304, 21.088, 589),
    ("The input is plants absorb water through their roots.", 22.336, 27.136, 571),
    ("Take in carbon dioxide from the air through the tiny leaf pores called stomata.", 27.648, 33.856, 693),
    ("And Capture Sunlight. The Process.", 34.272, 36.992, 598),
    ("The process is that inside plant cell chloroplasts, a green pigment called chlorophyll absorbs solar "
     "energy.", 37.248, 45.824, 758),
    ("which comes from the Sun.", 46.176, 48.16, 353),
    ("The chemical equation is 6CO2 plus 6H2 plus light gives us C6H12O6 plus 6O2.", 48.64, 60.544, 692),
    ("The output of this process is", 61.056, 62.944, 356),
    ("The plants creates glucose that is C6H12O6 for food and energy while they release oxygen O2 as a "
     "by-product.", 63.36, 73.696, 782),
    ("Two main stages of photosynthesis are", 74.912, 77.216, 593),
    ("Light-dependent reaction and light-independent reactions.", 77.632, 81.664, 634),
    ("Why it matters?", 82.24, 83.488, 319),
    ("Because...", 84.16, 85.024, 335),
    ("It contributes in food production and also for the atmosphere.", 85.312, 90.336, 658),
]
BOUNDARY = {2, 13}  # segments whose ConceptSignal had boundary=true in the session
TICK = 0.05
FLOOR_S = 8.0
CALL_S = 1.5


def replay(cfg: GateConfig, legacy_silence: bool = False):
    gate, buf = Gate(cfg), DiscourseBuffer()
    arrivals = sorted((end + 0.4 + lat / 1000, i) for i, (_, _, end, lat) in enumerate(SESSION))
    units: list[tuple[str, list[int]]] = []
    last_voice = None
    last_arrival = 0.0
    last_end = 0.0
    last_call = None
    busy_until = 0.0
    pending = None  # (reason, send_at): a trigger waiting on the rate floor (the service sleeps, then takes)
    t = 0.0
    k = 0
    while t < 130.0:
        if any(s + 0.2 <= t <= e - 0.2 for _, s, e, _ in SESSION):
            last_voice = t
        while k < len(arrivals) and arrivals[k][0] <= t:
            i = arrivals[k][1]
            text, s, e, _ = SESSION[i]
            buf.add(BufferedLine(str(i), text, s, e), boundary=i in BOUNDARY)
            last_end, last_arrival = max(last_end, e), t
            k += 1
        if pending is None and t >= busy_until and not buf.empty:
            now = last_end + (t - last_arrival)
            if legacy_silence:  # pre-fix: min(lecture_now - last_end, ...) is 0 when the text arrives
                silence = min(now - last_end, vad_silence(t, last_voice, last_arrival))
            else:
                silence = vad_silence(t, last_voice, last_arrival) if last_voice is not None else None
            flushing = k == len(arrivals) and t > arrivals[-1][0] + 20
            reason = gate.check(buf, now, silence, flushing)
            if reason:
                wait = 0.0 if last_call is None else last_call + FLOOR_S - t
                if wait > 0 and reason != "words":
                    buf.seal()
                pending = (reason, t + max(0.0, wait))
        if pending is not None and t >= pending[1]:
            lines = buf.take(cfg.buffer_cap_tokens)
            units.append((pending[0], [int(l.segment_id) for l in lines]))
            last_call, busy_until, pending = t, t + CALL_S, None
        t = round(t + TICK, 4)
    return units


def test_live_session_replay_sends_coherent_units():
    units = replay(GateConfig())
    sent = [i for _, seg in units for i in seg]
    assert sent == list(range(len(SESSION)))                     # nothing lost, in order
    for _, seg in units:
        assert seg != [7], "lone fragment 'which comes from the Sun.' sent by itself"
        if 9 in seg:
            assert 10 in seg, "'The output of this process is' split from its continuation"
        if 11 in seg:
            assert 12 in seg, "'Two main stages of photosynthesis are' split from its continuation"
    reasons = [r for r, _ in units]
    # This speaker paused >= 1.2 s only ~3 times (most gaps were 0.6-1.0 s); the pauses that exist are caught,
    # and the remaining units are closed by max_wait only at a sentence end.
    assert reasons.count("pause") >= 2, units


def test_pre_fix_gate_reproduces_the_live_failure():
    """Sanity check of the replay model: the old thresholds and arrival-based silence split fragments as live."""
    old = GateConfig(pause_min_words=12, long_pause_s=1e9, min_unit_words=0, hold_s=0)
    units = replay(old, legacy_silence=True)
    assert ("max_wait", [8, 9]) in units                          # 'The output of this process is' cut off
    # Same trigger mix as the live log: words, 4 x max_wait, boundary, one pause (only at the very end).
    assert [r for r, _ in units] == ["words", "max_wait", "max_wait", "max_wait", "max_wait", "boundary", "pause"]
