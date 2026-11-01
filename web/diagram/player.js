// The concept-diagram player (F-018 K1, docs/contracts/diagram-spec.md §7): draws a `diagram.patch` (the stage
// block's `diagram`) full slide under the title, in the S0-S4 simulation look. Every position comes from Python; the
// browser draws and runs the patch's tracks, seamless loops that are a pure function of the time t (orbits, the pour
// stream, the stirring rod, the flame, the field's flowing dashes). still: the slide's figure at t = 0, no clock.
import { html, useLayoutEffect, useRef } from "../vendor/htm-preact-standalone.mjs";
import { PARTS, ABSOLUTE } from "./parts/index.js";
import { Arrow, HEAD, symbolParts } from "../sims/draw.js";

const reduced = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;
const F = (v) => Math.round(v * 10) / 10;
const tf = (p) => `translate(${F(p.cx)},${F(p.cy)}) rotate(${p.rot || 0})`;

function part(p) {
  if (ABSOLUTE[p.kind]) return ABSOLUTE[p.kind](p);
  const draw = PARTS[p.kind] || PARTS.unknown;
  return html`<g key=${p.id} data-id=${p.id} data-kind=${p.kind} class=${"dg-part" + (p.attr && p.attr.focus ? " focus" : "")}
    transform=${tf(p)}>${draw(p)}</g>`;
}

function arrowAt(pts, f = 0.5) {
  let total = 0;
  const seg = [];
  for (let i = 1; i < pts.length; i++) { const d = Math.hypot(pts[i][0] - pts[i - 1][0], pts[i][1] - pts[i - 1][1]); seg.push(d); total += d; }
  let at = total * f;
  for (let i = 1; i < pts.length; i++) {
    if (at <= seg[i - 1] || i === pts.length - 1) {
      const [x0, y0] = pts[i - 1], [x1, y1] = pts[i];
      const k = seg[i - 1] ? Math.min(1, at / seg[i - 1]) : 0;
      return { x: x0 + (x1 - x0) * k, y: y0 + (y1 - y0) * k, a: Math.atan2(y1 - y0, x1 - x0) * 180 / Math.PI };
    }
    at -= seg[i - 1];
  }
  return null;
}

function wire(w) {
  if (w.kind === "orbit") {
    const [cx, cy, rx, ry] = w.ellipse;
    return html`<ellipse key=${w.id} class="sim-guide dg-orbit" cx=${cx} cy=${cy} rx=${rx} ry=${ry} fill="none" />`;
  }
  const d = "M" + w.pts.map((p) => `${F(p[0])},${F(p[1])}`).join(" L");
  if (w.kind === "field") {
    const a = arrowAt(w.pts, w.arrow || 0.5);
    return html`<g key=${w.id} class="dg-field-g"><path class="dg-field" data-flow="1" d=${d} />
      ${a && html`<path class="dg-field-head" transform=${`translate(${F(a.x)},${F(a.y)}) rotate(${F(a.a)})`} d="M12,0 L-10,-10 L-10,10 Z" />`}</g>`;
  }
  if (w.kind === "stream") return html`<path key=${w.id} class=${`dg-stream t-${w.tint || "water"}`} data-stream=${w.id} d=${d} />`;
  // F-019 M5: a body's dotted path (or a dimension line); `turn`: it turns with a circling body (the radius)
  if (w.kind === "trail") return html`<path key=${w.id} class="dg-trail" d=${d} data-carry=${w.turn || undefined} />`;
  return html`<path key=${w.id} class=${w.kind === "rope" ? "sim-string dg-rope" : "sim-wire"} d=${d} fill="none"
    data-rope=${w.kind === "rope" ? w.id : undefined} />`;
}

function overlay(o, i) {
  if (o.kind === "node") return html`<circle key=${"n" + i} class="dg-node" cx=${o.x} cy=${o.y} r="9" />`;
  if (o.kind === "angle") {
    const r = o.r, a0 = o.a0 * Math.PI / 180, a1 = o.a1 * Math.PI / 180, m = (a0 + a1) / 2;
    const tx = o.x + (r + 46) * Math.cos(m), ty = o.y + (r + 46) * Math.sin(m) + 12;
    return html`<g key=${"a" + i} data-overlay="angle">
      <path class="sim-angle" d=${`M${F(o.x + r * Math.cos(a0))},${F(o.y + r * Math.sin(a0))} A${r},${r} 0 0,1 ${F(o.x + r * Math.cos(a1))},${F(o.y + r * Math.sin(a1))}`} />
      <text class="sim-label" x=${F(tx)} y=${F(ty)} text-anchor="end" data-source=${o.src}><tspan class="sym">${o.text}</tspan></text></g>`;
  }
  return null;
}

function label(l) {
  return html`<g key=${l.id} data-label=${l.for} data-src=${l.src}>
    ${l.leader && html`<line class="dg-leader" x1=${l.leader[0][0]} y1=${l.leader[0][1]} x2=${l.leader[1][0]} y2=${l.leader[1][1]} />`}
    <text class="sim-label word part dg-label" x=${l.x} y=${l.y + 12} text-anchor="middle"><tspan class="sym">${l.text}</tspan></text></g>`;
}

// F-019 §4: the solver's force arrows, grouped per body so a sliding body carries its arrows and their labels.
// "mg = 49 N" said / computed / a bare symbol, exactly as the server wrote it; colour is never the only cue.
function valueText(text, role) {
  const i = text.indexOf(" = ");
  const sym = i < 0 ? text : text.slice(0, i);
  return html`<tspan class="sym">${symbolParts(sym)}</tspan>${i >= 0 && html`<tspan class="val">${text.slice(i)}</tspan>`}`;
}

function forces(m) {
  const by = {}, marks = {};
  for (const f of (m && m.forces) || []) (by[f.on] = by[f.on] || []).push(f);
  for (const k of (m && m.marks) || []) { marks[k.on] = k; by[k.on] = by[k.on] || []; }
  // a said mass written in its body ("2 kg"): a tag over the arrows (spot chosen by mech._marks), moving with the body
  const tag = (k) => k && html`<g class="dg-mass" transform=${`translate(${k.x},${k.y}) rotate(${k.rot})`}>
    <rect x=${-k.w / 2} y=${-k.h / 2} width=${k.w} height=${k.h} rx="6" />
    <text data-mark=${k.on} x="0" y="1" text-anchor="middle" dominant-baseline="central" font-size=${k.size}>${k.text}</text></g>`;
  return Object.entries(by).map(([on, fs]) => html`<g key=${"carry-" + on} data-carry=${on}>
    ${fs.map((f) => html`<g key=${f.id} data-force=${f.id} data-kind=${f.kind} data-src=${f.src}>
      ${Arrow({ x1: f.x1, y1: f.y1, x2: f.x2, y2: f.y2, role: f.role, dashed: !f.said_dir, id: f.id })}
      <text class=${`sim-label r-${f.role} dg-force`} x=${f.lx} y=${f.ly} text-anchor=${f.anchor} data-source=${f.src}
        >${valueText(f.text)}</text></g>`)}
  </g>`).concat(Object.values(marks).map((k) => html`<g key=${"mark-" + k.on} data-carry=${k.on}>${tag(k)}</g>`));
}

function panel(m) {
  const pn = m && m.panel;
  if (!pn || !(pn.rows || []).length) return null;
  let y = 44;
  const rows = [];
  for (const [i, r] of pn.rows.entries()) {
    if (r.kind === "head") {
      y += i ? 14 : 0;
      rows.push(html`<text key=${"h" + i} class="tag dg-panel-head" x="22" y=${y}>${r.text}</text>`);
      y += 36;
      continue;
    }
    rows.push(html`<g key=${"r" + i} data-row=${r.src}>
      <text class=${"sim-label r-ink dg-panel-val" + (r.src === "computed" ? " computed" : "")} x="22" y=${y + 8}
        data-source=${r.src}>${valueText(r.text)}</text>
      ${r.sub && html`<text class="dg-panel-sub" x="22" y=${y + 38}>${r.sub}</text>`}</g>`);
    y += r.sub ? 74 : 50;
  }
  for (const [i, n] of ((m.notes || []).entries())) {
    rows.push(html`<text key=${"n" + i} class="dg-panel-note" x="22" y=${y + 6}>${n}</text>`);
    y += 32;
  }
  if (pn.foot) { rows.push(html`<text key="foot" class="dg-panel-sub" x="22" y=${y + 10}>${pn.foot}</text>`); y += 30; }
  // Python fits the panel to the slide (mech._fit: its steps mirror the ones above)
  return html`<g class="sim-readout dg-panel" data-panel="values"
    transform=${`translate(${pn.x},${pn.y}) scale(${pn.scale || 1})`}>
    <rect class="card" x="0" y="0" width=${pn.w} height=${y + 10} rx="18" />${rows}</g>`;
}

// F-019 M2: the free-body view: each body alone (Python placed it), every force from its centre dot, the forces the
// body on top puts on it too; drawn instead of the scene, standing still
function freeBody(fb, uid) {
  return html`<g class="dg-fbd" data-fbd="1">
    <text class="tag dg-fbd-head" x="60" y=${fb.name_y - 34}>Free-body diagram</text>
    ${fb.bodies.map((b) => html`<g key=${"fb-" + b.id} data-fbd-body=${b.id}>
      ${part({ id: "fbd-" + b.id, kind: "block", cx: b.cx, cy: b.cy, w: b.w, h: b.h, rot: b.rot, attr: {}, uid })}
      <circle class="dg-fbd-dot" cx=${b.cx} cy=${b.cy} r="7" />
      <text class="sim-label word dg-fbd-name" x=${b.cx} y=${fb.name_y} text-anchor="middle">${b.name}${b.mass ? ` · ${b.mass}` : ""}</text></g>`)}
    ${forces({ forces: fb.forces })}</g>`;
}

let SEQ = 0;  // each drawn diagram's own clip ids (two diagram slides can share part ids)

export function DiagramSvg({ p }) {
  const uid = useRef(0);
  if (!uid.current) uid.current = ++SEQ;
  const own = (x) => part({ ...x, uid: uid.current });
  const wires = p.wires || [];
  const under = wires.filter((w) => w.kind === "orbit" || w.kind === "field");
  const over = wires.filter((w) => w.kind !== "orbit" && w.kind !== "field");
  const badges = p.badges || [];
  const fb = p.mech && p.mech.fbd;
  return html`<svg class="diagram-svg" viewBox=${`0 0 ${(p.view || [1600, 1000]).join(" ")}`} preserveAspectRatio="xMidYMid meet"
      data-rev=${p.rev || 0}>
    ${fb ? freeBody(fb, uid.current) : html`
    ${under.map(wire)}
    ${(p.parts || []).filter((x) => x.kind !== "electron" && x.kind !== "planet").map(own)}
    ${over.map(wire)}
    ${(p.parts || []).filter((x) => x.kind === "electron" || x.kind === "planet").map(own)}
    ${(p.overlays || []).map(overlay)}
    ${(p.labels || []).map(label)}
    ${forces(p.mech)}`}
    ${panel(p.mech)}
    ${badges.map((b, i) => html`<text key=${"b" + i} class="sim-caption dg-badge" x="1560" y=${975 - (badges.length - 1 - i) * 30} text-anchor="end">${b}</text>`)}
  </svg>`;
}

// F-019 M2: a value said again re-solves the scene; each arrow (same id) moves from its old place to the new one in
// MORPH s (tip, start and label; both ends from Python), then the tracks run as before.
export const MORPH = 0.6;

function arrowGeom(el, a) {
  const line = el.querySelector("line"), head = el.querySelector("path"), text = el.querySelector("text");
  const len = Math.hypot(a.x2 - a.x1, a.y2 - a.y1);
  if (line && head && len >= 4) {
    const ux = (a.x2 - a.x1) / len, uy = (a.y2 - a.y1) / len;
    const bx = a.x2 - ux * HEAD, by = a.y2 - uy * HEAD, px = -uy * HEAD * 0.55, py = ux * HEAD * 0.55;
    line.setAttribute("x1", F(a.x1)); line.setAttribute("y1", F(a.y1));
    line.setAttribute("x2", F(bx)); line.setAttribute("y2", F(by));
    head.setAttribute("d", `M${F(a.x2)},${F(a.y2)} L${F(bx + px)},${F(by + py)} L${F(bx - px)},${F(by - py)} Z`);
  }
  if (text) { text.setAttribute("x", F(a.lx)); text.setAttribute("y", F(a.ly)); }
}

export function morph(svg, prev, cur, t) {
  if (!svg || !prev || !cur) return;
  const k = Math.min(1, Math.max(0, t / MORPH));
  const e = k < 0.5 ? 2 * k * k : 1 - (-2 * k + 2) ** 2 / 2;  // ease in-out
  const old = Object.fromEntries(prev.map((a) => [a.id, a]));
  for (const a of cur) {
    const o = old[a.id], el = svg.querySelector(`[data-force="${CSS.escape(a.id)}"]`);
    if (!o || !el) continue;
    const m = {};
    for (const key of ["x1", "y1", "x2", "y2", "lx", "ly"]) m[key] = o[key] + (a[key] - o[key]) * e;
    arrowGeom(el, m);
  }
}

const shown = (p) => (p && p.mech ? (p.mech.fbd ? p.mech.fbd.forces : p.mech.forces) || [] : []);

// One frame of the patch's tracks at time t (s). Pure: the same t always gives the same picture.
export function frame(svg, p, t) {
  if (!svg || !p) return;
  const byId = (id) => svg.querySelector(`[data-id="${CSS.escape(id)}"]`);
  const parts = Object.fromEntries((p.parts || []).map((x) => [x.id, x]));
  for (const tr of p.tracks || []) {
    if (tr.kind === "orbit") {
      const el = byId(tr.id), x = parts[tr.id];
      if (!el || !x) continue;
      const a = tr.phase + (tr.dir || 1) * 2 * Math.PI * t / tr.period;
      const nx = tr.cx + tr.rx * Math.cos(a), ny = tr.cy + tr.ry * Math.sin(a);
      el.setAttribute("transform", `translate(${F(nx)},${F(ny)}) rotate(${x.rot || 0})`);
      const lab = svg.querySelector(`[data-label="${CSS.escape(tr.id)}"]`);
      if (lab) lab.setAttribute("transform", `translate(${F(nx - x.cx)},${F(ny - x.cy)})`);
      if (tr.carry) {  // M5: v along the circle and a_c to its centre turn with the body (drawn at t = 0)
        const deg = (a - tr.phase) * 180 / Math.PI;
        for (const c of svg.querySelectorAll(`[data-carry="${CSS.escape(tr.id)}"]`)) {
          c.setAttribute("transform", `rotate(${F(deg)} ${tr.cx} ${tr.cy})`);
          for (const tx of c.querySelectorAll("text")) {  // the words stay upright
            tx.setAttribute("transform", `rotate(${F(-deg)} ${tx.getAttribute("x")} ${tx.getAttribute("y")})`);
          }
        }
      }
    } else if (tr.kind === "path") {
      // F-019 M5: the solver's x(t), y(t) sampled (offsets from the part's place), a run, a rest at the end, again
      const el = byId(tr.id), x = parts[tr.id];
      if (!el || !x || !tr.pts.length) continue;
      const s = Math.min(t % (tr.run + tr.hold), tr.run);
      let i = 1;
      while (i < tr.pts.length - 1 && tr.pts[i][0] < s) i++;
      const [t0, x0, y0] = tr.pts[i - 1], [t1, x1, y1] = tr.pts[Math.min(i, tr.pts.length - 1)];
      const k = t1 > t0 ? Math.min(1, Math.max(0, (s - t0) / (t1 - t0))) : 1;
      const dx = x0 + (x1 - x0) * k, dy = y0 + (y1 - y0) * k;
      el.setAttribute("transform", `translate(${F(x.cx + dx)},${F(x.cy + dy)}) rotate(${x.rot || 0})`);
      const move = `translate(${F(dx)},${F(dy)})`;
      const lab = svg.querySelector(`[data-label="${CSS.escape(tr.id)}"]`);
      if (lab) lab.setAttribute("transform", move);
      for (const carry of svg.querySelectorAll(`[data-carry="${CSS.escape(tr.id)}"]`)) carry.setAttribute("transform", move);
    } else if (tr.kind === "pour") {
      const el = svg.querySelector(`[data-stream="${CSS.escape(tr.id)}"]`);
      if (el) el.style.strokeDashoffset = String(F(-t * 60 * (tr.speed || 1)));
    } else if (tr.kind === "swirl") {
      const el = byId(tr.id), x = parts[tr.id];
      if (!el || !x) continue;
      const tip = [x.cx - Math.sin(x.rot * Math.PI / 180) * x.h / 2, x.cy + Math.cos(x.rot * Math.PI / 180) * x.h / 2];
      const wob = 5 * Math.sin(2 * Math.PI * t / tr.period);
      el.setAttribute("transform", `rotate(${F(wob)} ${F(tip[0])} ${F(tip[1])}) ${tf(x)}`);
      for (const lid of tr.liquids || []) {  // only the stirred container's liquid swirls
        const s = svg.querySelector(`[data-swirl="${CSS.escape(lid)}"]`);
        if (s) { s.style.display = ""; s.style.strokeDashoffset = String(F(-t * 70)); }
      }
    } else if (tr.kind === "heat") {
      const el = byId(tr.id);
      const fl = el && el.querySelector("[data-flame]");
      const k = 2 * Math.PI * t / tr.period;
      if (fl) fl.style.transform = `scale(${(1 + 0.04 * Math.sin(k)).toFixed(3)}, ${(1 + 0.08 * Math.sin(k + 1)).toFixed(3)})`;
    } else if (tr.kind === "slide" || tr.kind === "shm") {
      // F-019: x(t) = ½ a t² for a run, a rest, again (slide); y(t) = amp · sin(2πt / T) about the stretched length (shm)
      const el = byId(tr.id), x = parts[tr.id];
      if (!el || !x) continue;
      let dx = 0, dy = 0;
      if (tr.kind === "slide") {
        const s = Math.min(t % (tr.run + tr.hold), tr.run);
        const d = 0.5 * tr.acc * s * s;
        dx = tr.ux * d; dy = tr.uy * d;
      } else {
        dy = tr.amp * Math.sin(2 * Math.PI * t / tr.period);
        const sp = byId(tr.spring), spx = parts[tr.spring];
        if (sp && spx) {
          const k = (spx.h + dy) / spx.h;
          sp.setAttribute("transform", `translate(${F(spx.cx)},${F(spx.cy + dy / 2)}) rotate(${spx.rot || 0}) scale(1,${k.toFixed(4)})`);
        }
      }
      el.setAttribute("transform", `translate(${F(x.cx + dx)},${F(x.cy + dy)}) rotate(${x.rot || 0})`);
      const move = `translate(${F(dx)},${F(dy)})`;
      const lab = svg.querySelector(`[data-label="${CSS.escape(tr.id)}"]`);
      if (lab) lab.setAttribute("transform", move);
      for (const carry of svg.querySelectorAll(`[data-carry="${CSS.escape(tr.id)}"]`)) carry.setAttribute("transform", move);
      for (const r of tr.ropes || []) {
        const w = (p.wires || []).find((x) => x.id === r.id), path = svg.querySelector(`[data-rope="${CSS.escape(r.id)}"]`);
        if (!w || !path) continue;
        const pts = w.pts.map((q, i) => (i === (r.end < 0 ? w.pts.length - 1 : r.end) ? [q[0] + dx, q[1] + dy] : q));
        path.setAttribute("d", "M" + pts.map((q) => `${F(q[0])},${F(q[1])}`).join(" L"));
      }
    } else if (tr.kind === "flow") {
      for (const el of svg.querySelectorAll("[data-flow]")) el.style.strokeDashoffset = String(F(-t * 40 * (tr.speed || 1)));
    }
  }
}

export function DiagramView({ b, onClick }) {
  const host = useRef(null);
  const st = useRef({ raf: 0, t0: 0, rev: -1, prev: null, last: null });
  const p = b.diagram;
  useLayoutEffect(() => {  // before paint: a morph starts at the old arrows, no flash of the new
    const s = st.current;
    const svg = host.current && host.current.querySelector("svg");
    cancelAnimationFrame(s.raf);
    if (!svg || !p) return undefined;
    if ((p.rev || 0) !== s.rev) {
      s.rev = p.rev || 0; s.t0 = performance.now();
      s.prev = s.last && !!(s.last.mech && s.last.mech.fbd) === !!(p.mech && p.mech.fbd) ? shown(s.last) : null;
      s.last = p;
      if (s.prev) s.t0 += MORPH * 1000;  // the tracks start once the arrows have moved
    }
    if (b.still || reduced()) {
      if (s.prev) { morph(svg, s.prev, shown(p), MORPH); s.prev = null; }  // no move: the arrows at their new place
      frame(svg, p, 0);
      return undefined;
    }
    const loop = () => {
      const t = (performance.now() - s.t0) / 1000;  // < 0 while the arrows move (the bodies at their run's start)
      if (s.prev && t < 0) { frame(svg, p, 0); morph(svg, s.prev, shown(p), t + MORPH); }
      else {
        if (s.prev) { morph(svg, s.prev, shown(p), MORPH); s.prev = null; }
        frame(svg, p, Math.max(0, t));
      }
      s.raf = requestAnimationFrame(loop);
    };
    loop();
    return () => cancelAnimationFrame(s.raf);
  }, [p && p.rev, b.still]);
  return html`<div class=${"diagram-view" + (b.still ? " still" : "") + (b.frozen ? " frozen" : "")} data-diagram=${b.id}
      data-rev=${p ? p.rev || 0 : 0} ref=${host} onClick=${onClick}>
    ${p && html`<${DiagramSvg} p=${p} />`}
  </div>`;
}
