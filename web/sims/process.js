// Process scenes (F-014 S3): parts shared by the step templates (water cycle, heart, photosynthesis, Bohr atom,
// neutralisation). The server sends the steps (simulation/steps.py): each with its number among the drawn steps and its
// name only once the teacher said it or went to it; the current step is `sim.step`, or the auto-cycle's
// (`sim.cycle`), worked out here from the clock exactly as steps.current() does on the server.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { W } from "./draw.js";

// the step shown at simulation time t (-1: none highlighted)
export function currentStep(sim, t) {
  const c = sim.cycle;
  if (sim.step_by !== "auto" || !c) return sim.step;
  const order = (sim.steps || []).map((s, i) => [s, i]).filter(([s]) => s.n > 0).map(([, i]) => i);
  if (!order.length) return sim.step;
  const k0 = Math.max(0, order.indexOf(c.first));
  return order[(k0 + Math.floor(Math.max(0, t - c.t0) / c.every_s)) % order.length];
}

export const stepOf = (sim, id) => (sim.steps || []).find((s) => s.id === id);
export const stepIndex = (sim, id) => (sim.steps || []).findIndex((s) => s.id === id);

// A step's printed number (S4): a main step keeps its own for good, an optional one said later is "1b" (the server's tag)
export const stepTag = (s) => s.tag || String(s.n);
export const mainSteps = (sim) => (sim.steps || []).filter((s) => !s.optional).length;

// The heading over the picture: "Step 2 of 4 · Condensation" (the name only once said), nothing before the first step.
export function StepTitle({ sim, cur, y = 58 }) {
  const s = cur >= 0 ? sim.steps[cur] : null;
  if (!s || !s.n) return null;
  return html`<text class="sim-step-title" x=${W / 2} y=${y} text-anchor="middle" data-el="steps" data-step=${s.id}>
    <tspan class="num">${`Step ${stepTag(s)} of ${mainSteps(sim)}`}</tspan>${s.label && html`<tspan class="name">${` · ${s.label}`}</tspan>`}</text>`;
}

// A step's badge: its number in a circle and, once said, its name beside it in one pill (the name never drifts away from
// its number; each scene puts the badges in free places, sized for the longest name). The circle stays where it is when
// the name appears: anchor start = the pill grows to the right of (x, y), end = to the left. The badge is fixed for
// layout.js (other labels keep off it).
export const PILL_H = 52;
export const pillWidth = (name) => (name ? 80 + name.length * 18 : 52);
export function StepBadge({ sim, id, x, y, cur, anchor = "start" }) {
  const i = stepIndex(sim, id), s = sim.steps[i];
  if (!s || !s.n) return null;
  const on = i === cur, name = s.label || "", w = pillWidth(name);
  const cx = anchor === "end" ? x - 26 : x + 26, x0 = anchor === "end" ? x - w : x;
  return html`<g key=${"b-" + id} class=${"sim-badge" + (on ? " cur" : "") + (name ? " named" : "")} data-step=${id} data-el=${id}>
    ${name && html`<rect class="pill" x=${x0} y=${y - PILL_H / 2} width=${w} height=${PILL_H} rx=${PILL_H / 2} />`}
    <circle cx=${cx} cy=${y} r=${stepTag(s).length > 1 ? 26 : 22} /><text class="num" x=${cx} y=${y + 10} text-anchor="middle">${stepTag(s)}</text>
    ${name && html`<text class="name" x=${anchor === "end" ? cx - 34 : cx + 34} y=${y + 12} text-anchor=${anchor === "end" ? "end" : "start"}
      data-source=${s.source}>${name}</text>`}
  </g>`;
}

// A named part's label ("Left ventricle"), printed only once the teacher named it (the server sends it in labels).
export function PartLabel({ sim, id, x, y, anchor = "middle", cls = "" }) {
  const lb = (sim.labels || {})[id];
  if (!lb || !lb.symbol) return null;
  return html`<text class=${"sim-label word part" + (cls ? " " + cls : "")} x=${x} y=${y} text-anchor=${anchor}
    data-el=${id} data-source="said"><tspan class="sym">${lb.symbol}</tspan></text>`;
}

// A flow along a polyline [[x, y], ...]: a stroke with an arrow head; the current step's flow is bold and moving
// (dashes travel along it with the clock), the others quiet. role: a colour role (tokens.css --sim-*).
export function Flow({ pts, t, on, role = "water", id, head = true, speed = 60 }) {
  const d = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
  const [ax, ay] = pts[pts.length - 2], [bx, by] = pts[pts.length - 1];
  const len = Math.hypot(bx - ax, by - ay) || 1, ux = (bx - ax) / len, uy = (by - ay) / len, H = on ? 26 : 20;
  const hx = bx - ux * H, hy = by - uy * H, px = -uy * H * 0.55, py = ux * H * 0.55;
  return html`<g class=${`sim-flow r-${role}${on ? " cur" : ""}`} data-el=${id}>
    <path class="line" d=${d} style=${{ strokeDashoffset: (-(t * (on ? speed : speed / 3)) % 1000).toFixed(1) }} />
    ${head && html`<path class="head" d=${`M${bx},${by} L${hx + px},${hy + py} L${hx - px},${hy - py} Z`} />`}
  </g>`;
}

// Particles moving along a polyline, evenly spaced, looping with the clock (decorative: no number rests on them)
export function Dots({ pts, t, n = 6, speed = 0.25, r = 9, cls = "sim-dot", phase = 0 }) {
  const seg = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    const L = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    seg.push(L);
    total += L;
  }
  if (!(total > 0)) return null;
  const at = (f) => {
    let s = (((f % 1) + 1) % 1) * total;
    for (let i = 0; i < seg.length; i++) {
      if (s <= seg[i] || i === seg.length - 1) {
        const k = seg[i] ? s / seg[i] : 0;
        return [pts[i][0] + (pts[i + 1][0] - pts[i][0]) * k, pts[i][1] + (pts[i + 1][1] - pts[i][1]) * k];
      }
      s -= seg[i];
    }
    return pts[0];
  };
  return html`${Array.from({ length: n }, (_, i) => {
    const [x, y] = at(phase + i / n + t * speed);
    return html`<circle key=${i} class=${cls} cx=${x.toFixed(1)} cy=${y.toFixed(1)} r=${r} />`;
  })}`;
}
