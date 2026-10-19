// Photosynthesis in a leaf (simulation/templates/photosynthesis.py), a process scene (S3): a plant with one large
// leaf, the Sun, the soil. Five numbered steps: light onto the leaf, water up from the roots, carbon dioxide in and
// oxygen out through the stomata, glucose made in the leaf; the current one is bold and moving, its name in the
// heading once said. Under the picture the word equation, built term by term as the teacher says them (a term not
// said is an empty box); respiration's reverse equation only once "respiration" is said. Nothing here is a number.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, W, shown } from "./draw.js";
import { Dots, Flow, PartLabel, StepBadge, StepTitle, currentStep, stepIndex } from "./process.js";

export const TWEEN = [];
export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const LEAF = "M 300 330 Q 540 140 820 300 Q 560 450 300 330 Z";
const STOMA_IN = [664, 366], STOMA_OUT = [560, 382];
const PATH = {
  light: [[[958, 214], [786, 262]], [[986, 248], [814, 294]]],
  water: [[[230, 584], [230, 420], [300, 340], [430, 318]]],
  co2: [[[930, 470], [790, 420], [STOMA_IN[0] + 10, STOMA_IN[1] + 8]]],
  o2: [[[STOMA_OUT[0], STOMA_OUT[1] + 10], [610, 440], [660, 490]]],
};
const BADGE = { light: [1062, 290], water: [176, 470], co2: [1050, 430], glucose: [600, 262], o2: [540, 470] };
const TERM_OF = { co2: "t_co2", water: "t_water", glucose: "t_glucose", o2: "t_o2", light: "t_light" };

function Equation({ sim, cur, y }) {
  const lb = sim.labels || {}, txt = (id) => (lb[id] && lb[id].symbol) || "";
  const curTerm = cur >= 0 ? TERM_OF[sim.steps[cur].id] : "";
  const terms = [["t_co2"], ["+"], ["t_water"], ["→"], ["t_glucose"], ["+"], ["t_o2"]];
  const cond = [txt("t_light"), txt("t_chlorophyll")].filter(Boolean).join(", ");
  const width = (t) => (t === "+" ? 50 : t === "→" ? Math.max(150, 30 + cond.length * 13) : txt(t) ? 36 + txt(t).length * 18.5 : 120);
  const total = terms.reduce((a, [t]) => a + width(t) + 12, -12);
  let x = (W - total) / 2;
  const out = [];
  for (const [t] of terms) {
    const w = width(t);
    if (t === "+") out.push(html`<text key=${"p" + x} class="sim-eq-op" x=${x + w / 2} y=${y + 12} text-anchor="middle">+</text>`);
    else if (t === "→") {
      out.push(html`<g key="arrow" class="sim-eq-arrow"><line x1=${x + 10} y1=${y} x2=${x + w - 18} y2=${y} />
        <path d=${`M${x + w - 6},${y} L${x + w - 26},${y - 11} L${x + w - 26},${y + 11} Z`} /></g>`);
      if (cond) out.push(html`<text key="cond" class="sim-eq-cond" x=${x + w / 2} y=${y - 18} text-anchor="middle" data-el="equation">${cond}</text>`);
    } else {
      const said = Boolean(txt(t));
      out.push(html`<g key=${t} class=${"sim-eq-term" + (said ? " said" : "") + (t === curTerm ? " cur" : "")} data-term=${t} data-el="equation">
        <rect x=${x} y=${y - 30} width=${w} height="60" rx="14" />
        ${said && html`<text x=${x + w / 2} y=${y + 12} text-anchor="middle">${txt(t)}</text>`}</g>`);
    }
    x += w + 12;
  }
  return html`<g class="sim-equation" data-el="equation">${out}</g>`;
}

export function scene({ sim, t }) {
  const cur = currentStep(sim, t);
  const on = (id) => stepIndex(sim, id) === cur;
  const lb = sim.labels || {};
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (lb.respiration && lb.respiration.symbol) {  // said: the reverse, in the plant's cells, all the time
    // two lines: one line ran into the sun's rays (S3 screenshots)
    out.push(html`<text key="resp" class="sim-label word part" x="34" y="100" data-el="equation" data-source="said">
      <tspan class="sym">Respiration (the reverse):</tspan>
      <tspan class="sym" x="34" dy="40">glucose + oxygen → carbon dioxide + water + energy</tspan></text>`);
  }
  if (shown(sim, "plant")) {
    out.push(html`<rect key="soil" class="sim-soil" data-el="plant" x="0" y="520" width=${W} height="70" />`);
    out.push(html`<g key="roots" class="sim-roots" data-el="plant">
      <line x1="230" y1="520" x2="180" y2="580" /><line x1="230" y1="520" x2="230" y2="586" /><line x1="230" y1="520" x2="284" y2="576" />
      <line x1="200" y1="556" x2="168" y2="560" /><line x1="258" y1="548" x2="296" y2="550" /></g>`);
    out.push(html`<path key="stem" class="sim-stem" data-el="plant" d="M 230 520 L 230 410 L 300 330" />`);
    out.push(html`<path key="leaf" class=${"sim-leaf" + (on("glucose") ? " cur" : "")} data-el="plant" d=${LEAF} />`);
    out.push(html`<line key="midrib" class="sim-midrib" data-el="plant" x1="300" y1="330" x2="820" y2="300" />`);
    for (const [x, y] of [STOMA_IN, STOMA_OUT]) {
      out.push(html`<ellipse key=${"st" + x} class="sim-stoma" data-el="plant" cx=${x} cy=${y} rx="16" ry="8" />`);
    }
    out.push(html`<${PartLabel} key="leafl" sim=${sim} id="leaf" x=${290} y=${300} anchor="end" />`);
    out.push(html`<${PartLabel} key="stl" sim=${sim} id="stomata" x=${520} y=${414} anchor="end" />`);
    out.push(html`<${PartLabel} key="rtl" sim=${sim} id="roots" x=${306} y=${566} anchor="start" />`);
  }
  if (shown(sim, "sun")) {
    const rays = [];
    for (let k = 0; k < 8; k++) {
      const a = (k * Math.PI) / 4 + t * 0.2;
      rays.push(html`<line key=${k} x1=${1020 + 48 * Math.cos(a)} y1=${168 + 48 * Math.sin(a)} x2=${1020 + 64 * Math.cos(a)} y2=${168 + 64 * Math.sin(a)} />`);
    }
    out.push(html`<g key="sun" class="sim-sun" data-el="sun"><circle cx="1020" cy="168" r="38" />${rays}</g>`);
  }
  const ROLE = { light: "light", water: "water", co2: "gas", o2: "gas" };
  for (const id of ["light", "water", "co2", "o2"]) {
    if (!shown(sim, id)) continue;
    for (const [k, pts] of PATH[id].entries()) {
      out.push(html`<${Flow} key=${id + k} pts=${pts} t=${t} on=${on(id)} role=${ROLE[id]} id=${id} />`);
    }
    if (on(id) && id !== "light") {
      out.push(html`<${Dots} key=${id + "d"} pts=${PATH[id][0]} t=${t} n=${4} r=${8} cls=${"sim-dot r-" + (id === "water" ? "water" : "gas")} />`);
    }
  }
  // the gases' formulas only once said (as the equation's terms)
  if (shown(sim, "co2") && lb.t_co2 && lb.t_co2.symbol) out.push(html`<text key="co2t" class="sim-gas" x="940" y="462" data-el="co2">CO₂</text>`);
  if (shown(sim, "o2") && lb.t_o2 && lb.t_o2.symbol) out.push(html`<text key="o2t" class="sim-gas" x="676" y="506" data-el="o2">O₂</text>`);
  if (shown(sim, "glucose")) {  // sugar made in the leaf: small hexagons, bold while it is the step
    const g = on("glucose");
    out.push(html`<g key="glu" class=${"sim-glucose" + (g ? " cur" : "")} data-el="glucose">
      ${[[520, 318], [566, 300], [612, 318]].map(([x, y], i) => {
        const r = g ? 18 + 3 * Math.sin(t * 4 + i) : 16;
        const pts = Array.from({ length: 6 }, (_, k) => `${(x + r * Math.cos((k * Math.PI) / 3)).toFixed(1)},${(y + r * Math.sin((k * Math.PI) / 3)).toFixed(1)}`).join(" ");
        return html`<polygon key=${i} points=${pts} />`;
      })}</g>`);
  }
  for (const id of Object.keys(BADGE)) {
    const [x, y] = BADGE[id];
    // the number only (the step's name prints in the heading once said)
    out.push(html`<${StepBadge} key=${"b" + id} sim=${{ ...sim, steps: sim.steps.map((s) => ({ ...s, label: "" })) }}
      id=${id} x=${x - 26} y=${y} cur=${cur} />`);
  }
  if (shown(sim, "equation")) out.push(html`<${Equation} key="eq" sim=${sim} cur=${cur} y=${640} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} x=${34} y=${712} />`);
  return out;
}
