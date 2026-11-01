// Motion parts (F-019 M5): drawn in the part's own frame, centred on (0, 0), size w x h (diagram units). A ball, a
// car (attr.flip: faces left), a boat (nose to +x; the layout turns it to its heading), a river band (flowing dashes,
// data-flow), rain (dashes slanted by attr.slant degrees from the vertical, the way the walker sees it) and a simple
// K1 figure (no puppet) with an umbrella tilted forward by attr.umbrella degrees. The S0-S4 look, both themes.
import { html } from "../../vendor/htm-preact-standalone.mjs";

const rainLines = (w, h, slant) => {
  const out = [];
  const dx = h * Math.tan((slant || 0) * Math.PI / 180);
  const step = 46;
  for (let x = -w / 2 - Math.max(0, dx); x < w / 2 + Math.max(0, -dx); x += step) {
    for (let row = 0; row < 2; row++) {
      const off = row * step / 2;
      out.push(html`<line key=${`${x}-${row}`} class="dg-rain" data-flow="1" x1=${x + dx + off} y1=${-h / 2} x2=${x + off} y2=${h / 2} />`);
    }
  }
  return out;
};

export const motion = {
  ball: ({ w }) => html`<circle class="sim-bob dg-ball" cx="0" cy="0" r=${w / 2} />`,
  car: ({ w, h, attr }) => html`<g transform=${attr && attr.flip ? "scale(-1,1)" : ""}>
    <path class="sim-block dg-car" d=${`M${-w / 2},${h * 0.28} L${-w / 2},${-h * 0.05} Q${-w / 2},${-h * 0.12} ${-w * 0.42},${-h * 0.12}
      L${-w * 0.22},${-h * 0.14} L${-w * 0.1},${-h / 2} L${w * 0.22},${-h / 2} L${w * 0.36},${-h * 0.12}
      Q${w / 2},${-h * 0.1} ${w / 2},${h * 0.05} L${w / 2},${h * 0.28} Z`} />
    <path class="dg-window" d=${`M${-w * 0.06},${-h * 0.4} L${w * 0.18},${-h * 0.4} L${w * 0.28},${-h * 0.15} L${-w * 0.14},${-h * 0.15} Z`} />
    <circle class="dg-wheel" cx=${-w * 0.27} cy=${h * 0.3} r=${h * 0.2} /><circle class="dg-wheel" cx=${w * 0.27} cy=${h * 0.3} r=${h * 0.2} /></g>`,
  boat: ({ w, h }) => html`<g>
    <path class="sim-block dg-boat" d=${`M${-w / 2},${-h / 2} L${w * 0.25},${-h / 2} L${w / 2},0 L${w * 0.25},${h / 2} L${-w / 2},${h / 2} Z`} />
    <line class="dg-seat" x1=${-w * 0.12} y1=${-h / 2 + 8} x2=${-w * 0.12} y2=${h / 2 - 8} /></g>`,
  river: ({ w, h }) => {
    const lines = [];
    for (let k = 1; k < 4; k++) lines.push(html`<line key=${k} class="dg-flow" data-flow="1" x1=${-w / 2} y1=${-h / 2 + h * k / 4} x2=${w / 2} y2=${-h / 2 + h * k / 4} />`);
    return html`<g><rect class="dg-river" x=${-w / 2} y=${-h / 2} width=${w} height=${h} />${lines}
      <line class="sim-surface" x1=${-w / 2} y1=${-h / 2} x2=${w / 2} y2=${-h / 2} /><line class="sim-surface" x1=${-w / 2} y1=${h / 2} x2=${w / 2} y2=${h / 2} /></g>`;
  },
  rain: ({ w, h, attr, uid, id }) => {
    const clip = `rc-${uid || 0}-${id}`;
    return html`<g class="dg-rain-g"><clipPath id=${clip}><rect x=${-w / 2} y=${-h / 2} width=${w} height=${h} /></clipPath>
      <g clip-path=${`url(#${clip})`}>${rainLines(w, h, attr && attr.slant)}</g></g>`;
  },
  man: ({ w, h, attr }) => {
    const head = w * 0.24, top = -h / 2 + head, hip = h * 0.12, foot = h / 2;
    const hand = [w * 0.32, -h * 0.04];
    const tilt = attr && attr.umbrella !== undefined ? attr.umbrella : null;
    return html`<g class="dg-figure">
      <circle cx="0" cy=${top} r=${head} />
      <line x1="0" y1=${top + head} x2="0" y2=${hip} />
      <line x1="0" y1=${hip} x2=${-w * 0.3} y2=${foot} /><line x1="0" y1=${hip} x2=${w * 0.3} y2=${foot} />
      <line x1="0" y1=${-h * 0.18} x2=${hand[0]} y2=${hand[1]} /><line x1="0" y1=${-h * 0.18} x2=${-w * 0.3} y2=${-h * 0.02} />
      ${tilt !== null && html`<g class="dg-umbrella" transform=${`rotate(${tilt} ${hand[0]} ${hand[1]})`}>
        <line x1=${hand[0]} y1=${hand[1]} x2=${hand[0]} y2=${-h / 2 - 40} />
        <path d=${`M${hand[0] - 92},${-h / 2 - 34} Q${hand[0]},${-h / 2 - 130} ${hand[0] + 92},${-h / 2 - 34} Z`} /></g>`}
    </g>`;
  },
};
