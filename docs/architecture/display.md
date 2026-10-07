# Live Display + Control View

## Technology (ADR-0003, ADR-0005)
- Server: FastAPI + uvicorn in the same process/loop; the WebSocket hub broadcasts `SlidePatch` and status.
- Client: static ES modules served from `web/`, **no build step**: Preact + htm (vendored in `web/vendor/`),
  KaTeX 0.16.22 for formulas (vendored in `web/vendor/katex/`, woff2 only; `web/shared/rich.js`: KaTeX + chemical
  subscripts in any slide text; words inside formulas use the slide font), custom SVG components for flows/timelines/trees/causal graphs.
- Display opened full screen on the projector (Chrome/Edge `--app=<url> --start-fullscreen`, or the teacher presses F11).

## Opening the pages
`python -m copilot` opens `/control` and `/display` in the default browser ~3 s after READY, only for a role with no
page connected since the server started: tabs left open from an earlier run reconnect on their own (client reconnect
backoff capped at 2 s), so no duplicate tabs. `--no-open` disables it. Test: `tests/e2e/test_auto_open.py`.

## Pages
| URL | Who | Shows |
|---|---|---|
| `/display` | projector | the live slide only; nothing else |
| `/control` | teacher laptop | status, mic level, live preview (editable), dock, mistake cards, lecture structure, transcript strip, Share |
| `/view` | students (shared link, F-008) | the projector page as a viewer: live slide only, sends nothing, no transcript |

Access (F-008, ADR-0009): only a direct localhost request (loopback, localhost Host, no proxy headers) is the
teacher's; from the tunnel or the LAN, `/control`, `/display` (→ `/view`), `/api/upload` and the control/display
WebSocket roles need the per-run teacher key (`/control?key=…` from the terminal → HttpOnly cookie). `/` goes to
`/control` locally, `/view` otherwise.

## Rendering rules (visual quality)
- 16:9 stage scaled to the viewport; a design-token system (type scale, spacing, color roles) per theme (light/dark).
- One layout component per representation; layouts are designed, not generic bullets.
- Definition: a card with a small "Definition" tab on its top edge and a soft accent tint from the corner (no side bar,
  user 2026-10-06); concepts side by side / member cards: each one card, the term as its heading. Note / key idea:
  a plain labelled card like the example (no colour fill). A tree of several levels: the divided kinds tinted, their
  kinds below them; beside an image it becomes one chip card per divided kind.
- Auto-fit: measure overflow → step down the type scale within limits → otherwise ask the server to split (`overflow` event).
- Transitions: new slide = cross-fade/slide; in-slide update = FLIP animation + fade-in of new items only;
  no full re-render, so there is no flicker. Images fade in only after they are loaded. The new slide fades in by a
  CSS animation, never by a script step waiting on animation frames: Edge pauses those for a window it does not
  paint (/display popped out behind /control, a background tab), and the new slide stayed invisible until a reload
  (live test 2026-10-06; browser test simulates a window without frames).
- Provisional items render subtly (lighter weight); refined content replaces them in place.
- The display reconnects automatically and requests the full current spec on reconnect (state is server-authoritative).
- Client files under `/web` are served with `Cache-Control: no-cache`, and `/display` + `/control` are served with
  every client URL stamped `?v=<hash of client files>` — modules imported by other modules too, via an import map —
  so a browser can never run an old renderer or mix old and new modules (verify rounds 3–4: blank slides / blank
  pages). A classic-script banner shows any load/runtime error instead of a silently blank page.
- Each page carries `<meta name="client-version">`; on every (re)connect `ws.js` compares it with
  `GET /api/client-version` and reloads when the client files changed (a tab left open across app runs otherwise
  kept the old renderer: live tests 2026-10-06 showed no KaTeX and no subscripts).
- `tools/replay_interpretations.py <session>` replays a session's logged interpretations through the current engine
  and display (0 tokens); `tools/export_transcript.py <session> <name>` saves a live transcript as a fixture.
- `tools/replay_session.py <session>` replays a recorded session's slide patches into Edge and reports console errors.

## Images (F-007b)
- Image layout: content column | image column (`slide-body.with-image`); the column width comes from the image's
  aspect (`imageColumn` = `composer.image_column_px`: ≤ 720 px landscape, ≤ 600 px otherwise, a tall image only as
  wide as it needs); the picture keeps its aspect at the largest size that fits (container units), fades in, no
  credit line. `safe center` alignment: overflowing content goes down (measured by auto-fit), never into the title.
- `GET /media/<16 hex>.jpg`: only re-encoded files of our image cache (`data/cache/images`); no hot-linking.
- `POST /api/upload` (raw body, `Content-Type` image/jpeg|png|webp|gif, ≤ 10 MB): stores a validated, re-encoded copy,
  returns `{image_id, url, width, height, aspect, alt}`; no state change — `/control` then sends `set_image`.
- `/control` image controls float on the preview (bottom right, a small glass bar, no extra row): **Find image**
  (`change_image` on a slide without one: a search even where the policy said no) · **Add image** (file picker) +
  "or drop one" when the slide has none; with an image: ‹ n / m › (every image this slide has shown, `image_prev` /
  `image_next`), **Change**, upload (own file), remove. A small chip bottom left shows "Finding an image…",
  "No other image found" / "No suitable image found" (after Change / Find) or an upload error. Dragging a file over
  the preview shows the slide as it will look with a dashed drop zone where the image goes; drop → upload →
  `set_image`. The hub sends `image_status` (`state`, `request` = auto | change, `reason` = why none) and
  `image_choices` to the control view only.
- Zoom: clicking the image in the preview sends `zoom_image`; the deck sets `DeckState.zoom`; /display shows the
  image filling the stage (slide background, as large as its aspect allows), /control shows the same inside its
  preview with "← Back to slide (Esc)" at the top right (round 4 step C; it was top left, hard to reach). Esc, a
  click on the image or Back → `unzoom_image`; navigation or the image leaving the slide also ends it; blank still
  wins.
- Before the first slide /display — and the /control preview — show no text, only a slide developing behind glass
  (round 5; redesigned after the long test 2026-10-06: "topic content and an image loading behind a glass, more
  premium, better colours; on /control too"): a soft aurora with fine grain (light: pearl room, teal / periwinkle /
  apricot; dark: deep ink, teal / indigo / violet; tokens `--g-*`); a slide-shaped glass card with a hairline edge
  and a travelling highlight (`@property --glass-angle`) and a halo behind it; behind its frost a slide (crumb,
  title, definition card, lines, image tile) develops from blur to sharp piece by piece (`glass-develop`), a sheen
  sweeps across, three dots breathe below. When the first slide arrives the glass clears over it (`.glass.leaving`,
  backdrop blur 28 → 0 px in 1.2 s) and goes. CSS only; `slide.js Glass` + `useGlassExit` (shared). Between slides
  the previous slide stays; blank is an empty screen (no glass).
- Titles: a slide always shows its own title (`shownTitle` = `spec.title`), so every part reads the same ("What is
  dipole moment?" on parts I and II; user 2026-10-06: keep "What is X?", it answers a question). A lone leading
  definition hides its term when the title names it; otherwise it is a card with its term inside. Definitions after
  other content are one row of cards where the first of them stands (`trailingDefs` = `composer.trailing_definitions`).

## Themes (F-009, V2)
- Slide theme light / dark, switchable mid-lecture: dock button (sun / solid crescent with a small star — the outline
  moon looked hollow, user 2026-10-07) or `T` → `set_theme` → the state store
  (`setup.theme`) → `ThemeChanged` → hub `{"type": "theme"}` → `/display`, `/view` (students follow) and the /control
  preview repaint without a reload. Tokens apply on any element with `data-theme`: the preview carries the slide
  theme, the control page its own.
- Dark (redesigned 2026-10-07): true near-black stage `#050608` with faint teal / indigo corner light
  (`--stage-bg`), graphite cards with a hairline inset ring + deep shadow (`--shadow`, no borders: the composer's
  height model stays exact), a faint top sheen (`--card-sheen`), luminous teal `#3ddcc6` / amber `#ffab66`. Images
  sit on a light mat (`--figure-bg`), since labelled diagrams are drawn on white.
- /control page dark mode: header moon button, per browser (localStorage `copilot.controlTheme`), default light —
  the user decides whether to keep it.

## Teacher notes (F-009, V2)
- Right column = mistake cards + one card with tabs: **Structure · My notes · Materials · Lectures** (F-010; in a
  column narrower than 520 px the tabs not in use show their icon only; F-010b below).
- My notes: Add PDF / drop → `POST /api/notes` (teacher only, ≤ 50 MB) → `data/notes/<sha16>.pdf` (+ page texts) →
  `notes_open`; pages as PNG `GET /api/notes/<id>/page/<n>?w=` (pypdfium2, cached); ‹ n / m ›, arrows inside the
  panel, wider view, remove. **Follow lecture** (on by default): `NotesService` matches the live slide's words
  (MiniLM, 0 tokens; formula TeX skipped) to page chunks → page when ≥ 0.45 and ≥ 0.04 better than the page shown;
  a page turned by hand holds until the next slide. A scan without text: follow off, the panel says why. Never sent to
  `/display`, `/view` or the LLM. The last opened notes reopen next lecture.
- Review 2026-10-07 (user): the empty card is minimal (icon, Add PDF notes, "or drop one here · only you see it", the
  PDFs added before); the notes picker is a menu in the app's style (the open PDF ✓, the others, + Add PDF), not a
  native select.
- F-010b: tabs **Lecture structure · My notes · Materials · Lectures** (icons only below 600 px). Notes take any file
  (Word / PowerPoint via Office, text via Edge, images via Pillow → PDF; `notes/convert.py`) and web links (Edge PDF
  snapshot, `POST /api/notes/link`). **Project**: `notes_project {on}` → `NotesProjected` → every page; /display and
  /view show the page over the slide (blank wins), served by `GET /api/notes/shown/<id>/<page>` only while it is the
  one shown; the lecture never turns a projected page; Esc / Back to slide in /control. Start card at READY (chapter
  + Start). Styled tooltip: `title` → `aria-label` + `data-tip` on render.

## Lecture materials + past lectures (F-010, V2)
- **Materials** tab: *From* chips (This lecture, + Past lecture menu), then tick cards — Summary slide (This topic /
  Whole lecture), Key concepts slide, Notes (PDF), Assignment (PDF, − 10 + questions), Slides (PowerPoint, Light /
  Dark) — files with a name field whose placeholder is the automatic name (`<title> - Notes - 7 Oct 2026.pdf`);
  one **Create** → `materials_create`. Without an LLM the four LLM cards are disabled and the footer says so.
  **Made** list (newest first): spinner + progress while working, the reason in orange when it failed, otherwise
  time · questions / slides · tokens; actions on hover: show on the projector (slides), open (PDF, new tab),
  download, students (shared PDF on/off), rename (inline), delete.
- Summary / key-concepts slides: added at the end of the deck and shown (`Deck.present`); the lecture's next new slide
  follows as usual. Topic summary = the live slide's topic.
- **Lectures** tab: past lectures newest first (title, date, slides, minutes, "test run" for simulator sessions,
  materials count; hide). Opening one: a viewer over /control — the slide full size in that lecture's theme, ‹ › /
  arrow keys, the slide list, the materials made from it; **Make materials** preselects it in the Materials tab.
- Students (`/view`): a Materials button (only when something is shared) → the shared PDFs → download
  (`GET /api/materials/<id>/file`: anyone for a shared PDF, the teacher for everything; `/api/lectures*` teacher only).
- `/web/export/index.html` + `export.js`: the page headless Edge uses to draw slides for the PPTX (not for people).

## Teacher controls
Control View buttons and keyboard shortcuts (when focused): `←/→` navigate, `Space` pause / resume,
`B` blank, `N` force new slide (End lecture: button only; `Esc` closes a zoomed image). The terminal also accepts
`Enter` (start) and `q` (end). **Pin was removed** (round 5, user 2026-10-06: Pause, Blank and navigating back to a
slide — which stops following new slides — cover it).
The buttons are a dock under the preview in the image bar's style: pill groups ‹ n / m › · Pause Blank (on =
filled; Blank in the warning colour, Pause in the accent green like every other button — blue until the long test
2026-10-06) · New slide, End lecture on the right. The earlier plain button
row is removed (the teacher chose the dock).
- **Pause** (replaces Freeze, user 2026-10-06): `pause` / `resume` commands → the app switches the lifecycle
  LIVE ⇄ PAUSED. While paused the understanding service does not buffer new transcript lines (lines already heard are
  still interpreted), so nothing said in the break reaches a slide; the transcript shows those lines greyed
  "(paused)", the terminal "(paused, not used)". Navigation, images and the other controls keep working. The
  projector keeps showing the live slide.
Controls send `Command` messages over the WebSocket → `CommandReceived` events; the UI never mutates state.
- **Layout (round 4 step D):** header (status, Share with students, Open classroom display) · left: preview + dock
  (‹ n / m › · Pause Blank · New slide, Add point · End lecture with a "leave" icon) · right: mistake cards +
  **lecture structure** (topic → facet → slides with part badges, live slide highlighted, click = `goto`; it replaced
  the plain slide list) · bottom: **transcript strip** (last line; click expands to the whole transcript). One column
  below 980 px.
- **Live slide editing:** hovering an element marked `data-edit` in the preview shows an outline and pencil / bin
  (title: pencil only; formula: bin only) **inside the element's top-right corner** (round 5: above it they vanished on
  the way); they stay 1 s after the pointer leaves; a **double-click** on an element opens its editor directly. The
  pencil opens an edit box over it (Enter saves, Esc cancels, leaving it saves); Add point opens one at the bottom. Commands `edit_text` / `delete_item` / `add_point`; the engine keeps the
  teacher's text final (F-005 "Teacher edits").
- **Share with students:** `share_start` → `ShareChanged` (starting → on with the `/view` link | failed with why);
  the header shows the link, Copy, "n watching" (viewer connections), Stop (`share_stop`).
- Mistake cards: only factual / conceptual / formula concerns ("You said X · The slide shows Y", one switch:
  Show what I said ⇄ Show correction, plus **Keep correction** / **Keep what I said** = keep the slide as it is and
  close the card (`dismiss`; round 5, the × alone was too small); × still closes; nothing to approve). Transcription concerns are never sent
  to /control (the hub drops them); the terminal logs them as `[HEARD] wrong -> right`.
