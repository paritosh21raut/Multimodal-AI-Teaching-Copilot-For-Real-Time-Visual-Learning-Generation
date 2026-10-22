// Live scene stage (F-015, docs/contracts/scene-spec.md): renders a slide's `scene` block.
//
// Python computed everything drawn here (geom in stage px, the motion's sampled frames, readouts); this file only
// draws it. Morph-in: a new entity fades and grows in (CSS, ≤ 300 ms); a changed one tweens from where it was to its
// new geometry (TWEEN_MS), so nothing pops. The clock is the simulations' (runtime.js clockOf): anchored when
// playback.rev changes, so a patch of ops never restarts the motion. A motion run is `period` s, then it holds `hold`
// s at its end and starts again. Live readouts print the nearest Python sample (never an interpolated number).
import { html, useEffect, useLayoutEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { H, W, Readout } from "../sims/draw.js";
import { placeLabels } from "../sims/layout.js";
import { clockOf, simTime } from "../sims/runtime.js";
import { Shape, StageParts, Words } from "./kinds.js";

const TWEEN_MS = 280;
const STILL_K = 0.6;  // a still frame (export, archive): this far into the run
const now = () => performance.now();
const ease = (k) => 1 - Math.pow(1 - k, 3);
// simulation.base.fmt on the client (live readouts only): 3 significant figures, whole digits kept, no trailing zeros
export function fmt(x) {
  const ax = Math.abs(x);
  if (!Number.isFinite(x)) return "?";
  if (ax < 5e-4) return ax < 1e-9 ? "0" : "≈ 0";
  const s = x.toFixed(Math.max(0, 2 - Math.floor(Math.log10(ax))));
  return s.includes(".") ? s.replace(/0+$/, "").replace(/\.$/, "") : s;
}
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// a geometry's numbers as one flat list (same shape and size: tweenable)
const flat = (g) => (g ? [...(g.pts || []).flat(), ...(g.c || []), g.r || 0] : []);
function lerpGeom(a, b, k) {
  const fa = flat(a), fb = flat(b);
  if (!a || a.shape !== b.shape || fa.length !== fb.length || a.d !== b.d) return b;
  const f = fa.map((v, i) => v + (fb[i] - v) * k);
  const n = (b.pts || []).length;
  const out = { ...b, pts: (b.pts || []).map((_, i) => [f[2 * i], f[2 * i + 1]]) };
  if (b.c) out.c = [f[2 * n], f[2 * n + 1]];
  out.r = f[f.length - 1];
  return out;
}

// where a track is at simulation time t (the run loops: period, then hold at the end)
export function poseAt(track, frames, t) {
  const p = track.pts;
  if (!p.length) return null;
  const cycle = frames.period + frames.hold;
  let tau = cycle > 0 ? t % cycle : 0;
  tau = Math.min(tau, frames.period, p[p.length - 1][0]);
  let i = 1;
  while (i < p.length - 1 && p[i][0] < tau) i++;
  const [t0, x0, y0, a0] = p[i - 1], [t1, x1, y1, a1] = p[i];
  const k = t1 > t0 ? Math.max(0, Math.min(1, (tau - t0) / (t1 - t0))) : 1;
  const near = k < 0.5 ? p[i - 1] : p[i];
  let da = a1 - a0;
  if (da > 180) da -= 360; else if (da < -180) da += 360;
  return { x: x0 + (x1 - x0) * k, y: y0 + (y1 - y0) * k, angle: a0 + da * k, v: near[4], s: near[5] };
}

export function SceneStage({ b, full, onClick }) {
  const scene = b.scene, still = !!b.still;
  const st = useRef(null);
  if (!st.current) st.current = { shown: {}, from: {}, start: {} };  // per entity: geometry drawn, tween origin, start
  const s = st.current;
  const svgRef = useRef(null);
  const [, setFrame] = useState(0);
  useLayoutEffect(() => placeLabels(svgRef.current));
  const clock = clockOf(b.id, scene.playback);

  // a changed geometry starts a tween from what is drawn now
  const t0 = now();
  for (const e of scene.entities) {
    const prev = s.shown[e.id];
    if (prev && e.geom && JSON.stringify(prev.target) !== JSON.stringify(e.geom)) {
      s.from[e.id] = prev.drawn;
      s.start[e.id] = t0;
    }
    if (!prev || JSON.stringify(prev.target) !== JSON.stringify(e.geom)) s.shown[e.id] = { target: e.geom, drawn: (prev && prev.drawn) || e.geom };
  }
  for (const id of Object.keys(s.shown)) if (!scene.entities.some((e) => e.id === id)) delete s.shown[id];

  useEffect(() => {
    let raf = 0, timer = 0, gone = false;
    const reduced = reducedMotion();
    const step = () => {
      if (gone) return;
      const tweening = Object.values(s.start).some((x) => now() - x < TWEEN_MS);
      const playing = scene.playback.state === "playing" && !still && !!scene.frames;
      if (playing || tweening) setFrame((f) => f + 1);
      if (reduced) timer = setTimeout(step, 500);
      else if (playing || tweening) raf = requestAnimationFrame(step);
    };
    step();
    return () => { gone = true; cancelAnimationFrame(raf); clearTimeout(timer); };
  }, [scene]);

  let t = still ? (scene.frames ? scene.frames.period * STILL_K : 0) : simTime(clock);
  if (reducedMotion() && !still) t = Math.floor(t * 2) / 2;
  const n = now();
  const geomOf = (e) => {
    const sh = s.shown[e.id];
    if (!sh || !e.geom) return e.geom;
    const k = s.start[e.id] === undefined || still ? 1 : Math.min(1, (n - s.start[e.id]) / TWEEN_MS);
    if (k >= 1) delete s.start[e.id];
    sh.drawn = k >= 1 ? e.geom : lerpGeom(s.from[e.id], e.geom, ease(k));
    return sh.drawn;
  };
  const tracks = {};
  for (const tr of (scene.frames && scene.frames.tracks) || []) tracks[tr.id] = poseAt(tr, scene.frames, t);
  const focus = new Set(scene.focus || []);
  const rows = (scene.derived || []).map((d) => {
    if (!d.live) return { id: d.id, symbol: d.label, text: d.text };
    const p = tracks[d.of];
    return p ? { id: d.id, symbol: d.label, text: `${fmt(d.live === "v" ? p.v : p.s)} ${d.unit}` } : null;
  }).filter(Boolean);
  const drawn = scene.entities.map((e) => ({ e, g: geomOf(e) }));
  return html`<div class=${"sim-stage scene-stage" + (full ? " full" : "") + (onClick ? " clickable" : "")} onClick=${onClick}
      title=${onClick ? "Show the scene full screen" : undefined}>
    <svg ref=${svgRef} class="sim-svg" viewBox=${`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
      aria-label=${scene.title} data-template="scene" data-world=${scene.world} data-rev=${scene.rev}
      data-state=${still ? "still" : scene.playback.state} data-t=${t.toFixed(3)}>
      <${StageParts} stage=${scene.stage} />
      ${drawn.map(({ e, g }) => g && html`<g key=${e.id} class="sc-ent" data-id=${e.id} data-kind=${e.kind}>
        <${Shape} e=${e} g=${g} pose=${tracks[e.id]} focus=${focus.has(e.id)} /></g>`)}
      ${drawn.map(({ e, g }) => g && html`<g key=${"w-" + e.id} class="sc-ent sc-words"><${Words} e=${e} g=${g} pose=${tracks[e.id]} /></g>`)}
      ${rows.length > 0 && html`<${Readout} sim=${{ derived: rows }} />`}
    </svg>
  </div>`;
}
