// Simulation runtime (F-014, ADR-0010): renders a slide's `simulation` block (docs/contracts/simulation-spec.md).
//
// One clock per simulation, kept here at module level and shared by every mount of it (the slide, the full stage,
// the /control preview): it is anchored at playback.t whenever playback.rev changes and runs on from there while
// playing. A patch that changes only values (rev unchanged) never touches it, so the motion does not restart: the
// picture tweens to the new geometry and the motion continues from where the block is (Track below).
// Position is a closed-form function of time, never a sum of frame steps, so a paused / background window (Edge stops
// animation frames for a window it does not paint) cannot drift. prefers-reduced-motion: 2 frames a second.
import { html, useEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { H, W } from "./draw.js";
import * as blockOnSurface from "./block_on_surface.js";
import * as incline from "./incline.js";

// template id -> scene module: { scene({sim, v, u, t}), motion(v) -> {a, dir, L, rest}, TWEEN: keys tweened }
export const SCENES = { block_on_surface: blockOnSurface, incline };

const clocks = new Map();  // block id -> {rev, t, at, speed, state}
const now = () => performance.now() / 1000;

function clockOf(id, pb) {
  let c = clocks.get(id);
  if (!c || c.rev !== pb.rev) {
    c = { rev: pb.rev, t: pb.t, at: now(), speed: pb.speed, state: pb.state };
    clocks.set(id, c);
  }
  return c;
}
export const simTime = (c) => (c.state === "playing" ? c.t + (now() - c.at) * c.speed : c.t);

// One-dimensional textbook motion along a track of L metres, closed form and piecewise: from u0 with velocity v0 at
// time t0, constant acceleration a in direction dir (+1 towards L, -1 towards 0, 0 = at rest). At the end of the
// track the block holds HOLD s and the run starts again from the start end. A change of values starts a new piece
// at the current position and velocity (no jump); a change of direction or a reset starts from the start end.
const HOLD = 0.9;
export function makeTrack() {
  let seg = null;
  const at = (g, t) => {
    const tau = Math.max(0, t - g.t0);
    if (!g.dir || g.a <= 1e-9) return { u: g.u0, v: 0 };
    const start = g.dir > 0 ? 0 : g.L, end = g.dir > 0 ? g.L : 0;
    const w0 = Math.max(0, g.v0 * g.dir);
    const rem = Math.abs(end - g.u0);
    const tEnd = (-w0 + Math.sqrt(w0 * w0 + 2 * g.a * rem)) / g.a;
    if (tau <= tEnd) return { u: g.u0 + g.dir * (w0 * tau + 0.5 * g.a * tau * tau), v: g.dir * (w0 + g.a * tau) };
    const run = Math.sqrt((2 * g.L) / g.a);
    const k = tau - tEnd - HOLD;
    if (k < 0) return { u: end, v: 0 };
    const r = k % (run + HOLD);
    return r <= run ? { u: start + g.dir * 0.5 * g.a * r * r, v: g.dir * g.a * r } : { u: end, v: 0 };
  };
  return {
    at: (t) => (seg ? at(seg, t).u : 0),
    update(m, t, restart) {
      if (!seg || restart) {
        seg = { ...m, t0: 0, v0: 0, u0: m.dir > 0 ? 0 : m.dir < 0 ? m.L : m.rest * m.L };
        return;
      }
      if (seg.a === m.a && seg.dir === m.dir && seg.L === m.L) return;
      const cur = at(seg, t);
      const flip = m.dir && seg.dir && m.dir !== seg.dir;
      seg = { ...m, t0: t, v0: flip || !m.dir ? 0 : cur.v, u0: flip ? (m.dir > 0 ? 0 : m.L) : cur.u };
    },
  };
}

const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const TWEEN_S = 0.16;  // time constant of the geometry tween

// The stage of one simulation block. full: the teacher's Full stage (bigger, same clock).
export function SimStage({ b, full, onClick }) {
  const sim = b.sim;
  const mod = SCENES[sim.template];
  const st = useRef(null);
  const [, setFrame] = useState(0);
  if (!st.current || st.current.template !== sim.template) {
    st.current = { template: sim.template, v: { ...sim.drive }, track: makeTrack(), rev: -1, last: now(), t: 0 };
  }
  const s = st.current;
  const clock = clockOf(b.id, sim.playback);
  const restart = s.rev !== sim.playback.rev && (sim.playback.t === 0 || s.rev === -1);
  s.rev = sim.playback.rev;

  useEffect(() => {
    let raf = 0, timer = 0, gone = false;
    const reduced = reducedMotion();
    const step = () => {
      if (gone) return;
      const n = now();
      const dt = Math.min(0.1, n - s.last);
      s.last = n;
      let moving = false;
      for (const k of Object.keys(sim.drive)) {  // tween the geometry towards the new values
        const target = sim.drive[k];
        if (!(mod && mod.TWEEN && mod.TWEEN.includes(k)) || s.v[k] === undefined) { s.v[k] = target; continue; }
        const d = target - s.v[k];
        if (Math.abs(d) < 1e-3 * Math.max(1, Math.abs(target))) s.v[k] = target;
        else { s.v[k] += d * (1 - Math.exp(-dt / TWEEN_S)); moving = true; }
      }
      const playing = sim.playback.state === "playing";
      if (playing || moving) setFrame((f) => f + 1);
      if (reduced) timer = setTimeout(step, 500);
      else if (playing || moving) raf = requestAnimationFrame(step);
    };
    s.last = now();
    step();
    return () => { gone = true; cancelAnimationFrame(raf); clearTimeout(timer); };
  }, [sim]);

  if (!mod) return html`<div class="sim-stage missing"></div>`;  // an unknown template: no picture rather than a wrong one
  let t = simTime(clock);
  if (reducedMotion()) t = Math.floor(t * 2) / 2;
  s.t = t;
  s.track.update(mod.motion(sim.drive), t, restart);
  let body = null;
  try {
    body = mod.scene({ sim, v: s.v, u: s.track.at(t), at: (tt) => s.track.at(tt), t });
  } catch (e) {
    console.error("simulation render failed", sim.template, e);
  }
  return html`<div class=${"sim-stage" + (full ? " full" : "") + (onClick ? " clickable" : "")} onClick=${onClick}
      title=${onClick ? "Show the simulation full screen" : undefined}>
    <svg class="sim-svg" viewBox=${`0 0 ${W} ${H}`} preserveAspectRatio="xMidYMid meet" role="img"
      aria-label=${sim.title} data-template=${sim.template} data-state=${sim.playback.state} data-t=${t.toFixed(3)}
      data-u=${s.track.at(t).toFixed(4)}>
      ${body}
    </svg>
  </div>`;
}

// The slide's simulation filling the 1920x1080 stage (the teacher's Full stage). /control passes onClose.
export function SimFull({ b, onClose }) {
  return html`<div class=${"sim-full" + (onClose ? " closable" : "")}>
    <${SimStage} b=${b} full />
  </div>`;
}

export const simOf = (spec) => (spec && spec.blocks ? spec.blocks.find((x) => x.type === "simulation") : null);
