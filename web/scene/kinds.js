// Scene drawing kinds (F-015, docs/contracts/scene-spec.md): one function per engine shape. Parts, not templates: no
// topic logic here. Every coordinate comes from Python (geom, stage px); every printed text comes from the spec
// (a said name, a said size, a computed note). Colours by role (main / second / third / accent / muted), both themes.
import { html } from "../vendor/htm-preact-standalone.mjs";

const pts = (ps) => ps.map(([x, y]) => `${x},${y}`).join(" ");

// A body (ball, block, car, particle) at (x, y), turned by angle degrees (a ball rolls; the others do not turn).
function Body({ e, x, y, angle }) {
  const r = (e.geom && e.geom.r) || 22;
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
export function Shape({ e, g, pose, focus }) {
  if (!g) return null;
  const cls = `sc-shape r-${e.look.role}${focus ? " focus" : ""}`;
  switch (g.shape) {
    case "poly": return html`<polygon class=${cls} points=${pts(g.pts)} />`;
    case "circle": return html`<circle class=${cls} cx=${g.c[0]} cy=${g.c[1]} r=${g.r} />`;
    case "seg": return html`<line class=${cls + " sc-line"} x1=${g.pts[0][0]} y1=${g.pts[0][1]} x2=${g.pts[1][0]} y2=${g.pts[1][1]} />`;
    case "dot": return html`<circle class=${cls + " sc-dot"} cx=${g.c[0]} cy=${g.c[1]} r="9" />`;
    case "path": return html`<path class=${cls + " sc-curve"} d=${g.d} />`;
    case "body": {
      const p = pose || { x: g.c[0], y: g.c[1], angle: 0 };
      return html`<${Body} e=${e} x=${p.x} y=${p.y} angle=${p.angle} />`;
    }
    default: return null;
  }
}

// The entity's printed words: its said name (or label), a computed note ("(2, 1)"), the said sizes on the shape.
export function Words({ e, g, pose }) {
  if (!g) return null;
  let at = g.label_at;
  if (g.shape === "body" && pose) at = [pose.x, pose.y - g.r - 16];
  const name = e.label && e.label.source === "said" ? e.label.text : "";
  const anchor = g.shape === "dot" || g.shape === "seg" ? "start" : g.shape === "path" ? "end" : "middle";
  return html`
    ${at && (name || g.note) && html`<text class=${`sim-label word sc-name r-${e.look.role}`} x=${at[0]} y=${at[1]} text-anchor=${anchor} data-el=${e.id}>
      ${name && html`<tspan class="sym">${name}</tspan>`}${g.note && html`<tspan class="val computed">${(name ? " " : "") + g.note}</tspan>`}
    </text>`}
    ${(g.dims || []).map(([x, y, text], i) => html`<text key=${i} class="sim-label sc-dim" x=${x} y=${y} text-anchor="middle" data-el=${e.id + "-dim" + i}>
      <tspan class="val">${text}</tspan></text>`)}
    ${e.expr_shown && g.shape === "path" && at && html`<text class=${`sim-label sc-expr r-${e.look.role}`} x=${at[0]} y=${at[1] + 44} text-anchor="end" data-el=${e.id + "-expr"}>
      <tspan class="val">${e.expr_shown}</tspan></text>`}`;
}

// The plot world's axes (ticks computed by Python) and the motion world's ground and lanes.
export function StageParts({ stage }) {
  const a = stage.axes;
  return html`
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
      ${(stage.lanes || []).map((y) => html`<line key=${y} class="sim-guide" x1=${stage.ground[0]} y1=${y + 30} x2=${stage.ground[1]} y2=${y + 30} />`)}
    </g>`}`;
}
