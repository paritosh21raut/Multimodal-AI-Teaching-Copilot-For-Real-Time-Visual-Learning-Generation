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
import { Backdrop, Effect, Magnifier, CANVAS } from "./canvas.js";

const TWEEN_MS = 280;
const CAMERA_MS = 650;  // F-016 focus: the view eases to the focused things
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
// what a body is drawn as (tests and screenshots read it): its picture, else its kind's own drawing
const picOf = (e) => { const l = e.look || {}; return l.image ? "image" : l.photo ? "photo" : l.emoji ? "emoji" : l.form ? "form:" + l.form : l.icon ? "icon:" + l.icon : l.glyph ? "glyph" : "kind"; };
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
  const out = { x: x0 + (x1 - x0) * k, y: y0 + (y1 - y0) * k, angle: a0 + da * k, v: near[4], s: near[5] };
  const sa = track.sa;  // F-016: scale x, scale y, opacity per sample
  if (sa && sa.length === p.length) {
    const [ax, ay, aa] = sa[i - 1], [bx, by, ba] = sa[i];
    out.sx = ax + (bx - ax) * k; out.sy = ay + (by - ay) * k; out.a = aa + (ba - aa) * k;
  }
  return out;
}

export function SceneStage({ b, full, onClick }) {
  const scene = b.scene, still = !!b.still;
  const st = useRef(null);
  if (!st.current) st.current = { shown: {}, from: {}, start: {}, cam: null };  // per entity: geometry drawn, tween origin, start
  const s = st.current;
  const svgRef = useRef(null);
  const [, setFrame] = useState(0);
  const size = useRef([W, H]);
  useLayoutEffect(() => placeLabels(svgRef.current, size.current));
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
      const tweening = Object.values(s.start).some((x) => now() - x < TWEEN_MS) || (s.cam && now() - s.cam.start < CAMERA_MS);
      // a canvas's backdrop moves too (clouds, bubbles): it plays without frames
      const playing = scene.playback.state === "playing" && !still && (!!scene.frames || !!scene.stage.backdrop);
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
  // F-016: things in depth order (behind < in front), the rest dimmed while some are focused, the camera's view box
  const drawn = scene.entities.map((e) => ({ e, g: geomOf(e) }))
    .sort((a, b) => ((a.g && a.g.z) || 0) - ((b.g && b.g.z) || 0));
  const umb = scene.stage.umbrella;
  const canvas = scene.world === "canvas";
  // F-016: a canvas is the whole slide (Python's stage size, 1920 x 1080), drawn 1:1; the other worlds 1100 x 740
  const [SW, SH] = canvas ? scene.stage.size || CANVAS : [W, H];
  size.current = [SW, SH];
  const dimmed = canvas && focus.size > 0;
  let target = scene.stage.camera || [0, 0, SW, SH];
  // one focused thing that moves: the camera follows it (Python sized the box at its laid-out place)
  const fid = scene.stage.camera && focus.size === 1 ? [...focus][0] : null;
  const fe = fid && scene.entities.find((x) => x.id === fid);
  if (fe && fe.geom && tracks[fid]) {
    const [x, y, w, h] = target, dx = tracks[fid].x - fe.geom.c[0], dy = tracks[fid].y - fe.geom.c[1];
    target = [Math.min(Math.max(x + dx, 0), SW - w), Math.min(Math.max(y + dy, 0), SH - h), w, h];
  }
  const following = !!(fe && tracks[fid]);
  if (!s.cam || (!following && JSON.stringify(s.cam.to) !== JSON.stringify(target))
      || (following && JSON.stringify(s.cam.box) !== JSON.stringify(scene.stage.camera))) {
    s.cam = { from: s.cam ? s.cam.now : target, to: target, start: still ? -1e9 : n, now: s.cam ? s.cam.now : target,
              box: scene.stage.camera };
  }
  if (following) s.cam.to = target;  // eases in once, then rides along
  const ck = still ? 1 : Math.min(1, (n - s.cam.start) / CAMERA_MS);
  s.cam.now = s.cam.from.map((v, i) => v + (s.cam.to[i] - v) * ease(ck));
  const fxOf = (id) => (scene.stage.effects || []).filter((f) => f.of === id);
  const zoom = canvas ? s.cam.now[2] / SW : 1;  // names keep their size on screen while the camera zooms in
  const mag = canvas && scene.stage.magnifier;
  const magE = mag && scene.entities.find((x) => x.id === mag.of);
  return html`<div class=${"sim-stage scene-stage" + (canvas ? " canvas" : "") + (full ? " full" : "") + (onClick ? " clickable" : "")} onClick=${onClick}
      title=${onClick ? "Show the scene full screen" : undefined}>
    <svg ref=${svgRef} class="sim-svg" viewBox=${canvas ? s.cam.now.map((v) => v.toFixed(1)).join(" ") : `0 0 ${W} ${H}`}
      preserveAspectRatio=${canvas ? "xMidYMid slice" : "xMidYMid meet"} role="img" style=${canvas ? { "--cam-k": zoom.toFixed(3) } : undefined}
      aria-label=${scene.title} data-template="scene" data-world=${scene.world} data-rev=${scene.rev}
      data-state=${still ? "still" : scene.playback.state} data-t=${t.toFixed(3)} data-camera=${scene.stage.camera ? "focus" : "all"}>
      <${Backdrop} bd=${scene.stage.backdrop} t=${t} W=${SW} H=${SH} />
      <${StageParts} stage=${scene.stage} t=${t} />
      ${drawn.map(({ e, g }) => g && html`<g key=${e.id} class=${"sc-ent" + (dimmed && !focus.has(e.id) ? " cv-dimmed" : "")} data-id=${e.id} data-kind=${e.kind} data-pic=${picOf(e)}>
        <${Shape} e=${e} g=${g} pose=${tracks[e.id]} focus=${focus.has(e.id)} umbrella=${umb && umb[0] === e.id ? umb[1] : null} />
        ${fxOf(e.id).map((fx, i) => html`<${Effect} key=${"fx" + i} fx=${fx} g=${g} pose=${tracks[e.id] || { x: g.c[0], y: g.c[1] }} t=${t} />`)}</g>`)}
      ${drawn.map(({ e, g }) => g && html`<g key=${"w-" + e.id} class=${"sc-ent sc-words" + (dimmed && !focus.has(e.id) ? " cv-dimmed" : "")}><${Words} e=${e} g=${g} pose=${tracks[e.id]} umbrella=${umb && umb[0] === e.id ? umb[1] : null} /></g>`)}
      ${magE && html`<${Magnifier} m=${mag} e=${magE} />`}
      ${rows.length > 0 && html`<g transform=${canvas ? `translate(${s.cam.now[0]} ${s.cam.now[1]}) scale(${zoom})` : undefined}>
        ${canvas ? html`<${Readout} sim=${{ derived: rows }} x=${48} y=${150} />` : html`<${Readout} sim=${{ derived: rows }} />`}</g>`}
    </svg>
  </div>`;
}
