# F-003: Live Display shell + minimal Control View (M2)

## Scope
- `presentation/spec.py`: Pydantic `SlideSpec` + block types (contract: docs/contracts/slide-spec.md). M2 implements
  the blocks `definition`, `points`, `callout`, `example`, `process` (simple), plus layouts `title`, `definition`,
  `concept`, `key_points`, `process_flow`. The others are defined in the model but render as a labelled placeholder until V1.
- `presentation/deck.py`: `Deck` holds slides, live index, frozen/blank flags; produces `SlidePatch` events; navigation.
- `display/server.py`: FastAPI app in the same asyncio loop (uvicorn `Server.serve()` task), static files from `web/`.
  - `GET /display`, `GET /control`, `GET /api/state` (full snapshot)
  - `WS /ws?role=display|control`: server → client messages
    - `hello` {deck, live, theme, lifecycle}
    - `patch` {slide_id, version, spec, live}
    - `live` {slide_id}
    - `status` {lifecycle, audio_level, transcript line, stats}

    client → server: `command` {kind, args} (control only) → `CommandReceived` on the bus.
  - The hub keeps the latest state; a reconnecting client gets `hello` with the full current deck (server-authoritative).
  - Slow clients: per-connection send queue; drop superseded `patch`es of the same slide (latest wins).
- `web/`: no build step. `web/vendor/htm-preact-standalone.mjs`, `web/shared/{tokens.css,layouts.js,ws.js}`,
  `web/display/{index.html,app.js,display.css}`, `web/control/{index.html,app.js,control.css}`.
- Rendering: 16:9 stage, scaled to the viewport (CSS transform), design tokens per theme, keyed item lists
  (stable ids) → only new/changed items animate (fade/slide-in 250 ms); slide change = 350 ms cross-fade; auto-fit by
  measuring overflow and stepping the font scale down (max 2 steps), then reporting `overflow` to the server.
- Startup: the server starts during STARTING; READY prints both URLs; `--open` launches the display in an app window
  (Edge/Chrome `--app=URL`), and the teacher drags it to the projector + F11.
- Demo source until M4: `--demo-slides` publishes a scripted sequence of SlideSpecs (incl. in-place updates).

## Acceptance
- Unit: Deck ops (add/update/navigate/freeze/blank), patch versioning, spec validation (stable ids required).
- Integration: FastAPI TestClient WebSocket: hello on connect, patch fan-out to 2 clients, command → bus event,
  reconnect gets the full deck.
- Browser (Playwright, `-m browser`): screenshots of every M2 layout in light and dark; 100 rapid in-place patches with
  no element re-creation for unchanged items (MutationObserver count) and no console errors. **Screenshots must be viewed.**
- Runtime: `python -m copilot --demo-slides --open` shows the slides updating live on screen.
