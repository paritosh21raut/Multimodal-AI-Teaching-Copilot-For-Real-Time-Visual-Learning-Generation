# Current State

_Last updated: 2026-10-15: **IEEE paper finished (6 pages, validation phase 4 done, 0 tokens)**. Before that, 2026-10-12:
F-012 group D (reference materials / study material) done (8,582 Groq tokens). V2 groups A–D are implemented. Next: the
user's review of the paper and of group D, then the truthfulness bug below, then V1c.
Older detail (every round since M1): `docs/history/STATE-until-2026-10-12.md`._

## Now
- **F-013 S1 done (2026-10-16): responsiveness.** An announced topic is on screen at once (replay 15.0 → 0.64 s
  median), named list members appear as spoken, units no longer mix two topics, call floor 4 s; live simulated check
  6.0 s median speech → slide (was 9.5 s on the same speech). Details: `docs/specs/F-013-v1-hardening.md` "S1 result".
  Next: S2 (structure). User: try it on the real mic.
- **F-013 S1b done (2026-10-16): live as you speak.** A fast second speech model gives text while the teacher
  talks; titles appear before the announcing sentence ends, definitions build on screen as said, list names append,
  every finished sentence goes to the LLM; slide quality unchanged vs S1 settings on the same audio. Details: F-013
  "S1b result". User: try it with the real mic.
- **NEXT: F-013 V1 hardening** (`docs/specs/F-013-v1-hardening.md`, 2026-10-16, 0 tokens): evaluation of tests 1–30
  (latency 11.2 s median, boundary recall 0.54, 70 % "part N" slides, ~100 comparison cues → 5 slides, 39 % definition
  cards repeat the title, …) + the user's 12 issues → plan S1 (metrics + responsiveness) → S2 (structure) → S3
  (representation + truthfulness bug) → S4 (images + UI) → S5 (wrap-up). Start with S1.
- **Paper v5 after a 3rd review round** (2026-10-16, 0 tokens): `paper/..._v5.docx/.pdf`, 6 pages; wording of the
  extend-only claim, rating range, teacher-edit count (6 accepted corrections), Table V metric definitions, full-page
  materials figure. Details: docs/paper/VALIDATION.md "Phase 7".
- **Paper v4 after a 2nd review round** (2026-10-15; 499k free Groq tokens for the baseline, rest 0 tokens):
  `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot_v4.docx/.pdf`, 6 pages. LLM-controlled baseline re-run on the 18
  annotated D2 lectures (rewrites 38.2 % vs 2.0 %, lower in 18/18, p < 0.001), coverage-guard ablation (+9.0 pts),
  WER 7.1 % on web1 vs MIT captions, "never rewrite" made precise, materials figure back. Tools:
  `paper_baseline_d2.py`, `paper_guards.py`, `paper_wer.py`; `baseline_llm_slides.py` retries outages and reads
  verify_results tests. Sources: `docs/paper/VALIDATION.md` "Phase 6".
- **Paper revised after 3 external reviews** (2026-10-15, 0 tokens): `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot_v3.docx/.pdf`,
  exactly 6 pages; title now "…: Live Slide Generation from Lecture Speech". New: replay ablation on the 18 annotated
  lectures (`tools/paper_ablation.py`, Table IV), bootstrap CIs, Gwet AC1, model shares, populations stated per
  result, new /control screenshot, 3×3 slide grid, Fig. 4 (notes) removed. Sources: `docs/paper/VALIDATION.md` "Phase 5".
  No result was invented or changed. Authors to confirm: speaker-consent sentence, "data on request" sentence.
- **Paper finished** (2026-10-15, phase 4 of the validation campaign). `paper/IEEE_Paper_Multimodal_AI_Teaching_Copilot.docx/.pdf`,
  exactly 6 pages, new title "Multimodal AI Teaching Copilot: Real-Time Slide Generation from Live Lecture Speech",
  results from 36 held-out lectures (409 min; Recorded = 30 tests by six speakers, merged; Public = web1–6), annotated
  accuracy, T1–T5 ratings, D2 latency (Fig. 6 now D2), LLM-controlled baseline. Every number and its source:
  `docs/paper/VALIDATION.md` → "Phase 4 — final numbers". Fast 553, slow 25, browser 39 tests pass.
  Layout note: full-width figures float to the top of the page their anchor lands on; after text edits, re-render and
  look for gaps (anchors are placed in `paper/build/src/body.py` to avoid them).
- **F-012 study material** (spec `docs/specs/F-012-reference-materials.md`). The My Notes files are also the
  lecture's study material, held in a local index (`notes/reference.py`: MiniLM passages, PDF figures, rare terms)
  that is kept apart from the transcript. The LLM part is optional.
  - **Slides.** One passage, ≤ 150 tokens, only when it clearly matches (≥ 0.5). Its rule: name and spell only,
    never add, and a contradicting line is a factual concern. Concern cards cite "Your material: <file> p.N".
  - **Images.** The teacher's own figures come first: a figure is taken from its page region, its label is matched by
    MiniLM, then it goes through the same CLIP gate as web images. Change image falls back to the web.
  - **Speech.** ≤ 30 rare terms go into Whisper's prompt.
  - **Quiz / test.** *Check facts with My Notes*: passages matched to the taught content, plus a guard that drops
    answers that come only from the reference.
  - **Lecture materials.** Not used (they cannot be checked).
  - **UI.**
    - My Notes menu rows: Use for lectures (book) and Private (lock).
    - A study line under the notes.
    - A start card **Study material** row: chips, × to stop using one, Add.
- Tests: 17 unit (`test_reference.py`), 17 slow real-model (`test_reference_real.py`), 1 Edge
  (`test_reference_browser.py`). Fixture: `tests/fixtures/notes/reference_biology.pdf` (`tools/make_reference_fixture.py`).
- Runtime:
  - **Dry run, 0 tokens** (`tools/reference_check.py`, 3 recorded lectures): 12 of 197 units got a passage, all on
    topic, at +10 tokens per unit on average. 2 image requests were answered by the teacher's figures.
  - **Live simulated heart lecture**, temporary data folder, 6,937 tokens: 3 of 3 interpretations got the passage; the
    concern cites p.1; the slide image was the teacher's heart diagram.
  - **Quiz live**, 2 small sets, 1,645 tokens: no reference-only question. Correcting a wrong *taught* fact was not
    reliable (see Known issues).

## Progress (honest; done = implemented + tested + runtime-verified)
| Subsystem | % | Status |
|---|---|---|
| Core (events, bus, config, state store, lifecycle) | 30 | verified; snapshots in V1c |
| Persistence (event log, recovery) | 15 | event log verified; recovery = V1c |
| Simulator / test harness | 55 | text simulator, WAV-as-mic, display harness, screenshot / check tools; no soak runner |
| Audio / STT | 95 | verified on WAV and real voice; F-012 terms not yet tried on real audio |
| Lecture understanding + LLM | 88 | verified with real Groq; F-012 passage verified live |
| Presentation engine | 87 | verified on several lectures with real LLM + screenshots; F-013 cue slides verified (replay + simulated live) |
| Live display + control view | 85 | verified in Edge |
| Visual system (images/diagrams) | 65 | web images + CLIP, labelled diagrams, the teacher's own figures (F-012); generated diagrams not started |
| V2 group A (themes, teacher notes, labelled images) | 100 | verified |
| V2 group B (materials, past lectures) + review fixes F-010b/c | 100 | verified |
| V2 group C (quiz + test, F-011) + review fixes | 100 | verified, committed |
| V2 group D (reference materials, F-012) | 95 | verified; speech terms unit-tested only (no real audio run) |
| Crash recovery + soak (V1c) | 0 | not started |
| Concept Simulation / Story Scenes / Multilingual | 0 | not started |

## Verification (latest; the full log is in the history file)
| Item | Unit | Integration | Runtime |
|---|---|---|---|
| F-012 study material | ✅ 17 (+17 slow real MiniLM / CLIP) | ✅ Edge (1) | ✅ dry 3 lectures (0 tok); live heart lecture 6,937 tok; quiz 1,645 tok |
| Full suites after F-012 | ✅ 553 fast | ✅ 39 Edge | – |

## Code map
- `src/copilot/core/`: events, bus, config, state, interpretation, memory, textutil, logging_setup
- `src/copilot/persistence/event_log.py`; `src/copilot/sim/simulator.py`
- `src/copilot/audio/`: sources, vad, segmenter, mic_check
- `src/copilot/stt/`: engine, pipeline, factory (`vocabulary_prompt` + study terms)
- `src/copilot/llm/`: providers, ratelimit, router, usage
- `src/copilot/understanding/`: filter, embedder (MiniLM ONNX), tracker, gate, prompt (+ REFERENCE block), grounding,
  interpreter, service
- `src/copilot/presentation/`: spec, deck, content, composer, planner, engine, mathtext, demo
- `src/copilot/visuals/`: sources, filters, finder (CLIP), cache, clip, service (the teacher's figures first)
- `src/copilot/notes/`: library (files, flags), convert, service (open / follow / project / study material),
  reference (F-012 index)
- `src/copilot/materials/` (F-010), `src/copilot/assess/` (F-011, generator + reference guard)
- `src/copilot/display/`: hub, server, share; `web/` shared / display / control / view / export / vendor
- `tools/`: display_harness, screenshot_*, prompt_ab, replay_interpretations, materials_check, quiz_check
  (`--reference`), reference_check, make_reference_fixture, paper tools

## Known issues / notes
- **Truthfulness bug (pre-existing, found by the F-012 live run).** A confident factual concern was marked applied,
  "slide shows the correction", while the model's *acts* kept the wrong words: "right atrium, left atrium and one
  ventricle". The engine found nothing to switch ("0 element(s)"), so the projector kept the wrong fact, and the
  archive and the quiz then used it. Evidence: temporary session 20261012-230109-6a3f (script
  `heart_short.txt`). Proposed fix: when an applied concern changes no element, show the card as "the slide shows
  what you said" (applied = false) and offer Show correction. Not fixed yet (outside F-012; ask first).
- Old sessions hold the removed `freeze` command, so `prompt_ab.rebuild` cannot decode them;
  `tools/reference_check.py` skips such events.
- LLM output varies run to run (facet names, topic vs subtopic). Deterministic guards cover the known cases.
- The deterministic fallback shows complete sentences only.
- Groq: 8k TPM per model, and qwen3.8 has a 1000 output-tokens/min limit.
- Not reproduced: mic overflow lag; unbounded STT queue if Whisper runs slower than real time.

## User actions pending
- Review F-012 in the app: My Notes toggles, the Study material row, a lecture with your own PDF (e.g. STM32 notes).
- Decide on the truthfulness-bug fix above.
- Later: classroom lapel mic with `mic_check`.
