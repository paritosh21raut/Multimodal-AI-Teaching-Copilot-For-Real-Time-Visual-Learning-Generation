// Procedural 2D animals (F-017 §2), ported from tools/stage/reference/people2.js: dog, cat, horse, cow, bird, fish.
// The gait is synced to the distance walked (no sliding feet); dog and cat can sit. Prims in world units (B per m).
import { B, shade } from './style.js';
import { F, P, smooth, taperD } from './svg.js';

export const SPECIES = {
  dog:   { L: 0.62, H: 0.24, hip: 0.44, head: 0.12, neck: 0.16, nAng: 50, tail: 0.24, tailUp: 0.8, color: '#C98B4F', belly: '#EBC79B', ear: 'flop', snout: 0.11, stride: 0.55 },
  cat:   { L: 0.42, H: 0.16, hip: 0.27, head: 0.09, neck: 0.07, nAng: 55, tail: 0.34, tailUp: 1.4, color: '#E39B4B', belly: '#F6D2A2', ear: 'point', snout: 0.03, stride: 0.35, stripes: true },
  horse: { L: 1.3, H: 0.62, hip: 1.25, head: 0.2, neck: 0.62, nAng: 58, tail: 0.55, tailUp: -0.3, color: '#8B5A3C', belly: '#A6714E', mane: '#3B2A20', ear: 'point', snout: 0.26, stride: 1.4 },
  cow:   { L: 1.45, H: 0.72, hip: 1.12, head: 0.2, neck: 0.3, nAng: 25, tail: 0.6, tailUp: -0.6, color: '#F5F1EA', spots: '#2E2B29', belly: '#F5F1EA', ear: 'side', horn: true, snout: 0.16, stride: 0.9 },
  bird:  { color: '#3A86FF' },
  fish:  { color: '#F28C28' },
};

// a: {kind, x, y, t, dir, speed (m/s, 0 stands), dist (m walked), pose: walk|stand|sit|fly|swim, scale}
export function draw(a) {
  const d = a.dir || 1, k = a.scale || 1;
  const X = (u) => (a.x + d * u * k) * B, Y = (v) => -((a.y || 0) + v * k) * B, S = (m) => m * k * B;
  const pr = [];
  const tp = (p, q, wa, wb, fill) => pr.push(['path', { d: taperD(p, q, wa, wb), fill }]);
  if (a.kind === 'bird') {
    const fl = Math.sin((a.t || 0) * 14) * (a.pose === 'fly' ? 1 : 0), c = [X(0), Y(0)], col = a.color || SPECIES.bird.color;
    const wing = [[X(-0.02), Y(0.03)], [X(-0.12), Y(0.03 + 0.18 * fl)], [X(0.08), Y(0.03)]];
    pr.push(P.ellipse(c, S(0.12), S(0.06), col), P.circle([X(0.11), Y(0.045)], S(0.05), col),
      P.path(`M${F(X(0.155))},${F(Y(0.05))}L${F(X(0.21))},${F(Y(0.035))}L${F(X(0.155))},${F(Y(0.025))}Z`, '#F2A541'),
      P.path(`M${F(X(-0.1))},${F(Y(0.0))}L${F(X(-0.22))},${F(Y(0.05))}L${F(X(-0.2))},${F(Y(-0.04))}Z`, shade(col, 0.8)),
      P.path(`M${F(wing[0][0])},${F(wing[0][1])}L${F(wing[1][0])},${F(wing[1][1])}L${F(wing[2][0])},${F(wing[2][1])}Z`, shade(col, 0.75)),
      P.circle([X(0.125), Y(0.06)], S(0.012), '#1b1b1b'));
    if (a.pose !== 'fly') pr.push(P.line([X(0), Y(-0.05)], [X(0), Y(-0.12)], S(0.01), '#F2A541'));
    return pr;
  }
  if (a.kind === 'fish') {
    const wag = Math.sin((a.t || 0) * 7) * 0.5, col = a.color || SPECIES.fish.color;
    const tt = [X(-0.17), Y(0)], tb = [X(-0.3), Y(0.08 + wag * 0.05)], tc = [X(-0.3), Y(-0.08 + wag * 0.05)];
    pr.push(P.path(`M${F(tt[0])},${F(tt[1])}L${F(tb[0])},${F(tb[1])}L${F(tc[0])},${F(tc[1])}Z`, shade(col, 0.85)),
      P.ellipse([X(0), Y(0)], S(0.2), S(0.09), col),
      P.path(`M${F(X(-0.02))},${F(Y(0.08))}L${F(X(0.05))},${F(Y(0.15))}L${F(X(0.09))},${F(Y(0.07))}Z`, shade(col, 0.85)),
      P.circle([X(0.12), Y(0.025)], S(0.018), '#1b1b1b'));
    return pr;
  }
  const sp = SPECIES[a.kind], t = a.t || 0, dist = a.dist != null ? a.dist : (a.speed || 0) * t;
  const shadow = (rx) => P.ellipse([X(0), -(a.y || 0) * B], S(rx), S(0.035), 'rgba(40,50,40,0.16)');
  if (a.pose === 'sit' && (a.kind === 'dog' || a.kind === 'cat')) {  // haunch down, chest up, front legs straight
    const Lb = sp.L, hp = sp.hip, Q = (u, v) => [X(u * Lb), Y(v * hp)], col = sp.color, hr = S(sp.head) * 1.1;
    pr.push(shadow(Lb * 0.5));
    const t0 = Q(-0.45, 0.08), t1 = Q(-0.2, -0.05), t2 = Q(0.35, 0.05);
    pr.push(P.path(`M${F(t0[0])},${F(t0[1])} Q${F(t1[0])},${F(t1[1])} ${F(t2[0])},${F(t2[1])}`, 'none', { stroke: shade(col, 0.85), 'stroke-width': F(S(0.035)), 'stroke-linecap': 'round' }));
    tp(Q(0.2, 1.0), Q(0.22, 0.04), S(0.05), S(0.035), shade(col, 0.82));
    pr.push(P.ellipse(Q(-0.18, 0.42), S(Lb * 0.3), S(hp * 0.42), col));
    pr.push(P.path(smooth([Q(-0.42, 0.25), Q(-0.38, 0.85), Q(-0.05, 1.35), Q(0.25, 1.45), Q(0.32, 1.0), Q(0.2, 0.35), Q(-0.05, 0.08)]), col));
    pr.push(P.path(smooth([Q(0.08, 1.25), Q(0.27, 1.3), Q(0.25, 0.7), Q(0.12, 0.6)]), sp.belly));
    if (sp.stripes) [0.6, 0.85, 1.1].forEach((v) => pr.push(P.line(Q(-0.35, v), Q(-0.15, v + 0.05), S(0.022), shade(col, 0.8))));
    tp(Q(0.25, 1.0), Q(0.28, 0.04), S(0.055), S(0.04), col);
    pr.push(P.ellipse(Q(0.3, 0.03), S(0.04), S(0.022), shade(col, 0.75)), P.ellipse(Q(-0.02, 0.04), S(0.06), S(0.03), shade(col, 0.85)));
    const hc = [X(0.2 * Lb), Y(1.45 * hp) - hr * 0.9];
    if (sp.ear === 'point') for (const e of [-0.45, 0.35]) pr.push(P.path(`M${F(hc[0] + d * hr * (e - 0.25))},${F(hc[1] - hr * 0.6)}L${F(hc[0] + d * hr * e)},${F(hc[1] - hr * 1.55)}L${F(hc[0] + d * hr * (e + 0.35))},${F(hc[1] - hr * 0.75)}Z`, shade(col, 0.9)));
    pr.push(P.circle(hc, hr, col), P.ellipse([hc[0] + d * hr * 0.75, hc[1] + hr * 0.3], hr * 0.45, hr * 0.35, sp.belly));
    if (sp.ear === 'flop') pr.push(P.ellipse([hc[0] - d * hr * 0.55, hc[1] + hr * 0.1], hr * 0.32, hr * 0.75, shade(col, 0.7), d * 15));
    pr.push(P.circle([hc[0] + d * hr * 0.4, hc[1] - hr * 0.12], hr * 0.14, '#1b1b1b'), P.circle([hc[0] + d * hr * 1.12, hc[1] + hr * 0.2], hr * 0.12, '#2b2522'));
    return pr;
  }
  const moving = (a.speed || 0) > 0.01;
  const phi = 2 * Math.PI * dist / sp.stride, amp = moving ? 0.42 : 0;
  const legTop = sp.hip - sp.H * 0.3, l1 = legTop * 0.52, l2 = legTop * 0.5;
  const legs = [['bl', -0.36, 0, true], ['fl', 0.36, 0.5, true], ['br', -0.36, 1.0, false], ['fr', 0.36, 1.5, false]];
  const foot = (xo, ph, front) => {
    const th1 = amp * Math.sin(phi + ph * Math.PI), lift = Math.max(0, Math.cos(phi + ph * Math.PI)) * (moving ? 0.7 : 0);
    const th2 = front ? th1 - lift : th1 + lift * 0.8;
    const hipP = [xo * sp.L, legTop], kn = [hipP[0] + Math.sin(th1) * l1, hipP[1] - Math.cos(th1) * l1];
    return [hipP, kn, [kn[0] + Math.sin(th2) * l2, kn[1] - Math.cos(th2) * l2]];
  };
  const chains = legs.map(([n, xo, ph]) => foot(xo, ph, n[0] === 'f'));
  const bob = -Math.min(...chains.map((c) => c[2][1])) + (moving ? 0.012 * Math.abs(Math.sin(2 * phi)) : 0);
  const PT = (u, v) => [X(u), Y(v + bob)];
  const col = sp.color, far = shade(col, 0.82), lw = S(sp.L * 0.12);
  const hoof = a.kind === 'horse' || a.kind === 'cow';
  const legPrims = (c, cc) => {
    const a0 = PT(...c[0]), a1 = PT(...c[1]), a2 = PT(...c[2]), o = [];
    o.push(['path', { d: taperD(a0, a1, lw * 1.6, lw * 0.85), fill: cc }], ['path', { d: taperD(a1, a2, lw * 0.85, lw * 0.62), fill: cc }]);
    o.push(P.ellipse([a2[0] + d * lw * 0.12, a2[1] - lw * 0.1], lw * 0.48, lw * 0.36, hoof ? '#3A2E28' : shade(cc, 0.75)));
    return o;
  };
  pr.push(shadow(sp.L * 0.6));
  const tb = PT(-0.5 * sp.L, sp.hip - sp.H * 0.05), wag = Math.sin(t * 6) * 0.15;
  const tm = PT(-0.5 * sp.L - sp.tail * 0.5, sp.hip + sp.tail * 0.5 * sp.tailUp * 0.6 + wag * sp.tail), te = PT(-0.5 * sp.L - sp.tail * 0.75, sp.hip + sp.tail * sp.tailUp * 0.6 + wag * sp.tail * 2);
  pr.push(P.path(`M${F(tb[0])},${F(tb[1])} Q${F(tm[0])},${F(tm[1])} ${F(te[0])},${F(te[1])}`, 'none', { stroke: sp.mane || shade(col, 0.85), 'stroke-width': F(lw * (a.kind === 'horse' ? 1.3 : 0.7)), 'stroke-linecap': 'round' }));
  chains.forEach((c, i) => { if (legs[i][3]) pr.push(...legPrims(c, far)); });
  pr.push(P.path(smooth([PT(-0.5 * sp.L, sp.hip + sp.H * 0.4), PT(0, sp.hip + sp.H * 0.45), PT(0.5 * sp.L, sp.hip + sp.H * 0.5), PT(0.56 * sp.L, sp.hip),
    PT(0.45 * sp.L, sp.hip - sp.H * 0.45), PT(0, sp.hip - sp.H * 0.55), PT(-0.5 * sp.L, sp.hip - sp.H * 0.4), PT(-0.57 * sp.L, sp.hip)]), col));
  pr.push(P.path(smooth([PT(-0.35 * sp.L, sp.hip - sp.H * 0.2), PT(0.35 * sp.L, sp.hip - sp.H * 0.25), PT(0.3 * sp.L, sp.hip - sp.H * 0.5), PT(-0.3 * sp.L, sp.hip - sp.H * 0.45)]), sp.belly));
  if (sp.spots) [[-0.25, 0.15, 0.16], [0.15, 0.25, 0.12], [0.05, -0.1, 0.1], [-0.4, -0.05, 0.08]].forEach(([u, v, rr]) => pr.push(P.circle(PT(u * sp.L, sp.hip + v * sp.H), S(rr * sp.L * 0.6), sp.spots)));
  if (sp.stripes) [-0.25, -0.1, 0.05].forEach((u) => pr.push(P.line(PT(u * sp.L, sp.hip + sp.H * 0.45), PT(u * sp.L - 0.02, sp.hip + sp.H * 0.1), S(0.025), shade(col, 0.8))));
  const na = sp.nAng * Math.PI / 180, nb0 = [0.42 * sp.L, sp.hip + sp.H * 0.2], hcU = nb0[0] + Math.cos(na) * sp.neck, hcV = nb0[1] + Math.sin(na) * sp.neck;
  tp(PT(nb0[0], nb0[1]), PT(hcU, hcV), S(sp.H * 0.75), S(sp.head * 1.3), col);
  if (sp.mane) tp(PT(nb0[0] - 0.08, nb0[1] + sp.H * 0.4), PT(hcU - 0.06, hcV + sp.head * 0.6), S(0.08), S(0.06), sp.mane);
  const hc = PT(hcU, hcV), hr = S(sp.head);
  pr.push(P.circle(hc, hr, col));
  const sn = PT(hcU + sp.snout + sp.head * 0.4, hcV - sp.head * 0.35);
  tp(hc, sn, hr * 1.4, hr * 0.85, col);
  pr.push(P.circle([sn[0] + d * hr * 0.3, sn[1] - hr * 0.05], hr * 0.18, '#2b2522'));
  const tri = (p, q, r, fill) => pr.push(P.path(`M${F(p[0])},${F(p[1])}L${F(q[0])},${F(q[1])}L${F(r[0])},${F(r[1])}Z`, fill));
  if (sp.ear === 'point') tri(PT(hcU - 0.02, hcV + sp.head * 0.6), PT(hcU - 0.05, hcV + sp.head * 1.6), PT(hcU + 0.05, hcV + sp.head * 0.8), shade(col, 0.85));
  if (sp.ear === 'flop') pr.push(P.ellipse(PT(hcU - sp.head * 0.45, hcV - sp.head * 0.1), hr * 0.35, hr * 0.8, shade(col, 0.7), d * 15));
  if (sp.ear === 'side') pr.push(P.ellipse(PT(hcU - sp.head * 0.6, hcV + sp.head * 0.5), hr * 0.55, hr * 0.25, shade(col, 0.9), -d * 20));
  if (sp.horn) { const h0 = PT(hcU - 0.02, hcV + sp.head * 0.8), h1 = PT(hcU - 0.05, hcV + sp.head * 1.6), h2 = PT(hcU + 0.08, hcV + sp.head * 1.5), h3 = PT(hcU + 0.04, hcV + sp.head * 0.85);
    pr.push(P.path(`M${F(h0[0])},${F(h0[1])}Q${F(h1[0])},${F(h1[1])} ${F(h2[0])},${F(h2[1])}L${F(h3[0])},${F(h3[1])}Z`, '#E9DCC0')); }
  chains.forEach((c, i) => { if (!legs[i][3]) pr.push(...legPrims(c, col)); });
  const eye = PT(hcU + sp.head * 0.35, hcV + sp.head * 0.25);
  pr.push(P.circle(eye, hr * 0.16, '#1b1b1b'));
  return pr;
}

// sockets (world metres): the collar (a leash), the back (a rider), the head
export function sockets(a) {
  const sp = SPECIES[a.kind], d = a.dir || 1, k = a.scale || 1, x = a.x, y = a.y || 0;
  if (!sp || !sp.L) return { centre: [x, y], back: [x, y + 0.1 * k], head: [x + d * 0.12 * k, y + 0.05 * k] };
  return { collar: [x + d * 0.5 * sp.L * k, y + (sp.hip + sp.H * 0.3) * k], back: [x, y + (sp.hip + sp.H * 0.45) * k],
    head: [x + d * (0.42 * sp.L + Math.cos(sp.nAng * Math.PI / 180) * sp.neck) * k, y + (sp.hip + sp.H * 0.2 + Math.sin(sp.nAng * Math.PI / 180) * sp.neck) * k] };
}
