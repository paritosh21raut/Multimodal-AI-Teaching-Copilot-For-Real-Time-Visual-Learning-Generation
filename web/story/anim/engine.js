// Story scene player (ADR-0015 §5, P0 part 2): plays one StorySceneSpec (story/compile.py) on a Canvas. The frame
// is a pure function of t (seek for tests and screenshots, requestAnimationFrame for play); the browser only
// evaluates the targets and contact times Python gave (the fall's curve uses the spec's g, start and velocity).
import { pose, draw as drawPerson, ease } from './rig.js';
import { sky, ground, tree, branches, fruit, horse, horseFrame, village, box, thing, PROPS } from './props.js';

export const W = 1920, H = 1080;
const GROUND_PX = 960;
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const lerp2 = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];

const THEMES = {
  light: { ink: '#1d2126', far: '#8a929c', skin: '#fff8ee', wig: '#f1efe8', sky0: '#cfe7f6', sky1: '#f4f1e6',
    sun: '#ffd666', ground: '#e3dcc6', grass: '#6f9a4a', bark: '#9a6b43', leaf: '#9fd18b', leafLine: '#5f9a4d',
    horse: '#c98c55', mane: '#5a3a22', saddle: '#7a3b2a', wall: ['#f6e3c3', '#e8d3b0', '#f1d9cf'], roof: '#b5523b',
    door: '#7a5235', window: '#cfe7f6', boxFill: '#ffffff', bubble: '#ffffff', caption: '#3c434c', body: '#2c6fb5' },
  dark: { ink: '#eef2f6', far: '#7f8994', skin: '#2b3038', wig: '#dfe3e8', sky0: '#0c1a2b', sky1: '#1b2633',
    sun: '#f2d27a', ground: '#1f2a22', grass: '#5c8f45', bark: '#7a5233', leaf: '#2f6b3d', leafLine: '#8ccf7b',
    horse: '#8a5a33', mane: '#e7d2b8', saddle: '#b0573e', wall: ['#3a3226', '#34302a', '#3b2f2c'], roof: '#a0473a',
    door: '#c99a6b', window: '#f2d27a', boxFill: '#1b2330', bubble: '#1b2330', caption: '#c9d1da', body: '#6fb3ff' },
};

export class Player {
  constructor(canvas, A) {
    this.cv = canvas; this.ctx = canvas.getContext('2d'); this.A = A; this.C = THEMES.light;
    this.camera(0, 14);
    this.spec = null;
  }
  theme(name) { this.C = THEMES[name] || THEMES.light; }
  load(spec) {
    this.spec = spec; this.byId = Object.fromEntries(spec.entities.map((e) => [e.id, e]));
    this.frameScene(spec);
  }

  camera(x0, span) {
    const s = W / span;
    this.M = Object.assign((p) => [(p[0] - x0) * s, GROUND_PX - p[1] * s], { s, x0, span });
  }

  // Fit the scene: every entity's start and end (and each move's path) inside, the tallest thing's reach above the
  // ground (a tree's canopy top may crop, its fruit never), 7-14 m wide.
  frameScene(spec) {
    const A = this.A, half = { person: 0.45, tree: A.tree.width / 2, horse: A.horse.length / 2 + 0.2,
      village: A.village.width / 2 + 0.2, apple: 0.2, box: 0.6 };
    const tall = { person: 1.9, tree: 4.4, horse: 2.25, village: 2.8, apple: 0.3, box: 0.6 };
    let lo = Infinity, hi = -Infinity, top = 2;
    const add = (x, a) => { lo = Math.min(lo, x - (half[a] ?? 0.6)); hi = Math.max(hi, x + (half[a] ?? 0.6)); };
    for (const e of spec.entities) {
      for (const p of [e.start, e.end]) if (p) add(p.x, e.asset);
      top = Math.max(top, tall[e.asset] ?? 1);
      if (e.asset === 'person' && spec.entities.some((o) => o.asset === 'horse')) top = Math.max(top, 3.5);
    }
    for (const ev of spec.events) {
      const a = this.byId[ev.actor]?.asset;
      if (ev.op === 'move' && !ev.exit) { add(ev.from, a); add(ev.to, a); }   // walking off: the camera stays
      if (ev.op === 'climb' || ev.op === 'jump') top = Math.max(top, ev.to[1] + 2.0);
      if (ev.op === 'fall' && ev.v && ev.v[1]) { add(ev.from[0], 'apple'); add(ev.rest[0], 'apple'); }
      if (ev.op === 'speak') top = Math.max(top, 2.9);
    }
    const need = Math.max(hi - lo + 0.8, ((top + 0.3) * W) / GROUND_PX, 7);
    const span = Math.min(14, need);
    const x0 = clamp((lo + hi) / 2 - span / 2, 0, 14 - span);
    this.camera(x0, span);
  }

  // ---- state at t ------------------------------------------------------------------------------------------------
  state(t) {
    const S = {}, fx = [], bubbles = [];
    for (const e of this.spec.entities) {
      const s = e.start;
      S[e.id] = { e, x: s.x, y: s.y, f: s.facing, from: s.posture, to: s.posture, k: 1, carrier: s.carrier,
        hanging: s.fruit >= 0, pos: [s.x, s.y], phase: null, holder: s.holder || null, hand: s.hand || 0,
        lift: e.asset === 'person' ? s.y : 0 };
    }
    for (const ev of this.spec.events) {
      const st = S[ev.actor];
      if (!st || t < ev.t0) continue;
      const k = clamp((t - ev.t0) / Math.max(1e-6, ev.t1 - ev.t0), 0, 1);
      if (ev.facing) for (const [id, f] of Object.entries(ev.facing)) if (S[id]) S[id].f = f;   // turns Python made
      switch (ev.op) {
        case 'posture': st.from = ev.from; st.to = ev.to; st.k = k; break;
        case 'mount':
          st.carrier = ev.carrier; st.from = st.to = 'sit';
          if (k < 1) { st.seatK = k; st.mountFrom = ev.from; } else st.seatK = null;
          break;
        case 'move': {
          const d = ev.to - ev.from;
          const ke = k < 1 ? k - Math.sin(2 * Math.PI * k) / (4 * Math.PI) : 1;   // eased start / stop
          st.x = ev.from + d * ke; st.f = ev.facing;
          const stride = (this.A[st.e.asset] || this.A.person).stride;
          st.phase = k < 1 && k > 0 ? (Math.abs(d * ke) / stride) * Math.PI * 2 : null;
          if (st.e.asset === 'person') st.walk = st.phase == null ? null : { phase: st.phase };
          break;
        }
        case 'fall': st.hanging = false; st.holder = null; st.tween = null; st.pos = this.fallAt(ev, t); st.x = st.pos[0];
          if (t < ev.t1) st.falling = true; break;
        case 'speak':
          if (t <= ev.t1 || ev.hold) {   // P1c: the shot's last words stay on its end frame
            st.talk = Math.min(t, ev.t1) - ev.t0;
            const n = Math.floor(ev.text.length * clamp((t - ev.t0 - 0.3) / Math.max(0.05, ev.type_s), 0, 1));
            bubbles.push({ actor: ev.actor, to: ev.to, text: ev.text.slice(0, n), full: ev.text });
            st.talkOpen = n < ev.text.length ? 0.5 + 0.5 * Math.sin((t - ev.t0) * 22) : 0;
          }
          break;
        case 'react':
          if (t <= ev.t1) {
            st.react = { k, rub: !!ev.rub }; st.surprised = k < 0.55;
            if (k < 0.45) fx.push({ kind: 'mark', actor: ev.actor, k });
            if (ev.style === 'hit_reacts' && k < 0.25) fx.push({ kind: 'hit', actor: ev.actor, k });
          }
          break;
        case 'point': if (t <= ev.t1) st.point = true; break;
        // ---- P1b: hand ops (the thing's place is set after the poses, from the hand joints) ----
        case 'grip': st.hanging = false; st.tween = k < 1 ? { a: ev.from, by: ev.by, hand: ev.hand, k } : null;
          st.holder = ev.by; st.hand = ev.hand; break;
        case 'place':   // the hand carries it down to the spot (handTo), it rides the hand, then stays there
          if (k < 1) { st.tween = { from: ev.by, fromHand: ev.hand, b: ev.to, k, flat: true };
            if (S[ev.by]) S[ev.by].handTo = { p: ev.to, k, hand: ev.hand }; }
          else { st.tween = null; st.pos = ev.to; st.x = ev.to[0]; }
          st.holder = null; break;
        case 'ready': if (t <= ev.t1) st.ready = k; break;
        case 'handover':
          if (k < 1) {
            st.tween = { from: ev.by, fromHand: ev.hand, by: ev.to, hand: ev.to_hand, k }; st.holder = null;
            for (const id of [ev.by, ev.to]) if (S[id]) S[id].reach = Math.min(1, k * 3);
          } else { st.tween = null; st.holder = ev.to; st.hand = ev.to_hand; }
          break;
        case 'raise': if (t <= ev.t1) st.raise = { hand: ev.hand, k }; break;
        case 'throw_arm': if (t <= ev.t1) st.throwArm = { k, rel: ev.release ?? 0.75 }; break;
        case 'push': if (t <= ev.t1) st.push = true; break;
        case 'slide': { const x = ev.from + (ev.to - ev.from) * ease(k); st.x = x; st.pos = [x, st.pos[1]]; break; }
        case 'jump': {   // crouch, the hop Python timed (v0 from g and the hop height), land
          st.f = ev.facing;
          const crouch = (a) => { st.from = 'stand'; st.to = 'crouch'; st.k = a; };
          if (t < ev.t_up) { crouch(Math.sin((Math.PI / 2) * (t - ev.t0) / (ev.t_up - ev.t0))); st.lift = ev.from[1]; st.x = ev.from[0]; }
          else if (t < ev.t_land) {
            const d = t - ev.t_up, T = ev.t_land - ev.t_up;
            st.from = st.to = 'stand'; st.k = 1;
            st.x = ev.from[0] + (ev.to[0] - ev.from[0]) * (d / T);
            st.lift = ev.from[1] + ev.v0 * d - 0.5 * this.spec.g * d * d;
          } else {
            crouch(t < ev.t1 ? Math.sin(Math.PI * (t - ev.t_land) / (ev.t1 - ev.t_land)) * 0.7 : 0);
            st.lift = ev.to[1]; st.x = ev.to[0];
          }
          break;
        }
        case 'climb': {   // up the trunk hand over hand (85 %), then over onto the anchor
          st.f = ev.facing;
          const dy = ev.to[1] - ev.from[1];
          if (k < 0.85) {
            st.from = st.to = 'climb'; st.k = 1; st.x = ev.from[0];
            st.lift = ev.from[1] + dy * k; st.climbPh = (dy * k / 0.3) * Math.PI;
          } else if (k < 1) {
            const k2 = (k - 0.85) / 0.15;
            st.x = ev.from[0] + (ev.to[0] - ev.from[0]) * ease(k2);
            st.lift = ev.from[1] + dy * (0.85 + 0.15 * ease(k2)); st.from = 'climb'; st.to = ev.end; st.k = k2;
          } else { st.from = st.to = ev.end; st.k = 1; st.lift = ev.to[1]; st.x = ev.to[0]; st.climbPh = null; }
          break;
        }
        case 'dismount':
          if (k < 1) { st.carrier = ev.carrier; st.seatK = 1 - k; st.mountFrom = [ev.to[0], 0.92]; st.from = st.to = 'sit'; }
          else { st.carrier = null; st.seatK = null; st.x = ev.to[0]; st.from = st.to = 'stand'; st.k = 1; }
          break;
        default: break;
      }
    }
    // shaking fruit just before it drops; the fruit spot it left is hidden by the compiler from the start
    for (const ev of this.spec.events) {
      if (ev.op === 'fall' && t < ev.t0 && t > ev.t0 - ev.shake) {
        const st = S[ev.actor];
        st.pos = [ev.from[0] + 0.012 * Math.sin(t * 70), ev.from[1]];
      }
    }
    // horses first (frames), then riders take the saddle
    for (const st of Object.values(S)) if (st.e.asset === 'horse') st.frame = horseFrame(this.A, st.x, st.f, st.phase);
    for (const st of Object.values(S)) {
      if (st.e.asset !== 'person') continue;
      const c = st.carrier && S[st.carrier];
      const hold = [false, false];
      for (const o of Object.values(S)) if (o.holder === st.e.id) hold[o.hand] = true;
      const ps = { x: st.x, f: st.f, from: st.from, to: st.to, k: st.k, walk: st.walk || null,
        talk: st.talk ?? null, react: st.react || null, point: st.point || false,
        scale: st.e.look?.scale ?? 1, stoop: st.e.look?.stoop ?? 0, hold, raise: st.raise || null,
        reach: st.reach || 0, push: !!st.push, throwArm: st.throwArm ?? null, lift: st.lift || 0, climbPh: st.climbPh,
        ready: st.ready ?? null, handTo: st.handTo || null };
      if (!c && st.to === 'sit' && st.lift > 0.05) ps.seat = [st.x, this.A.person.branch_seat];   // on a branch: legs hang
      if (c && c.frame) {
        ps.f = st.f = c.f;
        ps.seat = c.frame.saddle; ps.reins = c.frame.reins;
        if (st.seatK != null) {
          ps.seatK = st.seatK; ps.mountFrom = st.mountFrom;
          ps.x = st.mountFrom[0] + (c.frame.saddle[0] - st.mountFrom[0]) * ease(st.seatK);
        } else ps.x = st.x = c.frame.saddle[0];   // a rider is where the saddle is (bubbles, facing)
      }
      st.joints = pose(this.A.person, ps);
    }
    // held things ride the hand joint; a grip / put / hand-over tweens between the ground, a hand and a spot
    const hand = (id, k) => { const j = S[id]?.joints; return j ? (k ? j.lHand : j.rHand) : null; };
    for (const st of Object.values(S)) {
      const w = st.tween;
      if (w) {
        const a = w.a || hand(w.from, w.fromHand), b = w.b || hand(w.by, w.hand);
        if (a && b) { st.pos = w.flat ? b.slice() : lerp2(a, b, ease(w.k)); if (!w.flat) st.pos[1] += Math.sin(Math.PI * w.k) * 0.12; }
        if (w.flat && w.from) { const h = hand(w.from, w.fromHand); if (h && w.k < 1) st.pos = h; }   // in the hand till it lets go
      } else if (st.holder) { const h = hand(st.holder, st.hand); if (h) st.pos = h; }
      if (st.e.asset === 'box' || st.e.asset === 'apple' || PROPS.includes(st.e.asset)) st.x = st.pos[0];
    }
    return { S, fx, bubbles };
  }

  fallAt(ev, t) {
    const g = this.spec.g, c = ev.contact;
    if (t <= c.t) {
      const d = t - ev.t0;
      return [ev.from[0] + ev.v[0] * d, ev.from[1] + (ev.v[1] || 0) * d - 0.5 * g * d * d];   // v[1] > 0: a throw
    }
    if (!ev.bounce) return c.at;
    const b = ev.bounce;
    if (t <= b.t_ground) {
      const d = t - c.t;
      return [c.at[0] + b.v[0] * d, c.at[1] + b.v[1] * d - 0.5 * g * d * d];
    }
    const k = ease((t - b.t_ground) / 0.5);
    const x0 = c.at[0] + b.v[0] * (b.t_ground - c.t);
    return [x0 + (ev.rest[0] - x0) * k, ev.rest[1]];
  }

  // ---- draw ------------------------------------------------------------------------------------------------------
  frame(t) {
    const { ctx, M, C, A } = this, { S, fx, bubbles } = this.state(t);
    ctx.clearRect(0, 0, W, H);
    sky(ctx, M, C, W, H); ground(ctx, M, C, W, H);
    const list = Object.values(S);
    for (const st of list) if (st.e.asset === 'village') village(ctx, M, C, A, st.x);
    for (const st of list) if (st.e.asset === 'tree') tree(ctx, M, C, A, st.x, { fruit: st.e.fruit, hidden: st.e.hidden });
    for (const st of list) if (st.e.asset === 'tree' && st.e.parts?.includes('branch')) branches(ctx, M, C, A, st.x);   // only once said
    for (const st of list) if (PROPS.includes(st.e.asset) && !(st.holder || st.tween)) thing(ctx, M, C, A, st.e.asset, st.pos, false, st.pos[0] - st.e.start.x);
    const small = (st) => st.holder || st.tween || st.e.kind === 'prop' && st.pos[1] > 0.05;
    for (const st of list) if (st.e.asset === 'box' && !small(st)) box(ctx, M, C, st.x, st.pos[1], st.e.name);
    for (const st of list) if (st.e.asset === 'horse') horse(ctx, M, C, A, st.x, st.f, st.phase);
    // supporting people behind, the main characters in front
    const people = list.filter((st) => st.e.asset === 'person').sort((a, b) => (a.e.look?.main ? 1 : 0) - (b.e.look?.main ? 1 : 0));
    for (const st of people) {
      drawPerson(ctx, st.joints, st.f, M, C, { known: st.e.known, talkOpen: st.talkOpen, surprised: st.surprised,
        look: st.e.look, t });
    }
    this.tags(people);
    for (const st of list) if (st.e.asset === 'apple') fruit(ctx, M, C, A, st.pos, 'apple');
    for (const st of list) if (PROPS.includes(st.e.asset) && (st.holder || st.tween)) thing(ctx, M, C, A, st.e.asset, st.pos, true, 0);
    // a held / moving / put-on-something box is hand-sized; a held one is centred on the hand that holds it
    for (const st of list) {
      if (st.e.asset === 'box' && small(st)) box(ctx, M, C, st.pos[0], st.pos[1] - (st.holder || st.tween ? 0.11 : 0), st.e.name, 0.5);
    }
    for (const f of fx) this.effect(f, S[f.actor]);
    for (const b of bubbles) this.bubble(b, S);
    ctx.fillStyle = C.caption; ctx.font = '500 26px Segoe UI, sans-serif'; ctx.textAlign = 'center';
    ctx.fillText(this.spec.line, W / 2, H - 14);
  }

  // Name tags (user 2026-11-02): only named people, under their feet on the ground band (never in the bubbles'
  // way); a tag that would overlap the one before drops to a second row.
  tagBoxes(people) {
    const { ctx, M } = this, out = [];
    ctx.font = '700 30px Segoe UI, sans-serif';
    const named = people.filter((st) => st.e.label).map((st) => ({ st, x: M([st.joints.pelvis[0], 0])[0] }))
      .sort((a, b) => a.x - b.x);
    const rowEnd = [-Infinity, -Infinity];
    for (const { st, x } of named) {
      const w = ctx.measureText(st.e.label).width + 28, h = 40;
      const row = x - w / 2 >= rowEnd[0] + 8 ? 0 : 1;
      rowEnd[row] = x + w / 2;
      out.push({ id: st.e.id, text: st.e.label, x: x - w / 2, y: GROUND_PX + 12 + row * (h + 6), w, h });
    }
    return out;
  }

  tags(people) {
    const { ctx, C } = this;
    ctx.save();
    for (const b of this.tagBoxes(people)) {
      const shirt = people.find((st) => st.e.id === b.id)?.e.look?.shirt || C.body;
      ctx.fillStyle = C.bubble; ctx.strokeStyle = shirt; ctx.lineWidth = 4;
      ctx.beginPath(); ctx.roundRect(b.x, b.y, b.w, b.h, 20); ctx.fill(); ctx.stroke();
      ctx.fillStyle = C.ink; ctx.textAlign = 'center'; ctx.textBaseline = 'middle';
      ctx.fillText(b.text, b.x + b.w / 2, b.y + b.h / 2 + 1);
    }
    ctx.restore();
  }

  effect(f, st) {
    const { ctx, M, C } = this, j = st.joints;
    const [hx, hy] = M(j.head), r = j.r * M.s;
    ctx.save(); ctx.strokeStyle = C.ink; ctx.lineCap = 'round';
    if (f.kind === 'mark') {     // the surprise mark above the head
      ctx.fillStyle = C.ink; ctx.font = `800 ${Math.round(r * 2.2)}px Segoe UI, sans-serif`; ctx.textAlign = 'center';
      ctx.fillText('!', hx - st.f * r * 1.6, hy - r * 1.6 - 10 * Math.sin(Math.PI * f.k / 0.45));
    } else {                     // hit_reacts: short impact strokes at the top of the head
      ctx.lineWidth = M.s * 0.02;
      for (let i = -2; i <= 2; i++) {
        const a = -Math.PI / 2 + i * 0.45, r0 = r * 1.25, r1 = r * (1.6 + f.k * 2);
        ctx.beginPath(); ctx.moveTo(hx + Math.cos(a) * r0, hy + Math.sin(a) * r0);
        ctx.lineTo(hx + Math.cos(a) * r1, hy + Math.sin(a) * r1); ctx.stroke();
      }
    }
    ctx.restore();
  }

  bubbleBox(b, S) {
    const st = S[b.actor], j = st.joints, M = this.M;
    const [hx, hy] = M([j.head[0], j.head[1] + j.r]);
    this.ctx.font = '600 52px Segoe UI, sans-serif';
    const w = Math.max(160, this.ctx.measureText(b.full).width + 64), h = 96;
    const dir = b.to && S[b.to] ? Math.sign(S[b.to].x - st.x) || 1 : 1;
    const x = clamp(hx + dir * 40 - w / 2, 20, W - w - 20), y = hy - 70 - h;
    return { x, y, w, h, tip: [hx, hy - 8] };
  }

  bubble(b, S) {
    const { ctx, C } = this, bx = this.bubbleBox(b, S);
    ctx.save(); ctx.fillStyle = C.bubble; ctx.strokeStyle = C.ink; ctx.lineWidth = 4; ctx.lineJoin = 'round';
    const tx = clamp(bx.tip[0], bx.x + 30, bx.x + bx.w - 30);
    ctx.beginPath(); ctx.roundRect(bx.x, bx.y, bx.w, bx.h, 26); ctx.fill(); ctx.stroke();
    ctx.beginPath(); ctx.moveTo(tx - 16, bx.y + bx.h - 2); ctx.lineTo(bx.tip[0], bx.tip[1]); ctx.lineTo(tx + 16, bx.y + bx.h - 2);
    ctx.fill(); ctx.stroke();
    ctx.fillStyle = C.ink; ctx.textBaseline = 'middle'; ctx.textAlign = 'left';
    ctx.fillText(b.text, bx.x + 28, bx.y + bx.h / 2 + 2);
    ctx.restore();
  }

  // ---- checks for tests (the same state the frame draws) -------------------------------------------------------
  probe(t) {
    const { S, bubbles } = this.state(t), out = { t, ents: {} };
    for (const [id, st] of Object.entries(S)) {
      const o = { asset: st.e.asset, x: st.x, f: st.f, posture: st.k >= 1 ? st.to : `${st.from}>${st.to}` };
      if (st.joints) {
        o.pelvis = st.joints.pelvis; o.head = st.joints.head; o.headTop = [st.joints.head[0], st.joints.head[1] + st.joints.r];
        o.feet = [st.joints.lFoot, st.joints.rFoot];
        const c = st.carrier && S[st.carrier];
        if (c && c.frame && st.seatK == null) o.saddleGap = Math.hypot(o.pelvis[0] - c.frame.saddle[0], o.pelvis[1] - c.frame.saddle[1]);
        o.reacting = !!st.react; o.talking = st.talk != null;
      }
      if (st.e.asset === 'apple' || st.e.asset === 'box' || PROPS.includes(st.e.asset)) { o.pos = st.pos; o.hanging = st.hanging; o.holder = st.holder; }
      if (st.joints) { o.hands = [st.joints.rHand, st.joints.lHand]; o.lift = st.lift || 0; }
      if (st.frame) o.saddle = st.frame.saddle;
      out.ents[id] = o;
    }
    out.bubbles = bubbles.map((b) => ({ ...b, box: this.bubbleBox(b, S) }));
    out.tags = this.tagBoxes(Object.values(S).filter((st) => st.e.asset === 'person'));
    return out;
  }
}

export async function loadAssets(base = './assets/') {
  const names = ['person', 'tree', 'horse', 'village', 'apple', ...PROPS];
  const got = await Promise.all(names.map((n) => fetch(`${base}${n}.json`).then((r) => r.json())));
  return Object.fromEntries(names.map((n, i) => [n, got[i]]));
}
