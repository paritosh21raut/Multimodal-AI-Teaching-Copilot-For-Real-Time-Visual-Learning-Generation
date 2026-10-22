// An ideal gas under a piston (simulation/templates/gas_piston.py): a cylinder closed by a piston at the height the
// server gives (drive.h: V on a log scale), molecules bouncing inside at a speed ∝ √T (drive.speed), a pressure gauge
// (drive.gauge: log P), a thermometer (drive.temp). What is held constant is named over the cylinder. Every printed
// value is the server's (labels, readout); the picture's own numbers (molecule count, scales) are never printed.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = ["h", "speed", "gauge", "temp"];
const X0 = 200, X1 = 520, BOT = 650, SPAN = 470, WALL = 10, N = 34, R = 9;
const GX = 650, GY = 230, GR = 66, TX = 840, TY0 = 400, TY1 = 610;  // V and n at the cylinder's left

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });

// a fixed scatter: molecule k's start (0..1, 0..1) and direction, the same on every page
const seed = (k, j) => { const x = Math.sin(k * 12.9898 + j * 78.233) * 43758.5453; return x - Math.floor(x); };
const tri = (x) => { const f = ((x % 2) + 2) % 2; return f < 1 ? f : 2 - f; };  // 0 → 1 → 0, bouncing

export function scene({ sim, v, t }) {
  const lb = sim.labels || {};
  const out = [];
  const top = BOT - v.h * SPAN;  // the piston's underside
  if (shown(sim, "cylinder")) {
    out.push(html`<path key="cyl" class="sim-cylinder" d=${`M${X0},${BOT - SPAN - 40} L${X0},${BOT} L${X1},${BOT} L${X1},${BOT - SPAN - 40}`} data-el="cylinder" />`);
    out.push(html`<rect key="gas" class="sim-gas-fill" x=${X0 + WALL / 2} y=${top} width=${X1 - X0 - WALL} height=${BOT - top} data-el="cylinder" />`);
    out.push(html`<rect key="pst" class="sim-piston" x=${X0 + 6} y=${top - 34} width=${X1 - X0 - 12} height="34" rx="4" data-el="cylinder" />`);
    out.push(html`<rect key="rod" class="sim-piston" x=${(X0 + X1) / 2 - 12} y=${top - 34 - 90} width="24" height="90" data-el="cylinder" />`);
    out.push(html`<${Label} key="v" x=${X0 - 24} y=${(top + BOT) / 2} label=${lb.v} anchor="end" fallback="V" id="cylinder" />`);
    out.push(html`<${Label} key="n" x=${X0 - 24} y=${BOT - 10} label=${lb.n} anchor="end" fallback="n" id="cylinder" />`);
    if (lb.hold && lb.hold.symbol) out.push(html`<text key="hold" class="sim-note" x=${(X0 + X1) / 2} y=${BOT - SPAN - 70} text-anchor="middle">${lb.hold.symbol}</text>`);
  }
  if (shown(sim, "molecules")) {
    const w = X1 - X0 - 2 * WALL - 2 * R, h = Math.max(4, BOT - top - 2 * R - 4);
    const ms = [];
    for (let k = 0; k < N; k++) {
      const vx = 0.25 + 0.5 * seed(k, 3), vy = 0.25 + 0.5 * seed(k, 4);  // per second, in box widths (× √T)
      const x = X0 + WALL + R + w * tri(seed(k, 1) * 2 + vx * v.speed * t * 1.6);
      const y = top + R + 2 + h * tri(seed(k, 2) * 2 + vy * v.speed * t * 1.6 * (300 / Math.max(120, h)));
      ms.push(html`<circle key=${k} class="sim-molecule" cx=${x} cy=${y} r=${R} />`);
    }
    out.push(html`<g key="mol" data-el="molecules">${ms}</g>`);
  }
  if (shown(sim, "gauge")) {
    const a = (-210 + 240 * v.gauge) * Math.PI / 180;
    out.push(html`<g key="gauge" data-el="gauge"><circle class="sim-gauge" cx=${GX} cy=${GY} r=${GR} />
      <line class="sim-needle" x1=${GX} y1=${GY} x2=${GX + (GR - 12) * Math.cos(a)} y2=${GY + (GR - 12) * Math.sin(a)} />
      <circle class="sim-needle-hub" cx=${GX} cy=${GY} r="7" /></g>`);
    out.push(html`<path key="pipe" class="sim-pipe" d=${`M${X1 + 5},${BOT - 30} L${GX},${BOT - 30} L${GX},${GY + GR}`} />`);
    out.push(html`<${Label} key="p" x=${GX + GR + 22} y=${GY + 12} label=${lb.p} fallback="P" id="gauge" />`);
  }
  if (shown(sim, "thermometer")) {
    const fill = TY1 - (TY1 - TY0) * Math.max(0.04, v.temp);
    out.push(html`<g key="th" data-el="thermometer"><rect class="sim-thermo" x=${TX - 12} y=${TY0} width="24" height=${TY1 - TY0} rx="12" />
      <rect class="sim-thermo-fill" x=${TX - 6} y=${fill} width="12" height=${TY1 - fill} rx="6" />
      <circle class="sim-thermo-fill" cx=${TX} cy=${TY1 + 14} r="20" /></g>`);
    out.push(html`<${Label} key="t" x=${TX + 40} y=${(TY0 + TY1) / 2} label=${lb.t} fallback="T" id="thermometer" />`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} right fixed y=${30} minW=${300} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
