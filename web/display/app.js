// /display — the projector view. Shows only the live slide; no controls, no chrome.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { Slide, ZoomedImage, imageOf, useStageScale } from "../shared/slide.js";
import { connect, initialState, reduce } from "../shared/ws.js";

const SLIDE_MS = 380;

function useSlideTransition(spec) {
  // Keeps the outgoing slide mounted while it fades out; the incoming one fades in.
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
      ...ls.filter((l) => l.phase !== "is-leaving").map((l) => ({ ...l, phase: "is-leaving" })),
      ...(spec ? [{ spec, phase: "is-entering" }] : []),
    ]);
    const raf = requestAnimationFrame(() => requestAnimationFrame(() =>
      setLayers((ls) => ls.map((l) => (l.phase === "is-entering" ? { ...l, phase: "" } : l)))));
    const t = setTimeout(() => setLayers((ls) => ls.filter((l) => l.phase !== "is-leaving")), SLIDE_MS + 50);
    return () => { cancelAnimationFrame(raf); clearTimeout(t); };
  }, [spec]);
  return layers;
}

function App() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const frozenSpec = useRef(null);
  const containerRef = useRef(null);
  const scale = useStageScale(containerRef);
  const conn = useRef(null);
  const reported = useRef(new Set());

  useEffect(() => {
    conn.current = connect("display", dispatch, (s) => dispatch({ type: "connection", connected: s === "connected" }));
    return () => conn.current.close();
  }, []);
  useEffect(() => { document.documentElement.dataset.theme = state.theme; }, [state.theme]);

  // Auto-fit could not fit the slide even at the smallest type step: tell the server (once per version),
  // so the planner continues on a new slide instead of adding more here.
  const onOverflow = (id) => {
    const spec = state.slides[id];
    const key = `${id}@${spec ? spec.version : 0}`;
    if (reported.current.has(key) || !conn.current) return;
    reported.current.add(key);
    conn.current.send({ type: "overflow", slide_id: id, version: spec ? spec.version : 0 });
  };

  const deck = state.deck;
  const liveSpec = deck && deck.live_id ? state.slides[deck.live_id] : null;
  // Frozen: hold exactly what was on screen when the teacher froze the display.
  if (deck && deck.frozen) { if (!frozenSpec.current) frozenSpec.current = liveSpec; }
  else frozenSpec.current = null;
  const shown = deck && deck.blank ? null : (frozenSpec.current || liveSpec);
  const layers = useSlideTransition(shown);

  const waiting = !shown && !(deck && deck.blank);
  // the teacher clicked the slide's image in /control: it fills the screen until Back / Esc (blank still wins)
  const zoomed = deck && deck.zoom && !deck.blank ? imageOf(state.slides[deck.zoom]) : null;
  return html`<div class="viewport" ref=${containerRef}>
    <div class="stage" style=${{ transform: `translate(-50%, -50%) scale(${scale})` }}>
      ${layers.map((l) => html`<${Slide} key=${l.spec.id} spec=${l.spec} phase=${l.phase} onOverflow=${onOverflow} />`)}
      ${zoomed && html`<${ZoomedImage} key=${zoomed.image_id || zoomed.url} image=${zoomed} />`}
      ${waiting && html`<div class="waiting"><span><span class="dot"></span>${
        state.lifecycle === "live" ? "Listening…" : state.connected ? "Waiting for the lecture to start" : "Connecting…"}</span></div>`}
    </div>
  </div>`;
}

render(html`<${App} />`, document.getElementById("root"));
