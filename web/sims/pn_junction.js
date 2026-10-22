// p-n junction (simulation/templates/pn_junction.py): the crystal across the stage, p on the left, n on the right; the
// depletion region around the junction with its fixed ions (− acceptors on the p side, + donors on the n side), the
// field E across it (n to p), holes (open, p side) and electrons (filled, n side) jiggling outside it, the bias battery
// under it once a bias is said. The region's width is the solver's W against the unbiased one (drive.w_ratio) and its
// split is x_p / W (drive.p_share). Carriers are a decorative layer: under forward bias more of them cross (diffusion,
// drive.fwd), under reverse bias only the odd minority carrier drifts back; no number rests on them. Every printed
// value is the server's (labels, readout, the I–V graph).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, clamp, shown } from "./draw.js";

export const TWEEN = ["w_ratio", "p_share", "fwd", "rev"];
const X0 = 110, X1 = 990, XJ = 550, Y0 = 320, Y1 = 470, W0 = 200, YB = 630;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const hash = (i, k) => { const s = Math.sin(i * 127.1 + k * 311.7) * 43758.5453; return s - Math.floor(s); };

// the depletion region's edges (px) for a width ratio and the p side's share of it
export function edges(ratio, share) {
  const w = clamp(ratio, 0.04, 2.8) * W0;
  return [XJ - w * share, XJ + w * (1 - share)];
}

function carriers(t, xl, xr, fwd, rev) {
  const out = [];
  const jig = (i, k) => 7 * Math.sin(t * (1.3 + hash(i, k) * 1.4) + hash(i, k + 1) * 6.28);
  const place = (i, lo, hi, k) => [lo + 14 + hash(i, k) * Math.max(0, hi - lo - 28), Y0 + 18 + hash(i, k + 2) * (Y1 - Y0 - 36)];
  for (let i = 0; i < 22; i++) {  // majority carriers outside the region
    const [hx, hy] = place(i, X0, xl, 1), [ex, ey] = place(i, xr, X1, 5);
    if (hx < xl - 10) out.push(html`<circle key=${"h" + i} class="sim-hole" cx=${hx + jig(i, 1)} cy=${hy + jig(i, 2)} r="9" />`);
    if (ex > xr + 10) out.push(html`<circle key=${"e" + i} class="sim-electron" cx=${ex + jig(i, 3)} cy=${ey + jig(i, 4)} r="8" />`);
  }
  // crossers: diffusion (holes to the right, electrons to the left), more under forward bias, none under reverse
  const nd = rev > 0 ? 0 : Math.round(1 + 6 * fwd), span = 260;
  for (let i = 0; i < nd; i++) {
    const ph = ((t * (0.18 + 0.25 * fwd) + i / nd) % 1 + 1) % 1, y = Y0 + 24 + hash(i, 9) * (Y1 - Y0 - 48);
    out.push(html`<circle key=${"dh" + i} class="sim-hole" cx=${xl - 60 + ph * span} cy=${y + jig(i, 6)} r="9" />`);
    out.push(html`<circle key=${"de" + i} class="sim-electron" cx=${xr + 60 - ph * span} cy=${Y1 - (y - Y0) + jig(i, 7)} r="8" />`);
  }
  // drift: one minority carrier each way, pulled across by the field (an electron to n, a hole to p), any bias
  const ph = ((t * 0.22) % 1 + 1) % 1;
  out.push(html`<circle key="me" class="sim-electron minority" cx=${xl - 30 + ph * (xr - xl + 60)} cy=${Y0 + 28} r="8" />`);
  out.push(html`<circle key="mh" class="sim-hole minority" cx=${xr + 30 - ph * (xr - xl + 60)} cy=${Y1 - 28} r="9" />`);
  return out;
}

export function scene({ sim, v, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const [xl, xr] = edges(v.w_ratio, v.p_share);
  const out = [];
  if (shown(sim, "regions")) {
    out.push(html`<g key="xtal" data-el="regions">
      <rect class="sim-region p" x=${X0} y=${Y0} width=${XJ - X0} height=${Y1 - Y0} />
      <rect class="sim-region n" x=${XJ} y=${Y0} width=${X1 - XJ} height=${Y1 - Y0} />
      <rect class="sim-crystal" x=${X0} y=${Y0} width=${X1 - X0} height=${Y1 - Y0} rx="6" /></g>`);
    out.push(html`<text key="pl" class="sim-region-name" x=${X0 + 24} y=${Y0 - 18}>p</text>`);
    out.push(html`<text key="nl" class="sim-region-name" x=${X1 - 24} y=${Y0 - 18} text-anchor="end">n</text>`);
    out.push(html`<${Label} key="na" x=${X0} y=${Y1 + 42} label=${lb.na} fallback="N_A" id="regions" />`);
    out.push(html`<${Label} key="nd" x=${X1} y=${Y1 + 42} label=${lb.nd} anchor="end" fallback="N_D" id="regions" />`);
  }
  if (shown(sim, "depletion")) {
    out.push(html`<rect key="dep" class="sim-depletion" data-el="depletion" x=${xl} y=${Y0} width=${xr - xl} height=${Y1 - Y0} />`);
    out.push(html`<line key="dl" class="sim-guide" x1=${xl} y1=${Y0 - 6} x2=${xl} y2=${Y1 + 6} data-el="depletion" />`);
    out.push(html`<line key="dr" class="sim-guide" x1=${xr} y1=${Y0 - 6} x2=${xr} y2=${Y1 + 6} data-el="depletion" />`);
    out.push(html`<${Label} key="w" x=${XJ} y=${Y1 + 44} label=${lb.w} anchor="middle" fallback="W" id="depletion" />`);  // under it, between N_A and N_D
  }
  if (shown(sim, "ions")) {
    const ions = [];
    const ion = (key, x, y, cls, sign) => html`<g key=${key} class=${"sim-ion " + cls}><circle cx=${x} cy=${y} r="12" />
      <text x=${x} y=${y + 8} text-anchor="middle">${sign}</text></g>`;
    for (let x = XJ - 18; x > xl + 10; x -= 32) for (let r = 0; r < 4; r++) ions.push(ion("a" + x + ":" + r, x, Y0 + 30 + r * 30, "neg", "−"));
    for (let x = XJ + 18; x < xr - 10; x += 32) for (let r = 0; r < 4; r++) ions.push(ion("d" + x + ":" + r, x, Y0 + 30 + r * 30, "pos", "+"));
    out.push(html`<g key="ions" data-el="ions">${ions}</g>`);
  }
  if (shown(sim, "carriers")) out.push(html`<g key="car" data-el="carriers">${carriers(t, xl, xr, v.fwd, v.rev)}</g>`);
  if (shown(sim, "field") && xr - xl > 40) {  // E points from the + ions (n) to the − ions (p)
    out.push(html`<${Arrow} key="e" x1=${xr - 8} y1=${Y0 - 34} x2=${xl + 8} y2=${Y0 - 34} role="weight" id="field" />`);
    out.push(html`<${Label} key="el" x=${XJ} y=${Y0 - 52} label=${lb.e} role="weight" anchor="middle" fallback="E" id="field" />`);
  }
  if (shown(sim, "currents")) {  // diffusion (p to n, holes' way) and drift (back): lengths only, no numbers
    const dif = v.rev > 0 ? 40 * (1 - v.rev) : 60 + 190 * v.fwd, dr = 60;
    out.push(html`<${Arrow} key="cd" x1=${XJ - dif / 2} y1=${Y1 + 84} x2=${XJ + dif / 2} y2=${Y1 + 84} role="applied" id="currents" />`);
    if (dif >= 24) out.push(html`<text key="cdl" class="sim-label r-applied" x=${XJ - dif / 2 - 16} y=${Y1 + 94} text-anchor="end" data-el="currents">diffusion</text>`);
    out.push(html`<${Arrow} key="cr" x1=${XJ + dr / 2} y1=${Y1 + 124} x2=${XJ - dr / 2} y2=${Y1 + 124} role="friction" id="currents" />`);
    out.push(html`<text key="crl" class="sim-label r-friction" x=${XJ + dr / 2 + 16} y=${Y1 + 134} data-el="currents">drift</text>`);
  }
  if (shown(sim, "battery") && d.bias !== 0) {  // forward: + to the p side
    const fwd = d.bias > 0, cx = XJ, gap = 14;
    out.push(html`<g key="bat" data-el="battery">
      <path class="sim-wire" d=${`M${X0},${Y1} L${X0},${YB + 40} L${cx - gap},${YB + 40} M${cx + gap},${YB + 40} L${X1},${YB + 40} L${X1},${Y1}`} />
      <line class="sim-plate" x1=${cx - gap} y1=${YB + (fwd ? 10 : 24)} x2=${cx - gap} y2=${YB + (fwd ? 70 : 56)} />
      <line class="sim-plate short" x1=${cx + gap} y1=${YB + (fwd ? 24 : 10)} x2=${cx + gap} y2=${YB + (fwd ? 56 : 70)} />
      <text class="sim-sign" x=${cx - gap - 22} y=${YB + 16} text-anchor="middle">${fwd ? "+" : "−"}</text>
      <text class="sim-sign" x=${cx + gap + 22} y=${YB + 16} text-anchor="middle">${fwd ? "−" : "+"}</text></g>`);
    out.push(html`<${Label} key="bl" x=${cx + 56} y=${YB + 52} label=${lb.bias} fallback="V" id="battery" />`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (lb.mat && lb.mat.symbol) out.push(html`<text key="mat" class="sim-note" x="1066" y="712" text-anchor="end">${lb.mat.symbol}</text>`);
  if (lb.note && lb.note.symbol) out.push(html`<text key="note" class="sim-note" x="1066" y="680" text-anchor="end">${lb.note.symbol}</text>`);
  return out;
}
