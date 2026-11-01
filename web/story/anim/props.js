// Story props (ADR-0015 §6, P0): drawn in code from the anchor sidecars (assets/*.json) in one line-art style.
// tree (trunk, canopy, fruit at its anchors), apple, horse (quadruped rig + walk gait), village, ground + sky, and the
// fallback box (a labelled thing with no asset). Metres, y up; M maps metres -> px.
import { ik2 } from './rig.js';

const FRUIT_COL = { apple: '#d23a2c', orange: '#ee8a1d', mango: '#f0b429', pear: '#9cc23a', lemon: '#f2d33a', cherry: '#b0123a' };

function path(ctx, M, pts) {
  pts.forEach((p, i) => { const q = M(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
}

export function sky(ctx, M, C, W, H) {
  const g = ctx.createLinearGradient(0, 0, 0, M([0, 0])[1]);
  g.addColorStop(0, C.sky0); g.addColorStop(1, C.sky1);
  ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
  ctx.fillStyle = C.sun; ctx.beginPath(); ctx.arc(W - 150, 120, 58, 0, 7); ctx.fill();
}

export function ground(ctx, M, C, W, H) {
  const [, gy] = M([0, 0]);
  ctx.fillStyle = C.ground; ctx.fillRect(0, gy, W, H - gy);
  ctx.strokeStyle = C.ink; ctx.lineWidth = M.s * 0.025;
  ctx.beginPath(); ctx.moveTo(0, gy); ctx.lineTo(W, gy); ctx.stroke();
  ctx.strokeStyle = C.grass; ctx.lineWidth = M.s * 0.018; ctx.lineCap = 'round';
  for (let x = 0.3; x < 14; x += 0.83) {   // a few grass tufts (fixed in the world, no randomness)
    const [px, py] = M([x + 0.2 * Math.sin(x * 3.1), 0]);
    ctx.beginPath();
    const u = M.s / 137;
    ctx.moveTo(px - 6 * u, py); ctx.lineTo(px - 10 * u, py - 14 * u); ctx.moveTo(px, py); ctx.lineTo(px, py - 18 * u);
    ctx.moveTo(px + 6 * u, py); ctx.lineTo(px + 11 * u, py - 13 * u); ctx.stroke();
  }
}

export function tree(ctx, M, C, A, x, opt) {
  const T = A.tree, { trunk: tk, canopy: cp } = T;
  ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  // trunk: tapered, two branches into the canopy
  ctx.fillStyle = C.bark; ctx.strokeStyle = C.ink; ctx.lineWidth = M.s * 0.03;
  ctx.beginPath();
  path(ctx, M, [[x - tk.w / 2, 0], [x - tk.w * 0.32, tk.top], [x + tk.w * 0.32, tk.top], [x + tk.w / 2, 0]]);
  ctx.closePath(); ctx.fill(); ctx.stroke();
  ctx.lineWidth = M.s * 0.06; ctx.strokeStyle = C.bark;
  ctx.beginPath(); path(ctx, M, [[x, tk.top - 0.3], [x - 0.9, tk.top + 0.5]]); ctx.stroke();
  ctx.beginPath(); path(ctx, M, [[x, tk.top - 0.2], [x + 0.85, tk.top + 0.6]]); ctx.stroke();
  // canopy: a cloud of lobes; stroke all wide first, then fill all = one outer outline
  const lobes = [];
  for (let i = 0; i < 9; i++) {
    const a = (i / 9) * Math.PI * 2;
    lobes.push([x + cp.cx + Math.cos(a) * cp.rx * 0.68, cp.cy + Math.sin(a) * cp.ry * 0.62, 0.78 + 0.12 * (i % 3)]);
  }
  lobes.push([x + cp.cx, cp.cy, 1.25]);
  ctx.strokeStyle = C.ink; ctx.lineWidth = M.s * 0.06;
  for (const [lx, ly, r] of lobes) { const [px, py] = M([lx, ly]); ctx.beginPath(); ctx.arc(px, py, r * M.s, 0, 7); ctx.stroke(); }
  ctx.fillStyle = C.leaf;
  for (const [lx, ly, r] of lobes) { const [px, py] = M([lx, ly]); ctx.beginPath(); ctx.arc(px, py, r * M.s, 0, 7); ctx.fill(); }
  ctx.strokeStyle = C.leafLine; ctx.lineWidth = M.s * 0.015;   // a few leaf marks
  for (let i = 0; i < 7; i++) {
    const [px, py] = M([x + cp.cx - 1.4 + i * 0.47, cp.cy + 0.55 * Math.sin(i * 1.7)]);
    ctx.beginPath(); ctx.arc(px, py, M.s * 0.16, Math.PI * 1.1, Math.PI * 1.6); ctx.stroke();
  }
  // fruit at the anchors (the fallen ones hidden); a shaking one wiggles
  if (opt.fruit) {
    T.fruit.forEach(([fx, fy], k) => {
      if (opt.hidden.includes(k)) return;
      fruit(ctx, M, C, A, [x + fx, fy], opt.fruit);
    });
  }
  ctx.restore();
}

export function fruit(ctx, M, C, A, at, kind = 'apple') {
  const r = A.apple.r * M.s, [px, py] = M(at);
  ctx.save();
  ctx.strokeStyle = C.ink; ctx.lineWidth = Math.max(2, M.s * 0.014);
  ctx.beginPath(); ctx.moveTo(px, py - r * 0.8); ctx.lineTo(px + r * 0.3, py - r * 1.7); ctx.stroke();
  ctx.fillStyle = FRUIT_COL[kind] || FRUIT_COL.apple;
  ctx.beginPath(); ctx.arc(px, py, r, 0, 7); ctx.fill(); ctx.stroke();
  ctx.fillStyle = 'rgba(255,255,255,.55)';
  ctx.beginPath(); ctx.arc(px - r * 0.35, py - r * 0.3, r * 0.28, 0, 7); ctx.fill();
  ctx.restore();
}

// The horse's current geometry (absolute metres): body bob from the gait, saddle and reins points for the rider.
export function horseFrame(A, x, f, phase) {
  const H = A.horse;
  const bob = phase == null ? 0 : 0.035 * Math.sin(2 * phase);
  const P = (p) => [x + f * p[0], p[1] + bob];
  return { bob, saddle: P(H.saddle), reins: P(H.reins), P };
}

export function horse(ctx, M, C, A, x, f, phase) {
  const H = A.horse, fr = horseFrame(A, x, f, phase), P = fr.P;
  ctx.save(); ctx.lineJoin = 'round'; ctx.lineCap = 'round';
  const lw = M.s * 0.04;
  // legs: hips -> hoof by 2-bone IK; walk = 4-beat (LH, LF, RH, RF); front knees forward, hind hocks back
  const legs = [[0, 0, 0], [1, 0, 0.25], [0, 1, 0.5], [1, 1, 0.75]];   // [front?, near?, phase offset]
  const drawLeg = (front, near, off) => {
    const hip = P(H.hips[front]);
    let foot = [hip[0], 0.02];
    if (phase != null) {
      const p = phase + off * Math.PI * 2;
      foot = [hip[0] + f * 0.32 * Math.sin(p), 0.02 + Math.max(0, Math.cos(p)) * 0.18];
    }
    const [knee, hoof] = ik2(hip, foot, H.leg[0], H.leg[1], front ? f : -f);
    ctx.strokeStyle = near ? C.ink : C.far; ctx.lineWidth = lw;
    ctx.beginPath(); path(ctx, M, [hip, knee, hoof]); ctx.stroke();
    ctx.fillStyle = near ? C.ink : C.far;
    const [hx, hy] = M(hoof); ctx.fillRect(hx - lw * 0.7, hy - lw * 0.5, lw * 1.4, lw * 0.8);
  };
  legs.filter((l) => !l[1]).forEach((l) => drawLeg(...l));
  // tail, body, neck, head, mane, ear, eye
  ctx.strokeStyle = C.ink; ctx.lineWidth = lw * 1.3;
  ctx.beginPath(); path(ctx, M, [P([-0.82, 1.36]), P([-1.05, 1.1]), P([-1.08, 0.75])]); ctx.stroke();
  ctx.fillStyle = C.horse; ctx.lineWidth = lw * 0.8;
  const [bx, by] = M(P([H.body.cx, H.body.cy]));
  ctx.beginPath(); ctx.ellipse(bx, by, H.body.rx * M.s, H.body.ry * M.s, 0, 0, 7); ctx.fill(); ctx.stroke();
  ctx.beginPath(); path(ctx, M, [P([0.5, 1.45]), P([0.98, 2.0]), P([1.18, 1.95]), P([0.85, 1.2])]);
  ctx.closePath(); ctx.fill(); ctx.stroke();
  const [hx, hy] = M(P(H.head));
  ctx.save(); ctx.translate(hx, hy); ctx.rotate(f * 0.55); ctx.scale(f, 1);
  ctx.beginPath(); ctx.ellipse(0, 0, 0.3 * M.s, 0.13 * M.s, 0, 0, 7); ctx.fill(); ctx.stroke();
  ctx.restore();
  ctx.beginPath(); path(ctx, M, [P([1.0, 2.02]), P([1.02, 2.18]), P([1.1, 2.0])]); ctx.fill(); ctx.stroke();
  ctx.strokeStyle = C.mane; ctx.lineWidth = lw * 0.9;
  ctx.beginPath(); path(ctx, M, [P([0.98, 2.02]), P([0.75, 1.75]), P([0.55, 1.5])]); ctx.stroke();
  ctx.fillStyle = C.ink; const [ex, ey] = M(P([1.2, 1.93]));
  ctx.beginPath(); ctx.arc(ex, ey, M.s * 0.025, 0, 7); ctx.fill();
  // saddle
  ctx.fillStyle = C.saddle; ctx.strokeStyle = C.ink; ctx.lineWidth = lw * 0.6;
  ctx.beginPath(); path(ctx, M, [P([-0.35, 1.53]), P([0.25, 1.53]), P([0.2, 1.42]), P([-0.3, 1.42])]);
  ctx.closePath(); ctx.fill(); ctx.stroke();
  legs.filter((l) => l[1]).forEach((l) => drawLeg(...l));
  ctx.restore();
  return fr;
}

export function village(ctx, M, C, A, x) {
  ctx.save(); ctx.lineJoin = 'round'; ctx.strokeStyle = C.ink; ctx.lineWidth = M.s * 0.03;
  A.village.houses.forEach(([hx, w, h, roof], i) => {
    const cx = x + hx;
    ctx.fillStyle = C.wall[i % C.wall.length];
    ctx.beginPath(); path(ctx, M, [[cx - w / 2, 0], [cx - w / 2, h], [cx + w / 2, h], [cx + w / 2, 0]]);
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = C.roof;
    ctx.beginPath(); path(ctx, M, [[cx - w / 2 - 0.15, h], [cx, h + roof], [cx + w / 2 + 0.15, h]]);
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = C.door;
    ctx.beginPath(); path(ctx, M, [[cx - 0.18, 0], [cx - 0.18, 0.75], [cx + 0.18, 0.75], [cx + 0.18, 0]]);
    ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.fillStyle = C.window;
    for (const wx of [-w * 0.3, w * 0.3]) {
      ctx.beginPath(); path(ctx, M, [[cx + wx - 0.14, h * 0.62], [cx + wx - 0.14, h * 0.85], [cx + wx + 0.14, h * 0.85], [cx + wx + 0.14, h * 0.62]]);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  });
  ctx.restore();
}

export function box(ctx, M, C, x, y, label) {
  const [px, py] = M([x, y]);
  ctx.save(); ctx.font = `600 ${Math.round(M.s * 0.2)}px Segoe UI, sans-serif`;
  const w = Math.max(M.s * 0.7, ctx.measureText(label).width + M.s * 0.3), h = M.s * 0.45;
  ctx.fillStyle = C.boxFill; ctx.strokeStyle = C.ink; ctx.lineWidth = M.s * 0.02;
  ctx.beginPath(); ctx.roundRect(px - w / 2, py - h, w, h, 10); ctx.fill(); ctx.stroke();
  ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
  ctx.fillText(label, px, py - h / 2);
  ctx.restore();
}
