# F-005: Presentation Engine (M4 → MVP)

Architecture: `docs/architecture/presentation.md`, `display.md`. Contract: `slide-spec.md`.
Goal: turn `InterpretationReady` (+ `ConceptSignal`, teacher commands) into a stable, continuity-aware, **truthful**
deck of clear slides on the existing `Deck` / `DisplayHub`. Everything here is deterministic code; no LLM calls.

Revised 2026-10-05 after the real-mic verify lectures (solar system, basics of chemistry): display-quality text,
fact tiles / groups / trees, space-based composition, part badges instead of "(cont.)", revisions, truthful slides.

## Components (`src/copilot/presentation/`)
| Module | Role |
|---|---|
| `content.py` | `Interpretation` acts → typed **pieces**: definition, points, steps, comparison, timeline, formula, causes, example, **facts**, **tree**, **groups**. Transitions/questions and announcement text ("let's learn about X") never become pieces; yes/no "facts" become points; two+ labelled classifications in one unit become one groups piece. Pure. |
| `composer.py` | Height model (design px, mirrors `slide.css`); `merge(slide, piece)` → new spec or leftover; titles; word-aware near-duplicate check; ≤ 1 `added` item; provisional teaser; `describe()` (CURRENT SLIDE text + `S1..` refs); in-place edits: `revise_item`, `substitute`, `remove_elements`. Pure. |
| `planner.py` | Frame decision per interpretation: `update` / `continue` (new facet) / `new` (topic) / `retitle` / `noop`; new-topic confirmation; announced-topic candidate. Pure. |
| `engine.py` | `PresentationEngine`: bus wiring, working slide, dwell queue, parts, revisions, corrections (truthful slides), tentative-topic move, provisional fast path, teacher commands, `SlideContextChanged`. Drives `Deck`. |

## Frame decisions
Frame of a slide = (topic, facet). Facet = subtopic (or the topic). Titles compare with `core.memory.titles_match`.

| Interpretation | Op |
|---|---|
| `digression`, or nothing displayable | `noop` (an announced new topic is remembered as the candidate) |
| topic ≠ working topic, **confirmed** | `new` slide for the topic (tentative items move there, see below) |
| topic ≠ working topic, not confirmed | shown on the working slide meanwhile (*tentative*), topic kept as candidate |
| same topic, facet ≠ working facet | `continue`: new slide; `retitle` if the working slide has no teacher content |
| same frame | `update` in place; what does not fit continues on the **next part** of the frame |

- **Confirmation**: a `ConceptSignal.boundary` / shift ≥ threshold on the unit, two interpretations agreeing, or an
  earlier no-op that announced this topic. **Tentative move**: items shown under an unconfirmed topic are removed
  from the old slide and placed first on the new topic's slide when it is confirmed.
- **Min dwell** 15 s (lecture-scaled) before an automatic slide change; new slides wait as *pending* (content keeps
  merging). The next part of the same (full) frame waits only `part_dwell_s` = 6 s. Exempt: first content slide,
  title slide, teacher `force_new_slide`.
- **Sparse definition slide absorbs supporting content**: a `continue` whose pieces are only tree / groups / facts /
  points / example stays on the working slide when that slide is just a definition filling ≤ 45 % of the space and
  everything fits (e.g. "Chemistry" definition + "Branches of chemistry" tree). A new definition never is absorbed,
  nor a `sub_concept` whose facet names a thing ("Female Reproductive System": its own slide like its sibling;
  round 4, issue 8 — in every recorded session the branches came as `sibling_concept`).
- **Teacher flags**: pinned → new slides queue; frozen → the display holds its render; navigated back to a slide of
  the same frame → updated in place (never adopted as working slide); `force_new_slide` → next part now.

## Composition (space, not slot counts)
- Each block has an estimated height (definition by lines at 42 px, points one or two columns, fact tiles 4 per
  row, groups, tree, process, comparison rows, …). A piece goes on the slide while the body stays within
  `BODY_BUDGET_PX` = 740 (display auto-fit can still shrink type to 0.8; measured body 754–763 px in Edge on 29
  slides of the live test 2026-10-06 — 700 left lonely last parts). One small leftover (one short point,
  example or fact) is squeezed in at 1.25 × budget instead of opening a lonely next part.
- A heading belongs to its own items: unlabelled points never join a labelled list and a labelled list never takes
  over earlier points (live test 2026-10-06). "C++"/"C#" are not duplicates of "C". A classification whose named
  groups have no members shows the group names as its kinds.
- The display's overflow report holds while the slide has at least as many items as when it was reported.
- At most one large diagram (process, comparison, timeline, cause-effect, formula, tree) per slide; facts, points,
  groups and definitions may sit next to it when space allows. Several classifications of one thing (by bits, by
  memory type, by architecture) are ONE groups block: the first one's tree becomes its first card (same ids) and the
  labels lose the repeated subject ("Microcontroller types by bit width" → "By bit width"; round 4, issue 4). A tree
  that does not fit moves whole to the next part (its kinds as a list only when all of them fit; "Ovaries" alone).
- Definitions: same term → extra text as a point; a word part ("photo" of "photosynthesis", "X means …") → note chip;
  a peer concept defined alongside (element + compound, atom + molecule) → two definition cards side by side;
  a new term on a slide with other content → a definition card below it if room, else the next part.
- **Members of a set** (round 4, issues 1–2): on a slide whose facet lists a set ("Types", "Components"), a defined
  member is a card under the facet's title (layout `members`), not the slide's title; the next members join as cards
  (2 | 3 | 2×2 | 3+2 | 3×2, ≤ 6) while they fit and the slide holds only definitions, their details and examples (no
  formula once there are 3). An automatic image yields to them. A member's details (`about`) stay in its card: ≤ 3
  points once there are 3+ cards. **Depth**: details that no longer fit their card → the member's own slide, titled
  by it, same crumb (Topic — Types), no part badge; content that is not about that member → the set's next part
  (set title, part 2; part 1 numbered then). The topic's own definition is never a member.
- **Parts**: overflow of a frame continues on a slide with the same title and `part` = 2, 3, … (part 1 is numbered
  then); the display shows a small roman-numeral badge (I, II, III), never "(cont.)".
- Near-duplicates: same content words (plural-folded) and ≥ 0.85 similarity, or whole-word containment
  ("organic chemistry" is not a duplicate of "inorganic chemistry").
- Titles: templates for Definition ("What is <term>?"), Process, Importance, Requirements; otherwise the facet name
  (the crumb already shows the topic: "CHEMISTRY — MATTER").
- **Provisional fast path**: one keyword teaser on the live list slide, replaced by the refined items; one slide at a
  time; none while a concept boundary is uninterpreted; expires after 20 s; ignored by dedupe and definition pairing.

## Revisions (fragments become complete items)
`describe()` lists revisable items of the working slide as `[S1] …` (points, notes, steps, facts) and publishes the
ref map with `SlideContextChanged`; the store keeps it in `slide_refs`; the prompt shows the CURRENT SLIDE; the
interpreter keeps only revisions with known refs; `InterpretationReady.slide_refs` carries the map the prompt used;
the engine rewrites the item in place (same id → the display updates only that text).

## Truthful slides (concerns)
- Interpretations carry the **corrected** content; a concern says `claim` (what was said), `suggested_correction`,
  `wrong` / `right` (the minimal differing words; derived deterministically when missing).
- The store sets `applied` = confidence ≥ 0.75 (factual) or ≥ 0.4 (transcription). Not applied → the engine
  substitutes `right` → `wrong` in that unit's new elements, so the projector shows what the teacher said.
- If the model raised a correction but left the wrong words in its items, the engine applies it.
- Control view card: "You said / Heard", "Correct", and what the slide shows; buttons **OK** / **Show as I said**
  (applied) or **Show correction** / **OK** (not applied) → `resolve_concern{id, action: dismiss|keep|accept}` →
  store → `ConcernResolved` → engine toggles the words in the tracked elements.
- Self-corrections by the teacher ("Uranus, sorry, Neptune") are used as corrected, not raised.

## Events added
`SlideContextChanged(text, refs)` engine → store; `ConcernResolved(concern_id, status)` store;
`SlideOverflow(slide_id, version)` hub (display auto-fit failed) → engine marks the slide full.

## Acceptance
- Unit: content mapping (facts, groups, trees, announcements, yes/no facts); composer (space budget, parts,
  definitions, dedupe, squeeze, revise/substitute/remove); planner incl. confirmation and announced topics; engine:
  dwell, parts, revisions, corrections (applied / not applied / enforced / toggled), tentative move, force-new,
  pinned, navigated back, provisional.
- Integration: simulator → understanding (mock HTTP) → engine → deck on photosynthesis.txt.
- Layout render check: `tools/screenshot_lessons.py` (real engine, scripted interpretations) → `artifacts/lessons/`.
- Runtime: `tools/screenshot_app.py --lecture --simulate tests/fixtures/lectures/{solar_system,chemistry_basics}.txt`
  (the verify lectures' exact STT lines) with real LLM calls; screenshots inspected.
