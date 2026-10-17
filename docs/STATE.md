# Current State

_Last updated: 2026-10-17: **F-013 S5 (wrap-up) + the user's 3 issues: preview jumping with long transcript lines,
no photos of the body, dock labels; figures from My Notes onto the slide**, ≈ 9k Groq tokens (app screenshot run only). **V1 (Live Lecture to
Slides) is ready to be marked complete** after the user's check. Before that, 2026-10-17: F-013 S4 (images, figures the
teacher asks for, own-PDF figures, web pages, /control layout lock, disk full), 0 LLM tokens. Before that, 2026-10-17: F-013 S3c (truthfulness) + performance mode + start
card + Follow removed (31,338 Groq tokens, A/B). Before that, 2026-10-17: F-013 S3b (comparison, glossary, named equations, 34,808 tokens). Before
that, 2026-10-17: F-013 S3a (deterministic representation fixes, 0 tokens). Before that, 2026-10-16:
**F-013 S2 (structure) done, targets partly met** (≈ 75k Groq tokens: A/B + one live run).
Before that, 2026-10-15: **IEEE paper finished (6 pages, validation phase 4 done, 0 tokens)**. Before that, 2026-10-12:
F-012 group D (reference materials / study material) done (8,582 Groq tokens). V2 groups A–D are implemented. Next: the
user's review of the paper and of group D, then the truthfulness bug below, then V1c.
Older detail (every round since M1): `docs/history/STATE-until-2026-10-12.md`._

## Now
- **F-013 S5 done (2026-10-17, 0 LLM tokens) + the user's issues of that day.** Details: F-013 "S5 result".
  - **Preview jumping mid-lecture (second report):** a long transcript line widened the whole page (outer grid's
    implicit column; horizontal scrollbar, right panel cut off, preview grew). Fixed; the top bar is one fixed row;
    dock labels never break (Equation out of line with wide notes), icons-only when they do not fit.
  - **No photos of the body:** human-body subjects get drawings only, and a real photo of a body part is refused on
    any slide (CLIP style + body score, measured on the cache; real search checked). Cache version s5.
  - **Figures from My Notes:** figures on the open page are outlined; click or drag one onto the slide preview, or
    select any part of a page (crop button); shown in the wide column. Index format 3: the files in use are read
    once more at the next start.
  - **v1_eval** of the user's two lectures of 2026-10-17 (56 slides) vs baseline: latency median 10.1 → 7.1 s,
    announced topic → slide 17.2 → 0.3 s (missed 36 → 0), part slides 70 → 32 %, duplicates 19 → 2, image repeats
    39 → 1, fallback 59 → 2.
  - **Tests:** fast 751 pass (+7 `test_s5.py`), slow 24 pass, browser 45: the full run found one regression
    (the dock went icons-only at 1600 px: End lecture's `margin-left: auto` made the measured width always "full");
    fixed by measuring the row's parts, then the affected browser files pass (10/10). Runtime: `screenshot_app` (real
    app, 4 Groq calls ≈ 9k tokens, the only tokens of S5), `screenshot_display` both themes; probe of the dock at
    1536 x 864 / 1600 x 1000 / 1920 x 1080.
  - **User:** two live mic lectures (one with a comparison and a classification) to close V1; then V2 (the user's
    "Live Lecture to Visualization" = ROADMAP "Concept Simulation mode").
- **F-013 S4 done (2026-10-17, 0 LLM tokens) + the user's 3 /control issues.** Details: F-013 "S4 result".
  - **/control layout locked:** at the user's 1536 x 730 (125 %) the page sat 2 px from a scrollbar, so the preview
    jumped; now every card keeps its size (probe of the real app + browser test). Tabs collapse to icons only when
    their labels do not fit (measured), Project centred, mistake cards capped with their own scroll, the study line
    finally shows "Reading ... %" / "Used for the slide".
  - **Figures the teacher asks for:** "let's look at the block diagram of STM32" → fetched at once (own files first,
    then Wikipedia / Commons / educational web pages), large on the slide. Checked with the user's ESP-WROOM-32
    datasheet and STM32 IDE book (`tools/figure_check.py`).
  - **Own PDFs:** drawn (vector) figures and "Figure N:" captions (ESP-WROOM-32: 0 → 6 figures). The user's files in
    use are re-indexed once at the next start (format 2; old figure lists kept as figures.v1.json).
  - **Images:** one picture per concept card for objects (each planet: the article's lead image, all or none); a
    subtopic naming a thing in a visual topic gets one; no image repeated across topics.
  - **Disk full:** no traceback, events kept in memory, `[DISK]` warning at start below 1 GB.
  - Web-page figures are not free-licensed (credited by page, classroom use). DuckDuckGo refuses bursts of scripted
    searches (rests 15 min; Bing fallback is unreliable for scripts).
  - **Tests:** fast 744 pass (+23 `test_s4.py`), browser 42 pass (+1 layout). Runtime (0 tokens): real-app layout
    probe at 1536 x 730; figure check with the user's PDFs; image replays of test13 / 21 / 24 (live network, many
    failed downloads in some runs, so counts vary); the S3c leftover `--mode high` WAV run: 30 lines (standard 14).
- **F-013 S3c done (2026-10-17) + the user's 3 requests of that day.**
  - **E1:** a concern card now says what the slide really shows (correction / states it correctly / what you said /
    not on the slide; `CorrectionPlaced`). Replay: of 29 factual cards, 7 claimed "corrected" falsely before; now 1 is
    imperfect (test13). Show correction replaces an item that says the teacher's version in other words. This fixes
    the old "truthfulness bug" (heart lecture) below.
  - **E2:** prompt rule "never state a fact the NEW lines do not say" live after an A/B (31,338 tokens: 2 unsaid facts
    gone, none added; form cost handled by dropping cut-off items in code); a reversed two-way comparison is swapped
    (test15). Library 48 equations (Pascal, Kirchhoff, straight line).
  - **Performance mode:** Standard (default, the S1 settings, fewer calls) | High performance (S1b, every sentence);
    switch on the start card and the top bar, remembered in data/preferences.json, `--mode`.
  - **Start card:** one Study material row + picker (search, ticks, Add file, Add web link); fits with 15 files. Web
    pages named by title ("Human Brain · byjus.com").
  - **Follow removed** (it turned pages early and back).
  - **Tests:** fast 721 pass. Browser suite: the full run was stopped by the system (low memory) after ~40 tests with
    no failure printed; the changed browser files passed alone (`test_reference_browser.py` 2/2). Re-run in S4: the
    whole browser suite passes (42, incl. the notes and KaTeX tests).
  - **Runtime (0 tokens):** WAV `f013_cues_chem.wav` with `--mode standard`: 14 lines (utterances, S1b cut it into ~31),
    `[MODE]` line printed. `--mode high` (re-run in S4): 30 lines.
- **F-013 S3b done (2026-10-17): N-way comparison, lecture glossary + Whisper prompt, named equations.**
  - **Replay** of tests 1–30 (0 tokens): unusable comparison tables 2 → 0; formulas 23 → 32, of which 9 are named
    standard equations (test16 now shows both Schrödinger forms); boundaries unchanged (P 0.775, R 0.507).
  - **Comparison:** 2–4 columns, cells placed by name, no table without headings. Rule + cue tag A/B on gpt-oss-120b
    (34,808 tokens) was not worse (it gained the test27 / test18 tables), so it is live.
  - **Glossary:** primes Whisper as the lecture grows; a 59-word prompt is not slower on medium.en. It fixes slide
    text only from study-material / setup spellings (lecture terms as the source were 2–3 of 10 right in the replay).
    New dependency: wordfreq.
  - **Equation library:** 42 entries, all KaTeX-tested. Engine adds a named equation once per lecture and never over
    the teacher's own formula. /control **Equation** search. 3+ formulas in two columns.
  - **Code block:** not built; as-heard spoken code is unreadable (test26).
  - **Tests:** fast 706, browser 40 (one intermittent failure in `test_blank_and_navigation_on_projector`, which passes
    alone 3/3). Screenshots looked at.
  - **Next:** S3c (E1 card, E2 "never state a fact not said" + the model's `standard_formula`, A/B).
- **F-013 S3a done (2026-10-17, 0 tokens): representation, deterministic.** Replay of tests 1–30 with the guards re-run
  (`tools/v1_eval.py --s3`): coverage-guard lines on slides 118 → 33, verbatim copies 187 → 105 (12.7 → 7.7 %), garbage
  lines 31 → 10, duplicates 6 → 1, bad definition cards 18 → 2, broken formulas 7 → 0; boundaries unchanged (P 0.775,
  R 0.507). The S2 "verbatim bullets" came from our coverage guard, not the model. Built: quantity normaliser + stemmer,
  garbage gate (`understanding/quality.py`), cited-line limit, definition-card fixes, Greek / subscript / function
  formulas, group cards / fact tiles / member cards from "Label: …" points, dated timelines. Also fixed: "-55 °C"
  shown as "55 °C" (a list-dash strip), an example drawn twice (card + aside), a meta note applied as a correction.
  Cost: ~14 real statements of 93 no-longer-shown guard lines. Tests: fast 674 (+48 `test_representation.py`),
  browser 39. Screenshots `tools/screenshot_s3.py` looked at. Not live-checked (no LLM change). Details: F-013
  "S3 result". **Next:** S3b (N-way comparison, glossary + Whisper prompt, named equations + Show equation, code block).
- **Paper v8** (2026-10-16, 0 tokens): `paper/..._v8.docx/.pdf`, 6 pages; AI-flagged passages rewritten, Fig. 4 = 9 accurate slides (3 × 3) from verify_results/ subject folders. v7 report: similarity 13 % (all bibliography/author block), AI 28 %. Details: docs/paper/VALIDATION.md "Phase 10".
- **Paper v7** (2026-10-16, 0 tokens): `paper/..._v7.docx/.pdf`, 6 pages; 31 references (2 removed, long author lists → et al.), every reference cited in Related Work (asserted by build_docx.py). The 24 % report was run on the old v5 report PDF, not on the paper. Details: docs/paper/VALIDATION.md "Phase 9".
- **Paper v6** (2026-10-16, 0 tokens): `paper/..._v6.docx/.pdf`, 6 pages; plagiarism-matched sentences rewritten, tables simplified (6 tables, one measure per row), Fig. 1 larger, Fig. 3 = notes page + assignment, Fig. 4 = 12 slides. Details: docs/paper/VALIDATION.md "Phase 8".
- **F-013 S2 done, targets partly met (2026-10-16): structure.** Replay of the 18 annotated lectures (0 tokens):
  boundary P 0.80 → 0.775, R 0.44 → 0.51, F1 0.51 → 0.555, part rate 0.73 → 0.62, 34 slides under a parent. Recall
  (≥ 0.70) and part-N (≤ 45 %) are NOT met; the remaining gap is model subtopic granularity. The tree is built by code
  (sections, set members, registry, qualifier children, naming gate, crumb Topic — Parent, nested Lecture
  Structure). The model `parent` rule was A/B-tested on gpt-oss-120b (27,988 tokens), was worse, and is OFF. Live
  check on `f013_s2_causes.txt` (≈ 47k tokens) looked right; a gap it showed ("X of Y" parent) was fixed but not
  re-run live. Tests: fast 626, browser 39. Details: F-013 "S2 result". **Next:** S3 (representation +
  truthfulness, including transcript lines copied verbatim as points).
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
| Audio / STT | 95 | verified on WAV and real voice; F-012 terms not yet tried on real audio; S3b glossary prompt timed on WAV only |
| Lecture understanding + LLM | 88 | verified with real Groq; F-012 passage verified live |
| Presentation engine | 90 | verified on several lectures with real LLM + screenshots; F-013 cue slides verified (replay + simulated live); S3a/S3b replay-verified, S3b comparison rule A/B on Groq |
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
- **Truthfulness bug: FIXED in F-013 S3c (E1)** — the card says what the slide shows; kept below for history.
  Original: A confident factual concern was marked applied,
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
- Try S4 in the app: say "let's look at the block diagram of ..." with your datasheet in My Notes; check the /control
  page at your screen size (wide notes, mistake cards); a planets / organs lecture for the card pictures.
- Review F-012 / F-013 S3c in the app: the Study material picker, the Speed switch (Standard / High performance), a
  lecture with your own PDF (e.g. STM32 notes).
- Later: classroom lapel mic with `mic_check`.
