// Mechanics parts (F-018 K1): drawn in the part's own frame, centred on (0, 0), size w x h (diagram units). The S0-S4
// look: sim-* classes (tokens.css roles, light and dark), the same line weights as the simulation templates.
import { html } from "../../vendor/htm-preact-standalone.mjs";

export const hatch = (x1, x2, y, dir = 1, step = 26) => {
  const out = [];
  for (let x = x1 + 8; x < x2; x += step) out.push(html`<line key=${x} class="sim-hatch-line" x1=${x} y1=${y} x2=${x - 16} y2=${y + dir * 18} />`);
  return out;
};

export const mech = {
  block: ({ w, h }) => html`<rect class="sim-block" x=${-w / 2} y=${-h / 2} width=${w} height=${h} rx="10" />`,
  mass: ({ w, h }) => html`<g>
    <circle class="dg-hook" cx="0" cy=${-h / 2 + 9} r="9" />
    <line class="dg-hook" x1="0" y1=${-h / 2 + 18} x2="0" y2=${-h / 2 + 28} />
    <rect class="sim-block" x=${-w / 2} y=${-h / 2 + 28} width=${w} height=${h - 28} rx="8" /></g>`,
  incline: ({ w, h }) => html`<g>
    <path class="sim-wedge" d=${`M${-w / 2},${h / 2} L${w / 2},${h / 2} L${-w / 2},${-h / 2} Z`} />
    <line class="sim-surface" x1=${-w / 2 - 40} y1=${h / 2} x2=${w / 2 + 40} y2=${h / 2} />
    ${hatch(-w / 2 - 40, w / 2 + 40, h / 2)}</g>`,
  floor: ({ w, h }) => html`<g><line class="sim-surface" x1=${-w / 2} y1=${-h / 2} x2=${w / 2} y2=${-h / 2} />${hatch(-w / 2, w / 2, -h / 2)}</g>`,
  support: ({ w, h }) => html`<g><line class="sim-surface" x1=${-w / 2} y1=${h / 2} x2=${w / 2} y2=${h / 2} />${hatch(-w / 2, w / 2, h / 2, -1)}</g>`,
  spring: ({ w, h }) => {
    const lead = 18, n = 11, top = -h / 2 + lead, bot = h / 2 - lead, step = (bot - top) / n;
    let d = `M0,${-h / 2} L0,${top}`;
    for (let i = 0; i < n; i++) d += ` L${(i % 2 ? -1 : 1) * w / 2},${top + step * (i + 0.5)}`;
    d += ` L0,${bot} L0,${h / 2}`;
    return html`<path class="dg-spring" d=${d} />`;
  },
  pulley: ({ w }) => html`<g><circle class="sim-bob" cx="0" cy="0" r=${w / 2} /><circle class="dg-groove" cx="0" cy="0" r=${w / 2 - 12} />
    <circle class="sim-pivot" cx="0" cy="0" r="9" /></g>`,
};
