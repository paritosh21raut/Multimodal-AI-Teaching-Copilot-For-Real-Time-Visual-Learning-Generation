# Visual System

## Decision: does this slide need a visual?
Deterministic policy from representation + content type + grade level:
- definition of an abstract term → usually none (typography carries it)
- physical object, organism, place, structure, historical event/person → retrieved image
- process, cycle, hierarchy, timeline, comparison, cause/effect → a **generated diagram** (SVG layout), not a photo
- mechanism with forces or motion → diagram now; simulation in V3
- formula → equation layout (+ a diagram if the variables map to a physical picture)

The LLM may suggest `visual {query, kind}`; the policy decides.

## Images (V1b, F-007b) — implemented
```
InterpretationReady(visual hint) → engine: hint remembered per frame → visuals.policy.decide(slide, hint, frame)
   search → ImageRequested ─→ visuals.service.ImageService (one job at a time) → visuals.finder.ImageFinder
                                   Wikipedia lead images + Commons search (Openverse: built, off) → filters
                                   → download ≤ 8 previews (330 px) → CLIP ViT-B/32 int8 on CPU
                                   → download the chosen ≤ 3 at 960 px (best first) → cache
   ImageReady ←───────────────────┘   (≤ 3 accepted, best first; or none + reason)
   engine: image on the slide only if it still fits at the default type size; else kept for a later part
   engine: an automatic image goes only on a slide it is about: MiniLM cosine(query, slide text) ≥ 0.25
```
Relevance gate (live test 2026-10-06: "human digestive system diagram" on the quadratic-equation slide, 0.07): the
weakest right pairing recorded is 0.33 (stomata diagram / photosynthesis process slide). It only stops clearly
unrelated images; `IMAGE_MIN_RELEVANCE` in `presentation/engine.py`, calibration test in
`tests/integration/test_embedder_real.py`. Without the embedder the gate is off (logged at startup).
| Module | Role |
|---|---|
| `visuals/policy.py` | pure: no image on title slides, slides without teacher content, full-width diagrams (process, comparison, timeline, cause-effect, a formula that opens the slide or a second one), groups, > 4 fact tiles, two or more definitions side by side (concept columns, member cards), abstract queries, frames where the teacher removed it; later parts keep the frame's image while there is no new hint. Round 4 step B: a tree beside an image is one card (female organs); a formula after text goes below the text + image (photosynthesis intro); `sibling_hint`: a subtopic that names a thing and has no hint takes its sibling's query with its own name ("female reproductive system" → "Male Reproductive System") |
| `visuals/sources.py` | httpx calls (UA header, 5 s per call) → `Candidate` (licence, author, categories) |
| `visuals/filters.py` | mime, size ≥ 400 px, aspect 0.5–2.2 (diagrams up to 2.5), free licence, blocklist (logos, flags, maps, posters, medical pathology/gore …), non-English labels (file-name codes, `X-language` categories; a diagram's file name must name the query), the distinctive query words in name/categories/description/article (all of one or two, most of three or more); `core_query`: the first two content words of a longer query or one with a picture word ("sigma bond orbital overlap" → "sigma bond", "Charles Law graph" → "Charles Law"); prior: the topic article's own lead image, featured pictures, English labels, diagram words |
| `visuals/clip.py` | Xenova/clip-vit-base-patch32 ONNX int8, CPU, 2 threads, Pillow preprocessing (≈ 0.7 s for 8) |
| `visuals/finder.py` | searches the query and, in parallel, its core phrase (Wikipedia lead images + Commons; each candidate is filtered against what it was found for, CLIP judges it against the slide's query). Long test 2026-10-06: 12 of 25 searches found nothing (the literal Commons search found 1-4 files, the filter wanted every word in the file name); on those queries 9 of 16 now find an image, 7 clearly relevant (NaCl lattice, sigma/pi overlap, H–H bond, gas molecules). 8 s budget (previews get budget − 1 s CLIP − 2.5 s full-size reserve; slow ones dropped; the best image is then fetched alone, the alternatives after it; an incomplete search is never remembered as "no relevant image"); accept = CLIP ≥ 0.22 and ≥ 0.01 above the best generic distractor ("a logo", "a map", …); alternatives within 0.03 of the best |
| `visuals/cache.py` | `data/cache/images/<id>.jpg` (re-encoded, ≤ 1280 px, transparency → white) + JSON metadata (source, licence, author, query); query results cached (also "nothing found") |
| `visuals/service.py` | bus wiring, CLIP loads in the background at start; network down / CLIP missing → no images, logged |

Teacher: Remove (the frame gets no automatic image again), Change (next accepted candidate, then a deeper search
excluding all shown), Find image on a slide without one (same command: unused candidates, else a search for the
model's hint or the slide's topic — also where the policy said no; past the first results if they were not
relevant), own image by drag & drop / file picker (`/api/upload` → `set_image`; on a full slide the last
content moves to the next part, and comes back when the teacher removes that image while the next part still holds
only it). Layout: `display.md` § Images.

## Labelled diagrams first (F-009, V2, user 2026-10-07)
Where labels teach (kind `diagram`, or the query names a structure / organ / system / cycle / apparatus —
`filters.wants_labels`; not planets, animals, places): an extra Commons search "<core> labelled diagram" runs with
the others; labelled candidates (`filters.is_labelled`: labelled / annotated / with labels, or English labels by
file-name code / category) take up to 5 of the 8 preview slots; an accepted labelled image ranks above every
accepted unlabelled one; none accepted → the best unlabelled image as before. Same filters + CLIP gate. A diagram
named "in <language> language" (not English) is refused. Query cache key `<kind>+labels`. Real searches
2026-10-07 (4 runs × 10 queries): heart, plant cell, skeleton, digestive system, water cycle → English-labelled
diagrams; Saturn / tiger unchanged; "downloads failed" (slow Wikimedia link) about equally often with and without.

## The teacher's own figures first (F-012)
Before the web, `ImageService._from_reference` looks through the figures of the study material in use (Private files
too, since nothing leaves the laptop):
- **Figures**: pypdfium2 image objects, minus page backgrounds and decorations repeated on 3 or more pages. Each is
  rendered from its page region, so labels drawn over it stay.
- **Label**: the caption, the text on the figure, the page heading and the file name. An image file the teacher added
  is labelled by its name.
- **Match**: label ↔ query by MiniLM ≥ 0.5, then the same CLIP gate as web images (0.22, margin 0.01).
- **Accepted**: the figure goes into the image cache as `source="reference"`, titled `<file> p.N`.

Change image excludes it, which brings in the web search. Measured on the fixture: the right figure scores CLIP
0.29–0.34; "plant cell" ↔ the chloroplast scores label 0.47, so it is not used. In a recorded human-body lecture,
"human skeleton" and "human heart and blood vessels" were answered by the teacher's figures.

## F-013 S4: figures the teacher asks for, per-concept pictures, the teacher's drawn figures, web pages
- **Asked figure.** "Let's look at the block diagram of STM32" / "This is the pin diagram of 8051 microcontroller" is a
  spoken cue (`understanding.cues.figure_cue`, no LLM) → `ConceptSignal.figure` = "STM32 block diagram" →
  `ImageRequested(reason="asked", kind="diagram")` for the slide being built. It goes on whatever the slide holds, as
  a large image (`ImageBlock.large`: up to 1100 px of the 1680 px body); text that no longer fits moves to the next
  part. "Look at the diagram" / "the following diagram" name nothing: no cue.
- **Order of sources** for every request: the teacher's figures (below), then Wikipedia lead images, Commons, the
  images INSIDE the best Wikipedia article (`sources.wikipedia_article_images`: the hypothalamus nuclei, the ESP32
  function block diagram), and for diagrams and asked figures **educational web pages** (`visuals/webpages.py`).
- **Web pages.** A web search (DuckDuckGo's HTML page; it refuses a burst of scripted searches with a "select the
  ducks" page, then rests 15 min and Bing answers; Bing sometimes returns unrelated pages to scripts, so only results
  whose title or address names the subject are kept) → the first 3 pages that are not PDFs, social sites, shops,
  file mirrors or Q&A, robots.txt respected, 4 s per page → the pictures whose own words (alt, figure caption, file
  name, the heading above) name every subject word and the figure type ("block diagram") → CLIP like any image.
  These are not free-licensed: the page is the credit (`licence` "© host"), for the teacher's own classroom.
  Diagram budget 12 s, asked 15 s (photos 8 s). Answers are remembered per query (`cache.QUERY_VERSION` "s4": the
  answers found before these sources are searched again once).
- **Block diagrams in CLIP.** A block diagram / schematic / pinout is boxes, lines and words: against "a page of
  text" and "a chart" it lost; for a query naming a figure type the decoys are photo-like only
  (`finder.FIGURE_DISTRACTORS`).
- **The teacher's drawn figures** (D4). Datasheets draw their figures with vector paths (ESP-WROOM-32: 0 image
  objects). `reference._drawn_regions`: the page's path objects (in page coordinates: a path inside a form XObject
  is reported in the form's own space, `reference.page_boxes` applies the forms' matrices) are clustered (gap
  28 pt), never joined across a caption or "Table N" line, framed text ("Note:" boxes) and boxes crossing a caption
  left out; each "Figure N: ..." caption no image figure took gets the nearest cluster above it (else below), plus
  the nearby pieces of the same drawing. Rotated pages: not yet. On the user's datasheet: pin layout, reflow profile,
  peripheral schematics, discharge circuit, reset circuit, PCB land pattern (6; the rotated full schematic is missed).
- **Captions** (D3). A "Figure N: ..." line under (≤ 12 % of the page) or over (≤ 6 %) a figure is its caption:
  the label is that line + the page heading + the file name; the alt text shown is the caption without its number,
  else the query, never the page's words. Index format 2 (`ref.v2.npz`; the format-1 `figures.json` is kept as
  `figures.v1.json`); files in use are re-indexed once.
- **Caption gate.** A teacher's figure whose caption names every subject word (and the asked figure type) with a
  label match ≥ 0.62 is used without the CLIP photo gate (screenshots and drawings score like "a page of text");
  an automatic photo request still needs CLIP unless the figure is drawn.
- **One picture per concept card** (D1, user: "each planet's image must be loaded"). 2-6 concepts side by side whose
  terms name objects (`policy.names_an_object`: not ideas ending -tion / -ment / -ity ..., not short acronyms such as
  SSID, not "protocols" / "devices"), in a topic that has shown a picture already: one search each
  (`reason="item:<block id>"`, "Mars" under "Planets" → "Mars planet"). Only the lead image of the Wikipedia article
  that IS the term counts (`find(lead_only=True)`, searched as "Mars planet" and "Mars"; a loose Commons search gave a
  water-cycle diagram for "Router" and a bicycle hub for "Hub" in the test24 replay), then CLIP. Shown together at
  the top of each card (`DefinitionBlock.image`, a fixed 190 px box), only when every card has one and the slide
  still fits at its type size; a card that joins later without one takes the others' away.
- **A subtopic of a visual topic** (D1): a subtopic naming a thing gets a picture of itself when its topic showed one
  (test13: Hypothalamus, Pons). The model's hint and the sibling rule come first.
- **No repeat across topics** (D2, user: "on consecutive slides or different slides when the topic is a continuation
  or the image is relevant"): an image shown under one topic is excluded from another topic's searches (and from a
  cached answer); within the topic it may come back.

## Generated diagrams
Structured data from the Interpretation (steps, nodes, edges, events) → `DiagramBlock` → rendered client-side
as SVG by layout components (flow, cycle, tree, timeline, causal graph, two-column contrast).

## Future
- Local image generation (SD-Turbo-class) is only an optional experiment (4 GB VRAM); see ADR-0006.
- Teacher-provided labelled images (V2) are preferred over web images when they are relevant.
