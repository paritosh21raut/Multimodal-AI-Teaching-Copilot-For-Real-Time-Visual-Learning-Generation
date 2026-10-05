# F-005: Presentation Engine (M4 → MVP)

Architecture: `docs/architecture/presentation.md`, `display.md`. Contract: `slide-spec.md`.
Goal: turn `InterpretationReady` (+ `ConceptSignal`, teacher commands) into a stable, continuity-aware deck on
the existing `Deck` / `DisplayHub`. Everything here is deterministic code; no LLM calls.

## Components (`src/copilot/presentation/`)
| Module | Role |
|---|---|
| `content.py` | `Interpretation` acts → typed **pieces** (definition, points, steps, comparison, timeline, formula, causes, example), each with its source lines and `added` flag. Pure. |
| `composer.py` | Capacity model per layout; `merge(slide, piece)` → new spec or "does not fit"; `new_slide(frame, piece)`; titles; near-duplicate merge; ≤ 1 `added` item per slide; provisional item set/clear. Pure. |
| `planner.py` | Frame decision per interpretation: `update` / `continue` (new facet or capacity) / `new` (topic) / `noop`; new-topic confirmation. Pure (inputs: frame of the working slide, interpretation, signals). |
| `holds.py` | Concern hold-back: which pieces wait for which open concerns, and what accept / keep / dismiss releases. Pure. |
| `engine.py` | `PresentationEngine`: bus wiring, working slide, dwell queue, held (concern-linked) content, provisional fast path, teacher commands, `SlideContextChanged` for the prompt. Drives `Deck`. |

## Inputs → decisions
- **Frame** of a slide = (topic, facet). Facet = interpretation subtopic (or topic when none). Titles compare with
  `core.memory.titles_match` (case, plural, word overlap).
- **Working slide** = the slide receiving content: the newest planner slide (pending or in the deck). If the
  teacher navigated back to a slide (not following) whose frame matches, that slide is updated in place.

| Interpretation | Op |
|---|---|
| `digression`, or no displayable content | `noop` (provisional item cleared) |
| topic ≠ working topic, **confirmed** | `new`: slide for the new topic's facet |
| topic ≠ working topic, not confirmed | content goes on the working slide; topic remembered as candidate |
| same topic, facet ≠ working facet | `continue`: new slide (`continuation_of` = working); if the working slide has no teacher content yet (only title/provisional) it is **retitled** in place |
| same frame, piece fits | `update` (merge in place, stable ids) |
| same frame, piece needs another layout or capacity is full | `continue`: new slide, same frame |

**New-topic confirmation**: any of (a) a `ConceptSignal.boundary` (strong cue or shift ≥ threshold) or
`shift_score ≥ shift_threshold` on the request's segments, (b) the previous interpretation proposed the same topic
(two consecutive agree), (c) no content slide exists yet (only a title slide or none).

**Min dwell** (`min_dwell_s`, default 15 s, lecture-scaled wall clock): an automatic slide change waits until the
live slide has been up that long. The new slide is built as *pending* (further content merges into it) and is
added to the deck when the dwell ends. Exempt: the first content slide, a title slide, a teacher `force_new_slide`.

**Teacher flags** (enforced by `Deck` + display, respected here): `pinned` → new slides queue behind the pinned one;
`frozen` → the projector holds its render while the deck keeps updating (control preview shows it);
navigation back → in-place updates for a matching frame. `force_new_slide` → an empty slide of the current frame
now; the next content fills it.

## Composer
Capacity (items): definition 1 term + 2 notes + a 3-point supporting list; key_points 6 (two columns when short); process_flow 6 steps; comparison 3 columns × 5 rows;
timeline 6; cause_effect 4; formula 1 + 4 variables; + ≤ 2 secondary blocks (example/callout) per slide.

| Piece | New-slide layout | Merges into |
|---|---|---|
| definition | `definition` | definition slide with the same term (→ notes) or a free note slot ("term: definition") |
| points | `key_points` | the slide's points block (or definition notes) |
| steps | `process_flow` | the process block |
| comparison | `comparison` | a comparison with the same columns (rows appended) |
| timeline / causes | `timeline` / `cause_effect` | the same block |
| formula | `formula` | never (one formula per slide) |
| example | `example` block (secondary) | any slide with a free secondary slot; else points |

- Near-duplicates (normalised text, SequenceMatcher ≥ 0.85 or containment) are skipped.
- `added` pieces: at most one added item per slide, rendered subtly; the rest are dropped (logged).
- Item ids are stable: existing items are never rebuilt; new items get new ids.
- **Provisional fast path**: on a content `ConceptSignal` the live list-like slide gets one `provisional` item
  (≤ 3 short keyphrases, updated in place). The interpretation covering that segment removes it and adds the
  refined items; it expires after 20 s; only one slide carries a teaser at a time; no teaser while a concept
  boundary is not yet interpreted (the slide may be about to change). Duplicates are never checked against teasers.
- Continuations: same kind that did not fit → "(cont.)"; another representation of the frame → a suffix
  ("How photosynthesis works: the equation", "Respiration in Plants: compared").
- Display case: definition terms, comparison headings and row aspects get a capital first letter; term notes read
  naturally ("photo means light", "Chlorophyll: green pigment").

## Concerns (`holds.py`; rules hardened after the independent review)
- A piece whose lines overlap a concern of the same request is **held** (not on the projector) until **every**
  concern linked to it is resolved; each decision transforms it. In a list only the texts matching the claim are
  held, the rest is shown at once; if none matches, the whole piece is held.
- A concern without usable lines holds the best-matching piece, or every piece of that interpretation.
- A factual concern with no extracted content holds the claim itself, so Accept shows the correction.
- Decisions already made when the engine reads the state (backlog) are applied immediately.
- Released content goes back to the slide it belonged to without taking the screen or the working slide.
- Control view lists open concerns: claim, issue, suggested correction, kind, confidence; buttons
  **Accept** (show the corrected form: transcription → spoken token, and its coefficient-free form, replaced;
  factual → the matching text replaced by the correction), **Keep** (show as said), **Dismiss** (drop only the
  disputed text). Buttons send `resolve_concern{id, action}`;
  the store applies it and publishes `ConcernResolved`; the engine then releases the held content to its slide.

## Events added
`SlideContextChanged(text)` engine → store (`LectureState.slide_context`, used in the prompt's CURRENT SLIDE line);
`ConcernResolved(concern_id, status)` store; `SlideOverflow(slide_id)` hub (display auto-fit could not fit) →
engine marks that slide full (next content continues on a new slide).

## Acceptance
- Unit: content mapping; composer capacity/merge/dedupe/added cap/stable ids/provisional; planner table incl.
  confirmation; engine with a fake clock: dwell queue, held content + resolve paths, force_new_slide, pinned.
- Integration: simulator → understanding (mock LLM) → engine → deck: slides in order, no slide for meta lines,
  concern-linked content absent until resolved.
- Runtime: `python -m copilot --simulate tests/fixtures/lectures/photosynthesis.txt --no-wait --speed 1` with real
  Groq; `tools/screenshot_app.py` screenshots inspected: Definition → Requirements → Process (steps) → formula →
  Importance → Respiration (new topic, comparison); oxygen claim shown only in the control view.
