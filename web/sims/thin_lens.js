// A thin lens (simulation/templates/thin_lens.py): the principal axis, the lens (convex or concave), both focal
// points, the object (an upright arrow at distance u) and its image (where the server's v puts it, its height m times
// the object's), and the three principal rays from the object's tip: parallel to the axis then through F (or away
// from F: concave), through the optical centre undeflected, through F (or towards F′: concave) then parallel. A
// virtual image is met by the rays' dashed extensions. Light pulses run along the rays. The axis is to scale (the
// server's px_m), the heights on their own scale. Every printed value is the server's.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = ["u", "v", "m", "px_m", "f"];
const LX = 550, AY = 265, HO = 90, HMAX = 190, BOX = [40, 60, 1060, 470], LENS_H = 200;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });

// the point where the ray from p in direction dv leaves the drawing box
function toEdge([x, y], [dx, dy]) {
  let k = Infinity;
  if (dx > 1e-9) k = Math.min(k, (BOX[2] - x) / dx);
  if (dx < -1e-9) k = Math.min(k, (BOX[0] - x) / dx);
  if (dy > 1e-9) k = Math.min(k, (BOX[3] - y) / dy);
  if (dy < -1e-9) k = Math.min(k, (BOX[1] - y) / dy);
  return Number.isFinite(k) ? [x + dx * k, y + dy * k] : [x, y];
}

const clampY = (y) => Math.max(AY - HMAX, Math.min(AY + HMAX, y));

function lensPath(convex) {
  const h = LENS_H, w = 26;
  return convex
    ? `M${LX},${AY - h} Q${LX + w * 2},${AY} ${LX},${AY + h} Q${LX - w * 2},${AY} ${LX},${AY - h} Z`
    : `M${LX - w},${AY - h} L${LX + w},${AY - h} Q${LX + 4},${AY} ${LX + w},${AY + h} L${LX - w},${AY + h} Q${LX - 4},${AY} ${LX - w},${AY - h} Z`;
}

function Pulses({ pts, t, k0 }) {  // light along one ray (a polyline), three pulses
  const seg = [];
  let tot = 0;
  for (let i = 1; i < pts.length; i++) { const L = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(L); tot += L; }
  if (!(tot > 0)) return null;
  return [0, 1, 2].map((j) => {
    let s = (((t * 240 + (j * tot) / 3 + k0 * 57) % tot) + tot) % tot;
    let i = 0;
    while (i < seg.length - 1 && s > seg[i]) { s -= seg[i]; i++; }
    const f = seg[i] ? s / seg[i] : 0;
    return html`<circle key=${j} class="sim-light" r="7" cx=${pts[i][0] + (pts[i + 1][0] - pts[i][0]) * f}
      cy=${pts[i][1] + (pts[i + 1][1] - pts[i][1]) * f} />`;
  });
}

export function scene({ sim, v, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const out = [];
  const px = v.px_m, convex = d.convex > 0.5, inf = d.inf > 0.5;
  const ho = Math.min(HO, HMAX / Math.max(Math.abs(v.m), 1e-9));  // a tall image: a shorter object, the rays still meet at it
  const fpx = v.f * px, xo = LX - v.u * px, yt = AY - ho;
  const xi = LX + v.v * px, yi = clampY(AY - v.m * ho);  // m > 0 upright (above the axis: screen y is down)
  out.push(html`<line key="axis" class="sim-guide" x1=${BOX[0]} y1=${AY} x2=${BOX[2]} y2=${AY} />`);
  if (shown(sim, "lens")) {
    out.push(html`<path key="lens" class="sim-lens" d=${lensPath(convex)} data-el="lens" />`);
    if (lb.lens && lb.lens.symbol) out.push(html`<text key="ln" class="sim-note" x=${LX} y=${AY - LENS_H - 14} text-anchor="middle">${lb.lens.symbol}</text>`);
  }
  if (shown(sim, "foci")) {
    for (const [k, x] of [["F1", LX - fpx], ["F2", LX + fpx]]) {
      out.push(html`<circle key=${k} class="sim-focus" cx=${x} cy=${AY} r="7" data-el="foci" />`);
      out.push(html`<text key=${k + "t"} class="sim-label r-ink" x=${x} y=${AY + 40} text-anchor="middle" data-el="foci"><tspan class="sym">F</tspan></text>`);
    }
    out.push(html`<${Label} key="f" x=${LX + fpx / 2} y=${AY + 78} label=${lb.f} anchor="middle" fallback="f" id="foci" />`);
  }
  if (shown(sim, "object")) {
    out.push(html`<line key="obj" class="sim-object" x1=${xo} y1=${AY} x2=${xo} y2=${yt + 14} data-el="object" />`);
    out.push(html`<path key="objh" class="sim-object-head" d=${`M${xo},${yt} L${xo - 11},${yt + 18} L${xo + 11},${yt + 18} Z`} data-el="object" />`);
    out.push(html`<${Label} key="h" x=${xo - 18} y=${AY - ho / 2} label=${lb.h} anchor="end" fallback="h" id="object" />`);
    out.push(html`<${Label} key="u" x=${(xo + LX) / 2} y=${AY + 120} label=${lb.u} anchor="middle" fallback="u" id="object" />`);
  }
  if (shown(sim, "rays")) {
    const T = [xo, yt];
    const rays = [];  // [incoming polyline, outgoing start, outgoing direction]
    // 1: parallel to the axis, then through F′ (convex) / away from F (concave)
    const p1 = [LX, yt];
    rays.push([[T, p1], p1, convex ? [fpx, AY - yt] : [fpx, yt - AY]]);
    // 2: through the optical centre, undeflected
    rays.push([[T, [LX, AY]], [LX, AY], [LX - xo, AY - yt]]);
    // 3: through F (convex) / towards F′ (concave), then parallel; none when the object sits at F
    const aim = convex ? LX - fpx : LX + fpx;
    if (Math.abs(aim - xo) > 2) {
      const y3 = yt + ((LX - xo) * (AY - yt)) / (aim - xo);
      if (Math.abs(y3 - AY) < LENS_H + 40) rays.push([[T, [LX, y3]], [LX, y3], [1, 0]]);
    }
    rays.forEach(([inc, p, dv], k) => {
      const far = toEdge(p, dv);
      out.push(html`<polyline key=${"r" + k} class="sim-ray" points=${[...inc, far].map((q) => q.join(",")).join(" ")} data-el="rays" />`);
      if (!inf && v.v < 0 && shown(sim, "image")) {  // a virtual image: the rays seem to come from it
        out.push(html`<line key=${"x" + k} class="sim-ray faint dashed" x1=${p[0]} y1=${p[1]} x2=${xi} y2=${yi} data-el="rays" />`);
      }
      out.push(html`<g key=${"p" + k} data-el="rays"><${Pulses} pts=${[...inc, far]} t=${t} k0=${k} /></g>`);
    });
  }
  if (shown(sim, "image") && !inf && xi > BOX[0] && xi < BOX[2]) {
    const virt = v.v < 0;
    const dir = yi < AY ? 1 : -1;
    out.push(html`<line key="img" class=${"sim-image" + (virt ? " virtual" : "")} x1=${xi} y1=${AY} x2=${xi} y2=${yi + dir * 14} data-el="image" />`);
    out.push(html`<path key="imgh" class=${"sim-image-head" + (virt ? " virtual" : "")} d=${`M${xi},${yi} L${xi - 11},${yi + dir * 18} L${xi + 11},${yi + dir * 18} Z`} data-el="image" />`);
    out.push(html`<${Label} key="v" x=${xi + 18} y=${(AY + yi) / 2} label=${lb.v} fallback="image" id="image" />`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} right fixed y=${490} minW=${300} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
