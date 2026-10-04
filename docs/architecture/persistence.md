# Persistence, Recovery, Post-lecture

## Storage
- `data/sessions/<session_id>/session.sqlite`:
  - `events(seq, ts, type, payload_json)`: append-only log of all domain events (not audio frames)
  - `snapshots(seq, state_json)`: a `LectureState` + deck snapshot every N events / 60 s
- `data/sessions/<session_id>/transcript.jsonl`: final transcript (human-readable mirror)
- `data/cache/images/`: image cache (shared across sessions)
- Writes are batched in a dedicated writer task (no blocking on the loop).

## Recovery
On start, the app offers to resume an unfinished session: load the latest snapshot + replay later events
→ restore state and deck → the display resumes the live slide.

## Bounded memory
In-memory state holds only: outline, rolling summary, current/last few slides, and recent buffers.
Older transcript and slides live only in SQLite.

## Post-lecture (V2) — separate jobs after `ENDED`
Reads the archive and produces: notes, short/detailed summary, key concepts, question bank/quiz, revision sheet,
PPTX (python-pptx rendering of the final `SlideSpec`s), transcript export. It processes the transcript in chunks
(map-reduce over per-topic segments); it never sends the entire lecture in one prompt.
