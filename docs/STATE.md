# Current State

_Last updated: 2026-10-05: M0 ✅, M1 ⏳ (needs a real-voice mic test), M2 ✅._

## Now
- **Next milestone: M3 Lecture Understanding.** Write `docs/specs/F-004-understanding.md`, then build:
  - utterance filter (classroom talk vs. content) and concept tracker (MiniLM embeddings, shift score)
  - discourse buffer and gate
  - LLM provider layer: Groq → OpenRouter → Ollama, with rate limiting and JSON-schema validation
  - interpreter with a bounded prompt, and rolling memory
- **Blocked on the user:**
  - real-voice mic test (M1 sign-off)
  - `GROQ_API_KEY` in `.env` (needed for M3's live-LLM verification)
  - optionally, install Ollama

## Progress (honest; done = implemented + tested + runtime-verified)
| Subsystem | % | Status |
|---|---|---|
| Core (events, bus, config, state store, lifecycle) | 30 | verified; state grows in M3/M4 |
| Persistence (event log, recovery) | 15 | event log verified; snapshots/recovery not started |
| Simulator / test harness | 55 | text simulator, WAV-as-mic, display harness, screenshot tools; no soak runner yet |
| Audio / STT | 80 | verified on WAV in real time; real-voice mic capture unverified |
| Lecture understanding + LLM | 0 | not started |
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
| Real mic | – | – | ⚠️ opens and closes cleanly with no false transcripts; a human-voice test is needed |
| SlideSpec validation, Deck ops/navigation/pin/freeze/blank | ✅ | – | ✅ |
| DisplayHub + server: hello, patch fan-out, reconnect snapshot, commands, role check, coalescing | ✅ | ✅ (real WebSockets) | ✅ |
| Display in Edge: 100 rapid in-place patches → 0 nodes re-created, no console errors | – | ✅ `-m browser` | ✅ |
| Display: freeze holds, blank, navigation, self-reconnect after a server drop | – | ✅ `-m browser` | ✅ |
| All 9 layouts × 2 themes (screenshots inspected) | – | – | ✅ `artifacts/display/` |
| Control view (live preview, transcript, deck, keys) | – | – | ✅ `artifacts/app/` |

## Code map
- `src/copilot/core/`: events, bus, config, state, logging_setup
- `src/copilot/persistence/event_log.py`
- `src/copilot/sim/simulator.py`
- `src/copilot/audio/`: sources, vad, segmenter, mic_check
- `src/copilot/stt/`: engine, pipeline, factory, cuda_dlls
- `src/copilot/presentation/`: spec (SlideSpec), deck, demo (scripted slides; not used in real lectures)
- `src/copilot/display/`: hub (WebSocket fan-out, coalescing outbox), server (FastAPI/uvicorn embedded)
- `web/`
  - `shared/` (tokens.css, slide.css, slide.js renderer + fit, ws.js)
  - `display/` (projector)
  - `control/` (teacher)
  - `vendor/` (htm+preact)
- `tools/`: display_harness, screenshot_display, screenshot_app
- `src/copilot/app/main.py`, CLI flags:
  - `--simulate`, `--audio-file`, `--speed`
  - `--subject/--grade/--topic`
  - `--no-wait`, `--no-display`, `--open`, `--demo-slides`

## Known issues / notes
- Open (plausible, not reproduced):
  - mic overflow drops frames, so lecture time lags the wall clock
  - the STT queue is unbounded if Whisper runs slower than real time
- Formula blocks show the spoken form; KaTeX rendering is pending (V1).
- The `onOverflow` callback exists in the renderer but is not reported to the server yet (needed by the M4 planner).
- Mic levels on the Intel SST array are very low in a quiet room; the classroom lapel mic may differ.

## User actions pending
1. **Mic test:** `.venv/Scripts/python -m copilot.audio.mic_check --seconds 8` (speak), then
   `.venv/Scripts/python -m copilot --subject Biology --topic Photosynthesis --open`. Press Enter, talk for about a minute, type `q`.
2. Free Groq API key → `.env` (`GROQ_API_KEY`). Optional: install Ollama + `ollama pull qwen2.5:3b`.
