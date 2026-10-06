# F-008: Sharing, live slide editing, lecture structure, transcript strip (verify round 4, step D)

User decisions 2026-10-06. Architecture: `display.md`. Contracts: `events.md`.

## 1. Share with students (Cloudflare quick tunnel)
- /control header: **Share with students** → `share_start` → `ShareService` (`display/share.py`) runs
  `cloudflared tunnel --no-autoupdate --url http://127.0.0.1:<port>` (no account; `cloudflared.exe` is downloaded once
  to `data/bin/` from Cloudflare's GitHub release on the first share), reads the `https://….trycloudflare.com` URL from
  its log, waits until the URL answers, then publishes `ShareChanged(state=on, url=<url>/view)`.
  States: `off · starting · on · failed (error)`. `share_stop` / app end → the process is stopped.
- Students open `<url>/view`: the projector page in **viewer** role (live slide only, sends nothing). `/` from outside
  → `/view`.
- **Teacher token** (`secrets.token_urlsafe`, per app run): a request is *local* only when it comes from the loopback
  address with a localhost Host header and no proxy headers (`cf-ray`, `cf-connecting-ip`, `x-forwarded-for`).
  Anything else (the tunnel, the LAN) needs the token for `/control`, `/display`, `/api/upload` and the `control` /
  `display` WebSocket roles: `/control?key=<token>` sets an HttpOnly cookie. The terminal prints the remote control
  link; it is never shown on a page.
- /control shows the link, Copy, the number of students watching, Stop sharing.

## 2. Live slide editing (/control preview)
- Hover an item in the preview → pencil (edit) + bin (delete). Title: pencil only. Formula: bin only.
  Round 5 (user 2026-10-06, "it disappears before I can select it"): the tools sit inside the item's top-right corner,
  stay 1 s after the pointer leaves, and a double-click on an item / the title opens the editor directly.
  Editable: title, definition text (+ member card term), notes, points, steps, facts (`label: value`), group labels and
  items, tree nodes, example / note text. **+ Add point** in the dock adds a point to the live slide.
- Commands: `edit_text {slide_id, item_id, text}` (`item_id` = `title`, an element id or `<definition id>:term`),
  `delete_item {slide_id, item_id}`, `add_point {slide_id, text}`.
- **Edits are final:** the engine records every edited / added element and the slide title as the teacher's; revisions,
  correction switches, tentative moves and retitles never change them, and a deleted (or replaced) text never comes
  back on that slide (near-duplicates of it are dropped from later content).

## 3. Lecture structure (/control right column)
Built from the deck: topic → facet → slides (number, shown title, part badge); the live slide highlighted; click =
`goto`. Updates with every patch. Fits a narrow window (titles ellipsize; one column below 980 px).

## 4. Transcript strip (/control bottom)
Collapsed: the last line (paused / dropped lines greyed). Click → expands to the scrollable transcript; click the
header to collapse.

## Acceptance
- Unit: edit/delete/add/title commands; locks against revisions, correction toggles, retitle; deleted text not
  re-added; local-request rule; tunnel URL parsing; viewer cannot send.
- Integration: token rules over HTTP + WebSocket (remote headers), `/view`, share state to control.
- Browser: hover tools + edit + delete + add point in Edge; structure tree click navigates; transcript expands; viewer
  page shows the slide.
- Runtime: real app, Share → a real trycloudflare URL opened in a second browser shows the live slide; /control via the
  tunnel without the key is refused.
