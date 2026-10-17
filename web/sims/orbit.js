// Circular orbit (simulation/templates/orbit.py). The orbit radius is a fixed size on the stage and the body is drawn
// to the same scale (a body too small to see is drawn at a minimum and the stage says so). One orbit takes the real
// period T, compressed to SHOWN_T seconds on the stage ("shown N× faster"). The satellite goes anticlockwise; its
// velocity is along the orbit, gravity points to the centre.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = [];
const CX = 720, CY = 420, RPX = 250, SAT = 15, SHOWN_T = 8, VLEN = 130, GLEN = 90, MIN_BODY = 14;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

export function scene({ sim, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const above = d.above > 0.5;
  const raw = above ? (d.R / d.r) * RPX : RPX * 0.9, bpx = Math.max(MIN_BODY, raw);
  const th = (2 * Math.PI * t) / SHOWN_T, sx = CX + RPX * Math.cos(th), sy = CY - RPX * Math.sin(th);  // from the right
  const out = [];
  if (shown(sim, "body")) {
    out.push(html`<circle key="body" class="sim-planet" data-el="body" cx=${CX} cy=${CY} r=${bpx} />`);
    if (lb.body && lb.body.text && bpx > 60) {
      out.push(html`<text key="bn" class="sim-label r-ink" x=${CX + 40} y=${CY + 70} text-anchor="middle">${lb.body.text}</text>`);
    } else if (lb.body && lb.body.text) {
      out.push(html`<text key="bn" class="sim-label r-ink" x=${CX} y=${CY + bpx + 40} text-anchor="middle">${lb.body.text}</text>`);
    }
  }
  if (!above) {
    out.push(html`<${Caption} key="cap" text=${`${sim.title} · that radius is inside the body: no orbit`} />`);
    if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
    return out;
  }
  if (shown(sim, "path")) {
    out.push(html`<circle key="path" class="sim-guide" data-el="path" cx=${CX} cy=${CY} r=${RPX} fill="none" />`);
  }
  if (shown(sim, "radius")) {  // drawn to the top of the orbit, still while the satellite moves
    out.push(html`<line key="rad" class="sim-guide solid" data-el="radius" x1=${CX} y1=${CY} x2=${CX - RPX * 0.7071} y2=${CY - RPX * 0.7071} />`);
    out.push(html`<${Label} key="rl" x=${CX - RPX * 0.36 - 18} y=${CY - RPX * 0.36 - 6} label=${lb.radius} anchor="end" fallback="r" id="radius" />`);
    if (lb.altitude && lb.altitude.text) {
      out.push(html`<${Label} key="al" x=${CX + RPX * 0.7071 + 24} y=${CY + RPX * 0.7071 + 30} label=${lb.altitude} id="radius" />`);
    }
  }
  if (shown(sim, "satellite")) {
    out.push(html`<circle key="sat" class="sim-bob" data-el="satellite" cx=${sx} cy=${sy} r=${SAT} />`);
  }
  if (shown(sim, "velocity")) {  // anticlockwise: the tangent is (−sin θ, −cos θ) on screen
    const ex = sx - VLEN * Math.sin(th), ey = sy - VLEN * Math.cos(th);
    out.push(html`<${Arrow} key="v" x1=${sx} y1=${sy} x2=${ex} y2=${ey} role="applied" id="velocity" />`);
    out.push(html`<${Label} key="vl" x=${ex + 14} y=${ey - 8} fallback="v" id="velocity" />`);
  }
  if (shown(sim, "gravity")) {
    const gx = sx - GLEN * Math.cos(th), gy = sy + GLEN * Math.sin(th);
    out.push(html`<${Arrow} key="g" x1=${sx} y1=${sy} x2=${gx} y2=${gy} role="weight" id="gravity" />`);
    out.push(html`<${Label} key="gl" x=${gx + (gx < sx ? -10 : 10)} y=${gy + 34} anchor=${gx < sx ? "end" : "start"} fallback="F_g" id="gravity" />`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  const notes = [];
  if (d.T > SHOWN_T * 1.01) {
    const n = d.T / SHOWN_T;
    notes.push(`shown ${n >= 100 ? Math.round(n).toLocaleString("en") : n.toFixed(n >= 10 ? 0 : 1)}× faster`);
  }
  if (raw < MIN_BODY) notes.push("body not to scale");
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (notes.length) out.push(html`<text key="note" class="sim-caption" x="1066" y="712" text-anchor="end">${notes.join(" · ")}</text>`);
  return out;
}
