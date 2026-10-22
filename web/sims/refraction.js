// Refraction at a flat boundary (simulation/templates/refraction.py): medium 1 above, medium 2 below (shaded by its
// index), the normal at the point of incidence, the incident ray from the upper left, the refracted ray below (none
// past the critical angle: the reflected ray is then the bright one), the angles marked to the normal. Light pulses
// run along the rays, slower in the denser medium (speed ∝ 1 / n). Every printed value is the server's.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = ["t1", "n1", "n2"];
const PX = 560, YB = 330, R = 250, ARC = 74, X0 = 40, X1 = 1060, TOP = 70, BOT = 600;
const rad = (d) => (d * Math.PI) / 180;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

// a medium's shade: denser darker (n 1 → none, n 2.4 → the darkest)
const shade = (n) => Math.max(0, Math.min(0.32, (n - 1) * 0.22));

function arc(a0, a1, r) {  // an arc around the point of incidence between two directions (radians from +x, screen y down)
  const p = (a) => [PX + r * Math.cos(a), YB + r * Math.sin(a)];
  const [x0, y0] = p(a0), [x1, y1] = p(a1);
  return `M${x0},${y0} A${r},${r} 0 0 ${a1 > a0 ? 1 : 0} ${x1},${y1}`;
}

export function scene({ sim, v, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const out = [];
  const t1 = rad(Math.max(0, Math.min(89, v.t1)));
  const tir = d.tir > 0.5;
  const t2 = tir ? 0 : rad(d.t2);
  const inc = [PX - R * Math.sin(t1), YB - R * Math.cos(t1)];
  const refr = [PX + R * Math.sin(t2), YB + R * Math.cos(t2)];
  const refl = [PX + R * Math.sin(t1), YB - R * Math.cos(t1)];
  if (shown(sim, "media")) {
    out.push(html`<rect key="m1" class="sim-medium" x=${X0} y=${TOP} width=${X1 - X0} height=${YB - TOP}
      style=${{ opacity: shade(v.n1) }} data-el="media" />`);
    out.push(html`<rect key="m2" class="sim-medium" x=${X0} y=${YB} width=${X1 - X0} height=${BOT - YB}
      style=${{ opacity: shade(v.n2) }} data-el="media" />`);
    out.push(html`<line key="b" class="sim-surface" x1=${X0} y1=${YB} x2=${X1} y2=${YB} data-el="media" />`);
    if (lb.m1 && lb.m1.symbol) out.push(html`<text key="m1n" class="sim-medium-name" x=${X1 - 16} y=${YB - 70} text-anchor="end">${lb.m1.symbol}</text>`);
    if (lb.m2 && lb.m2.symbol) out.push(html`<text key="m2n" class="sim-medium-name" x=${X1 - 16} y=${YB + 56} text-anchor="end">${lb.m2.symbol}</text>`);
    out.push(html`<${Label} key="n1" x=${X1 - 16} y=${YB - 22} label=${lb.n1} anchor="end" fallback="n₁" id="media" />`);
    out.push(html`<${Label} key="n2" x=${X1 - 16} y=${YB + 102} label=${lb.n2} anchor="end" fallback="n₂" id="media" />`);
  }
  if (shown(sim, "normal")) {
    out.push(html`<line key="nm" class="sim-guide" x1=${PX} y1=${YB - R - 10} x2=${PX} y2=${YB + R + 10} data-el="normal" />`);
  }
  if (shown(sim, "rays")) {
    out.push(html`<line key="ri" class="sim-ray" x1=${inc[0]} y1=${inc[1]} x2=${PX} y2=${YB} data-el="rays" />`);
    out.push(html`<line key="rl" class=${"sim-ray" + (tir ? "" : " faint")} x1=${PX} y1=${YB} x2=${refl[0]} y2=${refl[1]} data-el="rays" />`);
    if (!tir) out.push(html`<line key="rr" class="sim-ray" x1=${PX} y1=${YB} x2=${refr[0]} y2=${refr[1]} data-el="rays" />`);
    // pulses: the incident leg at speed 1 / n₁, then on at 1 / n₂ (refracted) or back at 1 / n₁ (reflected)
    const legIn = R * v.n1, legOut = R * (tir ? v.n1 : v.n2), cyc = legIn + legOut;
    const end = tir ? refl : refr;
    for (let k = 0; k < 3; k++) {
      const s = (((t * 260 + (k * cyc) / 3) % cyc) + cyc) % cyc;
      const [x, y] = s < legIn
        ? [inc[0] + ((PX - inc[0]) * s) / legIn, inc[1] + ((YB - inc[1]) * s) / legIn]
        : [PX + ((end[0] - PX) * (s - legIn)) / legOut, YB + ((end[1] - YB) * (s - legIn)) / legOut];
      out.push(html`<circle key=${"ph" + k} class="sim-light" cx=${x} cy=${y} r="9" data-el="rays" />`);
    }
  }
  if (shown(sim, "angles")) {
    const up = -Math.PI / 2, down = Math.PI / 2;
    if (t1 > 0.01) {
      out.push(html`<path key="a1" class="sim-angle" d=${arc(up - t1, up, ARC)} data-el="angles" />`);
      const m = up - t1 / 2;
      out.push(html`<${Label} key="t1" x=${PX + (ARC + 46) * Math.cos(m)} y=${YB + (ARC + 46) * Math.sin(m) + 10}
        label=${lb.t1} anchor="middle" fallback="θ₁" id="angles" />`);
    }
    if (!tir && t2 > 0.01) {
      out.push(html`<path key="a2" class="sim-angle" d=${arc(down - t2, down, ARC)} data-el="angles" />`);
      const m = down - t2 / 2;
      out.push(html`<${Label} key="t2" x=${PX + (ARC + 46) * Math.cos(m)} y=${YB + (ARC + 46) * Math.sin(m) + 10}
        label=${lb.t2} anchor="middle" fallback="θ₂" id="angles" />`);
    }
  }
  if (lb.tir && lb.tir.symbol) out.push(html`<text key="tir" class="sim-note" x=${PX + 40} y=${YB + 60}>${lb.tir.symbol}</text>`);
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} x=${34} y=${YB + 120} fixed minW=${300} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
