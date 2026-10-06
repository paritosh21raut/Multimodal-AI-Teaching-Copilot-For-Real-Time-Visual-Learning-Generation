// /display — the projector view. Shows only the live slide; no controls, no chrome.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { Slide, ZoomedImage, imageOf, useStageScale } from "../shared/slide.js";
import { connect, initialState, reduce } from "../shared/ws.js";

const SLIDE_MS = 380;
// /view: the same page for students on the shared link (F-008): it only watches, it sends nothing back
const VIEWER = location.pathname === "/view";

function useSlideTransition(spec) {
  // Keeps the outgoing slide mounted while it fades out; the incoming one fades in by a CSS animation (is-new).
  // Nothing waits on animation frames: Edge pauses them for a window it does not paint (a /display window behind
  // /control, a background tab) and the new slide stayed invisible until a reload (live test 2026-10-06). The
  // clean-up timer is not tied to the effect either, so in-place updates of the new slide cannot cancel it.
  const [layers, setLayers] = useState(spec ? [{ spec, phase: "" }] : []);
  const currentId = useRef(spec && spec.id);
  useEffect(() => {
    const id = spec && spec.id;
    if (id === currentId.current) {
      // same slide: in-place update
      setLayers((ls) => ls.map((l) => (l.spec.id === id ? { ...l, spec } : l)));
      return;
    }
    currentId.current = id;
    setLayers((ls) => [
      ...ls.filter((l) => l.phase !== "is-leaving" && l.spec.id !== id).map((l) => ({ ...l, phase: "is-leaving" })),
      ...(spec ? [{ spec, phase: "is-new" }] : []),
    ]);
    setTimeout(() => setLayers((ls) => ls.filter((l) => l.phase !== "is-leaving")), SLIDE_MS + 50);
  }, [spec]);
  return layers;
}

function App() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const containerRef = useRef(null);
  const scale = useStageScale(containerRef);
  const conn = useRef(null);
  const reported = useRef(new Set());

  useEffect(() => {
    conn.current = connect(VIEWER ? "viewer" : "display", dispatch, (s) => dispatch({ type: "connection", connected: s === "connected" }));
    return () => conn.current.close();
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = state.theme; }, [state.theme]);
  useEffect(() => { if (VIEWER) { document.title = "Live lecture"; document.body.style.cursor = "auto"; } }, []);

  // Auto-fit could not fit the slide even at the smallest type step: tell the server (once per version),
  // so the planner continues on a new slide instead of adding more here.
  const onOverflow = (id) => {
    const spec = state.slides[id];
    const key = `${id}@${spec ? spec.version : 0}`;
    if (VIEWER || reported.current.has(key) || !conn.current) return;  // a student's screen size decides nothing
    reported.current.add(key);
    conn.current.send({ type: "overflow", slide_id: id, version: spec ? spec.version : 0 });
  };

  const deck = state.deck;
  const liveSpec = deck && deck.live_id ? state.slides[deck.live_id] : null;
  const shown = deck && deck.blank ? null : liveSpec;
  const layers = useSlideTransition(shown);

  const waiting = !shown && !(deck && deck.blank);
  // the teacher clicked the slide's image in /control: it fills the screen until Back / Esc (blank still wins)
  const zoomed = deck && deck.zoom && !deck.blank ? imageOf(state.slides[deck.zoom]) : null;
  return html`<div class="viewport" ref=${containerRef}>
    <div class="stage" style=${{ transform: `translate(-50%, -50%) scale(${scale})` }}>
      ${layers.map((l) => html`<${Slide} key=${l.spec.id} spec=${l.spec} phase=${l.phase} onOverflow=${onOverflow} />`)}
      ${zoomed && html`<${ZoomedImage} key=${zoomed.image_id || zoomed.url} image=${zoomed} />`}
      ${waiting && html`<${Glass} />`}
    </div>
  </div>`;
}

// Before the first slide (user 2026-10-06): no "preparing" text, which looks dull; soft light moves behind a frosted
// pane, so the projector visibly works while the first slide is prepared. Only here: between slides the previous
// slide stays on screen.
function Glass() {
  return html`<div class="glass" aria-hidden="true">
    <span class="blob b1"></span><span class="blob b2"></span><span class="blob b3"></span><span class="blob b4"></span>
    <div class="pane"><span class="sheen"></span></div>
  </div>`;
}

render(html`<${App} />`, document.getElementById("root"));
