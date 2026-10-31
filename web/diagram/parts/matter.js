// Matter and astronomy parts (F-018 K1): the atom is drawn by its sub-parts (nucleus, shells, electrons, laid out by
// Python from the shell table); the sun and planets (sizes relative, not to scale; orbits are wires).
import { html } from "../../vendor/htm-preact-standalone.mjs";

export const matter = {
  atom: () => null,
  nucleus: ({ w, attr }) => html`<g><circle class="sim-nucleus" cx="0" cy="0" r=${w / 2} />
    ${attr && attr.symbol && html`<text class="dg-nuc-sym" x="0" y=${w * 0.13} text-anchor="middle">${attr.symbol}</text>`}</g>`,
  shell: ({ w }) => html`<circle class="sim-shell on" cx="0" cy="0" r=${w / 2} />`,
  electron: ({ w }) => html`<circle class="sim-electron" cx="0" cy="0" r=${w / 2} />`,
  sun: ({ w }) => html`<g><circle class="dg-sun-halo" cx="0" cy="0" r=${w * 0.66} /><circle class="dg-sun" cx="0" cy="0" r=${w / 2} /></g>`,
  planet: ({ w, attr }) => html`<g class=${`dg-planet t-${(attr && attr.tint) || "rock"}`}>
    ${attr && attr.rings && html`<ellipse class="dg-rings" cx="0" cy="0" rx=${w * 0.95} ry=${w * 0.3} />`}
    <circle cx="0" cy="0" r=${w / 2} />
    ${attr && attr.rings && html`<path class="dg-rings" d=${`M${-w * 0.95},0 A${w * 0.95},${w * 0.3} 0 0,0 ${w * 0.95},0`} />`}</g>`,
};
