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
- **Split (user, 2026-10-06), each finished and verified before the next:**
  - **V1a** formulas (KaTeX) + layout polish → `docs/specs/F-007a-formulas-layout.md`
  - **V1b** images (auto on the projector; teacher remove / replace / drag-drop in /control) → `F-007b-images.md`
  - **V1c** crash recovery + 60-min soak with recorded/fake LLM answers (0 tokens) → `F-007c-robustness.md`
  - Teacher controls and the concern flow already exist (M4).

## V1.5 (done) — Reference materials + post-lecture
_Built as "V2" (groups A–D); renamed 2026-10-17 when Concept Simulation became V2. History docs keep the old label._
- Teacher uploads (PDF, docs, labelled images) → local index (separate from the transcript); used for enrichment only.
- Post-lecture: notes, short and detailed summaries, key concepts, quiz/question bank, PPTX export, archive viewer.
- **Plan (user, 2026-10-07)**, groups built one after another, everything only when the teacher asks for it:
  - **A** slide themes light / premium dark mid-lecture, /control dark (user decides), teacher's PDF notes in
    /control, labelled diagrams first → `F-009-themes-notes-labelled.md` (done)
  - **B** one Materials card in /control (multi-select): summary **as a slide** (this topic / whole lecture), key
    concepts slide (+ in the notes), notes PDF, assignment PDF (theory questions, count chosen, default 10, short +
    long, no key), PPTX of the deck (projector look, light / dark chosen), editable names, from this and / or past
    lectures; past lectures viewer; shared PDFs for students; no transcript export → `F-010-lecture-tools-archive.md`
    (done)
  - **C** quiz (MCQ, time per question, count, topic incl. picked past lectures, leaderboard on the projector) and
    test (MCQ, count + duration, submit, scores to the teacher); students join through the share link with name +
    roll number, one submission per roll number; questions previewed / edited by the teacher before start
  - **D** reference materials (upload + local index; most accurate / efficient use, LLM optional) — done 2026-10-12,
    F-012: My Notes = study material (slides passage, own figures first, speech terms, quiz fact check)
- V1c (crash recovery + soak): **marked done for now (user, 2026-10-17)**; V1 still has room for improvement
  (crash-recovery diagnosis, 60-min soak). V1 fixes are made on the V2 branch.

## V2 — Concept Simulation (branch `V2-Concept-Simulation`) → `docs/specs/F-014-concept-simulation.md`
- Live parametric simulations inside the slide (a `simulation` block beside the points), from a spoken cue and the
  values said; every printed number said, set by the teacher or computed in Python. SVG + own closed-form models, no
  matter.js (ADR-0010). The LLM never writes code; S2 adds an optional closed-list field after an A/B.
- **S0** foundation + block on a surface + incline (done 2026-10-17) · **S1** 8 templates, scenario score, Suggest,
  0-token replay · **S2** relative phrases, graphs, readouts, optional LLM field · **S3** processes · **S4** hard
  topics (p-n junction, RLC transients / resonance / phasors, networks: packets, routing, TCP) · **Explore mode**
  for students on /view (later).
- **V2 Next — F-017 Explainer Stage** (re-planned 2026-10-26, `docs/v2/V2-ROADMAP.md`, ADR-0011): 2D SVG stage,
  look explainer_flat + chibi people (baked CC0 mocap), LLM op deltas → Python laws → director + acting → stage.
  Sessions **E1** renderer + kit · **E2** stage core (laws, director, acting) · **E3** live language · **E4** views,
  diagrams, laws · **E5** evaluation (paper 2). Supersedes F-016 C2/C3 and F-015's remaining plan below.
- _(superseded)_ **F-015 Live Scene Engine** (`docs/v2/`, planned 2026-10-22): open-vocabulary scenes from speech, no
  templates. The LLM emits typed SceneOps; Python engines compute. **L1** scene core (geometry, plot, motion) · **L2**
  science worlds (rigid, field, wave/optics, particles) + nouns not built in · **L3** any subject (flow, graph) + continuity + teacher
  panel · **L4** benchmark + baseline + ablations (paper 2). Templates: teacher pick only.

## V3 — Story Scenes mode
- Reuses the F-015 SceneSpec (`docs/v3/V3-story-outline.md`). Narrative detection → a storyboard of scenes (retrieved and optionally locally generated stills),
  procedural camera motion, captions, timeline. See ADR-0006.

## V4 — Multilingual
- Hindi, Marathi, and mixed-language input (multilingual Whisper / Indic models); selectable output language (LLM or IndicTrans2).
