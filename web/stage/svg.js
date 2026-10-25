// SVG helpers for the stage. A drawing is a list of prims [tag, attrs]; reconcile() keeps one element per prim and
// writes only the attributes that changed, so a frame never rebuilds the DOM (the reference re-set innerHTML).
export const NS = 'http://www.w3.org/2000/svg';
export const F = (n) => (Math.round(n * 10) / 10).toString();
export const lerp = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k];
export const norm = (v) => { const l = Math.hypot(v[0], v[1]) || 1; return [v[0] / l, v[1] / l]; };
export const dist = (a, b) => Math.hypot(b[0] - a[0], b[1] - a[1]);

export function el(tag, attrs = {}, parent = null) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (parent) parent.appendChild(e);
  return e;
}

// "v_m" -> v with a subscript m; plain text otherwise (escaped)
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
export function sym(s) {
  const m = String(s).match(/^([^_]+)_(.+)$/);
  return m ? `${esc(m[1])}<tspan baseline-shift="sub" font-size="0.62em">${esc(m[2])}</tspan>` : esc(s);
}

// prims -> children of g. attrs `text` sets textContent, `html` sets the inner markup (subscripts)
export function reconcile(g, prims) {
  const kids = g.children;
  let i = 0;
  for (; i < prims.length; i++) {
    const [tag, a] = prims[i];
    let e = kids[i];
    if (!e || e.tagName !== tag) {
      const fresh = document.createElementNS(NS, tag);
      fresh.__a = {};
      if (e) g.replaceChild(fresh, e); else g.appendChild(fresh);
      e = fresh;
    }
    const old = e.__a || (e.__a = {});
    for (const k in a) {
      const v = a[k];
      if (old[k] === v) continue;
      old[k] = v;
      if (k === 'text') e.textContent = v;
      else if (k === 'html') e.innerHTML = v;
      else e.setAttribute(k, v);
    }
    for (const k in old) if (!(k in a)) { e.removeAttribute(k); delete old[k]; }
  }
  while (kids.length > prims.length) g.removeChild(g.lastChild);
}

// one markup string -> a group's content, written only when it changed (backdrops, static props)
export function setMarkup(g, s) { if (g.__m !== s) { g.__m = s; g.innerHTML = s; } }

export function setAttr(e, k, v) { const o = e.__a || (e.__a = {}); if (o[k] !== v) { o[k] = v; e.setAttribute(k, v); } }

// Catmull-Rom through points (closed) -> path d
export function smooth(pts, closed = true) {
  const n = pts.length; let d = `M${F(pts[0][0])},${F(pts[0][1])}`;
  for (let i = 0; i < (closed ? n : n - 1); i++) {
    const p0 = pts[(i - 1 + n) % n], p1 = pts[i], p2 = pts[(i + 1) % n], p3 = pts[(i + 2) % n];
    d += `C${F(p1[0] + (p2[0] - p0[0]) / 6)},${F(p1[1] + (p2[1] - p0[1]) / 6)} ${F(p2[0] - (p3[0] - p1[0]) / 6)},${F(p2[1] - (p3[1] - p1[1]) / 6)} ${F(p2[0])},${F(p2[1])}`;
  }
  return d + (closed ? 'Z' : '');
}
export const polyD = (pts, closed = true) => 'M' + pts.map((p) => F(p[0]) + ',' + F(p[1])).join('L') + (closed ? 'Z' : '');

// a limb tapering from width wa at a to wb at b, round ends, as one path
export function taperD(a, b, wa, wb) {
  const t = norm([b[0] - a[0], b[1] - a[1]]), n = [-t[1], t[0]], ra = wa / 2, rb = wb / 2;
  return `M${F(a[0] + n[0] * ra)},${F(a[1] + n[1] * ra)}L${F(b[0] + n[0] * rb)},${F(b[1] + n[1] * rb)}` +
    `A${F(rb)},${F(rb)} 0 0 0 ${F(b[0] - n[0] * rb)},${F(b[1] - n[1] * rb)}` +
    `L${F(a[0] - n[0] * ra)},${F(a[1] - n[1] * ra)}A${F(ra)},${F(ra)} 0 0 0 ${F(a[0] + n[0] * ra)},${F(a[1] + n[1] * ra)}Z`;
}

// prim constructors
export const P = {
  path: (d, fill, ex = {}) => ['path', { d, fill, ...ex }],
  circle: (c, r, fill, ex = {}) => ['circle', { cx: F(c[0]), cy: F(c[1]), r: F(Math.max(0, r)), fill, ...ex }],
  ellipse: (c, rx, ry, fill, a = 0, ex = {}) => ['ellipse', { cx: F(c[0]), cy: F(c[1]), rx: F(rx), ry: F(ry), fill,
    ...(a ? { transform: `rotate(${F(a)} ${F(c[0])} ${F(c[1])})` } : {}), ...ex }],
  line: (a, b, w, c, ex = {}) => ['line', { x1: F(a[0]), y1: F(a[1]), x2: F(b[0]), y2: F(b[1]), stroke: c,
    'stroke-width': F(w), 'stroke-linecap': 'round', ...ex }],
  rect: (x, y, w, h, fill, ex = {}) => ['rect', { x: F(x), y: F(y), width: F(Math.max(0, w)), height: F(Math.max(0, h)), fill, ...ex }],
  taper: (a, b, wa, wb, fill, ex = {}) => ['path', { d: taperD(a, b, wa, wb), fill, ...ex }],
};

// prims -> markup (static drawings: props, backdrops)
export function markup(prims) {
  let s = '';
  for (const [tag, a] of prims) {
    let attrs = '', inner = '';
    for (const k in a) {
      if (k === 'text') inner = String(a[k]).replace(/&/g, '&amp;').replace(/</g, '&lt;');
      else if (k === 'html') inner = a[k];
      else attrs += ` ${k}="${a[k]}"`;
    }
    s += `<${tag}${attrs}>${inner}</${tag}>`;
  }
  return s;
}
