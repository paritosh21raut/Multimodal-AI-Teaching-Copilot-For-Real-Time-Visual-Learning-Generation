# Roadmap

Order is driven by dependencies: the core and the display come first, because every later feature
plugs into them.

## M0 — Foundation
- Repo skeleton, config, logging, event bus, `LectureStateStore`, persistence event log.
- Text lecture simulator (script → timed `TranscriptSegment`s), so everything downstream is testable without a mic.
- App lifecycle: start → initialize → READY → Enter → LIVE → end.
- **Exit:** `pytest` green; `python -m copilot --simulate <script>` runs end to end and logs events.

## M1 — Audio + STT
- Mic capture (sounddevice), silero-vad segmentation, faster-whisper on CUDA (int8_float16).
- Partial and final transcript events, timestamps, confidence.
- **Exit:** a real-mic run with measured latency (target ≤ 2 s from end of utterance to final text) and VRAM ≤ 1.5 GB.

## M2 — Live Display shell
- FastAPI + WebSocket hub, versioned `SlideSpec` patches.
- Display page: core layouts (title, definition, explanation, key points), light/dark themes, auto-fit, flicker-free transitions.
- Minimal Control View: status, transcript, slide navigation.
- **Exit:** a Playwright screenshot set of all layouts in both themes; no flicker during 100 rapid patches.

## M3 — Lecture Understanding
- Utterance filter (classroom-management talk vs. content).
- Concept tracker (embeddings, topic-shift score), discourse buffer, gate.
- LLM provider layer: Groq → OpenRouter → Ollama fallback, rate limiter, JSON-schema validation, retries.
- Interpreter (discourse acts, concepts, content items, concerns), rolling memory.
- **Exit:** simulated lectures produce correct topic/subtopic/continuity labels on fixture scripts; LLM calls ≤ 8/min; prompt ≤ budget.

## M4 — Presentation Engine → **MVP**
- Planner: continuity, slide capacity, hysteresis (update / extend / continue-slide / new-topic slide).
- Composer: content items → `SlideSpec` blocks by representation.
- Progressive update: quick structural update, then a refined one.
- **MVP exit:** a real 20–30 min spoken lecture → stable, continuity-aware live slides on the projector.
  Runtime-verified with screenshots and an event log review.
  Adjusted 2026-10-05 (user decision): on the free Groq tier during development, a real continuous **5–10 min**
  spoken lecture (live mic, the user) is the exit check; 20–60 min lectures are for the paid API later (the
  60-min soak stays in V1).

## V1 — Rich representations + images + robustness
- Layouts: process, comparison, timeline, hierarchy, cause-effect, formula (KaTeX), application, example.
- Image retrieval (Wikimedia/Wikipedia/Openverse) with CLIP re-ranking and a "need-an-image?" decision.
- Full teacher controls (freeze, pin, blank, force new, prev/next), concern flow in the Control View.
- Crash recovery from the event log; 60-min soak test.

## V2 — Reference materials + post-lecture
- Teacher uploads (PDF, docs, labelled images) → local index (separate from the transcript); used for enrichment only.
- Post-lecture: notes, short and detailed summaries, key concepts, quiz/question bank, PPTX export, archive viewer.

## V3 — Concept Simulation mode
- Parametric simulation templates (forces on a block, incline, circuits, waves, orbits, cycles, geometry).
- The LLM selects a template and fills parameters; rendered with Canvas/SVG (+ matter.js).

## V4 — Story Scenes mode
- Narrative detection → a storyboard of scenes (retrieved and optionally locally generated stills),
  procedural camera motion, captions, timeline. See ADR-0006.

## V5 — Multilingual
- Hindi, Marathi, and mixed-language input (multilingual Whisper / Indic models); selectable output language (LLM or IndicTrans2).
