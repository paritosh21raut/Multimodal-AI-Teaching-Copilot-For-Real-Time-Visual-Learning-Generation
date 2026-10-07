# Current State

_Last updated: 2026-10-07 (evening): **V2 group B done** (lecture materials + past lectures, F-010); next group C
(quiz + test). Before: 2026-10-07: **V2 group A done** (themes, teacher notes, labelled images). Before:
2026-10-06 (night): **V1 long-test fixes done** (session 20261006-193517-c513; speed, lost content,
content relations, titles/parts, images, glass loader, pause colour, OpenRouter removed). Next: the user's check /
declare V1 complete; V2 not started. Before: **V1b verify round 5 done** (5 user issues + formula sets). Before: **V1b verify round 4, step D (features) done** + the user's design notes on the
step-C test (definition card, End lecture icon, classification as one tree, note card); steps A (correctness), B
(hierarchy + layouts) and C (UI) before it, after the user's
12–15 min multi-topic live test (session 20261006-112149-411e, fixture `tests/fixtures/lectures/multitopic_live.txt`).
Agreed plan: A correctness → B hierarchy + layouts (issues 1, 2, 4, 5, 8; prompt A/B + small live run) → C UI (pause
replaces freeze, first-slide glass state, zoom Back top-right, old control row removed, transcription concerns
silent / factual ones keep the card) → D features (share /display over the internet via a Cloudflare quick tunnel,
viewer role, control token; live slide editing; lecture structure tree in /control; transcript at the bottom).
Then V1c._

## Now
- **V2 started (2026-10-07).** Plan agreed with the user: ROADMAP § V2 (groups A → B → C → D; every output only when
  the teacher asks; V1c after V2). **Next: group C** (quiz + test through the share link) — ask its doubts first, then
  spec `F-011`.
- **V2 group B done (2026-10-07 evening)** (spec `docs/specs/F-010-lecture-tools-archive.md`). User answers: summary =
  a slide, teacher picks this topic (short) or whole lecture (complete), when they want; notes "all at once from what
  I teach" (= written explanations from the slides + transcript, with the slides' own content and key concepts);
  key concepts = own slide + part of the notes; assignment = theory questions, default 10, short + long, no key;
  PPTX light or dark chosen; no transcript export; past lectures openable in /control, materials from this and / or
  past lectures; students download from the share link; automatic, editable names.
  - **Built:** `materials/` (archive, content, writer, slides, render, store, service), Materials + Lectures tabs,
    lecture viewer, student Materials button, `Deck.present`, `SlideSpec.origin`, facts `terms` / groups `list`
    styles, router per-call `timeout_s`, `/web/export/` page, `tools/materials_check.py`, `tools/pptx_to_png.ps1`.
  - **Group A review fixes:** solid crescent moon, notes picker menu in the app's style, minimal empty notes card.
  - **Found + fixed on the way:** a transcript line went to the slide still being refined (now: the slide changed
    within 40 s that shares the most words); PPTX badge text off-centre and 650-weight titles too light; the viewer's
    CSS restyled the slide's own header; a Windows proactor `ConnectionResetError` logged as ERROR whenever the
    renderer's Edge closed (only that case is quiet now).
  - Verified: 501 fast (+ `test_materials` 22, `test_materials_access` 2 — fail on the old src), 26 Edge
    (+ `test_materials_browser` 3: real PDFs + PPTX, summary on the projector, viewer, students' download, notes menu,
    solid moon); real app (`--demo-slides --no-understanding`, 0 tokens): LLM cards disabled with the reason, PPTX in
    2.9 s, 84 past lectures listed, a 35-slide real lecture paged in the viewer, log clean; PPTX compared with the
    browser through PowerPoint (light + dark, formulas, images, badges); recorded lectures at 0 tokens: ≤ 2.2k tokens per
    prompt, ≈ 12k input tokens for all LLM items of a 20–30 min lecture. **Live Groq: 7,021 tokens** (Solar System
    session: topic + lecture summary, key concepts, notes, 10 questions) — outputs grounded, PDFs / slides inspected.
  - Not verified: materials from a real-LLM *live* lecture in the app (the writer ran live on a recorded one; the app
    path ran with the fake router in Edge and without LLM for real); several lectures at once only with the fake LLM.
    The teacher's own factual slips stay in the materials as taught (Solar System "1.4 billion years").
- **V2 group A done (2026-10-07), 0 LLM tokens** (spec `docs/specs/F-009-themes-notes-labelled.md`). User answers:
  dark design my call, theme button in the dock, students follow, /control dark → screenshots for the user to decide,
  notes = PDF, never projected, auto page follow kept only if accurate, manual pages too.
  - **Themes:** `set_theme` → store → `ThemeChanged` → hub → display / view / preview repaint (no reload); dock button
    + `T`. Dark redesigned: `#050608` stage with corner light, graphite cards with inset hairline + sheen, luminous
    teal / amber, images on a light mat. Tokens on any `[data-theme]` element (preview = slide theme). /control dark:
    header moon, per browser — screenshots `artifacts/app/notes_wide_control_dark.png` for the user.
  - **My notes:** right column card with tabs Structure · My notes; PDF upload → `data/notes`, page images
    (pypdfium2), ‹ › pages, wider, remove; Follow lecture (MiniLM page matching, 0 tokens). Real app run
    (photosynthesis, demo slides): definition → p2, needs → p3, steps → p4, equation → p5 (after the TeX-noise fix),
    comparison → p7, importance → p6, unrelated physics slides moved nothing.
  - **Labelled images:** extra "labelled diagram" search + labelled first (previews and ranking) for structures /
    organs / systems / cycles; foreign "in X language" diagrams refused. 4 real runs × 10 queries: labelled English
    diagrams for heart, plant cell, skeleton, digestive system, water cycle; photos unchanged.
  - Verified: 477 fast (+ `test_themes` 3, `test_notes` 8, `test_labelled_images` 6 — fail on the old src), 23 Edge
    (+ `test_themes_notes_browser` 2), 7 slow (+ notes calibration on the real model); real app (`--demo-slides
    --no-understanding`) driven in Edge, screenshots inspected (`artifacts/app/v2a_*`, `notes_*`, `theme_*`).
  - Not verified: a live lecture with real LLM + notes (nothing LLM-related changed); image downloads on the slow
    Wikimedia link fail ~25 % of searches in both modes (existing, not caused by this).
- **V1 long-test fixes (2026-10-06 night), user's 18 min test session 20261006-193517-c513** (chemical bonding →
  gas laws; all gpt-oss keys were spent before it, so it ran on the qwen backup). LLM tokens: 29,352 (prompt A/B,
  gpt-oss-120b, `GROQ_API_KEY_6`). User answers: keep "What is X?" titles, cards on the same slide ok, prompt test
  ok, remove OpenRouter completely, loader in both themes, no automatic comparison slide in V1.
  - Speed: lines waited a median 11 s (worst 37 s) before a request; the model answers in 1.3 s. Cause: every concept
    boundary was its own request 8 s apart (scraps, half sentences). Now cuts only after a finished sentence and
    scraps (< 6 words) join the next unit: simulated 9.5 → 5.3 s median, worst 44 → 18 s, 107 → 83 requests.
  - Lost content: 7 units fell back ("skipped (tpm)"); the router now waits for the first entry that frees up within
    the deadline. OpenRouter removed (config, order, docs).
  - Content relations, titles, parts, formulas: F-005 § "V1 long test fixes" (term identity, carried concept, cards
    after content, property lists, repeated-name lines, value facts, subsumed points, title casing, part runs,
    numbered variables). Replay of the lecture: 33 → 29 slides; Resonance, Intermolecular forces, Molecular
    velocities one slide each; polar / non-polar as two cards; Covalent Bond revisit I, II.
  - Images: core-phrase search + most-words match for long queries + diagrams up to aspect 2.5: the 16 failed
    queries → 9 found (7 clearly relevant).
  - Prompt: named-subtopic rule A/B'd (29,352 tokens): on gpt-oss the old prompt already named Fajan's rules,
    Gay-Lussac's law, valence bond theory → rule off; the mis-filing was the qwen backup.
  - UI: Pause in the accent green; new loader (aurora, glass card, slide developing behind frost) in light + dark,
    also in the /control preview.
  - Verified: 460 fast + 21 Edge tests (new: `test_long_test_fixes.py` 17 tests, gate 2, router 3, finder 2 — all fail
    on the old src except 2 controls); requirement changes in 3 old tests (title edit edits the title; pause green;
    glass design). Old/new replay of 8 lectures: fewer parts in 6, no content lost except intended drops; one
    regression found (discriminant cases, 411e) and fixed. Screenshots inspected (replay, glass light/dark, control).
  - Not verified live: a real lecture with the new gate/router (unit-tested + simulated on the recorded session).
  - Process slips: two shell edits (router dedent script, one `sed` line in `tools/prompt_ab.py`) instead of the Edit
    tool.
- **V1b verify round 5 (2026-10-06 evening), user's live test session 20261006-172934-8aa4** (atoms, digestive
  system, kinematics, long pause). LLM tokens: 8,510 (one accidental real-LLM run of `tools/screenshot_app.py`,
  gpt-oss-120b on `GROQ_API_KEY_5`; every check was meant to be 0 tokens). User answers before coding: 1 ok,
  2 remove Pin, 3–6 ok.
  1. Edit tools vanished on the way to them (they sat ABOVE the item, the pointer crossed the gap / the item above):
     now inside the item's top-right corner, kept 1 s after the pointer leaves, double-click an item / title = edit.
  2. **Pin removed** (deck flag, `pin`/`unpin` commands, `DeckState.pinned`, dock button, P key): it only queued new
     slides, which navigating back already does; the user expected a private browse and found it irrelevant.
  3. First-slide glass: slide-shaped glass card, light running round its edge (conic gradient + glow), a slide's
     outline drawn piece by piece with a shimmer, scan band, rising sparks; clears over the first slide (backdrop
     blur 28 → 0 in 1.2 s). Light + dark inspected.
  4. Digestive process split 6 + 4 with part II restarting at STEP 1: process capacity 6 → 10 (≤ 6 one row, 7–10 two
     rows with a turn connector, `composer.process_rows` ≡ `slide.js processRows`); a longer one continues on the
     next part counting on (`ProcessBlock.start`, "… continues from step N"), also on a teacher-opened part.
  5. Mistake card: **Keep correction** / **Keep what I said** buttons (= `dismiss`) beside the switch.
  - Found in the test: the three kinematic equations were three slides (one formula per slide) → consecutive
    slide-wide formulas form a set (≤ 4): stacked compact cards + one legend; concept columns unchanged.
  - Verified: 437 fast + 20 Edge tests (new: `test_round5_layouts.py` 5 tests fail on the old src; edit tools,
    Keep buttons, glass pieces fail on the old web files); replay of the live session: digestive process one slide
    (5 + 5), equations one slide; old/new replay diff of 5 sessions: 3 identical, the others only formula sets
    (Series 4 → 2 slides, RC 5 → 2, Kinetic 3 → 2) and Heart 3 → 2 parts (steps 7–11 continue); real app
    (`tools/screenshot_app.py`) control without Pin; screenshots inspected.
  - Not fixed (model): "bowel glider" (gall bladder) "corrected" to "small intestine" and not applied on the slide;
    Heart (0ddb) part II re-tells the cycle in other words (a repetition, now numbered 7–11); STT got slow (4–10 s)
    on long background chatter while paused (those lines are dropped anyway).
- **Verify round 4, step D (2026-10-06 night), 0 LLM tokens** (spec `docs/specs/F-008-control-features.md`,
  ADR-0009). The user's step-C test (session 20261006-160025-13fe, `verify_results/`) was good; their notes:
  - Definition card: no green side bar; a card with a "Definition" tab on its top edge and a soft tint from the corner;
    concepts side by side / member cards are one card each (term as heading). Composer height 88 → 92 px.
  - End lecture: a "leave" icon instead of the stop square.
  - Classification of matter was three equal group cards → a kind of a classification divided further grows the
    tree a level (`composer.subdivide`: Matter → Physical (Solid, Liquid, Gas) / Chemical (Pure substances,
    Mixtures)); ≤ 3 levels, only while it fits the width; other bases (by bit width / by instruction set) stay group
    cards; a tree of several levels takes no automatic image. Replay old vs new on 3 sessions: only this slide changed.
  - Note (and key idea) cards: plain labelled card like the example, no colour fill.
  - **Share with students:** /control button → Cloudflare quick tunnel (`display/share.py`, cloudflared downloaded
    once to `data/bin/`) → `https://….trycloudflare.com/view` (viewer role: slides only, sends nothing, no transcript),
    Copy, "n watching", Stop. Teacher key: only a direct localhost request is trusted; through the tunnel / LAN
    `/control`, `/display`, uploads and the control/display WebSocket need the per-run key (`/control?key=…`, printed
    in the terminal, then an HttpOnly cookie).
  - **Live slide editing:** hover an item in the /control preview → pencil / bin (title: pencil; formula: bin);
    **Add point** in the dock. Commands `edit_text`, `delete_item`, `add_point`. Final: revisions, correction switches,
    tentative moves and retitles never change the teacher's elements or title; deleted / replaced text does not come
    back on that slide.
  - **Lecture structure** (right column, replaces the slide list): topic → facet → slides, live slide highlighted,
    click = goto; one column below 980 px. **Transcript** strip at the bottom: last line, click to expand.
  - Verified: 432 fast + 19 Edge tests (17 new; the new tests fail on the old code: missing functions / commands);
    real app + real tunnel (`--simulate --demo-slides --no-understanding`): Share → link in 17 s, a separate browser
    profile opened it through the internet and saw the live slide, "1 watching"; through the tunnel /control → 403,
    /display → /view, control WebSocket refused; with the key /control connected; Stop. Screenshots inspected
    (replays light + dark with real images, control light/dark/narrow, editing, student view).
  - First runtime run found a real bug: the link was checked through this PC's DNS before it existed, the "no such
    name" answer stayed cached → now waits for "Registered tunnel connection" and checks over DNS-over-HTTPS.
  - Not exercised live: editing during a real-LLM lecture (verified in Edge with the real engine in-process); the
    presentation engine exists only with understanding on, so `--no-understanding` runs cannot edit.
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
| Presentation engine | 85 | content/composer/planner/engine: continuity, space-based layout, parts, dwell, new-topic confirmation + tentative move, revisions, truthful corrections, provisional fast path, force-new, nav-back (pin removed in round 5), overflow; verified on 3 lectures with real LLM + screenshots |
| Live display + control view | 82 | + fact tiles, group cards, side-by-side definitions, part badges, concern card (said / correct / shown, switchable), overflow reporting; KaTeX formulas + chemical subscripts (V1a); images pending (V1b) |
| Visual system (images/diagrams) | 60 | V1b: retrieval (Wikipedia/Commons + CLIP on CPU), policy, image layout, teacher controls (drop, add, change, previous/next, remove, zoom); one real-LLM lecture + replay verified; generated diagrams not started |
| V2 group A (themes, teacher notes, labelled images) | 100 | verified (0 tokens): unit + Edge + real app |
| V2 group B (materials: summary / key-concepts slides, notes + assignment PDFs, PPTX; past lectures) | 100 | verified: unit + Edge (fake LLM) + real app (no LLM) + live Groq writer on a recorded lecture (7,021 tokens) |
| Reference materials (group D) | 0 | not started |
| Quiz + test (group C) | 0 | not started |
| Concept Simulation mode | 0 | not started |
| Story Scenes mode | 0 | not started |
| Multilingual | 0 | not started (interfaces carry `language`) |

## Verification log
| Item | Unit | Integration | Runtime |
|---|---|---|---|
| EventBus, config, state store, event log, simulator | ✅ | ✅ | ✅ |
| V2 B: Materials tab (summary / key-concepts slides, notes + assignment PDFs, PPTX light/dark, names, share), past lectures + viewer, students' downloads; A-review fixes (moon, notes menu, minimal card) | ✅ 501 total (`test_materials` 22, `test_materials_access` 2) | ✅ Edge (3): real PDFs / PPTX, projector, viewer, student download | ✅ real app no LLM; PPTX vs browser through PowerPoint; `materials_check.py` 0 tokens on 4 lectures; live Groq 7,021 tokens |
| V2 A: slide theme mid-lecture (premium dark), /control dark, teacher PDF notes + follow, labelled images first | ✅ 477 total | ✅ Edge (2) + slow calibration | ✅ real app in Edge (notes follow 7 slides, dark switch); real image searches 4 × 10 |
| Verify round 5: edit tools inside the item + grace + double-click, Pin removed, glass anticipation, 10-step process in two rows + continued numbering, formula sets, Keep buttons on mistake cards | ✅ 437 total (`test_round5_layouts`) | ✅ Edge (20) | ✅ replay of 20261006-172934-8aa4 + 5-session old/new diff; real app control; glass light/dark + exit frames |
| Verify round 4 step D: share (quick tunnel, viewer role, teacher key), live editing (final), structure tree, transcript strip; definition card, End icon, sub-classification tree, plain note card | ✅ 432 total (`test_teacher_edits`, `test_sub_classification`) | ✅ `test_share_access` (real server, tunnel headers) + Edge `test_control_features_browser` | ✅ real app + real Cloudflare tunnel (student profile, refused / keyed control); replays light + dark with real images |
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
| SlideSpec validation, Deck ops/navigation/blank | ✅ | – | ✅ |
| Round 4 step C: Pause (lifecycle LIVE ⇄ PAUSED, speech in the break not interpreted), first-slide glass, zoom Back top right, mistake cards (no transcription cards) | ✅ `test_pause.py`, hub tests | ✅ `-m browser` control + display (fail on the old web files) | ✅ real app (`--simulate --no-understanding`): Pause/Resume clicked in Edge, terminal "(paused, not used)", transcript "(paused)"; screenshots inspected (glass light + dark, paused dock, cards, Back) |
| DisplayHub + server: hello, patch fan-out, reconnect snapshot, commands, role check, coalescing | ✅ | ✅ (real WebSockets) | ✅ |
| Display in Edge: 100 rapid in-place patches → 0 nodes re-created, no console errors | – | ✅ `-m browser` | ✅ |
| Display: blank, navigation, self-reconnect after a server drop (freeze removed in step C) | – | ✅ `-m browser` | ✅ |
| All 9 layouts × 2 themes (screenshots inspected) | – | – | ✅ `artifacts/display/` |
| Control view (live preview, dock, structure tree, transcript strip, share, editing, keys) | – | ✅ Edge | ✅ `artifacts/app/` |
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
- `src/copilot/notes/`: library (the teacher's PDFs in data/notes, page texts, rendering), service (open / page /
  follow the lecture, F-009)
- `src/copilot/materials/` (F-010): archive (past lectures from event logs), content (taught content per topic,
  budgeted), writer (LLM prompts, JSON, repair), slides (summary / key concepts), render (print HTML → PDF, slides →
  PPTX via headless Edge), store (data/materials), service (commands, one job at a time)
- `web/export/`: the page headless Edge draws PPTX slides on; `tools/materials_check.py` (prompts at 0 tokens,
  `--live`), `tools/pptx_to_png.ps1` (PowerPoint export to check a PPTX)
- `src/copilot/sim/simulator.py`
- `src/copilot/audio/`: sources, vad, segmenter, mic_check
- `src/copilot/stt/`: engine, pipeline, factory, cuda_dlls
- `src/copilot/presentation/`: spec (SlideSpec), deck, content (acts → pieces), composer (height model, merge, titles,
  provisional, revise/substitute/remove), planner (frame decision), engine (PresentationEngine), mathtext (formula → LaTeX), demo (scripted + stress)
- `src/copilot/display/`: hub (WebSocket fan-out, coalescing outbox; roles display / control / viewer), server
  (FastAPI/uvicorn embedded; `/view`, teacher key), share (Cloudflare quick tunnel, F-008)
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
