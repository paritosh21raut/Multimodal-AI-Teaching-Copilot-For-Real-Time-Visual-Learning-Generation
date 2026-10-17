// Block on a horizontal surface, pushed from the left, friction along the contact (simulation/templates/block_on_surface.py).
// Free-body arrows: W from the centre down, N from the top face up, the push F into the left face, friction f along the
// contact face against the motion. Lengths keep the forces' ratios (draw.arrowScale).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Hatch, Label, Readout, arrowScale, shown } from "./draw.js";

export const TWEEN = ["W", "N", "F", "f", "m"];
const GROUND = 500, BW = 176, BH = 150, MAX = 180;  // N above and W below fit the stage under the readout
const X0 = 270, TRAVEL = 600;  // the block's left edge travels X0 .. X0 + TRAVEL (room on the left for the push)

export const motion = (d) => ({ a: d.a || 0, dir: d.moving ? 1 : 0, L: d.track_m || 8, rest: 0.08 });

export function scene({ sim, v, u, at, t }) {
  const L = sim.drive.track_m || 8;
  const xOf = (uu) => X0 + (uu / L) * TRAVEL;
  const x = xOf(u);
  const top = GROUND - BH, cx = x + BW / 2, cy = top + BH / 2;
  const len = arrowScale([v.W, v.N, v.F, v.f], MAX);
  const lb = sim.labels || {};
  const rough = (sim.params.mu || 0) > 0;
  const out = [];
  if (shown(sim, "surface")) {
    out.push(html`<g key="surface" data-el="surface">
      <rect class="sim-ground" x="40" y=${GROUND} width="1020" height="64" />
      <line class="sim-surface" x1="40" y1=${GROUND} x2="1060" y2=${GROUND} />
      <${Hatch} x1=${40} x2=${1060} y=${GROUND} rough=${rough} />
    </g>`);
    if (lb.surface && lb.surface.text) out.push(html`<${Label} key="mu" x=${1040} y=${GROUND + 112} label=${lb.surface} anchor="end" id="surface" />`);
  }
  if (shown(sim, "block") && sim.drive.moving && sim.playback.state === "playing") {  // a faint trail while it slides
    [0.12, 0.24, 0.36].forEach((dt, i) => {
      const gx = xOf(at(Math.max(0, t - dt)));
      if (x - gx > 4) out.push(html`<rect key=${"g" + i} class="sim-ghost" x=${gx} y=${top} width=${BW} height=${BH} rx="10"
        style=${{ opacity: 0.16 - i * 0.05 }} />`);
    });
  }
  // arrows first, the block over them: W is drawn from the centre and shows from the bottom face (as long as N shows)
  if (shown(sim, "weight") && len(v.W)) {
    out.push(html`<${Arrow} key="w" x1=${cx} y1=${cy} x2=${cx} y2=${GROUND + len(v.W)} role="weight" id="weight" />`);
    out.push(html`<${Label} key="wl" x=${cx + 22} y=${GROUND + len(v.W) - 4} label=${lb.weight} role="weight" fallback="W" id="weight" />`);
  }
  if (shown(sim, "normal") && len(v.N)) {
    out.push(html`<${Arrow} key="n" x1=${cx} y1=${cy} x2=${cx} y2=${top - len(v.N)} role="normal" id="normal" />`);
    out.push(html`<${Label} key="nl" x=${cx + 22} y=${top - len(v.N) + 26} label=${lb.normal} role="normal" fallback="N" id="normal" />`);
  }
  if (shown(sim, "friction") && len(v.f)) {  // along the contact, against the motion (or the push); label above it
    const y = GROUND - 14;
    out.push(html`<${Arrow} key="f" x1=${x + 20} y1=${y} x2=${x - len(v.f)} y2=${y} role="friction" id="friction" />`);
    out.push(html`<${Label} key="fl" x=${x - len(v.f) - 14} y=${GROUND - 12} label=${lb.friction} role="friction" anchor="end" fallback="f" id="friction" />`);
  }
  if (shown(sim, "applied") && len(v.F)) {  // the push: into the left face, label above it
    out.push(html`<${Arrow} key="F" x1=${x - 6 - len(v.F)} y1=${cy - 20} x2=${x - 6} y2=${cy - 20} role="applied" id="applied" />`);
    out.push(html`<${Label} key="Fl" x=${x - 14 - len(v.F)} y=${cy - 8} label=${lb.applied} role="applied" anchor="end" fallback="F" id="applied" />`);
  }
  if (shown(sim, "block")) {  // "5 kg" inside the block when it was said (the symbol m would crowd it)
    const mass = lb.block && lb.block.text;
    out.push(html`<g key="block" data-el="block">
      <rect class="sim-block" x=${x} y=${top} width=${BW} height=${BH} rx="10" />
      ${mass && html`<text class="sim-label r-ink in-block" x=${cx} y=${cy + 12} text-anchor="middle"
        data-source=${lb.block.source}>${mass}</text>`}
    </g>`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
