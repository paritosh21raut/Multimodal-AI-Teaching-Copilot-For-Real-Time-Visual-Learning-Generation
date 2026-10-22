// TCP (simulation/templates/tcp.py): the sender's and the receiver's time lines (time runs down), the server's event
// schedule drawn as it happens: the handshake, the segments (a lost one stops half way under a cross), the ACKs coming
// back, timeouts and fast retransmits at the sender; the sliding window over the segment row at the top (acknowledged
// ones filled, sent ones outlined, the window bracketed). The run plays drive.t_end delays in drive.stage_per_d stage
// seconds each, holds, and plays again. Every text is the server's (segment names, "ACK 3", the readout).
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Caption, Readout, W, shown } from "./draw.js";

export const TWEEN = [];
const SX = 170, RX = 560, YT = 168, YB = 676, STRIP = 14;  // the caption under YB

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

// the schedule's time (in one-way delays) at stage time t: the run, then a hold at its end
export function runTime(d, t) {
  const run = d.t_end * d.stage_per_d, cyc = run + d.hold_s;
  const tc = ((t % cyc) + cyc) % cyc;
  return Math.min(tc, run) / d.stage_per_d;
}

export function scene({ sim, t }) {
  const d = sim.drive, evs = sim.events || [], lb = sim.labels || {};
  const now = runTime(d, t);
  const T = d.t_end + 0.5, y = (tt) => YT + (tt / T) * (YB - YT);
  const out = [];
  out.push(html`<line key="sl" class="sim-timeline" x1=${SX} y1=${YT - 10} x2=${SX} y2=${YB} />`);
  out.push(html`<line key="rl" class="sim-timeline" x1=${RX} y1=${YT - 10} x2=${RX} y2=${YB} />`);
  out.push(html`<text key="sh" class="sim-label word" x=${SX} y=${YT - 26} text-anchor="middle">Sender</text>`);
  out.push(html`<text key="rh" class="sim-label word" x=${RX} y=${YT - 26} text-anchor="middle">Receiver</text>`);
  if (lb.protocol && lb.protocol.symbol) out.push(html`<text key="proto" class="sim-note" x=${(SX + RX) / 2} y=${YT - 26} text-anchor="middle">${lb.protocol.symbol}</text>`);
  const arrow = (e, i, cls, from, to, labelX, anchor) => {
    if (e.t > now) return null;
    const end = Math.min(e.t2, now, e.lost ? e.t + 0.5 * (e.t2 - e.t) : e.t2);
    const k = (end - e.t) / (e.t2 - e.t || 1), x2 = from + (to - from) * k, y1 = y(e.t), y2 = y1 + (y(e.t2) - y1) * k;
    return html`<g key=${e.kind + i} class=${"sim-msg " + cls + (e.lost ? " lost" : "")}>
      <line x1=${from} y1=${y1} x2=${x2} y2=${y2} />
      ${!e.lost && end < e.t2 && html`<circle cx=${x2} cy=${y2} r="7" />`}
      ${e.lost && end >= e.t + 0.5 * (e.t2 - e.t) && html`<text class="cross" x=${x2} y=${y2 + 11} text-anchor="middle">✕</text>`}
      <text class="tag" x=${labelX} y=${y1 + 7} text-anchor=${anchor}>${e.label}</text></g>`;
  };
  evs.forEach((e, i) => {
    if (["syn", "hsack"].includes(e.kind) && shown(sim, "handshake")) out.push(arrow(e, i, "hs", SX, RX, SX - 14, "end"));
    else if (e.kind === "synack" && shown(sim, "handshake")) out.push(arrow(e, i, "hs", RX, SX, RX + 14, "start"));
    else if (e.kind === "seg" && shown(sim, "data")) out.push(arrow(e, i, "seg", SX, RX, SX - 14, "end"));
    else if (e.kind === "ack" && shown(sim, "acks")) out.push(arrow(e, i, "ack", RX, SX, RX + 14, "start"));
    else if (["timeout", "fast"].includes(e.kind) && shown(sim, "timers") && e.t <= now) {
      out.push(html`<g key=${"to" + i} class="sim-timer"><line x1=${SX - 8} y1=${y(e.t)} x2=${SX + 8} y2=${y(e.t)} />
        <text x=${SX - 96} y=${y(e.t) + 7} text-anchor="end">${e.label}</text></g>`);
    }
  });
  if (shown(sim, "window")) {  // the segment row and the window over it, as at `now`
    const n = d.n, bw = Math.min(44, (RX - SX + 120) / n - 6), x0 = (SX + RX) / 2 - (n * (bw + 6) - 6) / 2;
    const bases = evs.filter((e) => e.kind === "base" && e.t <= now);
    const base = bases.length ? bases[bases.length - 1].n : 1;
    const sent = new Set(evs.filter((e) => e.kind === "seg" && e.t <= now).map((e) => e.n));
    const boxes = [];
    for (let s = 1; s <= n; s++) {
      const cls = s < base ? "acked" : sent.has(s) ? "sent" : "";
      boxes.push(html`<g key=${s} class=${"box " + cls}><rect x=${x0 + (s - 1) * (bw + 6)} y=${STRIP} width=${bw} height="40" rx="6" />
        <text x=${x0 + (s - 1) * (bw + 6) + bw / 2} y=${STRIP + 28} text-anchor="middle">${s}</text></g>`);
    }
    const wl = x0 + (Math.min(base, n + 1) - 1) * (bw + 6) - 4, wr = x0 + (Math.min(base + d.w, n + 1) - 1) * (bw + 6) - 2;
    out.push(html`<g key="strip" class="sim-strip" data-el="window">${boxes}
      ${base <= n && html`<rect class="win" x=${wl} y=${STRIP - 8} width=${Math.max(0, wr - wl)} height="56" rx="10" />`}</g>`);
  }
  if (shown(sim, "readout")) {
    const said = ["w", "n", "lost"].filter((k) => lb[k] && lb[k].text).map((k) => ({ id: k, symbol: lb[k].symbol, text: lb[k].text }));
    out.push(html`<${Readout} key="readout" sim=${sim} said=${said} right fixed y=${YT - 10} minW=${380} />`);
  }
  // the server's notes: the model's timing (whenever a time is printed), a lost segment that is not among those sent
  // (one line per clause of the server's text, right of the receiver: under the readout)
  const notes = [lb.assume, lb.note].filter((l) => l && l.symbol).flatMap((l) => l.symbol.split(", "));
  notes.forEach((s, i) => out.push(html`<text key=${"note" + i} class="sim-note" x=${W - 34} y=${560 + i * 42}
    text-anchor="end">${s}</text>`));
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  return out;
}
