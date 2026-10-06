// Slide renderer shared by /display and /control. Renders a SlideSpec (docs/contracts/slide-spec.md).
// Items are keyed by their stable ids, so Preact keeps existing DOM nodes and only new nodes get the
// mount animation (.enter) - in-place updates never re-animate the whole slide.
import { html, useEffect, useLayoutEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { mixed, rich, Tex } from "./rich.js";

const ARROW = html`<svg class="arrow" viewBox="0 0 56 40" aria-hidden="true">
  <path d="M4 20h40M34 9l12 11-12 11" fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;

const itemClass = (it, base) =>
  [base, "enter", it.provisional && "provisional", it.added && "added", it.emphasis && "emph"].filter(Boolean).join(" ");

// A definition: a card with a small "Definition" tab on its top edge (user 2026-10-06: the green side bar was
// dull). Concepts side by side / members of a set (`card`): the whole column is one card, the term its heading.
function Definition({ b, termInTitle, card }) {
  return html`<div class=${"def enter" + (card ? " def-card" : "")}>
    ${!termInTitle && html`<div class="def-term enter" data-edit=${card ? b.id + ":term" : undefined}>${rich(b.term)}</div>`}
    <div class="def-body enter" data-edit=${b.id}>${!card && html`<span class="def-tab">Definition</span>`}${mixed(b.definition, b.math)}</div>
    ${b.notes.length > 0 && html`<div class="def-notes">
      ${b.notes.map((n) => html`<span key=${n.id} class=${itemClass(n, "def-note")} data-edit=${n.id}>${mixed(n.text, n.math)}</span>`)}
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
      ${markers(b.items, style).map(([it, mark]) => html`<li key=${it.id} class=${itemClass(it, "point")}
          data-edit=${it.provisional ? undefined : it.id}>
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

// Up to 6 steps in one row; 7-10 in two rows, the longer first (mirrors composer.process_rows). Round 5 (user
// 2026-10-06): a whole process on one slide; a longer one continues on the next part and keeps counting (b.start).
function processRows(n) {
  if (n <= 6) return n ? [[0, n]] : [];
  const k = Math.ceil(n / 2);
  return [[0, k], [k, n]];
}

// from the end of row 1 back to the start of row 2 (both rows share the column grid, so the ends line up)
function Turn({ cols }) {
  const right = 100 - 50 / cols, left = 50 / cols;
  return html`<div class="process-turn" aria-hidden="true">
    <svg viewBox="0 0 100 40" preserveAspectRatio="none"><path d=${`M${right} 0 V20 H${left} V40`}
      fill="none" stroke="currentColor" stroke-width="3" vector-effect="non-scaling-stroke" stroke-linejoin="round"/></svg>
    <span class="turn-head" style=${{ left: `calc(${left}% - 20px)` }}></span>
  </div>`;
}

function Process({ b }) {
  const rows = processRows(b.steps.length);
  const cols = rows.length ? Math.max(...rows.map(([a, z]) => z - a)) : 1;
  const start = b.start || 1;
  const row = ([a, z]) => html`<div class=${"process-row" + (cols >= 5 ? " many" : "") + (rows.length > 1 ? " grid" : "")}
      style=${rows.length > 1 ? { "--cols": cols } : null}>
    ${b.steps.slice(a, z).map((s, j) => { const { label, detail } = stepText(s); return html`<div key=${s.id} class="step enter">
      <div class="step-card" data-edit=${s.id}>
        <span class="step-no">STEP ${start + a + j}</span>
        <span class=${"step-label" + (label.length > LONG_STEP ? " long" : "")}>${mixed(label, s.math)}</span>
        ${detail && html`<span class="step-detail">${rich(detail)}</span>`}
      </div>
      ${a + j < z - 1 && ARROW}
    </div>`; })}
  </div>`;
  return html`<div class=${"process" + (rows.length > 1 ? " two-rows" : "")}>
    ${start > 1 && html`<div class="process-cont">continues from step ${start - 1}</div>`}
    ${rows.map((r, i) => html`${i > 0 && html`<${Turn} cols=${cols} />`}${row(r)}`)}
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
  return html`<div class=${(root ? "tree-root" : "tree-sub enter") + (n.children.length ? " has-kids" : "")}>
    <div class="tree-node" data-edit=${n.id}>${rich(n.label)}</div>
    ${n.children.length > 0 && html`<div class="tree-children">
      ${n.children.map((c) => html`<${TreeNode} key=${c.id} n=${c} />`)}
    </div>`}
  </div>`;
}

const Chips = ({ label, labelId, kids }) => html`<div class="group enter">
  <div class="group-label" data-edit=${labelId}>${rich(label)}</div>
  <div class="group-items">${kids.map((c) => html`<span key=${c.id} class="group-item enter" data-edit=${c.id}>${rich(c.label)}</span>`)}</div>
</div>`;

// Beside an image a classification is one card: its label, the kinds as chips; a tree of several levels is a card
// per divided kind under the tree's label (composer.block_height mirrors both).
function NarrowTree({ root }) {
  const divided = root.children.filter((c) => c.children.length);
  if (!divided.length) return html`<div class="groups"><${Chips} label=${root.label} labelId=${root.id} kids=${root.children} /></div>`;
  const leaves = root.children.filter((c) => !c.children.length);
  return html`<div class="groups narrow-tree">
    <div class="points-heading" data-edit=${root.id}>${rich(root.label)}</div>
    ${divided.map((c) => html`<${Chips} key=${c.id} label=${c.label} labelId=${c.id} kids=${c.children} />`)}
    ${leaves.length > 0 && html`<div class="group-items">${leaves.map((c) => html`<span key=${c.id}
      class="group-item enter" data-edit=${c.id}>${rich(c.label)}</span>`)}</div>`}
  </div>`;
}

// KaTeX (latex built by presentation.mathtext); the formula as said when it cannot be rendered. Words and chemical
// formulas inside it use the slide font (slide.css), so a word equation looks like the rest of the slide.
function Formula({ b }) {
  return html`<div class="formula">
    <div class="formula-eq enter" data-edit=${b.id} data-delete-only="1"><${Tex} latex=${b.latex} text=${b.spoken || b.latex} /></div>
    ${b.variables.length > 0 && html`<div class="formula-vars">
      ${b.variables.map((v) => html`<span key=${v.symbol} class="var enter"><${Tex} cls="sym" latex=${v.latex} text=${v.symbol} />
        <span class="meaning">${rich(v.meaning)}</span>${v.unit && html`<span class="unit">${v.unit}</span>`}</span>`)}
    </div>`}
  </div>`;
}

// Formulas said together (round 5, user 2026-10-06: the three equations of motion were three slides): one compact
// equation card each, stacked, and ONE legend of the symbols below them (the first meaning of a symbol wins).
function FormulaSet({ b }) {
  const seen = new Map();
  b.items.forEach((f) => f.variables.forEach((v) => { if (!seen.has(v.symbol)) seen.set(v.symbol, v); }));
  const vars = [...seen.values()];
  return html`<div class="formula formula-set">
    ${b.items.map((f) => html`<div key=${f.id} class="formula-eq enter" data-edit=${f.id} data-delete-only="1">
      <${Tex} latex=${f.latex} text=${f.spoken || f.latex} /></div>`)}
    ${vars.length > 0 && html`<div class="formula-vars">
      ${vars.map((v) => html`<span key=${v.symbol} class="var enter"><${Tex} cls="sym" latex=${v.latex} text=${v.symbol} />
        <span class="meaning">${rich(v.meaning)}</span>${v.unit && html`<span class="unit">${v.unit}</span>`}</span>`)}
    </div>`}
  </div>`;
}

// Consecutive slide-wide formulas become one set (mirrors composer._stack_height); a lone formula stays as it was.
function groupFormulas(blocks) {
  const out = [];
  for (const b of blocks) {
    const last = out[out.length - 1];
    if (b.type === "formula" && !b.about && last && last.type === "formula" && !last.about) {
      out[out.length - 1] = { type: "formula_set", id: `set-${last.id}`, items: [last, b] };
    } else if (b.type === "formula" && !b.about && last && last.type === "formula_set") {
      last.items = [...last.items, b];
    } else out.push(b);
  }
  return out;
}

// Fact tiles: short attribute facts about named things ("Smallest planet" / "Mercury").
function Facts({ b, narrow }) {
  // beside an image: at most 4 tiles in 2 columns (policy), full type size (composer: block_height narrow=True)
  const cols = narrow ? Math.min(2, b.facts.length)
    : b.facts.length === 3 || b.facts.some((f) => f.value.length > 24) ? 3 : Math.min(4, Math.max(1, b.facts.length));
  return html`<div class="facts">
    ${b.heading && html`<div class="points-heading">${rich(b.heading)}</div>`}
    <div class="facts-grid" style=${{ "--cols": cols }}>
      ${b.facts.map((f) => html`<div key=${f.id} class="fact enter" data-edit=${f.id}>
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
        <div class="group-label" data-edit=${g.id}>${rich(g.label)}</div>
        <div class="group-items">${g.items.map((i) => html`<span key=${i.id} class=${itemClass(i, "group-item")}
          data-edit=${i.id}>${rich(i.text)}</span>`)}</div>
      </div>`)}
    </div>
  </div>`;
}

// The image of the image layout (F-007b): the box has the image's aspect ratio before the file loads (no reflow),
// the picture fades in. No credit line on slides (user 2026-10-06; licence and author are kept for exports).
// A `ghost` block is the drop zone /control shows while the teacher drags a file over the slide.
function Figure({ b, onClick }) {
  const [loaded, setLoaded] = useState(false);
  const style = { "--aspect": b.aspect || 4 / 3 };
  if (b.ghost) {
    return html`<figure class="figure ghost" style=${style}>
      <div class="drop-hint"><svg viewBox="0 0 48 48" aria-hidden="true"><path d="M24 32V12M15 21l9-9 9 9M10 36h28"
        fill="none" stroke="currentColor" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round"/></svg>
        <span>${b.alt || "Drop to place the image here"}</span></div>
    </figure>`;
  }
  return html`<figure class=${"figure" + (onClick ? " zoomable" : "")} style=${style}
      onClick=${onClick} title=${onClick ? "Show full screen on the display" : undefined}>
    <img src=${b.url} alt=${b.alt} class=${loaded ? "loaded" : ""} onLoad=${() => setLoaded(true)} />
  </figure>`;
}

// The slide's image filling the 1920x1080 stage (the teacher clicked it in /control). Both pages render it the same
// way; only /control passes onClose (click on it = back to the slide).
export function ZoomedImage({ image, onClose }) {
  const [loaded, setLoaded] = useState(false);
  return html`<div class=${"zoomed" + (onClose ? " closable" : "")} onClick=${onClose}>
    <img src=${image.url} alt=${image.alt} class=${loaded ? "loaded" : ""} onLoad=${() => setLoaded(true)}
      style=${{ "--aspect": image.aspect || 4 / 3 }} />
  </div>`;
}

export const imageOf = (spec) => (spec && spec.blocks ? spec.blocks.find((b) => b.type === "image") : null);

// Mirrors composer.image_column_px: wider column for landscape images; a tall image takes only the width it needs.
const BODY_BUDGET_PX = 740; // composer.IMAGE_HEIGHT_PX (the body is 754-763 px tall in Edge)
export const imageColumn = (aspect) => {
  const a = aspect || 4 / 3;
  return Math.round(Math.min(a >= 1.25 ? 720 : 600, Math.max(380, BODY_BUDGET_PX * a)));
};

function Block({ b, wide, termInTitle, narrow, card }) {
  switch (b.type) {
    case "definition": return html`<${Definition} b=${b} termInTitle=${termInTitle} card=${card && !termInTitle} />`;
    case "points": return html`<${Points} b=${b} wide=${wide} />`;
    case "facts": return html`<${Facts} b=${b} narrow=${narrow} />`;
    case "process": return html`<${Process} b=${b} />`;
    case "comparison": return html`<${Comparison} b=${b} />`;
    case "timeline": return html`<${Timeline} b=${b} />`;
    case "cause_effect": return html`<${CauseEffect} b=${b} />`;
    case "hierarchy": return narrow ? html`<${NarrowTree} root=${b.root} />`
      : html`<div class="tree"><${TreeNode} n=${b.root} root /></div>`;
    case "formula": return html`<${Formula} b=${b} />`;
    case "formula_set": return html`<${FormulaSet} b=${b} />`;
    case "image": return html`<${Figure} b=${b} />`;
    case "groups": return html`<${Groups} b=${b} />`;
    case "example": return html`<div class="example enter" data-edit=${b.id}><span class="label">Example</span>
      ${b.title && html`<span class="title">${rich(b.title)}</span>`}${mixed(b.text, b.math)}</div>`;
    // a note is labelled like an example, on a plain card (user 2026-10-06: the coloured note card looked bad)
    case "callout": return html`<div class=${"callout enter " + b.kind} data-edit=${b.id}><span class="label">${
      { key: "Key idea", tip: "Remember", note: "Note" }[b.kind]}</span>${mixed(b.text, b.math)}</div>`;
    default: return null;
  }
}

// Secondary blocks go into the right-hand aside when the primary block leaves room for one.
// With an image (image layout, F-007b) the image has the right-hand column alone and everything else is content.
const ASIDE_TYPES = new Set(["callout", "example"]);
const FULL_WIDTH_PRIMARY = new Set(["process", "comparison", "timeline", "hierarchy", "cause_effect", "formula", "facts", "groups"]);
const ROMAN = ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"];
// definition cards per row (composer.grid_columns): 1 | 2 | 3 | 2x2 | 3+2 | 3x2
const cardColumns = (n) => (n <= 1 ? 1 : n === 3 || n >= 5 ? 3 : 2);
const words = (s) => (s || "").toLowerCase().match(/[a-z0-9]+/g) || [];
// does the title name this term ("What is dipole moment?" / "Dipole moment")? (composer._title_names)
export const titleNames = (title, term) => {
  const t = words(term).join(" ");
  return !!t && ` ${words(title).join(" ")} `.includes(` ${t} `);
};
// definitions after other content, with at most one definition before it (composer.trailing_definitions)
export function trailingDefs(blocks) {
  const lead = [], later = [];
  let content = false;
  for (const b of blocks) {
    if (b.type === "image") continue;
    if (b.type === "definition") (content ? later : lead).push(b);
    else if (!b.about) content = true;
  }
  return lead.length <= 1 ? later : [];
}
export const partLabel = (n) => (n ? ROMAN[n] || String(n) : "");

function splitBlocks(blocks, members) {
  const image = blocks.find((b) => b.type === "image");
  if (image) {
    const rest = blocks.filter((b) => b.type !== "image");
    // a formula after text: the text sits beside the image, the formula and what follows go full width below
    const at = rest.findIndex((b) => b.type === "formula");
    if (at > 0) return { main: rest.slice(0, at), below: rest.slice(at), aside: [], image };
    return { main: rest, aside: [], image };
  }
  if (blocks.length < 2 || members) return { main: blocks, aside: [] };
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

export function Slide({ spec, phase = "", onOverflow, onImageClick }) {
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
    // the image column always fills the body height: only the content decides whether the type may grow
    const content = [...el.children].filter((c) => !c.classList.contains("image-col"))
      .reduce((h, c) => Math.max(h, c.scrollHeight), 0);
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
        <h1 class="slide-title"><span data-edit="title">${rich(spec.title)}</span></h1>
        ${spec.subtitle && html`<p class="slide-subtitle">${spec.subtitle}</p>`}
      </div>
    </section>`;
  }
  const members = spec.layout === "members";
  const { main, below, aside, image } = splitBlocks(spec.blocks, members);
  const defs = spec.blocks.filter((b) => b.type === "definition");
  const title = spec.title;
  // Terms defined after other content (long test 2026-10-06): one row of cards where the first of them stands,
  // instead of a part II / a giant heading (composer.trailing_definitions)
  const later = members ? [] : trailingDefs(spec.blocks);
  const laterIds = new Set(later.map((d) => d.id));
  const lead = defs.filter((d) => !laterIds.has(d.id));
  // a lone leading definition: its term is the title's subject ("What is dipole moment?") or a card of its own
  const def = lead.length === 1 && titleNames(title, lead[0].term) && lead[0];
  // Concepts defined together (elements and compounds) or the members of a set (the types of networks): definition
  // cards side by side, 1 | 2 | 3 | 2x2 | 3x2 (composer.grid_columns) ...
  const pairDefs = !later.length && (defs.length > 1 || (members && defs.length)) ? new Set(defs.map((d) => d.id)) : null;
  const gridCols = cardColumns(defs.length);
  // ... each concept is a column: its definition, then its own formula / points / examples (block.about = def id)
  const grouped = pairDefs || laterIds;
  const mainRest = main.filter((b) => !grouped.has(b.id) && !grouped.has(b.about));
  const rowAt = later.length ? mainRest.filter((b) => main.indexOf(b) < main.indexOf(later[0])).length : -1;
  const cardRow = later.length > 0 && html`<div key="card-row" class=${`def-pair card-row cols-${cardColumns(later.length)}`}>
    ${later.map((d) => html`<div key=${d.id} class="def-col">
      <${Definition} b=${d} termInTitle=${false} card />
      ${spec.blocks.filter((b) => b.about === d.id).map((b) => html`<${Block} key=${b.id} b=${b} wide=${false} />`)}
    </div>`)}</div>`;
  const stack = (blocks) => groupFormulas(blocks).map((b) => html`<${Block} key=${b.id} b=${b}
    wide=${!aside.length && !image} narrow=${!!image} termInTitle=${b === def} card=${b.type === "definition" && b !== def} />`);
  const bodyClass = "slide-body" + (aside.length ? " with-aside" : "") + (image ? (below ? " image-top" : " with-image") : "");
  const figure = image && html`<div class="image-col"><${Figure} key=${image.id} b=${image}
    onClick=${onImageClick && !image.ghost ? () => onImageClick(image) : undefined} /></div>`;
  return html`<section data-slide=${spec.id} class=${`slide layout-${spec.layout} ${phase}`} style=${style}>
    <header class="slide-head">
      ${(spec.facet || spec.continuation_of) && html`<div class="crumb">
        ${spec.subtitle && html`<span>${spec.subtitle}</span>`}
        ${spec.facet && html`<span class="sep"></span><span class="facet">${spec.facet}</span>`}
        ${spec.continuation_of && !spec.facet && html`<span class="cont">continued</span>`}
      </div>`}
      <h1 class="slide-title"><span data-edit="title">${rich(title)}</span>${spec.part && html`<span class="part" title=${`Part ${spec.part}`}>${partLabel(spec.part)}</span>`}</h1>
    </header>
    <div ref=${bodyRef} class=${bodyClass}
      style=${image ? { "--img-col": `${imageColumn(image.aspect)}px` } : null}>
      ${below ? html`<div class="image-top-row">
          <div class="main">${main.map((b) => html`<${Block} key=${b.id} b=${b} wide=${false} narrow=${true}
            termInTitle=${b === def} card=${b.type === "definition" && b !== def} />`)}</div>
          ${figure}
        </div>
        <div class="main below">${groupFormulas(below).map((b) => html`<${Block} key=${b.id} b=${b} wide=${true} />`)}</div>`
      : html`<div class="main">
        ${pairDefs && html`<div class=${`def-pair cols-${gridCols}`}>${defs.map((d) => html`<div key=${d.id} class="def-col">
          <${Definition} b=${d} termInTitle=${false} card />
          ${spec.blocks.filter((b) => b.about === d.id).map((b) => html`<${Block} key=${b.id} b=${b} wide=${false} />`)}
        </div>`)}</div>`}
        ${rowAt < 0 ? stack(mainRest) : [...stack(mainRest.slice(0, rowAt)), cardRow, ...stack(mainRest.slice(rowAt))]}
      </div>
      ${aside.length > 0 && html`<div class="aside">${aside.map((b) => html`<${Block} key=${b.id} b=${b} />`)}</div>`}
      ${figure}`}
    </div>
  </section>`;
}

// Before the first slide (/display and the /control preview): a slide develops behind glass, no text (round 5;
// redesigned after the long test 2026-10-06: "topic content and an image loading behind a glass, more premium").
// The glass stays a moment after the first slide arrives and clears over it; Blank removes it at once.
export const GLASS_EXIT_MS = 1250;
export function useGlassExit(waiting, blank) {
  const [phase, setPhase] = useState(waiting ? "on" : null);
  useEffect(() => {
    if (waiting) { setPhase("on"); return undefined; }
    if (blank) { setPhase(null); return undefined; }
    setPhase((p) => (p ? "leaving" : null));
    const t = setTimeout(() => setPhase(null), GLASS_EXIT_MS);
    return () => clearTimeout(t);
  }, [waiting, blank]);
  return phase;
}

export function Glass({ leaving }) {
  return html`<div class=${"glass" + (leaving ? " leaving" : "")} aria-hidden="true">
    <div class="aurora"><span class="au a1"></span><span class="au a2"></span><span class="au a3"></span></div>
    <span class="grain"></span>
    <div class="card">
      <span class="halo"></span>
      <div class="pane">
        <div class="draft">
          <span class="pc crumb"></span>
          <span class="pc title"></span>
          <div class="row">
            <div class="text"><span class="pc def"></span><span class="pc line l1"></span>
              <span class="pc line l2"></span><span class="pc line l3"></span></div>
            <span class="pc picture"><svg viewBox="0 0 460 392" preserveAspectRatio="xMidYMid slice">
              <circle cx="340" cy="110" r="44" fill="white" opacity="0.7" />
              <path d="M0 330 L130 200 L230 290 L310 220 L460 340 L460 392 L0 392 Z" fill="white" opacity="0.55" />
            </svg></span>
          </div>
        </div>
        <span class="frost"></span>
        <span class="sheen"></span>
      </div>
      <span class="edge"></span>
    </div>
    <div class="dots"><i></i><i></i><i></i></div>
  </div>`;
}

// The title the slide shows: always the slide title, so every part of a slide reads the same ("What is dipole
// moment?" on part I and II; user 2026-10-06: keep "What is X?", it answers a question).
export function shownTitle(spec) {
  return spec ? spec.title : "";
}

// The text the teacher edits for an element marked data-edit (live editing in /control, round 4 step D): the same
// ids the server's composer.edit_text uses. null = no such element on this slide.
export function editableText(spec, id) {
  if (!spec) return null;
  if (id === "title") return shownTitle(spec);
  let found = null;
  const walk = (n) => { if (n.id === id) found = n.label; n.children.forEach(walk); };
  for (const b of spec.blocks) {
    if (b.type === "definition") {
      if (id === b.id) return b.definition;
      if (id === `${b.id}:term`) return b.term;
      const n = b.notes.find((x) => x.id === id);
      if (n) return n.text;
    } else if (b.type === "points") {
      const i = b.items.find((x) => x.id === id);
      if (i) return i.text;
    } else if (b.type === "process") {
      const s = b.steps.find((x) => x.id === id);
      if (s) return s.label;
    } else if (b.type === "facts") {
      const f = b.facts.find((x) => x.id === id);
      if (f) return f.value ? `${f.label}: ${f.value}` : f.label;
    } else if (b.type === "groups") {
      for (const g of b.groups) {
        if (g.id === id) return g.label;
        const i = g.items.find((x) => x.id === id);
        if (i) return i.text;
      }
    } else if (b.type === "hierarchy") {
      walk(b.root);
      if (found !== null) return found;
    } else if ((b.type === "example" || b.type === "callout") && b.id === id) {
      return b.text;
    } else if (b.type === "formula" && b.id === id) {
      return b.spoken || b.latex;
    }
  }
  return null;
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
