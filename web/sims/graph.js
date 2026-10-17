// The graph strip under the motion (F-014 S2): x-t / v-t, θ-t, y-t, V-I from the solver's Series
// (docs/contracts/simulation-spec.md). Python samples every curve and writes every axis number (Tick.text); this
// file only scales and draws them. A time graph is drawn up to the clock's time with a cursor (the scene's
// graphTime maps its clock to the curve's time, in seconds); the rest of the curve shows faint, so the shape is
// there from the start. A graph whose inputs are not all known has no numbers: the shape alone.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { W, clamp, symbolParts } from "./draw.js";

export const GH = 250;                       // the strip's height in stage units (the stage is W x 740)
const PADX = 30, GAP = 40, LEFT = 86, RIGHT = 104, TOP = 62, BOTTOM = 52;  // RIGHT: the x axis name after its end

// the y on a line at x (its xs rise)
function yAt(ln, x) {
  const xs = ln.xs, ys = ln.ys;
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) {
      const f = (x - xs[i - 1]) / (xs[i] - xs[i - 1] || 1);
      return ys[i - 1] + f * (ys[i] - ys[i - 1]);
    }
  }
  return ys[ys.length - 1];
}

const axisName = (sym, unit) => html`${symbolParts(sym)}${unit ? ` (${unit})` : ""}`;

function Panel({ s, x0, w, gt }) {
  const named = s.lines.some((ln) => ln.label);  // room at the right for the lines' names
  const L = x0 + LEFT, R = x0 + w - RIGHT - (named ? 70 : 0), T = TOP, B = GH - BOTTOM;
  const [xa, xb] = s.x_range, [ya, yb] = s.y_range;
  const X = (x) => L + ((x - xa) / (xb - xa)) * (R - L);
  const Y = (y) => B - ((y - ya) / (yb - ya)) * (B - T);
  const zero = ya < 0 && yb > 0 ? Y(0) : B;  // the time axis runs along y = 0 when the curve goes below it
  const now = s.time && gt != null ? clamp(gt * (s.x_scale || 1), xa, xb) : null;
  const pts = (xs, ys) => xs.map((x, i) => `${X(x).toFixed(1)},${Y(ys[i]).toFixed(1)}`).join(" ");
  const out = [];
  out.push(html`<line key="ya" class="sim-graph-axis" x1=${L} y1=${T - 8} x2=${L} y2=${B} />`);
  out.push(html`<line key="xa" class="sim-graph-axis" x1=${L} y1=${zero} x2=${R} y2=${zero} />`);
  s.y_ticks.forEach((k) => out.push(html`<g key=${"y" + k.text}>
    <line class="sim-graph-grid" x1=${L} y1=${Y(k.value)} x2=${R} y2=${Y(k.value)} />
    <text class="sim-tick" x=${L - 10} y=${Y(k.value) + 8} text-anchor="end">${k.text}</text></g>`));
  s.x_ticks.forEach((k) => out.push(html`<text key=${"x" + k.text} class="sim-tick" x=${X(k.value)} y=${B + 30}
    text-anchor="middle">${k.text}</text>`));
  out.push(html`<text key="yn" class="sim-graph-name" x=${L} y=${T - 30} text-anchor="middle">${axisName(s.y_symbol, s.y_unit)}</text>`);
  out.push(html`<text key="xn" class="sim-graph-name" x=${R + 24} y=${zero + 10}>${axisName(s.x_symbol, s.x_unit)}</text>`);
  for (const ln of s.lines) {
    const role = ln.role || "ink";
    if (now == null) {
      out.push(html`<polyline key=${ln.id} class=${"sim-graph-line r-" + role} points=${pts(ln.xs, ln.ys)} />`);
    } else {
      const xs = [], ys = [];
      ln.xs.forEach((x, i) => { if (x <= now) { xs.push(x); ys.push(ln.ys[i]); } });
      xs.push(now); ys.push(yAt(ln, now));
      out.push(html`<polyline key=${ln.id + "g"} class="sim-graph-line ghost" points=${pts(ln.xs, ln.ys)} />`);
      if (xs.length > 1) out.push(html`<polyline key=${ln.id} class=${"sim-graph-line r-" + role} points=${pts(xs, ys)} />`);
      out.push(html`<circle key=${ln.id + "c"} class=${"sim-graph-dot r-" + role} cx=${X(now)} cy=${Y(yAt(ln, now))} r="9" />`);
    }
    if (ln.mark) {
      out.push(html`<circle key=${ln.id + "m"} class=${"sim-graph-dot r-" + role} cx=${X(ln.mark[0])} cy=${Y(ln.mark[1])} r="9" />`);
    }
  }
  // several lines: each named at its end, the names at least a line apart (in series they all end at one current)
  const names = s.lines.filter((ln) => ln.label).map((ln) => ({ ln, x: X(ln.xs[ln.xs.length - 1]) + 10, y: Y(ln.ys[ln.ys.length - 1]) + 8 }))
    .sort((a, b) => a.y - b.y);
  for (let i = 1; i < names.length; i++) {
    if (Math.abs(names[i].x - names[i - 1].x) < 60) names[i].y = Math.max(names[i].y, names[i - 1].y + 32);
  }
  names.forEach(({ ln, x, y }) => out.push(html`<text key=${ln.id + "n"} class=${"sim-graph-name r-" + (ln.role || "ink")} x=${x}
    y=${y}>${symbolParts(ln.label)}</text>`));
  if (now != null) out.push(html`<line key="cur" class="sim-graph-cursor" x1=${X(now)} y1=${T} x2=${X(now)} y2=${B} />`);
  return html`<g data-graph=${s.id}>${out}</g>`;
}

// The strip: one or two graphs side by side. gt: the clock's time on the curves (s), null = no cursor.
export function Graph({ sim, gt }) {
  const list = sim.series || [];
  if (!list.length) return null;
  const n = list.length, w = (W - 2 * PADX - GAP * (n - 1)) / n;
  return html`<svg class="sim-graph" viewBox=${`0 0 ${W} ${GH}`} preserveAspectRatio="xMidYMid meet" role="img"
      aria-label=${list.map((s) => s.title).join(", ")} data-el="graph">
    ${list.map((s, i) => html`<${Panel} key=${s.id} s=${s} x0=${PADX + i * (w + GAP)} w=${w} gt=${gt} />`)}
  </svg>`;
}
