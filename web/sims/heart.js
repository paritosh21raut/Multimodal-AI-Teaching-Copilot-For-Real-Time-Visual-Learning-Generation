// The human heart (simulation/templates/heart.py), a process scene (S3): a schematic front view (the patient's right
// on the viewer's left): right atrium / ventricle on the left, left atrium / ventricle on the right, the lungs above,
// the body below, the four vessels. The six steps of the blood's path are numbered on the vessels and valves; the
// current one is bold and its blood moves. The heart beats at the server's period: the atria contract, then the
// ventricles; the tricuspid / mitral valves close while the ventricles contract, the pulmonary / aortic valves open only
// then. Oxygen-poor blood (right side) and oxygen-rich blood (left side) have their own colours and arrows, and every
// part is named once the teacher names it.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Readout, shown } from "./draw.js";
import { Dots, Flow, PartLabel, StepBadge, StepTitle, currentStep, stepIndex } from "./process.js";

export const TWEEN = [];
export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

const RA = [322, 280, 244, 130], LA = [614, 280, 244, 130], RV = [322, 440, 244, 145], LV = [614, 440, 244, 145];
const LUNGS = [470, 92, 360, 68], BODY = [470, 620, 360, 60];
// the vessels and the passages inside the heart, one per step, in the blood's direction
const PATH = {
  ra: [[470, 650], [240, 650], [240, 345], [322, 345]],          // body -> right atrium (venae cavae)
  rv: [[444, 372], [444, 492]],                                   // right atrium -> right ventricle (tricuspid)
  lungs: [[566, 505], [590, 505], [590, 162]],                    // right ventricle -> lungs (pulmonary artery)
  la: [[830, 126], [950, 126], [950, 345], [858, 345]],           // lungs -> left atrium (pulmonary veins)
  lv: [[736, 372], [736, 492]],                                   // left atrium -> left ventricle (mitral)
  body: [[858, 520], [1010, 520], [1010, 650], [830, 650]],       // left ventricle -> body (aorta)
};
const OXY = { ra: "deoxy", rv: "deoxy", lungs: "deoxy", la: "oxy", lv: "oxy", body: "oxy" };
const BADGE = { ra: [240, 500], rv: [499, 425], lungs: [590, 236], la: [950, 236], lv: [791, 425], body: [1010, 590] };

// phase of the beat: 0..1 squeeze of the atria / ventricles (a smooth bump in their systole), the valves
function beat(d, t) {
  const T = d.period_s || 0.8, ta = d.atrial_s || 0.1, tv = d.ventricular_s || 0.3, u = ((t % T) + T) % T;
  const bump = (a, b) => (u >= a && u < b ? Math.sin((Math.PI * (u - a)) / (b - a)) : 0);
  const vsys = u >= ta && u < ta + tv;
  return { atria: bump(0, ta), ventricles: bump(ta, ta + tv), av: !vsys, semilunar: vsys };
}

function Chamber({ box, squeeze, side, id, cur }) {
  const [x, y, w, h] = box, k = 1 - 0.08 * squeeze, cx = x + w / 2, cy = y + h / 2;
  return html`<rect class=${`sim-chamber ${side}${cur ? " cur" : ""} sim-obstacle`} data-el="chambers" data-part=${id}
    x=${cx - (w * k) / 2} y=${cy - (h * k) / 2} width=${w * k} height=${h * k} rx="34" />`;
}

// a valve as two leaflets across the opening at (x, y); open: parted along the flow (dir: the flow's direction)
function Valve({ x, y, open, vertical, id }) {
  const s = 26, g = open ? 18 : 0;
  const lines = vertical  // a valve across a vertical passage (the flow goes down): leaflets left and right
    ? [[x - s, y, x - 2 - g * 0.2, y + g], [x + s, y, x + 2 + g * 0.2, y + g]]
    : [[x, y - s, x + g, y - 2 - g * 0.2], [x, y + s, x + g, y + 2 + g * 0.2]];
  return html`<g class=${"sim-valve" + (open ? " open" : "")} data-el="valves" data-valve=${id} data-open=${open ? 1 : 0}>
    ${lines.map(([a, b, c, e], i) => html`<line key=${i} x1=${a} y1=${b} x2=${c} y2=${e} />`)}</g>`;
}

export function scene({ sim, t }) {
  const d = sim.drive, cur = currentStep(sim, t), b = beat(d, t);
  const on = (id) => stepIndex(sim, id) === cur;
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (shown(sim, "lungs")) {
    const [x, y, w, h] = LUNGS;
    out.push(html`<rect key="lungs" class="sim-organ lungs sim-obstacle" data-el="lungs" x=${x} y=${y} width=${w} height=${h} rx="30" />`);
    out.push(html`<${PartLabel} key="lungsl" sim=${sim} id="lungs" x=${x + w / 2} y=${y + 46} cls="in-block" />`);
  }
  if (shown(sim, "body")) {
    const [x, y, w, h] = BODY;
    out.push(html`<rect key="body" class="sim-organ body sim-obstacle" data-el="body" x=${x} y=${y} width=${w} height=${h} rx="30" />`);
    out.push(html`<${PartLabel} key="bodyl" sim=${sim} id="body" x=${x + w / 2} y=${y + 44} cls="in-block" />`);
  }
  if (shown(sim, "vessels")) {
    for (const id of ["ra", "lungs", "la", "body"]) {
      out.push(html`<${Flow} key=${"v" + id} pts=${PATH[id]} t=${t} on=${on(id)} role=${OXY[id]} id="vessels" />`);
    }
  }
  if (shown(sim, "chambers")) {
    out.push(html`<${Chamber} key="ra" box=${RA} squeeze=${b.atria} side="right" id="ra" cur=${on("ra")} />`);
    out.push(html`<${Chamber} key="la" box=${LA} squeeze=${b.atria} side="left" id="la" cur=${on("la")} />`);
    out.push(html`<${Chamber} key="rv" box=${RV} squeeze=${b.ventricles} side="right" id="rv" cur=${on("rv") || on("lungs")} />`);
    out.push(html`<${Chamber} key="lv" box=${LV} squeeze=${b.ventricles} side="left" id="lv" cur=${on("lv") || on("body")} />`);
    out.push(html`<${Flow} key="prv" pts=${PATH.rv} t=${t} on=${on("rv")} role="deoxy" id="chambers" />`);
    out.push(html`<${Flow} key="plv" pts=${PATH.lv} t=${t} on=${on("lv")} role="oxy" id="chambers" />`);
    for (const [id, box] of [["ra", RA], ["la", LA], ["rv", RV], ["lv", LV]]) {
      out.push(html`<${PartLabel} key=${id + "l"} sim=${sim} id=${id} x=${box[0] + box[2] / 2} y=${box[1] + (id[1] === "a" ? 50 : box[3] - 32)} cls="in-block" />`);
    }
  }
  if (shown(sim, "valves")) {
    out.push(html`<${Valve} key="tri" x=${444} y=${425} open=${b.av} vertical id="tricuspid" />`);
    out.push(html`<${Valve} key="mit" x=${736} y=${425} open=${b.av} vertical id="mitral" />`);
    out.push(html`<${Valve} key="pul" x=${574} y=${505} open=${b.semilunar} id="pulmonary" />`);
    out.push(html`<${Valve} key="aor" x=${872} y=${520} open=${b.semilunar} id="aortic" />`);
  }
  if (shown(sim, "blood")) {  // the blood moves round the whole circuit; the current step's faster and bigger
    for (const id of Object.keys(PATH)) {
      out.push(html`<${Dots} key=${"d" + id} pts=${PATH[id]} t=${t} n=${on(id) ? 5 : 3} speed=${on(id) ? 0.5 : 0.2}
        r=${on(id) ? 10 : 7} cls=${"sim-dot r-" + OXY[id]} />`);
    }
  }
  for (const id of Object.keys(BADGE)) {
    const [x, y] = BADGE[id];
    // the number only: a heart step's name is long ("Right atrium → right ventricle (tricuspid valve)"), it prints
    // in the heading once said
    out.push(html`<${StepBadge} key=${"b" + id} sim=${{ ...sim, steps: sim.steps.map((s) => ({ ...s, label: "" })) }}
      id=${id} x=${x - 26} y=${y} cur=${cur} />`);
  }
  if (shown(sim, "vessels")) {
    out.push(html`<${PartLabel} key="vcl" sim=${sim} id="vena_cava" x=${226} y=${470} anchor="end" />`);
    out.push(html`<${PartLabel} key="pal" sim=${sim} id="pulmonary_artery" x=${624} y=${212} anchor="start" />`);
    out.push(html`<${PartLabel} key="pvl" sim=${sim} id="pulmonary_veins" x=${916} y=${264} anchor="end" />`);
    out.push(html`<${PartLabel} key="aol" sim=${sim} id="aorta" x=${994} y=${562} anchor="end" />`);
  }
  if (shown(sim, "readout")) {
    // the said heart rate heads the card (plain), then what is computed from it (T, cardiac output)
    const lb = sim.labels && sim.labels.rate;
    const said = lb && lb.text ? [{ id: "rate", symbol: "HR", text: lb.text }] : [];
    out.push(html`<${Readout} key="readout" sim=${sim} x=${34} y=${76} fixed said=${said} minW=${300} />`);
  }
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
