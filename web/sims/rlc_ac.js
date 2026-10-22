// Series RLC on an AC source (simulation/templates/rlc_ac.py): the readout at the left, the phasor diagram at the
// top right, the circuit under it (R and L on the top wire, C on the right wire, the source on the bottom wire). The
// phasors turn together, slowed down (drive.rev_s turns a second): the current I is the reference, V_R along it, V_L
// 90° ahead, V_C 90° behind, and the source voltage V = V_R + (V_L − V_C) at the phase angle φ. Lengths keep the
// voltages' ratios (one scale: the largest gets R_MAX). Every printed value is the server's (labels, readout).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, shown } from "./draw.js";
import { coil, zigzag } from "./rlc_transient.js";

export const TWEEN = ["vr", "vl", "vc", "phi"];
const X1 = 570, X2 = 1010, Y1 = 480, Y2 = 650, CX = 800, CY = 225, R_MAX = 165;
const RES = [600, 700], IND = [780, 880], SRC = 790;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

export function scene({ sim, v, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const out = [];
  if (["source", "resistor", "inductor", "capacitor"].some((e) => shown(sim, e))) {
    out.push(html`<path key="wires" class="sim-wire" d=${`M${X1},${Y2} L${X1},${Y1} L${RES[0]},${Y1} M${RES[1]},${Y1}
      L${IND[0]},${Y1} M${IND[1]},${Y1} L${X2},${Y1} L${X2},${(Y1 + Y2) / 2 - 16} M${X2},${(Y1 + Y2) / 2 + 16} L${X2},${Y2}
      L${SRC + 30},${Y2} M${SRC - 30},${Y2} L${X1},${Y2}`} />`);
  }
  if (shown(sim, "source")) {
    out.push(html`<g key="src" data-el="source"><circle class="sim-source" cx=${SRC} cy=${Y2} r="30" />
      <path class="sim-source-wave" d=${`M${SRC - 18},${Y2} q9,-18 18,0 t18,0`} /></g>`);
    out.push(html`<${Label} key="vl" x=${SRC - 46} y=${Y2 + 54} label=${lb.v} anchor="end" fallback="V" id="source" />`);
    out.push(html`<${Label} key="fl" x=${SRC + 46} y=${Y2 + 54} label=${lb.f} fallback="f" id="source" />`);
  }
  if (shown(sim, "resistor")) {
    out.push(html`<polyline key="r" class="sim-resistor" data-el="resistor" points=${zigzag(RES[0], RES[1], Y1)} />`);
    out.push(html`<${Label} key="rl" x=${(RES[0] + RES[1]) / 2} y=${Y1 - 42} label=${lb.r} anchor="middle" fallback="R" id="resistor" />`);
  }
  if (shown(sim, "inductor")) {
    out.push(html`<path key="l" class="sim-coil" data-el="inductor" d=${coil(IND[0], IND[1], Y1)} />`);
    out.push(html`<${Label} key="ll" x=${(IND[0] + IND[1]) / 2} y=${Y1 - 50} label=${lb.l} anchor="middle" fallback="L" id="inductor" />`);
  }
  if (shown(sim, "capacitor")) {
    const ym = (Y1 + Y2) / 2;
    out.push(html`<g key="cap" data-el="capacitor">
      <line class="sim-plate" x1=${X2 - 40} y1=${ym - 16} x2=${X2 + 40} y2=${ym - 16} />
      <line class="sim-plate" x1=${X2 - 40} y1=${ym + 16} x2=${X2 + 40} y2=${ym + 16} /></g>`);
    out.push(html`<${Label} key="cl" x=${X2 - 58} y=${ym + 12} label=${lb.c} anchor="end" fallback="C" id="capacitor" />`);
  }
  if (shown(sim, "phasors")) {
    const th = 2 * Math.PI * d.rev_s * t;  // the current's angle now (counter-clockwise; screen y is down)
    const vs = Math.hypot(v.vr, v.vl - v.vc);
    const top = Math.max(1e-12, v.vr, v.vl, v.vc, vs);
    const tip = (mag, ang) => [CX + (mag / top) * R_MAX * Math.cos(ang), CY - (mag / top) * R_MAX * Math.sin(ang)];
    const phi = (v.phi * Math.PI) / 180;
    const [rx, ry] = tip(v.vr, th), [lx, ly] = tip(v.vl, th + Math.PI / 2), [cx, cy] = tip(v.vc, th - Math.PI / 2);
    const [sx, sy] = tip(vs, th + phi), [ix, iy] = tip(top * 0.45, th);
    out.push(html`<circle key="ring" class="sim-ring" cx=${CX} cy=${CY} r=${R_MAX} data-el="phasors" />`);
    out.push(html`<line key="k1" class="sim-guide" x1=${rx} y1=${ry} x2=${sx} y2=${sy} data-el="phasors" />`);
    out.push(html`<${Arrow} key="pi" x1=${CX} y1=${CY} x2=${ix} y2=${iy} role="component" dashed id="phasors" />`);
    out.push(html`<${Arrow} key="pl" x1=${CX} y1=${CY} x2=${lx} y2=${ly} role="pull" id="phasors" />`);
    out.push(html`<${Arrow} key="pc" x1=${CX} y1=${CY} x2=${cx} y2=${cy} role="friction" id="phasors" />`);
    out.push(html`<${Arrow} key="ps" x1=${CX} y1=${CY} x2=${sx} y2=${sy} role="normal" id="phasors" />`);
    out.push(html`<${Arrow} key="pr" x1=${CX} y1=${CY} x2=${rx} y2=${ry} role="applied" id="phasors" />`);
    const lab = (key, [x, y], label, role, fallback) => {
      const k = Math.hypot(x - CX, y - CY) || 1, ux = (x - CX) / k, uy = (y - CY) / k;
      return html`<${Label} key=${key} x=${x + ux * 22} y=${y + uy * 22 + 12} label=${label} role=${role}
        anchor=${ux < -0.3 ? "end" : ux > 0.3 ? "start" : "middle"} fallback=${fallback} id="phasors" />`;
    };
    out.push(lab("lvr", [rx, ry], lb.vr, "applied", "V_R"), lab("lvl", [lx, ly], lb.vl, "pull", "V_L"),
      lab("lvc", [cx, cy], lb.vc, "friction", "V_C"),
      // near resonance V lies on V_R: its label goes to the other side of the tip (review)
      lab("lvs", Math.abs(phi) < 0.2 ? [sx - (rx - CX) * 0.35, sy - (ry - CY) * 0.35 - 30] : [sx, sy], { symbol: "V" }, "normal", "V"),
      lab("lvi", [ix, iy], { symbol: "I" }, "component", "I"));
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (shown(sim, "phasors")) out.push(html`<text key="slow" class="sim-note" x="1066" y="712" text-anchor="end">phasors turn slowed down</text>`);
  return out;
}
