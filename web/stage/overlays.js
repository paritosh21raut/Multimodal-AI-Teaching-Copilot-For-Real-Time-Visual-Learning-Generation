// Overlays (contract §8): arrow, path (dotted trajectory), label (symbol with subscripts), dim (dimension line),
// line (dashed construction / rest line), card, badge, clock, energy bars, words. Drawn in the pane's screen space
// (fixed sizes at any zoom); a label is nudged off the figures and off the labels placed before it.
import { FONT, LABEL_MIN, T, roleColour } from './style.js';
import { F, P, norm, sym } from './svg.js';

const textAttrs = (x, y, size, fill, ex = {}) => ({ x: F(x), y: F(y), 'font-size': F(size), fill, 'paint-order': 'stroke',
  stroke: T.halo, 'stroke-width': '6', 'stroke-linejoin': 'round', ...ex });
export const symbolText = (x, y, s, color, size = 42, anchor = 'start') => ['text', { ...textAttrs(x, y, Math.max(LABEL_MIN, size), color,
  { 'text-anchor': anchor, 'font-family': FONT.symbol, 'font-style': 'italic', stroke: '#ffffff', 'stroke-width': '8' }), html: sym(s) }];
export const wordsText = (x, y, s, { size = 30, anchor = 'start', color = T.ink, weight = 500, halo = true } = {}) => ['text', {
  ...textAttrs(x, y, Math.max(LABEL_MIN, size), color, { 'text-anchor': anchor, 'font-family': FONT.words, 'font-weight': String(weight) }),
  ...(halo ? {} : { stroke: 'none' }), html: s }];

function arrowPrims(a, b, color, { dashed = false, w = 7, head = 26 } = {}) {
  const dx = b[0] - a[0], dy = b[1] - a[1], len = Math.hypot(dx, dy);
  if (len < 6) return [];
  const ux = dx / len, uy = dy / len, H = Math.min(head, len * 0.6), bx = b[0] - ux * H, by = b[1] - uy * H, px = -uy * H * 0.55, py = ux * H * 0.55;
  return [P.line(a, [bx, by], w, color, dashed ? { 'stroke-dasharray': '14 10' } : {}),
    P.path(`M${F(b[0])},${F(b[1])}L${F(bx + px)},${F(by + py)}L${F(bx - px)},${F(by - py)}Z`, color)];
}

// a value from samples [[t, ...v]] at time t (linear; held at the ends)
export function at(samples, t) {
  if (!samples || !samples.length) return null;
  if (t <= samples[0][0]) return samples[0].slice(1);
  const n = samples.length;
  if (t >= samples[n - 1][0]) return samples[n - 1].slice(1);
  let lo = 0, hi = n - 1;
  while (hi - lo > 1) { const m = (lo + hi) >> 1; if (samples[m][0] <= t) lo = m; else hi = m; }
  const a = samples[lo], b = samples[hi], k = (t - a[0]) / (b[0] - a[0] || 1);
  return a.slice(1).map((v, i) => v + (b[i + 1] - v) * k);
}

const overlaps = (a, b) => a[0] < b[2] && a[2] > b[0] && a[1] < b[3] && a[3] > b[1];
// estimated text box [x0, y0, x1, y1] for a label at its baseline
function box(x, y, s, size, anchor) {
  const plain = String(s).replace(/_/g, '');
  const w = plain.length * size * 0.55 + 8, x0 = anchor === 'middle' ? x - w / 2 : anchor === 'end' ? x - w : x;
  return [x0, y - size * 0.85, x0 + w, y + size * 0.25];
}

// place a label at (x, y) or the nearest nudged spot clear of the figures and placed labels
function nudge(x, y, s, size, anchor, ctx) {
  const tries = [[0, 0]];
  for (let k = 1; k <= 8; k++) tries.push([0, -k * 16], [k * 16, 0], [-k * 16, 0], [0, k * 16]);
  for (const [dx, dy] of tries) {
    const b = box(x + dx, y + dy, s, size, anchor);
    if (!ctx.obstacles.some((o) => overlaps(b, o))) { ctx.obstacles.push(b); return [x + dx, y + dy]; }
  }
  ctx.obstacles.push(box(x, y, s, size, anchor));
  return [x, y];
}

// list: overlays; ctx: {t, proj(world [x, y]) -> screen, resolve(anchor) -> world [x, y] | null, figures: [screen boxes],
// track(entityId) -> path samples, w, h}
export function drawOverlays(list, ctx) {
  const out = [], labels = [];
  ctx.obstacles = [...ctx.figures];
  const P_ = (anchor) => { const p = ctx.resolve(anchor); return p ? ctx.proj(p) : null; };
  for (const o of list) {
    if (o.t0 != null && ctx.t < o.t0) continue;
    if (o.t1 != null && ctx.t > o.t1) continue;
    const c = roleColour(o.role || o.color);
    if (o.kind === 'arrow') {
      const a0 = o.screen ? o.screen : P_(o.at);
      if (!a0) continue;
      const a = [a0[0] + (o.dx || 0), a0[1] - (o.dy || 0)];
      let b;
      if (o.to) { const q = P_(o.to); if (!q) continue; b = q; }
      else { const v = o.samples ? at(o.samples, ctx.t) : o.vec; if (!v) continue; b = [a[0] + v[0], a[1] - v[1]]; }
      const pr = arrowPrims(a, b, c, { dashed: o.dashed, w: o.w || 7 });
      if (!pr.length) continue;
      out.push(...pr);
      if (o.label) {
        const u = norm([b[0] - a[0], b[1] - a[1]]);
        labels.push({ x: b[0] + (o.lx != null ? o.lx : u[0] * 18 + 10), y: b[1] + (o.ly != null ? o.ly : u[1] * 18 + 14), s: o.label, c, size: o.size || 42 });
      }
    } else if (o.kind === 'path') {
      const pts = o.of ? (ctx.track(o.of) || []).filter((q) => !o.upto || q[0] <= ctx.t).map((q) => [q[1], q[2]]) : o.pts;
      if (!pts || pts.length < 2) continue;
      const every = o.every || 1;
      if (o.style === 'dashed') out.push(P.path('M' + pts.map((q) => ctx.proj(q).map(F).join(',')).join('L'), 'none',
        { stroke: c, 'stroke-width': F(o.w || 4), 'stroke-dasharray': '4 12', 'stroke-linecap': 'round' }));
      else for (let i = 0; i < pts.length; i += every) out.push(P.circle(ctx.proj(pts[i]), o.r || 5, c));
    } else if (o.kind === 'label') {
      const p = o.screen || P_(o.at); if (!p) continue;
      labels.push({ x: p[0] + (o.dx || 0), y: p[1] - (o.dy || 0), s: o.text, c, size: o.size || 42, anchor: o.anchor });
    } else if (o.kind === 'line' || o.kind === 'dim') {
      const a = o.screen_a || P_(o.a), b = o.screen_b || P_(o.b); if (!a || !b) continue;
      const off = o.offset || 0, n = norm([-(b[1] - a[1]), b[0] - a[0]]), A = [a[0] + n[0] * off, a[1] + n[1] * off], Bq = [b[0] + n[0] * off, b[1] + n[1] * off];
      if (o.kind === 'line') out.push(P.line(A, Bq, o.w || 3, o.color ? c : T.muted, { 'stroke-dasharray': '10 10', opacity: o.opacity || '0.8' }));
      else if (o.arrows) { const m = [(A[0] + Bq[0]) / 2, (A[1] + Bq[1]) / 2]; out.push(...arrowPrims(m, Bq, c, { w: 4, head: 20 }), ...arrowPrims(m, A, c, { w: 4, head: 20 })); }
      else {
        out.push(P.line(A, Bq, 3, c));
        for (const q of [A, Bq]) out.push(P.line([q[0] - n[0] * 10, q[1] - n[1] * 10], [q[0] + n[0] * 10, q[1] + n[1] * 10], 3, c));
      }
      if (o.text) labels.push({ x: (A[0] + Bq[0]) / 2 + (o.lx || 0), y: (A[1] + Bq[1]) / 2 + (o.ly != null ? o.ly : 44), s: o.text, c: o.kind === 'dim' && !o.arrows ? T.ink : c, size: o.size || 38, anchor: 'middle' });
    } else if (o.kind === 'card') {
      const [x, y] = o.screen, w = o.w || 470, rows = o.rows || [], lines = o.lines || [];
      const h = o.h || (30 + (o.title ? 44 : 0) + rows.length * 54 + lines.length * 40 + (o.eq ? 60 : 0));
      out.push(P.rect(x, y, w, h, T.card, { rx: '18' }));
      let yy = y + 44;
      if (o.title) { out.push(wordsText(x + 24, yy, o.title, { size: o.title_size || 24, weight: 600, color: o.title_color || T.ink })); yy += 44; }
      for (const r of rows) { out.push(['text', { x: F(x + 24), y: F(yy + 10), 'font-family': FONT.symbol, 'font-size': '36', fill: T.ink, html: `<tspan font-style="italic">${sym(r[0])}</tspan> = ${r[1]}` }]); yy += 54; }
      if (o.eq) { out.push(['text', { x: F(x + 24), y: F(yy + 12), 'font-family': FONT.symbol, 'font-style': 'italic', 'font-size': '40', fill: T.ink, html: o.eq }]); yy += 60; }
      for (const l of lines) { out.push(wordsText(x + 24, yy, l, { size: 24, color: T.muted, halo: false })); yy += 40; }
      for (const v of o.vectors || []) {
        const a = [x + v.from[0], y + v.from[1]], b = [x + v.to[0], y + v.to[1]], vc = roleColour(v.role);
        out.push(...arrowPrims(a, b, vc, { dashed: v.dashed, w: 6 }));
        if (v.label) out.push(symbolText(b[0] + (v.lx || 0), b[1] + (v.ly || 0), v.label, vc, 36));
      }
    } else if (o.kind === 'badge') {
      const text = o.text || 'Illustrative', w = text.length * 13 + 44;
      out.push(P.rect(ctx.w - w - 40, 34, w, 46, T.card, { rx: '23', stroke: T.muted, 'stroke-width': '2' }),
        ['text', { x: F(ctx.w - w / 2 - 40), y: '65', 'text-anchor': 'middle', 'font-family': FONT.words, 'font-size': '24', fill: T.muted, text }]);
    } else if (o.kind === 'clock') {  // a dial, no numbers
      const [x, y] = o.screen, r = o.r || 40, a = ((ctx.t - (o.t0 || 0)) * Math.PI * 2) / (o.period || 60);
      out.push(P.circle([x, y], r, T.card, { stroke: T.muted, 'stroke-width': '4' }), P.line([x, y], [x + Math.sin(a) * r * 0.8, y - Math.cos(a) * r * 0.8], 4, '#C0392B'), P.circle([x, y], 4, T.ink));
    } else if (o.kind === 'energy') {
      const [x, y] = o.screen, w = o.w || 470, v = at(o.samples, ctx.t) || [0, 0], bw = w - 150;
      out.push(P.rect(x, y, w, 250, T.card, { rx: '18' }), wordsText(x + 25, y + 45, o.title || 'energy', { size: 26, weight: 600 }));
      [['PE', v[0], '#43A047', '#E3E8E3'], ['KE', v[1], '#E4572E', '#F1E3E1']].forEach(([n, k, fc, bg], i) => {
        const yy = y + 76 + i * 60;
        out.push(wordsText(x + 25, yy + 24, n, { size: 26, weight: 700, color: fc, halo: false }), P.rect(x + 90, yy, bw, 30, bg, { rx: '8' }), P.rect(x + 90, yy, bw * Math.max(0, Math.min(1, k)), 30, fc, { rx: '8' }));
      });
      if (o.note) out.push(wordsText(x + 25, y + 222, o.note, { size: 24, color: T.muted, halo: false }));
    } else if (o.kind === 'words') {
      const p = o.screen || P_(o.at); if (!p) continue;
      out.push(wordsText(p[0] + (o.dx || 0), p[1] - (o.dy || 0), o.text, { size: o.size || 30, anchor: o.anchor || 'start', color: o.color || T.ink, weight: o.weight || 500, halo: o.halo !== false }));
    }
  }
  for (const l of labels) {
    const [x, y] = nudge(l.x, l.y, l.s, l.size, l.anchor || 'start', ctx);
    out.push(symbolText(x, y, l.s, l.c, l.size, l.anchor || 'start'));
  }
  return { prims: out, labels: labels.length };
}
