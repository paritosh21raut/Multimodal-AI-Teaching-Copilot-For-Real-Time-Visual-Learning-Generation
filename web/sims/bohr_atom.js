// The Bohr model of the atom (simulation/templates/bohr_atom.py), a process scene (S3): the nucleus, the shells as
// circles, the electrons on them (2, 8, 8 ... as the server sends them: e1..e4), each shell turning slowly. Before an
// atom is said: the nucleus and four empty shells, no electron drawn. A jump said: the outer electron moves between the
// two shells round and round (every 4 s), a photon leaves (falling) or comes in (rising), coloured by its wavelength
// when the server knows it (hydrogen only). Shell letters K L M N and the parts are named once said.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Readout, shown } from "./draw.js";
import { PartLabel, StepBadge, StepTitle, currentStep } from "./process.js";

export const TWEEN = [];
export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const CX = 660, CY = 404, R0 = 40, DR = 36, JUMP_S = 4;
const radius = (n) => R0 + DR * n;
const LETTER = ["k", "l", "m", "n"];

// a visible wavelength as a colour (approximate, 380-750 nm); null outside the visible range
function spectral(nm) {
  if (!(nm >= 380 && nm <= 750)) return null;
  const hue = nm < 440 ? 270 - (nm - 380) * 0.5 : nm < 490 ? 240 - (nm - 440) * 1.2 : nm < 510 ? 180 - (nm - 490) * 3 :
    nm < 580 ? 120 - (nm - 510) * 0.85 : nm < 645 ? 60 - (nm - 580) * 0.92 : 0;
  return `hsl(${hue.toFixed(0)}, 90%, 50%)`;
}

// the jumping electron's radius and the photon's progress (0..1, -1 = none) at time t
function jumpAt(d, t) {
  const u = (((t % JUMP_S) + JUMP_S) % JUMP_S) / JUMP_S, r1 = radius(d.n_from), r2 = radius(d.n_to);
  const s = u < 0.35 ? 0 : u < 0.55 ? (u - 0.35) / 0.2 : 1;
  const r = r1 + (r2 - r1) * (0.5 - 0.5 * Math.cos(Math.PI * s));
  const photon = d.emits ? (u >= 0.5 && u < 0.95 ? (u - 0.5) / 0.45 : -1) : (u >= 0.05 && u < 0.4 ? (u - 0.05) / 0.35 : -1);
  return { r, photon };
}

function Photon({ x0, y0, x1, y1, k, colour }) {
  // a short wave packet travelling from (x0, y0) to (x1, y1), k = 0..1
  const L = 90, ang = Math.atan2(y1 - y0, x1 - x0), cx = x0 + (x1 - x0) * k, cy = y0 + (y1 - y0) * k;
  const pts = [];
  for (let i = 0; i <= 24; i++) {
    const s = -L / 2 + (L * i) / 24, w = 9 * Math.sin((i / 24) * Math.PI * 6);
    pts.push(`${(cx + s * Math.cos(ang) - w * Math.sin(ang)).toFixed(1)},${(cy + s * Math.sin(ang) + w * Math.cos(ang)).toFixed(1)}`);
  }
  const hx = cx + (L / 2) * Math.cos(ang), hy = cy + (L / 2) * Math.sin(ang);
  const head = [[hx + 16 * Math.cos(ang), hy + 16 * Math.sin(ang)], [hx + 9 * Math.cos(ang + 2.2), hy + 9 * Math.sin(ang + 2.2)],
    [hx + 9 * Math.cos(ang - 2.2), hy + 9 * Math.sin(ang - 2.2)]];
  return html`<g class="sim-photon" data-el="photon" style=${colour ? `--photon: ${colour}` : ""}>
    <polyline points=${pts.join(" ")} /><polygon points=${head.map((p) => p.map((v) => v.toFixed(1)).join(",")).join(" ")} /></g>`;
}

export function scene({ sim, t }) {
  const d = sim.drive, cur = currentStep(sim, t), lb = sim.labels || {};
  const z = d.z || 0, nShells = d.shells || 4, jump = d.n_from > 0 && d.n_to > 0;
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (shown(sim, "shells")) {
    for (let n = 1; n <= nShells; n++) {
      const occupied = (d[`e${n}`] || 0) > 0 || (jump && (n === d.n_from || n === d.n_to));
      out.push(html`<circle key=${"s" + n} class=${"sim-shell" + (occupied ? " on" : "")} data-el="shells" cx=${CX} cy=${CY} r=${radius(n)} />`);
      if (n <= 4) {
        out.push(html`<${PartLabel} key=${"sl" + n} sim=${sim} id=${LETTER[n - 1]} x=${CX} y=${CY - radius(n) + 26} />`);
      }
    }
  }
  if (shown(sim, "nucleus")) {
    out.push(html`<circle key="nuc" class="sim-nucleus sim-obstacle" data-el="nucleus" cx=${CX} cy=${CY} r="30" />`);
    if (z) out.push(html`<text key="nz" class="sim-nucleus-z" x=${CX} y=${CY + 10} text-anchor="middle">${`${z}p⁺`}</text>`);
    out.push(html`<${PartLabel} key="nl" sim=${sim} id="nucleus" x=${CX + radius(Math.min(nShells, 4)) + 22} y=${CY + 10} anchor="start" />`);
  }
  const J = jump ? jumpAt(d, t) : null;
  if (shown(sim, "electrons")) {
    for (let n = 1; n <= 4; n++) {
      let k = d[`e${n}`] || 0;
      const outer = !d[`e${n + 1}`];
      if (jump && outer && k > 0) k -= 1;  // the outer electron is the one that jumps
      const w = 0.5 / n;
      for (let i = 0; i < k; i++) {
        const a = (2 * Math.PI * i) / Math.max(k, 1) + w * t - Math.PI / 2;
        out.push(html`<circle key=${`e${n}-${i}`} class="sim-electron" data-el="electrons" cx=${(CX + radius(n) * Math.cos(a)).toFixed(1)} cy=${(CY + radius(n) * Math.sin(a)).toFixed(1)} r="11" />`);
      }
    }
    if (J) {
      const a = -Math.PI / 4;
      out.push(html`<circle key="ej" class="sim-electron jump" data-el="electrons" cx=${(CX + J.r * Math.cos(a)).toFixed(1)} cy=${(CY + J.r * Math.sin(a)).toFixed(1)} r="13" />`);
      if (J.photon >= 0 && shown(sim, "photon")) {
        const e = [CX + radius(d.emits ? d.n_to : d.n_from) * Math.cos(a), CY + radius(d.emits ? d.n_to : d.n_from) * Math.sin(a)];
        const far = [CX + 420 * Math.cos(a), CY + 420 * Math.sin(a)];
        const [p0, p1] = d.emits ? [e, far] : [far, e];
        out.push(html`<${Photon} key="ph" x0=${p0[0]} y0=${p0[1]} x1=${p1[0]} y1=${p1[1]} k=${J.photon} colour=${spectral(d.lambda_nm)} />`);
      }
    }
    out.push(html`<${PartLabel} key="el" sim=${sim} id="electrons" x=${CX - radius(Math.min(nShells, 4)) * 0.72 - 16} y=${CY + radius(Math.min(nShells, 4)) * 0.72 + 30} anchor="end" />`);
  }
  if (jump) out.push(html`<${PartLabel} key="phl" sim=${sim} id="photon" x=${CX + 200} y=${CY - 220} anchor="start" />`);
  // the step numbers: on the nucleus, on the outer shell, at the jump
  const rOut = radius(Math.min(nShells, 4));
  const marks = { nucleus: [CX - 54, CY - 44], shells: [CX - rOut * 0.71 - 26, CY - rOut * 0.71], absorb: [CX + 320, CY - 70], emit: [CX + 250, CY - 150] };
  const plain = { ...sim, steps: sim.steps.map((s) => ({ ...s, label: "" })) };  // numbers only: names in the heading
  for (const id of Object.keys(marks)) {
    out.push(html`<${StepBadge} key=${"b" + id} sim=${plain} id=${id} x=${marks[id][0] - 26} y=${marks[id][1]} cur=${cur} />`);
  }
  if (shown(sim, "readout")) {
    const el = lb.element;
    const said = el && el.text ? [{ id: "el", symbol: "Z", text: `${z} (${el.symbol})` }] : [];  // "Z = 11 (Sodium)"
    out.push(html`<${Readout} key="readout" sim=${sim} x=${34} y=${76} fixed said=${said} minW=${300} />`);
  }
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
