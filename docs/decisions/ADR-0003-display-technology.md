# ADR-0003: Live display = browser page fed by WebSocket
Status: accepted (2026-10-05)

**Options.** (a) PPTX regenerated live, (b) Python GUI (Qt), (c) dashboard frameworks (Streamlit/Gradio),
(d) a dedicated browser page + WebSocket.

**Decision.** (d). FastAPI serves `/display` (projector, full screen) and `/control` (teacher). The server pushes
versioned `SlidePatch`es; the client renders designed layouts with CSS/SVG/KaTeX and animates diffs.

**Why.** Best typography/layout/animation quality; flicker-free incremental updates; the same tech serves
simulations (Canvas/SVG) and storyboards later; dashboards rerun whole pages (flicker, coupling); PPTX is not a live medium.

**Consequences.** PPTX becomes a post-lecture export. The display is a pure client and can reconnect at any time.
