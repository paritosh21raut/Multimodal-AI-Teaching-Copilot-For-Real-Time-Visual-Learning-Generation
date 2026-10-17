// Label placement for every simulation scene (F-014 S2, the user's item of 2026-10-18: values overlapped each other on
// the stage, e.g. the long "shown 400× slower" note against the caption, a force label on its angle's label, μ under
// the weight arrow). Deterministic: the same picture always gets the same placement. It moves only where a label is
// drawn, never what it says (the numbers stay Python's).
//
// After each render of a stage:
//   1. fixed: the readout card, the block / bob, arrow lines, the footer texts (caption left, notes right; a note
//      that would run into the caption moves up one line)
//   2. labels (.sim-label outside the readout and the block) in scene order, which is each scene's priority: a label
//      that overlaps a fixed thing or a label placed before it tries OFFSETS in their fixed order and takes the first
//      free spot inside the stage; the spot it had before comes right after its home (little flicker while the block
//      slides). A label that finds no free spot within reach stays where the scene put it (brought inside the stage).
import { H, W } from "./draw.js";

const PAD = 3;         // boxes closer than this count as touching
const STEPS = [26, 52, 78, 104, 140, 180];
const DIRS = [[0, -1], [0, 1], [-1, 0], [1, 0], [-1, -1], [1, -1], [-1, 1], [1, 1]];
export const OFFSETS = [[0, 0], ...STEPS.flatMap((d) => DIRS.map(([x, y]) => [x * d, y * d]))];

// the drawn strokes a label must not sit on (besides the arrows): surfaces, guides, angle arcs, wedges, strings,
// wires, waves, the marked angle and its segments. Not the hatching (texture) and not the readout's card.
export const STROKES = ".sim-surface, .sim-guide, .sim-angle, .sim-wedge, .sim-string, .sim-wire, .sim-resistor, " +
  ".sim-plate, .sim-wave, .sim-marked, .sim-seg";

const hit = (a, b) => a.x < b.x + b.w + PAD && b.x < a.x + a.w + PAD && a.y < b.y + b.h + PAD && b.y < a.y + a.h + PAD;
const inside = (a) => a.x >= 4 && a.y >= 4 && a.x + a.w <= W - 4 && a.y + a.h <= H - 4;
const moved = (b, [dx, dy]) => ({ x: b.x + dx, y: b.y + dy, w: b.w, h: b.h });

// does the segment p-q cross box b (Liang-Barsky)
function crosses(b, p, q) {
  let t0 = 0, t1 = 1;
  const dx = q[0] - p[0], dy = q[1] - p[1];
  for (const [pp, qq] of [[-dx, p[0] - (b.x - PAD)], [dx, b.x + b.w + PAD - p[0]], [-dy, p[1] - (b.y - PAD)], [dy, b.y + b.h + PAD - p[1]]]) {
    if (pp === 0) { if (qq < 0) return false; continue; }
    const r = qq / pp;
    if (pp < 0) { if (r > t1) return false; if (r > t0) t0 = r; } else { if (r < t0) return false; if (r < t1) t1 = r; }
  }
  return true;
}

// a box in the stage's own units (viewBox 1100 x 740), whatever the page's scale
function boxOf(svg, el) {
  const m = svg.getScreenCTM();
  const r = el.getBoundingClientRect();
  if (!m || !r.width) return null;
  const inv = m.inverse();
  const a = new DOMPoint(r.left, r.top).matrixTransform(inv), b = new DOMPoint(r.right, r.bottom).matrixTransform(inv);
  return { x: a.x, y: a.y, w: b.x - a.x, h: b.y - a.y };
}

// a drawn element as straight segments in stage units: a line's two ends, any other shape sampled every ~10 units
export function segments(svg, el) {
  const m = el.getScreenCTM(), sm = svg.getScreenCTM();
  if (!m || !sm) return [];
  const toStage = sm.inverse().multiply(m);  // the element's own units -> the stage's (inside a turned group)
  const at = (x, y) => { const p = new DOMPoint(x, y).matrixTransform(toStage); return [p.x, p.y]; };
  if (el.tagName === "line") {
    return [[at(+el.getAttribute("x1"), +el.getAttribute("y1")), at(+el.getAttribute("x2"), +el.getAttribute("y2"))]];
  }
  if (typeof el.getTotalLength !== "function") return [];
  const total = el.getTotalLength();
  if (!(total > 0)) return [];
  const n = Math.min(300, Math.max(2, Math.ceil(total / 10)));
  const pts = [];
  for (let i = 0; i <= n; i++) { const p = el.getPointAtLength((total * i) / n); pts.push(at(p.x, p.y)); }
  return pts.slice(1).map((q, i) => [pts[i], q]);
}

export function placeLabels(svg) {
  if (!svg || typeof svg.getScreenCTM !== "function") return;
  const fixed = [];
  const lines = [];  // [p, q] in stage units
  const shapes = [];
  for (const el of svg.querySelectorAll(".sim-block, .sim-bob")) {
    const b = boxOf(svg, el);
    if (b) { fixed.push(b); shapes.push(b); }
  }
  for (const el of svg.querySelectorAll(".sim-arrow line")) lines.push(...segments(svg, el));
  const strokes = [];  // not arrows: the card may cover these (it is opaque), a label may not sit on them
  for (const el of svg.querySelectorAll(STROKES)) if (!el.closest(".sim-readout")) strokes.push(...segments(svg, el));
  // the readout card: as wide as its rows, in the first corner (top left, top right, bottom left) where it covers no
  // block, bob or arrow (a steep incline's block stands where the card usually is)
  const card = svg.querySelector(":scope > .sim-readout");
  if (card) {
    const rect = card.querySelector(".card");
    const rows = [...card.querySelectorAll(":scope > g .sim-label")].map((t) => t.getBBox());
    const tag = card.querySelector(".tag");
    // rows sit at x 26 in the card; the "computed" tag at its top right
    const w = Math.max(300, ...rows.map((r) => 26 + r.x + r.width + 30), tag ? tag.getBBox().width + 60 : 0);
    if (Math.abs(+rect.getAttribute("width") - w) > 1) {
      rect.setAttribute("width", w.toFixed(0));
      if (tag) tag.setAttribute("x", (w - 26).toFixed(0));
    }
    const h = +rect.getAttribute("height");
    const spots = [[34, 30], [W - 34 - w, 30], [34, H - 64 - h]];
    const covers = ([x, y]) => { const b = { x, y, w, h };
      return shapes.some((o) => hit(b, o)) || lines.some(([p, q]) => crosses(b, p, q)); };
    const [x, y] = spots.find((p) => !covers(p)) || spots[0];
    card.setAttribute("transform", `translate(${x},${y})`);
    fixed.push({ x, y, w, h });
  }
  // the footer: the caption stays, a note that runs into it goes up a line
  const foot = [...svg.querySelectorAll(":scope > .sim-caption")];
  const placedFoot = [];
  for (const el of foot) {
    el.removeAttribute("transform");
    let b = boxOf(svg, el);
    if (!b) continue;
    let dy = 0;
    while (placedFoot.some((o) => hit(moved(b, [0, dy]), o)) && dy > -120) dy -= 32;
    if (dy) el.setAttribute("transform", `translate(0,${dy})`);
    b = moved(b, [0, dy]);
    placedFoot.push(b);
    fixed.push(b);
  }
  const placed = [];
  for (const el of svg.querySelectorAll(":scope > .sim-label, :scope > g:not([transform]) > .sim-label")) {
    if (el.classList.contains("in-block")) continue;
    const prev = el.dataset.off ? el.dataset.off.split(",").map(Number) : null;
    el.removeAttribute("transform");
    const b = boxOf(svg, el);
    if (!b) continue;
    const free = (c) => inside(c) && !fixed.some((o) => hit(c, o)) && !placed.some((o) => hit(c, o)) &&
      !lines.some(([p, q]) => crosses(c, p, q)) &&  // its own arrow too: a label beside its arrow, not on it
      !strokes.some(([p, q]) => crosses(c, p, q));
    // a home off the stage (a label beside a shape at the edge): the spots around the nearest place inside come last,
    // and that place itself is the fallback, so a label never leaves the stage
    const cx = Math.max(0, 4 - b.x) - Math.max(0, b.x + b.w - (W - 4)), cy = Math.max(0, 4 - b.y) - Math.max(0, b.y + b.h - (H - 4));
    const back = cx || cy ? OFFSETS.map(([x, y]) => [x + cx, y + cy]) : [];
    const order = [...(prev ? [[0, 0], prev, ...OFFSETS] : OFFSETS), ...back];  // home first, then where it was
    const off = order.find((o) => free(moved(b, o)));
    const use = off || [cx, cy];
    if (use[0] || use[1]) {
      el.setAttribute("transform", `translate(${use[0]},${use[1]})`);
      el.dataset.off = use.join(",");
    } else {
      delete el.dataset.off;
    }
    placed.push(moved(b, use));
  }
}
