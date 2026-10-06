# Contract: SlideSpec

Source of truth: `src/copilot/presentation/spec.py` (created in M2). The display renders only this.

```
SlideSpec
  id, version, topic_id, subtopic_id?, facet?        # facet e.g. "Process", "Factors"
  title, subtitle?, continuation_of?                 # continuity link to the previous slide of the same concept
  part?                                              # 1, 2, 3 … when a frame spans slides (badge I / II / III)
  layout: concept | definition | key_points | process_flow | comparison | timeline |
          hierarchy | cause_effect | formula | example | application | narrative | facts | groups | members | title
  blocks: list[Block]                                # one primary + optional secondary
  language = "en", theme_hint?

Block (discriminated by `type`), each with a stable `id` and items with stable ids:
  definition   { term, definition, notes[] }
  points       { heading?, items[{id, text, emphasis?, provisional?, added?}] }
  facts        { heading?, facts[{id, label, value}] }                # fact tiles ("Smallest planet" / "Mercury")
  groups       { heading?, groups[{id, label, items[Item]}] }        # named groups side by side
  process      { steps[{id, label, detail?}], cyclic: bool, start = 1 }   # ≤ 10 steps: one row ≤ 6, else two rows;
                                                                         # start: first step number on a next part
  comparison   { columns[{id, heading}], rows[{id, aspect, cells[]}] }
  timeline     { events[{id, when, label, detail?}] }
  hierarchy    { root{label, children[...]} }
  cause_effect { links[{id, cause, effect}] }
  formula      { latex, spoken, variables[{symbol, meaning, unit?, latex?}] }   # latex from mathtext (F-007a);
               # consecutive slide-wide formulas (≤ 4, said together) render as ONE set: stacked cards, one legend
  example      { title?, text }
  image        { url, alt, credit, licence, aspect, origin: auto|teacher, image_id }   # F-007b
  callout      { kind: note|tip|key, text }
  simulation   { template, params }          # V3
  storyboard   { scenes[] }                  # V4
```

## Rules
- Item ids are stable across versions → the client animates only diffs.
- `provisional` items are replaced in place by refined items.
- `added=true` marks non-teacher supporting content (≤ 1 per slide, styled subtly).
- Truthful slides: items show the corrected words when the concern is applied, else what the teacher said; the
  concern itself is only in the Control View (F-005).
- Formulas (F-007a): `spoken` = the formula as the model wrote it; `latex` = KaTeX source built from it by
  `presentation.mathtext` ("" = not renderable → the display shows `spoken`). Edits (truthful substitution) change
  `spoken` and rebuild `latex`. Chemical formulas in any text (`CO2`) are subscripted by the display (`rich.js`).
- `math` (items, steps, definitions, examples, callouts): the text with `\(latex\)` around its equations, filled by
  `presentation.annotate` in the Deck for every published spec ("" = none); the display renders prose as text and
  each span with KaTeX. `PointsBlock.style`: `bullets` (default) | `numbers` (counted / ordered lists, labelled
  kinds) | `letters` (a) b) options), also set by `annotate`.
- `about` (formula, points, example, facts): id of a definition block when concepts are defined side by side;
  the display draws one column / card per concept (definition + its blocks), the rest full width below (F-007a,
  issue 6).
- Members of a set (verify round 4 step B): several `definition` blocks are cards side by side — 2 | 3 | 2×2 | 3+2
  | 3×2 (≤ 6; `composer.grid_columns` = slide.js). Layout `members`: ONE definition that is a member of the slide's
  facet (facet "Types", term "PAN"; not a definition / introduction facet, not the facet or topic itself) — a card
  under the facet's title instead of the term as title; its details (`about`) stay in the card.
- Definitions after other content (long test 2026-10-06; at most one definition before that content): one row of
  cards where the first of them stands, each with its `about` blocks (`composer.trailing_definitions` = slide.js
  `trailingDefs`); the other blocks keep their order around the row. The display always shows `title` (all parts
  read the same); a lone leading definition hides its term when the title names it, else it is a card.
- A `hierarchy` may have up to 3 levels (a kind divided further, `composer.subdivide`). Beside an image it renders as
  one card (label + kinds as chips); with several levels, a chip card per divided kind. A `formula` after other content beside
  an image: that content and the image share the top row (image ≤ 380 px tall), the formula and what follows go
  full width below (`composer.image_top` = slide.js `splitBlocks`).
- `image` (F-007b): at most one, always the last block; `url` = `/media/<image_id>.jpg` (our server). A slide with
  an image uses the image layout (content | image column); without one, today's layouts. Not content: it never
  counts as a teacher item, never enters the prompt or correction targets, and does not stay on a slide whose content
  was removed. Beside an image the type may shrink to 0.8 before content opens the next part.
- Builder: `presentation.composer` (space-based height model, F-005). Overflow continues on the next part of the
  same frame: same title, `part` badge, never "(cont.)". Several `definition` blocks render side by side. A member
  explained in depth continues on a slide titled by the member (no `part`, same crumb); the set's next part follows.
