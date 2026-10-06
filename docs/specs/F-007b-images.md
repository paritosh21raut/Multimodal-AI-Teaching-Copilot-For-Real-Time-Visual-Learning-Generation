# F-007b: Images (V1b)

Starts after V1a is verified. Architecture: `visuals.md`, ADR-0007. User decisions (2026-10-06, fixed):
1. Images appear on the projector **automatically**. In `/control` the teacher can **remove**, **replace**, or
   **drag and drop** their own image into the slide.
2. Sources: Wikimedia Commons, Wikipedia; Openverse only if its results are educational. Never generic stock
   photos. No credit line on slides for now (licence/author stored).
3. Concrete things (organs, planets, apparatus, animals) and diagrams for processes, only where an image really
   helps. Most slides get none. **When unsure: no image.**
4. Relevance re-ranking (CLIP or similar) on **CPU (ONNX)**, never on the GPU next to Whisper; latency measured first.

User answers (2026-10-06): need-an-image signal = **LLM `visual` hint** in the existing call (A/B first), the
policy decides; images to the right of points/definitions, never next to a full-width diagram, formula or an
abstract definition. **Slides without an image keep today's centred layout; a slide with an image gets its own
designed layout (title + content + image) with no overlap and no shrinking of either.**

User answers round 2 (2026-10-06, before building; numbering = the 12 open questions):
- (1) image next to fact tiles when ≤ 4 tiles (2 columns, full type size); never next to groups.
  (2) no image on a slide that shows a generated process flow; a retrieved diagram only where the process is points.
  (5) Openverse built, off in config. (6) up to 3 accepted, cached candidates per request. (7) upload ≤ 10 MB,
  JPEG/PNG/WebP/GIF, re-encoded, ≤ 1280 px. (8) top-level `visual {query, kind: photo|diagram}`. (9) A/B old arm =
  recorded answers. (10) new `human_body.txt` fixture. (11) Xenova clip-vit-base-patch32 int8, extra `images`.
  (12) OpenRouter backup untouched in V1b.
- (3) **Content grows beside an image:** first the type shrinks (auto-fit down to 0.8) with the image kept. If it
  still does not fit, the slide stays as it was (no shrink beyond that) and the new points open the next part. The
  next part gets the **same** image, a **new** image, or **none**, by need: same while the points are still about
  the same visual thing, new when the new points name a different concrete thing/process (a different `visual`
  query), none when the new content is abstract (formula, abstract definition, full-width diagram).
- (4) **Need, not quota:** an image only where the topic needs a visual explanation (solar system, organs,
  apparatus: yes; kinetic-energy equations: no). No per-topic minimum or quota; the `visual` hint + policy decide.
- **New (teacher):** in `/control`, dragging a file over the slide preview shows the image's **designated region**
  (the right-hand image column, drawn as a dashed drop zone with the content already reflowed to the left); on
  drop the image sits there and the content adjusts (image layout). Buttons per slide: **Add image** (file picker),
  **Change image** (a different image for the same scenario: next candidate, then a new search), **Remove image**.
  The layout must stay beautiful.

## What exists
- `ImageBlock {url, alt, credit, licence}` in the contract; client `Figure` fades in after load; image goes into
  the right-hand aside next to points/definitions (`splitBlocks`); full-width diagrams take the whole body.
- `onnxruntime` (CPU) + `tokenizers` already used for MiniLM (ADR-0008). Network probe 2026-10-06: Commons search
  ("human heart diagram" → `Heart diagram-en.svg`), Wikipedia REST summary and Openverse all reachable;
  Openverse's first hit was a carved-heart photo (quality risk). Pillow is not installed (new dependency).

## Missing (plan)
| # | Part | Notes |
|---|---|---|
| 1 | **Need-an-image signal** | LLM `visual {query, kind}` hint, only for concrete things/processes; old-vs-new A/B on gpt-oss-120b first |
| 2 | **Policy** (`visuals/policy.py`) | deterministic: ≤ 1 image per slide; none on abstract definitions, formulas, slides with a full-width diagram unless the diagram *is* the image; none while the slide is provisional; frame-level cooldown; teacher-removed frames never get one again |
| 3 | **Sources** (`visuals/sources.py`) | Wikipedia page image of the exact concept (REST summary), Commons search (bitmap/drawing, `diagram`/`labelled` qualifier for processes/structures), Openverse behind config; httpx, 8 s total budget, UA header |
| 4 | **Filters** | mime, min 400 px, aspect 0.5–2.2, title/category blocklist (logo, flag, stamp, coat of arms, map unless geography, portrait unless a person) |
| 5 | **Re-rank** (`visuals/clip.py`) | CLIP ViT-B/32 ONNX (Xenova int8: text 64 MB + vision 89 MB) on CPU, Pillow preprocessing; reject below threshold; **benchmark latency first** (target ≤ 1.5 s for 8 candidates) |
| 6 | **Cache + serving** | `data/cache/images/<sha>.jpg` (≤ 1280 px) + metadata JSON; served by our server under `/media/`; no hot-linking, works if the network drops later |
| 7 | **Engine wiring** | `ImageRequested` → async worker → `ImageReady`/`ImageRejected`; engine adds the block only if the slide is still in that frame and it fits; never blocks a slide |
| 8 | **Control view** | per slide: Remove, Replace (next ranked candidate), drag & drop a file → `POST /api/upload` (size/type checked) → command `set_image`; UI never mutates state |
| 9 | **Composer + layout** | dedicated image layout (content column + image column, both at full size, no overlap); the space model reserves the image column; the teacher's image always wins |

## Re-check against the code (2026-10-06, before building)
| Where | Today | Consequence for V1b |
|---|---|---|
| `slide.js splitBlocks` / `composer._split` | image shares the aside with example/callout; no aside when any full-width block or ≥ 2 definitions | new **image layout**: image alone in its column, examples/callouts move to the content column; two layouts must stay mirrored (JS + Python) |
| `composer.block_height("image")` | fixed 500 px, aside 620 px wide | real size from the image's aspect at a fixed column width; the image is added only if the content still fits at the **default** type size (no squeeze) |
| `body_height` with two definitions (concept columns) | columns are half width | policy: no image on a slide with ≥ 2 definitions (columns unchanged) |
| `teacher_items`, `_is_empty` | an image counts as 1 teacher item | must count 0 (an image-only slide is still "empty" for the planner / dwell / retitle) |
| `describe` (CURRENT SLIDE in the prompt), `element_texts`, `remove_elements`, `substitute` | image falls into the generic branch | image never enters the prompt nor correction targets; `remove_elements` keeps it only while the slide has content |
| `Deck.update` → `annotate` | pure text annotations | unaffected |
| engine `_place` → next part | a full slide continues on part II | the image stays on the part it was put on; later parts get none (one image per frame) |
| `PresentationEngine` | single writer of slide content | applies `ImageReady` and the teacher's image commands (`remove_image`, `replace_image`, `set_image`) via `_commit`; the UI only sends commands |
| `display/server.py` | static `/web` only | `/media/<file>` from the image cache; `POST /api/upload` (stores a validated, re-encoded file, returns its URL — no state change) |
| prompt (`SYSTEM_PROMPT`, unchanged since b8d240a) | all `*_live` sessions used it with gpt-oss-120b | the A/B "old" arm can reuse those recorded answers (0 tokens) if the rebuilt prompts match the recorded `prompt_tokens` |
| fixtures | `solar_system.txt`, `photosynthesis.txt`, `chemistry_*`, 5 physics/maths `*_live` | no human-body lecture yet |

## Measured (build log)
**Step 1 — CLIP latency** (`tools/bench_clip.py`, this laptop's CPU, 8 Commons images, median of 3–5):

| model | threads | load | text | preprocess ×8 | vision ×8 | 8 candidates total |
|---|---|---|---|---|---|---|
| **int8 (chosen)** | 2 | 1.6 s | 8 ms | 134 ms | 542 ms | **≈ 0.69 s** |
| int8 | 4 | 1.5 s | 11 ms | 133 ms | 487 ms | ≈ 0.63 s |
| fp32 | 2 | 2.7 s | 14 ms | 144 ms | 1203 ms | ≈ 1.36 s |

Target ≤ 1.5 s met with int8 at 2 threads (no GPU). Both pick the right image for 8/8 queries; fp32 separates
slightly better (wider gaps), int8 is enough with the filters + distractor margin below.

**Step 2 — sources, filters, cache** (`visuals/{sources,filters,cache,finder}.py`; `tools/image_eval.py`, 30
labelled concepts from the fixture lectures, real network, contact sheet `artifacts/image_eval/sheet.html`):
- Search ≈ 1.5–2.5 s, downloads ≈ 1–2 s, CLIP ≈ 0.2–0.7 s → 2.5–6 s per query (budget 8 s; slow downloads are
  dropped at the deadline, the rest is still ranked). Since the live run: 330 px previews for CLIP, 960 px only for
  the chosen images (see "Real-LLM run" below).
- Found by looking at the sheet and fixed: diagrams with Persian/Arabic/Greek/… labels (language codes in file
  names + `X-language` categories; a diagram's file name must name the query in English), autopsy / cancer images
  (blocklist), off-topic matches ("Rock cycle" for water cycle: every distinctive query word must appear in the
  file name, categories or description), the Sun's sunset photo (the topic article's own lead image gets a prior).
- Result (third run): first image relevant for **28/28** queries that returned one (2 were throttled by Wikimedia
  during the 300-request batch; re-run alone they work). Weakest: "states of matter" → a small classification
  chart. Alternatives (for Change image) are kept only within 0.03 of the best score.
- Tests: `tests/unit/test_visuals_finder.py` (recorded HTTP `tests/fixtures/http/*.json`, fake scorer; network
  down / timeout → no image, no error; real CLIP in a slow test).

**Step 3 — policy** (`visuals/policy.py`, `tests/unit/test_image_policy.py`): table above; space model knows the
image layout (`composer.image_column_px/image_of/with_image/split_to_fit`; `fits` allows the 0.8 shrink beside an
image; `fits_unshrunk` for automatic images). An image is never content (`teacher_items`, `element_texts`,
`remove_elements`).

**Step 4 — prompt A/B: PASSED (2026-10-06), visual rule live.** `tools/prompt_ab.py --dry` rebuilt 40 recorded units
of 6 sessions exactly (logged prompt size matched). Real run, gpt-oss-120b, units
`20261005-232616-f7cb:1,2,6,8 20261005-233249-77ea:5,7 20261006-015047-44b7:1,2 20261006-014301-5830:1
20261006-020147-a3e0:0 20261006-015722-69aa:1` (6 concrete, 5 abstract), results `artifacts/prompt_ab/20261006-0921*.json`
and `-0924*.json`:
- Validity 11/11 (0 repaired). Same topic 10/11, same relation 10/11 (differences are naming variance).
- Hints: Sun (photo), Saturn rings (photo), stomach diagram, "speed and velocity diagram" (abstract → refused by the
  policy, which now ignores picture words like "diagram"); none for kinetic/potential energy, quadratic, neutralisation.
- Truthfulness: one new-arm answer added the quadratic formula the teacher only named; re-sending the OLD prompt
  (`--old`) gave the same addition → sampling variance of the model, not the rule (open issue outside V1b).
- Tokens: 8,925 + 15,299 + 2,084 (old-prompt check) = 26,308. The first run sent 4 units, then the only key with quota
  hit its 8k TPM and 7 units fell back unsent (0 tokens); `prompt_ab.py` now paces by tokens.
`SYSTEM_PROMPT = system_prompt(True)` (+ ≈ 86 prompt tokens/call).

**Step 5 — engine wiring:** `ImageRequested` / `ImageReady`; hint remembered per frame (a new topic's first unit can
wait on the previous slide — found in the solar lesson: Galaxies lost its hint); search result applied to the
requested slide or the frame's current part; full-width content arriving on a slide with an automatic image removes
the image; beside an image a piece that does not fit even shrunk goes whole to the next part, which keeps the image
(user answer 3). `tests/unit/test_presentation_images.py` (10).

**Step 6 — layout** (`slide.js`, `slide.css`): content | image column, no overlap, no credit line, aspect box
before load, fade-in; facts beside an image in 2 columns. Bug found by looking: content taller than the body
overflowed upwards into the title (invisible to `scrollHeight`, so auto-fit never shrank) → `safe center`.

**Step 7 — /control:** drag over → dashed drop zone at the image's place with the content already reflowed; drop /
Add image → `/api/upload` → `set_image`; Change / Remove; wrong type → message, no change.
`tests/e2e/test_images_browser.py` (Edge): drag, drop, layout gap ≥ 40 px, nothing above/below the body, PDF refused,
remove, automatic + change, file picker, teacher image on a full slide → part II inserted after it.

**Zero-token verification (2026-10-06):** `tools/screenshot_lessons.py` light + dark with the real image service:
human body 4/5 slides with an image (heart, lungs, digestive system, skeleton — all relevant; the breathing process
flow has none), solar 2/3 (Moon, Milky Way; the overview with groups + tiles none), physics 0/4 (the hint
"kinetic energy" refused as abstract). Replays of the 5 `*_live` sessions: unchanged layouts, no images (no hints).
Tests: 380 fast, 11 browser, 5 slow. Self-review fixes: failed searches (network / timeout / no CLIP) wait 60 lecture
seconds before a retry (the remembered hint would otherwise search on every unit); no image on title slides;
uploaded file names decoded for the alt text.

**Real-LLM run (2026-10-06, `tools/screenshot_app.py --lecture --simulate tests/fixtures/lectures/human_body.txt
--speed 1`, session 20261006-093559-e5ce):** 18 interpretations, 0 fallbacks, 38,892 tokens (23,881 gpt-oss-120b +
15,011 qwen3.8-27b when the one fresh key hit its TPM). Model queries: "human heart", "human heart chambers", "human
lungs anatomy", "digestive tract diagram", "human skeleton" — all concrete and on topic. Only 1/4 slides got an
image: two searches lost every candidate ("downloads failed": eight 960 px downloads took 3–19 s on a slow link) and
"human heart" was cached as "no relevant image" although most previews had not arrived. Skeleton (6 fact tiles) and
the breathing process correctly got none.
Fixes: candidates are judged on 330 px previews (≈ 15–60 KB) and only the chosen ≤ 3 are downloaded at 960 px (best
first, alone); an incomplete search is "incomplete", never remembered as "no relevant image".
Zero-token replay of the same session with the fixed finder (`tools/replay_interpretations.py
20261006-093559-e5ce light --images`, fresh cache): 4/4 searches found an image; heart diagram, lungs, digestive
system (all relevant); the breathing process went to Lungs part II at full width (user answer 3); skeleton none.
The solar-system real run was skipped to stay inside the token budget (the A/B and this run used ≈ 65k).

**/control round 2 (user, 2026-10-06):** the image tools no longer take a row: a small floating bar on the preview
(bottom right) — "Add image · or drop one on the slide" without an image; ‹ n / m › · Change · upload · remove with
one. No auto/teacher label. Status (searching, nothing else found, upload errors) as a small chip bottom left.
- Previous / next: every image a slide has shown (automatic, Change, the teacher's own) in order; a new one goes to
  the end, nothing is lost (`image_prev` / `image_next`, `ImageChoices` → control only).
- Click the image in the preview: it fills the projector (`zoom_image` → `DeckState.zoom`); /control shows the same
  inside its preview (never full window) with a "Back to slide" button; Esc, a click on the image or Back ends it
  (`unzoom_image`); navigation or the image leaving the slide also ends it. New content keeps arriving behind it.
- Verified: `tests/e2e/test_images_browser.py` (arrows 4/4 → 3/4 → 4/4, zoom ≥ 80 % of the projector, inside the
  preview on /control, all three ways back), unit tests for the history and zoom rules, screenshots light + dark
  (`artifacts/app/images_*`, `dark_*`). Bug found by the test: a small file stayed small when zoomed → sized from
  the aspect ratio.
Tests: 384 fast, 11 browser, 5 slow.

**Not verified yet:** solar-system real-LLM run; share of slides with images over more real lectures; the new
download path on a fast network in a full live run (replay only).

## Risks
- Relevance (the main risk) → threshold tuned on a labelled set; when unsure, no image.
- CPU load of CLIP during a lecture (MiniLM also on CPU, Whisper on GPU) → measure, run in a thread, at most one job.
- Prompt change for the visual hint costs tokens and needs an old-vs-new A/B on gpt-oss-120b.
- Classroom network off → no images, no errors on screen.
- Licences: store licence/author even without a credit line (needed for exports later).

## Tests
- Unit: policy table, query building, filters, ranking with fixed embeddings, cache, upload validation.
- Integration: recorded HTTP responses (saved fixtures) → worker → engine patch; teacher remove/replace/upload.
- Real network `-m net` (small); CLIP latency benchmark script with numbers in this spec.
- Labelled relevance set (≈ 30 concepts from the fixture lectures): precision of shown images, share of slides with images.
- Browser: fade-in, Remove/Replace buttons, drag & drop upload in Edge.

## Runtime exit check
Two lecture fixtures (human body, solar system) with the real LLM (small, tokens reported) or recorded answers:
images only on concrete/process slides, all relevant on inspection, ≤ ~30 % of slides with images; teacher
remove / replace / drag-drop verified in Edge with screenshots; CLIP latency and CPU numbers recorded.
