// SVG primitives shared by the simulation scenes (F-014, ADR-0010). Stage units: the simulation column is drawn in a
// 1100 x 740 viewBox, so at stage size 1 unit = 1 stage px (labels >= 34 px, strokes >= 4 px on the projector).
// Colours are roles (tokens.css --sim-*), one per force kind in both themes, and every arrow carries its text label:
// colour is never the only cue. Numbers are printed exactly as the server formatted them (SimLabel.text).
import { html } from "../vendor/htm-preact-standalone.mjs";

export const W = 1100;
export const H = 740;
export const LABEL_PX = 34;
const HEAD = 24;      // arrow head length
const MIN_ARROW = 70;
export const MAX_ARROW = 250;

export const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x));

// Arrow lengths keep the forces' ratios: the largest force present gets `max`, none is shorter than MIN_ARROW.
export function arrowScale(values, max = MAX_ARROW) {
  const top = Math.max(1e-9, ...values.map((v) => Math.abs(v || 0)));
  return (v) => (Math.abs(v || 0) < 1e-6 ? 0 : clamp((Math.abs(v) / top) * max, MIN_ARROW, max));
}

// An arrow from (x1, y1) to its tip (x2, y2). role: weight | normal | friction | applied | component
export function Arrow({ x1, y1, x2, y2, role, dashed, id }) {
  const dx = x2 - x1, dy = y2 - y1;
  const len = Math.hypot(dx, dy);
  if (len < 4) return null;
  const ux = dx / len, uy = dy / len;
  const bx = x2 - ux * HEAD, by = y2 - uy * HEAD;   // where the head starts
  const px = -uy * HEAD * 0.55, py = ux * HEAD * 0.55;
  return html`<g class=${`sim-arrow r-${role}${dashed ? " dashed" : ""}`} data-el=${id}>
    <line x1=${x1} y1=${y1} x2=${bx} y2=${by} />
    <path d=${`M${x2},${y2} L${bx + px},${by + py} L${bx - px},${by - py} Z`} />
  </g>`;
}

// "F = 20 N": the symbol in the KaTeX math face (italic), the value as the server wrote it. A computed value is
// lighter and italic, a said / the teacher's value is ink; anchor: start | middle | end.
export function Label({ x, y, label, role, anchor = "start", fallback, id }) {
  const sym = (label && label.symbol) || fallback || "";
  if (!sym) return null;
  const text = label && label.text;
  const src = label && label.source;
  return html`<text class=${`sim-label r-${role || "ink"}`} x=${x} y=${y} text-anchor=${anchor} data-el=${id}
      data-source=${text ? src : "none"}>
    <tspan class="sym">${symbolParts(sym)}</tspan>${text && html`<tspan class=${"val" + (src === "computed" ? " computed" : "")}>${` = ${text}`}</tspan>`}
  </text>`;
}

// "F_net" -> F with a subscript; "mg sin θ" keeps "sin" upright
function symbolParts(sym) {
  const sub = sym.match(/^([^_]+)_(.+)$/);
  if (sub) return html`${sub[1]}<tspan class="sub" baseline-shift="sub" font-size="0.62em">${sub[2]}</tspan>`;
  const fn = sym.match(/^(.*?)\b(sin|cos|tan)\b(.*)$/);
  if (fn) return html`${fn[1]}<tspan class="fn">${fn[2]}</tspan>${fn[3]}`;
  return sym;
}

// The computed readouts (Derived), top left of the stage: "a = 2.04 m/s²   computed".
export function Readout({ sim, x = 34, y = 30 }) {
  const rows = sim.derived || [];
  if (!rows.length) return null;
  const h = 34 + rows.length * 52;
  const w = Math.max(430, 60 + Math.max(...rows.map((r) => (r.symbol.length + r.text.length + 3) * 18)));
  return html`<g class="sim-readout" data-el="readout" transform=${`translate(${x},${y})`}>
    <rect class="card" x="0" y="0" width=${w} height=${h} rx="18" />
    ${rows.map((r, i) => html`<g key=${r.id} transform=${`translate(26,${62 + i * 52})`}>
      <text class="sim-label r-ink"><tspan class="sym">${symbolParts(r.symbol)}</tspan><tspan class="val computed">${` = ${r.text}`}</tspan></text>
    </g>`)}
    <text class="tag" x=${w - 26} y="30" text-anchor="end">computed</text>
  </g>`;
}

// A short caption (the template's name) under the readout, small and muted.
export function Caption({ text, x = 34, y = 712 }) {
  return text ? html`<text class="sim-caption" x=${x} y=${y}>${text}</text>` : null;
}

// Diagonal hatching under a surface line (a rough surface), from (x1, y) to (x2, y).
export function Hatch({ x1, x2, y, rough }) {
  if (!rough) return null;
  const lines = [];
  for (let x = x1 + 12; x < x2; x += 30) lines.push(html`<line key=${x} x1=${x} y1=${y + 6} x2=${x - 20} y2=${y + 30} />`);
  return html`<g class="sim-hatch">${lines}</g>`;
}

export const shown = (sim, el) => (sim.shown || []).includes(el);
