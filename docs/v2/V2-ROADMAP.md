# V2 roadmap — Explainer Stage (F-017, 2D) · 2026-10-26

Spec `F-017-explainer-stage.md` · contract `docs/contracts/stage-spec.md` · decision ADR-0011 · look reference
`tools/stage/reference/` · history of the look choice `V2-LOOK-SAMPLES.md`.
Five build sessions (E1–E5). Each ends at a **gate** the user judges on a contact sheet or a live run. The next
session starts fresh from its card. Order: accurate basics first, then breadth, then live, then evaluation.

| # | Card | Builds | Gate (stop point) |
|---|---|---|---|
| E0 | (done 2026-10-26) | reviews, 3D samples, 2D samples ×3 rounds | look = explainer_flat + chibi ✔ |
| E1 | `E1-stage-renderer.md` | `web/stage/` modules ported from the reference (motion, chibi cast, IK, animals, about 60 props, 10 backdrops, overlays), `stage.patch` player, motion pack + clip table, catalog, shoot tool | sheets: cast × poses, props at true relative size, backdrops, 8 reference scenes re-made from patch JSON; contacts + perf measured |
| E2 | `E2-stage-core.md` | event log, op validator + provenance, law modules, director (layout, rows, framing), acting (clips, time-warp, IK, sockets, mirror), timeline, fixture replays (0 tokens) | sheet of 12 op-script scenes, physics checked by tests |
| E3 | `E3-live-language.md` | fast path, LLM delta (cached prompt), lookup ladder, stage on slides + Imagine Mode + sim mode, Whisper prompt, fix word, safety, /control | one live run (~15k tokens): draft p50 ≤ 1 s, full p95 ≤ 3 s, scenes right |
| E4 | `E4-views-diagrams-laws.md` | top / cutaway / split / inset views, diagram recipes, more laws, templates → recipes, continuity edits | sheet of 12 science scenes; every number provenance-checked |
| E5 | `E5-evaluation.md` | corpus, golden replays, blind rating page, metrics, ablations, teaching features, paper figures | metrics vs F-017 §9; user verdict on a 10-min lecture |

**Polish rounds (P).** The user wants the people and props improved over time. Each gate collects a short look list
(≤ 10 items). One timeboxed P-round runs after E2 and one after E4 (half a session, contact sheet before / after).
Accuracy fixes always come before polish.

## Rules for every session
- Read `STATE.md`, the card, and only the files it lists. Tests for touched code, browser tests for touched JS,
  one contact sheet per gate, one review subagent, card Result ≤ 1 KB, STATE ≤ 3 KB.
- Look changes are timeboxed: two variants → the user picks → move on.
- People, animals, props and backdrops are drawn by the kit in one style. No photos, emoji, generated images or 3D
  on the stage. Every prop has a real size in metres.
- The browser never decides positions or numbers; it plays `stage.patch`.

## Risks and the planned answer
| Risk | Answer |
|---|---|
| A verb has no clip | IK action (reach, hold, point) or the nearest verb; log it; more clips (paid UAL Source tier) later |
| A noun is not in the kit | ladder rungs 2–6; misses logged; the top misses are drawn between sessions |
| SVG too slow with many people | persistent nodes, update only changed attributes, ≤ 12 entities; measure in E1 with Whisper on |
| Overlapping labels / entities | director nudge order + depth rows; tests on bounding boxes |
| Groq 429 / 8k TPM | cached prefix, 1 call per visual sentence, 20b → 120b → fast path only; paid tokens later |
| The user wants more realistic people later | toon3d option in the reference folder (3D body rendered into the 2D stage) |

## After V2
V3 Story (beats, shots, cast registry, personify) reuses the stage; V4 multilingual reuses the graph.
