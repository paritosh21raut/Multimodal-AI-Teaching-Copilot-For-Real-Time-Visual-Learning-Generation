// Slide renderer shared by /display and /control. Renders a SlideSpec (docs/contracts/slide-spec.md).
// Items are keyed by their stable ids, so Preact keeps existing DOM nodes and only new nodes get the
// mount animation (.enter) - in-place updates never re-animate the whole slide.
import { html, useLayoutEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { mixed, rich, Tex } from "./rich.js";

const ARROW = html`<svg class="arrow" viewBox="0 0 56 40" aria-hidden="true">
  <path d="M4 20h40M34 9l12 11-12 11" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

const itemClass = (it, base) =>
  [base, "enter", it.provisional && "provisional", it.added && "added", it.emphasis && "emph"].filter(Boolean).join(" ");

function Definition({ b, termInTitle }) {
  return html`<div class="def enter">
    ${!termInTitle && html`<div class="def-term enter">${rich(b.term)}</div>`}
    <div class="def-body enter">${mixed(b.definition, b.math)}</div>
    ${b.notes.length > 0 && html`<div class="def-notes">
      ${b.notes.map((n) => html`<span key=${n.id} class=${itemClass(n, "def-note")}>${mixed(n.text, n.math)}</span>`)}
    </div>`}
  </div>`;
}

// List markers (style chosen by the server, presentation.annotate): numbers for counted / ordered lists, letters for
// a) b) options, bullets for explanations. Provisional teasers get no marker number.
const LETTER_PREFIX = /^\(?[a-h][).]\s+/;
const markers = (items, style) => {
  let n = 0;
  return items.map((it) => {
    if (it.provisional) return [it, ""];
    n += 1;
    return [it, style === "numbers" ? String(n) : style === "letters" ? String.fromCharCode(96 + n) : ""];
  });
};

function Points({ b, wide }) {
  const style = b.style || "bullets";
  const cols = wide && b.items.length > 3 && b.items.every((i) => i.text.length < 90) ? "cols-2" : "";
  const strip = (s) => (style === "letters" && s ? s.replace(LETTER_PREFIX, "") : s);
  return html`<div class="points">
    ${b.heading && html`<div class="points-heading">${rich(b.heading)}</div>`}
    <ol class=${`points-list list-${style} ${cols}`}>
      ${markers(b.items, style).map(([it, mark]) => html`<li key=${it.id} class=${itemClass(it, "point")}>
        ${it.provisional ? html`<span class="num ghost"></span>`
          : mark ? html`<span class="num">${mark}</span>` : html`<span class="num bullet"></span>`}<span>${mixed(strip(it.text), strip(it.math))}</span>
      </li>`)}
    </ol>
  </div>`;
}

// "Inhale: diaphragm contracts, ..." -> label "Inhale" + detail; a long label without a name reads as text.
const LONG_STEP = 60;
function stepText(s) {
  if (s.detail || s.math) return { label: s.label, detail: s.detail };
  const m = /^([^:]{2,40}):\s+(.{8,})$/.exec(s.label);
  return m && m[1].split(" ").length <= 4 ? { label: m[1], detail: m[2] } : { label: s.label, detail: "" };
}

function Process({ b }) {
  return html`<div class="process">
    <div class=${"process-row" + (b.steps.length >= 5 ? " many" : "")}>
      ${b.steps.map((s, i) => { const { label, detail } = stepText(s); return html`<div key=${s.id} class="step enter">
        <div class="step-card">
          <span class="step-no">STEP ${i + 1}</span>
          <span class=${"step-label" + (label.length > LONG_STEP ? " long" : "")}>${mixed(label, s.math)}</span>
          ${detail && html`<span class="step-detail">${rich(detail)}</span>`}
        </div>
        ${i < b.steps.length - 1 && ARROW}
      </div>`; })}
    </div>
    ${b.cyclic && html`<div class="cycle-note">↻ The cycle repeats</div>`}
  </div>`;
}

function Comparison({ b }) {
  return html`<table class="compare enter">
    <thead><tr><th></th>${b.columns.map((c) => html`<th key=${c.id}>${rich(c.heading)}</th>`)}</tr></thead>
    <tbody>
      ${b.rows.map((r) => html`<tr key=${r.id} class="enter">
        <td class="aspect">${rich(r.aspect)}</td>${r.cells.map((c, i) => html`<td key=${i}>${rich(c)}</td>`)}
      </tr>`)}
    </tbody>
  </table>`;
}

function Timeline({ b }) {
  return html`<div class="timeline">
    ${b.events.map((e) => html`<div key=${e.id} class="tl-event enter">
      <span class="tl-when">${e.when}</span>
      <span class="tl-label">${rich(e.label)}</span>
      ${e.detail && html`<span class="tl-detail">${rich(e.detail)}</span>`}
    </div>`)}
  </div>`;
}

function CauseEffect({ b }) {
  return html`<div class="causal">
    ${b.links.map((l) => html`<div key=${l.id} class="link enter">
      <div class="cause"><span>${rich(l.cause)}</span></div>${ARROW}<div class="effect"><span>${rich(l.effect)}</span></div>
    </div>`)}
  </div>`;
}

function TreeNode({ n, root }) {
  return html`<div class=${root ? "tree-root" : "tree-sub enter"}>
    <div class="tree-node">${rich(n.label)}</div>
    ${n.children.length > 0 && html`<div class="tree-children">
      ${n.children.map((c) => html`<${TreeNode} key=${c.id} n=${c} />`)}
    </div>`}
  </div>`;
}

// KaTeX (latex built by presentation.mathtext); the formula as said when it cannot be rendered. Words and chemical
// formulas inside it use the slide font (slide.css), so a word equation looks like the rest of the slide.
function Formula({ b }) {
  return html`<div class="formula">
    <div class="formula-eq enter"><${Tex} latex=${b.latex} text=${b.spoken || b.latex} /></div>
    ${b.variables.length > 0 && html`<div class="formula-vars">
      ${b.variables.map((v) => html`<span key=${v.symbol} class="var enter"><${Tex} cls="sym" latex=${v.latex} text=${v.symbol} />
        <span class="meaning">${rich(v.meaning)}</span>${v.unit && html`<span class="unit">${v.unit}</span>`}</span>`)}
    </div>`}
  </div>`;
}

// Fact tiles: short attribute facts about named things ("Smallest planet" / "Mercury").
function Facts({ b }) {
  const cols = b.facts.length === 3 || b.facts.some((f) => f.value.length > 24) ? 3 : Math.min(4, Math.max(1, b.facts.length));
  return html`<div class="facts">
    ${b.heading && html`<div class="points-heading">${rich(b.heading)}</div>`}
    <div class="facts-grid" style=${{ "--cols": cols }}>
      ${b.facts.map((f) => html`<div key=${f.id} class="fact enter">
        <span class="fact-label">${rich(f.label)}</span>
        ${f.value && html`<span class="fact-value">${rich(f.value)}</span>`}
      </div>`)}
    </div>
  </div>`;
}

// Named groups side by side ("Inner planets" | "Outer planets").
function Groups({ b }) {
  return html`<div class="groups">
    ${b.heading && html`<div class="points-heading">${rich(b.heading)}</div>`}
    <div class="groups-row">
      ${b.groups.map((g) => html`<div key=${g.id} class="group enter">
        <div class="group-label">${rich(g.label)}</div>
        <div class="group-items">${g.items.map((i) => html`<span key=${i.id} class=${itemClass(i, "group-item")}>${rich(i.text)}</span>`)}</div>
      </div>`)}
    </div>
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
    case "facts": return html`<${Facts} b=${b} />`;
    case "groups": return html`<${Groups} b=${b} />`;
    case "example": return html`<div class="example enter"><span class="label">Example</span>
      ${b.title && html`<span class="title">${rich(b.title)}</span>`}${mixed(b.text, b.math)}</div>`;
    case "callout": return html`<div class="callout enter"><span class="label">${
      { key: "Key idea", tip: "Remember", note: "Note" }[b.kind]}</span>${mixed(b.text, b.math)}</div>`;
    default: return null;
  }
}

// Secondary blocks go into the right-hand aside when the primary block leaves room for one.
const ASIDE_TYPES = new Set(["callout", "example", "image"]);
const FULL_WIDTH_PRIMARY = new Set(["process", "comparison", "timeline", "hierarchy", "cause_effect", "formula", "facts", "groups"]);
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
export const partLabel = (n) => (n ? ROMAN[n] || String(n) : "");

function splitBlocks(blocks) {
  if (blocks.length < 2) return { main: blocks, aside: [] };
  const [primary, ...rest] = blocks;
  // wide content anywhere (a diagram, tiles, two definitions side by side) needs the full width: stack instead
  if (blocks.some((b) => FULL_WIDTH_PRIMARY.has(b.type)) || blocks.filter((b) => b.type === "definition").length > 1)
    return { main: blocks, aside: [] };
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
        <h1 class="slide-title">${rich(spec.title)}</h1>
        ${spec.subtitle && html`<p class="slide-subtitle">${spec.subtitle}</p>`}
      </div>
    </section>`;
  }
  const { main, aside } = splitBlocks(spec.blocks);
  const defs = spec.blocks.filter((b) => b.type === "definition");
  const def = spec.layout === "definition" && defs.length === 1 && defs[0];
  const title = def ? def.term : spec.title;
  // Two concepts defined together (elements and compounds): side-by-side definition cards.
  const pairDefs = defs.length > 1 ? new Set(defs.map((d) => d.id)) : null;
  // ... each concept is a column: its definition, then its own formula / points / examples (block.about = def id)
  const mainRest = pairDefs ? main.filter((b) => !pairDefs.has(b.id) && !pairDefs.has(b.about)) : main;
  return html`<section data-slide=${spec.id} class=${`slide layout-${spec.layout} ${phase}`} style=${style}>
    <header class="slide-head">
      ${(spec.facet || spec.continuation_of) && html`<div class="crumb">
        ${spec.subtitle && html`<span>${spec.subtitle}</span>`}
        ${spec.facet && html`<span class="sep"></span><span class="facet">${spec.facet}</span>`}
        ${spec.continuation_of && !spec.facet && html`<span class="cont">continued</span>`}
      </div>`}
      <h1 class="slide-title">${rich(title)}${spec.part && html`<span class="part" title=${`Part ${spec.part}`}>${partLabel(spec.part)}</span>`}</h1>
    </header>
    <div ref=${bodyRef} class=${"slide-body" + (aside.length ? " with-aside" : "")}>
      <div class="main">
        ${pairDefs && html`<div class="def-pair">${defs.map((d) => html`<div key=${d.id} class="def-col">
          <${Definition} b=${d} termInTitle=${false} />
          ${spec.blocks.filter((b) => b.about === d.id).map((b) => html`<${Block} key=${b.id} b=${b} wide=${false} />`)}
        </div>`)}</div>`}
        ${mainRest.map((b) => html`<${Block} key=${b.id} b=${b} wide=${!aside.length} termInTitle=${!!def} />`)}
      </div>
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
