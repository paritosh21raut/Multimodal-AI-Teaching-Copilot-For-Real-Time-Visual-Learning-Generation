# Live Display + Control View

## Technology (ADR-0003, ADR-0005)
- Server: FastAPI + uvicorn in the same process/loop; the WebSocket hub broadcasts `SlidePatch` and status.
- Client: static ES modules served from `web/`, **no build step**: Preact + htm (vendored in `web/vendor/`),
  KaTeX for formulas, custom SVG components for flows/timelines/trees/causal graphs.
- Display opened full screen on the projector (Chrome/Edge `--app=<url> --start-fullscreen`, or the teacher presses F11).

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
- `tools/replay_session.py <session>` replays a recorded session's slide patches into Edge and reports console errors.

## Teacher controls
Control View buttons and keyboard shortcuts (when focused): `←/→` navigate, `F` freeze, `P` pin, `B` blank,
`N` force new slide, `Esc` end lecture. The terminal also accepts `Enter` (start) and `q` (end).
Controls send `Command` messages over the WebSocket → `CommandReceived` events; the UI never mutates state.
