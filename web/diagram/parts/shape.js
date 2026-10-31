// Plain shapes and the unknown part (F-018 K1): outlines with a light fill; the unknown part is a dashed box that
// carries the said word (never a wrong symbol).
import { html } from "../../vendor/htm-preact-standalone.mjs";

export const shape = {
  circle: ({ w }) => html`<circle class="dg-shape" cx="0" cy="0" r=${w / 2} />`,
  square: ({ w, h }) => html`<rect class="dg-shape" x=${-w / 2} y=${-h / 2} width=${w} height=${h} />`,
  rectangle: ({ w, h }) => html`<rect class="dg-shape" x=${-w / 2} y=${-h / 2} width=${w} height=${h} />`,
  triangle: ({ w, h }) => html`<path class="dg-shape" d=${`M0,${-h / 2} L${w / 2},${h / 2} L${-w / 2},${h / 2} Z`} />`,
  unknown: ({ w, h }) => html`<rect class="dg-unknown" x=${-w / 2} y=${-h / 2} width=${w} height=${h} rx="16" />`,
};
