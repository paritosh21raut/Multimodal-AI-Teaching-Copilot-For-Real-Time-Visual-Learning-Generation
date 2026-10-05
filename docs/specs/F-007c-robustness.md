# F-007c: Robustness — crash recovery + 60-min soak (V1c)

Starts after V1b is verified. Architecture: `persistence.md`. Zero LLM quota: the soak uses recorded/fake answers.

User answers (2026-10-06): the soak runs in **real time** (60 min); resume is **offered at start** ("Resume session X? [Y/n]").

## What exists
- `data/sessions/<id>/session.sqlite`: append-only `events` table of every non-ephemeral event (transcript,
  interpretations, slide patches, commands, concerns, lifecycle), batched writer thread. `snapshots` table exists
  but is never written. No resume path.
- Text simulator (timed segments), `--speed`, `tools/replay_session.py` (slide patches → Edge).
- `InterpretationReady` events hold the validated interpretations of past sessions (usable as recorded answers).
- Raw LLM responses are not stored per session (only usage counts).

## Missing (plan)
| # | Part | Notes |
|---|---|---|
| 1 | **Snapshots** | every 60 s and at lifecycle changes: `LectureState` + `Deck` (slides, live, flags) + engine frame pointer → `snapshots` |
| 2 | **Recovery** | on start, find the newest session without `ENDED` → offer resume → load latest snapshot + apply later state/deck events (no LLM re-run) → display shows the live slide again; same session log continues |
| 3 | **Engine re-entry** | after restore the engine continues on the live slide's frame (working slide = live slide); dwell timers restart |
| 4 | **Recorded LLM provider** (`llm/recorded.py`) | OpenAI-compatible fake behind the existing router: answers from recorded responses (fixtures), so router/interpreter/validation run for real; 0 tokens |
| 5 | **Response recorder** | live runs save raw request/response pairs per session (`llm_exchanges.jsonl`) → new fixtures |
| 6 | **Soak runner** (`tools/soak.py`) | 60-min lecture from concatenated fixtures (re-timed), recorded provider, display + control connected (Playwright); samples RSS, event-loop lag, bus queue depths, deck size, interpretation latency, WS reconnects, errors |
| 7 | **Bounded memory** | check that in-memory state stays bounded (rolling buffers, deck archive); fix leaks found |

## Risks
- The engine has time-based state (dwell, pending slides): restore resumes a consistent deck, not the exact pending queue.
- Recorded answers must match the replayed units (unit boundaries depend on timing) → key by unit text with a
  nearest-match fallback; unmatched units go to the deterministic fallback (counted, not hidden).
- A 60-min real-time run takes an hour; an accelerated run may hide timing problems.

## Tests
- Unit: snapshot round-trip (state + deck), resume selection, recorded-provider matching.
- Integration: run → kill (task cancel / process kill) → resume → same deck/live slide/outline.
- Soak: pass criteria below; report saved under `artifacts/soak/`.

## Runtime exit check
1. Real process kill (`taskkill /F`) mid-lecture → restart → resume → `/display` shows the same live slide
   (screenshots before/after), transcript and deck intact.
2. 60-min soak, 0 tokens: no crash, no unhandled errors, RSS growth < 150 MB after warm-up, event-loop lag p99
   < 100 ms, interpretation latency stable (p95 first 10 min ≈ last 10 min), display never blank.
