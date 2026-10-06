# Current State

_Last updated: 2026-10-06 (evening): **V1b verify round 4, step C (UI) done**; steps A (correctness) and B
(hierarchy + layouts) before it, after the user's
12–15 min multi-topic live test (session 20261006-112149-411e, fixture `tests/fixtures/lectures/multitopic_live.txt`).
Agreed plan: A correctness → B hierarchy + layouts (issues 1, 2, 4, 5, 8; prompt A/B + small live run) → C UI (pause
replaces freeze, first-slide glass state, zoom Back top-right, old control row removed, transcription concerns
silent / factual ones keep the card) → D features (share /display over the internet via a Cloudflare quick tunnel,
viewer role, control token; live slide editing; lecture structure tree in /control; transcript at the bottom).
Then V1c._

## Now
- **Verify round 4, step C (2026-10-06 evening), 0 LLM tokens:**
  - Pause replaces Freeze: `pause` / `resume` → the app switches the lifecycle LIVE ⇄ PAUSED; the understanding
    service drops lines heard while paused (lines heard before are still interpreted); the hub marks them
    "(paused)" in the /control transcript, the terminal "(paused, not used)". Dock button with a pause icon, blue when
    on (`--pause` token), PAUSED flag on the preview, `Space` key. Navigation and image controls keep working.
    `freeze`/`unfreeze` and `DeckState.frozen` are removed (deck test now checks pin/blank; the display browser
    test lost its freeze half).
  - /display before the first slide: no text; coloured light drifts behind a framed frosted pane (CSS only).
  - Zoom: "Back to slide (Esc)" top right of the preview; the flags hide while zoomed.
  - The old control button row (`DOCK_CONTROLS = false`) and its CSS are removed.
  - Mistake cards: factual / conceptual / formula only — "You said … · The slide shows …" with one switch (Show what
    I said ⇄ Show correction) and × to close; no OK / approval. Transcription concerns never reach /control; applied
    silently at ≥ 0.4 (all 86 recorded ones were) and logged as `[HEARD] wrong -> right`. RULES.md rule 8 updated.
  - Verified: 415 fast + 16 Edge tests (7 new; the 4 UI ones fail on the old web files); real app with a simulated
    lecture (no LLM): Pause / Resume clicked in Edge, terminal and transcript checked; screenshots inspected.
  - Not exercised live: Pause with the microphone and the real LLM (unit-tested at the service with the real bus).
- **Verify round 4, step B (2026-10-06 evening), 67,465 LLM tokens (A/B 27,942 + live run ≈ 39,523, gpt-oss-120b
  on `GROQ_API_KEY_main`, 3 calls borrowed `_5`):**
  - Issues 1–2, members of a set: a defined member of a facet's set ("Types": PAN …; "Components": nodes …) is a card
    under the facet's title (layout `members`, not the term as title); further members join as cards (2 | 3 | 2×2 |
    3+2 | 3×2, ≤ 6); an automatic image yields to them; a member's details stay in its card (≤ 3 with 3+ cards); a
    member explained in depth continues on its own slide (titled by it, same crumb, no part), then the set's next
    part. Kinds given as "Name – meaning" in a classification are defined members (live run: PAN). Concept columns
    with formulas (energy) unchanged.
  - Issue 4: several classifications of one thing are ONE groups block (the first tree becomes its first card, labels
    "By bit width", "By memory type" …). The model still mixes "by instruction set" with "by memory architecture".
  - Issue 5: a formula after text beside an image: text + image on top (image ≤ 380 px), formula full width below.
  - Issue 8: a tree beside an image is one card (female organs keep the image); a subtopic that names a thing and has
    no hint takes its sibling's query ("Male Reproductive System"); a `sub_concept` that names a thing is not absorbed
    into the sparse definition slide (female had no slide of its own); a tree that does not fit moves whole.
  - Image column: slide.js now sizes it from 740 like the composer (step A left 700 there).
  - Prompt: a hierarchy rule ("members of a set keep its subtopic") passed the A/B (`prompt_ab.py --both`, 6 units:
    subtopic right in 3 more) but the live run (`hierarchy_live.txt`) showed it over-applied (components stayed under
    "Types", PAN as a list item) → NOT live (`system_prompt(hierarchy=True)` keeps it for a later attempt).
  - Verified: 410 fast + 12 Edge tests (10 new step-B tests; the 8 layout/image ones fail on the step-A code); replays with real
    images of the live test and the live run (screenshots inspected: Types 4 cards, Components 3 cards with the
    nodes' details, MCU types one set of group cards, photosynthesis intro with image above the formula, male system
    image from the sibling hint); no-image replays of 5 sessions old vs new: energy and kinematics identical,
    chemistry identical, the rest only the intended changes.
  - Open: the model's subtopic mistakes (components under "Types" in the live run; female organs in the male unit
    because the gate joined the lines); fallback still cannot open a new topic (Chemistry under Atoms, quadratic under
    Digestive) — not done in B.
- **Verify round 4, step A (2026-10-06 evening), 0 LLM tokens:** the live run used only qwen on one key and 25 of ~75
  units fell back. Root causes and fixes (each with a test that fails before / passes after):
  - Keys: `GROQ_API_KEY_main` was never read (only `GROQ_API_KEY`, `_2`…`_9`). Now any `GROQ_API_KEY_<name>`, in
    `.env` order; one ACTIVE key per model until 95 % of its daily quota, then the next, wrapping to the top
    (remembered in `data/llm_usage.json`); a full per-minute bucket waits ≤ 4 s before borrowing the next key for one
    call. `[QUOTA]` shows each key by its `.env` name (IN USE / ok / unused / SPENT, free again in …). `.env` has 5
    Groq keys (`_main`, `_2`…`_5`), not 6.
  - /display needed a reload after slide changes (popped-out window or background tab): the new slide waited on an
    animation frame Edge pauses there, and in-place updates cancelled it → CSS animation; browser test without frames.
  - Fallback ("MATLAB", "Thank you very much", lost "Chemistry is the branch …"): sentence-level, joined split
    sentences, "is called" definitions, announcement used only when the unit talks about it, asides dropped.
  - Coverage guard duplicates (Benefits, Microcontroller I): stems + Whisper's early sentence end.
  - Headings swallowing later points (Microcontroller III, 5G, Reproductive I); "C++" dropped as "C"; a
    classification with empty named groups (memory type) lost.
  - Digestive diagram on the quadratic slide: automatic images need MiniLM similarity(query, slide text) ≥ 0.25.
  - Solar thin part IV: Find image moved two points to a new part and Remove image did not bring them back → it does.
  - Lonely last parts: overflow report held after the slide shrank; body budget 700 → 740 px (measured 754–763 px).
  - Verified: 400 fast + 12 browser + slow embedder tests; `[QUOTA]` with the real `.env`; replay of the session with
    real image search and the current fallback (`tools/replay_interpretations.py <session> light --images`, which now
    re-runs fallback units): screenshots `artifacts/replay/20261006-112149-411e_light_*.png` inspected.
  - Open for step B: Types/Components members split (1, 2), classification grouping (4: the model merged instruction
    set + memory architecture), intro image beside a formula (5), sibling image consistency (8; with the 740 px budget
    the female organs fit as a tree on part I, and trees take no image), fallback cannot open a new topic ("Chemistry"
    lands under Atoms and keeps the atom image), quadratic definition stays under the Digestive breadcrumb.
- **V1b round 3 (2026-10-06):** empty image bar = Find image · Add image · "or drop one"; Find = `change_image` on a
  slide without an image (unused candidates, else hint / topic search, deeper after "no relevant image").
  Hub `image_status` now carries `request` (auto | change) — the "No other image found" chip never showed before
  (it checked `reason`, which is the why-none text). Controls dock (pill groups, slide n / m, on = filled);
  `DOCK_CONTROLS = false` in `web/control/app.js` restores the old row (verified by screenshot). 385 fast + 11
  browser + 5 slow. 0 LLM tokens.
- **V1b (F-007b "Measured"):** CLIP int8 on CPU ≈ 0.7 s / 8 candidates (target 1.5 s); Wikipedia + Commons sources,
  filters, disk cache, `/media`, policy, engine wiring (`ImageRequested`/`ImageReady`), image layout, `/control`
  drag & drop (drop zone) / Add / Change / Remove image, `/api/upload`. 30-concept labelled set: first image relevant
  in 28/28 answered. Lessons (real image service, 0 LLM tokens): human body 4/5 slides with an image, solar 2/3,
  physics 0/4.
- **V1b round 2 (2026-10-06):** prompt A/B passed (11/11 valid; the one untruthful addition also comes from the old
  prompt) → `SYSTEM_PROMPT = system_prompt(True)`. Real Groq `human_body.txt`: model queries all concrete and on topic,
  but only 1/4 slides got an image (slow link: full-size downloads of every candidate missed the budget) → previews
  at 330 px for CLIP, full size only for the chosen; replay of that session (0 tokens): 4/4 found, 3/5 slides with a
  relevant image. /control: image tools float on the preview, previous/next through a slide's images, click → image
  full screen on /display (inside the preview on /control, Back / Esc / click). 384 fast + 11 browser + 5 slow.
  Tokens today: 10,420 (earlier smoke run) + 26,308 (A/B) + 38,892 (human_body run) = 75,620. Solar real run skipped
  (budget).
- **Groq quota (2026-10-06 ≈ 09:40):** keys 2 and 3 nearly spent on gpt-oss-120b, key 4 ≈ 145k left. A single key
  hits the 8k TPM in a live lecture → some calls go to qwen3.8-27b. OpenRouter backup still 404 (untouched).
- **V1a round 2 (F-007a "Round 2"):** root causes + fixes for all 7 user issues; 323 fast + 9 browser tests; replays of
  the 5 live sessions (0 tokens) + real Groq energy ×2 / kinematics (≈ 43k tokens incl. a 2.2k probe), 0 fallbacks.
  Biggest find: gpt-oss-120b flattens `items.formula` → half the formulas were silently dropped since M3 (fixed).
  Live transcripts saved: `tests/fixtures/lectures/*_live.txt`. New tools: `export_transcript.py`,
  `replay_interpretations.py`. Open: model keeps several concepts under subtopic "Definition" (kinematics parts).
- **V1 (2026-10-06):** order V1a → V1b → V1c (ROADMAP). Specs: `docs/specs/F-007a-formulas-layout.md`,
  `F-007b-images.md`, `F-007c-robustness.md` (user answers recorded in each).
- **V1a done (see F-007a "Result"):** KaTeX vendored + `web/shared/rich.js`; `presentation/mathtext.py`
  (plain/spoken formula → LaTeX, no prompt change); chemical subscripts in all slide text; plural title templates;
  step/process/cause-effect/teaser polish; **M4 bug fixed**: points mentioning the slide's term were dropped as
  duplicates. 274 fast + 7 browser tests. Screenshots inspected: `artifacts/display/`, `artifacts/lessons/physics_*`,
  `artifacts/app/lecture_force_motion/`.
- **Real LLM run (user, session 20261006-010822-cdb5):** 8/10 by qwen3.8-27b (gpt-oss-120b quota spent), ~33k tokens,
  2 fallbacks at the end; `KE = 1/2 mv²` rendered wrongly → converter fixed + tests. OpenRouter backup now 404 (model no longer free).
- **M4 / MVP: accepted by the user 2026-10-05.**
- **Live chemistry test 2026-10-05 (session 20261005-230039-f084), fixed:**
  1. The lecture ended after 43 s: forced 15 s split inside a pause → negative frame count → audio thread crash.
     Fixed in the segmenter + the pipeline now drops only the pending utterance on a segmenter error.
  2. Definition stuck at "the branch of science which deals": the definition had no [S#] ref, the model's
     completion was dropped as an unknown ref. Definitions are now revisable.
  3. Coverage guard: complete content sentences the model leaves out are shown as said (logged).
  4. `relation: "transition"` no longer costs a repair call.
  Verified: replay of the user's transcript (`tests/fixtures/lectures/chemistry_live7.txt`, real Groq): 8/8 by LLM,
  0 repaired, 0 fallbacks, 3 slides, full definition, matter facts shown (screenshots
  `artifacts/app/lecture_chemistry_live7/`). 215 fast tests.
- **Architecture decision (user, 2026-10-05):** the free tier is for development only (continuous 5–10 min lectures);
  no extra fallback models layer. Later the same system moves to a paid API for long lectures. Keep LLM use efficient.
  Groq primary (3–4 keys, used one after another), OpenRouter as backup, deterministic fallback when all fail.
- **Done this round (on 0e8bff5):** Groq keys `GROQ_API_KEY`, `_2` … `_9` → per-key entries, same model first;
  Ollama opt-in only; `copilot.llm.usage` daily ledger (429 TPD body parsed, spent key skipped across sessions);
  `[QUOTA]` printed before READY; `/control` + `/display` auto-open (`--no-open`). Verified: 203 fast + 4 browser
  tests; real run photosynthesis (session 20261005-225236-fff4): 12/12 by LLM, 0 fallbacks, 5 slides.
- **Next: user test** with the keys added to `.env` as `GROQ_API_KEY_2`, `_3`, … (check the `[QUOTA]` lines).
- Prompt shrink A/B (gpt-oss-120b, 11 recorded units): 2135 → 1860 tokens/call, both 11/11 valid, but the shorter
  prompt was less truthful in 3/11 → not adopted. Further token savings need a different approach (later).
- **Next: user real-mic re-test** of the solar-system / chemistry style lectures (`python -m copilot`), ideally on
  a fresh Groq daily quota. Watch: concise slide text, facts as tiles, no "(cont.)", corrections shown truthfully
  with the teacher card (OK / Show as I said).
- **Decision needed soon (LLM budget):** Groq free tier caps openai/gpt-oss-120b at 200k tokens/day. One
  interpretation ≈ 2.3k tokens (system prompt ≈ 1.45k), i.e. ≈ 85 interpretations ≈ 15–20 lecture minutes per day on
  the main model; today's tests exhausted it and the run fell back to qwen (8k TPM → skips) and OpenRouter (50/day).
  Options: shrink/split the system prompt, longer units, add more free models to the router, or a local model.
  **Confirmed by session 20261005-110717-dc56 (states of matter): all three remote models rate-limited (both Groq
  models at ~199k/200k TPD, OpenRouter free upstream-limited) → almost every unit used the deterministic fallback.
  Superseded by the 2026-10-05 architecture decision above (several Groq keys, no extra provider layer).**
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
| Live display + control view | 82 | + fact tiles, group cards, side-by-side definitions, part badges, concern card (said / correct / shown, switchable), overflow reporting; KaTeX formulas + chemical subscripts (V1a); images pending (V1b) |
| Visual system (images/diagrams) | 60 | V1b: retrieval (Wikipedia/Commons + CLIP on CPU), policy, image layout, teacher controls (drop, add, change, previous/next, remove, zoom); one real-LLM lecture + replay verified; generated diagrams not started |
| Reference materials | 0 | not started |
| Post-lecture outputs | 0 | not started |
| Concept Simulation mode | 0 | not started |
| Story Scenes mode | 0 | not started |
| Multilingual | 0 | not started (interfaces carry `language`) |

## Verification log
| Item | Unit | Integration | Runtime |
|---|---|---|---|
| EventBus, config, state store, event log, simulator | ✅ | ✅ | ✅ |
| Verify round 4 step B: member cards (≤ 6) + member in depth, classifications as one groups block, image above a formula, tree beside an image, sibling image hint, sub_concept not absorbed, whole trees | ✅ 410 total | ✅ Edge (12) | ✅ A/B 27,942 tok + live run ≈ 39.5k tok (hierarchy prompt rule rejected); replays with real images inspected; 5-session old/new diff |
| Verify round 4 step A: keys (any name, .env order, one active key, minute wait/borrow), /display without animation frames, fallback, coverage stems, headings, C++, empty groups, image relevance, image tail back, overflow hold, 740 px budget | ✅ 400 total | ✅ Edge (12) + slow embedder calibration | ✅ 0 tokens: `[QUOTA]` with real .env; replay of 20261006-112149-411e with real images + current fallback |
| V1b images: finder (previews → CLIP → full size), policy, engine, layout, /control (drop, add, change, ‹ ›, remove, zoom) | ✅ 384 total | ✅ Edge (2 image tests) | ✅ real Groq human_body (queries) + zero-token replay with real image search (4/4 found); A/B 11/11 valid |
| V1a: formulas → KaTeX (`mathtext`, `rich.js`), chemical subscripts, layout polish, dropped-point fix | ✅ 52 + 9 | ✅ Edge (3 tests) | ✅ 0 tokens: display set, physics lesson, real app; real LLM (qwen) force_motion |
| V1a round 2: parser (fractions, brackets, ions, spoken), equations in text, concept columns, list styles, peer pairing, flattened-formula parsing, math-aware guard, stale-tab reload | ✅ 323 total | ✅ Edge (9 tests) | ✅ replays of 5 live sessions; real Groq energy ×2 + kinematics |
| Several Groq keys, daily quota ledger, `[QUOTA]` at startup | ✅ | – | ✅ photosynthesis real run, quota printed |
| Auto-open /control + /display, no duplicate tabs, `--no-open` | ✅ | ✅ browser (real app + Edge) | ✅ |
| Segmenter: forced split inside a pause, segmenter error keeps the lecture going | ✅ | – | replay ✅, live mic pending |
| Definition completed in place across units (revisable ref) | ✅ | ✅ engine | ✅ chemistry replay |
| Coverage guard (dropped sentences shown as said) | ✅ | offline replay 128 units | ✅ chemistry replay |
| App lifecycle READY → Enter / control Start → LIVE → q / control End → ENDED | – | – | ✅ (Ctrl+C not exercised) |
| Segmenter, VAD, Whisper engine and guard, speech pipeline | ✅ | ✅ (GPU) | ✅ WAV real time: p50 ≈ 650 ms, VRAM ~1.1 GB |
| M1 review fixes (forced-split loss, stop hangs, mic leak, device "0", watchdog) | ✅ regression tests | – | – |
| Real mic (human voice, Intel SST array) | – | – | ✅ mic_check rms −37.5 dBFS, accurate transcript, conf 0.92; live run 7 segments, 0 dropped, STT p50 781 / p95 971 ms |
| SlideSpec validation, Deck ops/navigation/pin/blank | ✅ | – | ✅ |
| Round 4 step C: Pause (lifecycle LIVE ⇄ PAUSED, speech in the break not interpreted), first-slide glass, zoom Back top right, mistake cards (no transcription cards) | ✅ `test_pause.py`, hub tests | ✅ `-m browser` control + display (fail on the old web files) | ✅ real app (`--simulate --no-understanding`): Pause/Resume clicked in Edge, terminal "(paused, not used)", transcript "(paused)"; screenshots inspected (glass light + dark, paused dock, cards, Back) |
| DisplayHub + server: hello, patch fan-out, reconnect snapshot, commands, role check, coalescing | ✅ | ✅ (real WebSockets) | ✅ |
| Display in Edge: 100 rapid in-place patches → 0 nodes re-created, no console errors | – | ✅ `-m browser` | ✅ |
| Display: blank, navigation, self-reconnect after a server drop (freeze removed in step C) | – | ✅ `-m browser` | ✅ |
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
| Verify round 5 (states of matter, all LLMs rate-limited) | ✅ 192 fast | ✅ Ctrl+C check | root cause = LLM quota (next build). Fixed now: fallback names the topic from an opening "let us learn about X" (deck was titled "Lecture"); httpx ConnectTimeout (Ollama not running, Windows) → Unavailable + 60 s cooldown instead of a 4 s retry on every unit; Ctrl+C with pages open no longer prints ASGI CancelledError tracebacks |
| Verify round 4 (user: slides did not show in the browser) | ✅ 190 fast + 3 Edge | ✅ | server-side fine (replay of session 20261005-100233-e18f in Edge: 13 patches, 0 errors). Cause: stale browser cache mixing an old slide.js with the new control script (missing export → page fails). Fixed: version-stamped client URLs + import map, visible error banner, empty slide removed after a tentative move. Edge request log: every /web file fetched with ?v= |
| Verify round 3 (user: chemistry, solar system, microcontroller; mostly on the backup model, main-model quota spent) | ✅ 188 fast | – | fixed: browser kept an old slide.js/css (no cache headers) → blank fact-tile slide, missing groups, stacked definitions; fallback now makes definitions and follows "let's learn about X"; sparse definition slide absorbs its supporting tree/facts; next part waits 6 s not 15 s; split-word mis-hearing hint. Not yet re-run live |
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
  provisional, revise/substitute/remove), planner (frame decision), engine (PresentationEngine), mathtext (formula → LaTeX), demo (scripted + stress)
- `src/copilot/display/`: hub (WebSocket fan-out, coalescing outbox), server (FastAPI/uvicorn embedded)
- `src/copilot/core/`: interpretation (Interpretation contract), memory (outline matching, rolling summary), textutil
- `src/copilot/llm/`: providers (OpenAI-compatible), ratelimit, router (`build_router` from config `[llm]`)
- `src/copilot/understanding/`: filter, embedder (MiniLM ONNX), tracker, gate, prompt, grounding, interpreter, service
- `web/`
  - `shared/` (tokens.css, slide.css, slide.js renderer + fit, rich.js KaTeX + chemical subscripts, ws.js)
  - `display/` (projector)
  - `control/` (teacher)
  - `vendor/` (htm+preact, katex 0.16.22)
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
  - The model sometimes swaps variable symbol/meaning in formulas (formulas render with KaTeX since V1a).
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
- Display overflow is reported to the server (`SlideOverflow`) and the planner continues on a new slide.
- Mic levels on the Intel SST array are low (≈ −37 dBFS speech) but transcribe well.
- Fixed: terminal READY/LIVE lines garbled by unflushed prints (all app prints now flush).

## User actions pending
- Optional: install Ollama + `ollama pull qwen2.5:3b` (local LLM fallback).
- Later: try the classroom lapel mic with `mic_check`.
