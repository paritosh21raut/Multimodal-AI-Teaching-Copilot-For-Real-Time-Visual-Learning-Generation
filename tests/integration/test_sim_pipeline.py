"""Simulator → bus → state store + SQLite event log (F-001 acceptance)."""
from pathlib import Path

from copilot.core.bus import EventBus
from copilot.core.state import LectureStateStore
from copilot.persistence.event_log import EventLog, read_events
from copilot.sim.simulator import LectureSimulator, parse_script

FIXTURE = Path(__file__).parents[1] / "fixtures" / "lectures" / "photosynthesis.txt"


async def test_simulated_lecture_flows_into_state_and_log(tmp_path):
    script = parse_script(FIXTURE)
    bus = EventBus()
    bus.session_id = "itest"
    store = LectureStateStore(bus, "itest")
    store.attach()
    log = EventLog(tmp_path / "session.sqlite", flush_interval_s=0.05, flush_batch=5)
    await log.open(bus)

    sim = LectureSimulator(bus, script, speed=1000.0)
    await sim.run()
    await bus.close()
    await log.close()

    n = len(script.utterances)
    s = store.snapshot()
    assert sim.published == n
    assert s.stats.segments == n
    assert s.stats.words == sum(len(u.text.split()) for u in script.utterances)

    rows = list(read_events(log.path))
    finals = [e for _, t, e in rows if t == "TranscriptFinal"]
    assert [e.segment.text for e in finals] == [u.text for u in script.utterances]
    assert all(e is not None and e.session_id == "itest" for _, _, e in rows)
    assert sum(1 for _, t, _ in rows if t == "StateChanged") == n
    seqs = [seq for seq, _, _ in rows]
    assert seqs == sorted(seqs)
    ends = [e.segment.end for e in finals]
    assert ends == sorted(ends)  # lecture-time timestamps are monotonic
