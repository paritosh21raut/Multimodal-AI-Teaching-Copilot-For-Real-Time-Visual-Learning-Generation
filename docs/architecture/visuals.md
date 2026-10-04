# Visual System

## Decision: does this slide need a visual?
Deterministic policy from representation + content type + grade level:
- definition of an abstract term → usually none (typography carries it)
- physical object, organism, place, structure, historical event/person → retrieved image
- process, cycle, hierarchy, timeline, comparison, cause/effect → a **generated diagram** (SVG layout), not a photo
- mechanism with forces or motion → diagram now; simulation in V3
- formula → equation layout (+ a diagram if the variables map to a physical picture)

The LLM may suggest `visual_query` + `visual_kind`; the policy decides.

## Image retrieval (V1)
1. Query building: concept + subtopic + level-appropriate qualifier ("diagram", "labeled", "illustration").
2. Sources (free, no paid keys): Wikipedia page images (REST summary), Wikimedia Commons search API,
   Openverse API. Optional Pexels/Unsplash with free keys later.
3. Ranking: CLIP (open_clip ViT-B/32) similarity to the query text + metadata/licence filters + size/aspect checks.
   Reject below a threshold → **no image rather than an irrelevant one**.
4. Cache: disk cache keyed by query; images downscaled; the licence/attribution is stored and shown small.
5. Runs async; never blocks a slide; times out at 8 s.

## Generated diagrams
Structured data from the Interpretation (steps, nodes, edges, events) → `DiagramBlock` → rendered client-side
as SVG by layout components (flow, cycle, tree, timeline, causal graph, two-column contrast).

## Future
- Local image generation (SD-Turbo-class) is only an optional experiment (4 GB VRAM); see ADR-0006.
- Teacher-provided labelled images (V2) are preferred over web images when they are relevant.
