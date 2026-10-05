"""Export a recorded session's transcript (as heard, mis-hearings kept) as a lecture fixture for the simulator.

    .venv/Scripts/python tools/export_transcript.py <session_id> <fixture_name> ["one-line description"]

Writes tests/fixtures/lectures/<fixture_name>.txt: one line per final transcript segment, `[pause N]` where the
teacher paused for a second or more. Every live test transcript is kept this way (docs/TESTING.md).
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def export(session_id: str, name: str, note: str = "") -> Path:
    db = ROOT / "data" / "sessions" / session_id / "session.sqlite"
    rows = sqlite3.connect(db).execute(
        "select payload from events where type='TranscriptFinal' order by seq").fetchall()
    segments = [json.loads(r[0])["segment"] for r in rows]
    if not segments:
        raise SystemExit(f"no transcript in {session_id}")
    out = [f"# Live test transcript, session {session_id}, exported as heard (mis-hearings kept)."]
    if note:
        out.append(f"# {note}")
    prev_end = None
    for seg in segments:
        if prev_end is not None and seg["start"] - prev_end >= 1.0:
            out.append(f"[pause {min(6.0, round(seg['start'] - prev_end, 1))}]")
        out.append(" ".join(seg["text"].split()))
        prev_end = seg["end"]
    path = ROOT / "tests" / "fixtures" / "lectures" / f"{name}.txt"
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return path


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    print(export(sys.argv[1], sys.argv[2], " ".join(sys.argv[3:])))
