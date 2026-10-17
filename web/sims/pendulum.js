// Simple pendulum (simulation/templates/pendulum.py). The bob swings by the exact equation θ'' = -(g/L) sin θ: one
// quarter swing is integrated (RK4) in units of ω₀t once per amplitude and the swing is read from that table, scaled
// to the server's period T, so the motion is a closed-form function of the clock (no drift, every page in step).
// A change of L, θ₀ or g restarts the swing from the release point (server: Template.restart_on, rev + 1).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, clamp, shown } from "./draw.js";

export const TWEEN = ["L"];
const PX = 620, PY = 132, BOB = 34, MAX_V = 150;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time (table below)
// S2 graph: θ-t covers two periods from the release, as the swing below (phase t / T)
export const graphTime = ({ sim, t }) => (sim.drive.T > 0 ? t % (2 * sim.drive.T) : null);

// K(k), the complete elliptic integral of the first kind: one quarter period in units of 1/ω₀
function quarter(th0) {
  let a = 1, b = Math.sqrt(1 - Math.sin(th0 / 2) ** 2);
  for (let i = 0; i < 30 && Math.abs(a - b) > 1e-15; i++) [a, b] = [(a + b) / 2, Math.sqrt(a * b)];
  return Math.PI / (2 * a);
}

const tables = new Map();  // amplitude (0.1° steps) -> {K, th: [], w: []} from release (θ₀) to the bottom (0)
const STEPS = 400;
function table(th0) {
  const key = Math.round(th0 * 1800 / Math.PI);
  let tb = tables.get(key);
  if (tb) return tb;
  const K = quarter(th0), h = K / STEPS;
  const f = (th, w) => [w, -Math.sin(th)];
  let th = th0, w = 0;
  const T = [th], Wv = [w];
  for (let i = 0; i < STEPS; i++) {  // RK4 in τ = ω₀ t
    const [a1, b1] = f(th, w), [a2, b2] = f(th + (h / 2) * a1, w + (h / 2) * b1);
    const [a3, b3] = f(th + (h / 2) * a2, w + (h / 2) * b2), [a4, b4] = f(th + h * a3, w + h * b3);
    th += (h / 6) * (a1 + 2 * a2 + 2 * a3 + a4);
    w += (h / 6) * (b1 + 2 * b2 + 2 * b3 + b4);
    T.push(th);
    Wv.push(w);
  }
  tb = { K, th: T, w: Wv };
  tables.set(key, tb);
  return tb;
}

// θ (rad) and dθ/dτ at the phase p in [0, 1) of a full swing, released from +θ₀ at p = 0
export function swing(th0, p) {
  const tb = table(th0);
  const q = (p * 4) % 4, n = Math.floor(q), r = q - n;  // quarter n: 0 out->bottom, 1 bottom->-θ₀, 2 back, 3 up
  const read = (x) => {
    const i = Math.min(STEPS - 1, Math.floor(x * STEPS)), fr = x * STEPS - i;
    return [tb.th[i] + (tb.th[i + 1] - tb.th[i]) * fr, tb.w[i] + (tb.w[i + 1] - tb.w[i]) * fr];
  };
  if (n === 0) return read(r);
  if (n === 1) { const [a, b] = read(1 - r); return [-a, b]; }
  if (n === 2) { const [a, b] = read(r); return [-a, -b]; }
  const [a, b] = read(1 - r);
  return [a, -b];
}

export function scene({ sim, v, t }) {
  const d = sim.drive;
  const th0 = (clamp(d.theta0_deg || 20, 1, 90) * Math.PI) / 180;
  // string length on the stage: longer strings are drawn longer (log scale), and the swing always fits the stage
  let len = 210 + 230 * clamp((Math.log10(v.L || 1) + 1) / 2, 0, 1);
  const T = d.T || 2;
  const playing = sim.playback.state === "playing" || t > 0;
  const [th, w] = playing ? swing(th0, (t / T) % 1) : [th0, 0];
  const bx = PX + len * Math.sin(th), by = PY + len * Math.cos(th);
  const lb = sim.labels || {};
  const out = [];
  if (shown(sim, "path")) {  // the arc the bob travels, -θ₀ .. θ₀
    const a = (x) => [PX + len * Math.sin(x), PY + len * Math.cos(x)];
    const [x1, y1] = a(-th0), [x2, y2] = a(th0);
    out.push(html`<path key="path" class="sim-guide" data-el="path" fill="none"
      d=${`M ${x1} ${y1} A ${len} ${len} 0 ${th0 > Math.PI / 2 ? 1 : 0} 0 ${x2} ${y2}`} />`);
  }
  if (shown(sim, "angle")) {  // the vertical, the release position (faint) and θ₀ between them
    const rx = PX + len * Math.sin(th0), ry = PY + len * Math.cos(th0), R = Math.min(120, len * 0.42);
    out.push(html`<g key="ang" data-el="angle">
      <line class="sim-guide" x1=${PX} y1=${PY} x2=${PX} y2=${PY + len + 30} />
      <line class="sim-string ghost" x1=${PX} y1=${PY} x2=${rx} y2=${ry} />
      <circle class="sim-bob ghost" cx=${rx} cy=${ry} r=${BOB} />
      <path class="sim-angle" d=${`M ${PX} ${PY + R} A ${R} ${R} 0 0 0 ${PX + R * Math.sin(th0)} ${PY + R * Math.cos(th0)}`} />
    </g>`);
    out.push(html`<${Label} key="al" x=${PX + (R + 16) * Math.sin(th0 / 2) + 8} y=${PY + (R + 16) * Math.cos(th0 / 2) + 12}
      label=${lb.angle} fallback="θ₀" id="angle" />`);
  }
  if (shown(sim, "support")) {
    out.push(html`<g key="support" data-el="support">
      <line class="sim-surface" x1=${PX - 150} y1=${PY} x2=${PX + 150} y2=${PY} />
      ${[...Array(10).keys()].map((i) => html`<line key=${i} class="sim-hatch-line" x1=${PX - 140 + i * 30} y1=${PY}
        x2=${PX - 120 + i * 30} y2=${PY - 22} />`)}
      <circle class="sim-pivot" cx=${PX} cy=${PY} r="8" />
    </g>`);
  }
  if (shown(sim, "string")) {
    out.push(html`<line key="string" class="sim-string" data-el="string" x1=${PX} y1=${PY} x2=${bx} y2=${by} />`);
    // beside the release string, outside it and below θ₀
    const mx = PX + 0.66 * len * Math.sin(th0) + 34 * Math.cos(th0), my = PY + 0.66 * len * Math.cos(th0) - 34 * Math.sin(th0) + 12;
    out.push(html`<${Label} key="ll" x=${mx} y=${my} label=${lb.length} fallback="L" id="length" />`);
  }
  if (shown(sim, "weight") && d.W) {
    out.push(html`<${Arrow} key="w" x1=${bx} y1=${by} x2=${bx} y2=${by + BOB + 96} role="weight" id="weight" />`);
    out.push(html`<${Label} key="wl" x=${bx + 20} y=${by + BOB + 92} label=${lb.weight} role="weight" fallback="W" id="weight" />`);
  }
  if (shown(sim, "velocity") && playing) {  // along the path, as long as the bob's speed on the stage (one scale)
    const n = clamp(w * len * 0.5, -MAX_V, MAX_V);
    if (Math.abs(n) > 6) {
      const ux = Math.cos(th), uy = -Math.sin(th);
      out.push(html`<${Arrow} key="v" x1=${bx} y1=${by} x2=${bx + ux * (n + Math.sign(n) * BOB)} y2=${by + uy * (n + Math.sign(n) * BOB)}
        role="component" dashed id="velocity" />`);
    }
  }
  if (shown(sim, "bob")) {
    const mass = lb.bob && lb.bob.text;
    out.push(html`<g key="bob" data-el="bob"><circle class="sim-bob" cx=${bx} cy=${by} r=${BOB} /></g>`);
    if (mass) out.push(html`<text key="ml" class="sim-label r-ink" x=${bx + (th >= 0 ? -BOB - 14 : BOB + 14)} y=${by + 12}
      text-anchor=${th >= 0 ? "end" : "start"} data-source=${lb.bob.source}>${mass}</text>`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
