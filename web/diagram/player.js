// The concept-diagram player (F-018 K1, docs/contracts/diagram-spec.md §7): draws a `diagram.patch` (the stage
// block's `diagram`) full slide under the title, in the S0-S4 simulation look. Every position comes from Python; the
// browser draws and runs the patch's tracks, seamless loops that are a pure function of the time t (orbits, the pour
// stream, the stirring rod, the flame, the field's flowing dashes). still: the slide's figure at t = 0, no clock.
import { html, useEffect, useRef } from "../vendor/htm-preact-standalone.mjs";
import { PARTS, ABSOLUTE } from "./parts/index.js";

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
  return html`<path key=${w.id} class=${w.kind === "rope" ? "sim-string dg-rope" : "sim-wire"} d=${d} fill="none" />`;
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

let SEQ = 0;  // each drawn diagram's own clip ids (two diagram slides can share part ids)

export function DiagramSvg({ p }) {
  const uid = useRef(0);
  if (!uid.current) uid.current = ++SEQ;
  const own = (x) => part({ ...x, uid: uid.current });
  const wires = p.wires || [];
  const under = wires.filter((w) => w.kind === "orbit" || w.kind === "field");
  const over = wires.filter((w) => w.kind !== "orbit" && w.kind !== "field");
  const badges = p.badges || [];
  return html`<svg class="diagram-svg" viewBox=${`0 0 ${(p.view || [1600, 1000]).join(" ")}`} preserveAspectRatio="xMidYMid meet"
      data-rev=${p.rev || 0}>
    ${under.map(wire)}
    ${(p.parts || []).filter((x) => x.kind !== "electron" && x.kind !== "planet").map(own)}
    ${over.map(wire)}
    ${(p.parts || []).filter((x) => x.kind === "electron" || x.kind === "planet").map(own)}
    ${(p.overlays || []).map(overlay)}
    ${(p.labels || []).map(label)}
    ${badges.map((b, i) => html`<text key=${"b" + i} class="sim-caption dg-badge" x="1560" y=${975 - (badges.length - 1 - i) * 30} text-anchor="end">${b}</text>`)}
  </svg>`;
}

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
    } else if (tr.kind === "flow") {
      for (const el of svg.querySelectorAll("[data-flow]")) el.style.strokeDashoffset = String(F(-t * 40 * (tr.speed || 1)));
    }
  }
}

export function DiagramView({ b, onClick }) {
  const host = useRef(null);
  const st = useRef({ raf: 0, t0: 0, rev: -1 });
  const p = b.diagram;
  useEffect(() => {
    const s = st.current;
    const svg = host.current && host.current.querySelector("svg");
    cancelAnimationFrame(s.raf);
    if (!svg || !p) return undefined;
    if ((p.rev || 0) !== s.rev) { s.rev = p.rev || 0; s.t0 = performance.now(); }
    if (b.still || reduced()) { frame(svg, p, 0); return undefined; }
    const loop = () => { frame(svg, p, (performance.now() - s.t0) / 1000); s.raf = requestAnimationFrame(loop); };
    loop();
    return () => cancelAnimationFrame(s.raf);
  }, [p && p.rev, b.still]);
  return html`<div class=${"diagram-view" + (b.still ? " still" : "") + (b.frozen ? " frozen" : "")} data-diagram=${b.id}
      data-rev=${p ? p.rev || 0 : 0} ref=${host} onClick=${onClick}>
    ${p && html`<${DiagramSvg} p=${p} />`}
  </div>`;
}
