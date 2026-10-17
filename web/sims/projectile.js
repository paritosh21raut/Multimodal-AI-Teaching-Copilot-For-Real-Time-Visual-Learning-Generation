// Projectile motion (simulation/templates/projectile.py): x = uₓ t, y = h + u_y t − ½ g t², closed form from the
// server's drive. The whole flight fits the stage (one scale for x and y, so the parabola keeps its true shape) and
// lasts 1.5 to 4 stage seconds (a 40 s flight is shown faster, a 0.3 s one slower; nothing here is printed). The
// ball holds where it lands, then flies again. A change of u, θ, h or g starts a new flight (Template.restart_on).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, clamp, shown } from "./draw.js";

export const TWEEN = [];
const GROUND = 590, X0 = 150, WIDE = 860, TALL = 330, BALL = 18, HOLD = 1.0, ARROW = 190;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

// the flight time at the clock's t: each flight is shown in 1.5 - 4 stage seconds, then held, then again
function flightAt(d, t) {
  const tf = d.tf || 0;
  const pace = tf > 0 ? clamp(tf, 1.5, 4) / tf : 1;  // stage seconds per flight second
  const cycle = tf + HOLD / pace;
  return tf > 0 ? Math.min(tf, (t / pace) % cycle) : 0;
}
export const graphTime = ({ sim, t }) => (sim.drive.tf > 0 ? flightAt(sim.drive, t) : null);  // S2 graph

export function scene({ sim, t }) {
  const d = sim.drive;
  const { ux = 0, uy = 0, h = 0, g = 9.81, tf = 0, R = 0, H = 0 } = d;
  const k = Math.min(WIDE / Math.max(R, 1e-6), TALL / Math.max(H, 1e-6));  // stage px per metre
  const X = (x) => X0 + x * k, Y = (y) => GROUND - y * k;
  const tau = flightAt(d, t);
  const bx = X(ux * tau), by = Y(h + uy * tau - 0.5 * g * tau * tau);
  const lb = sim.labels || {};
  const out = [];
  if (shown(sim, "ground")) {
    out.push(html`<g key="ground" data-el="ground">
      <rect class="sim-ground" x="40" y=${GROUND} width="1020" height="60" />
      <line class="sim-surface" x1="40" y1=${GROUND} x2="1060" y2=${GROUND} />
      ${h > 0 && html`<rect class="sim-wedge" x=${X0 - 110} y=${Y(h)} width="110" height=${GROUND - Y(h)} />`}
    </g>`);
    if (h > 0) out.push(html`<${Label} key="hl" x=${X0 - 124} y=${(Y(h) + GROUND) / 2 + 12} label=${lb.height} anchor="end"
      fallback="h" id="ground" />`);
  }
  if (shown(sim, "path") && tf > 0) {  // the whole parabola, dashed
    const pts = [];
    for (let i = 0; i <= 64; i++) {
      const s = (tf * i) / 64;
      pts.push(`${X(ux * s).toFixed(1)},${Y(h + uy * s - 0.5 * g * s * s).toFixed(1)}`);
    }
    out.push(html`<polyline key="path" class="sim-guide" data-el="path" fill="none" points=${pts.join(" ")} />`);
  }
  const th = Math.atan2(uy, ux), sx = X(0), sy = Y(h);
  // one scale for every velocity arrow: the fastest (landing) speed is ARROW long, u and its components to match
  const vs = ARROW / Math.max(1e-9, d.v_max || Math.hypot(ux, uy)), U = Math.hypot(ux, uy) * vs;
  if (shown(sim, "peak") && uy > 0 && tf > 0) {  // H: from the ground up to the top of the path
    const tp = uy / g, px = X(ux * tp);
    out.push(html`<g key="peak" data-el="peak"><line class="sim-guide" x1=${px} y1=${GROUND} x2=${px} y2=${Y(H)} /></g>`);
    out.push(html`<${Label} key="pl" x=${px + 18} y=${(GROUND + Y(H)) / 2 + 12} label=${lb.peak} fallback="H" id="peak" />`);
  }
  if (shown(sim, "range") && R > 1e-6) {  // R: along the ground, launch point to landing point
    out.push(html`<g key="range" data-el="range">
      <line class="sim-angle" x1=${sx} y1=${GROUND + 34} x2=${X(R)} y2=${GROUND + 34} />
      <line class="sim-angle" x1=${sx} y1=${GROUND + 22} x2=${sx} y2=${GROUND + 46} />
      <line class="sim-angle" x1=${X(R)} y1=${GROUND + 22} x2=${X(R)} y2=${GROUND + 46} />
    </g>`);
    out.push(html`<${Label} key="rl" x=${(sx + X(R)) / 2} y=${GROUND + 88} label=${lb.range} anchor="middle" fallback="R" id="range" />`);
  }
  if (shown(sim, "launch")) {  // u at the launch point, θ from the horizontal
    const ex = sx + U * Math.cos(th), ey = sy - U * Math.sin(th);
    out.push(html`<${Arrow} key="u" x1=${sx} y1=${sy} x2=${ex} y2=${ey} role="applied" id="launch" />`);
    const under = th > 0.05 && th < 1.2;  // angled: under the tip, where the path is not (it curves above it)
    out.push(html`<${Label} key="ul" x=${ex + 14} y=${under ? ey + 40 : ey - 8} label=${lb.speed} role="applied" fallback="u" id="launch" />`);
    if (th > 0.01) {
      const r = 84;
      out.push(html`<g key="ang" data-el="launch">
        <line class="sim-guide" x1=${sx} y1=${sy} x2=${sx + r + 40} y2=${sy} />
        <path class="sim-angle" d=${`M ${sx + r} ${sy} A ${r} ${r} 0 0 0 ${sx + r * Math.cos(th)} ${sy - r * Math.sin(th)}`} />
      </g>`);
      out.push(html`<${Label} key="al" x=${sx + (r + 16) * Math.cos(th / 2)} y=${sy - (r + 16) * Math.sin(th / 2) + 12}
        label=${lb.angle} fallback="θ" id="launch" />`);
    }
  }
  if (shown(sim, "components")) {  // u cos θ along the ground, u sin θ up, from the launch point
    const n = U;  // the components close the rectangle of u
    if (Math.cos(th) > 0.02) {
      out.push(html`<${Arrow} key="cx" x1=${sx} y1=${sy} x2=${sx + n * Math.cos(th)} y2=${sy} role="component" dashed id="components" />`);
      out.push(html`<${Label} key="cxl" x=${sx + n * Math.cos(th)} y=${sy + 46} label=${lb.ux} role="component" anchor="middle" id="components" />`);
    }
    if (Math.sin(th) > 0.02) {
      out.push(html`<${Arrow} key="cy" x1=${sx} y1=${sy} x2=${sx} y2=${sy - n * Math.sin(th)} role="component" dashed id="components" />`);
      out.push(html`<${Label} key="cyl" x=${sx - 16} y=${sy - n * Math.sin(th) + 8} label=${lb.uy} role="component" anchor="end" id="components" />`);
    }
  }
  if (shown(sim, "velocity") && tf > 0 && tau < tf) {  // the velocity now: uₓ stays, v_y = u_y − g t
    const vx = ux, vy = uy - g * tau;
    out.push(html`<${Arrow} key="v" x1=${bx} y1=${by} x2=${bx + vx * vs} y2=${by - vy * vs} role="component" dashed id="velocity" />`);
  }
  if (shown(sim, "ball")) out.push(html`<circle key="ball" class="sim-bob" data-el="ball" cx=${bx} cy=${by} r=${BALL} />`);
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
