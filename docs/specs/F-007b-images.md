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
