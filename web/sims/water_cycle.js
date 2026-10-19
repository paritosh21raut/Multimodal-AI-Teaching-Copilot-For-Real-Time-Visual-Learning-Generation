// The water cycle (simulation/templates/water_cycle.py), a process scene (S3): the sea on the left, land rising to a
// hill on the right, the Sun, a cloud. Each step is an arrow with its number; the current step's arrow is bold and
// moving, the others quiet; a step's name prints once the teacher said it. Transpiration, runoff and infiltration
// appear once said. Directions are the textbook's; nothing here is a number.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, shown } from "./draw.js";
import { Dots, Flow, PartLabel, StepBadge, StepTitle, currentStep, stepIndex } from "./process.js";

export const TWEEN = [];
export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const SEA = 560, FOOT = 680;
const LAND = [[470, FOOT], [520, 572], [640, 520], [780, 430], [900, 352], [1000, 392], [1100, 440], [1100, FOOT]];
const CLOUD = [[520, 200, 46], [578, 172, 60], [646, 196, 50], [700, 214, 34]];

export function scene({ sim, t }) {
  const cur = currentStep(sim, t);
  const on = (id) => stepIndex(sim, id) === cur;
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (shown(sim, "sea")) {
    const wave = [];
    for (let x = 0; x <= 500; x += 20) wave.push(`${x},${(SEA + 6 * Math.sin(x / 40 + t * 1.5)).toFixed(1)}`);
    out.push(html`<polygon key="sea" class=${"sim-sea" + (on("collection") ? " cur" : "")} data-el="sea"
      points=${`0,${FOOT} ${wave.join(" ")} 520,${FOOT}`} />`);
    out.push(html`<${PartLabel} key="seal" sim=${sim} id="ocean" x=${30} y=${530} anchor="start" />`);
  }
  if (shown(sim, "land")) {
    out.push(html`<polygon key="land" class="sim-land" data-el="land" points=${LAND.map((p) => p.join(",")).join(" ")} />`);
    out.push(html`<g key="tree" class="sim-tree" data-el="land">
      <line class="trunk" x1="1010" y1="396" x2="1010" y2="356" /><circle class="crown" cx="1010" cy="330" r="32" />
    </g>`);
  }
  if (shown(sim, "sun")) {
    const rays = [];
    for (let k = 0; k < 8; k++) {
      const a = (k * Math.PI) / 4 + t * 0.2;
      rays.push(html`<line key=${k} x1=${80 + 48 * Math.cos(a)} y1=${112 + 48 * Math.sin(a)} x2=${80 + 64 * Math.cos(a)} y2=${112 + 64 * Math.sin(a)} />`);
    }
    out.push(html`<g key="sun" class="sim-sun" data-el="sun"><circle cx="80" cy="112" r="38" />${rays}</g>`);
    out.push(html`<${PartLabel} key="sunl" sim=${sim} id="sun" x=${170} y=${124} anchor="start" />`);
  }
  if (shown(sim, "cloud")) {
    out.push(html`<g key="cloud" class=${"sim-cloud" + (on("condensation") ? " cur" : "")} data-el="cloud">
      ${CLOUD.map(([x, y, r]) => html`<circle key=${x} cx=${x} cy=${y} r=${r} />`)}
      <rect x="500" y="200" width="210" height="44" rx="22" /></g>`);
    out.push(html`<${PartLabel} key="cloudl" sim=${sim} id="cloud" x=${610} y=${290} />`);
  }
  // the steps, each an arrow: [id, polyline(s), badge (x, y, anchor)]
  if (shown(sim, "evaporation")) {
    const e = on("evaporation");
    for (const x0 of [250, 330, 410]) {
      const pts = [];
      for (let y = SEA - 14; y >= 300; y -= 22) pts.push([x0 + 12 * Math.sin((y + x0) / 26), y]);
      out.push(html`<${Flow} key=${"ev" + x0} pts=${pts} t=${t} on=${e} role="vapour" id="evaporation" />`);
    }
    out.push(html`<${StepBadge} key="evb" sim=${sim} id="evaporation" x=${24} y=${262} cur=${cur} />`);
  }
  if (shown(sim, "transpiration")) {
    const pts = [];
    for (let y = 290; y >= 196; y -= 16) pts.push([1010 + 9 * Math.sin(y / 18), y]);
    out.push(html`<${Flow} key="tr" pts=${pts} t=${t} on=${on("transpiration")} role="vapour" id="transpiration" />`);
    out.push(html`<${StepBadge} key="trb" sim=${sim} id="transpiration" x=${1084} y=${480} cur=${cur} anchor="end" />`);
  }
  if (shown(sim, "condensation")) {
    out.push(html`<${Flow} key="co" pts=${[[420, 282], [452, 250], [490, 232]]} t=${t} on=${on("condensation")} role="vapour" id="condensation" />`);
    if (on("condensation")) {
      out.push(html`<${Dots} key="cod" pts=${[[380, 300], [440, 250], [520, 215]]} t=${t} n=${5} r=${6} cls="sim-dot r-vapour" />`);
    }
    out.push(html`<${StepBadge} key="cob" sim=${sim} id="condensation" x=${470} y=${118} cur=${cur} anchor="end" />`);
  }
  if (shown(sim, "precipitation")) {
    const p = on("precipitation"), drops = [];
    for (let k = 0; k < 7; k++) {
      const x = 640 + k * 24, y0 = 250, L = 150 + (k % 3) * 25, y = y0 + ((t * (p ? 220 : 90) + k * 47) % L);
      drops.push(html`<line key=${k} x1=${x} y1=${y} x2=${x - 5} y2=${y + 22} />`);
    }
    out.push(html`<g key="rain" class=${"sim-rain" + (p ? " cur" : "")} data-el="precipitation">${drops}</g>`);
    out.push(html`<${Flow} key="pr" pts=${[[724, 252], [760, 330], [800, 410]]} t=${t} on=${p} role="water" id="precipitation" />`);
    out.push(html`<${StepBadge} key="prb" sim=${sim} id="precipitation" x=${762} y=${150} cur=${cur} />`);
  }
  if (shown(sim, "runoff")) {
    out.push(html`<${Flow} key="ro" pts=${[[892, 336], [780, 412], [640, 504], [540, 556]]} t=${t} on=${on("runoff")} role="water" id="runoff" />`);
    out.push(html`<${StepBadge} key="rob" sim=${sim} id="runoff" x=${444} y=${470} cur=${cur} />`);
  }
  if (shown(sim, "infiltration")) {
    out.push(html`<${Flow} key="in" pts=${[[700, 488], [700, 600], [560, 648]]} t=${t} on=${on("infiltration")} role="ground" id="infiltration" />`);
    out.push(html`<${StepBadge} key="inb" sim=${sim} id="infiltration" x=${724} y=${574} cur=${cur} />`);
  }
  if (shown(sim, "collection")) {
    out.push(html`<${Flow} key="cl" pts=${[[560, 606], [490, 612], [420, 610]]} t=${t} on=${on("collection")} role="water" id="collection" />`);
    out.push(html`<${StepBadge} key="clb" sim=${sim} id="collection" x=${404} y=${610} cur=${cur} anchor="end" />`);
  }
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
