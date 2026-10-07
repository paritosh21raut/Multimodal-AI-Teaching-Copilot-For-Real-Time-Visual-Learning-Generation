# F-009: Slide themes, teacher notes, labelled images (V2 group A)

0 LLM tokens. User answers 2026-10-07 (V2 planning).

## 1. Slide themes (light / premium dark), switchable mid-lecture
- Dock button (sun / moon) → command `set_theme {theme}` → `LectureStateStore` sets `setup.theme` and emits
  `ThemeChanged` → hub → `/display`, `/view` (students follow the teacher's theme) and the `/control` preview.
- Light: unchanged. Dark (redesigned): true near-black stage (#07080a) with a faint teal/indigo light from the
  corners, cards as raised graphite panels with a hairline edge (inset box-shadow ring — no layout change, the
  composer height model stays exact), luminous teal / amber accents, high-contrast ink.
- Images in dark: shown on a soft light mat (labelled diagrams are drawn on white), rounded like the cards.
- Tokens apply on any element with `data-theme` (not only `:root`): the `/control` preview carries the slide theme,
  the control page its own.
- `/control` page dark mode: header toggle, per-browser (localStorage), default light. Screenshots → the user
  decides whether to keep it.

## 2. Teacher notes (PDF), never on the projector
- `/control` right column becomes tabs: **Structure · Notes** (later groups add tabs, so the page stays calm).
- Notes tab: Add PDF (file picker / drop) → `POST /api/notes` (teacher only, ≤ 50 MB, `%PDF` header checked) →
  stored in `data/notes/<sha16>.pdf` (local laptop; the same file again is not duplicated); a list of the notes
  (choose one), the page rendered as an image (`GET /api/notes/<id>/page/<n>?w=`, pypdfium2, cached), ‹ page n / m ›,
  expand (wider column), remove from the list.
- **Follow the lecture** (on by default, the teacher can turn it off; turning a page by hand pauses it until the
  next slide): when the live slide changes, MiniLM cosine between the slide text (title, topic, items) and each
  page's text → the best page when ≥ `NOTES_FOLLOW_MIN` and clearly better than the current one. A PDF without text
  (scans) → "No text in this PDF: follow is off".
- `NotesService` on the bus (like ShareService): commands `notes_open {id}`, `notes_page {page}`, `notes_follow
  {on}`, `notes_remove {id}` → `NotesState` event → hub → control only. Nothing goes to `/display` or `/view`.

## 3. Labelled images preferred (Wikipedia / Commons)
- Only for diagram-like subjects (kind `diagram`, or the query names a structure: system, organ, cell, structure,
  parts, anatomy, cycle, apparatus, layers, …); photos of planets / animals unchanged.
- Labelled = "labelled / labeled / labels / annotated / with labels" in the file name, description or categories.
- Search: an extra Commons search "<core> labelled diagram" runs with the others; among the candidates the labelled
  ones go first (they get the 8 preview slots). Ranking: an accepted labelled image always comes before an accepted
  unlabelled one; none labelled accepted → the best unlabelled as before. Every image still passes the same
  filters + CLIP relevance gate.
- Query cache: results of diagram-like queries are cached under a new key (old answers would skip the preference).

## Tests
- Unit: set_theme → state + ThemeChanged; hub broadcasts theme to display/viewer/control; labelled detection,
  ordering, extra search; notes: upload validation, page text extraction, follow matching, commands → NotesState.
- Edge: theme switch repaints /display without reload; dark tokens on the stage; notes tab renders a page.
- Runtime: real app, switch theme mid-lecture (screenshots light/dark, /control dark); real PDF follow on a
  scripted lecture; real image searches for diagram queries (old vs new choice).
