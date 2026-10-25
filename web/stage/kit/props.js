// Kit props (F-017 §4), keyed by catalog id (config/stage_catalog.json). draw(w, h, st, ctx) -> prims in the prop's
// own frame: metres x right / y up from its origin (bottom centre unless the row says otherwise), drawn at B per m.
// w, h = the row's size_m (or the entity's size); st = state; ctx = {t, x}. `dynamic` props redraw every frame.
import { B, ROLE, shade, hash } from '../style.js';
import { F, P, polyD, smooth } from '../svg.js';

const X = (u) => u * B, Y = (v) => -v * B;
const pt = (p) => [X(p[0]), Y(p[1])];
const R = (x0, y0, x1, y1, fill, rx = 0, ex = {}) => P.rect(X(Math.min(x0, x1)), Y(Math.max(y0, y1)), X(Math.abs(x1 - x0)), X(Math.abs(y1 - y0)), fill, rx ? { rx: F(X(rx)), ...ex } : ex);
const C = (x, y, r, fill, ex) => P.circle([X(x), Y(y)], X(r), fill, ex);
const E = (x, y, rx, ry, fill, a = 0, ex) => P.ellipse([X(x), Y(y)], X(rx), X(ry), fill, -a, ex);
const G = (pts, fill, ex) => P.path(polyD(pts.map(pt)), fill, ex);
const S = (pts, fill, ex) => P.path(smooth(pts.map(pt)), fill, ex);
const Ln = (a, b, w, c, ex) => P.line(pt(a), pt(b), X(w), c, ex);
const Open = (pts, w, c, ex = {}) => P.path(polyD(pts.map(pt), false), 'none', { stroke: c, 'stroke-width': F(X(w)), 'stroke-linejoin': 'round', 'stroke-linecap': 'round', ...ex });
const shine = (x0, y0, x1, y1, w) => Ln([x0, y0], [x1, y1], w, 'rgba(255,255,255,0.55)');

function wheel(cx, cy, r, ang, tyre = '#2F3238', hub = '#C9CDD3') {
  const o = [C(cx, cy, r, tyre), C(cx, cy, r * 0.55, hub)];
  for (let i = 0; i < 3; i++) { const q = ang + i * Math.PI / 3; o.push(Ln([cx + Math.cos(q) * r * 0.5, cy + Math.sin(q) * r * 0.5], [cx - Math.cos(q) * r * 0.5, cy - Math.sin(q) * r * 0.5], r * 0.08, '#888')); }
  return o;
}

export const PROPS = {
  // ---------- from the reference samples ----------
  crate: { draw: (w, h, st) => { const c = st.color || '#D9A066';
    return [R(-w / 2, 0, w / 2, h, c, 0.06), R(-w / 2, h * 0.88, w / 2, h, shade(c, 0.9), 0.05), R(-w * 0.08, 0, w * 0.08, h, '#EBC895', 0, { opacity: '0.9' }),
      R(-w / 2, 0, w / 2, h, 'none', 0.06, { stroke: shade(c, 0.85), 'stroke-width': F(X(0.03)) })]; } },
  ball: { draw: (w, h, st) => { const r = h / 2; return [C(0, r, r, st.color || '#E4572E'), C(-r * 0.32, r * 1.32, r * 0.28, 'rgba(255,255,255,0.55)')]; } },
  table: { draw: (w, h) => { const lg = 0.07, th = 0.06;
    return [R(-w / 2 + lg * 0.6, 0, -w / 2 + lg * 1.6, h - th, '#9C6A43'), R(w / 2 - lg * 1.6, 0, w / 2 - lg * 0.6, h - th, '#9C6A43'), R(-w / 2, h - th, w / 2, h, '#B98256', 0.03)]; } },
  tree: { draw: (w, h) => { const tw = Math.min(0.4, w * 0.1), th = h * 0.45, cy = th + h * 0.25, Rr = h * 0.27;
    return [R(-tw / 2, 0, tw / 2, th + 0.08, '#8A5A3B'), C(-Rr * 0.55, cy - Rr * 0.2, Rr * 0.72, '#3F8A4B'), C(Rr * 0.55, cy - Rr * 0.25, Rr * 0.7, '#3F8A4B'),
      C(0, cy + Rr * 0.25, Rr * 0.85, '#4E9F5A'), C(-Rr * 0.3, cy + Rr * 0.45, Rr * 0.25, 'rgba(255,255,255,0.18)')]; } },
  car: { dynamic: true, draw: (w, h, st, ctx) => {  // facing +x; wheels turn with the distance driven
    const k = w / 4.45, kh = h / 1.45, q = (u, v) => [u * k - w / 2, v * kh], c = st.color || '#E4572E', a = -((ctx.x || 0) / (0.34 * k));
    return [G([[0, 0.32], [4.4, 0.32], [4.45, 0.72], [4.05, 0.9], [2.95, 0.98], [2.3, 1.45], [1.05, 1.45], [0.45, 0.98], [0.02, 0.86]].map(([u, v]) => q(u, v)), c),
      G([[1.2, 1.0], [2.15, 1.0], [2.15, 1.36], [1.28, 1.36]].map(([u, v]) => q(u, v)), '#CFE7F5'), G([[2.3, 1.0], [2.8, 1.0], [2.25, 1.36]].map(([u, v]) => q(u, v)), '#CFE7F5'),
      R(...q(4.25, 0.72), ...q(4.41, 0.62), '#FFE08A'), ...wheel(...q(0.95, 0.34), 0.34 * kh, a), ...wheel(...q(3.45, 0.34), 0.34 * kh, a)]; } },
  beaker: { draw: (w, h, st) => { const f = st.fill == null ? 0.5 : st.fill, liq = st.liquid || 'rgba(120,190,230,0.6)', gl = '#7FA3BC', t = w * 0.06;
    return [R(-w / 2 + t, t, w / 2 - t, t + (h * 0.85 - t) * f, liq), Open([[-w / 2 - w * 0.12, h + w * 0.05], [-w / 2, h], [-w / 2, 0], [w / 2, 0], [w / 2, h]], t, gl),
      ...[1, 2, 3, 4].map((i) => Ln([w / 2 - w * 0.25, h * i / 5], [w / 2 - t, h * i / 5], t * 0.4, gl)), shine(-w * 0.3, h * 0.2, -w * 0.3, h * 0.8, t * 0.8)]; } },
  bench: { draw: (w, h, st) => { const s = st.seat_h || h * 0.53, c = '#A0673F';
    return [R(-w / 2 + 0.12, 0, -w / 2 + 0.18, s, shade(c, 0.8)), R(w / 2 - 0.18, 0, w / 2 - 0.12, s, shade(c, 0.8)), R(-w / 2 + 0.1, s, -w / 2 + 0.16, h, shade(c, 0.85)),
      R(-w / 2, s - 0.07, w / 2, s, c, 0.03), R(-w / 2, h - 0.12, w / 2, h - 0.04, c, 0.03)]; } },
  seesaw: { draw: (w, h, st) => {  // the plank (origin: its bottom centre, on the pivot) and its handles
    const hs = st.handles || [[-w * 0.3, h - 0.05], [w * 0.3, h - 0.05]], o = [R(-w / 2, 0, w / 2, 0.08, '#F2C14E', 0.05)];
    for (const [x, gy] of hs) o.push(R(x - 0.025, 0.08, x + 0.025, gy, '#5D6470'), R(x - 0.08, gy - 0.03, x + 0.08, gy + 0.03, '#5D6470', 0.03));  // [x, grip height]
    return o; } },
  fulcrum: { draw: (w, h) => [G([[-w / 2, 0], [0, h], [w / 2, 0]], '#E4572E'), C(0, h, w * 0.06, shade('#E4572E', 0.8))] },
  swing: { draw: (w, h) => [Ln([-w / 2, 0], [0, h], 0.09, '#4F7CAC'), Ln([w / 2, 0], [0, h], 0.09, '#4F7CAC'), C(0, h, 0.1, '#3B5F86')] },
  swing_seat: { draw: (w, h) => [Ln([0, 0], [0, -h], 0.03, '#6B4A2F'),  // side view: both ropes in line; origin = the pivot
    R(-w / 2, -h - 0.04, w / 2, -h + 0.03, '#A0673F', 0.03), C(0, 0, 0.04, '#5D6470')] },
  watering_can: { draw: (w, h, st) => { const c = st.color || '#2F80ED';
    return [G([[w * 0.1, h * 0.55], [w / 2, h * 0.95], [w / 2 + 0.02, h * 0.85], [w * 0.15, h * 0.35]], c), R(-w / 2 + 0.04, 0, w * 0.18, h * 0.7, c, 0.05),
      Open([[-w * 0.32, h * 0.7], [-w * 0.15, h], [w * 0.05, h * 0.7]], 0.03, shade(c, 0.8))]; } },
  pot_plant: { draw: (w, h, st) => { const ph = h * 0.4, g = st.grow == null ? 1 : st.grow, sh = (h - ph) * g;
    return [G([[-w / 2, ph], [w / 2, ph], [w * 0.35, 0], [-w * 0.35, 0]], '#C8693E'), R(-w / 2, ph - 0.03, w / 2, ph + 0.01, '#B5582F', 0.01),
      Ln([0, ph], [0, ph + sh], 0.03, '#3F8A4B'), E(-w * 0.22, ph + sh * 0.55, w * 0.22, w * 0.09, '#4E9F5A', 25), E(w * 0.22, ph + sh * 0.75, w * 0.22, w * 0.09, '#4E9F5A', -25),
      E(0, ph + sh, w * 0.18, w * 0.1, '#5DB06A')]; } },
  lamp_post: { draw: (w, h, st) => { const on = st.on !== false;
    return [...(on ? [C(0, h - 0.25, w * 0.9, '#FFE9A8', { opacity: '0.35' })] : []), Ln([0, 0], [0, h - 0.2], 0.12, '#2D3142'),
      G([[-w / 2, h - 0.18], [w / 2, h - 0.18], [w * 0.3, h], [-w * 0.3, h]], '#2D3142'), C(0, h - 0.24, w * 0.2, on ? '#FFF3B0' : '#C9CDD3')]; } },
  rope: { draw: (w, h, st) => { const o = [Ln([-w / 2, h / 2], [w / 2, h / 2], Math.max(0.03, h), '#C8A165')];
    if (st.marker) o.push(G([[0, h / 2], [-0.09, h / 2 - 0.27], [0.09, h / 2 - 0.27]], '#E4572E'));
    return o; } },
  post: { draw: (w, h) => [R(-w / 2, 0, w / 2, h, '#8A5A3B', 0.02), R(-w / 2, h - 0.05, w / 2, h, shade('#8A5A3B', 0.85), 0.02)] },
  cliff: { draw: (w, h) => [G([[-w / 2, 0], [-w / 2 + 0.3, h * 0.36], [-w / 2 + 0.1, h * 0.66], [-w / 2 + 0.5, h], [w / 2, h], [w / 2, 0]], '#9C8F80'),
    Ln([-w / 2 + 0.6, h * 0.22], [-w / 2 + 1.7, h * 0.26], 0.06, '#857868'), Ln([-w / 2 + 0.5, h * 0.55], [-w / 2 + 2.0, h * 0.58], 0.06, '#857868'), Ln([-w / 2 + 0.7, h * 0.85], [-w / 2 + 1.8, h * 0.9], 0.06, '#857868')] },
  board: { draw: (w, h, st) => { const green = st.kind === 'black';
    return [R(-w / 2 + 0.2, 0, -w / 2 + 0.26, h * 0.3, '#9C8B74'), R(w / 2 - 0.26, 0, w / 2 - 0.2, h * 0.3, '#9C8B74'),
      R(-w / 2, h * 0.3, w / 2, h, '#9C8B74', 0.05), R(-w / 2 + 0.07, h * 0.3 + 0.07, w / 2 - 0.07, h - 0.07, green ? '#2F5D50' : '#FBFBF8', 0.03),
      R(-w * 0.3, h * 0.3 - 0.04, w * 0.3, h * 0.3 + 0.02, '#B8A88E')]; } },
  desk: { draw: (w, h) => [R(-w / 2 + 0.05, 0, -w / 2 + 0.1, h - 0.05, '#8E5B3A'), R(w / 2 - 0.1, 0, w / 2 - 0.05, h - 0.05, '#8E5B3A'),
    R(w / 2 - 0.45, h * 0.55, w / 2 - 0.08, h - 0.05, '#A06B45'), R(-w / 2, h - 0.05, w / 2, h, '#B07A4F', 0.02)] },
  chair: { draw: (w, h, st) => { const s = st.seat_h || h * 0.52, c = '#8E5B3A';
    return [R(-w / 2 + 0.02, 0, -w / 2 + 0.06, s, shade(c, 0.8)), R(w / 2 - 0.06, 0, w / 2 - 0.02, s, shade(c, 0.8)),
      R(-w / 2, s - 0.05, w / 2, s, c, 0.02), R(-w / 2, s, -w / 2 + 0.05, h, c, 0.02), R(-w / 2, h - 0.12, -w / 2 + 0.05, h - 0.02, shade(c, 1.15))]; } },
  bulb: { dynamic: true, draw: (w, h, st, ctx) => { const on = !!st.on, g = 0.85 + 0.15 * Math.sin((ctx.t || 0) * 5);
    return [...(on ? [C(0, h * 0.62, w * 1.4 * g, '#FFE27A', { opacity: '0.35' })] : []), C(0, h * 0.62, w / 2, on ? '#FFF3B0' : '#EDEFF2'),
      Open([[-w * 0.2, h * 0.42], [-w * 0.1, h * 0.7], [0, h * 0.42], [w * 0.1, h * 0.7], [w * 0.2, h * 0.42]], w * 0.05, on ? '#E08A00' : '#9AA0A6'),
      R(-w * 0.22, 0, w * 0.22, h * 0.32, '#9AA0A6', w * 0.05)]; } },
  cell: { draw: (w, h) => [R(-w / 2, 0, w / 2, h * 0.92, '#2F3238', w * 0.15), R(-w / 2, h * 0.62, w / 2, h * 0.92, '#E4572E', w * 0.15), R(-w * 0.2, h * 0.92, w * 0.2, h, '#9AA0A6', w * 0.05),
    ['text', { x: F(X(0)), y: F(Y(h * 0.68)), 'text-anchor': 'middle', 'font-size': F(X(w * 0.7)), 'font-weight': '700', fill: '#fff', 'font-family': 'Segoe UI', text: '+' }]] },
  switch: { draw: (w, h, st) => { const closed = st.closed !== false, a = closed ? 0 : 0.5;
    return [R(-w / 2, 0, w / 2, h * 0.3, '#7A6A55', h * 0.1), C(-w * 0.38, h * 0.45, h * 0.15, '#555'), C(w * 0.38, h * 0.45, h * 0.15, '#555'),
      Ln([-w * 0.38, h * 0.45], [-w * 0.38 + Math.cos(a) * w * 0.76, h * 0.45 + Math.sin(a) * w * 0.76], h * 0.14, '#6B7280')]; } },
  wire: { draw: (w, h) => [Ln([-w / 2, h / 2], [w / 2, h / 2], Math.max(0.012, h), '#B5652B')] },
  lift: { draw: (w, h) => [R(-w / 2, 0, w / 2, h, '#F5EEDF', 0.06), R(-w / 2, 0, w / 2, h, 'none', 0.06, { stroke: '#9C8B74', 'stroke-width': F(X(0.05)) }),
    Ln([0, h], [0, h + 3], 0.04, '#5D6470'), R(-w / 2, 0, w / 2, 0.05, '#C9BFAE')] },
  scale: { draw: (w, h, st) => { const k = st.reading == null ? 0.35 : st.reading;
    return [R(-w / 2, 0, w / 2, h, '#7F8C9A', 0.03), C(0, h * 0.5, h * 0.32, '#ffffff'), Ln([0, h * 0.5], [Math.sin(k) * h * 0.3, h * 0.5 + Math.cos(k) * h * 0.3], h * 0.07, '#C0392B')]; } },
  // ---------- new for E1 ----------
  book: { draw: (w, h, st) => { const c = st.color || '#2E86AB';
    return [R(-w / 2, 0, w / 2, h, c, h * 0.2), R(-w / 2 + w * 0.04, h * 0.25, w / 2, h * 0.75, '#F7F3E8'), R(-w / 2, 0, -w / 2 + w * 0.08, h, shade(c, 0.8), h * 0.2)]; } },
  bag: { draw: (w, h, st) => { const c = st.color || '#E07A5F';
    return [Open([[-w * 0.25, h * 0.85], [-w * 0.2, h * 1.0], [w * 0.2, h * 1.0], [w * 0.25, h * 0.85]], w * 0.08, shade(c, 0.75)),
      R(-w / 2, 0, w / 2, h * 0.88, c, w * 0.18), R(-w * 0.35, h * 0.1, w * 0.35, h * 0.45, shade(c, 0.88), w * 0.08), Ln([-w * 0.3, h * 0.45], [w * 0.3, h * 0.45], w * 0.03, shade(c, 0.7))]; } },
  bottle: { draw: (w, h, st) => { const c = st.color || 'rgba(90,170,120,0.85)';
    return [S([[-w / 2, 0], [w / 2, 0], [w / 2, h * 0.62], [w * 0.2, h * 0.8], [w * 0.18, h * 0.95], [-w * 0.18, h * 0.95], [-w * 0.2, h * 0.8], [-w / 2, h * 0.62]], c),
      R(-w * 0.22, h * 0.93, w * 0.22, h, '#E4572E', w * 0.05), R(-w / 2, h * 0.25, w / 2, h * 0.5, '#F7F3E8'), shine(-w * 0.28, h * 0.08, -w * 0.28, h * 0.6, w * 0.08)]; } },
  cup: { draw: (w, h, st) => { const c = st.color || '#F2C14E';
    return [Open([[w * 0.42, h * 0.75], [w * 0.75, h * 0.7], [w * 0.75, h * 0.35], [w * 0.4, h * 0.3]], w * 0.12, shade(c, 0.85)), G([[-w / 2, h], [w / 2, h], [w * 0.4, 0], [-w * 0.4, 0]], c),
      E(0, h, w / 2, w * 0.1, shade(c, 0.75))]; } },
  phone: { draw: (w, h) => [R(-w / 2, 0, w / 2, h, '#2F3238', w * 0.15), R(-w * 0.42, h * 0.08, w * 0.42, h * 0.9, '#7FB8E6', w * 0.05), C(0, h * 0.95, w * 0.06, '#555')] },
  laptop: { draw: (w, h) => [G([[-w * 0.4, h * 0.06], [-w * 0.48, h], [w * 0.2, h], [w * 0.28, h * 0.06]], '#5D6470'), G([[-w * 0.36, h * 0.12], [-w * 0.43, h * 0.93], [w * 0.15, h * 0.93], [w * 0.22, h * 0.12]], '#7FB8E6'),
    R(-w / 2, 0, w / 2, h * 0.06, '#8A93A3', h * 0.02)] },
  door: { draw: (w, h, st) => { const c = st.color || '#B07A4F';
    return [R(-w / 2 - 0.05, 0, w / 2 + 0.05, h + 0.05, '#E6D3B5'), R(-w / 2, 0, w / 2, h, c, 0.02), R(-w * 0.38, h * 0.55, w * 0.38, h * 0.92, shade(c, 0.9), 0.02),
      R(-w * 0.38, h * 0.08, w * 0.38, h * 0.48, shade(c, 0.9), 0.02), C(w * 0.36, h * 0.5, 0.035, '#F2C14E')]; } },
  bicycle: { dynamic: true, draw: (w, h, st, ctx) => { const r = h * 0.34, a = -((ctx.x || 0) / r), c = st.color || '#2F80ED', fx = w / 2 - r, rx = -w / 2 + r;
    const o = [C(rx, r, r, 'none', { stroke: '#2F3238', 'stroke-width': F(X(0.05)) }), C(fx, r, r, 'none', { stroke: '#2F3238', 'stroke-width': F(X(0.05)) })];
    for (const cx of [rx, fx]) for (let i = 0; i < 4; i++) { const q = a + i * Math.PI / 4; o.push(Ln([cx + Math.cos(q) * r, r + Math.sin(q) * r], [cx - Math.cos(q) * r, r - Math.sin(q) * r], 0.008, '#9AA0A6')); }
    o.push(Open([[rx, r], [-w * 0.05, r], [w * 0.2, h * 0.78], [-w * 0.18, h * 0.78], [rx, r]], 0.04, c), Open([[-w * 0.05, r], [-w * 0.2, h * 0.86]], 0.04, c),
      Open([[w * 0.2, h * 0.78], [fx, r]], 0.04, c), Open([[w * 0.2, h * 0.78], [w * 0.17, h * 0.98], [w * 0.27, h]], 0.035, '#2F3238'), R(-w * 0.28, h * 0.86, -w * 0.1, h * 0.9, '#2F3238', 0.02));
    return o; } },
  bus: { dynamic: true, draw: (w, h, st, ctx) => { const c = st.color || '#F2C14E', r = 0.5, a = -((ctx.x || 0) / r), o = [R(-w / 2, 0.35, w / 2, h, c, 0.25)];
    for (let i = 0; i < 6; i++) o.push(R(-w / 2 + 0.6 + i * (w - 1.6) / 6, h * 0.55, -w / 2 + 0.6 + (i + 0.8) * (w - 1.6) / 6, h * 0.88, '#CFE7F5', 0.05));
    o.push(R(w / 2 - 0.9, h * 0.5, w / 2 - 0.15, h * 0.9, '#CFE7F5', 0.06), R(-w / 2, h * 0.42, w / 2, h * 0.47, shade(c, 0.8)), ...wheel(-w / 2 + 2.2, r, r, a), ...wheel(w / 2 - 2.2, r, r, a));
    return o; } },
  boat: { draw: (w, h, st) => { const c = st.color || '#E4572E';
    return [G([[-w / 2, h * 0.55], [w / 2, h * 0.55], [w * 0.36, 0], [-w * 0.4, 0]], c), R(-w / 2, h * 0.5, w / 2, h * 0.6, shade(c, 0.8)),
      R(-w * 0.1, h * 0.6, w * 0.25, h, '#F7F3E8', 0.05), R(-w * 0.05, h * 0.72, w * 0.08, h * 0.9, '#CFE7F5', 0.02)]; } },
  ladder: { draw: (w, h) => { const o = [Ln([-w / 2, 0], [-w / 2, h], 0.05, '#B07A4F'), Ln([w / 2, 0], [w / 2, h], 0.05, '#B07A4F')];
    for (let y = 0.3; y < h; y += 0.3) o.push(Ln([-w / 2, y], [w / 2, y], 0.035, '#C89A6A'));
    return o; } },
  ramp: { draw: (w, h, st) => [G(st.down === 'left' ? [[-w / 2, 0], [w / 2, 0], [w / 2, h]] : [[-w / 2, 0], [w / 2, 0], [-w / 2, h]], '#C7A27C'),
    Ln(st.down === 'left' ? [-w / 2, 0] : [w / 2, 0], st.down === 'left' ? [w / 2, h] : [-w / 2, h], 0.04, shade('#C7A27C', 0.85))] },
  spring: { draw: (w, h, st) => { const n = st.coils || 8, pts = [[0, 0], [0, h * 0.06]];
    for (let i = 0; i <= n; i++) pts.push([(i % 2 ? 1 : -1) * w / 2, h * 0.06 + (h * 0.88) * (i + 0.5) / (n + 1)]);
    pts.push([0, h * 0.94], [0, h]);
    return [Open(pts, w * 0.12, '#7F8C9A')]; } },
  pulley: { draw: (w, h) => { const r = w / 2; return [Ln([0, h], [0, h - r * 0.9], 0.03, '#5D6470'), R(-0.03, h - 0.04, 0.03, h, '#5D6470'),
    C(0, h - r * 1.6, r, '#9AA0A6'), C(0, h - r * 1.6, r * 0.75, '#C9CDD3'), C(0, h - r * 1.6, r * 0.15, '#5D6470'), Ln([-r, h - r * 1.6], [-r, 0], 0.015, '#C8A165'), Ln([r, h - r * 1.6], [r, 0], 0.015, '#C8A165')]; } },
  magnet: { draw: (w, h) => [R(-w / 2, 0, 0, h, '#D9443A', h * 0.1), R(0, 0, w / 2, h, '#2F6BE0', h * 0.1),
    ['text', { x: F(X(-w / 4)), y: F(Y(h * 0.22)), 'text-anchor': 'middle', 'font-size': F(X(h * 0.7)), 'font-weight': '700', fill: '#fff', 'font-family': 'Segoe UI', text: 'N' }],
    ['text', { x: F(X(w / 4)), y: F(Y(h * 0.22)), 'text-anchor': 'middle', 'font-size': F(X(h * 0.7)), 'font-weight': '700', fill: '#fff', 'font-family': 'Segoe UI', text: 'S' }]] },
  compass: { draw: (w, h, st) => { const r = w / 2, a = ((st.angle || 0) * Math.PI) / 180;
    return [C(0, r, r, '#9AA0A6'), C(0, r, r * 0.85, '#FBFBF8'), G([[Math.sin(a) * r * 0.75, r + Math.cos(a) * r * 0.75], [Math.cos(a) * r * 0.12, r - Math.sin(a) * r * 0.12], [-Math.cos(a) * r * 0.12, r + Math.sin(a) * r * 0.12]], '#D9443A'),
      G([[-Math.sin(a) * r * 0.75, r - Math.cos(a) * r * 0.75], [Math.cos(a) * r * 0.12, r - Math.sin(a) * r * 0.12], [-Math.cos(a) * r * 0.12, r + Math.sin(a) * r * 0.12]], '#5D6470'), C(0, r, r * 0.08, '#33363d')]; } },
  thermometer: { draw: (w, h, st) => { const k = st.level == null ? 0.5 : st.level;
    return [R(-w / 2, w * 0.6, w / 2, h, '#FBFBF8', w / 2, { stroke: '#9AA0A6', 'stroke-width': F(X(w * 0.12)) }), C(0, w * 0.6, w * 0.6, '#D9443A'),
      R(-w * 0.18, w * 0.6, w * 0.18, w * 0.6 + (h - w * 1.2) * k, '#D9443A'), ...[0.3, 0.45, 0.6, 0.75, 0.9].map((v) => Ln([w * 0.2, h * v], [w / 2, h * v], w * 0.08, '#9AA0A6'))]; } },
  flask: { draw: (w, h, st) => { const f = st.fill == null ? 0.35 : st.fill, gl = '#7FA3BC', liq = st.liquid || 'rgba(120,190,230,0.6)', nk = w * 0.18;
    return [G([[-w / 2 + w * 0.06, w * 0.04], [w / 2 - w * 0.06, w * 0.04], [w / 2 - w * 0.06 - (w / 2 - nk) * f * 0.9, h * 0.62 * f], [-w / 2 + w * 0.06 + (w / 2 - nk) * f * 0.9, h * 0.62 * f]], liq),
      Open([[-nk, h], [-nk, h * 0.62], [-w / 2, 0], [w / 2, 0], [nk, h * 0.62], [nk, h]], w * 0.05, gl), shine(-w * 0.18, h * 0.1, -w * 0.08, h * 0.45, w * 0.05)]; } },
  test_tube: { draw: (w, h, st) => { const f = st.fill == null ? 0.4 : st.fill, liq = st.liquid || 'rgba(120,190,230,0.7)';
    return [R(-w / 2, 0, w / 2, h * f, liq, w / 2), Open([[-w / 2, h], [-w / 2, w / 2]], w * 0.12, '#7FA3BC'), Open([[w / 2, h], [w / 2, w / 2]], w * 0.12, '#7FA3BC'),
      P.path(`M${F(X(-w / 2))},${F(Y(w / 2))} A${F(X(w / 2))},${F(X(w / 2))} 0 0 0 ${F(X(w / 2))},${F(Y(w / 2))}`, 'none', { stroke: '#7FA3BC', 'stroke-width': F(X(w * 0.12)) })]; } },
  burner: { dynamic: true, draw: (w, h, st, ctx) => { const on = st.on !== false, fl = 1 + 0.1 * Math.sin((ctx.t || 0) * 12);
    return [R(-w / 2, 0, w / 2, h * 0.1, '#5D6470', h * 0.03), R(-w * 0.18, h * 0.1, w * 0.18, h * 0.7, '#9AA0A6'),
      ...(on ? [S([[0, h * 0.7 + h * 0.3 * fl], [w * 0.2, h * 0.8], [w * 0.14, h * 0.7], [-w * 0.14, h * 0.7], [-w * 0.2, h * 0.8]], '#5DADE2', { opacity: '0.85' }), E(0, h * 0.76, w * 0.07, h * 0.05, '#2F80ED')] : [])]; } },
  sun: { dynamic: true, draw: (w, h, st, ctx) => { const r = w * 0.32, cy = h / 2, o = [];
    for (let i = 0; i < 8; i++) { const a = i * Math.PI / 4 + (ctx.t || 0) * 0.2; o.push(Ln([Math.cos(a) * r * 1.25, cy + Math.sin(a) * r * 1.25], [Math.cos(a) * r * 1.6, cy + Math.sin(a) * r * 1.6], r * 0.12, '#FFC21A')); }
    return [...o, C(0, cy, r, '#FFD23F')]; } },
  moon: { draw: (w, h, st) => {  // st.phase: 0 new .. 0.5 half .. 1 full (waxing, lit on the right)
    const r = w / 2, k = st.phase == null ? 1 : st.phase, rx = r * Math.abs(1 - 2 * k), top = `${F(X(0))},${F(Y(2 * r))}`, bot = `${F(X(0))},${F(Y(0))}`;
    const lit = k >= 1 ? C(0, r, r, '#F4F1DE') : P.path(`M${top} A${F(X(r))},${F(X(r))} 0 0 1 ${bot} A${F(X(rx))},${F(X(r))} 0 0 ${k > 0.5 ? 1 : 0} ${top}Z`, '#F4F1DE');
    return [C(0, r, r, '#5D6472'), lit, C(-r * 0.3, r * 1.2, r * 0.15, 'rgba(0,0,0,0.08)'), C(r * 0.25, r * 0.7, r * 0.1, 'rgba(0,0,0,0.08)')]; } },
  planet: { draw: (w, h, st) => { const r = w / 2, c = st.color || '#3B8FE0';
    return [C(0, r, r, c), S([[-r * 0.6, r * 1.3], [-r * 0.1, r * 1.5], [r * 0.2, r * 1.1], [-r * 0.3, r * 0.9]], '#4E9F5A'), S([[r * 0.2, r * 0.5], [r * 0.6, r * 0.6], [r * 0.5, r * 0.3]], '#4E9F5A'),
      P.path(`M${F(X(0))},${F(Y(0))} A${F(X(r))},${F(X(r))} 0 0 1 ${F(X(0))},${F(Y(2 * r))}`, 'rgba(0,0,20,0.22)')]; } },
  cloud: { draw: (w, h, st) => { const c = st.rain ? '#B8C3CC' : '#ffffff', k = w / 2.7;
    return [[-0.6, 0.35, 0.48], [0, 0.55, 0.62], [0.62, 0.38, 0.46], [-0.2, 0.25, 0.4], [0.3, 0.22, 0.4]].map(([u, v, r]) => C(u * k, h * 0.42 + (v - 0.35) * k, r * k, c)); } },
  rock: { draw: (w, h) => [S([[-w / 2, 0], [w / 2, 0], [w * 0.42, h * 0.6], [w * 0.1, h], [-w * 0.3, h * 0.85], [-w * 0.48, h * 0.4]], '#9AA0A6'), S([[-w * 0.2, h * 0.7], [w * 0.05, h * 0.9], [w * 0.2, h * 0.6]], '#B8BEC6')] },
  house: { draw: (w, h, st) => { const c = st.color || '#F2E6CF', wh = h * 0.6;
    return [R(-w * 0.45, 0, w * 0.45, wh, c), G([[-w / 2, wh], [0, h], [w / 2, wh]], '#C0533A'), R(-w * 0.08, 0, w * 0.08, wh * 0.55, '#8E5B3A', 0.05),
      R(-w * 0.36, wh * 0.45, -w * 0.18, wh * 0.8, '#CFE7F5', 0.05), R(w * 0.18, wh * 0.45, w * 0.36, wh * 0.8, '#CFE7F5', 0.05), R(w * 0.22, h * 0.72, w * 0.3, h * 0.92, '#8A5A3B')]; } },
  rain: { dynamic: true, draw: (w, h, st, ctx) => {  // drops falling at st.speed m/s over the box w x h (world-fixed)
    const v = st.speed || 7, n = st.drops || Math.round(w * h * 3), t = ctx.t || 0, o = [];
    for (let i = 0; i < n; i++) { const x = -w / 2 + hash(i) * w, y = h - ((v * t + hash(i + 50) * h) % h); if (y < 0.05) continue;
      o.push(Ln([x, y], [x, Math.max(0, y - 0.22)], 0.035, '#4F86C6', { opacity: '0.75' })); }
    return o; } },
  umbrella: { draw: (w, h, st) => { const c = st.color || '#E4572E';
    return [Ln([0, 0.05], [0, h * 0.85], 0.03, '#5D6470'), Open([[0, 0.05], [0.06, 0], [0.12, 0.05]], 0.03, '#5D6470'), S([[-w / 2, h * 0.7], [0, h], [w / 2, h * 0.7], [0, h * 0.78]], c)]; } },
  bucket: { draw: (w, h, st) => { const c = st.color || '#2F80ED';
    return [Open([[-w * 0.45, h * 0.95], [0, h * 1.25], [w * 0.45, h * 0.95]], 0.012, '#5D6470'), G([[-w / 2, h], [w / 2, h], [w * 0.38, 0], [-w * 0.38, 0]], c), E(0, h, w / 2, w * 0.08, shade(c, 0.7))]; } },
  clock: { dynamic: true, draw: (w, h, st, ctx) => { const r = w / 2, a = ((ctx.t || 0) * Math.PI * 2) / 60;  // a dial, no numbers
    const o = [C(0, r, r, '#5D6470'), C(0, r, r * 0.88, '#FBFBF8')];
    for (let i = 0; i < 12; i++) { const q = i * Math.PI / 6; o.push(Ln([Math.sin(q) * r * 0.72, r + Math.cos(q) * r * 0.72], [Math.sin(q) * r * 0.82, r + Math.cos(q) * r * 0.82], r * 0.05, '#5D6470')); }
    o.push(Ln([0, r], [Math.sin(a) * r * 0.7, r + Math.cos(a) * r * 0.7], r * 0.05, '#C0392B'), Ln([0, r], [0, r + r * 0.5], r * 0.08, '#33363d'), C(0, r, r * 0.07, '#33363d'));
    return o; } },
  apple: { draw: (w, h) => [S([[0, h * 0.82], [w * 0.45, h * 0.85], [w / 2, h * 0.35], [w * 0.15, 0], [-w * 0.15, 0], [-w / 2, h * 0.35], [-w * 0.45, h * 0.85]], '#D9443A'),
    Ln([0, h * 0.8], [w * 0.05, h], w * 0.06, '#6B4A2F'), E(w * 0.18, h * 0.95, w * 0.16, w * 0.07, '#4E9F5A', 20), C(-w * 0.2, h * 0.6, w * 0.1, 'rgba(255,255,255,0.45)')] },
  basket: { draw: (w, h) => [Open([[-w * 0.4, h * 0.8], [-w * 0.3, h * 1.3], [w * 0.3, h * 1.3], [w * 0.4, h * 0.8]], 0.025, '#A0673F'), G([[-w / 2, h * 0.8], [w / 2, h * 0.8], [w * 0.4, 0], [-w * 0.4, 0]], '#C89A6A'),
    ...[0.2, 0.45, 0.7].map((v) => Ln([-w * 0.45, h * v], [w * 0.45, h * v], 0.015, '#A0673F'))] },
  fence: { draw: (w, h) => { const o = [R(-w / 2, h * 0.3, w / 2, h * 0.4, '#E8DCC4'), R(-w / 2, h * 0.65, w / 2, h * 0.75, '#E8DCC4')];
    for (let x = -w / 2 + 0.1; x < w / 2; x += 0.35) o.push(G([[x - 0.05, 0], [x + 0.05, 0], [x + 0.05, h * 0.92], [x, h], [x - 0.05, h * 0.92]], '#F2E6CF'));
    return o; } },
  bush: { draw: (w, h) => [C(-w * 0.25, h * 0.4, h * 0.42, '#3F8A4B'), C(w * 0.25, h * 0.42, h * 0.42, '#3F8A4B'), C(0, h * 0.55, h * 0.45, '#4E9F5A'), C(-w * 0.1, h * 0.7, h * 0.12, 'rgba(255,255,255,0.18)')] },
  trolley: { dynamic: true, draw: (w, h, st, ctx) => { const r = 0.09, a = -((ctx.x || 0) / r);
    return [R(-w / 2, 0.2, w / 2, h * 0.75, '#9AA0A6', 0.03), Open([[-w / 2, h * 0.75], [-w / 2 - 0.15, h]], 0.03, '#5D6470'), ...wheel(-w / 2 + 0.15, r, r, a), ...wheel(w / 2 - 0.15, r, r, a)]; } },
};

export const ROLES = ROLE;
