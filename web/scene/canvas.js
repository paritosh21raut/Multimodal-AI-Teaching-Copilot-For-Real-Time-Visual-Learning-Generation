// The canvas world's drawing (F-016, docs/contracts/scene-spec.md): a thing's picture, the place's backdrop (a photo
// or an illustration), drawn effects and the part magnifier. Every position comes from Python (geom, frames, stage);
// nothing here measures anything, and no text is printed here except a part's said name under its magnifier (a
// thing's said name is drawn by kinds.js Words).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { ICONS } from "../vendor/icons/scene-icons.js";

// the canvas stage: the whole 1920 x 1080 slide, 1:1 (scene.worlds.canvas W, H; stage.size)
export const CANVAS = [1920, 1080];
// fixed, evenly spread patterns (golden ratio) on a unit square: a still frame and a paused scene are reproducible
const spread = (n, seed = 0) => Array.from({ length: n }, (_, i) => [(((i + seed) * 0.6180339) % 1), ((i * 0.7548776 + seed * 0.13) % 1)]);
const STARS = spread(140, 3);
const BUBBLES = spread(30, 7);
const CRATERS = spread(9, 5);

// ---- a thing's picture ------------------------------------------------------------------------------------------
// One picture in a w x h box centred on (0, 0): the teacher's image, a photo cutout, a Fluent 3D emoji, a shaded solid
// for a shape noun, an icon or a glyph; none yet: a soft placeholder (the picture cross-fades in when it lands).
function Pic({ lk, w, h, role, emoji, icon, opacity = 1, glass = false }) {
  const href = lk.image || lk.photo || emoji;
  if (href) {
    return html`<image key=${href} class="cv-img" href=${href} x=${-w / 2} y=${-h / 2} width=${w} height=${h}
      preserveAspectRatio="xMidYMid meet" opacity=${opacity} />`;
  }
  if (lk.form) return html`<${Form} form=${lk.form} w=${w} h=${h} role=${role} opacity=${opacity} glass=${glass} />`;
  const ic = icon && ICONS[icon];
  if (ic || lk.glyph) {
    const s = Math.min(w, h) / 24;
    return html`<g key=${icon || "glyph"} class=${"cv-icon sc-pic r-" + role} opacity=${opacity}>
      <circle class="pic-back" cx="0" cy="0" r=${Math.min(w, h) * 0.5} />
      <g class="pic-lines" transform=${`translate(${-12 * s} ${-12 * s}) scale(${s})`}>
        ${ic ? ic.nodes.map(([tag, a], i) => html`<${tag} key=${i} ...${a} />`) : html`<path d=${lk.glyph} />`}</g></g>`;
  }
  return html`<rect class=${"cv-placeholder r-" + role} x=${-w * 0.42} y=${-h * 0.42} width=${w * 0.84} height=${h * 0.84}
    rx=${Math.min(w, h) * 0.2} opacity=${opacity} />`;
}

// A shape noun drawn as a shaded solid (light from the top left), in the thing's role colour; glass: something is
// inside it, so it is drawn see-through.
function Form({ form, w, h, role, opacity, glass }) {
  const cls = `cv-form r-${role}${glass ? " glass" : ""}`;
  const s = Math.min(w, h) * 0.46;
  if (form === "sphere" || form === "hemisphere") {
    return html`<g class=${cls} opacity=${opacity}><circle class="base" cx="0" cy="0" r=${s} />
      <circle class="shade" cx=${s * 0.25} cy=${s * 0.3} r=${s * 0.8} /><circle class="hi" cx=${-s * 0.35} cy=${-s * 0.38} r=${s * 0.28} /></g>`;
  }
  if (form === "cylinder") {
    return html`<g class=${cls} opacity=${opacity}><rect class="base" x=${-s * 0.7} y=${-s * 0.8} width=${s * 1.4} height=${s * 1.6} />
      <rect class="shade" x=${s * 0.15} y=${-s * 0.8} width=${s * 0.55} height=${s * 1.6} />
      <ellipse class="base" cx="0" cy=${s * 0.8} rx=${s * 0.7} ry=${s * 0.25} /><ellipse class="top" cx="0" cy=${-s * 0.8} rx=${s * 0.7} ry=${s * 0.25} /></g>`;
  }
  if (form === "cone" || form === "pyramid") {
    const base = form === "cone"
      ? html`<ellipse class="base" cx="0" cy=${s * 0.8} rx=${s * 0.8} ry=${s * 0.26} />`
      : html`<polygon class="base" points=${`${-s * 0.9},${s * 0.8} ${s * 0.5},${s * 0.95} ${s * 0.9},${s * 0.65}`} />`;
    return html`<g class=${cls} opacity=${opacity}>${base}
      <polygon class="base" points=${`0,${-s} ${-s * 0.8},${s * 0.8} ${s * 0.8},${s * 0.8}`} />
      <polygon class="shade" points=${`0,${-s} ${s * 0.15},${s * 0.85} ${s * 0.8},${s * 0.8}`} /></g>`;
  }
  // cube / cuboid / prism: an oblique box
  const a = form === "cuboid" ? s * 1.3 : s, b = s, d = s * 0.45;
  return html`<g class=${cls} opacity=${opacity}>
    <polygon class="top" points=${`${-a},${-b + d * 0.2} ${-a + d},${-b - d * 0.6} ${a},${-b - d * 0.6} ${a - d},${-b + d * 0.2}`} />
    <polygon class="shade" points=${`${a - d},${-b + d * 0.2} ${a},${-b - d * 0.6} ${a},${b - d * 0.6} ${a - d},${b + d * 0.2}`} />
    <rect class="base" x=${-a} y=${-b + d * 0.2} width=${2 * a - d} height=${2 * b} /></g>`;
}

const picKind = (lk) => (lk.image ? "image" : lk.photo ? "photo" : lk.emoji ? "emoji" : lk.form ? "form:" + lk.form
  : lk.icon ? "icon:" + lk.icon : lk.glyph ? "glyph" : "placeholder");

// A thing at its pose: picture, shadow on the ground, lean / spin (angle), mirrored when it moves west, squash and
// fade (sa). transform_into: the second picture fades in as the first fades out.
export function Thing({ e, g, pose }) {
  const lk = e.look || {};
  const [w, h] = g.wh || [g.r * 2, g.r * 2];
  const p = pose || { x: g.c[0], y: g.c[1], angle: 0, sx: 1, sy: 1, a: 1 };
  const role = lk.role || "main";
  const morph = !!lk.to_noun;  // no picture for it yet: the placeholder fades in (the thing never vanishes)
  const a = p.a == null ? 1 : p.a;
  const tf = `translate(${p.x} ${p.y}) rotate(${p.angle || 0}) scale(${(g.flip ? -1 : 1) * (p.sx || 1)} ${p.sy || 1})`;
  let shadow = null;
  if (g.ground != null) {
    const lift = Math.max(0, g.ground - (p.y + h / 2));
    const k = Math.max(0.25, 1 - lift / 700);
    shadow = html`<ellipse class="cv-shadow" cx=${p.x} cy=${g.ground - 4} rx=${w * 0.36 * k} ry=${14 * k} opacity=${morph ? 1 : a} />`;
  }
  return html`<g class=${"cv-thing r-" + role} data-pic=${picKind(lk)}>
    ${shadow}
    <g transform=${tf} opacity=${morph ? 1 : a}>
      <${Pic} lk=${lk} w=${w} h=${h} role=${role} emoji=${lk.emoji} icon=${lk.icon} opacity=${morph ? a : 1} glass=${!!g.glass} />
      ${morph && html`<${Pic} lk=${{ ...lk, image: "", photo: "", form: "" }} w=${w} h=${h} role=${role} emoji=${lk.to_emoji} icon=${lk.to_icon} opacity=${1 - a} />`}
    </g>
  </g>`;
}

// ---- a focused part ---------------------------------------------------------------------------------------------
// The part's picture enlarged in an inset circle, a ring where it is on its whole and a leader line between them;
// its said name under the inset.
export function Magnifier({ m, e }) {
  const lk = e.look || {};
  const [ax, ay] = m.at, [cx, cy] = m.c, r = m.r;
  const d = Math.hypot(cx - ax, cy - ay) || 1, ring = r * 0.22;
  const ux = (cx - ax) / d, uy = (cy - ay) / d;
  const name = e.label && e.label.source === "said" ? e.label.text : "";
  return html`<g class="cv-magnifier" data-el=${"mag-" + e.id} data-pic=${picKind(lk)}>
    <circle class="cv-mag-spot" cx=${ax} cy=${ay} r=${ring} />
    <line class="cv-mag-lead" x1=${ax + ux * ring} y1=${ay + uy * ring} x2=${cx - ux * r} y2=${cy - uy * r} />
    <clipPath id=${"mag-clip-" + e.id}><circle cx=${cx} cy=${cy} r=${r} /></clipPath>
    <circle class="cv-mag-back" cx=${cx} cy=${cy} r=${r} />
    <g clip-path=${`url(#mag-clip-${e.id})`}><g transform=${`translate(${cx} ${cy})`}>
      <${Pic} lk=${lk} w=${r * 1.5} h=${r * 1.5} role=${lk.role || "main"} emoji=${lk.emoji} icon=${lk.icon} />
    </g></g>
    <circle class="cv-mag-ring" cx=${cx} cy=${cy} r=${r} />
    ${name && html`<text class="sim-label word sc-name cv-name cv-mag-name" x=${cx} y=${cy + r + 52} text-anchor="middle"><tspan class="sym">${name}</tspan></text>`}
  </g>`;
}

// ---- the place --------------------------------------------------------------------------------------------------
const hills = (W, H, y, amp, n, seed) => {
  let d = `M0,${H} L0,${y}`;
  for (let i = 0; i <= n; i++) {
    const x = (i / n) * W, k = ((i * 0.618 + seed) % 1);
    d += ` L${x},${y - amp * (0.35 + 0.65 * k)}`;
  }
  return d + ` L${W},${H} Z`;
};

function Stars({ W, H, t, below }) {
  return STARS.map(([u, v], i) => {
    const y = v * (below || H);
    return html`<circle key=${"s" + i} class="cv-star" cx=${u * W} cy=${y} r=${i % 7 === 0 ? 3 : 1.6}
      opacity=${0.5 + 0.5 * Math.abs(Math.sin(t * 1.3 + i))} />`;
  });
}

export function Backdrop({ bd, t = 0, W = CANVAS[0], H = CANVAS[1] }) {
  if (!bd) return null;
  const g = bd.ground, typ = bd.type;
  const ground = (cls) => g != null && html`<rect class=${cls} x="0" y=${g} width=${W} height=${H - g} />
    <line class="cv-ground-line" x1="0" y1=${g} x2=${W} y2=${g} />`;
  // C1b: a landscape photo of the place, dimmed for contrast (the things stand on Python's ground line)
  if (bd.photo) {
    return html`<g class=${"cv-backdrop cv-photo cv-" + typ} data-place=${typ} data-photo="1">
      <image class="cv-img" href=${bd.photo} x="0" y="0" width=${W} height=${H} preserveAspectRatio="xMidYMid slice" />
      <rect class="cv-photo-dim" x="0" y="0" width=${W} height=${H} /></g>`;
  }
  const sky = html`<rect class="cv-sky" x="0" y="0" width=${W} height=${H} />`;
  let body;
  if (typ === "space") {
    body = html`<rect class="cv-space" x="0" y="0" width=${W} height=${H} /><${Stars} W=${W} H=${H} t=${t} />`;
  } else if (typ === "moon" || typ === "mars") {
    // the black sky with stars (moon) or a dusky one (mars) over a cratered grey / red ground
    body = html`<rect class=${typ === "moon" ? "cv-space" : "cv-mars-sky"} x="0" y="0" width=${W} height=${H} />
      ${typ === "moon" && html`<${Stars} W=${W} H=${H} t=${t} below=${g} />`}
      <path class=${typ === "moon" ? "cv-moon-far" : "cv-mars-far"} d=${hills(W, H, g - 40, 110, 7, 0.3)} />
      ${ground(typ === "moon" ? "cv-moon-ground" : "cv-mars-ground")}
      ${CRATERS.map(([u, v], i) => html`<ellipse key=${"c" + i} class="cv-crater" cx=${u * W} cy=${g + 30 + v * (H - g - 50)}
        rx=${40 + (i % 3) * 30} ry=${10 + (i % 3) * 6} />`)}`;
  } else if (typ === "water") {
    const s = bd.surface;
    body = html`${sky}<rect class="cv-water" x="0" y=${s} width=${W} height=${H - s} />
      <path class="cv-surface" d=${Array.from({ length: Math.ceil(W / 50) + 1 }, (_, i) => `${i ? "L" : "M"}${i * 50},${s + 6 * Math.sin(i * 0.9 + t * 2)}`).join(" ")} />
      ${[0.15, 0.4, 0.7].map((k, i) => html`<polygon key=${"ray" + i} class="cv-ray" points=${`${W * k},${s} ${W * k + 90},${s} ${W * k + 300},${g} ${W * k + 120},${g}`} />`)}
      ${BUBBLES.map(([u], i) => { const y = g - ((t * 70 + i * 41) % (g - s)); return html`<circle key=${"b" + i} class="cv-bubble" cx=${u * W + 8 * Math.sin(t * 2 + i)} cy=${y} r=${3 + (i % 4)} />`; })}
      ${ground("cv-sand")}`;
  } else if (typ === "sky") {
    body = html`${sky}${[[0.1, 0.2, 1.3], [0.45, 0.13, 1.8], [0.78, 0.28, 1.2], [0.3, 0.55, 1.4], [0.68, 0.68, 1.7]].map(([u, v, k], i) => {
      const cx = ((u * W + t * 14 * k) % (W + 400)) - 200, y = v * H;
      return html`<g key=${i} class="cv-cloud"><ellipse cx=${cx} cy=${y} rx=${90 * k} ry=${30 * k} /><ellipse cx=${cx - 40 * k} cy=${y + 8} rx=${50 * k} ry=${24 * k} /><ellipse cx=${cx + 45 * k} cy=${y + 6} rx=${55 * k} ry=${22 * k} /></g>`;
    })}`;
  } else if (typ === "indoors") {
    body = html`<rect class="cv-wall" x="0" y="0" width=${W} height=${H} />
      <rect class="cv-window" x=${W * 0.72} y="160" width="300" height="230" rx="8" /><line class="cv-frame" x1=${W * 0.72 + 150} y1="160" x2=${W * 0.72 + 150} y2="390" />
      ${ground("cv-floor")}`;
  } else {
    const back = typ === "mountain" ? html`<path class="cv-far" d=${hills(W, H, g - 160, 420, 7, 0.2)} /><path class="cv-near" d=${hills(W, H, g - 50, 240, 11, 0.6)} />`
      : typ === "street" ? html`${Array.from({ length: 13 }, (_, i) => html`<rect key=${i} class="cv-far" x=${30 + i * 148} y=${g - 200 - (i * 73) % 240} width="128" height=${200 + (i * 73) % 240 + 2} />`)}`
      : typ === "nature" ? html`<path class="cv-far" d=${hills(W, H, g - 80, 130, 6, 0.4)} />${[0.05, 0.16, 0.84, 0.95].map((u, i) => html`<g key=${i} class="cv-tree"><rect x=${u * W - 8} y=${g - 100} width="16" height="100" /><circle cx=${u * W} cy=${g - 135} r="58" /></g>`)}`
      : typ === "beach" ? html`<rect class="cv-water" x="0" y=${g - 100} width=${W} height="100" />`
      : typ === "desert" ? html`<path class="cv-sand" d=${hills(W, H, g - 40, 100, 5, 0.3)} />`
      : null;
    const floor = typ === "street" ? "cv-road" : typ === "nature" || typ === "mountain" ? "cv-grass"
      : typ === "beach" || typ === "desert" ? "cv-sand" : typ === "snow" ? "cv-snow" : "cv-plain-ground";
    body = html`${typ === "plain" ? html`<rect class="cv-plain" x="0" y="0" width=${W} height=${H} />` : sky}${back}${ground(floor)}
      ${typ === "street" && g != null && html`<line class="cv-lane" x1="0" y1=${g + 45} x2=${W} y2=${g + 45} />`}`;
  }
  return html`<g class=${"cv-backdrop cv-" + typ} data-place=${typ}>${body}</g>`;
}

// ---- effects ----------------------------------------------------------------------------------------------------
// What a thing gives off (emit), drawn around its pose, moved by the clock (t): bubbles rise, rings and waves spread,
// rays turn, smoke drifts, sparks fly; a push / pull arrow (dir deg, 0 = +x).
export function Effect({ fx, pose, g, t }) {
  if (!pose) return null;
  const [w, h] = g.wh || [g.r * 2, g.r * 2];
  const { x, y } = pose;
  const k = fx.kind;
  if (k === "bubbles" || k === "smoke") {
    return html`<g class=${"cv-fx cv-" + k}>${Array.from({ length: 7 }, (_, i) => {
      const u = ((t * 0.6 + i / 7) % 1);
      return html`<circle key=${i} cx=${x + w * 0.15 * Math.sin(i * 2 + t * 2) + (k === "smoke" ? u * 40 : 0)} cy=${y - h * 0.4 - u * 220}
        r=${(k === "smoke" ? 10 + u * 26 : 4 + (i % 3) * 3)} opacity=${1 - u} />`;
    })}</g>`;
  }
  if (k === "rings" || k === "waves") {
    return html`<g class=${"cv-fx cv-" + k}>${[0, 1, 2].map((i) => {
      const u = ((t * 0.5 + i / 3) % 1), r = Math.max(w, h) * 0.55 + u * 260;
      return html`<circle key=${i} cx=${x} cy=${y} r=${r} opacity=${1 - u} />`;
    })}</g>`;
  }
  if (k === "rays") {
    const R0 = Math.max(w, h) * 0.6, R1 = R0 + 70;
    return html`<g class="cv-fx cv-rays">${Array.from({ length: 12 }, (_, i) => {
      const a = (i / 12) * 2 * Math.PI + t * 0.4;
      return html`<line key=${i} x1=${x + R0 * Math.cos(a)} y1=${y + R0 * Math.sin(a)} x2=${x + R1 * Math.cos(a)} y2=${y + R1 * Math.sin(a)} />`;
    })}</g>`;
  }
  if (k === "sparks") {
    return html`<g class="cv-fx cv-sparks">${Array.from({ length: 10 }, (_, i) => {
      const u = ((t * 1.2 + i / 10) % 1), a = i * 2.4;
      return html`<circle key=${i} cx=${x + Math.cos(a) * u * 140} cy=${y + Math.sin(a) * u * 140} r="4" opacity=${1 - u} />`;
    })}</g>`;
  }
  if (k === "push" || k === "pull") {
    const a = (fx.dir * Math.PI) / 180, ux = Math.cos(a), uy = Math.sin(a), L = 110;
    const sx = k === "push" ? x - ux * (w / 2 + 20 + L) : x + ux * (w / 2 + 20);
    const sy = k === "push" ? y - uy * (w / 2 + 20 + L) : y + uy * (w / 2 + 20);
    const ex = sx + ux * L, ey = sy + uy * L;
    return html`<g class="cv-fx cv-arrow"><line x1=${sx} y1=${sy} x2=${ex - ux * 18} y2=${ey - uy * 18} />
      <polygon points=${`${ex},${ey} ${ex - ux * 22 - uy * 12},${ey - uy * 22 + ux * 12} ${ex - ux * 22 + uy * 12},${ey - uy * 22 - ux * 12}`} /></g>`;
  }
  return null;
}
