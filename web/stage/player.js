// Plays a `stage.patch` (contract §8): entities, tracks (path, clip, ik, socket, tween), overlays, frame. The browser
// draws; it never decides positions: everything here is a pure function of the patch and the stage time t, so a
// replay at the same t draws the same picture. One persistent <g> per entity; a frame only changes attributes.
import * as animals from './animals.js';
import { BACKDROPS, PROPS } from './kit/index.js';
import { blend, clip as clipRow, hasClip, sample } from './motion.js';
import { drawOverlays, at as sampleAt } from './overlays.js';
import * as people from './people.js';
import { B, VH } from './style.js';
import { F, el, markup, reconcile, setAttr, setMarkup } from './svg.js';

const FAR = 0.6;  // the far row: drawn behind, at 0.6 scale, standing a little up the backdrop
const ease3 = (k) => (k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2);
const rotv = (p, deg) => { const a = (deg * Math.PI) / 180, c = Math.cos(a), s = Math.sin(a); return [p[0] * c - p[1] * s, p[0] * s + p[1] * c]; };
const add = (a, b) => [a[0] + b[0], a[1] + b[1]];

export class Player {
  // panes: [{svg, bd, world, far, near, over, w}] from the stage; catalog: {props, backdrops, species} rows by id
  constructor(panes, catalog, top = null) {
    this.panes = panes; this.cat = catalog; this.top = top; this.ents = new Map(); this.patch = null; this.cam = []; this.applyAt = null;
  }

  apply(patch) {
    const prevCam = this.cam.map((c) => c && c.now);
    this.patch = patch;
    this.byId = {};
    const tracks = patch.tracks || [];
    for (const e of patch.entities || []) this.byId[e.id] = { e, path: null, clips: [], ik: [], socket: [], tween: [] };
    for (const tr of tracks) {
      const s = this.byId[tr.id];
      if (!s) continue;
      if (tr.kind === 'path') s.path = tr;
      else if (tr.kind === 'clip') s.clips.push(tr);
      else if (tr.kind === 'ik') s.ik.push(tr);
      else if (tr.kind === 'socket') s.socket.push(tr);
      else if (tr.kind === 'tween') s.tween.push(tr);
    }
    for (const s of Object.values(this.byId)) for (const k of ['clips', 'socket']) s[k].sort((a, b) => (a.t0 || 0) - (b.t0 || 0));  // the latest started wins
    // DOM: one <g> per entity, kept across patches
    for (const [id, d] of this.ents) if (!this.byId[id]) { d.g.remove(); this.ents.delete(id); }
    for (const e of patch.entities || []) {
      const pane = this.panes[e.pane || 0], layer = (e.xform && e.xform.row === 'far') ? pane.far : pane.near;
      let d = this.ents.get(e.id);
      if (!d || d.draw !== e.draw || d.layer !== layer) {
        if (d) d.g.remove();
        const g = el('g', { 'data-id': e.id, class: 'st-ent' }, layer);
        d = { g, inner: el('g', {}, g), draw: e.draw, layer, key: null };
        this.ents.set(e.id, d);
      } else layer.appendChild(d.g);  // keep the patch's order (later = in front)
    }
    // backdrops / frames per pane
    const panes = patch.view === 'split' ? patch.panes : [{ backdrop: patch.backdrop, frame: patch.frame, camera: patch.camera }];
    this.paneDefs = panes;
    this.cam = panes.map((p, i) => ({ def: p, from: prevCam[i] || null, now: null }));
    this.applyAt = null;
  }

  // ---------- time ----------
  time(t) { const p = this.patch && this.patch.period; return p ? ((t % p) + p) % p : t; }

  camera(i, tRaw) {  // keyframes on the scene's (wrapped) time; the ease from the last patch on wall time
    const c = this.cam[i], f = c.def.frame || { cx: 0, cy: 2, s: 200 }, t = this.time(tRaw);
    let cur = { cx: f.cx, cy: f.cy, s: f.s };
    for (const k of c.def.camera || []) {
      if (t <= k.t) break;
      const u = Math.min(1, (t - k.t) / Math.max(0.001, (k.ease_ms || 600) / 1000)), e = ease3(u);
      cur = { cx: cur.cx + (k.cx - cur.cx) * e, cy: cur.cy + (k.cy - cur.cy) * e, s: cur.s + (k.s - cur.s) * e };
    }
    if (c.from && this.applyAt != null && f.ease_ms) {  // a new patch eases from where the camera was
      const u = Math.min(1, (tRaw - this.applyAt) / (f.ease_ms / 1000));
      if (u < 1) { const e = ease3(Math.max(0, u)); cur = { cx: c.from.cx + (cur.cx - c.from.cx) * e, cy: c.from.cy + (cur.cy - c.from.cy) * e, s: c.from.s + (cur.s - c.from.s) * e }; }
    }
    c.now = cur;
    return cur;
  }

  // ---------- placement (world metres) ----------
  base(id, t) {
    const s = this.byId[id], e = s.e, x = e.xform || {};
    const o = { x: x.x || 0, y: x.y || 0, rot: x.rot || 0, dir: x.dir || 1, scale: x.scale || 1, opacity: x.dim ? 0.45 : 1,
      state: { ...(e.state || {}) }, size: x.size || null };
    if (s.path) {
      const v = sampleAt(s.path.samples, t);
      o.x = v[0]; o.y = v[1]; if (v.length > 2) o.rot = v[2];
      const back = sampleAt(s.path.samples, t - 0.05);
      o.speed = Math.hypot(v[0] - back[0], v[1] - back[1]) / 0.05;
      o.dist = Math.abs(v[0] - s.path.samples[0][1]);
    }
    for (const tw of s.tween) {
      if (t < tw.t0) continue;
      const u = tw.t1 > tw.t0 ? Math.min(1, (t - tw.t0) / (tw.t1 - tw.t0)) : 1, k = tw.ease === 'linear' ? u : ease3(u);
      const v = typeof tw.from === 'number' ? tw.from + (tw.to - tw.from) * k : (k < 1 ? tw.from : tw.to);
      if (tw.prop.startsWith('state.')) o.state[tw.prop.slice(6)] = v; else o[tw.prop] = v;
    }
    if (x.row === 'far') { o.far = true; o.scale *= FAR; o.y += (this.regions(e.pane).far_y || 0.9); }
    return o;
  }

  regions(pane = 0) {
    const d = this.paneDefs[pane] || this.paneDefs[0], bd = d && d.backdrop && this.cat.backdrops[d.backdrop.id || d.backdrop];
    return (bd && bd.regions) || {};
  }

  kind(id) { const d = this.byId[id].e.draw; return d.startsWith('cast:') ? 'person' : d.startsWith('species:') ? 'animal' : 'prop'; }

  // the entity's placement at t (socket attachments resolved); memoised per frame
  place(id, t) {
    const key = id + '@' + t;
    if (this.memo.has(key)) return this.memo.get(key);
    if (this.visiting.has(key)) return this.base(id, t);
    this.visiting.add(key);
    const o = this.base(id, t);
    const sk = this.byId[id].socket.filter((s) => t >= (s.t0 || 0)).pop();
    const path = this.byId[id].path;
    const free = sk && sk.t1 != null && t > sk.t1 && path && path.samples[0][0] <= t;  // let go onto its own path (a throw)
    if (sk && !free && this.byId[sk.parent]) {
      const tt = sk.t1 != null ? Math.min(t, sk.t1) : t;  // after t1 the child stays where it was let go
      const pp = this.place(sk.parent, tt), pt = this.anchorWorld(sk.parent, sk.socket, tt, sk.offset);
      if (pt) {
        const rot = sk.inherit === false ? o.rot : pp.rot;
        const local = sk.child_socket ? this.localSocket(id, sk.child_socket, tt, { ...o, rot: 0 }) : [0, 0];
        const q = add(pt, rotv([-local[0], -local[1]], rot));
        o.x = q[0]; o.y = q[1]; o.rot = rot; o.attached = true;
      }
    }
    this.visiting.delete(key);
    this.memo.set(key, o);
    return o;
  }

  sizeOf(id, o) {
    const e = this.byId[id].e, row = this.cat.props[e.draw];
    return o.size || (e.xform && e.xform.size) || (row ? row.size_m : [1, 1]);
  }

  // a named point of an entity in its own frame (unrotated, at origin) in metres
  localSocket(id, name, t, o) {
    const k = this.kind(id);
    if (k === 'person') {
      const ps = this.posePerson(id, t, { ...o, x: 0, y: 0, rot: 0 }, false);
      return name === 'lap' ? ps.lapLocal : ps.sockets[name] || [0, 0];
    }
    if (k === 'prop') {
      const row = this.cat.props[this.byId[id].e.draw], a = (row && row.anchors && row.anchors[name]) || [0, 0], [w, h] = this.sizeOf(id, o);
      return [a[0] * w * o.dir * o.scale, a[1] * h * o.scale];
    }
    return [0, 0];
  }

  // a socket / anchor in world metres; offset [dx, dy] in the entity's frame (dx along its facing for a person)
  anchorWorld(id, name, t, offset) {
    const o = this.place(id, t), k = this.kind(id), off = offset || [0, 0];
    if (k === 'person') {
      const ps = this.posePerson(id, t, o, true), p = ps.sockets[name] || [o.x, o.y];
      return add(p, rotv([off[0] * o.dir, off[1]], o.rot));
    }
    if (k === 'animal') {
      const sp = this.byId[id].e.draw.slice(8), p = animals.sockets({ kind: sp, x: o.x, y: o.y, dir: o.dir, scale: o.scale })[name] || [o.x, o.y];
      return add(p, [off[0] * o.dir, off[1]]);
    }
    const local = this.localSocket(id, name || 'bottom', t, o);
    return add([o.x, o.y], rotv(add(local, [off[0], off[1]]), o.rot));
  }

  resolve(a, t) {
    if (!a) return null;
    if (Array.isArray(a)) return a;
    if (!this.byId[a.entity]) return null;
    return this.anchorWorld(a.entity, a.anchor || a.socket, t, [a.dx || 0, a.dy || 0]);
  }

  // ---------- people ----------
  clipPose(id, t) {
    const cs = this.byId[id].clips.filter((c) => t >= (c.t0 || 0) && (c.t1 == null || t < c.t1));
    const cur = cs.pop() || { clip: 'Idle_Loop', t0: 0 };
    const fr = (c) => {
      const name = hasClip(c.clip) ? c.clip : 'Idle_Loop', row = clipRow(name);
      const loop = c.loop != null ? c.loop : !!(row && row.loop);
      return sample(name, (c.t_offset || 0) + (t - (c.t0 || 0)) * (c.rate == null ? 1 : c.rate), loop, !!c.mirror);
    };
    let pose = fr(cur);
    const prev = cs.pop();
    if (cur.blend && prev && t - cur.t0 < cur.blend) pose = blend(fr(prev), pose, ease3((t - cur.t0) / cur.blend));
    return { fr: pose, lock: !!cur.lock };
  }

  posePerson(id, t, o, withIk) {
    const key = id + '#' + t + (withIk ? 'k' : '') + (o.x === 0 && o.y === 0 && !o.rot ? 'o' : '');
    if (this.memo.has(key)) return this.memo.get(key);
    const e = this.byId[id].e, L = people.castRow(e.draw.slice(5));
    const h = (e.xform && e.xform.h) || people.defaultHeight(L);
    const { fr, lock } = this.clipPose(id, t);
    const ik = {};
    if (withIk) for (const k of this.byId[id].ik) {
      if (t < (k.t0 || 0) || (k.t1 != null && t > k.t1)) continue;
      let p = this.resolve(k.target, t);
      if (!p) continue;
      if (k.pad) p = [p[0] - o.dir * people.handRadius(L, h * o.scale), p[1]];
      ik[k.hand] = p;
    }
    const ps = people.pose(fr, { x: o.x, y: o.y, rot: o.rot, dir: o.dir, h: h * o.scale, shadow: !o.attached && e.shadow !== false, groundY: o.far ? o.y : 0 }, L, ik, lock);
    ps.ikTargets = ik;
    this.memo.set(key, ps);
    return ps;
  }

  // ---------- draw ----------
  render(tRaw) {
    if (!this.patch) return;
    if (this.applyAt == null) this.applyAt = tRaw;
    const t = this.time(tRaw);
    this.t = t; this.memo = new Map(); this.visiting = new Set();
    const figures = this.panes.map(() => []);
    this.drawn = {};
    for (let i = 0; i < this.paneDefs.length; i++) {
      const pane = this.panes[i], cam = this.camera(i, tRaw), def = this.paneDefs[i];
      pane.proj = (p) => [pane.w / 2 + (p[0] - cam.cx) * cam.s, VH / 2 - (p[1] - cam.cy) * cam.s];
      setAttr(pane.world, 'transform', `translate(${F(pane.w / 2 - cam.cx * cam.s)},${F(VH / 2 + cam.cy * cam.s)}) scale(${(cam.s / B).toFixed(5)})`);
      const bd = def.backdrop && (typeof def.backdrop === 'string' ? { id: def.backdrop } : def.backdrop);
      if (bd && BACKDROPS[bd.id]) setMarkup(pane.bd, BACKDROPS[bd.id](pane.w, VH, pane.proj([0, 0])[1], bd.state || {}, `sky${i}`));
    }
    for (const e of this.patch.entities || []) {
      const d = this.ents.get(e.id), o = this.place(e.id, t), k = this.kind(e.id);
      setAttr(d.g, 'opacity', String(o.opacity));
      if (k === 'person') {
        const ps = this.posePerson(e.id, t, o, true), L = people.castRow(e.draw.slice(5));
        setAttr(d.g, 'transform', '');
        reconcile(d.inner, people.draw(ps, L));
        const bb = people.bounds(ps), pane = this.panes[e.pane || 0];
        const a = pane.proj([bb[0], bb[3]]), b = pane.proj([bb[2], bb[1]]);
        figures[e.pane || 0].push([a[0], a[1], b[0], b[1]]);
        this.drawn[e.id] = ps;
      } else if (k === 'animal') {
        const kind = e.draw.slice(8);
        reconcile(d.inner, animals.draw({ kind, x: o.x, y: o.y, t, dir: o.dir, speed: o.state.speed != null ? o.state.speed : o.speed, dist: o.dist,
          pose: o.state.pose || ((o.speed || 0) > 0.05 ? 'walk' : 'stand'), scale: o.scale, color: o.state.color }));
      } else {
        const kit = PROPS[e.draw];
        if (!kit) continue;
        const [w, h] = this.sizeOf(e.id, o);
        setAttr(d.g, 'transform', `translate(${F(o.x * B)},${F(-o.y * B)})${o.rot ? ` rotate(${F(-o.rot)})` : ''}${o.dir < 0 || o.scale !== 1 ? ` scale(${F(o.dir * o.scale * 100) / 100},${F(o.scale * 100) / 100})` : ''}`);
        const prims = kit.draw(w, h, o.state, { t, x: o.x });
        if (kit.dynamic) reconcile(d.inner, prims);
        else { const key = JSON.stringify([w, h, o.state]); if (d.key !== key) { d.key = key; setMarkup(d.inner, markup(prims)); } }
      }
    }
    // overlays per pane; pane 'all' (and the patch's badges) on the stage-wide layer
    const all = [...(this.patch.overlays || []).filter((o) => o.pane === 'all'), ...(this.patch.badges || []).map((b) => ({ kind: 'badge', text: b }))];
    if (this.top) {
      const { prims } = drawOverlays(all, { t, w: this.panes.reduce((a, p) => a + p.w, 0), h: VH, proj: (p) => p, figures: figures.flat(), resolve: () => null, track: () => null });
      reconcile(this.top, prims);
    }
    for (let i = 0; i < this.paneDefs.length; i++) {
      const pane = this.panes[i];
      const list = (this.patch.overlays || []).filter((o) => (o.pane || 0) === i);
      const { prims } = drawOverlays(list, { t, w: pane.w, h: VH, proj: pane.proj, figures: figures[i],
        resolve: (a) => this.resolve(a, t), track: (id) => this.byId[id] && this.byId[id].path && this.byId[id].path.samples });
      reconcile(pane.over, prims);
    }
  }

  // test hooks: world positions of hands / IK targets / feet for the current frame
  probe(id) {
    const ps = this.drawn && this.drawn[id];
    if (!ps) return null;
    const pane = this.panes[this.byId[id].e.pane || 0], cam = this.cam[this.byId[id].e.pane || 0].now;
    return { s: cam.s, hands: { r: ps.sockets.hand_r, l: ps.sockets.hand_l }, targets: ps.ikTargets, J: ps.J, sockets: ps.sockets,
      screen: (p) => pane.proj(p) };
  }
}

export const clipOf = clipRow;
