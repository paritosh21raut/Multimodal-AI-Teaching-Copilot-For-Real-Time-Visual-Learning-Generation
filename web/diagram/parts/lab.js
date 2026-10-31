// Lab parts (F-018 K1): glassware outlines (sim-flask), a liquid drawn as its container's inside below the level, a
// tilted pourer with its own liquid kept level, a glass rod, a burner on a tripod with gauze (the "on" surface).
import { html } from "../../vendor/htm-preact-standalone.mjs";

// the inside of a container, in its own frame (also the clip of its liquid)
export function inside(kind, w, h, inset = 5) {
  const L = -w / 2 + inset, R = w / 2 - inset, T = -h / 2, B = h / 2 - inset;
  if (kind === "flask") {
    const n = w * 0.14 - inset, sh = -h / 2 + h * 0.32;
    return `M${-n},${T} L${-n},${sh} L${L},${B - 12} Q${L},${B} ${L + 14},${B} L${R - 14},${B} Q${R},${B} ${R},${B - 12} L${n},${sh} L${n},${T} Z`;
  }
  if (kind === "test_tube") {
    const r = (R - L) / 2;
    return `M${L},${T} L${L},${B - r} A${r},${r} 0 0,0 ${R},${B - r} L${R},${T} Z`;
  }
  return `M${L},${T + 8} L${L},${B - 12} Q${L},${B} ${L + 12},${B} L${R - 12},${B} Q${R},${B} ${R},${B - 12} L${R},${T + 8} Z`;
}

function outline(kind, w, h) {
  if (kind === "flask") {
    const n = w * 0.14, sh = -h / 2 + h * 0.32;
    return `M${-n - 8},${-h / 2} L${-n},${-h / 2 + 8} L${-n},${sh} L${-w / 2},${h / 2 - 14} Q${-w / 2},${h / 2} ${-w / 2 + 16},${h / 2} L${w / 2 - 16},${h / 2} Q${w / 2},${h / 2} ${w / 2},${h / 2 - 14} L${n},${sh} L${n},${-h / 2 + 8} L${n + 8},${-h / 2}`;
  }
  if (kind === "test_tube") {
    return `M${-w / 2 - 6},${-h / 2} L${-w / 2},${-h / 2 + 6} L${-w / 2},${h / 2 - w / 2} A${w / 2},${w / 2} 0 0,0 ${w / 2},${h / 2 - w / 2} L${w / 2},${-h / 2 + 6} L${w / 2 + 6},${-h / 2}`;
  }
  return `M${-w / 2 - 12},${-h / 2} L${-w / 2},${-h / 2 + 12} L${-w / 2},${h / 2 - 14} Q${-w / 2},${h / 2} ${-w / 2 + 14},${h / 2} L${w / 2 - 14},${h / 2} Q${w / 2},${h / 2} ${w / 2},${h / 2 - 14} L${w / 2},${-h / 2}`;
}

const glass = (kind) => ({ w, h }) => html`<g>
  <path class="dg-glass" d=${inside(kind, w, h, 0)} />
  <path class="sim-flask" d=${outline(kind, w, h)} />
  ${kind === "beaker" && [0.35, 0.5, 0.65, 0.8].map((f) => html`<line key=${f} class="dg-grad" x1=${w / 2 - 34} y1=${-h / 2 + f * h} x2=${w / 2 - 8} y2=${-h / 2 + f * h} />`)}</g>`;

// the liquid: absolute coordinates (its container's box in attr.cbox), the container's inside clipped below the level
function liquid(p) {
  const a = p.attr || {};
  const [cx, cy, w, h] = a.cbox || [p.cx, p.cy, p.w, p.h];
  const id = `clip-${p.uid || 0}-${p.id}`;
  const d = inside(a.container || "beaker", w, h);
  return html`<g class=${`dg-liquid-g t-${a.tint || "water"}`} data-id=${p.id}>
    <clipPath id=${id}><rect x=${cx - w} y=${a.level} width=${2 * w} height=${2 * h} /></clipPath>
    <clipPath id=${id + "i"}><path transform=${`translate(${cx},${cy})`} d=${d} /></clipPath>
    <path class="dg-liquid" clip-path=${`url(#${id})`} transform=${`translate(${cx},${cy})`} d=${d} />
    <line class="dg-meniscus" x1=${cx - w} y1=${a.level} x2=${cx + w} y2=${a.level} clip-path=${`url(#${id}i)`} />
    <ellipse class="dg-swirl" data-swirl=${p.id} cx=${cx} cy=${(a.level + a.floor) / 2} rx=${w * 0.28} ry=${Math.max(8, (a.floor - a.level) * 0.18)}
      style="display:none" />
  </g>`;
}

// a small beaker with a spout at its top right, tilted by the layout; its liquid stays level on screen
function pourer({ id, w, h, rot, attr, uid }) {
  const a = attr || {};
  const clip = `pclip-${uid || 0}-${id}`;
  return html`<g class=${`t-${a.tint || "water"}`}>
    <clipPath id=${clip}><rect transform=${`rotate(${-rot})`} x=${-2 * w} y=${-h * 0.02} width=${4 * w} height=${2 * h} /></clipPath>
    <path class="dg-liquid" clip-path=${`url(#${clip})`} d=${inside("beaker", w, h)} />
    <path class="sim-flask" d=${`M${-w / 2},${-h / 2} L${-w / 2},${h / 2 - 12} Q${-w / 2},${h / 2} ${-w / 2 + 12},${h / 2} L${w / 2 - 12},${h / 2} Q${w / 2},${h / 2} ${w / 2},${h / 2 - 12} L${w / 2},${-h / 2 + 10} L${w / 2 + 14},${-h / 2 - 4}`} /></g>`;
}

const stirrer = ({ w, h }) => html`<rect class="dg-rod" x=${-w / 2} y=${-h / 2} width=${w} height=${h} rx=${w / 2} />`;

function burner({ w, h }) {
  const top = -h / 2, bot = h / 2, tubeTop = top + h * 0.42;
  return html`<g>
    <line class="dg-tripod" x1=${-w * 0.42} y1=${top + 6} x2=${-w * 0.47} y2=${bot} />
    <line class="dg-tripod" x1=${w * 0.42} y1=${top + 6} x2=${w * 0.47} y2=${bot} />
    <g class="dg-flame-g" data-flame="1" style=${`transform-origin: 0px ${tubeTop}px; transform-box: view-box`}>
      <path class="dg-flame" d=${`M0,${top + 28} C${w * 0.12},${tubeTop - 40} ${w * 0.09},${tubeTop} 0,${tubeTop} C${-w * 0.09},${tubeTop} ${-w * 0.12},${tubeTop - 40} 0,${top + 28} Z`} />
      <path class="dg-flame-in" d=${`M0,${top + 70} C${w * 0.05},${tubeTop - 26} ${w * 0.04},${tubeTop} 0,${tubeTop} C${-w * 0.04},${tubeTop} ${-w * 0.05},${tubeTop - 26} 0,${top + 70} Z`} />
    </g>
    <line class="dg-gauze" x1=${-w / 2} y1=${top + 5} x2=${w / 2} y2=${top + 5} />
    ${[-0.4, -0.25, -0.1, 0.05, 0.2, 0.35].map((f) => html`<line key=${f} class="dg-mesh" x1=${f * w} y1=${top + 1} x2=${f * w + 12} y2=${top + 9} />`)}
    <rect class="dg-tube" x="-17" y=${tubeTop} width="34" height=${bot - 26 - tubeTop} />
    <path class="dg-tube" d=${`M${-w * 0.2},${bot} L${-w * 0.14},${bot - 26} L${w * 0.14},${bot - 26} L${w * 0.2},${bot} Z`} /></g>`;
}

export const lab = { beaker: glass("beaker"), flask: glass("flask"), test_tube: glass("test_tube"), pourer, stirrer, burner };
export const absolute = { liquid };
