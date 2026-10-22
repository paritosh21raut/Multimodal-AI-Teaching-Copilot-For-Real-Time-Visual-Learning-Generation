// Scene drawing kinds (F-015, docs/contracts/scene-spec.md): one function per engine shape. Parts, not templates: no
// topic logic here. Every coordinate comes from Python (geom, stage px); every printed text comes from the spec
// (a said name, a said size, a computed note). Colours by role (main / second / third / accent / muted), both themes.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { ICONS } from "../vendor/icons/scene-icons.js";
import { Thing } from "./canvas.js";

const pts = (ps) => ps.map(([x, y]) => `${x},${y}`).join(" ");

// A body's picture for its said noun (scene.assets): an icon (Tabler, 24 x 24 strokes), an LLM glyph (path data on
// the same grid) or the teacher's image, in a box 2.6 r wide, mirrored when it moves west. null: no picture.
function Picture({ e, x, y, r, flip }) {
  const lk = e.look || {};
  const size = r * 2.6, s = size / 24;
  const cls = `sc-body sc-pic r-${lk.role}`;
  if (lk.image) {
    return html`<g class=${cls}><clipPath id=${"pic-" + e.id}><circle cx=${x} cy=${y} r=${size / 2} /></clipPath>
      <image href=${lk.image} x=${x - size / 2} y=${y - size / 2} width=${size} height=${size} preserveAspectRatio="xMidYMid slice"
        clip-path=${`url(#pic-${e.id})`} transform=${flip ? `translate(${2 * x} 0) scale(-1 1)` : undefined} />
      <circle class="pic-ring" cx=${x} cy=${y} r=${size / 2} /></g>`;
  }
  const icon = lk.icon && ICONS[lk.icon];
  if (!icon && !lk.glyph) return null;
  const tf = flip ? `translate(${x + size / 2} ${y - size / 2}) scale(${-s} ${s})` : `translate(${x - size / 2} ${y - size / 2}) scale(${s})`;
  return html`<g class=${cls}><circle class="pic-back" cx=${x} cy=${y} r=${size * 0.55} />
    <g class="pic-lines" transform=${tf}>${icon ? icon.nodes.map(([tag, a], i) => html`<${tag} key=${i} ...${a} />`) : html`<path d=${lk.glyph} />`}</g>
  </g>`;
}

// An umbrella held above a body, tilted from the vertical by `tilt` degrees (+: toward +x), into the rain.
function Umbrella({ x, y, r, tilt }) {
  const R = r * 1.5, top = y - r * 1.2;
  return html`<g class="sc-umbrella" transform=${`rotate(${tilt} ${x} ${top + R * 0.2})`}>
    <path class="canopy" d=${`M${x - R},${top - R * 0.55} A${R},${R * 0.75} 0 0 1 ${x + R},${top - R * 0.55} Z`} />
    <line class="handle" x1=${x} y1=${top - R * 0.55} x2=${x} y2=${top + R * 0.2} />
  </g>`;
}

// A body (ball, block, car, particle) at (x, y), turned by angle degrees (a ball rolls; the others do not turn).
function Body({ e, x, y, angle, flip }) {
  const r = (e.geom && e.geom.r) || 22;
  const pic = Picture({ e, x, y, r, flip });
  if (pic) return pic;
  const cls = `sc-body r-${e.look.role}`;
  if (e.kind === "block") {
    return html`<rect class=${cls} x=${x - r * 1.3} y=${y - r * 1.6 + r} width=${r * 2.6} height=${r * 1.6} rx="4" />`;
  }
  if (e.kind === "car") {
    return html`<g class=${cls}>
      <path d=${`M${x - r * 1.8},${y + r * 0.35} v${-r * 0.9} l${r * 0.6},${-r * 0.6} h${r * 1.8} l${r * 0.8},${r * 0.6} h${r * 0.2} v${r * 0.9} z`} />
      <circle class="wheel" cx=${x - r} cy=${y + r * 0.45} r=${r * 0.5} /><circle class="wheel" cx=${x + r} cy=${y + r * 0.45} r=${r * 0.5} />
    </g>`;
  }
  if (e.kind === "particle") return html`<circle class=${cls} cx=${x} cy=${y} r=${r * 0.45} />`;
  const a = (angle * Math.PI) / 180;
  return html`<g class=${cls}>
    <circle cx=${x} cy=${y} r=${r} />
    <line class="spoke" x1=${x} y1=${y} x2=${x + r * Math.cos(a)} y2=${y + r * Math.sin(a)} />
  </g>`;
}

// One entity's drawing. pose: a moving body's {x, y, angle} at the clock's time (else its geom centre).
export function Shape({ e, g, pose, focus, umbrella }) {
  if (!g) return null;
  const cls = `sc-shape r-${e.look.role}${focus ? " focus" : ""}`;
  switch (g.shape) {
    case "poly": return html`<polygon class=${cls} points=${pts(g.pts)} />`;
    case "circle": return html`<circle class=${cls} cx=${g.c[0]} cy=${g.c[1]} r=${g.r} />`;
    case "seg": return html`<line class=${cls + " sc-line"} x1=${g.pts[0][0]} y1=${g.pts[0][1]} x2=${g.pts[1][0]} y2=${g.pts[1][1]} />`;
    case "dot": return html`<circle class=${cls + " sc-dot"} cx=${g.c[0]} cy=${g.c[1]} r="9" />`;
    case "path": return html`<path class=${cls + " sc-curve"} d=${g.d} />`;
    case "solid": return html`<g class=${cls + " sc-solid"}>
      <polygon class="face" points=${pts(g.pts)} />
      ${g.d2 && html`<path class="hidden-edge" d=${g.d2} />`}
      <path class="edge" d=${g.d} />
    </g>`;
    case "thing": return g.hidden ? null : html`<${Thing} e=${e} g=${g} pose=${pose} />`;
    case "body": {
      const p = pose || { x: g.c[0], y: g.c[1], angle: 0 };
      return html`<${Body} e=${e} x=${p.x} y=${p.y} angle=${p.angle} flip=${!!g.flip} />
        ${umbrella != null && html`<${Umbrella} x=${p.x} y=${p.y} r=${g.r} tilt=${umbrella} />`}`;
    }
    default: return null;
  }
}

// The entity's printed words: its said name (or label), a computed note ("(2, 1)"), the said sizes on the shape.
export function Words({ e, g, pose, umbrella }) {
  if (!g || g.hidden) return null;
  let at = g.label_at;
  // a thing's name rides above its picture (F-016)
  // (or at its side when another thing rests on it: label_at says where, relative to its centre)
  const side = g.shape === "thing" && at && g.wh && at[0] < g.c[0] - g.wh[0] / 2;
  if (g.shape === "thing" && pose && g.wh) {
    at = side ? [pose.x + at[0] - g.c[0], pose.y + at[1] - g.c[1]] : [pose.x, pose.y - (g.wh[1] * (pose.sy || 1)) / 2 - 16];
  }
  // a body's name rides above it, or (many lanes) stays in the names' column on the left, level with its lane
  const column = g.shape === "body" && at && at[0] < g.c[0] - g.r;
  if (g.shape === "body" && pose) at = column ? [at[0], pose.y + 9] : [pose.x, pose.y - g.r - 16];
  // an umbrella is held above it: the name stands on its left instead
  const left = g.shape === "body" && umbrella != null && pose;
  if (left) at = [pose.x - g.r * 1.4 - 10, pose.y + 9];
  const name = e.label && e.label.source === "said" ? e.label.text : "";
  const anchor = left || side ? "end" : g.shape === "dot" || g.shape === "seg" || column ? "start" : g.shape === "path" ? "end" : "middle";
  return html`
    ${at && (name || g.note) && html`<text class=${`sim-label word sc-name r-${e.look.role}${g.shape === "thing" ? " cv-name" : ""}`} x=${at[0]} y=${at[1]} text-anchor=${anchor} data-el=${e.id}>
      ${name && html`<tspan class="sym">${name}</tspan>`}${g.note && html`<tspan class="val computed">${(name ? " " : "") + g.note}</tspan>`}
    </text>`}
    ${(g.dims || []).map(([x, y, text], i) => html`<text key=${i} class="sim-label sc-dim" x=${x} y=${y} text-anchor="middle" data-el=${e.id + "-dim" + i}>
      <tspan class="val">${text}</tspan></text>`)}
    ${e.expr_shown && g.shape === "path" && at && html`<text class=${`sim-label sc-expr r-${e.look.role}`} x=${at[0]} y=${at[1] + 44} text-anchor="end" data-el=${e.id + "-expr"}>
      <tspan class="val">${e.expr_shown}</tspan></text>`}`;
}

// Rain streaks falling at `angle` degrees from the vertical (+: toward +x) at `speed` px/s, over the stage above the
// ground: a fixed pattern moved by the clock's time t (so a still frame and a paused scene are reproducible).
// spread evenly: x by the golden ratio, y in equal steps
const STREAKS = Array.from({ length: 48 }, (_, i) => [((i * 0.6180339) % 1) * 1060 + 20, (i / 48) * 700]);
function Rain({ rain, ground, t }) {
  const [ang, speed] = rain;
  const a = (ang * Math.PI) / 180, dx = Math.sin(a), dy = Math.cos(a);
  const span = (ground ? ground[2] : 700) - 20;
  return html`<g class="sc-rain">${STREAKS.map(([x0, y0], i) => {
    const d = (y0 + t * speed) % span;
    const x = (((x0 + (d * dx) / Math.max(dy, 0.2)) % 1100) + 1100) % 1100, y = 20 + d;
    return html`<line key=${i} x1=${x} y1=${y} x2=${x - 26 * dx} y2=${y - 26 * dy} />`;
  })}</g>`;
}

// A velocity: an arrow with its head, its words beside the middle (whose velocity, its speed when known).
function Arrow({ v }) {
  const L = Math.hypot(v.x1 - v.x0, v.y1 - v.y0);
  if (L < 2) return null;
  const ux = (v.x1 - v.x0) / L, uy = (v.y1 - v.y0) / L, h = Math.min(22, L * 0.4);
  const bx = v.x1 - ux * h, by = v.y1 - uy * h;
  const head = `${v.x1},${v.y1} ${bx - uy * h * 0.5},${by + ux * h * 0.5} ${bx + uy * h * 0.5},${by - ux * h * 0.5}`;
  // its words where Python put them (outside the triangle), else beside its middle
  const [mx, my] = v.at || [(v.x0 + v.x1) / 2 + uy * 18, (v.y0 + v.y1) / 2 - ux * 18 + 8];
  const anchor = v.at ? v.anchor : uy > 0.3 ? "start" : uy < -0.3 ? "end" : "middle";
  return html`<g class=${"sc-vec r-" + v.role}>
    <line x1=${v.x0} y1=${v.y0} x2=${bx} y2=${by} /><polygon points=${head} />
    ${v.text && html`<text class="sim-label sc-vec-word" x=${mx} y=${my} text-anchor=${anchor}>${v.text}</text>`}
  </g>`;
}

// The plot world's axes (ticks computed by Python), the motion world's ground and lanes, the relative world's river,
// rain and velocity triangle.
export function StageParts({ stage, t = 0 }) {
  const a = stage.axes;
  const rv = stage.river, fl = stage.flow;
  return html`
    ${rv && html`<g class="sc-river">
      <rect class="bank" x=${rv[0]} y=${rv[2] - 40} width=${rv[1] - rv[0]} height="40" />
      <rect class="bank" x=${rv[0]} y=${rv[3]} width=${rv[1] - rv[0]} height="40" />
      <rect class="water" x=${rv[0]} y=${rv[2]} width=${rv[1] - rv[0]} height=${rv[3] - rv[2]} />
      <line class="edge" x1=${rv[0]} y1=${rv[2]} x2=${rv[1]} y2=${rv[2]} /><line class="edge" x1=${rv[0]} y1=${rv[3]} x2=${rv[1]} y2=${rv[3]} />
      ${fl && html`<${Arrow} v=${{ x0: fl[0], y0: fl[1], x1: fl[2], y1: fl[3], role: "water", text: "" }} />`}
    </g>`}
    ${stage.rain && html`<${Rain} rain=${stage.rain} ground=${stage.ground} t=${t} />`}
    ${(stage.vectors || []).map((v, i) => html`<${Arrow} key=${"v" + i} v=${v} />`)}
    ${a && html`<g class="sc-axes">
      <line class="axis" x1=${a.x0} y1=${a.origin[1]} x2=${a.x1} y2=${a.origin[1]} />
      <line class="axis" x1=${a.origin[0]} y1=${a.y0} x2=${a.origin[0]} y2=${a.y1} />
      ${a.xticks.map(([x, t]) => html`<g key=${"x" + t}><line class="tick" x1=${x} y1=${a.origin[1] - 7} x2=${x} y2=${a.origin[1] + 7} />
        <text class="tick-label" x=${x} y=${a.origin[1] + 32} text-anchor="middle">${t}</text></g>`)}
      ${a.yticks.map(([y, t]) => html`<g key=${"y" + t}><line class="tick" x1=${a.origin[0] - 7} y1=${y} x2=${a.origin[0] + 7} y2=${y} />
        <text class="tick-label" x=${a.origin[0] - 14} y=${y + 8} text-anchor="end">${t}</text></g>`)}
    </g>`}
    ${(stage.trails || []).map(([id, d]) => html`<path key=${"trail-" + id} class="sim-guide sc-trail" d=${d} fill="none" />`)}
    ${stage.ground && html`<g class="sc-ground">
      <rect class="sim-ground" x=${stage.ground[0]} y=${stage.ground[2]} width=${stage.ground[1] - stage.ground[0]} height="40" />
      <line class="sim-surface" x1=${stage.ground[0]} y1=${stage.ground[2]} x2=${stage.ground[1]} y2=${stage.ground[2]} />
      ${(stage.lanes || []).map((y) => html`<line key=${y} class="sim-guide" x1=${stage.ground[0]} y1=${y} x2=${stage.ground[1]} y2=${y} />`)}
    </g>`}`;
}
