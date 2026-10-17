// Unit circle → sine (simulation/templates/unit_circle.py). A point goes round the circle anticlockwise, one turn every
// TURN seconds; its height (sin φ) is carried across by a dashed line to the graph, which is traced as φ grows (one
// turn = 0° to 360° on the graph). An angle said is marked on both, with its sin and cos drawn as segments.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Label, Readout, shown } from "./draw.js";

export const TWEEN = [];
const CX = 250, CY = 450, R = 150, GX = 500, GW = 540, TURN = 8, NPTS = 180;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const gx = (deg) => GX + (GW * (((deg % 360) + 360) % 360)) / 360;

export function scene({ sim, t }) {
  const d = sim.drive, lb = sim.labels || {};
  const phi = ((t / TURN) % 1) * 360, pr = (phi * Math.PI) / 180;
  const px = CX + R * Math.cos(pr), py = CY - R * Math.sin(pr);
  const out = [];
  if (shown(sim, "axes")) {
    out.push(html`<g key="axes" data-el="axes" class="sim-axes">
      <line class="sim-guide solid" x1=${CX - R - 30} y1=${CY} x2=${CX + R + 30} y2=${CY} />
      <line class="sim-guide solid" x1=${CX} y1=${CY - R - 30} x2=${CX} y2=${CY + R + 30} />
      <line class="sim-guide solid" x1=${GX} y1=${CY} x2=${GX + GW + 20} y2=${CY} />
      <line class="sim-guide solid" x1=${GX} y1=${CY - R - 20} x2=${GX} y2=${CY + R + 20} />
      <text class="sim-tick" x=${GX - 12} y=${CY - R + 8} text-anchor="end">1</text>
      <text class="sim-tick" x=${GX - 12} y=${CY + R + 8} text-anchor="end">−1</text>
      ${[90, 180, 270, 360].map((a) => html`<text key=${a} class="sim-tick" x=${GX + (GW * a) / 360} y=${CY + 34} text-anchor="middle">${a}°</text>`)}
    </g>`);
  }
  if (shown(sim, "circle")) out.push(html`<circle key="circle" class="sim-guide" data-el="circle" cx=${CX} cy=${CY} r=${R} fill="none" />`);
  if (shown(sim, "graph")) {
    const all = [], done = [];
    for (let i = 0; i <= NPTS; i++) {
      const a = (360 * i) / NPTS, p = `${(GX + (GW * a) / 360).toFixed(1)},${(CY - R * Math.sin((a * Math.PI) / 180)).toFixed(1)}`;
      all.push(p);
      if (a <= phi) done.push(p);
    }
    done.push(`${gx(phi).toFixed(1)},${py.toFixed(1)}`);
    out.push(html`<polyline key="ghost" class="sim-wave ghost" data-el="graph" points=${all.join(" ")} />`);
    out.push(html`<polyline key="trace" class="sim-wave" data-el="graph" points=${done.join(" ")} />`);
  }
  if (shown(sim, "point")) {
    out.push(html`<g key="pt" data-el="point">
      <line class="sim-guide solid" x1=${CX} y1=${CY} x2=${px} y2=${py} />
      <line class="sim-guide" x1=${px} y1=${py} x2=${gx(phi)} y2=${py} />
      <circle class="sim-bob" cx=${px} cy=${py} r="11" />
      <circle class="sim-bob" cx=${gx(phi)} cy=${py} r="9" />
    </g>`);
  }
  if (d.marked > 0.5 && shown(sim, "marked")) {
    // past a full turn the arc and its label show the angle within the turn (405° sits where 45° does)
    const deg = ((d.theta % 360) + 360) % 360, whole = deg === 0 && d.theta > 0;
    const tr = (d.theta * Math.PI) / 180, mx = CX + R * Math.cos(tr), my = CY - R * Math.sin(tr), rr = 46;
    const arc = whole
      ? `M ${CX + rr} ${CY} A ${rr} ${rr} 0 1 0 ${CX - rr} ${CY} A ${rr} ${rr} 0 1 0 ${CX + rr} ${CY}`
      : `M ${CX + rr} ${CY} A ${rr} ${rr} 0 ${deg > 180 ? 1 : 0} 0 ${CX + rr * Math.cos(tr)} ${CY - rr * Math.sin(tr)}`;
    out.push(html`<g key="mk" data-el="marked">
      <line class="sim-marked" x1=${CX} y1=${CY} x2=${mx} y2=${my} />
      <path class="sim-marked thin" d=${arc} fill="none" />
      <line class="sim-guide" x1=${gx(d.theta)} y1=${CY} x2=${gx(d.theta)} y2=${my} />
      <circle class="sim-marked-dot" cx=${mx} cy=${my} r="8" />
      <circle class="sim-marked-dot" cx=${gx(d.theta)} cy=${my} r="8" />
    </g>`);
    out.push(html`<${Label} key="thl" x=${CX} y=${CY + R + 66} label=${lb.theta} anchor="middle" id="marked" />`);
    if (shown(sim, "components")) {
      out.push(html`<g key="comp" data-el="components">
        <line class="sim-seg sin" x1=${mx} y1=${CY} x2=${mx} y2=${my} />
        <line class="sim-seg cos" x1=${CX} y1=${CY} x2=${mx} y2=${CY} />
      </g>`);
      const up = my <= CY;
      out.push(html`<${Label} key="sl" x=${mx + (mx >= CX ? 14 : -14)} y=${(CY + my) / 2 + 10} label=${lb.sin} anchor=${mx >= CX ? "start" : "end"} id="components" />`);
      out.push(html`<${Label} key="cl" x=${(CX + mx) / 2} y=${CY + (up ? 40 : -16)} label=${lb.cos} anchor="middle" id="components" />`);
    }
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${`${sim.title} · radius 1 · one turn = 360°`} />`);
  return out;
}
