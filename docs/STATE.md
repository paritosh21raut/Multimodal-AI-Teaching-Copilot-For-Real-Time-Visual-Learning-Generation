# Current State

_Last updated: 2026-10-05: M0 ✅, M1 ✅ (real mic verified), M2 ✅, M3 ✅ (simulated lecture + real Groq). Next: M4._

## Now
- **Next milestone: M4 Presentation Engine → MVP.** Write `docs/specs/F-005-presentation.md`, then the planner
  (continuity, capacity, hysteresis, new-topic confirmation) and composer (`Interpretation` acts → `SlideSpec` blocks),
  driven by `InterpretationReady` + `ConceptSignal`; items linked to an open concern held back.
- `.env` has `GROQ_API_KEY` and `OPENROUTER_API_KEY` (never print/commit). Ollama not installed (optional fallback).

## Progress (honest; done = implemented + tested + runtime-verified)
| Subsystem | % | Status |
|---|---|---|
| Core (events, bus, config, state store, lifecycle) | 30 | verified; state grows in M3/M4 |
| Persistence (event log, recovery) | 15 | event log verified; snapshots/recovery not started |
| Simulator / test harness | 55 | text simulator, WAV-as-mic, display harness, screenshot tools; no soak runner yet |
| Audio / STT | 95 | verified on WAV and real human voice (laptop mic array); classroom lapel mic still to try |
| Lecture understanding + LLM | 75 | filter, tracker (MiniLM ONNX), buffer/gate, router (Groq → Groq → OpenRouter → Ollama), interpreter, rolling memory verified on the fixture with real Groq; not yet on a real-mic lecture |
| Presentation engine | 15 | SlideSpec + Deck (lifecycle, navigation, flags) verified; planner/composer not started |
| Live display + control view | 60 | server, hub, all layouts, themes, fit, transitions, controls verified in Edge; KaTeX, images, concern panel pending (V1) |
| Visual system (images/diagrams) | 10 | SVG/CSS diagram layouts (process, timeline, tree, causal) exist; image retrieval not started |
| Reference materials | 0 | not started |
| Post-lecture outputs | 0 | not started |
| Concept Simulation mode | 0 | not started |
| Story Scenes mode | 0 | not started |
| Multilingual | 0 | not started (interfaces carry `language`) |

## Verification log
| Item | Unit | Integration | Runtime |
|---|---|---|---|
| EventBus, config, state store, event log, simulator | ✅ | ✅ | ✅ |
| App lifecycle READY → Enter / control Start → LIVE → q / control End → ENDED | – | – | ✅ (Ctrl+C not exercised) |
| Segmenter, VAD, Whisper engine and guard, speech pipeline | ✅ | ✅ (GPU) | ✅ WAV real time: p50 ≈ 650 ms, VRAM ~1.1 GB |
| M1 review fixes (forced-split loss, stop hangs, mic leak, device "0", watchdog) | ✅ regression tests | – | – |
| Real mic (human voice, Intel SST array) | – | – | ✅ mic_check rms −37.5 dBFS, accurate transcript, conf 0.92; live run 7 segments, 0 dropped, STT p50 781 / p95 971 ms |
| SlideSpec validation, Deck ops/navigation/pin/freeze/blank | ✅ | – | ✅ |
| DisplayHub + server: hello, patch fan-out, reconnect snapshot, commands, role check, coalescing | ✅ | ✅ (real WebSockets) | ✅ |
| Display in Edge: 100 rapid in-place patches → 0 nodes re-created, no console errors | – | ✅ `-m browser` | ✅ |
| Display: freeze holds, blank, navigation, self-reconnect after a server drop | – | ✅ `-m browser` | ✅ |
| All 9 layouts × 2 themes (screenshots inspected) | – | – | ✅ `artifacts/display/` |
| Control view (live preview, transcript, deck, keys) | – | – | ✅ `artifacts/app/` |
| Utterance filter, concept tracker, gate/buffer (cuts, seal, cap, no loss) | ✅ | ✅ | ✅ |
| LLM router: 429 cooldown, timeout+retry, hard total timeout, malformed bodies, TPM/RPM, per-model output cap | ✅ (mock HTTP) | – | ✅ real Groq + OpenRouter fall-through |
| Interpreter: validation, repair within budget, deterministic fallback, sanitising | ✅ | ✅ | ✅ 0 fallbacks in real runs |
| State store: outline/subtopics, rolling summary, concerns, resolve_concern, wait_applied | ✅ | ✅ | ✅ |
| Understanding on photosynthesis.txt, real time, real Groq (`python -m copilot --simulate … --speed 1`) | – | ✅ mock LLM; ✅ `-m live_llm` | ✅ Definition → Requirements → Process → Importance → Respiration (new_topic); oxygen claim → concern (0.95–0.98); 14 calls, max 8/min, prompt ≤ 1171 est. tokens (budget 2600), LLM latency p50 1.1–1.2 s; last segment → interpretation p50 6.3 s, max 12.8 s; reproduced after review fixes |
| M3 independent review (subagent): 7 bugs + nits | regression tests added | – | fixed: content loss on unexpected interpreter errors, unhashable fields, hard timeouts, repair budget, apply-failure stall, 3.10 cancellation, flaky rate test, bounded stats, multi-cut buffer, numeric utterances |

## Code map
- `src/copilot/core/`: events, bus, config, state, logging_setup
- `src/copilot/persistence/event_log.py`
- `src/copilot/sim/simulator.py`
- `src/copilot/audio/`: sources, vad, segmenter, mic_check
- `src/copilot/stt/`: engine, pipeline, factory, cuda_dlls
- `src/copilot/presentation/`: spec (SlideSpec), deck, demo (scripted slides; not used in real lectures)
- `src/copilot/display/`: hub (WebSocket fan-out, coalescing outbox), server (FastAPI/uvicorn embedded)
- `src/copilot/core/`: interpretation (Interpretation contract), memory (outline matching, rolling summary), textutil
- `src/copilot/llm/`: providers (OpenAI-compatible), ratelimit, router (`build_router` from config `[llm]`)
- `src/copilot/understanding/`: filter, embedder (MiniLM ONNX), tracker, gate, prompt, interpreter, service
- `web/`
  - `shared/` (tokens.css, slide.css, slide.js renderer + fit, ws.js)
  - `display/` (projector)
  - `control/` (teacher)
  - `vendor/` (htm+preact)
- `tools/`: display_harness, screenshot_display, screenshot_app
- `src/copilot/app/main.py`, CLI flags:
  - `--simulate`, `--audio-file`, `--speed`
  - `--subject/--grade/--topic`
  - `--no-wait`, `--no-display`, `--open`, `--demo-slides`, `--no-understanding`

## Known issues / notes
- M3 (open):
  - Single-sentence MiniLM shift is noisy (0.3–0.6 within a facet); the threshold is 0.75, so cue words and the LLM carry
    boundary detection. Topics without spoken cues rely on the LLM alone.
  - OpenRouter free tier: 50 requests/day. Groq: 8k TPM per model, and qwen3.8 has a 1000 output-tokens/min limit
    (capped at 900).
  - The rate floor counts interpretations (≤ 7.5/min). During outages one interpretation can make several HTTP calls,
    but each entry's own RPM/TPM bucket is respected.
  - Pause detection in live mode is measured from transcript arrival, so it lags by the STT latency (~0.7 s).
  - The fallback with no current topic creates an expected-topic/"Lecture" node.
  - `test_understanding_pipeline` had a rare Windows timing flake. It was fixed by measuring on one clock; 10/10 runs passed since.
- Open (plausible, not reproduced):
  - mic overflow drops frames, so lecture time lags the wall clock
  - the STT queue is unbounded if Whisper runs slower than real time
- Formula blocks show the spoken form; KaTeX rendering is pending (V1).
- The `onOverflow` callback exists in the renderer but is not reported to the server yet (needed by the M4 planner).
- Mic levels on the Intel SST array are low (≈ −37 dBFS speech) but transcribe well.
- Fixed: terminal READY/LIVE lines garbled by unflushed prints (all app prints now flush).

## User actions pending
- Optional: install Ollama + `ollama pull qwen2.5:3b` (local LLM fallback).
- Later: try the classroom lapel mic with `mic_check`.
