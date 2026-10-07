# Persistence, Recovery, Post-lecture

## Storage
- `data/sessions/<session_id>/session.sqlite`:
  - `events(seq, ts, type, payload_json)`: append-only log of all domain events (not audio frames)
  - `snapshots(seq, state_json)`: a `LectureState` + deck snapshot every N events / 60 s
- `data/sessions/<session_id>/transcript.jsonl`: final transcript (human-readable mirror)
- `data/cache/images/`: image cache (shared across sessions)
- `data/notes/`: the teacher's PDF notes (F-009): `<sha16>.pdf`, page texts `<sha16>.json`, rendered pages, `index.json`
- `data/sessions/<session_id>/lecture.json`: the lecture rebuilt from that log (F-010 past lectures), cached by the log's
  size + mtime
- `data/materials/`: what the teacher made (F-010): `index.json` + `<id>.pdf | .pptx`
- `data/archive.json`: lectures the teacher took off the Lectures list (nothing is deleted)
- Writes are batched in a dedicated writer task (no blocking on the loop).

## Recovery
On start, the app offers to resume an unfinished session: load the latest snapshot + replay later events
→ restore state and deck → the display resumes the live slide.

## Bounded memory
In-memory state holds only: outline, rolling summary, current/last few slides, and recent buffers.
Older transcript and slides live only in SQLite.

## Past lectures + materials (V2 group B, F-010) — any time the teacher asks, not only after the lecture
- **Past lectures** (`materials/archive.py`): a session's final deck = the last `DeckState` order with every slide
  at its latest `SlidePatch`; its transcript keeps wall-clock times. Sessions without a content slide or with < 3
  transcript lines are not listed. The running lecture is read the same way after an event-log flush.
- **What was taught** (`materials/content.py`): topic (the slide's crumb) → subtopic (slide title, parts merged) →
  slide lines + the transcript lines said for it. A line goes to the slide changed within 40 s after it that shares
  the most words with it (a slide still being refined is patched after the next topic's first words), else the
  first changed after it. Slides with `origin = materials` (summary / key concepts) are never taught content.
- **Writer** (`materials/writer.py`): bounded prompts (≤ 3000 tokens; 2200 of material, 1800 per notes call, a fair
  share per subtopic and per lecture), JSON answers validated, one repair, failure = the reason shown (nothing made
  up). Per-call router timeout 45 s (live interpretation: 6 s). Calls per lecture: summary 1, key concepts 1 (shared
  by the notes and the slide in one Create), notes ≈ 1 per 1.8k tokens of material, assignment 1.
- **Files** (`materials/render.py`): PDFs are print HTML (KaTeX formulas, the slides' definitions, steps, tables,
  trees, images with credits) printed by headless Edge through our own server; the PPTX draws each slide with the
  real renderer (`/web/export/`) at 1920×1080 in the chosen theme — background picture + every plain text as an
  editable text box at its place (Segoe UI faces; 1 stage px = 0.5 pt). Checked through PowerPoint
  (`tools/pptx_to_png.ps1`).
- Measured (recorded lectures, `tools/materials_check.py`, 0 tokens): 17–29 min lectures need 8 prompts, ≈ 10.6–12.5k
  input tokens for all four LLM items. Live 2026-10-07 (Solar System, 10 min): 6 calls, 7,021 tokens.
- No transcript export (user 2026-10-07).
