# ADR-0011 — V2 visuals: 2D Explainer Stage (explainer_flat look, chibi people from CC0 motion capture)

Date 2026-10-26 · Status: **accepted** (user confirmed after three sample rounds) · Supersedes the visual layer of
F-016, the D1 / D1b / D1c / D1d style work, and this ADR's own first version (CC0 rigged 3D, toon-rendered).

## Context
Seven earlier attempts (templates only, topic worlds, emoji + photo canvas, SD-Turbo, code-drawn styles, code-built
3D man, 2D puppets cut from AI sheets) failed the user's eye or could not scale. A 3D plan (Quaternius rigged
bodies, toon shading) was sampled next: people moved well, but clothes showed the muscular body, every prop kit
needed palette and scale fixes, glass / liquids looked weak, and depth overlaps went wrong — slow to make accurate.
The 2D samples (`docs/v2/V2-LOOK-SAMPLES.md`, rounds 1–3, `tools/stage/reference/`) were exact by construction and
matched the incline templates the user rated "excellent". The user said 2D is enough if it is accurate, shows the
whole scene, and looks very good; then picked **explainer_flat** and **chibi** people, and asked for accuracy
first with the look improved in later rounds.

## Decision
- The stage is **2D SVG** in the browser, side view by default, plus top view, cutaway, split panes and "seen
  from" insets (no 3D camera).
- One look: **explainer_flat** — sky gradient, soft hills, ground band, soft contact shadows, no outlines, fixed
  colour roles for quantities (applied force orange, friction red, weight blue, normal green, velocity purple).
- **People = chibi** figures drawn from joints. Their motion is real motion capture: the CC0 Quaternius Universal
  Animation Library 1+2 (87 clips, one skeleton) baked once into 2D joint tracks (`motion.json`). Hands use
  two-bone IK to sit on objects; walking speed comes from each clip's stride, so feet don't slide.
- **Animals**, **props** and **backdrops** are a vector kit drawn in code in the same style, each with a real size in
  metres. Unknown nouns go down a ladder (near kit item → generic shape → recoloured flat icon → labelled box).
  Never a wrong picture.
- Python owns state, solvers, numbers (with provenance), director and acting. The LLM only emits semantic op
  deltas (`docs/contracts/stage-spec.md`).
- Not chosen: toon3d (the 3D body rendered into the 2D scene, kept in the reference folder as a possible later
  "detailed people" option); the flat capsule, shaped and stick figure styles; the textbook theme as default.

## Consequences
+ Every element sits exactly where the solver says. Glass, liquids, rays, fields, particles, strobe images,
  cutaways and split views are easy and clear. Light on the laptop next to Whisper; no asset downloads at run time.
+ Real human motion (push, throw, walk, carry, sit, jump, swim, water a plant…) without an animator.
+ Effort goes to what is ours (director, acting sync, provenance, continuity) = paper 2.
− One main viewpoint; no "walk around the object" camera.
− People are only as varied as the cast and clip list. A verb with no clip uses IK or the nearest verb.
− Props are drawn by us, so the kit has to grow; misses are logged and added between sessions.
− The look will need periodic polish rounds (user: "there's still scope of improvement … we'll improve them").
