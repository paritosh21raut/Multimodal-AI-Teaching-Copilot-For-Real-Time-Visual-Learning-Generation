// Stick person rig (ADR-0015 §5, P0 part 2): 14 joints, 2-bone analytic IK, postures stand / sit / lie / kneel /
// crouch, walk gait, ride (pelvis on the carrier's saddle), talk, react. Metres, y up, side view; f = facing (+1 / -1).
// The bone lengths and posture heights come from assets/person.json, the same file story/compile.py reads.

export const JOINTS = ['head', 'neck', 'chest', 'pelvis', 'lSh', 'rSh', 'lEl', 'rEl', 'lHand', 'rHand',
  'lKnee', 'rKnee', 'lFoot', 'rFoot'];

const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp = (a, b, k) => a + (b - a) * k;
const lerp2 = (a, b, k) => [lerp(a[0], b[0], k), lerp(a[1], b[1], k)];
export const ease = (k) => { k = clamp(k, 0, 1); return k * k * (3 - 2 * k); };

// 2-bone IK: root, target, lengths, bend (+1 = the joint turns counter-clockwise from the root->target line).
// Returns [joint, end] (end = the target, pulled in when out of reach).
export function ik2(root, target, l1, l2, bend) {
  const dx = target[0] - root[0], dy = target[1] - root[1];
  const d = clamp(Math.hypot(dx, dy), 1e-4, l1 + l2 - 1e-4);
  const a = Math.atan2(dy, dx);
  const A = Math.acos(clamp((l1 * l1 + d * d - l2 * l2) / (2 * l1 * d), -1, 1));
  const j = [root[0] + l1 * Math.cos(a + bend * A), root[1] + l1 * Math.sin(a + bend * A)];
  return [j, [root[0] + d * Math.cos(a), root[1] + d * Math.sin(a)]];
}

// A posture's targets around base x (pelvis point, torso lean, feet, hands), before IK.
function target(P, posture, f, ctx) {
  const pv = P.pelvis[posture] ?? P.pelvis.stand;
  const sh = (lean, py) => [f * Math.sin(lean) * P.torso, py + Math.cos(lean) * P.torso];
  switch (posture) {
    case 'sit': {
      if (ctx.seat) {   // on a saddle / seat: thighs forward, shins hang, hands to the reins
        const s = ctx.seat;
        return { pelvis: s, lean: P.lean.ride, feet: [[s[0] + f * 0.12, s[1] - 0.72], [s[0] + f * 0.16, s[1] - 0.7]],
          hands: ctx.reins ? [ctx.reins, [ctx.reins[0] - f * 0.04, ctx.reins[1] + 0.02]] : null, kneeFwd: 1 };
      }
      // on the ground, knees up, leaning back a little, hands on the knees
      return { pelvis: [0, pv], lean: P.lean.sit, feet: [[f * 0.52, 0.03], [f * 0.62, 0.03]],
        hands: [[f * 0.33, 0.42], [f * 0.4, 0.4]], kneeFwd: 1 };
    }
    case 'lie':
      return { pelvis: [0, pv], lean: P.lean.lie, feet: [[-f * 0.9, 0.05], [-f * 0.88, 0.08]],
        hands: [[f * 0.2, 0.06], [f * 0.25, 0.1]], kneeFwd: -1 };
    case 'kneel':
      return { pelvis: [0, pv], lean: P.lean.kneel, feet: [[-f * 0.42, 0.03], [f * 0.25, 0.02]],
        hands: [[f * 0.12, pv - 0.05], [f * 0.18, pv - 0.02]], kneeFwd: 1 };
    case 'crouch':
      return { pelvis: [f * P.pelvis_dx.crouch, pv], lean: P.lean.crouch, feet: [[f * 0.1, 0.02], [-f * 0.1, 0.02]],
        hands: [[f * 0.35, 0.25], [f * 0.3, 0.22]], kneeFwd: 1 };
    case 'reach_down':   // bent at the hips and knees to set a thing down on the ground / pick it up
      return { pelvis: [-f * 0.12, pv], lean: P.lean.reach_down, feet: [[f * 0.12, 0.02], [-f * 0.12, 0.02]],
        hands: [[f * 0.5, 0.12], [f * 0.45, 0.16]], kneeFwd: 1 };
    case 'climb': {   // P1b: facing the trunk / wall, hands up on it, one foot higher (the phase swaps them)
      const a = ctx.climbPh ?? 0, up = 0.5 + 0.5 * Math.sin(a);
      return { pelvis: [-f * 0.05, pv], lean: P.lean.climb, feet: [[f * 0.12, 0.02 + 0.3 * up], [f * 0.12, 0.32 - 0.3 * up]],
        hands: [[f * 0.22, 1.5 + 0.25 * (1 - up)], [f * 0.22, 1.75 - 0.25 * (1 - up)]], kneeFwd: 1 };
    }
    default: {
      const s = sh(0, pv);
      return { pelvis: [0, pv], lean: 0, feet: [[-f * 0.06, 0.02], [f * 0.08, 0.02]],
        hands: [[s[0] - f * 0.04, s[1] - 0.625], [s[0] + f * 0.05, s[1] - 0.625]], kneeFwd: 1 };
    }
  }
}

function blend(a, b, k) {
  return { pelvis: lerp2(a.pelvis, b.pelvis, k), lean: lerp(a.lean, b.lean, k),
    feet: [lerp2(a.feet[0], b.feet[0], k), lerp2(a.feet[1], b.feet[1], k)],
    hands: a.hands && b.hands ? [lerp2(a.hands[0], b.hands[0], k), lerp2(a.hands[1], b.hands[1], k)] : (b.hands || a.hands),
    kneeFwd: k < 0.5 ? a.kneeFwd : b.kneeFwd };
}

// s = { x, f, from, to, k, seat, reins, walk: {phase} | null, talk: 0..1 | null, react: {k, rub} | null, point,
//       scale (a child < 1, scaled about the feet or the seat), stoop (extra lean when standing, an old person) }
// Returns the 14 joints (absolute metres) + head radius. story/compile.py head_top() mirrors the head point.
export function pose(P, s) {
  const f = s.f;
  const ctx = { seat: s.seat ? [s.seat[0] - s.x, s.seat[1]] : null,
    reins: s.reins ? [s.reins[0] - s.x, s.reins[1]] : null, climbPh: s.climbPh };
  let T = blend(target(P, s.from, f, ctx), target(P, s.to, f, ctx), ease(s.k));
  if (s.seatK != null && s.seatK < 1) {   // mounting: the pelvis rides an arc from standing beside to the saddle
    const a = target(P, 'stand', f, {}), b = target(P, 'sit', f, ctx), k = ease(s.seatK);
    T = blend(a, b, k);
    T.pelvis = [lerp(s.mountFrom[0] - s.x, ctx.seat[0], k), lerp(s.mountFrom[1], ctx.seat[1], k) + Math.sin(Math.PI * k) * 0.35];
  }
  const swing = [0, 0];
  if (s.walk) {    // gait: feet swing forward while lifted, arms opposite, a small bob
    const ph = s.walk.phase;
    T.feet = [0, 1].map((i) => {
      const p = ph + i * Math.PI;
      return [f * 0.28 * Math.sin(p), 0.02 + Math.max(0, Math.cos(p)) * 0.13];
    });
    T.pelvis = [T.pelvis[0], T.pelvis[1] - 0.03 + 0.025 * Math.cos(2 * ph)];
    T.lean = 0.06;
    swing[0] = Math.sin(ph + Math.PI); swing[1] = Math.sin(ph);
  }
  const px = s.x + T.pelvis[0], py = T.pelvis[1];
  const pelvis = [px, py];
  let lean = T.lean;
  if (s.stoop && s.to === 'stand' && !s.walk) lean += s.stoop * ease(s.k);
  if (s.react && s.react.k < 0.3) lean -= 0.25 * Math.sin(Math.PI * s.react.k / 0.3);   // the jolt back
  const u = [f * Math.sin(lean), Math.cos(lean)];
  const neck = [px + u[0] * P.torso, py + u[1] * P.torso];
  const chest = [px + u[0] * P.torso * 0.62, py + u[1] * P.torso * 0.62];
  let headLean = lean;
  if (s.talk != null) headLean += 0.05 * Math.sin(s.talk * 18);
  const hu = [f * Math.sin(headLean), Math.cos(headLean)];
  const head = [neck[0] + hu[0] * (P.neck + P.head_r), neck[1] + hu[1] * (P.neck + P.head_r)];
  const shoulder = [neck[0] - u[0] * 0.05, neck[1] - u[1] * 0.05];
  const lSh = [shoulder[0] - f * 0.025, shoulder[1]], rSh = [shoulder[0] + f * 0.025, shoulder[1]];
  // hands: posture targets, then walk swing, talk gesture, react (hands up, then the near hand rubs the head)
  const reach = P.upper_arm + P.forearm;
  let hands = T.hands ? T.hands.map((h) => [s.x + h[0], h[1]]) : [[lSh[0], lSh[1] - reach], [rSh[0], rSh[1] - reach]];
  if (s.walk) hands = hands.map((h, i) => [h[0] + f * 0.22 * swing[i], h[1] + 0.03 * Math.abs(swing[i])]);
  if (s.talk != null) {
    const g = 0.5 + 0.5 * Math.sin(s.talk * 7);
    hands[1] = [rSh[0] + f * (0.32 + 0.06 * g), rSh[1] - 0.18 + 0.12 * g];
  }
  if (s.point) hands[1] = [rSh[0] + f * 0.55, rSh[1] + 0.05];
  // P1b hand ops: a held thing sits at the carry anchor off the pelvis (person.json "carry", compile.py hand_at);
  // hand 0 = the right (near) hand, 1 = the left
  const carry = (k) => [px + f * P.carry[k][0], py + P.carry[k][1]];
  if (s.hold) s.hold.forEach((on, k) => { if (on) hands[1 - k] = carry(k); });
  if (s.raise) {
    const k = s.raise.k, up = k < 0.25 ? ease(k / 0.25) : k > 0.8 ? 1 - ease((k - 0.8) / 0.2) : 1, i = 1 - s.raise.hand;
    hands[i] = lerp2(hands[i], [(i ? rSh : lSh)[0] + f * 0.12, head[1] + 0.32], up);
  }
  if (s.reach) hands[1] = lerp2(hands[1], [rSh[0] + f * P.reach_out[0], rSh[1] - 0.12], ease(s.reach));
  if (s.push) hands = [[lSh[0] + f * 0.48, lSh[1] - 0.12], [rSh[0] + f * 0.5, rSh[1] - 0.08]];
  if (s.throwArm != null) {   // overarm: wind up behind the head, whip to the release point (person.json), follow through
    const { k, rel } = s.throwArm, back = [rSh[0] - f * 0.3, rSh[1] + 0.3], out = [rSh[0] + f * P.release[0], rSh[1] + P.release[1]];
    const w = rel - 0.2;
    hands[1] = k < w ? lerp2(hands[1], back, ease(k / w)) : k < rel ? lerp2(back, out, (k - w) / 0.2)
      : lerp2(out, [rSh[0] + f * 0.4, rSh[1] - 0.35], ease((k - rel) / (1 - rel)));
    hands[0] = lerp2(hands[0], [lSh[0] + f * 0.35, lSh[1] + 0.05], Math.sin(Math.PI * Math.min(k / rel, 1)));   // the aim arm
  }
  if (s.ready) {   // both hands up and out to catch, at the point Python aims the throw at (person.json "catch")
    const c = [rSh[0] + f * P.catch[0], rSh[1] + P.catch[1]], u = ease(Math.min(1, s.ready * 3));
    hands = [lerp2(hands[0], [c[0] - f * 0.06, c[1] - 0.04], u), lerp2(hands[1], c, u)];
  }
  if (s.handTo) {   // setting a thing down: the hand carries it to the spot (absolute, before the lift shift)
    const i = 1 - s.handTo.hand, p = [s.handTo.p[0], s.handTo.p[1] - (s.lift || 0)];
    hands[i] = lerp2(hands[i], p, ease(s.handTo.k));
  }
  if (s.react) {
    const k = s.react.k;
    const up = k < 0.45 ? ease(k / 0.15) : 1 - ease((k - 0.45) / 0.2);
    const upH = [[lSh[0] - f * 0.22, lSh[1] + 0.28], [rSh[0] + f * 0.25, rSh[1] + 0.3]];
    hands = hands.map((h, i) => lerp2(h, upH[i], clamp(up, 0, 1)));
    if (s.react.rub && k > 0.45) {   // the near hand goes to the top of the head and rubs it
      const kk = ease((k - 0.45) / 0.15) * (k > 0.9 ? 1 - ease((k - 0.9) / 0.1) : 1);
      const rub = [head[0] + f * 0.05 + 0.03 * Math.sin(k * 40), head[1] + P.head_r + 0.02];
      hands[1] = lerp2(hands[1], rub, kk);
    }
  }
  const [lEl, lHand] = ik2(lSh, hands[0], P.upper_arm, P.forearm, -f);
  const [rEl, rHand] = ik2(rSh, hands[1], P.upper_arm, P.forearm, -f);
  const feet = T.feet.map((ft) => [s.x + ft[0], ft[1]]);
  const kb = f * T.kneeFwd;
  const [lKnee, lFoot] = ik2(pelvis, feet[0], P.thigh, P.shin, kb);
  const [rKnee, rFoot] = ik2(pelvis, feet[1], P.thigh, P.shin, kb);
  const J = { head, neck, chest, pelvis, lSh, rSh, lEl, rEl, lHand, rHand, lKnee, rKnee, lFoot, rFoot, r: P.head_r };
  const k = s.scale ?? 1;
  if (k !== 1) {
    const o = ctx.seat && s.seatK == null ? [s.x + ctx.seat[0], ctx.seat[1]] : [s.x, 0];
    for (const n of JOINTS) J[n] = [o[0] + (J[n][0] - o[0]) * k, o[1] + (J[n][1] - o[1]) * k];
    J.r *= k;
  }
  if (s.lift) for (const n of JOINTS) J[n] = [J[n][0], J[n][1] + s.lift];   // feet above the ground: a jump, a branch
  return J;
}

// Heads (ADR-0015 §7, look round 2026-11-02), drawn in head space: origin at the head centre, x towards the face,
// unit = head radius. back() = the parts behind the head (curls, tails, buns, long hair); top() = over it (the hair
// cap, a cap, glasses, beard, moustache). Famous people: curated overlays (Newton wig, Einstein hair + moustache).
const HAIR_COL = { dark: '#2b2118', grey: '#c9c9c4' };

function headSpace(ctx, j, f, M) {
  const [hx, hy] = M(j.head), r = j.r * M.s;
  ctx.save(); ctx.translate(hx, hy); ctx.scale(f * r, r);
  return r;
}

function blob(ctx, pts) {   // a smooth closed shape through the points
  const n = pts.length, mid = (a, b) => [(a[0] + b[0]) / 2, (a[1] + b[1]) / 2];
  ctx.beginPath();
  const m = mid(pts[n - 1], pts[0]); ctx.moveTo(m[0], m[1]);
  for (let i = 0; i < n; i++) { const q = mid(pts[i], pts[(i + 1) % n]); ctx.quadraticCurveTo(pts[i][0], pts[i][1], q[0], q[1]); }
  ctx.closePath();
}

function circles(ctx, list) {
  for (const [cx, cy, rr] of list) { ctx.beginPath(); ctx.arc(cx, cy, rr, 0, 7); ctx.fill(); ctx.stroke(); }
}

function back(ctx, j, f, M, C, look, known) {
  const r = headSpace(ctx, j, f, M);
  ctx.lineWidth = Math.max(2, M.s * 0.012) / r; ctx.strokeStyle = C.ink; ctx.lineJoin = 'round';
  ctx.fillStyle = known ? C.wig : (HAIR_COL[look.hair_col] || HAIR_COL.dark);
  if (known === 'newton') {
    circles(ctx, [[-0.55, -0.95, 0.48], [-0.95, -0.55, 0.48], [-1.12, 0, 0.48], [-1.1, 0.5, 0.48], [-0.95, 0.98, 0.48],
      [-0.6, 1.25, 0.48], [0.1, -1.1, 0.48], [0.62, -0.9, 0.48]]);
  } else if (known === 'einstein') {
    ctx.beginPath();
    for (let i = 0; i <= 14; i++) {
      const a = Math.PI * (0.55 + i * 0.075), rr = i % 2 ? 1.25 : 1.7;
      const px = Math.cos(a) * rr * 0.9 - 0.25, py = -Math.sin(a) * rr * 0.85 - 0.1;
      i ? ctx.lineTo(px, py) : ctx.moveTo(px, py);
    }
    ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (look.hair === 'ponytail') {
    blob(ctx, [[-0.7, -0.6], [-1.35, -0.35], [-1.55, 0.5], [-1.25, 1.3], [-1.0, 0.6], [-0.85, -0.1]]); ctx.fill(); ctx.stroke();
  } else if (look.hair === 'bun') {
    circles(ctx, [[-0.72, -0.82, 0.42]]);
  } else if (look.hair === 'long') {
    blob(ctx, [[-0.2, -1.05], [-1.05, -0.75], [-1.2, 0.4], [-1.05, 1.55], [-0.35, 1.45], [-0.6, 0.3]]); ctx.fill(); ctx.stroke();
  } else if (look.hair === 'braid') {
    circles(ctx, [[-0.95, 0.25, 0.3], [-1.0, 0.75, 0.26], [-1.02, 1.2, 0.22]]);
  }
  ctx.restore();
}

function top(ctx, j, f, M, C, look, known) {
  const r = headSpace(ctx, j, f, M);
  ctx.lineWidth = Math.max(2, M.s * 0.012) / r; ctx.strokeStyle = C.ink; ctx.lineJoin = 'round';
  if (!known && look.hair) {           // the hair cap over the crown and the back of the head, clear of the face
    ctx.fillStyle = HAIR_COL[look.hair_col] || HAIR_COL.dark;
    if (look.hair === 'spiky') {
      ctx.beginPath(); ctx.moveTo(-1.02, 0.1);
      for (const q of [[-1.25, -0.35], [-0.85, -0.55], [-0.95, -1.05], [-0.45, -0.9], [-0.25, -1.4], [0.05, -0.98],
        [0.45, -1.25], [0.5, -0.82], [0.95, -0.85], [0.72, -0.55]]) ctx.lineTo(q[0], q[1]);
      ctx.quadraticCurveTo(0, -0.7, -0.65, -0.15); ctx.closePath(); ctx.fill(); ctx.stroke();
    } else if (look.hair === 'curly') {
      circles(ctx, [[-0.85, -0.45, 0.34], [-0.55, -0.88, 0.34], [-0.05, -1.02, 0.34], [0.45, -0.88, 0.34], [-0.98, 0.05, 0.34]]);
    } else {
      ctx.beginPath(); ctx.arc(0, 0, 1.08, Math.PI * 0.92, Math.PI * 1.78);
      const fringe = look.hair === 'side' ? [0.95, -0.25] : [0.62, -0.55];
      ctx.quadraticCurveTo(fringe[0], fringe[1], 0.1, -0.62);
      ctx.quadraticCurveTo(-0.55, -0.45, -0.62, 0.2);
      ctx.closePath(); ctx.fill(); ctx.stroke();
    }
  }
  if (look.acc === 'cap') {
    ctx.fillStyle = look.shirt || C.ink;
    ctx.beginPath(); ctx.arc(0, -0.15, 1.04, Math.PI, Math.PI * 2); ctx.closePath(); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0.6, -0.2); ctx.lineTo(1.55, -0.12); ctx.lineTo(1.5, 0.0); ctx.lineTo(0.55, -0.02);
    ctx.closePath(); ctx.fill(); ctx.stroke();
  } else if (look.acc === 'glasses') {
    ctx.beginPath(); ctx.arc(0.5, -0.12, 0.27, 0, 7); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(0.23, -0.14); ctx.lineTo(-0.55, -0.2); ctx.stroke();
  } else if (look.acc === 'beard') {
    ctx.fillStyle = HAIR_COL[look.hair_col] || HAIR_COL.grey;
    blob(ctx, [[-0.35, 0.45], [0.2, 0.75], [0.85, 0.55], [0.55, 1.35], [-0.1, 1.15]]); ctx.fill(); ctx.stroke();
  }
  if (known === 'einstein') {
    ctx.fillStyle = C.wig;
    ctx.beginPath(); ctx.ellipse(0.5, 0.28, 0.36, 0.15, 0, 0, 7); ctx.fill(); ctx.stroke();
  }
  ctx.restore();
}

// Draw a person. M maps metres -> px (M.s = px per metre); C = theme colours;
// extra = { talkOpen, known, surprised, look: {shirt, hair, hair_col, dress, acc}, t (for the blink) }
export function draw(ctx, j, f, M, C, extra = {}) {
  const look = extra.look || {}, known = extra.known || '';
  const k = j.r / 0.13, w = M.s * 0.042 * Math.max(0.8, k);
  const shirt = look.shirt || C.body;
  ctx.save();
  ctx.lineCap = 'round'; ctx.lineJoin = 'round';
  const seg = (pts, col, lw) => {
    ctx.strokeStyle = col; ctx.lineWidth = lw; ctx.beginPath();
    pts.forEach((p, i) => { const q = M(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
    ctx.stroke();
  };
  const dot = (p, col, rad) => { const q = M(p); ctx.fillStyle = col; ctx.beginPath(); ctx.arc(q[0], q[1], rad, 0, 7); ctx.fill(); };
  const foot = (p, col) => seg([p, [p[0] + f * 0.09 * k, Math.max(p[1] - 0.005, 0.01)]], col, w * 0.9);
  // far limbs lighter (depth)
  seg([j.pelvis, j.lKnee, j.lFoot], C.far, w); foot(j.lFoot, C.far);
  seg([j.lSh, j.lEl, j.lHand], C.far, w); dot(j.lHand, C.far, w * 0.75);
  back(ctx, j, f, M, C, look, known);
  seg([j.pelvis, j.rKnee, j.rFoot], C.ink, w); foot(j.rFoot, C.ink);
  if (look.dress) {   // a said "she": a flared skirt from the waist
    const u = [j.neck[0] - j.pelvis[0], j.neck[1] - j.pelvis[1]];
    const waist = [j.pelvis[0] + u[0] * 0.35, j.pelvis[1] + u[1] * 0.35];
    const hem = 0.3 * k, spread = 0.2 * k;
    const pts = [waist, [j.pelvis[0] + spread, j.pelvis[1] - hem], [j.pelvis[0] - spread, j.pelvis[1] - hem]];
    ctx.fillStyle = shirt; ctx.strokeStyle = C.ink; ctx.lineWidth = w * 0.45;
    ctx.beginPath(); pts.forEach((p, i) => { const q = M(p); i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1]); });
    ctx.closePath(); ctx.fill(); ctx.stroke();
  }
  seg([j.pelvis, j.chest, j.neck], shirt, w * 1.5);
  seg([j.neck, [(j.neck[0] + j.head[0]) / 2, (j.neck[1] + j.head[1]) / 2]], C.ink, w * 0.8);
  // head and face: eye (blinks), brow (raised in surprise), mouth (talks, opens in surprise)
  const [hx, hy] = M(j.head), r = j.r * M.s;
  ctx.fillStyle = C.skin; ctx.strokeStyle = C.ink; ctx.lineWidth = w * 0.8;
  ctx.beginPath(); ctx.arc(hx, hy, r, 0, 7); ctx.fill(); ctx.stroke();
  const ex = hx + f * r * 0.45, ey = hy - r * 0.12, surprised = extra.surprised, open = extra.talkOpen || 0;
  const blink = extra.t != null && !surprised && ((extra.t + (look.shirt || '').charCodeAt(2) * 0.05) % 3.7) < 0.12;
  ctx.fillStyle = C.ink; ctx.strokeStyle = C.ink; ctx.lineWidth = Math.max(2, w * 0.4);
  if (blink) { ctx.beginPath(); ctx.moveTo(ex - r * 0.12, ey); ctx.lineTo(ex + r * 0.12, ey); ctx.stroke(); } else {
    ctx.beginPath(); ctx.arc(ex, ey, r * (surprised ? 0.14 : 0.11), 0, 7); ctx.fill();
  }
  const by = ey - r * (surprised ? 0.45 : 0.34);
  ctx.beginPath(); ctx.moveTo(ex - f * r * 0.17, by); ctx.quadraticCurveTo(ex, by - r * (surprised ? 0.12 : 0.06), ex + f * r * 0.17, by);
  ctx.stroke();
  const mx = hx + f * r * 0.48, my = hy + r * 0.42;
  ctx.beginPath();
  if (surprised) { ctx.ellipse(mx, my, r * 0.12, r * 0.18, 0, 0, 7); ctx.fill(); }
  else if (open > 0.05) { ctx.ellipse(mx, my, r * 0.17, r * (0.04 + 0.14 * open), 0, 0, 7); ctx.fill(); }
  else { ctx.moveTo(mx - f * r * 0.2, my - r * 0.04); ctx.quadraticCurveTo(mx, my + r * 0.12, mx + f * r * 0.16, my - r * 0.06); ctx.stroke(); }
  top(ctx, j, f, M, C, look, known);
  seg([j.rSh, j.rEl, j.rHand], C.ink, w); dot(j.rHand, C.ink, w * 0.75);   // the near arm over the body
  ctx.restore();
}
