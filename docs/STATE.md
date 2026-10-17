# Current State

_Last updated: 2026-10-18: **V2 Concept Simulation S2 done** (part A fixes, push + pull forces, time-series graphs,
values said in another form; the closed-list `sim` hint A/B'd, not live), 16,027 Groq tokens (A/B) + one simulated
lecture (11 calls, ~21.7k prompt + completions, est. ~25k). Before that, 2026-10-17: **V2 Concept Simulation S1 done** (simulation mode + recap, values without the slot, 6
templates, Suggest, `tools/v2_eval.py`), ≈ 22k Groq prompt tokens recorded in one simulated lecture (est. 25–28k with
completions; the simulation path itself 0). Before that, 2026-10-17: **V2 Concept Simulation S0 done** on branch `V2-Concept-Simulation` (F-014), 18,582 Groq
tokens (one simulated lecture; the simulation path itself 0). V1 (incl. V1.5 = old "V2" groups A–D) is done; V1c is
marked done for now. CLAUDE_rebuild stays V1. Before that, 2026-10-17: **F-013 S5 (wrap-up) + the user's 3 issues: preview jumping with long transcript lines,
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
- **V2 Concept Simulation S2 done (2026-10-18).** Details: F-014 "S2 result".
  - **Part A:** Simulation picker rows were hidden by the compact dock rule (the picker sits inside the dock group;
    the Equation picker had it too); Values names on theme tokens; the dock is tighter so icon + name fit at 1536 px
    again (icons only while My Notes is open; Simulation / Back to slides swap); stage labels placed by one
    deterministic layout (`web/sims/layout.js`), measured by a browser test across the 8 templates.
  - **Forces:** push (arrow onto the block) and pull (tail on the block, pointing away), each with its own angle and
    with / against the motion (incline: relative to the said motion, else up the slope); friction value printed.
  - **Graphs:** s-t / v-t (block, incline), theta-t (pendulum), y-t / v_y-t (projectile), y-t (wave), V-I (circuit);
    Python samples `Solution.series` (<= 400 points), the client draws up to the clock time with a cursor. Off by
    default: Show > Graph or "graph / plot" said.
  - **Values:** "the period is 0.2 s" -> f (computed), crest to trough -> lambda/2 (or 2A with height), "the string
    is 3 m long" is not lambda, "the Moon orbits the Earth at 384000 km" -> radius.
  - **Tests:** fast 1163 pass; browser 92 pass (one unnamed flake in test_simulation_browser.py on 1 of 4 reruns); `v2_eval` before / after unchanged (values 82 P/R
    1.00, detect precision 1.00, 0 on negatives).
  - **Next:** the user's look in the app; a larger `sim`-hint A/B before it goes live; S3.
- **V2 Concept Simulation S1 done (2026-10-17).** Details: F-014 "S1 result".
  - **Simulation mode:** a shown simulation is a slide of its own; no new slides while it runs (interpretations
    collected, values still update it); ends by "let's get back to the slides", Back to slides (sim bar / dock),
    removing it, a new topic, 180 s; then a deterministic recap slide (none if nothing worth keeping). /control
    "Simulation running" flag, `SimulationModeChanged` logged, Deck `sim_mode`.
  - **Values:** unit first, bare number → the slot changed last, push synonyms, relative phrases, μ variants ("new
    equal to 0.2" only with friction in context), push / pull at an angle; negative and π angles refused.
  - **Templates (8 total):** + pendulum, projectile, DC circuit (series / parallel), wave, orbit, unit circle → sine;
    each: solver vs hand values, detector positives + traps, JS scene, browser row both themes, screenshots looked at,
    independent review subagent (all findings fixed or listed as open in F-014).
  - **Suggest:** Auto / Suggest / Off on the start card + top bar; /control chip for a scored setup, a cue under
    Suggest, or topic talk (a template's setup twice in a topic).
  - **Tests:** fast 1100 pass; browser 65 pass (incl. sim-mode round trip, Suggest chip, 7 S1 template rows).
    `v2_eval detect` (54 lectures): show precision 1.00, recall 1.00 (3/3 cue moments), 0 on 23 negative lectures,
    topic chips 3/4. `v2_eval values`: 97 lines P/R 1.00.
  - **Open:** few cue moments in the recordings (cue path mostly unit-tested); period → f, crest-to-trough, "at
    384000 km" (no "from"); longitudinal waves / ellipses / cosine curve need their own templates.
  - **Next:** the user's look in the app (`--simulate tests/fixtures/lectures/incline_mode.txt` or a mic lecture),
    then S2 (time-series graphs, optional closed-list `sim` field after an A/B).
- **V2 Concept Simulation S0 done (2026-10-17).** Details and plan to S4 + Explore mode: `docs/specs/F-014-concept-simulation.md`.
  - **What works:** "Consider a block of 5 kg on a rough floor … push it with 20 newtons" → a live block-on-a-surface
    simulation beside the slide's points (forces labelled, block sliding, "computed" a / F_net); "imagine it on an
    inclined plane at 30 degrees" switches to the incline (mass and μ carried). Numbers only when said / set /
    computed from those; defaults never printed. /control sim bar (play, step, restart, speed, Values, Show, pick,
    Full stage, remove), dock **Simulation**; /display + /view follow; Full stage like a zoomed image.
  - **Code:** `src/copilot/simulation/` (contract, registry, 2 templates, values parser, detector, policy),
    `presentation/simulations.py` (controller in the engine), `RepresentationIntent` / `SimulationNotice` /
    `sim_*` commands in `core/events.py`, `web/sims/` (runtime + scenes). Contract `docs/contracts/simulation-spec.md`,
    ADR-0010 (SVG + own models, no matter.js).
  - **Tests:** fast 820 pass (+67 `test_simulation.py`, +2 cue negatives); browser: `test_simulation_browser.py` 6 pass,
    full browser suite 51 pass (45 V1 + 6 new). Independent physics review (subagent): 1 bug + 2 risks, all fixed.
  - **Runtime:** `tools/screenshot_sims.py` (both templates, both themes, slide / Full stage / static / unknown values,
    /control Values) looked at; layout fixed after the first look (arrows behind the block, labels off lines, readout
    width, sim bar position). Simulated lecture `incline_live.txt` with real Groq (18,582 tokens): found and fixed μ
    after "between … and …", a push direction taken from "the pull down the slope", and the simulation following
    onto an empty slide that V1's heading rule made from "let's see what happens" (V1 cue fixed too).
  - **Next:** S1 (6 more templates, scenario score, Suggest, `tools/v2_eval.py` replay with annotations); the user's
    look at S0 in the app (`--simulate tests/fixtures/lectures/incline_live.txt`, or a mic lecture with "consider a
    block of …").
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
| Crash recovery + soak (V1c) | 0 | marked done for now (user, 2026-10-17); not built |
| Concept Simulation (V2, F-014) | 15 | S0 verified: 2 templates, cue path, /control, browser + simulated lecture; S1–S4 + Explore planned |
| Story Scenes (V3) / Multilingual (V4) | 0 | not started |

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
- `src/copilot/presentation/`: spec, deck, content, composer, planner, engine, mathtext, demo, simulations (F-014
  controller: policy, placement, follow, sim commands, clock)
- `src/copilot/simulation/` (F-014): base (contract common parts, fmt, truthfulness), registry (union, build / solved /
  switched), templates/ (block_on_surface, incline), values (spoken quantities), detector (cue → RepresentationIntent),
  policy; `web/sims/` runtime (clock, track), draw, one scene per template
- `src/copilot/visuals/`: sources, filters, finder (CLIP), cache, clip, service (the teacher's figures first)
- `src/copilot/notes/`: library (files, flags), convert, service (open / follow / project / study material),
  reference (F-012 index)
- `src/copilot/materials/` (F-010), `src/copilot/assess/` (F-011, generator + reference guard)
- `src/copilot/display/`: hub, server, share; `web/` shared / display / control / view / export / vendor
- `tools/`: display_harness, screenshot_* (screenshot_sims: F-014), prompt_ab, replay_interpretations, materials_check, quiz_check
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
- Look at V2 S0: `artifacts/sims/*.png`; in the app `python -m copilot --simulate tests/fixtures/lectures/incline_live.txt
  --no-wait --speed 1` (≈ 19k tokens) or a mic lecture ("Consider a block of 5 kg on a rough floor …"); try the sim
  bar (Values, Full stage). Push the branch checkpoint.
- Try S4 in the app: say "let's look at the block diagram of ..." with your datasheet in My Notes; check the /control
  page at your screen size (wide notes, mistake cards); a planets / organs lecture for the card pictures.
- Review F-012 / F-013 S3c in the app: the Study material picker, the Speed switch (Standard / High performance), a
  lecture with your own PDF (e.g. STM32 notes).
- Later: classroom lapel mic with `mic_check`.
