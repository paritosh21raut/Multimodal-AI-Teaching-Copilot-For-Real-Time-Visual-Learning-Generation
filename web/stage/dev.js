// Dev hooks for the stage: line-ups, prop grids and backdrop panels for the contact sheets, the kit check and probes
// for the browser tests. Sheet patches are made here (dev only); lecture patches come from Python.
import { BACKDROPS, PROPS, SPECIES } from './kit/index.js';
import { clip, clipNames, duration, sample } from './motion.js';
import { castIds, castRow, defaultHeight, pose } from './people.js';
import { Stage, loadStage } from './stage.js';
import { VH, VW } from './style.js';
import { NS } from './svg.js';

export let stage = null, cat = null;
export const ready = (async () => {
  cat = await loadStage();
  stage = new Stage(document.getElementById('host'));
})();

// a still: no ease from the last patch shown, no entrance fade (each sheet cell stands alone)
export function show(patch, t = 0) { stage.still = true; stage.apply(patch); stage.render(t); return stage.player; }
// live: eases and entrances run on wall time since the patch arrived (t0 = when it was applied)
export function play(patch, t0, t) { stage.still = false; if (patch) stage.apply(patch); stage.render(t0 + t); return stage.player; }

// a frame whose ground sits at 75 % of the height (director rule) and whose width spans x0..x1
const groundFrame = (x0, x1, top) => {
  const s = Math.min(VW * 0.94 / (x1 - x0), VH * 0.68 / top);
  return { cx: (x0 + x1) / 2, cy: (VH * 0.75 - VH / 2) / s, s };
};

// one person in six poses: walk, push, throw, carry, sit, jump
export function lineup(id) {
  const L = castRow(id), h = defaultHeight(L), gap = 1.6 * Math.max(1, h / 1.78) + 0.05, ents = [], tracks = [], overlays = [];
  const pid = (k) => `${id}_${k}`;
  const xs = [0, 1, 2, 3, 4, 5].map((i) => (i - 2.5) * gap);
  const push = clip('Push_Loop'), thr = clip('OverhandThrow');
  // walk
  ents.push({ id: pid('walk'), draw: `cast:${id}`, xform: { x: xs[0] } });
  tracks.push({ id: pid('walk'), kind: 'clip', clip: 'Walk_Loop', t_offset: 0.25 });
  // push: hands on the crate's near face (IK, padded by the hand)
  const reach = push.reach_x * h, boxH = Math.min(1.4, push.hands_h.max * h + 0.14);
  ents.push({ id: pid('crate'), draw: 'crate', xform: { x: xs[1] + 0.25 + 0.4, size: [0.8, boxH] } });
  ents.push({ id: pid('push'), draw: `cast:${id}`, xform: { x: xs[1] + 0.25 - reach } });
  tracks.push({ id: pid('push'), kind: 'clip', clip: 'Push_Loop', t_offset: 0.4 });
  for (const hand of ['r', 'l']) tracks.push({ id: pid('push'), kind: 'ik', hand, target: { entity: pid('crate'), anchor: 'face_l', dy: (push.hands_h[hand] * h) - boxH / 2 }, pad: true });
  // throw: the ball in the hand at the release frame
  const tr = thr.events.release / (thr.frames - 1) * thr.dur;
  ents.push({ id: pid('throw'), draw: `cast:${id}`, xform: { x: xs[2] - 0.3 } }, { id: pid('ball'), draw: 'ball' });
  tracks.push({ id: pid('throw'), kind: 'clip', clip: 'OverhandThrow', t_offset: tr, rate: 0 },
    { id: pid('ball'), kind: 'socket', parent: pid('throw'), socket: 'hand_r', child_socket: 'centre', t0: 0 });
  // carry
  ents.push({ id: pid('carry'), draw: `cast:${id}`, xform: { x: xs[3] - 0.15 } }, { id: pid('box'), draw: 'crate', xform: { size: [0.42, 0.34] } });
  tracks.push({ id: pid('carry'), kind: 'clip', clip: 'Walk_Carry_Loop', t_offset: 0.5 },
    { id: pid('box'), kind: 'socket', parent: pid('carry'), socket: 'hands', child_socket: 'centre', offset: [0.1, 0.14], t0: 0 });  // the hands under the bottom edge
  // sit: on a chair whose seat is where the clip's thighs are (the socket hips at that frame), feet on the floor
  const seat = pose(sample('Sitting_Idle_Loop', 0.3, true), { x: 0, y: 0, h, dir: 1 }, L).hipsLocal[1];
  ents.push({ id: pid('chair'), draw: 'chair', xform: { x: xs[4] - 0.1, size: [Math.max(0.4, 0.26 * h), seat / cat.props.chair.anchors.seat[1]] } });
  ents.push({ id: pid('sit'), draw: `cast:${id}`, xform: { x: xs[4] } });
  tracks.push({ id: pid('sit'), kind: 'clip', clip: 'Sitting_Idle_Loop', t_offset: 0.3 },
    { id: pid('sit'), kind: 'socket', parent: pid('chair'), socket: 'seat_back', child_socket: 'hips', inherit: false, t0: 0 });  // back against the backrest
  // jump: mid-air
  ents.push({ id: pid('jump'), draw: `cast:${id}`, xform: { x: xs[5], y: 0.35 } });
  tracks.push({ id: pid('jump'), kind: 'clip', clip: 'Jump_Loop', t_offset: 0.2 });
  ['walk', 'push', 'throw', 'carry', 'sit', 'jump'].forEach((w, i) => overlays.push({ kind: 'words', at: [xs[i], -0.22], text: w, size: 26, anchor: 'middle', color: '#5d6672' }));
  overlays.push({ kind: 'words', screen: [40, 60], text: `${id} · ${L.sex === 'f' ? 'f' : 'm'}${L.child ? ' · child' : ''} · ${h} m`, size: 30, weight: 600 });
  const s = VW * 0.97 / (xs[5] - xs[0] + 1.5);  // tight: the ground low, so faces are big enough to judge
  return { rev: 1, view: 'side', backdrop: { id: 'outdoor' }, entities: ents, tracks, overlays, frame: { cx: (xs[0] + xs[5]) / 2 + 0.1, cy: (VH * 0.86 - VH / 2) / s, s } };
}

// props side by side at true relative size, with a scale bar
export function propRow(ids, title = '') {
  const ents = [], overlays = [];
  let x = 0;
  const sizes = ids.map((id) => cat.props[id].size_m);
  const gap = Math.max(...sizes.map((s) => s[0])) * 0.25 + 0.02;
  const pos = ids.map((id, i) => { const w = sizes[i][0], c = x + w / 2; x += w + gap; return c; });
  const x1 = x - gap, top = Math.max(...sizes.map((s) => s[1]));
  const big = cat.props[ids[0]].category === 'sky';
  ids.forEach((id, i) => {
    const s = sizes[i], y = big ? 0.5 : id === 'swing_seat' ? s[1] + 0.05 : 0;  // the seat hangs from its pivot
    ents.push({ id: 'p_' + id, draw: id, xform: { x: pos[i], y }, state: id === 'bulb' || id === 'lamp_post' ? { on: true } : id === 'rope' ? { marker: true } : {} });
    overlays.push({ kind: 'words', at: [pos[i], -0.04 * Math.max(top, x1 / 8)], text: id.replace(/_/g, ' '), size: 24, anchor: 'middle', color: '#33363d' });
  });
  // the bar: the largest power of ten not wider than a third of the row
  const span = Math.max(x1, top * 1.6), bar = Math.pow(10, Math.floor(Math.log10(span / 3)));
  const by = -0.14 * Math.max(top, x1 / 8);
  overlays.push({ kind: 'dim', a: [0, by], b: [bar, by], text: bar >= 1 ? `${bar} m` : `${Math.round(bar * 100)} cm`, ly: 40, role: 'ink' });
  if (title) overlays.push({ kind: 'words', screen: [40, 60], text: title, size: 30, weight: 600 });
  const f = groundFrame(-0.05 * x1, x1 * 1.05, top * 1.15);
  f.cy -= 0.12 * top;
  return { rev: 1, view: 'side', backdrop: { id: 'lab_bench' }, entities: ents, overlays, frame: f };
}

// the props in rows of similar size (each row on its own scale, shown by its bar)
export function propGroups(per = 8) {
  const ids = Object.keys(cat.props).filter((id) => cat.props[id].category !== 'effect');
  const key = (id) => Math.max(...cat.props[id].size_m);
  const sky = ids.filter((id) => cat.props[id].category === 'sky');
  const rest = ids.filter((id) => cat.props[id].category !== 'sky').sort((a, b) => key(a) - key(b));
  const rows = [];
  for (let i = 0; i < rest.length; i += per) rows.push(rest.slice(i, i + per));
  rows.push([...sky, 'rain'].filter((id) => cat.props[id]));
  return rows;
}

export function backdropPanel(id, state = {}) {
  const person = { id: 'b_man', draw: 'cast:man', xform: { x: 0 } };
  return { rev: 1, view: 'side', backdrop: { id, state }, entities: [person], tracks: [{ id: 'b_man', kind: 'clip', clip: 'Idle_Loop' }],
    overlays: [{ kind: 'words', screen: [40, 60], text: `${id}${Object.keys(state).length ? ' · ' + JSON.stringify(state) : ''}`, size: 30, weight: 600 }],
    frame: groundFrame(-5, 5, 3.2) };
}

// every catalog id has a draw function and every draw function a catalog row; each draws something
export function checkKit() {
  const out = { props: [], backdrops: [], species: [], empty: [] };
  const two = (a, b) => [a.filter((x) => !b.includes(x)), b.filter((x) => !a.includes(x))];
  const [p1, p2] = two(Object.keys(cat.props), Object.keys(PROPS)), [b1, b2] = two(Object.keys(cat.backdrops), Object.keys(BACKDROPS));
  const [s1, s2] = two(Object.keys(cat.species), Object.keys(SPECIES));
  out.props = { noDraw: p1, noRow: p2 }; out.backdrops = { noDraw: b1, noRow: b2 }; out.species = { noDraw: s1, noRow: s2 };
  for (const id of Object.keys(PROPS)) {
    const r = cat.props[id]; if (!r) continue;
    const prims = PROPS[id].draw(r.size_m[0], r.size_m[1], {}, { t: 1, x: 0 });
    if (!prims.length) out.empty.push(id);
  }
  for (const id of Object.keys(BACKDROPS)) if (!BACKDROPS[id](VW, VH, 750, {}, 'chk').length) out.empty.push(id);
  // species: draw one each through the stage
  show({ rev: 1, backdrop: 'outdoor', entities: Object.keys(SPECIES).map((s, i) => ({ id: 'sp_' + s, draw: 'species:' + s, xform: { x: i * 2 - 5, y: s === 'bird' || s === 'fish' ? 1 : 0 } })), frame: groundFrame(-6, 6, 3) }, 1);
  for (const s of Object.keys(SPECIES)) if (!document.querySelector(`[data-id="sp_${s}"] > g`).children.length) out.empty.push('species:' + s);
  return out;
}

// test probe: hands vs IK targets (px at stage size), the current frame
export function probe(id) {
  const p = stage.player.probe(id);
  if (!p) return null;
  const px = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1]) * p.s;
  const out = {};
  for (const h of ['r', 'l']) if (p.targets[h]) out[h] = px(p.hands[h], p.targets[h]);
  return { ik: out, hands: p.hands, sockets: p.sockets, J: p.J };
}

// average render time (ms) over n frames
export function perf(patch, n = 120, t0 = 0) {
  stage.apply(patch);
  stage.render(t0);
  const a = performance.now();
  for (let i = 1; i <= n; i++) stage.render(t0 + i / 60);
  return (performance.now() - a) / n;
}

// 6 people + 30 props, moving
export function busyPatch() {
  const ids = castIds().slice(0, 6), props = Object.keys(cat.props).filter((p) => cat.props[p].category !== 'sky' && Math.max(...cat.props[p].size_m) < 3).slice(0, 30);
  const ents = [], tracks = [];
  ids.forEach((id, i) => {
    ents.push({ id: 'w' + i, draw: `cast:${id}` });
    const v = clip('Walk_Loop').stride_mps * defaultHeight(castRow(id));
    tracks.push({ id: 'w' + i, kind: 'path', samples: [[0, -6 + i * 0.8, 0], [10, -6 + i * 0.8 + v * 10, 0]] }, { id: 'w' + i, kind: 'clip', clip: 'Walk_Loop', lock: true });
  });
  props.forEach((p, i) => ents.push({ id: 'q' + i, draw: p, xform: { x: -7 + (i % 15) * 1.0, y: i < 15 ? 0 : 0, row: i < 15 ? 'near' : 'far' } }));
  return { rev: 1, backdrop: 'park', entities: ents, tracks, frame: groundFrame(-8, 8, 3) };
}

export const info = () => ({ clips: clipNames().length, cast: castIds(), dur: (n) => duration(n), svgNS: NS });
