// Series / parallel DC circuit (simulation/templates/dc_circuit.py). The cell sits on the bottom wire, its + plate on
// the left; the circuit is two rails and rungs: series = R₁ and R₂ on the top rung, parallel = R₁ on the top rung and R₂
// on a second one. Dots move along every wire as conventional current (+ to −), each wire as fast as its current
// relative to the cell's current (one scale per circuit: the picture compares, the readout gives the numbers).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = [];
const XL = 520, XR = 980, YT = 290, YM = 470, YB = 590, CELL = 750, SPACING = 46, FAST = 150;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

function zigzag(x1, x2, y) {  // a resistor between x1 and x2 on a horizontal wire
  const n = 6, w = (x2 - x1) / n, pts = [`${x1},${y}`];
  for (let i = 0; i < n; i++) pts.push(`${x1 + w * (i + 0.5)},${y + (i % 2 ? 22 : -22)}`);
  pts.push(`${x2},${y}`);
  return pts.join(" ");
}

// dots along a polyline [[x, y], ...] moving from its first point to its last at `speed` px/s
function dots(key, pts, speed, t) {
  if (!(speed > 0.5)) return null;
  const seg = [];
  let total = 0;
  for (let i = 1; i < pts.length; i++) {
    const l = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]);
    seg.push(l);
    total += l;
  }
  const out = [];
  for (let s = (t * speed) % SPACING; s < total; s += SPACING) {
    let d = s, i = 0;
    while (i < seg.length - 1 && d > seg[i]) d -= seg[i++];
    const f = seg[i] ? d / seg[i] : 0;
    const x = pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f, y = pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f;
    out.push(html`<circle key=${key + s.toFixed(1)} class="sim-charge" cx=${x} cy=${y} r="7" />`);
  }
  return out;
}

export function scene({ sim, t }) {
  const d = sim.drive, series = d.series > 0.5, lb = sim.labels || {};
  const top = Math.max(1e-12, d.I || 0);
  // a branch with a tiny current still shows it moving (circuit review: 0.001 A beside 10 000 A drew nothing)
  const sp = (i) => (Math.abs(i || 0) > 0 ? Math.max(8, (FAST * Math.abs(i)) / top) : 0);
  const out = [];
  // R₁ (and R₂ in series) on the top rung; R₂ on the middle rung in parallel
  const r1 = series ? [600, 720] : [690, 810], r2 = series ? [800, 920] : [690, 810];
  if (shown(sim, "wires")) {
    const wires = series
      ? `M ${XL} ${YB} L ${XL} ${YT} L ${r1[0]} ${YT} M ${r1[1]} ${YT} L ${r2[0]} ${YT} M ${r2[1]} ${YT} L ${XR} ${YT} L ${XR} ${YB} L ${CELL + 12} ${YB} M ${CELL - 12} ${YB} L ${XL} ${YB}`
      : `M ${XL} ${YB} L ${XL} ${YT} L ${r1[0]} ${YT} M ${r1[1]} ${YT} L ${XR} ${YT} L ${XR} ${YB} L ${CELL + 12} ${YB} M ${CELL - 12} ${YB} L ${XL} ${YB}
         M ${XL} ${YM} L ${r2[0]} ${YM} M ${r2[1]} ${YM} L ${XR} ${YM}`;
    out.push(html`<path key="wires" class="sim-wire" data-el="wires" d=${wires} />`);
    if (!series) out.push(html`<g key="nodes">${[[XL, YM], [XR, YM]].map(([x, y]) => html`<circle key=${x} class="sim-pivot" cx=${x} cy=${y} r="8" />`)}</g>`);
  }
  if (shown(sim, "resistors")) {
    out.push(html`<g key="res" data-el="resistors">
      <polyline class="sim-resistor" points=${zigzag(r1[0], r1[1], YT)} />
      <polyline class="sim-resistor" points=${zigzag(r2[0], r2[1], series ? YT : YM)} />
    </g>`);
    out.push(html`<${Label} key="r1l" x=${(r1[0] + r1[1]) / 2} y=${YT - 40} label=${lb.r1} anchor="middle" fallback="R₁" id="resistors" />`);
    out.push(html`<${Label} key="r2l" x=${(r2[0] + r2[1]) / 2} y=${(series ? YT : YM) - 40} label=${lb.r2} anchor="middle" fallback="R₂" id="resistors" />`);
  }
  if (shown(sim, "voltages")) {
    out.push(html`<${Label} key="v1" x=${(r1[0] + r1[1]) / 2} y=${YT + 62} label=${lb.v1} anchor="middle" id="voltages" />`);
    out.push(html`<${Label} key="v2" x=${(r2[0] + r2[1]) / 2} y=${(series ? YT : YM) + 62} label=${lb.v2} anchor="middle" id="voltages" />`);
  }
  if (shown(sim, "cell")) {  // + is the long plate (left): the current leaves it to the left
    out.push(html`<g key="cell" data-el="cell">
      <line class="sim-plate" x1=${CELL - 12} y1=${YB - 40} x2=${CELL - 12} y2=${YB + 40} />
      <line class="sim-plate short" x1=${CELL + 12} y1=${YB - 20} x2=${CELL + 12} y2=${YB + 20} />
      <text class="sim-label r-ink" x=${CELL - 40} y=${YB + 46} text-anchor="middle">+</text>
      <text class="sim-label r-ink" x=${CELL + 40} y=${YB + 46} text-anchor="middle">−</text>
    </g>`);
    out.push(html`<${Label} key="cl" x=${CELL} y=${YB + 96} label=${lb.cell} anchor="middle" fallback="V" id="cell" />`);
  }
  if (shown(sim, "currents")) {
    out.push(html`<${Label} key="il" x=${XL - 22} y=${(YM + YB) / 2 + 12} label=${lb.i} anchor="end" id="currents" />`);
    if (!series) {
      out.push(html`<${Label} key="i1" x=${XR + 22} y=${(YT + YM) / 2 + 12} label=${lb.i1} id="currents" />`);
      out.push(html`<${Label} key="i2" x=${XR - 24} y=${YM - 16} label=${lb.i2} anchor="end" id="currents" />`);
    }
  }
  if (shown(sim, "current")) {
    const tl = sim.playback.state === "playing" || t > 0 ? t : 0;
    if (series) {  // one loop: + (left of the cell) -> left rail up -> top rung -> right rail down -> back to −
      out.push(html`<g key="dots">${dots("s", [[CELL - 12, YB], [XL, YB], [XL, YT], [XR, YT], [XR, YB], [CELL + 12, YB]], sp(d.I), tl)}</g>`);
    } else {
      out.push(html`<g key="dots">
        ${dots("a", [[CELL - 12, YB], [XL, YB], [XL, YM]], sp(d.I), tl)}
        ${dots("b", [[XL, YM], [XL, YT], [XR, YT], [XR, YM]], sp(d.I1), tl)}
        ${dots("c", [[XL, YM], [XR, YM]], sp(d.I2), tl)}
        ${dots("d", [[XR, YM], [XR, YB], [CELL + 12, YB]], sp(d.I), tl)}
      </g>`);
    }
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (shown(sim, "current")) out.push(html`<text key="legend" class="sim-caption" x="1066" y="712" text-anchor="end">● conventional current, + to − · ideal cell</text>`);
  return out;
}
