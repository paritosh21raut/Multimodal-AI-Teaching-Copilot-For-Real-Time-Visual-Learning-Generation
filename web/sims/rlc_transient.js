// Series RLC step response (simulation/templates/rlc_transient.py). A DC source on the left wire, the switch, R and L
// on the top wire, C on the right wire; the readout at the right. The switch closes at t = 0 of each run; the run
// plays the real transient (drive.t_end real seconds) in drive.stage_s stage seconds, holds, and runs again. The
// picture reads the solver's own curves (sim.series: V_C(t), I(t)) at that moment: the charges along the wire have
// moved by the charge that has flowed (∝ V_C), the capacitor's bar shows V_C against V. Nothing here is printed as a
// number: the graphs and the readout are Python's.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, clamp, shown, symbolParts } from "./draw.js";

export const TWEEN = [];
const XL = 130, XR = 540, YT = 190, YB = 600, YM = (YT + YB) / 2, SPACING = 46, SHIFT = 300;
const SW = [170, 250], RES = [285, 385], IND = [415, 515], BAR = 610;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

// the real time (s) of the transient shown at stage time t: the run, then the hold at its end
export function realTime(d, t) {
  const cyc = d.stage_s + d.hold_s;
  const tc = ((t % cyc) + cyc) % cyc;
  return (Math.min(tc, d.stage_s) / d.stage_s) * d.t_end;
}
export const graphTime = ({ sim, t }) => (sim.drive.t_end > 0 ? realTime(sim.drive, t) : null);

// y of a series line at real time tr (xs are in the axis unit: tr * x_scale)
export function seriesAt(s, tr) {
  if (!s) return 0;
  const ln = s.lines[0], x = tr * (s.x_scale || 1), xs = ln.xs, ys = ln.ys;
  if (x <= xs[0]) return ys[0];
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) return ys[i - 1] + ((x - xs[i - 1]) / (xs[i] - xs[i - 1] || 1)) * (ys[i] - ys[i - 1]);
  }
  return ys[ys.length - 1];
}

export const zigzag = (x1, x2, y) => {
  const n = 6, w = (x2 - x1) / n, pts = [`${x1},${y}`];
  for (let i = 0; i < n; i++) pts.push(`${x1 + w * (i + 0.5)},${y + (i % 2 ? 22 : -22)}`);
  pts.push(`${x2},${y}`);
  return pts.join(" ");
};
export const coil = (x1, x2, y) => {  // four loops above a horizontal wire
  const n = 4, w = (x2 - x1) / n;
  let d = `M${x1},${y}`;
  for (let i = 0; i < n; i++) d += ` a${w / 2},${w / 2} 0 0 1 ${w},0`;
  return d;
};

// charges along the loop, shifted by `shift` px (the charge that has flowed), clockwise from the + plate
function charges(shift) {
  const runs = [[[XL, YM - 30], [XL, YT], [XR, YT], [XR, YM - 22]], [[XR, YM + 22], [XR, YB], [XL, YB], [XL, YM + 30]]];
  const out = [];
  runs.forEach((run, r) => {
    const seg = [];
    let total = 0;
    for (let i = 1; i < run.length; i++) { const l = Math.hypot(run[i][0] - run[i - 1][0], run[i][1] - run[i - 1][1]); seg.push(l); total += l; }
    for (let s = ((shift % SPACING) + SPACING) % SPACING; s < total; s += SPACING) {
      let d = s, i = 0;
      while (i < seg.length - 1 && d > seg[i]) d -= seg[i++];
      const f = seg[i] ? d / seg[i] : 0;
      out.push(html`<circle key=${r + ":" + out.length} class="sim-charge" cx=${run[i][0] + (run[i + 1][0] - run[i][0]) * f}
        cy=${run[i][1] + (run[i + 1][1] - run[i][1]) * f} r="7" />`);
    }
  });
  return out;
}

export function scene({ sim, t }) {
  const d = sim.drive, lb = sim.labels || {}, series = sim.series || [];
  const tr = realTime(d, t);
  const vc = d.V > 0 ? seriesAt(series.find((s) => s.id === "vc_t"), tr) / d.V : 0;  // V_C / V: 0 ... 1 (+ overshoot)
  const out = [];
  if (["source", "resistor", "inductor", "capacitor"].some((e) => shown(sim, e))) {
    out.push(html`<path key="wires" class="sim-wire" d=${`M${XL},${YM - 30} L${XL},${YT} L${SW[0]},${YT} M${SW[1]},${YT}
      L${RES[0]},${YT} M${RES[1]},${YT} L${IND[0]},${YT} M${IND[1]},${YT} L${XR},${YT} L${XR},${YM - 16} M${XR},${YM + 16}
      L${XR},${YB} L${XL},${YB} L${XL},${YM + 30}`} />`);
  }
  if (shown(sim, "source")) {  // + is the long plate (on top); the switch, closed at t = 0
    out.push(html`<g key="cell" data-el="source">
      <line class="sim-plate" x1=${XL - 40} y1=${YM - 12} x2=${XL + 40} y2=${YM - 12} />
      <line class="sim-plate short" x1=${XL - 20} y1=${YM + 12} x2=${XL + 20} y2=${YM + 12} />
      <line class="sim-wire" x1=${XL} y1=${YM - 12} x2=${XL} y2=${YM - 30} /><line class="sim-wire" x1=${XL} y1=${YM + 12} x2=${XL} y2=${YM + 30} />
      <text class="sim-sign" x=${XL - 56} y=${YM - 4} text-anchor="middle">+</text>
      <circle class="sim-pivot" cx=${SW[0]} cy=${YT} r="8" /><circle class="sim-pivot" cx=${SW[1]} cy=${YT} r="8" />
      <line class="sim-wire" x1=${SW[0]} y1=${YT} x2=${SW[1] - 4} y2=${YT - 6} /></g>`);
    out.push(html`<${Label} key="vl" x=${XL + 60} y=${YM + 12} label=${lb.v} fallback="V" id="source" />`);
    out.push(html`<text key="sw" class="sim-note" x=${XL + 24} y=${YT + 44}>switch closed at t = 0</text>`);
  }
  if (shown(sim, "resistor")) {
    out.push(html`<polyline key="r" class="sim-resistor" data-el="resistor" points=${zigzag(RES[0], RES[1], YT)} />`);
    out.push(html`<${Label} key="rl" x=${(RES[0] + RES[1]) / 2} y=${YT - 44} label=${lb.r} anchor="middle" fallback="R" id="resistor" />`);
  }
  if (shown(sim, "inductor")) {
    out.push(html`<path key="l" class="sim-coil" data-el="inductor" d=${coil(IND[0], IND[1], YT)} />`);
    out.push(html`<${Label} key="ll" x=${(IND[0] + IND[1]) / 2} y=${YT - 52} label=${lb.l} anchor="middle" fallback="L" id="inductor" />`);
  }
  if (shown(sim, "capacitor")) {
    const n = Math.round(clamp(vc, 0, 2) * 4);  // + on the top plate, − on the bottom one, as many as V_C / V (drawn)
    const signs = [];
    for (let i = 0; i < n; i++) {
      const x = XR - 36 + (i % 4) * 24, row = Math.floor(i / 4);
      signs.push(html`<text key=${"p" + i} class="sim-sign" x=${x} y=${YM - 28 - row * 22} text-anchor="middle">+</text>`);
      signs.push(html`<text key=${"m" + i} class="sim-sign" x=${x} y=${YM + 48 + row * 22} text-anchor="middle">−</text>`);
    }
    out.push(html`<g key="cap" data-el="capacitor">
      <line class="sim-plate" x1=${XR - 46} y1=${YM - 16} x2=${XR + 46} y2=${YM - 16} />
      <line class="sim-plate" x1=${XR - 46} y1=${YM + 16} x2=${XR + 46} y2=${YM + 16} />${signs}</g>`);
    // V_C against V: a bar beside the plates, the source's level V dashed (a proportion, no number)
    const top = YT + 40, h = YB - 40 - top, full = h / 1.8, fill = clamp(vc, 0, 1.8) * full;
    out.push(html`<g key="bar" class="sim-meter" data-el="capacitor">
      <rect class="frame" x=${BAR - 13} y=${top} width="26" height=${h} rx="6" />
      <rect class="fill" x=${BAR - 13} y=${top + h - fill} width="26" height=${Math.max(0, fill)} rx="6" />
      <line class="level" x1=${BAR - 24} y1=${top + h - full} x2=${BAR + 24} y2=${top + h - full} /></g>`);
    out.push(html`<text key="barl" class="sim-meter-name" x=${BAR} y=${top - 14} text-anchor="middle">${symbolParts("V_C")}</text>`);
    out.push(html`<${Label} key="cl" x=${XR - 64} y=${YM + 12} label=${lb.c} anchor="end" fallback="C" id="capacitor" />`);
  }
  if (shown(sim, "current")) out.push(html`<g key="dots" data-el="current">${charges(SHIFT * vc)}</g>`);
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} right fixed y=${290} />`);  // right of the V_C bar
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (lb.slow && lb.slow.symbol) out.push(html`<text key="slow" class="sim-note" x="1066" y="712" text-anchor="end">${lb.slow.symbol}</text>`);
  return out;
}
