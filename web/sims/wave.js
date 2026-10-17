// Travelling transverse wave (simulation/templates/wave.py): y(x, t) = A sin(2π (x/λ − f t)), to the right. Two
// wavelengths fill the string; one marked particle moves only up and down (the wave travels, the medium does not).
// A wave faster than the server's shown_f is drawn slowed down, and the stage says by how much.
import { html } from "../vendor/htm-preact-standalone.mjs";
import { Arrow, Caption, Label, Readout, clamp, shown } from "./draw.js";

export const TWEEN = [];
const X0 = 120, X1 = 1040, AXIS = 430, LPX = (X1 - X0) / 2, NPTS = 240, PARTICLE = X0 + LPX * 1.25;

export const motion = () => ({ a: 0, dir: 0, L: 1, rest: 0 });  // the scene keeps its own time

export function scene({ sim, t }) {
  const d = sim.drive, lb = sim.labels || {};
  // an amplitude never said is drawn at a plain middle height (no scale claim); a said one to scale where it fits
  const said = Boolean(lb.amplitude && lb.amplitude.text);
  const raw = said ? (d.A / d.lambda) * LPX : 70, apx = clamp(raw, 18, 120), scaled = !said || Math.abs(apx - raw) > 0.5;
  const ph = (x) => 2 * Math.PI * ((x - X0) / LPX - d.shown_f * t);
  const y = (x) => AXIS - apx * Math.sin(ph(x));
  const out = [];
  if (shown(sim, "axis")) {
    out.push(html`<line key="axis" class="sim-guide" data-el="axis" x1=${X0} y1=${AXIS} x2=${X1} y2=${AXIS} />`);
  }
  if (shown(sim, "amplitude")) {
    out.push(html`<g key="env" data-el="amplitude">
      <line class="sim-guide" x1=${X0} y1=${AXIS - apx} x2=${X1} y2=${AXIS - apx} />
      <line class="sim-guide" x1=${X0} y1=${AXIS + apx} x2=${X1} y2=${AXIS + apx} />
    </g>`);
    out.push(html`<${Arrow} key="amp" x1=${X0 - 40} y1=${AXIS} x2=${X0 - 40} y2=${AXIS - apx} role="component" id="amplitude" />`);
    out.push(html`<${Label} key="ampl" x=${X0 - 52} y=${AXIS - apx / 2 + 12} label=${lb.amplitude} anchor="end" fallback="A" id="amplitude" />`);
  }
  if (shown(sim, "wave")) {
    const pts = [];
    for (let i = 0; i <= NPTS; i++) {
      const x = X0 + ((X1 - X0) * i) / NPTS;
      pts.push(`${x.toFixed(1)},${y(x).toFixed(1)}`);
    }
    out.push(html`<polyline key="wave" class="sim-wave" data-el="wave" points=${pts.join(" ")} />`);
    out.push(html`<${Arrow} key="dir" x1=${X1 - 170} y1=${AXIS - apx - 70} x2=${X1 - 20} y2=${AXIS - apx - 70} role="applied" id="wave" />`);
    out.push(html`<${Label} key="fl" x=${X1 - 180} y=${AXIS - apx - 58} label=${lb.wave} anchor="end" fallback="f" id="wave" />`);
  }
  if (shown(sim, "particle")) {
    const py = y(PARTICLE);
    out.push(html`<g key="part" data-el="particle">
      <line class="sim-guide" x1=${PARTICLE} y1=${AXIS - apx - 14} x2=${PARTICLE} y2=${AXIS + apx + 14} />
      <circle class="sim-bob" cx=${PARTICLE} cy=${py} r="13" />
    </g>`);
  }
  if (shown(sim, "wavelength")) {  // one wavelength, crest to crest: the bracket moves with a crest (wave review)
    const ft = d.shown_f * t, by = AXIS + apx + 56, a = X0 + LPX * (0.25 + ft - Math.floor(ft)) % LPX, b = a + LPX;
    out.push(html`<g key="lam" data-el="wavelength">
      <line class="sim-guide solid" x1=${a} y1=${by} x2=${b} y2=${by} />
      <line class="sim-guide solid" x1=${a} y1=${by - 14} x2=${a} y2=${by + 14} />
      <line class="sim-guide solid" x1=${b} y1=${by - 14} x2=${b} y2=${by + 14} />
    </g>`);
    out.push(html`<${Label} key="laml" x=${(a + b) / 2} y=${by + 46} label=${lb.wavelength} anchor="middle" fallback="λ" id="wavelength" />`);
  }
  if (shown(sim, "readout")) out.push(html`<${Readout} key="readout" sim=${sim} />`);
  const notes = [];
  if (d.slowed > 1.01) notes.push(`shown ${d.slowed >= 10 ? Math.round(d.slowed) : d.slowed.toFixed(1)}× slower`);
  if (scaled) notes.push("height not to scale");
  out.push(html`<${Caption} key="cap" text=${sim.title} />`);
  if (notes.length) out.push(html`<text key="note" class="sim-caption" x="1066" y="712" text-anchor="end">${notes.join(" · ")}</text>`);
  return out;
}
