# Testing Strategy

"Tests passed" is not "system works". Every milestone ends with runtime verification.

## Layers
| Layer | Location | What | Runs |
|---|---|---|---|
| Unit | `tests/unit/` | Pure logic: bus, state store, gate, planner, capacity, filters, prompt budget | every change |
| Integration | `tests/integration/` | Several real components wired via the bus; LLM replaced by **recorded responses** (cassettes) | every change |
| Simulated lecture (E2E) | `tests/e2e/` | Script → simulator → full pipeline → `SlideSpec` sequence; assertions on slide count, continuity, representations | per milestone |
| Live LLM | `tests/e2e/ -m live_llm` | Same as above with the real Groq/Ollama; opt-in | before milestone sign-off |
| Display/visual | `tests/e2e/ -m browser` | Playwright opens the display, applies specs, captures screenshots to `artifacts/` | per UI change |
| Long-running/soak | `tools/soak.py` | 60-min accelerated lecture; tracks RSS, VRAM, event-loop lag, LLM calls/min, prompt sizes | V1+ |
| Failure/recovery | `tests/integration/` | LLM timeout/429/invalid JSON, network down, mic loss, process kill + restore | M3+ |
| Real mic | manual + `tools/` | Live speech run with latency measurement | M1, MVP |

## Fixtures
- `tests/fixtures/lectures/*.txt`: lecture scripts with timing markers and **expected labels**
  (topic, subtopic, act, expected slide boundaries). Include classroom-management lines and an incorrect statement.
- `tests/fixtures/llm/`: recorded LLM responses keyed by prompt hash.
- `tests/fixtures/audio/`: short WAVs for STT tests (generated or recorded).

## Rules
- Don't mock the component under test. Mock only external boundaries (network LLM, mic).
- Assertions check behaviour (e.g. "≤ 3 slides for the 5-min photosynthesis segment"), not implementation details.
- A failing test means: fix the production code. Change a test only with written proof that it is wrong.
- Visual checks: screenshots must be **looked at** (read the PNG) during verification, not only generated.
- `docs/STATE.md` records for each component: `verified` / `unit-tested only` / `not started`.

## Key metrics (logged by the app, asserted in soak tests)
- End-of-utterance → final transcript latency
- Transcript → first display update latency (target 3–5 s) and → refined update (10–15 s)
- LLM calls/min (≤ 8), prompt tokens per call (≤ budget), failures/fallbacks
- Slides per 10 min, slide-change hysteresis violations
- Process RSS growth over 60 min (bounded), VRAM
