// Slide renderer shared by /display and /control. Renders a SlideSpec (docs/contracts/slide-spec.md).
// Items are keyed by their stable ids, so Preact keeps existing DOM nodes and only new nodes get the
// mount animation (.enter) - in-place updates never re-animate the whole slide.
import { html, useLayoutEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";

const ARROW = html`<svg class="arrow" viewBox="0 0 56 40" aria-hidden="true">
  <path d="M4 20h40M34 9l12 11-12 11" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

const itemClass = (it, base) =>
  [base, "enter", it.provisional && "provisional", it.added && "added", it.emphasis && "emph"].filter(Boolean).join(" ");

function Definition({ b, termInTitle }) {
  return html`<div class="def">
    ${!termInTitle && html`<div class="def-term enter">${b.term}</div>`}
    <div class="def-body enter">${b.definition}</div>
    ${b.notes.length > 0 && html`<div class="def-notes">
      ${b.notes.map((n) => html`<span key=${n.id} class=${itemClass(n, "def-note")}>${n.text}</span>`)}
    </div>`}
  </div>`;
}

function Points({ b, wide }) {
  const cols = wide && b.items.length > 3 && b.items.every((i) => i.text.length < 90) ? "cols-2" : "";
  return html`<div class="points">
    ${b.heading && html`<div class="points-heading">${b.heading}</div>`}
    <ol class=${"points-list " + cols}>
      ${b.items.map((it, i) => html`<li key=${it.id} class=${itemClass(it, "point")}>
        <span class="num">${i + 1}</span><span>${it.text}</span>
      </li>`)}
    </ol>
  </div>`;
}

function Process({ b }) {
  return html`<div class="process">
    <div class="process-row">
      ${b.steps.map((s, i) => html`<div key=${s.id} class="step enter">
        <div class="step-card">
          <span class="step-no">STEP ${i + 1}</span>
          <span class="step-label">${s.label}</span>
          ${s.detail && html`<span class="step-detail">${s.detail}</span>`}
        </div>
        ${i < b.steps.length - 1 && ARROW}
      </div>`)}
    </div>
    ${b.cyclic && html`<div class="cycle-note">↻ The cycle repeats</div>`}
  </div>`;
}

function Comparison({ b }) {
  return html`<table class="compare enter">
    <thead><tr><th></th>${b.columns.map((c) => html`<th key=${c.id}>${c.heading}</th>`)}</tr></thead>
    <tbody>
      ${b.rows.map((r) => html`<tr key=${r.id} class="enter">
        <td class="aspect">${r.aspect}</td>${r.cells.map((c, i) => html`<td key=${i}>${c}</td>`)}
      </tr>`)}
    </tbody>
  </table>`;
}

function Timeline({ b }) {
  return html`<div class="timeline">
    ${b.events.map((e) => html`<div key=${e.id} class="tl-event enter">
      <span class="tl-when">${e.when}</span>
      <span class="tl-label">${e.label}</span>
      ${e.detail && html`<span class="tl-detail">${e.detail}</span>`}
    </div>`)}
  </div>`;
}

function CauseEffect({ b }) {
  return html`<div class="causal">
    ${b.links.map((l) => html`<div key=${l.id} class="link enter">
      <div class="cause">${l.cause}</div>${ARROW}<div class="effect">${l.effect}</div>
    </div>`)}
  </div>`;
}

function TreeNode({ n, root }) {
  return html`<div class=${root ? "tree-root" : "tree-sub enter"}>
    <div class="tree-node">${n.label}</div>
    ${n.children.length > 0 && html`<div class="tree-children">
      ${n.children.map((c) => html`<${TreeNode} key=${c.id} n=${c} />`)}
    </div>`}
  </div>`;
}

function Formula({ b }) {
  // KaTeX rendering arrives in V1; until then show the teacher's spoken form (or the raw LaTeX).
  return html`<div class="formula">
    <div class="formula-eq enter">${b.spoken || b.latex}</div>
    ${b.variables.length > 0 && html`<div class="formula-vars">
      ${b.variables.map((v) => html`<span key=${v.symbol} class="enter"><span class="sym">${v.symbol}</span>${v.meaning}${v.unit && ` (${v.unit})`}</span>`)}
    </div>`}
  </div>`;
}

function Figure({ b }) {
  const [loaded, setLoaded] = useState(false);
  return html`<figure class="figure">
    <img src=${b.url} alt=${b.alt} class=${loaded ? "loaded" : ""} onLoad=${() => setLoaded(true)} />
    ${(b.credit || b.licence) && html`<figcaption>${[b.credit, b.licence].filter(Boolean).join(" · ")}</figcaption>`}
  </figure>`;
}

function Block({ b, wide, termInTitle }) {
  switch (b.type) {
    case "definition": return html`<${Definition} b=${b} termInTitle=${termInTitle} />`;
    case "points": return html`<${Points} b=${b} wide=${wide} />`;
    case "process": return html`<${Process} b=${b} />`;
    case "comparison": return html`<${Comparison} b=${b} />`;
    case "timeline": return html`<${Timeline} b=${b} />`;
    case "cause_effect": return html`<${CauseEffect} b=${b} />`;
    case "hierarchy": return html`<div class="tree"><${TreeNode} n=${b.root} root /></div>`;
    case "formula": return html`<${Formula} b=${b} />`;
    case "image": return html`<${Figure} b=${b} />`;
    case "example": return html`<div class="example enter"><span class="label">Example</span>
      ${b.title && html`<span class="title">${b.title}</span>`}${b.text}</div>`;
    case "callout": return html`<div class="callout enter"><span class="label">${
      { key: "Key idea", tip: "Remember", note: "Note" }[b.kind]}</span>${b.text}</div>`;
    default: return null;
  }
}

// Secondary blocks go into the right-hand aside when the primary block leaves room for one.
const ASIDE_TYPES = new Set(["callout", "example", "image"]);
const FULL_WIDTH_PRIMARY = new Set(["process", "comparison", "timeline", "hierarchy", "cause_effect", "formula"]);

function splitBlocks(blocks) {
  if (blocks.length < 2) return { main: blocks, aside: [] };
  const [primary, ...rest] = blocks;
  if (FULL_WIDTH_PRIMARY.has(primary.type)) return { main: blocks, aside: [] };
  return { main: [primary, ...rest.filter((b) => !ASIDE_TYPES.has(b.type))], aside: rest.filter((b) => ASIDE_TYPES.has(b.type)) };
}

// Type scale fitting: grow sparse slides (classroom legibility, no dead space) and shrink overfull
// ones; report overflow to the server when even the smallest step does not fit.
const FIT_STEPS = [0.8, 0.9, 1, 1.15, 1.3];
const FIT_DEFAULT = 2;
const SPARSE_RATIO = 0.6; // content filling less than this share of the body may grow

export function Slide({ spec, phase = "", onOverflow }) {
  const bodyRef = useRef(null);
  const [fit, setFit] = useState({ idx: FIT_DEFAULT, done: false });
  const lastKey = useRef(null);
  const key = spec.id; // only a new slide re-fits; in-place updates never jump the type size
  if (lastKey.current !== key) {
    // New slide: start fitting again from the default size.
    lastKey.current = key;
    if (fit.idx !== FIT_DEFAULT || fit.done) setFit({ idx: FIT_DEFAULT, done: false });
  }

  useLayoutEffect(() => {
    const el = bodyRef.current;
    if (!el) return;
    const overflow = el.scrollHeight > el.clientHeight + 2;
    const content = [...el.children].reduce((h, c) => Math.max(h, c.scrollHeight), 0);
    if (overflow) {
      if (fit.idx > 0) setFit({ idx: fit.idx - 1, done: true });
      else onOverflow && onOverflow(spec.id);
    } else if (!fit.done && fit.idx < FIT_STEPS.length - 1 && content < el.clientHeight * SPARSE_RATIO) {
      setFit({ idx: fit.idx + 1, done: false });
    }
  });

  const style = { "--fit": FIT_STEPS[fit.idx] };
  if (spec.layout === "title") {
    return html`<section data-slide=${spec.id} class=${`slide layout-title ${phase}`} style=${style}>
      <div class="slide-head">
        <div class="rule"></div>
        <h1 class="slide-title">${spec.title}</h1>
        ${spec.subtitle && html`<p class="slide-subtitle">${spec.subtitle}</p>`}
      </div>
    </section>`;
  }
  const { main, aside } = splitBlocks(spec.blocks);
  const def = spec.layout === "definition" && spec.blocks.find((b) => b.type === "definition");
  const title = def ? def.term : spec.title;
  return html`<section data-slide=${spec.id} class=${`slide layout-${spec.layout} ${phase}`} style=${style}>
    <header class="slide-head">
      ${(spec.facet || spec.continuation_of) && html`<div class="crumb">
        ${spec.subtitle && html`<span>${spec.subtitle}</span>`}
        ${spec.facet && html`<span class="sep"></span><span class="facet">${spec.facet}</span>`}
        ${spec.continuation_of && !spec.facet && html`<span class="cont">continued</span>`}
      </div>`}
      <h1 class="slide-title">${title}</h1>
    </header>
    <div ref=${bodyRef} class=${"slide-body" + (aside.length ? " with-aside" : "")}>
      <div class="main">${main.map((b) => html`<${Block} key=${b.id} b=${b} wide=${!aside.length} termInTitle=${!!def} />`)}</div>
      ${aside.length > 0 && html`<div class="aside">${aside.map((b) => html`<${Block} key=${b.id} b=${b} />`)}</div>`}
    </div>
  </section>`;
}

// Scales the 1920x1080 stage to fit its container, letterboxed and centred.
export function useStageScale(containerRef) {
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const fit = () => setScale(Math.min(el.clientWidth / 1920, el.clientHeight / 1080));
    fit();
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return scale;
}
