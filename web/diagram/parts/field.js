// Fields and circuit parts (F-018 K1; K2 wires the circuits). The bar magnet's N half is red, S blue, letters on both
// (colour is never the only cue); a compass needle points along the field Python computed (attr.needle).
import { html } from "../../vendor/htm-preact-standalone.mjs";

export const field = {
  bar_magnet: ({ w, h }) => html`<g>
    <rect class="dg-pole s" x=${-w / 2} y=${-h / 2} width=${w / 2} height=${h} />
    <rect class="dg-pole n" x="0" y=${-h / 2} width=${w / 2} height=${h} />
    <rect class="dg-magnet" x=${-w / 2} y=${-h / 2} width=${w} height=${h} rx="6" />
    <text class="dg-pole-t" x=${-w / 4} y=${h * 0.2} text-anchor="middle">S</text>
    <text class="dg-pole-t" x=${w / 4} y=${h * 0.2} text-anchor="middle">N</text></g>`,
  compass: ({ w, attr }) => html`<g><circle class="dg-compass" cx="0" cy="0" r=${w / 2} />
    <g transform=${`rotate(${(attr && attr.needle) || 0})`}>
      <path class="dg-needle n" d=${`M${w * 0.4},0 L0,${-w * 0.09} L0,${w * 0.09} Z`} />
      <path class="dg-needle s" d=${`M${-w * 0.4},0 L0,${-w * 0.09} L0,${w * 0.09} Z`} /></g></g>`,
};

export const circuit = {
  cell: ({ w, h }) => html`<g>
    <line class="sim-wire" x1=${-w / 2} y1="0" x2="-9" y2="0" /><line class="sim-wire" x1="9" y1="0" x2=${w / 2} y2="0" />
    <line class="sim-plate" x1="-9" y1=${-h / 2} x2="-9" y2=${h / 2} /><line class="sim-plate short" x1="9" y1=${-h / 4} x2="9" y2=${h / 4} />
    <text class="dg-sign" x="-30" y=${-h / 2 + 10} text-anchor="middle">+</text></g>`,
  resistor: ({ w, h }) => {
    const n = 6, a = w * 0.18, z = (w - 2 * a) / n;
    let d = `M${-w / 2},0 L${-w / 2 + a},0`;
    for (let i = 0; i < n; i++) d += ` L${-w / 2 + a + z * (i + 0.5)},${(i % 2 ? 1 : -1) * h / 2}`;
    d += ` L${w / 2 - a},0 L${w / 2},0`;
    return html`<path class="sim-resistor" d=${d} />`;
  },
  bulb: ({ w }) => {
    const r = w / 2 - 6, k = r * 0.7071;
    return html`<g><circle class="dg-bulb" cx="0" cy="0" r=${r} />
      <line class="sim-wire" x1=${-k} y1=${-k} x2=${k} y2=${k} /><line class="sim-wire" x1=${-k} y1=${k} x2=${k} y2=${-k} />
      <line class="sim-wire" x1=${-w / 2} y1="0" x2=${-r} y2="0" /><line class="sim-wire" x1=${r} y1="0" x2=${w / 2} y2="0" /></g>`;
  },
  switch: ({ w, h, attr }) => {
    const y = h * 0.3, open = attr && attr.state === "open";
    return html`<g><circle class="dg-term" cx=${-w / 2 + 8} cy=${y} r="8" /><circle class="dg-term" cx=${w / 2 - 8} cy=${y} r="8" />
      <line class="sim-wire" x1=${-w / 2 + 8} y1=${y} x2=${open ? w * 0.28 : w / 2 - 8} y2=${open ? y - w * 0.45 : y} /></g>`;
  },
  node: ({ w }) => html`<circle class="dg-node" cx="0" cy="0" r=${w / 2} />`,
};
