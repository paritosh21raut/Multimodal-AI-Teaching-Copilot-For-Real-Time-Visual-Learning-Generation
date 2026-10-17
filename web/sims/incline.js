// Block on an inclined plane (simulation/templates/incline.py). The slope rises to the left; θ is at the bottom right.
// Along-slope sign convention from the server's drive: + = down the slope (dir, f_dir, F_dir). The geometry tweens when
// θ changes ("now tilt it to 45 degrees"), so the wedge turns smoothly and the motion keeps its clock.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, arrowScale, fitIn, shown } from "./draw.js";

export const TWEEN = ["theta_deg", "W", "N", "w_par", "w_perp", "F", "P", "f"];
const XR = 1056, BASE = 664, MAXW = 760, MAXH = 452, SIDE = 128, MARGIN = 34;
const ARROW = 200, LOWEST = 430;  // longest arrow; lowest centre of the block (W + its label stay on the stage)

// track coordinate u: metres from the top of the slope (+ down); at rest the block sits a little above the middle
export const motion = (d) => ({ a: d.a || 0, dir: d.dir || 0, L: d.track_m || 8, rest: 0.42 });

// S2 graph: the time of the run on the s-t / v-t curves (from rest at the start end: u = ½at²), null at rest
export function graphTime({ sim, u }) {
  const d = sim.drive;
  if (!d.dir || !(d.a > 1e-9)) return null;
  const start = d.dir > 0 ? 0 : d.track_m || 8;
  return Math.sqrt((2 * Math.abs(u - start)) / d.a);
}

export function scene({ sim, v, u }) {
  const th = (Math.max(0.5, Math.min(89, v.theta_deg)) * Math.PI) / 180;
  const c = Math.cos(th), s = Math.sin(th);
  const hyp = Math.min(MAXW / c, MAXH / s);
  // S2: every arrow and its label stay on the stage wherever the block is. The block's centre travels a window of the
  // slope: no higher than what points up from it needs (N, a push from up the slope, a pull or friction up it, each
  // + its label), no lower than LOWEST (W + its label). A window too short is kept short (a steep slope moves the
  // block less); a shallow slope, whose every point is low, is lifted (base, picture only)
  const len = arrowScale([v.W, v.N, v.F, v.P || 0, v.f, v.w_par, v.w_perp], ARROW);
  const dr = sim.drive;
  const up = (k) => s * (SIDE / 2 + 6 + k) + 56;
  const highest = Math.max(c * (SIDE / 2 + len(v.N)) + 60, dr.F_dir > 0 && v.F > 1e-6 ? up(len(v.F)) : 0,
    dr.P_dir < 0 && (v.P || 0) > 1e-6 ? up(len(v.P)) : 0, dr.f_dir < 0 ? up(len(v.f)) : 0);
  const full = Math.max(0, hyp - 2 * MARGIN - SIDE);
  const top0 = BASE - hyp * s;
  const yAt = (a) => top0 + s * a - c * (SIDE / 2);              // centre y at `a` along the slope (before a lift)
  const aOf = (y) => (y - top0 + c * (SIDE / 2)) / s;
  const a0 = Math.min(MARGIN + SIDE / 2 + full, Math.max(MARGIN + SIDE / 2, aOf(highest)));
  const room = Math.min(MARGIN + SIDE / 2 + full, aOf(LOWEST)) - a0;
  const travel = room >= 120 ? room : Math.min(full - (a0 - MARGIN - SIDE / 2), s < 0.5 ? 220 : 120);
  const base = BASE - Math.max(0, yAt(a0 + travel) - LOWEST);
  // a steep slope stands at the right edge: the normal force (pointing right) and its label need room there
  const cxEnd = XR - hyp * c + c * (a0 + travel) + s * (SIDE / 2);
  const xr = XR - Math.max(0, Math.min(cxEnd + s * (len(v.N) + 80) + 250 - 1064, XR - hyp * c - 40));
  const xL = xr - hyp * c, yTop = base - hyp * s;
  const d = [c, s];      // down the slope
  const n = [s, -c];     // out of the surface
  const L = sim.drive.track_m || 8;
  const along = a0 + (u / L) * Math.max(0, travel);             // the block's centre, from the top vertex
  const cx = xL + d[0] * along + n[0] * (SIDE / 2), cy = yTop + d[1] * along + n[1] * (SIDE / 2);
  const CENTRE = [cx, cy];
  const lb = sim.labels || {};
  const deg = (th * 180) / Math.PI;
  const out = [];
  if (shown(sim, "surface")) {
    out.push(html`<g key="surface" data-el="surface">
      <path class="sim-wedge" d=${`M${xL},${base} L${xr},${base} L${xL},${yTop} Z`} />
      <line class="sim-surface" x1=${xL} y1=${yTop} x2=${xr} y2=${base} />
      <line class="sim-surface base" x1=${Math.min(xL, 40)} y1=${base} x2="1080" y2=${base} />
    </g>`);
    if (lb.surface && lb.surface.text) {  // μ in the wedge's open corner (bottom left), away from the arrows
      out.push(html`<${Label} key="mu" x=${xL + 28} y=${base - 30} label=${lb.surface} id="surface" />`);
    }
  }
  if (shown(sim, "angle")) {
    const r = 118;
    const ax = xr - r, ay = base, bx = xr - r * c, by = base - r * s;
    out.push(html`<path key="arc" class="sim-angle" data-el="angle" d=${`M${ax},${ay} A${r},${r} 0 0,1 ${bx},${by}`} />`);
    const mid = th / 2, lr = r + 30;
    out.push(html`<${Label} key="al" x=${xr - lr * Math.cos(mid) - 8} y=${base - lr * Math.sin(mid) + 12}
      label=${lb.angle} anchor="end" fallback="θ" id="angle" />`);
  }
  // a ray from the centre leaves the (rotated) square after exit(dir); the block, drawn last, hides the inner part
  const exit = (dir) => (SIDE / 2) / Math.max(Math.abs(dir[0] * c + dir[1] * s), Math.abs(-dir[0] * s + dir[1] * c));
  const arrow = (key, from, dir, k, role, label, fallback, place, dashed) => {
    if (!k) return;
    if (from === CENTRE) k += exit(dir);
    const tip = [from[0] + dir[0] * k, from[1] + dir[1] * k];
    out.push(html`<${Arrow} key=${key} x1=${from[0]} y1=${from[1]} x2=${tip[0]} y2=${tip[1]} role=${role} dashed=${dashed} id=${key} />`);
    const [ox, oy, anchor] = place(tip);
    out.push(html`<${Label} key=${key + "l"} x=${ox} y=${oy} label=${label} role=${role} anchor=${anchor} fallback=${fallback} id=${key} />`);
  };
  if (shown(sim, "components")) {
    arrow("w_par", CENTRE, d, len(v.w_par), "component", lb.w_par, "mg sin θ", (p) => [p[0] + 16, p[1] + 44, "start"], true);
    arrow("w_perp", CENTRE, [-n[0], -n[1]], len(v.w_perp), "component", lb.w_perp, "mg cos θ", (p) => [p[0] - 14, p[1] + 40, "end"], true);
  }
  if (shown(sim, "weight")) arrow("weight", CENTRE, [0, 1], len(v.W), "weight", lb.weight, "W", (p) => [p[0] - 18, p[1] + 4, "end"]);
  if (shown(sim, "normal")) {
    arrow("normal", CENTRE, n, len(v.N), "normal", lb.normal, "N", (p) => [p[0] + 14, p[1] - 8, "start"]);
  }
  if (shown(sim, "friction") && v.f > 1e-6 && sim.drive.f_dir) {  // on the contact face, along the slope
    const fd = [d[0] * sim.drive.f_dir, d[1] * sim.drive.f_dir];
    const base = [cx - n[0] * (SIDE / 2 - 10), cy - n[1] * (SIDE / 2 - 10)];
    arrow("friction", [base[0] + fd[0] * (SIDE / 2), base[1] + fd[1] * (SIDE / 2)], fd, len(v.f), "friction", lb.friction, "f",
      (p) => [p[0] - n[0] * 46, p[1] - n[1] * 46 + 12, "end"]);  // into the wedge, under the slope (it falls to the right)
  }
  // S2 (user 2026-10-18): the push points ONTO the face it pushes; the pull starts on the face it pulls and points away.
  // A push up the slope and a pull down it both sit on the downhill face: then the push rides a little higher
  const pushOn = shown(sim, "applied") && v.F > 1e-6, pullOn = shown(sim, "pull") && (v.P || 0) > 1e-6;
  const shared = pushOn && pullOn && sim.drive.F_dir === -sim.drive.P_dir;
  const side = n[0] > 0.6 ? "start" : "middle";  // steep: the label beside the arrow, not across it
  if (pushOn) {
    const fd = [d[0] * sim.drive.F_dir, d[1] * sim.drive.F_dir], k = len(v.F), off = shared ? 30 : 0;
    const tip = [cx - fd[0] * (SIDE / 2 + 6) + n[0] * off, cy - fd[1] * (SIDE / 2 + 6) + n[1] * off];
    const tail = [tip[0] - fd[0] * k, tip[1] - fd[1] * k];
    out.push(html`<${Arrow} key="applied" x1=${tail[0]} y1=${tail[1]} x2=${tip[0]} y2=${tip[1]} role="applied" id="applied" />`);
    out.push(html`<${Label} key="appliedl" x=${(tail[0] + tip[0]) / 2 + n[0] * 64} y=${(tail[1] + tip[1]) / 2 + n[1] * 64 + 12}
      label=${lb.applied} role="applied" anchor=${side} fallback="F" id="applied" />`);
  }
  if (pullOn) {
    const pd = [d[0] * sim.drive.P_dir, d[1] * sim.drive.P_dir], k = len(v.P), off = shared ? -22 : 0;
    const tail = [cx + pd[0] * (SIDE / 2 + 6) + n[0] * off, cy + pd[1] * (SIDE / 2 + 6) + n[1] * off];
    const tip = [tail[0] + pd[0] * k, tail[1] + pd[1] * k];
    out.push(html`<${Arrow} key="pull" x1=${tail[0]} y1=${tail[1]} x2=${tip[0]} y2=${tip[1]} role="pull" id="pull" />`);
    out.push(html`<${Label} key="pulll" x=${(tail[0] + tip[0]) / 2 + n[0] * 64} y=${(tail[1] + tip[1]) / 2 + n[1] * 64 + 12}
      label=${lb.pull} role="pull" anchor=${side} fallback="F" id="pull" />`);
  }
  if (shown(sim, "block")) {
    const mass = lb.block && lb.block.text;
    out.push(html`<g key="block" data-el="block" transform=${`translate(${cx},${cy}) rotate(${deg})`}>
      <rect class="sim-block" x=${-SIDE / 2} y=${-SIDE / 2} width=${SIDE} height=${SIDE} rx="10" />
      ${mass && html`<text class="sim-label r-ink in-block" x="0" y="12" text-anchor="middle" data-source=${lb.block.source}
        style=${fitIn(mass, SIDE)}>${mass}</text>`}
    </g>`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
