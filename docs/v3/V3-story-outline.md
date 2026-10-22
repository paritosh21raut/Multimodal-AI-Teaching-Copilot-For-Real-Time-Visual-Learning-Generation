# V3 — Story Scenes (outline, 2026-10-22; detailed after F-015)

**Idea:** when the teacher narrates ("in 1905 a young clerk in Bern…", "a drop of water starts in the ocean…",
"imagine you are a red blood cell…"), the projector shows a storyboard that moves with the narration.

**Reuse from F-015 (why V2 Next comes first):**
- The same `SceneSpec` / SceneOps, entities with `look` (icon / glyph / image), layout, renderer, clock and validator.
- V3 adds a `timeline`: scenes[] with {caption (said words), duration from the narration, camera (pan / zoom / Ken
  Burns), transitions}, plus characters and settings as entities that carry across scenes (continuity between scenes).
- A narrative detector (0 tokens) → `RepresentationIntent(visual_kind="story")`, already in `VisualKind`.
- Images: the teacher's own, then Wikimedia / Openverse (V1), then icons / glyphs. No generative video (ADR-0006).

**Paper 3 claim (draft):** turning live narration into a time-aligned storyboard, with entities kept consistent
across scenes and captions only from what was said.

**Not decided yet:** how scenes are timed (a pause or a sentence boundary), and whether the story owns its own slide or
shares simulation mode. Decide when V3 starts.
