# Presentation Engine (Live Slides mode)

Implementation and exact rules: `docs/specs/F-005-presentation.md` (`presentation.content` / `composer` /
`planner` / `engine`). Defaults: min dwell 10 s (config `[presentation]`; 15 s before F-013); near-duplicates by text similarity ≥ 0.85.

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

## Spoken cues (F-013 S1)
`understanding.cues.detect` reads each transcript line (no LLM) and `ConceptSignal` carries what it found.
- **Announced topic** ("Now let's study mixtures", "The third topic is Mercury", "What is economics?", "Difference
  between A and B"): a slide titled by it opens at once (`pending`, no dwell; waiting dwell slides go into the deck
  behind it). The unit holding the announcement or later lines is placed on it; an earlier unit goes to the previous
  slide without taking the screen. A "new" decision on the still-empty announced slide retitles it instead of opening
  another. The announced name stays the title when the interpretation's content talks about it (the model's broader
  label becomes the frame); otherwise (misheard) the model's title wins. Nothing confirmed in `cue_ttl_s` (30 s) and
  still empty → removed. The same subject as the slide on screen opens nothing.
- **Named list** ("X is classified into A, B and C", "There are two types of X" + "The first type is A"): a
  provisional tree on the slide on screen, members added as they are said, removed when the interpretation of those
  lines arrives (its own content replaces it) or after `cue_list_ttl_s`.
- Replay of tests 1–30 (recorded answers, `tools/v1_eval.py --replay`): announcement → titled slide 15.0 s → 0.64 s
  median (p90 29.3 → 1.9 s); never titled 38 → 4 of 95.

## Structure (F-013 S2)
Slides form a tree of at most three levels: topic → subtopic → child (`Frame.parent`, `SlideSpec.parent`). The crumb
shows "Topic — Parent" and the Lecture Structure in /control nests a child under its parent, in deck order. The tree
is built by code. The model's `parent` field was A/B-tested and rejected (see understanding.md).
- **Numbered sections** (`cues.section`, rule `section`): "1. Social. The social conditions …" (the name taken up by
  the next sentence, or the whole line), "Stage 2 …" (≥ 3 words after). A section announced after a non-series
  announcement makes the old title the parent ("Causes" → Social, Economic). A numbered step said as a sentence
  ("1. The user enters a domain name.") is no section. "The 7th topic is Jupiter" has the rule `ordinal`. A series
  member is a subtopic of its own, never a "part N".
- **Announced member of a set**: when the model still labels the unit with a set ("Planets") while the announced
  name is a member ("Mercury"), the member is the facet and the set is the parent. This does not apply when the
  announced name is the new topic, also when misheard ("Statics" for Statistics), in which case the model's spelling
  becomes the title.
- **Registry of expected children** (`_children`, ≤ 60): members of a named list or of a classification, under the
  subtopic that held it. When one of them starts later, its parent is already known.
- **Qualifier child** (`memory.is_child_facet`): "Intellectual Causes" under "Causes", "Political Causes" under
  "Causes of French Revolution" (the parent's head before "of"), "Inner Planets" under "Planets". Not "Respiration in
  Plants" or "Types of Bonds". `same_title` is `titles_match` without the one-extra-word leniency (a child is not its
  parent).
- **Member stays on its slide**: content the model files under the set stays on the member's slide only when it
  names the member, in its items or in the one-sentence summary (`planner.names`). Without that rule test20 put
  "Economic strain from wars" on the Social slide. A new definition after a member's slide is the next member
  ("Earth").
- **Lines before an announcement** stay on the previous slide (`_place_early`).
- **Confirmed new topic on the slide titled by it**: when the slide on screen already carries the confirmed topic's
  name (filed under the old topic until two interpretations agreed), it becomes that topic's slide. Before this,
  test23 showed two "Integral Calculus" slides in a row.
- Tried and dropped: a newly defined term opening a new subtopic. The replay showed that most such terms are
  supporting terms ("Bolus", "SSID", "Downlink"), and precision fell.
- Replay of the 18 annotated lectures (`tools/v1_eval.py --structure`, recorded answers, 0 tokens): boundary P 0.80 →
  0.78, R 0.44 → 0.51, F1 0.51 → 0.56, part rate 0.73 → 0.62, 34 child slides.

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
