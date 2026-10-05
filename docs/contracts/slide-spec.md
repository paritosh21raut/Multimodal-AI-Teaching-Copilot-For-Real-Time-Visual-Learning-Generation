# Contract: SlideSpec

Source of truth: `src/copilot/presentation/spec.py` (created in M2). The display renders only this.

```
SlideSpec
  id, version, topic_id, subtopic_id?, facet?        # facet e.g. "Process", "Factors"
  title, subtitle?, continuation_of?                 # continuity link to the previous slide of the same concept
  part?                                              # 1, 2, 3 … when a frame spans slides (badge I / II / III)
  layout: concept | definition | key_points | process_flow | comparison | timeline |
          hierarchy | cause_effect | formula | example | application | narrative | title
  blocks: list[Block]                                # one primary + optional secondary
  language = "en", theme_hint?

Block (discriminated by `type`), each with a stable `id` and items with stable ids:
  definition   { term, definition, notes[] }
  points       { heading?, items[{id, text, emphasis?, provisional?, added?}] }
  facts        { heading?, facts[{id, label, value}] }                # fact tiles ("Smallest planet" / "Mercury")
  groups       { heading?, groups[{id, label, items[Item]}] }        # named groups side by side
  process      { steps[{id, label, detail?}], cyclic: bool }
  comparison   { columns[{id, heading}], rows[{id, aspect, cells[]}] }
  timeline     { events[{id, when, label, detail?}] }
  hierarchy    { root{label, children[...]} }
  cause_effect { links[{id, cause, effect}] }
  formula      { latex, variables[{symbol, meaning, unit?}] }
  example      { title?, text }
  image        { url, alt, credit, licence }
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
- Builder: `presentation.composer` (space-based height model, F-005). Overflow continues on the next part of the
  same frame: same title, `part` badge, never "(cont.)". Two `definition` blocks render side by side.
