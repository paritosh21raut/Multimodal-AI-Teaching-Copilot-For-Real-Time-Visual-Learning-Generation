# Current State

_Last updated: 2026-10-05: M0–M3 ✅, M4 ✅ + M4 verify fixes (display-quality text, fact tiles / groups / trees,
space-based layout, part badges, revisions, truthful slides) verified on the user's two verify lectures replayed
through the real pipeline. Next: user real-mic re-test._

## Now
- **Next: user real-mic re-test** of the solar-system / chemistry style lectures (`python -m copilot`), ideally on
  a fresh Groq daily quota. Watch: concise slide text, facts as tiles, no "(cont.)", corrections shown truthfully
  with the teacher card (OK / Show as I said).
- **Decision needed soon (LLM budget):** Groq free tier caps openai/gpt-oss-120b at 200k tokens/day. One
  interpretation ≈ 2.3k tokens (system prompt ≈ 1.45k), i.e. ≈ 85 interpretations ≈ 15–20 lecture minutes per day on
  the main model; today's tests exhausted it and the run fell back to qwen (8k TPM → skips) and OpenRouter (50/day).
  Options: shrink/split the system prompt, longer units, add more free models to the router, or a local model.
- After that: V1 items (KaTeX, images), soak runner, snapshots/recovery.
- `.env` has `GROQ_API_KEY` and `OPENROUTER_API_KEY` (never print/commit). Ollama not installed (optional fallback).

## Progress (honest; done = implemented + tested + runtime-verified)
| Subsystem | % | Status |
|---|---|---|
| Core (events, bus, config, state store, lifecycle) | 30 | verified; state grows in M3/M4 |
| Persistence (event log, recovery) | 15 | event log verified; snapshots/recovery not started |
| Simulator / test harness | 55 | text simulator, WAV-as-mic, display harness, screenshot tools; no soak runner yet |
| Audio / STT | 95 | verified on WAV and real human voice (laptop mic array); classroom lapel mic still to try |
| Lecture understanding + LLM | 88 | M3 + live-mic fixes (VAD pause, fragment hold, grounding guard, process prompt, facet-question cue, empty-act fill); verified on the fixture with real Groq; gate fixes replay-tested on the real-mic session, not yet re-run live |
| Presentation engine | 85 | content/composer/planner/engine: continuity, space-based layout, parts, dwell, new-topic confirmation + tentative move, revisions, truthful corrections, provisional fast path, force-new, pin/nav-back, overflow; verified on 3 lectures with real LLM + screenshots |
| Live display + control view | 75 | + fact tiles, group cards, side-by-side definitions, part badges, concern card (said / correct / shown, switchable), overflow reporting; KaTeX, images pending (V1) |
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
| M3 live-mic fixes: gate (VAD silence, fragment/tiny-unit hold), grounding guard, process prompt | ✅ incl. replay of session 20261005-054752-39bc | ✅ mock LLM | ✅ fixture real Groq: 9–12 calls, max 6–8/min, 0 fallbacks, process acts as steps, oxygen concern raised |
| M4 presentation engine (F-005) | ✅ 40+ tests | ✅ sim → understanding (mock HTTP) → engine → deck | ✅ fixture real Groq, `tools/screenshot_app.py --lecture` inspected: Title → What is photosynthesis? → What photosynthesis needs → How photosynthesis works (4 steps) → …: the equation (+ accepted correction) → Why photosynthesis matters → Respiration (new topic, comparison); concern only in /control, Accept released the correction; no page errors |
| M4 verify fixes (user lectures: solar system, basics of chemistry) | ✅ 184 fast + 3 Edge | ✅ | ✅ `tools/screenshot_app.py --lecture --simulate tests/fixtures/lectures/{solar_system,chemistry_basics}.txt` (exact STT lines) with real LLM: facts as tiles + inner/outer groups on one slide, branches as tree, element/compound and atom/molecule side by side, galaxies new topic, fragments merged by revisions, "asteroid bite" → belt shown + teacher card; `tools/screenshot_lessons.py` both themes |
| Second independent review (subagent): 15 findings | regression tests added | – | fixed: corrections targeted by source lines (no unrelated rewrites), unapplied-correction accept, regex backslash crash, tentative move of diagrams/duplicates/multi-slide, aside reflow vs squeeze, switch-again concerns, part numbering, case-preserving substitution, fact height model, logged caps, odd-type coercion |
| M4 independent review (subagent): 8 confirmed bugs | regression tests added | – | fixed: multi-concern leak, accept/dismiss content loss, stale provisional, provisional dedupe, late release hijacking the screen, lost new-topic confirmation, grounding false positives, derived-symbol accept; + plausible: pre-resolved concerns, line-less concerns, pause grace after dropped/meta lines, stale overflow, hub hello fail-closed |
| M3 independent review (subagent): 7 bugs + nits | regression tests added | – | fixed: content loss on unexpected interpreter errors, unhashable fields, hard timeouts, repair budget, apply-failure stall, 3.10 cancellation, flaky rate test, bounded stats, multi-cut buffer, numeric utterances |

## Code map
- `src/copilot/core/`: events, bus, config, state, logging_setup
- `src/copilot/persistence/event_log.py`
- `src/copilot/sim/simulator.py`
- `src/copilot/audio/`: sources, vad, segmenter, mic_check
- `src/copilot/stt/`: engine, pipeline, factory, cuda_dlls
- `src/copilot/presentation/`: spec (SlideSpec), deck, content (acts → pieces), composer (height model, merge, titles,
  provisional, revise/substitute/remove), planner (frame decision), engine (PresentationEngine), demo (scripted)
- `src/copilot/display/`: hub (WebSocket fan-out, coalescing outbox), server (FastAPI/uvicorn embedded)
- `src/copilot/core/`: interpretation (Interpretation contract), memory (outline matching, rolling summary), textutil
- `src/copilot/llm/`: providers (OpenAI-compatible), ratelimit, router (`build_router` from config `[llm]`)
- `src/copilot/understanding/`: filter, embedder (MiniLM ONNX), tracker, gate, prompt, grounding, interpreter, service
- `web/`
  - `shared/` (tokens.css, slide.css, slide.js renderer + fit, ws.js)
  - `display/` (projector)
  - `control/` (teacher)
  - `vendor/` (htm+preact)
- `tools/`: display_harness, screenshot_display, screenshot_app (`--lecture [--simulate f]`: whole-lecture captures →
  artifacts/app/lecture_<fixture>), screenshot_lessons (real engine + scripted interpretations → artifacts/lessons)
- `src/copilot/app/main.py`, CLI flags:
  - `--simulate`, `--audio-file`, `--speed`
  - `--subject/--grade/--topic`
  - `--no-wait`, `--no-display`, `--open`, `--demo-slides`, `--no-understanding`

## Known issues / notes
- M4 verify fixes (open):
  - LLM output still varies run to run (facet names, whether an announced subject is a new topic; e.g. chemistry run made
    "Matter" a topic). Deterministic guards cover announcements, examples, yes/no facts, transitions, corrections.
  - The deterministic fallback (LLM unavailable) only shows complete sentences; fragments are skipped (still in transcript).
  - Revisions sometimes come with an extra, overlapping new point (model does both).
  - Contested facts (e.g. "coldest planet") may be flagged; below 0.75 confidence the slide shows what was said.
- M4 (open):
  - LLM extraction varies run to run (e.g. Respiration as "Definition" vs "Comparison"; explanations without items are
    filled from the spoken line; explanation "examples" become points). Slide titles follow the LLM's subtopic names.
  - Formula blocks show the spoken/LLM expression (KaTeX pending); the model sometimes swaps variable symbol/meaning.
  - Provisional teasers are keyword lists from the tracker (subtle italic); quality depends on keyphrases.
  - Dwell is 15 s (config `[presentation] min_dwell_s`); tune after the real-mic test.
  - Fixed during M4: Windows deadlock when a numpy DLL imports while the terminal thread reads a *piped* stdin
    (terminal input now starts after initialization).
- M3 (open):
  - Single-sentence MiniLM shift is noisy (0.3–0.6 within a facet); the threshold is 0.75, so cue words and the LLM carry
    boundary detection. Topics without spoken cues rely on the LLM alone.
  - OpenRouter free tier: 50 requests/day. Groq: 8k TPM per model, and qwen3.8 has a 1000 output-tokens/min limit
    (capped at 900).
  - The rate floor counts interpretations (≤ 7.5/min). During outages one interpretation can make several HTTP calls,
    but each entry's own RPM/TPM bucket is respected.
  - (fixed) Pause detection used transcript arrival; now raw VAD voice frames (`AudioLevel.voice`).
  - The fallback with no current topic creates an expected-topic/"Lecture" node.
  - `test_understanding_pipeline` had a rare Windows timing flake. It was fixed by measuring on one clock; 10/10 runs passed since.
- Open (plausible, not reproduced):
  - mic overflow drops frames, so lecture time lags the wall clock
  - the STT queue is unbounded if Whisper runs slower than real time
- Formula blocks show the spoken form; KaTeX rendering is pending (V1).
- Display overflow is reported to the server (`SlideOverflow`) and the planner continues on a new slide.
- Mic levels on the Intel SST array are low (≈ −37 dBFS speech) but transcribe well.
- Fixed: terminal READY/LIVE lines garbled by unflushed prints (all app prints now flush).

## User actions pending
- Optional: install Ollama + `ollama pull qwen2.5:3b` (local LLM fallback).
- Later: try the classroom lapel mic with `mic_check`.
