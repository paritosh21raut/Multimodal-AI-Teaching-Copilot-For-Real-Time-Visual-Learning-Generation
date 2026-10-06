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
                                   → download ≤ 8 thumbnails (960 px) → CLIP ViT-B/32 int8 on CPU → cache
   ImageReady ←───────────────────┘   (≤ 3 accepted, best first; or none + reason)
   engine: image on the slide only if it still fits at the default type size; else kept for a later part
```
| Module | Role |
|---|---|
| `visuals/policy.py` | pure: no image on title slides, slides without teacher content, full-width diagrams (process, comparison, timeline, cause-effect, formula, tree), groups, > 4 fact tiles, two definitions side by side, abstract queries, frames where the teacher removed it; later parts keep the frame's image while there is no new hint |
| `visuals/sources.py` | httpx calls (UA header, 5 s per call) → `Candidate` (licence, author, categories) |
| `visuals/filters.py` | mime, size ≥ 400 px, aspect 0.5–2.2, free licence, blocklist (logos, flags, maps, posters, medical pathology/gore …), non-English labels (file-name codes, `X-language` categories; a diagram's file name must name the query), every distinctive query word in name/categories/description; prior: the topic article's own lead image, featured pictures, English labels, diagram words |
| `visuals/clip.py` | Xenova/clip-vit-base-patch32 ONNX int8, CPU, 2 threads, Pillow preprocessing (≈ 0.7 s for 8) |
| `visuals/finder.py` | 8 s budget (downloads get budget − 2 s; slow ones dropped); accept = CLIP ≥ 0.22 and ≥ 0.01 above the best generic distractor ("a logo", "a map", …); alternatives within 0.03 of the best |
| `visuals/cache.py` | `data/cache/images/<id>.jpg` (re-encoded, ≤ 1280 px, transparency → white) + JSON metadata (source, licence, author, query); query results cached (also "nothing found") |
| `visuals/service.py` | bus wiring, CLIP loads in the background at start; network down / CLIP missing → no images, logged |

Teacher: Remove (the frame gets no automatic image again), Change (next accepted candidate, then a deeper search
excluding all shown), own image by drag & drop / file picker (`/api/upload` → `set_image`; on a full slide the last
content moves to the next part). Layout: `display.md` § Images.

## Generated diagrams
Structured data from the Interpretation (steps, nodes, edges, events) → `DiagramBlock` → rendered client-side
as SVG by layout components (flow, cycle, tree, timeline, causal graph, two-column contrast).

## Future
- Local image generation (SD-Turbo-class) is only an optional experiment (4 GB VRAM); see ADR-0006.
- Teacher-provided labelled images (V2) are preferred over web images when they are relevant.
