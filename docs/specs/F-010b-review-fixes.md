# F-010b — Group B review fixes (V2)

Status: done (2026-10-07), verified — see STATE.md. User review of group B + answers to the doubts (2026-10-07).
0 LLM tokens: nothing here calls the LLM.

## 1. Start + chapter in /control (review #4, user answer 1)
- Before the lecture (lifecycle `ready`) the preview shows a **start card**: a chapter picker (the chapters, newest
  used first selected; "+ New chapter" with a name field) and **Start lecture**. Start sends `lecture_move
  {id: <this session>, chapter}` then the existing `start` command (Enter in the terminal still works).
- During the lecture the chapter of this lecture can be changed in the Lectures tab (drag, or the row menu).
- Test runs (`--simulate`): the chapter chosen at start is not stored; they stay in **Unsorted** (user answer 5).

## 2. Chapters (review #4, user answers 2-4)
- `data/chapters.json`: `{chapters: [{id, name}], lectures: {session_id: chapter_id}, last: chapter_id}`.
  The order of `chapters` is the chapter number: shown "Chapter 3 · Cell biology"; only the name is edited, the
  number follows the position. Drag a chapter up / down to reorder (numbers change).
- Commands (MaterialsService, every change → `MaterialsState.chapters`): `chapter_create {name, assign?}`,
  `chapter_rename {id, name}`, `chapter_move {id, index}`, `chapter_delete {id}` (confirm with a warning in
  /control; its lectures go to Unsorted, nothing is deleted), `lecture_move {id, chapter}` ("" = Unsorted).
- Lectures tab: search bar, sort (Name / Date, ascending / descending; applies to chapters and to the lectures
  inside them), collapsible chapter groups, **Unsorted** last; lecture rows drag onto a chapter; "+ New chapter".
  The running lecture is listed in its chapter with a "now" tag.

## 3. Search (review #3, user answer #3)
`GET /api/lectures/search?q=` (teacher only): words matched in lecture titles, slide titles and slide content (no
transcript). Results: the lectures that match + up to 3 matching slides each; a slide hit opens the viewer at it.

## 4. Materials card (review #5, #7)
- Tiles: no tick boxes; the tile itself toggles (accent border + a small check in its corner).
- **From**: *This lecture* · *Pick lectures* (checklist incl. this lecture) · *Pick chapters* (checklist; the current
  chapter marked, several allowed). The service resolves chapters → lecture ids (this lecture included when it is in
  a picked chapter). File title of a chapter pick: the chapter names.

## 5. My notes: any file, links, projector (review #14, user answers 1-4)
- Files: PDF; Word (`.docx .doc .rtf .odt .txt .md`) via Microsoft Word, PowerPoint (`.pptx .ppt .odp`) via
  PowerPoint (both installed; COM through PowerShell, hidden, read-only, timeout) → PDF; images (`.png .jpg .jpeg
  .webp .gif`) → a one-page PDF (Pillow). Everything is then the existing PDF pipeline (pages, follow). Office
  missing → the teacher is told that this type needs Word / PowerPoint (no fake conversion).
- Links: drop a link (or "Add link" + paste) → the page is opened in headless Edge and saved as a PDF snapshot
  (layout, images and text kept; Follow lecture works; offline afterwards) + "Open original" button. Pages that
  refuse (login, error) → the reason.
- `NoteDoc.kind` (pdf | word | slides | image | text | web) and `source` (the link) for the icons.
- **Show on projector** (user answer 4): a toggle in the notes footer. `notes_project {on}` → `NotesProjected
  {on, doc_id, page, aspect}` → hub → display + viewers: the page fills the screen over the slide (like a zoomed
  image), follows page turns, off with the toggle / Esc in /control; blank still wins. Only the projected page is
  served to non-teachers (`GET /api/notes/shown/{doc}/{page}`, 403 for any other page). Never to the LLM.

## 6. Small fixes
| # | Fix |
|---|---|
| 1 | Materials + Lectures list items: regular weight (title rows 550, meta 400) |
| 2 | Tab "Structure" → "Lecture structure" |
| 6 | The notes panel goes back to its default width when the open note is removed (user: "it gets back to its original default width"; before, the panel stayed wide with no widen button) |
| 8 | Assignment PDF: no Name / Roll no. / Date lines |
| 9 | No token counts in /control (terminal + log keep them) |
| 10 | "or drop one" removed beside Add image / Change in the preview; kept in the notes card; drop still works everywhere |
| 11 | Styled tooltip (one component for /control, both themes) instead of native `title`: every `title` becomes the element's `aria-label` + `data-tip` as soon as it is rendered (a MutationObserver), so the browser box never shows; tests select by `aria-label` |
| 12 | Notes pages change without a fade; the next / previous pages are preloaded |
| 13 | Thin styled scroll bars in /control, the viewer and the student page, both themes |
| 15 | Lectures tab icon: a stack of books (line style like the other tabs) |

## Tests
unit: chapter book (create / rename / move / delete → unsorted / lecture_move / test run not stored), service
commands, chapter → lectures resolution, search (titles + content, no transcript), notes conversion per type (image →
PDF real; Office via a fake converter + one slow test with real Word / PowerPoint), link snapshot (fake), projected
page route (403 for other pages), assignment HTML without the lines, MaterialsState without tokens.
browser (Edge): start card + chapter, Lectures tab (search, groups, drag), tile toggle, notes image + projector,
tooltip, no fade. Runtime: the real app `--no-understanding` (0 tokens), screenshots looked at.
