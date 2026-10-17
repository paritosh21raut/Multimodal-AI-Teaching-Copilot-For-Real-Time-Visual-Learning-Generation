// Block on a horizontal surface, pushed and / or pulled, friction along the contact (simulation/templates/block_on_surface.py).
// Free-body arrows: W from the centre down, N from the top face up, friction f along the contact face against the
// motion (or the tendency to move). S2 (user 2026-10-18): the push's arrow points ONTO the block (its tip on the face it
// pushes, pressing down when at an angle); the pull's arrow STARTS on the block and points away (lifting when at an
// angle). Each acts forward (to the right) or back (drive F_dir / P_dir). Lengths keep the forces' ratios.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Hatch, Label, Readout, arrowScale, fitIn, shown } from "./draw.js";

export const TWEEN = ["W", "N", "F", "P", "f", "m"];
const GROUND = 500, BW = 176, BH = 150, MAX = 180;  // N above and W below fit the stage under the readout
const X0 = 240, TRAVEL = 460;  // the block's left edge travels X0 .. X0 + TRAVEL: an arrow + label fits on either side (S2)

export const motion = (d) => ({ a: d.a || 0, dir: d.moving ? (d.dir || 1) : 0, L: d.track_m || 8, rest: 0.33 });

// S2 graph: the time of the run on the s-t / v-t curves (from rest at the start end: u = ½at²), null at rest
export function graphTime({ sim, u }) {
  const d = sim.drive;
  if (!d.dir || !(d.a > 1e-9)) return null;
  const start = d.dir > 0 ? 0 : d.track_m || 8;
  return Math.sqrt((2 * Math.abs(u - start)) / d.a);
}

export function scene({ sim, v, u, at, t }) {
  const L = sim.drive.track_m || 8;
  const xOf = (uu) => X0 + (uu / L) * TRAVEL;
  const x = xOf(u);
  const top = GROUND - BH, cx = x + BW / 2, cy = top + BH / 2;
  const len = arrowScale([v.W, v.N, v.F, v.P, v.f], MAX);
  const lb = sim.labels || {};
  const dr = sim.drive;
  const rough = (sim.params.mu || 0) > 0;
  const out = [];
  if (shown(sim, "surface")) {
    out.push(html`<g key="surface" data-el="surface">
      <rect class="sim-ground" x="40" y=${GROUND} width="1020" height="64" />
      <line class="sim-surface" x1="40" y1=${GROUND} x2="1060" y2=${GROUND} />
      <${Hatch} x1=${40} x2=${1060} y=${GROUND} rough=${rough} />
    </g>`);
    if (lb.surface && lb.surface.text) out.push(html`<${Label} key="mu" x=${1040} y=${GROUND + 50} label=${lb.surface} anchor="end" id="surface" />`);
  }
  if (shown(sim, "block") && dr.moving && sim.playback.state === "playing") {  // a faint trail while it slides
    [0.12, 0.24, 0.36].forEach((dt, i) => {
      const gx = xOf(at(Math.max(0, t - dt)));
      if (Math.abs(x - gx) > 4) out.push(html`<rect key=${"g" + i} class="sim-ghost" x=${gx} y=${top} width=${BW} height=${BH} rx="10"
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
  if (shown(sim, "friction") && len(v.f) && dr.f_dir) {  // along the contact, against the (tendency to) move
    const y = GROUND - 14, k = len(v.f), right = dr.f_dir > 0;
    const [x1, x2] = right ? [x + BW - 20, x + BW + k] : [x + 20, x - k];
    out.push(html`<${Arrow} key="f" x1=${x1} y1=${y} x2=${x2} y2=${y} role="friction" id="friction" />`);
    out.push(html`<${Label} key="fl" x=${x2 + (right ? 14 : -14)} y=${GROUND - 12} label=${lb.friction} role="friction"
      anchor=${right ? "start" : "end"} fallback="f" id="friction" />`);
  }
  // the push and the pull: the face each acts on (a push forward presses the left face, a pull forward starts on the
  // right one); two forces on one face sit one above the other
  const pushOn = shown(sim, "applied") && len(v.F), pullOn = shown(sim, "pull") && len(v.P);
  const pushFace = (dr.F_dir || 1) > 0 ? -1 : 1, pullFace = (dr.P_dir || 1) > 0 ? 1 : -1;  // -1 left face, +1 right
  const shared = pushOn && pullOn && pushFace === pullFace;
  const faceX = (side) => (side < 0 ? x - 6 : x + BW + 6);
  const force = (key, el, angleEl, k, deg, side, onto, yy, label, angleLabel) => {
    const th = ((deg || 0) * Math.PI) / 180, c = Math.cos(th), s = Math.sin(th);
    const ox = faceX(side), oy = yy;                          // the point on the face
    const far = [ox + side * k * c, oy - k * s];              // away from the face, up at the angle
    const [x1, y1, x2, y2] = onto ? [far[0], far[1], ox, oy] : [ox, oy, far[0], far[1]];
    out.push(html`<${Arrow} key=${key} x1=${x1} y1=${y1} x2=${x2} y2=${y2} role=${key === "P" ? "pull" : "applied"} id=${el} />`);
    out.push(html`<${Label} key=${key + "l"} x=${far[0] + side * 10} y=${far[1] + (th > 0 ? -8 : 12)} label=${label}
      role=${key === "P" ? "pull" : "applied"} anchor=${side > 0 ? "start" : "end"} fallback="F" id=${el} />`);
    if (shown(sim, angleEl) && th > 0) {  // θ between the force and the horizontal, at the face it acts on
      const R = 92, ex = ox + side * R * c, ey = oy - R * s;
      out.push(html`<g key=${key + "ang"} data-el=${angleEl}>
        <line class="sim-guide" x1=${ox} y1=${oy} x2=${ox + side * (R + 30)} y2=${oy} />
        <path class="sim-angle" d=${`M ${ox + side * R} ${oy} A ${R} ${R} 0 0 ${side > 0 ? 0 : 1} ${ex} ${ey}`} />
      </g>`);
      out.push(html`<${Label} key=${key + "al"} x=${ox + side * (R + 14) * Math.cos(th / 2)} y=${oy - (R + 14) * Math.sin(th / 2) + 10}
        label=${angleLabel} anchor=${side > 0 ? "start" : "end"} fallback="θ" id=${angleEl} />`);
    }
  };
  if (pushOn) force("F", "applied", "angle", len(v.F), dr.theta_deg, pushFace, true, shared ? cy - 40 : cy - 20, lb.applied, lb.angle);
  if (pullOn) force("P", "pull", "pull_angle", len(v.P), dr.phi_deg, pullFace, false, shared ? cy + 30 : cy - 20, lb.pull, lb.pull_angle);
  if (dr.lift_note) out.push(html`<text key="lift" class="sim-label r-ink" x="550" y="100" text-anchor="middle">
    The pull lifts the block off the floor</text>`);
  if (shown(sim, "block")) {  // "5 kg" inside the block when it was said (the symbol m would crowd it)
    const mass = lb.block && lb.block.text;
    out.push(html`<g key="block" data-el="block">
      <rect class="sim-block" x=${x} y=${top} width=${BW} height=${BH} rx="10" />
      ${mass && html`<text class="sim-label r-ink in-block" x=${cx} y=${cy + 12} text-anchor="middle"
        data-source=${lb.block.source} style=${fitIn(mass, BW)}>${mass}</text>`}
    </g>`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
