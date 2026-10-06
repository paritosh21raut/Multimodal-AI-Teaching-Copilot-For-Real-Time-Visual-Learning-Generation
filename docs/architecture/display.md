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
| `/control` | teacher laptop | status, mic level, live transcript, deck thumbnails, concerns, controls, latency/LLM stats |

## Rendering rules (visual quality)
- 16:9 stage scaled to the viewport; a design-token system (type scale, spacing, color roles) per theme (light/dark).
- One layout component per representation; layouts are designed, not generic bullets.
- Auto-fit: measure overflow → step down the type scale within limits → otherwise ask the server to split (`overflow` event).
- Transitions: new slide = cross-fade/slide; in-slide update = FLIP animation + fade-in of new items only;
  no full re-render, so there is no flicker. Images fade in only after they are loaded.
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
- `/control` image bar under the preview: status (finding / none / automatic / yours), **Add image** (file picker;
  "Use my image" when there is one), **Change image**, **Remove image**. Dragging a file over the preview shows the
  slide as it will look with a dashed drop zone where the image goes; drop → upload → `set_image`. The hub sends
  `image_status` (searching / found / none) to the control view only.

## Teacher controls
Control View buttons and keyboard shortcuts (when focused): `←/→` navigate, `F` freeze, `P` pin, `B` blank,
`N` force new slide, `Esc` end lecture. The terminal also accepts `Enter` (start) and `q` (end).
Controls send `Command` messages over the WebSocket → `CommandReceived` events; the UI never mutates state.
