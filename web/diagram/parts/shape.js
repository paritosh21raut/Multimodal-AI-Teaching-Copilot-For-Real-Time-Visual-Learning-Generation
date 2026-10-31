// Plain shapes and the unknown part (F-018 K1): outlines with a light fill; the unknown part is a dashed box that
// carries the said word (never a wrong symbol).
import { html } from "../../vendor/htm-preact-standalone.mjs";

function poly(n, w, h) {
  const a0 = n % 2 ? -Math.PI / 2 : 0;  // a pentagon point up, a hexagon point sideways: a flat bottom both ways
  const pts = Array.from({ length: n }, (_, i) => [Math.cos(a0 + (2 * Math.PI * i) / n), Math.sin(a0 + (2 * Math.PI * i) / n)]);
  const [x0, x1] = [Math.min(...pts.map((p) => p[0])), Math.max(...pts.map((p) => p[0]))];
  const [y0, y1] = [Math.min(...pts.map((p) => p[1])), Math.max(...pts.map((p) => p[1]))];
  return pts.map(([x, y], i) => `${i ? "L" : "M"}${(((x - x0) / (x1 - x0)) - 0.5) * w},${(((y - y0) / (y1 - y0)) - 0.5) * h}`).join(" ") + " Z";
}

export const shape = {
  circle: ({ w }) => html`<circle class="dg-shape" cx="0" cy="0" r=${w / 2} />`,
  square: ({ w, h }) => html`<rect class="dg-shape" x=${-w / 2} y=${-h / 2} width=${w} height=${h} />`,
  rectangle: ({ w, h }) => html`<rect class="dg-shape" x=${-w / 2} y=${-h / 2} width=${w} height=${h} />`,
  triangle: ({ w, h }) => html`<path class="dg-shape" d=${`M0,${-h / 2} L${w / 2},${h / 2} L${-w / 2},${h / 2} Z`} />`,
  // M0 (test37): regular polygons, flat side down, scaled to the part box
  pentagon: ({ w, h }) => html`<path class="dg-shape" d=${poly(5, w, h)} />`,
  hexagon: ({ w, h }) => html`<path class="dg-shape" d=${poly(6, w, h)} />`,
  unknown: ({ w, h }) => html`<rect class="dg-unknown" x=${-w / 2} y=${-h / 2} width=${w} height=${h} rx="16" />`,
};
