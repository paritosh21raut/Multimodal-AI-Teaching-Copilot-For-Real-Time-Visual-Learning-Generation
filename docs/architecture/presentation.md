# Presentation Engine (Live Slides mode)

Implementation and exact rules: `docs/specs/F-005-presentation.md` (`presentation.content` / `composer` /
`planner` / `engine`). Defaults: min dwell 15 s (config `[presentation]`); near-duplicates by text similarity ≥ 0.85.

## Concepts
- **Deck**: an ordered list of `SlideSpec`s for the session; one is `live`. The teacher can navigate (Pin removed, round 5).
- **Slide**: one *concept frame* (topic + subtopic + facet), a representation layout, and blocks.
- **Capacity model**: each layout declares limits (e.g. definition: 1 term + ≤ 2 supporting points + 1 visual;
  process: ≤ 10 steps — one row up to 6, else two rows; a longer process continues on the next part and keeps
  counting (`ProcessBlock.start`); formulas said together: ≤ 4 on one slide as a set with one legend; comparison: ≤ 2–3 columns × ≤ 5 rows; key points: ≤ 5). Composer measures fill (0–1).

## Planner decision (deterministic)
Input: the `Interpretation` + current slide + `ConceptSignal` + teacher commands.

| Situation | Op |
|---|---|
| relation same_concept / elaboration, same representation, capacity left | `update` (add/merge items) |
| same concept, different representation needed (e.g. a process starts) | `continue` → new slide, same topic, new facet ("Photosynthesis — Process") |
| same concept, capacity exceeded | `continue` → new slide, same facet, "(cont.)" grouping |
| sub_concept / sibling_concept | `continue` (new facet), unless the current slide is nearly empty → `retitle/update` |
| new_topic, confirmed | `new` slide (title-level change) |
| digression / meta only | `noop` |
| teacher navigated back | new slides queue behind the slide shown (not following); `next` to the last slide follows again |
| lecture paused | nothing new arrives (the understanding service drops what is said during the pause) |

**Hysteresis / stability rules**
- Minimum dwell time per slide (default 20 s) before a non-teacher-forced slide change.
- A `new_topic` needs confirmation: either the LLM relation plus `shift_score` > threshold, or two consecutive
  interpretations agreeing. Otherwise the slide is updated provisionally.
- Updates are **additive and in place** (stable item ids); text edits animate only the changed item.
- Merge near-duplicate items (embedding similarity > 0.85) instead of adding them.

## Progressive update
1. **Fast path (≤ 3–5 s):** after the gate's fast trigger, the Composer may place a deterministic provisional item
   (key term or short sentence) marked `provisional`.
2. **Refined path (≈ 10–15 s):** the Interpretation replaces provisional items with structured content.
3. **Enrichment:** images and diagrams patch in asynchronously when ready (layout reserves space only after a visual is accepted).

## Representation selection
`DiscourseAct → layout`: definition → `definition`, process → `process_flow`, comparison → `comparison`,
timeline → `timeline`, hierarchy → `hierarchy`, cause_effect → `cause_effect`, formula → `formula`,
example/application → `example`/`application`, explanation → `concept` (callouts + points), story → `narrative`.
A slide can hold one primary block plus small secondary blocks (example callout, image).

## Output
The Planner emits `SlideOp`s; the Deck applies them and emits a `SlidePatch` (slide id, version, full spec
or block-level diff) to the DisplayHub. Every spec version is archived (post-lecture PPTX/notes).
