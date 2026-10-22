// Shortest-path routing, Dijkstra (simulation/templates/routing.py). The network at the left (nodes where the server
// put them, links with their costs), the distance table at the right, the readout (path, cost) under it. The steps
// are the server's: step k visits one node; its relaxations show on the links out of it (an improvement in the
// applied colour with "d + c = new", one that does not improve dashed), the table shows the distances after it (a
// changed one marked). The path step draws the path found and packets travelling along it. Every text is the server's.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Readout, shown } from "./draw.js";
import { Dots, StepTitle, currentStep } from "./process.js";

export const TWEEN = [];
const R = 30, TX = 750, TY = 140, ROW = 44;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

// the latest step <= cur that has rows of `kind` (the path step keeps the last visit's table)
const upTo = (evs, kind, cur) => {
  const ks = evs.filter((e) => e.kind === kind && e.step <= cur).map((e) => e.step);
  const k = ks.length ? Math.max(...ks) : null;
  return k === null ? [] : evs.filter((e) => e.kind === kind && e.step === k);
};

export function scene({ sim, t }) {
  const evs = sim.events || [], lb = sim.labels || {};
  const cur = currentStep(sim, t);
  const pos = Object.fromEntries(evs.filter((e) => e.kind === "node").map((e) => [e.a, [e.t, e.t2]]));
  const visited = new Set(evs.filter((e) => e.kind === "visit" && e.step <= cur && cur >= 0).map((e) => e.a));
  const now = evs.find((e) => e.kind === "visit" && e.step === cur);
  const relax = evs.filter((e) => e.kind === "relax" && e.step === cur);
  const pathEdges = evs.filter((e) => e.kind === "path" && cur >= 0 && e.step <= cur);
  const onPath = (a, b) => pathEdges.some((e) => (e.a === a && e.b === b) || (e.a === b && e.b === a));
  const out = [html`<${StepTitle} key="title" sim=${sim} cur=${cur} />`];
  if (shown(sim, "graph")) {
    for (const e of evs.filter((x) => x.kind === "edge")) {
      const [x1, y1] = pos[e.a], [x2, y2] = pos[e.b];
      const rx = relax.find((r) => (r.a === e.a && r.b === e.b) || (r.a === e.b && r.b === e.a));
      const cls = "sim-link" + (shown(sim, "path") && onPath(e.a, e.b) ? " path" : rx ? (rx.n ? " better" : " kept") : "");
      out.push(html`<line key=${"l" + e.a + e.b} class=${cls} data-el="graph" x1=${x1} y1=${y1} x2=${x2} y2=${y2} />`);
      if (shown(sim, "costs") && e.label) {
        const mx = (x1 + x2) / 2, my = (y1 + y2) / 2, k = Math.hypot(x2 - x1, y2 - y1) || 1;
        const nx = -(y2 - y1) / k, ny = (x2 - x1) / k, s = ny > 0 ? -1 : 1;  // the side above the link
        out.push(html`<g key=${"c" + e.a + e.b} class="sim-cost" data-el="costs">
          <circle cx=${mx + s * nx * 22} cy=${my + s * ny * 22} r="19" /><text x=${mx + s * nx * 22} y=${my + s * ny * 22 + 8} text-anchor="middle">${e.label}</text></g>`);
      }
    }
    for (const [n, [x, y]] of Object.entries(pos)) {
      const cls = "sim-node" + (visited.has(n) ? " visited" : "") + (now && now.a === n ? " cur" : "");
      out.push(html`<g key=${"n" + n} class=${cls} data-el="graph" data-node=${n}><circle cx=${x} cy=${y} r=${R} />
        <text x=${x} y=${y + 11} text-anchor="middle">${n}</text></g>`);
    }
    for (const [id, word] of [["source", "source"], ["target", "target"]]) {
      const l = lb[id];
      if (l && l.text && pos[l.text]) {
        const [x, y] = pos[l.text];
        out.push(html`<text key=${id} class="sim-note" x=${x} y=${y + R + 30} text-anchor="middle" data-el="graph">${word}</text>`);
      }
    }
  }
  if (shown(sim, "table")) {  // a relaxation's sum beside the neighbour it reached, the table at the right
    for (const r of relax) {
      const [x, y] = pos[r.b];
      const below = y > 400 && !["source", "target"].some((k) => lb[k] && lb[k].text === r.b);  // keep off the costs
      out.push(html`<text key=${"r" + r.b} class=${"sim-label " + (r.n ? "r-applied" : "r-component")} x=${x} y=${below ? y + R + 36 : y - R - 14}
        text-anchor="middle" data-el="table"><tspan class="val computed">${r.label}</tspan></text>`);
    }
    const rows = upTo(evs, "dist", cur);
    if (rows.length) {
      out.push(html`<g key="tbl" class="sim-table" data-el="table">
        <rect class="card" x=${TX - 20} y=${TY - 46} width="336" height=${ROW * rows.length + 64} rx="18" />
        <text class="head" x=${TX} y=${TY - 12}>node</text><text class="head" x=${TX + 200} y=${TY - 12} text-anchor="end">distance</text>
        <text class="head" x=${TX + 290} y=${TY - 12} text-anchor="end">via</text>
        ${rows.map((r, i) => html`<g key=${r.a} class=${"row" + (r.n ? " changed" : "") + (visited.has(r.a) ? " done" : "")}>
          <text x=${TX} y=${TY + 30 + i * ROW}>${r.a}</text>
          <text class="num" x=${TX + 200} y=${TY + 30 + i * ROW} text-anchor="end">${r.label}</text>
          <text class="num" x=${TX + 290} y=${TY + 30 + i * ROW} text-anchor="end">${r.b || "–"}</text></g>`)}
      </g>`);
    }
  }
  if (shown(sim, "packets") && pathEdges.length) {
    const pts = [pos[pathEdges[0].a], ...pathEdges.map((e) => pos[e.b])];
    out.push(html`<g key="pk" data-el="packets"><${Dots} pts=${pts} t=${t} n=${3} speed=${0.18} r=${11} cls="sim-packet" /></g>`);
  }
  // the path and its cost once the path step is reached: the readout never gives the answer ahead of the teacher
  const pathK = (sim.steps || []).findIndex((s) => s.id === "path");
  if (shown(sim, "readout") && pathK >= 0 && cur >= pathK) out.push(html`<${Readout} key="readout" sim=${sim} right fixed y=${560} minW=${300} />`);
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
