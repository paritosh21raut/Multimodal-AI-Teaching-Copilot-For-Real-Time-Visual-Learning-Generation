// Chibi people (F-017 §2), ported from tools/stage/reference/people2.js `shaped(..., {head: 1.6, limb: 1.22, chibi: 1})`.
// pose(): the clip's joints in world metres (facing, rotation, the foot lock with leg IK, arm IK) and the sockets;
// draw(): the figure as prims in world units (B per metre, y down). Cast rows: config/stage_cast.json.
import { joints, lockAt } from './motion.js';
import { B, T, shade } from './style.js';
import { F, P, lerp, norm, smooth, taperD } from './svg.js';

export const CHIBI = { head: 1.6, limb: 1.22 };
// a child: a bigger head for the height than an adult, slimmer limbs (accuracy fix: the reference's 1.3 x 1.6 head
// looked like a bobble-head)
const CHILD = { head: 1.18, limb: 0.9 };
const SHOE = '#F4F1EA';

let CAST = {};
export const setCast = (rows) => { CAST = Object.fromEntries(rows.map((r) => [r.id, r])); };
export const castRow = (id) => CAST[id];
export const castIds = () => Object.keys(CAST);

// per-figure proportions (metres per metre of height); the socket `lap` and IK use the same widths the drawing does
export function build(L) {
  const child = !!L.child;
  return { hs: CHIBI.head * (child ? CHILD.head : 1), lw: CHIBI.limb * (L.build || 1) * (child ? CHILD.limb : 1) };
}
const thighHalf = (L, h) => 0.044 * build(L).lw * h;
export const handRadius = (L, h) => 0.036 * build(L).lw * h;

// two-bone IK: from the root s, segments l1, l2, the end at target; `bend` picks the joint side (-1 lower / +1 higher
// in y, or a vector to prefer)
export function ik2(s, target, l1, l2, prefer) {
  const dx = target[0] - s[0], dy = target[1] - s[1], d = Math.hypot(dx, dy) || 1e-9;
  const dm = Math.max(Math.abs(l1 - l2) * 1.001, Math.min(d, (l1 + l2) * 0.9999));
  const ux = dx / d, uy = dy / d, a = (l1 * l1 - l2 * l2 + dm * dm) / (2 * dm), hh = Math.sqrt(Math.max(0, l1 * l1 - a * a));
  const base = [s[0] + ux * a, s[1] + uy * a], e1 = [base[0] - uy * hh, base[1] + ux * hh], e2 = [base[0] + uy * hh, base[1] - ux * hh];
  const sc = (e) => (e[0] - base[0]) * prefer[0] + (e[1] - base[1]) * prefer[1];
  return [sc(e1) >= sc(e2) ? e1 : e2, [s[0] + ux * dm, s[1] + uy * dm]];
}

// fr: the sampled clip pose; at: {x, y, rot (deg), dir, h}; L: cast row; ik: {r: [x, y], l: [x, y]} world targets;
// lock: apply the clip's foot lock (the clip plays at its stride speed)
export function pose(fr, at, L, ik = {}, lock = false) {
  const JI = joints(), h = at.h, d = at.dir || 1, th = ((at.rot || 0) * Math.PI) / 180, c = Math.cos(th), s = Math.sin(th);
  const mir = fr.mirror ? -1 : 1;
  const local = fr.map((q) => [d * q[0] * h, q[1] * h]);
  const lk = lock ? lockAt(fr.clip, fr) : null;
  const W = (p) => [at.x + p[0] * c - p[1] * s, (at.y || 0) + p[0] * s + p[1] * c];
  const J = local.map(W);
  // foot lock: shift the foot, keep the hip, bend the knee to reach
  if (lk) for (const side of ['l', 'r']) {
    const dx = d * mir * lk[side] * h;
    if (Math.abs(dx) < 1e-6) continue;
    const hip = J[JI['thigh_' + side]], knee = J[JI['calf_' + side]], an = J[JI['foot_' + side]], ba = J[JI['ball_' + side]];
    const sh = [dx * c, dx * s], an2 = [an[0] + sh[0], an[1] + sh[1]];
    const [kn] = ik2(hip, an2, Math.hypot(knee[0] - hip[0], knee[1] - hip[1]), Math.hypot(an[0] - knee[0], an[1] - knee[1]),
      [knee[0] - (hip[0] + an[0]) / 2, knee[1] - (hip[1] + an[1]) / 2]);  // the knee stays on its side
    J[JI['calf_' + side]] = kn; J[JI['foot_' + side]] = an2; J[JI['ball_' + side]] = [ba[0] + sh[0], ba[1] + sh[1]];
  }
  const palm = (sd) => lerp(J[JI['hand_' + sd]], J[JI['middle_01_' + sd]], 0.5);
  const hands = { r: palm('r'), l: palm('l') };
  for (const sd of ['r', 'l']) {
    if (!ik[sd]) continue;
    const sh = J[JI['upperarm_' + sd]], el = J[JI['lowerarm_' + sd]], wr = J[JI['hand_' + sd]], pm = hands[sd];
    const l1 = Math.hypot(el[0] - sh[0], el[1] - sh[1]), l2 = Math.hypot(pm[0] - el[0], pm[1] - el[1]);
    const [el2, pm2] = ik2(sh, ik[sd], l1, l2, [s, -c]);  // the elbow bends down
    const u = norm([pm2[0] - el2[0], pm2[1] - el2[1]]), wl = Math.hypot(pm[0] - wr[0], pm[1] - wr[1]);
    J[JI['lowerarm_' + sd]] = el2; J[JI['hand_' + sd]] = [pm2[0] - u[0] * wl, pm2[1] - u[1] * wl];
    J[JI['middle_01_' + sd]] = [pm2[0] + u[0] * wl, pm2[1] + u[1] * wl];
    hands[sd] = pm2;
  }
  // sockets (world metres)
  const { hs, lw } = build(L), r = 0.07 * h * hs;
  const nk = J[JI.neck_01], hd = J[JI.Head], v = norm([hd[0] - nk[0], hd[1] - nk[1]]);
  const hc = [hd[0] + v[0] * r * 0.85, hd[1] + v[1] * r * 0.85];
  const side = (fr[JI.thigh_l][1] < fr[JI.thigh_r][1]) ? 'l' : 'r';
  // lap: the thighs' underside, halfway from hip to knee, in the figure's own frame (then placed like the joints)
  const lhip = local[JI['thigh_' + side]], lknee = local[JI['calf_' + side]];
  const lapLocal = [(lhip[0] + lknee[0]) / 2, Math.min(lhip[1], lknee[1]) - thighHalf(L, h)];
  const sp3 = local[JI.spine_03];
  const sockets = {
    hand_r: hands.r, hand_l: hands.l, hands: lerp(hands.r, hands.l, 0.5),
    head_top: [hc[0] + v[0] * r * 1.05, hc[1] + v[1] * r * 1.05],
    lap: W(lapLocal), back: W([sp3[0] - d * 0.085 * lw * h, sp3[1]]),
    feet: [at.x, at.y || 0],
  };
  return { J, h, d, rot: at.rot || 0, sockets, lapLocal, hc, r, ik, shadow: at.shadow !== false, groundY: at.groundY || 0 };
}

// the figure's box on screen-independent world metres (for label nudging)
export function bounds(ps) {
  let x0 = Infinity, x1 = -Infinity, y0 = Infinity, y1 = -Infinity;
  for (const p of ps.J) { x0 = Math.min(x0, p[0]); x1 = Math.max(x1, p[0]); y0 = Math.min(y0, p[1]); y1 = Math.max(y1, p[1]); }
  const r = ps.r * 1.2;
  return [Math.min(x0, ps.hc[0] - r), Math.min(y0, ps.hc[1] - r), Math.max(x1, ps.hc[0] + r), Math.max(y1, ps.hc[1] + r)];
}

// pose -> prims (world units: x * B, -y * B)
export function draw(ps, L) {
  const JI = joints(), h = ps.h, d = ps.d, fem = L.sex === 'f';
  const { hs, lw } = build(L);
  const W = (k) => k * h * B;
  const P_ = (j) => { const q = ps.J[JI[j]]; return [q[0] * B, -q[1] * B]; };
  const dk = (c, far) => (far ? shade(c, 0.82) : c);
  const out = [];
  const tp = (a, b, wa, wb, fill, ex) => out.push(['path', { d: taperD(a, b, wa, wb), fill, ...(ex || {}) }]);
  // head frame (screen-style coordinates, y down)
  const nk = P_('neck_01'), hd = P_('Head');
  let vx = hd[0] - nk[0], vy = hd[1] - nk[1]; const vl = Math.hypot(vx, vy) || 1; vx /= vl; vy /= vl;
  const fx = -vy * d, fy = vx * d, r = W(0.07) * hs, hc = [hd[0] + vx * r * 0.85, hd[1] + vy * r * 0.85];
  const at = (u, v) => [hc[0] + fx * u * r + vx * v * r, hc[1] + fy * u * r + vy * v * r];
  const ring = (a0, a1, rad, step = 12) => { const o = []; for (let a = a0; a <= a1 + 0.01; a += step) o.push(at(Math.cos(a * Math.PI / 180) * rad, Math.sin(a * Math.PI / 180) * rad)); return o; };

  // contact shadow
  if (ps.shadow) {
    const gx = (P_('ball_l')[0] + P_('ball_r')[0]) / 2, gy = -ps.groundY * B;
    const lift = Math.max(0, gy - Math.max(P_('ball_l')[1], P_('ball_r')[1]) - W(0.03));  // y down: feet above the ground
    const k = Math.max(0.35, 1 - lift / (2.4 * B));
    out.push(P.ellipse([gx, gy], W(0.17) * k, W(0.028) * k, `rgba(40,50,40,${F(0.18 * k)})`));
  }
  const arm = (s, far) => {
    const sh = P_('upperarm' + s), el = P_('lowerarm' + s), wr = P_('hand' + s), pm = lerp(wr, P_('middle_01' + s), 0.5);
    const fore = L.sleeve === 'long' ? L.top : L.skin;
    tp(sh, el, W(0.058) * lw, W(0.046) * lw, dk(L.sleeve === 'long' ? L.top : L.skin, far));
    if (L.sleeve !== 'long') tp(sh, lerp(sh, el, 0.5), W(0.068) * lw, W(0.062) * lw, dk(L.top, far));
    tp(el, wr, W(0.046) * lw, W(0.036) * lw, dk(fore, far));
    const ang = Math.atan2(wr[1] - el[1], wr[0] - el[0]) * 180 / Math.PI, hr = W(0.036) * lw;
    if (L.sleeve === 'long') out.push(P.ellipse(wr, W(0.03) * lw, W(0.026) * lw, dk(shade(L.top, 0.85), far), ang));
    const ar = ang * Math.PI / 180;
    out.push(P.circle(pm, hr, dk(L.skin, far)),  // the hand, centred on the palm (socket hand_r / hand_l)
      P.circle([pm[0] - Math.sin(ar) * hr * 0.75 * d, pm[1] + Math.cos(ar) * hr * 0.75 * d], hr * 0.42, dk(shade(L.skin, 0.94), far)));
  };
  const leg = (s, far) => {
    const th = P_('thigh' + s), kn = P_('calf' + s), an = P_('foot' + s), ba = P_('ball' + s);
    const pantsLeg = L.bottom_type === 'pants', thighC = L.bottom_type === 'skirt' ? L.skin : L.bottom;
    tp(th, kn, W(0.088) * lw, W(0.064) * lw, dk(L.bottom_type === 'shorts' ? L.skin : thighC, far));
    if (L.bottom_type === 'shorts') tp(th, lerp(th, kn, 0.6), W(0.096) * lw, W(0.084) * lw, dk(L.bottom, far));
    tp(kn, an, W(0.064) * lw, W(0.048) * lw, dk(pantsLeg ? L.bottom : L.skin, far));
    // shoes: slimmer than the reference (accuracy fix), a white sole
    const u = norm([ba[0] - an[0], ba[1] - an[1]]), heel = [an[0] - u[0] * W(0.012), an[1] - u[1] * W(0.012) + W(0.02)];
    const toe = [ba[0] + u[0] * W(0.02), ba[1] + u[1] * W(0.02)], nn = [-u[1], u[0]], dn = nn[1] > 0 ? 1 : -1, so = W(0.016);
    tp([heel[0] + nn[0] * so * dn, heel[1] + nn[1] * so * dn], [toe[0] + nn[0] * so * dn, toe[1] + nn[1] * so * dn], W(0.022), W(0.018), dk(SHOE, far));
    tp(heel, toe, W(0.04), W(0.034), dk(L.shoes, far));
    out.push(P.circle(an, W(0.024), dk(L.shoes, far)));
  };
  // torso: the spine offset to the front / back by half-depths
  const pel = P_('pelvis'), sp2 = P_('spine_02'), sp3 = P_('spine_03'), nb = lerp(sp3, nk, 0.75);
  const prof = fem ? [[0.07, 0.075], [0.066, 0.062], [0.09, 0.068], [0.03, 0.032]] : [[0.072, 0.07], [0.076, 0.066], [0.088, 0.076], [0.034, 0.036]];
  const S = [lerp(pel, sp2, -0.25), sp2, sp3, nb];
  const off = (i) => { const a = S[Math.max(0, i - 1)], b = S[Math.min(3, i + 1)], t = norm([b[0] - a[0], b[1] - a[1]]); return [-t[1] * d, t[0] * d]; };
  const front = S.map((q, i) => { const n = off(i); return [q[0] + n[0] * W(prof[i][0]) * lw, q[1] + n[1] * W(prof[i][0]) * lw]; });
  const back = S.map((q, i) => { const n = off(i); return [q[0] - n[0] * W(prof[i][1]) * lw, q[1] - n[1] * W(prof[i][1]) * lw]; });
  const fb = lerp(front[0], front[1], 0.42), bb = lerp(back[0], back[1], 0.42);

  arm('_l', true);
  leg('_l', true);
  if (L.hair_style === 'long') out.push(P.path(smooth([at(-0.3, 0.9), at(-1.05, 0.2), at(-1.1, -1.0), at(-0.75, -2.0), at(-0.1, -1.7), at(0.0, -0.4)]), L.hair));
  if (L.hair_style === 'ponytail') out.push(P.path(smooth([at(-0.8, 0.55), at(-1.45, 0.1), at(-1.55, -0.9), at(-1.2, -1.15), at(-1.05, -0.2)]), L.hair));
  leg('_r', false);
  out.push(P.path(`M${F(fb[0])},${F(fb[1])}L${F(front[0][0])},${F(front[0][1])}L${F(back[0][0])},${F(back[0][1])}L${F(bb[0])},${F(bb[1])}Z`, L.bottom));
  out.push(P.path(smooth([fb, front[1], front[2], front[3], back[3], back[2], back[1], bb]), L.top));
  const mid = [1, 2, 3].map((i) => lerp(front[i], back[i], 0.6));
  out.push(P.path(smooth([lerp(fb, bb, 0.6), ...mid, back[3], back[2], back[1], bb]), shade(L.top, 0.9)));
  out.push(P.path(smooth([lerp(front[3], back[3], 0.15), lerp(front[3], back[3], 0.75), lerp(lerp(front[2], back[2], 0.4), front[3], 0.72), lerp(lerp(front[2], back[2], 0.15), front[3], 0.62)]), shade(L.top, 1.18)));
  if (L.bottom_type !== 'skirt') out.push(P.line(lerp(fb, bb, 0.04), lerp(fb, bb, 0.96), W(0.022), shade(L.bottom, 0.75)));
  if (L.bottom_type === 'skirt') {
    const cl = P_('calf_l'), cr = P_('calf_r'), xs = [cl[0], cr[0], P_('thigh_l')[0], P_('thigh_r')[0]];
    const ky = Math.max(cl[1], cr[1]) - W(0.03), fx2 = d > 0 ? Math.max(...xs) + W(0.06) : Math.min(...xs) - W(0.06), bx2 = d > 0 ? Math.min(...xs) - W(0.07) : Math.max(...xs) + W(0.07);
    out.push(P.path(smooth([fb, [fx2, ky], [bx2, ky], bb]), L.bottom));
  }
  // neck, head, ear
  tp(nb, at(-0.15, -0.75), W(0.05), W(0.05), shade(L.skin, 0.93));
  out.push(P.path(smooth([...ring(-60, 200, 1.0, 20), at(-0.55, -0.92), at(0.1, -1.12), at(0.62, -0.95)]), L.skin));
  out.push(P.circle(at(0.98, -0.12), r * 0.17, L.skin));
  // hair
  const cap = (a0, a1, rad) => ring(a0, a1, rad, 10);
  const hs_ = L.hair_style;
  if (hs_ === 'short') out.push(P.path(smooth([...cap(55, 215, 1.08), at(-0.55, -0.05), at(0.1, 0.62), at(0.7, 0.6)]), L.hair));
  else if (hs_ === 'long') out.push(P.path(smooth([...cap(50, 225, 1.1), at(-0.5, -0.2), at(0.0, 0.55), at(0.72, 0.62)]), L.hair));
  else if (hs_ === 'bun') out.push(P.path(smooth([...cap(55, 215, 1.07), at(-0.5, -0.05), at(0.15, 0.6), at(0.7, 0.58)]), L.hair), P.circle(at(-0.78, 0.82), r * 0.42, L.hair));
  else if (hs_ === 'ponytail') out.push(P.path(smooth([...cap(55, 215, 1.08), at(-0.55, -0.05), at(0.1, 0.62), at(0.7, 0.6)]), L.hair), P.circle(at(-0.88, 0.5), r * 0.22, shade(L.hair, 1.3)));
  else if (hs_ === 'curly') { for (let a = 40; a <= 230; a += 24) out.push(P.circle(at(Math.cos(a * Math.PI / 180) * 0.98, Math.sin(a * Math.PI / 180) * 0.98), r * 0.36, L.hair)); out.push(P.path(smooth([...cap(60, 210, 0.95), at(-0.4, 0.0), at(0.2, 0.55)]), L.hair)); }
  else if (hs_ === 'bald') out.push(P.path(smooth([...cap(150, 215, 1.04), at(-0.55, -0.1), at(-0.75, 0.25)]), L.hair));
  if (hs_ !== 'bald' && hs_ !== 'curly') out.push(P.path(smooth([...ring(85, 140, 0.88, 6), ...ring(85, 140, 0.76, 6).reverse()]), shade(L.hair, 1.6), { opacity: '0.45' }));
  // face
  if (L.beard) out.push(P.path(smooth([at(0.78, -0.3), at(0.72, -0.82), at(0.25, -1.16), at(-0.3, -0.88), at(-0.25, -0.3), at(0.2, -0.5)]), L.hair));
  out.push(P.circle(at(-0.12, -0.08), r * 0.2, shade(L.skin, 0.9)), P.circle(at(-0.1, -0.08), r * 0.1, shade(L.skin, 0.8)),
    P.ellipse(at(0.48, 0.02), r * 0.16, r * 0.21, '#ffffff'), P.ellipse(at(0.54, 0.0), r * 0.12, r * 0.17, '#3a2a22'),
    P.ellipse(at(0.56, -0.02), r * 0.07, r * 0.1, '#120d0b'), P.circle(at(0.6, 0.08), r * 0.045, '#ffffff'), P.circle(at(0.5, -0.09), r * 0.022, '#ffffff'),
    P.ellipse(at(0.4, -0.36), r * 0.15, r * 0.09, '#F07A7A', 0, { opacity: '0.4' }), P.circle(at(0.97, -0.16), r * 0.1, shade(L.skin, 0.95)));
  const bw = at(0.3, 0.36), bm = at(0.5, 0.44), be = at(0.72, 0.36);
  out.push(P.path(`M${F(bw[0])},${F(bw[1])} Q${F(bm[0])},${F(bm[1])} ${F(be[0])},${F(be[1])}`, 'none',
    { stroke: hs_ === 'bald' && !L.beard ? shade(L.skin, 0.55) : L.hair, 'stroke-width': F(r * 0.075), 'stroke-linecap': 'round' }));
  if (!L.beard) { const m0 = at(0.55, -0.48), m1 = at(0.7, -0.66), m2 = at(0.86, -0.46); out.push(P.path(`M${F(m0[0])},${F(m0[1])} Q${F(m1[0])},${F(m1[1])} ${F(m2[0])},${F(m2[1])} Z`, '#B8524A')); }
  if (L.glasses) {
    const g = at(0.55, 0.1), a = at(0.3, 0.12), b = at(-0.12, 0.12);
    out.push(P.circle(g, r * 0.25, 'rgba(255,255,255,0.25)', { stroke: '#2b2522', 'stroke-width': F(r * 0.06) }), P.line(a, b, r * 0.06, '#2b2522'));
  }
  arm('_r', false);
  return out;
}

export const defaultHeight = (L) => L.height_m || (L.child ? 1.25 : L.sex === 'f' ? 1.66 : 1.78);
export const ink = T.ink;
