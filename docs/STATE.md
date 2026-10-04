# Current State

_Last updated: 2026-10-05 — M0 Foundation complete._

## Now
- **Milestone:** M0 ✅ → next is **M1 Audio + STT**.
- **Next task:** write `docs/specs/F-002-audio-stt.md`, install the `[audio]` extra, implement
  mic capture → silero-vad → faster-whisper worker emitting `TranscriptFinal`; measure latency and VRAM on the laptop;
  pick the Whisper model (ADR-0002 update).

## Progress (honest; done = implemented + tested + runtime-verified)
| Subsystem | % | Status |
|---|---|---|
| Core (events, bus, config, state store, lifecycle) | 25 | M0 parts verified; state grows in M3/M4 |
| Persistence (event log, recovery) | 15 | event log verified; snapshots/recovery not started |
| Simulator / test harness | 40 | text simulator verified; audio playback sim and soak runner not started |
| Audio / STT | 0 | not started |
| Lecture understanding + LLM | 0 | not started |
| Presentation engine | 0 | not started |
| Live display + control view | 0 | not started |
| Visual system (images/diagrams) | 0 | not started |
| Reference materials | 0 | not started |
| Post-lecture outputs | 0 | not started |
| Concept Simulation mode | 0 | not started |
| Story Scenes mode | 0 | not started |
| Multilingual | 0 | not started (interfaces carry `language`) |

## Verification log
| Item | Unit | Integration | Runtime |
|---|---|---|---|
| EventBus (order, filter, overflow, failure isolation, close) | ✅ | ✅ | ✅ |
| Config precedence (default < local < env < overrides) | ✅ | – | ✅ |
| LectureStateStore (versioning, stats) | ✅ | ✅ | ✅ |
| EventLog (SQLite, batched, ordered) | – | ✅ | ✅ |
| Lecture simulator + script format | ✅ | ✅ | ✅ |
| App lifecycle: READY → Enter → LIVE → q/end → ENDED | – | – | ✅ (piped stdin; Ctrl+C path not yet exercised) |

## Code map
- `src/copilot/core/` events, bus, config, state, logging_setup
- `src/copilot/persistence/event_log.py`
- `src/copilot/sim/simulator.py`
- `src/copilot/app/main.py` (CLI + lifecycle)
- `tests/fixtures/lectures/photosynthesis.txt` (annotated with `@expect` for M3/M4 tests)

## Known issues / notes
- Ctrl+C handling on Windows is not runtime-tested yet.
- Base deps only (`pydantic`, `tomli`, `python-dotenv`, pytest). Milestone extras: `[audio]`, `[display]`, `[understanding]`.

## User setup pending (needed by M3)
- Free Groq API key → `.env` (`GROQ_API_KEY`); optional OpenRouter key.
- Install Ollama + pull a small model (offline fallback).
