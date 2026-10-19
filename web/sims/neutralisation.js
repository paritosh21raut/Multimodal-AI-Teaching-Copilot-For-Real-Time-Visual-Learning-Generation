// Acid-base neutralisation (simulation/templates/neutralisation.py), a process scene (S3): a burette over a conical
// flask of acid. The particles are a picture (12 of the acid's H⁺, never a number printed): with the amounts said, the
// share of the H⁺ the added OH⁻ has turned into H₂O is the server's (drive.frac = n(OH⁻) / n(H⁺)); without them the
// steps tell the story (H⁺ alone, OH⁻ dropping in, pairs turning into water, the salt's ions left). The acid's anion
// and the base's cation (the salt) stay as spectators. A legend names a kind of particle once the teacher named it.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Readout, shown } from "./draw.js";
import { PartLabel, StepBadge, StepTitle, currentStep, stepIndex } from "./process.js";

export const TWEEN = [];
export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const N = 12, FX = 700, NECK_Y = 330, BOT = 640, SURF = 470;
// fixed spots in the liquid (a few rows across the cone), the same every frame
const SPOTS = (() => {
  const out = [];
  for (let r = 0; r < 4; r++) {
    const y = SURF + 30 + r * 40, half = 70 + (y - NECK_Y) * 0.55 - 30;
    for (let c = 0; c < 9; c++) out.push([FX - half + ((c + 0.5) * 2 * half) / 9 + (r % 2 ? 10 : -10), y]);
  }
  return out.map((_, k) => out[(k * 7) % out.length]);  // filled in a spread order, not row by row
})();

function counts(sim, cur, t) {
  const d = sim.drive;
  if (d.frac >= 0) {
    const pairs = d.frac < 1 ? Math.floor(N * d.frac) : N;  // short of equivalence: some H⁺ always left
    return { h: N - pairs, water: pairs, oh: Math.min(N, Math.round(N * Math.max(0, d.frac - 1))), dropping: d.added > 0 };
  }
  const id = cur >= 0 ? sim.steps[cur].id : "";
  if (id === "water") {  // the pairs turn into water, round and round (4 s)
    const k = Math.floor(((t % 4) / 4) * (N + 1));
    return { h: N - k, water: k, oh: 0, dropping: true };
  }
  if (id === "salt") return { h: 0, water: N, oh: 0, dropping: false };
  if (id === "base") return { h: N, water: 0, oh: 0, dropping: true };
  return { h: N, water: 0, oh: 0, dropping: false };
}

export function scene({ sim, t }) {
  const cur = currentStep(sim, t), lb = sim.labels || {}, c = counts(sim, cur, t);
  const on = (id) => stepIndex(sim, id) === cur;
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (shown(sim, "burette")) {
    out.push(html`<g key="bur" class="sim-burette" data-el="burette">
      <rect x=${FX - 14} y="90" width="28" height="200" rx="6" /><line x1=${FX - 26} y1="296" x2=${FX + 26} y2="296" />
      <path d=${`M${FX - 6},300 L${FX + 6},300 L${FX + 2},322 L${FX - 2},322 Z`} /></g>`);
    if (c.dropping) {
      for (let i = 0; i < 2; i++) {
        const u = (t * 0.9 + i * 0.5) % 1;
        out.push(html`<circle key=${"drop" + i} class=${"sim-drop" + (on("base") ? " cur" : "")} data-el="burette" cx=${FX} cy=${330 + u * (SURF - 340)} r="7" />`);
      }
    }
    out.push(html`<${PartLabel} key="bl" sim=${{ ...sim, labels: { base: lb.base ? { symbol: lb.base.text } : null } }} id="base" x=${FX + 34} y=${170} anchor="start" />`);
  }
  if (shown(sim, "flask")) {
    const half = (y) => 70 + (y - NECK_Y) * 0.55;
    out.push(html`<path key="liq" class=${"sim-liquid" + (on("acid") ? " cur" : "")} data-el="flask"
      d=${`M${FX - half(SURF)},${SURF} L${FX + half(SURF)},${SURF} L${FX + half(BOT)},${BOT} L${FX - half(BOT)},${BOT} Z`} />`);
    out.push(html`<path key="flask" class="sim-flask sim-obstacle" data-el="flask"
      d=${`M${FX - 40},${NECK_Y - 40} L${FX - 40},${NECK_Y} L${FX - half(BOT)},${BOT} L${FX + half(BOT)},${BOT} L${FX + 40},${NECK_Y} L${FX + 40},${NECK_Y - 40}`} />`);
    out.push(html`<${PartLabel} key="al" sim=${{ ...sim, labels: { acid: lb.acid ? { symbol: lb.acid.text } : null } }} id="acid" x=${FX - half(BOT) - 16} y=${BOT - 20} anchor="end" />`);
  }
  if (shown(sim, "ions")) {
    let k = 0;
    const put = (n, cls) => {
      for (let i = 0; i < n && k < SPOTS.length; i++, k++) {
        const [x, y] = SPOTS[k], j = 2 * Math.sin(t * 2 + k);
        out.push(cls === "water"
          ? html`<g key=${"p" + k} class=${"sim-ion water" + (on("water") ? " cur" : "")} data-el="ions">
              <circle cx=${x + j} cy=${y} r="10" /><circle cx=${x + j - 11} cy=${y - 8} r="6" /><circle cx=${x + j + 11} cy=${y - 8} r="6" /></g>`
          : html`<circle key=${"p" + k} class=${`sim-ion ${cls}` + ((cls === "h" && on("acid")) || (cls === "oh" && on("base")) || (cls === "spec" && on("salt")) ? " cur" : "")}
              data-el="ions" cx=${x + j} cy=${y} r=${cls === "spec" ? 7 : 10} />`);
      }
    };
    put(c.water, "water");
    put(c.h, "h");
    put(c.oh, "oh");
    put(Math.min(SPOTS.length - k, Math.round(N * 0.5)), "spec");  // the salt's ions (a few shown)
  }
  // the legend: a kind of particle is named once said
  const legend = [["h", "h"], ["oh", "oh"], ["water", "water"], ["salt", "spec"]].filter(([id]) => lb[id] && lb[id].symbol);
  legend.forEach(([id, cls], i) => {
    const y = 470 + i * 50, name = lb[id].symbol;  // the salt by name: in the readout
    out.push(html`<g key=${"lg" + id} class="sim-legend" data-el="ions">
      ${cls === "water"
        ? html`<g class="sim-ion water"><circle cx="1000" cy=${y - 7} r="8" /><circle cx="991" cy=${y - 14} r="5" /><circle cx="1009" cy=${y - 14} r="5" /></g>`
        : html`<circle class=${"sim-ion " + cls} cx="1000" cy=${y - 9} r="9" />`}
      <text class="sim-label word part" x="1020" y=${y} data-source="said"><tspan class="sym">${name}</tspan></text></g>`);
  });
  const marks = { acid: [FX - 200, 560], base: [FX - 60, 190], water: [FX + 150, 420], salt: [FX + 220, 610] };
  const plain = { ...sim, steps: sim.steps.map((s) => ({ ...s, label: "" })) };  // numbers only: names in the heading
  for (const id of Object.keys(marks)) {
    out.push(html`<${StepBadge} key=${"b" + id} sim=${plain} id=${id} x=${marks[id][0] - 26} y=${marks[id][1]} cur=${cur} />`);
  }
  if (shown(sim, "readout")) {
    const said = [["acid", "Acid"], ["base", "Base"]].filter(([id]) => lb[id] && lb[id].text)
      .map(([id, name]) => ({ id, symbol: name, text: lb[id].text }));
    out.push(html`<${Readout} key="readout" sim=${sim} x=${34} y=${76} fixed said=${said} minW=${300} />`);
  }
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
