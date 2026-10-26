// The explainer stage (F-017): mounts a 1600 x 1000 SVG, one pane per view pane (split = two synced panes), and
// plays `stage.patch` messages through the Player. The clock is the caller's (the server clock in the app, so
// replays are deterministic); render(t) draws one frame, play(clock) runs the rAF loop.
import { loadMotion } from './motion.js';
import { setCast } from './people.js';
import { Player } from './player.js';
import { T, VH, VW } from './style.js';
import { el } from './svg.js';

const HERE = new URL('.', import.meta.url);
let CATALOG = null;

// motion pack, clip table, cast and catalog; urls default to the repo layout (web/stage/data, config/)
export async function loadStage({ motion, clips, cast, catalog } = {}) {
  if (CATALOG) return CATALOG;
  const cfg = (f) => new URL(`../../config/${f}`, HERE).href;
  const [, c, k] = await Promise.all([
    loadMotion(motion || new URL('data/motion.json', HERE).href, clips || cfg('stage_clips.json')),
    fetch(cast || cfg('stage_cast.json')).then((r) => r.json()),
    fetch(catalog || cfg('stage_catalog.json')).then((r) => r.json()),
  ]);
  setCast(c.cast);
  const by = (rows) => Object.fromEntries((rows || []).map((r) => [r.id, r]));
  CATALOG = { props: by(k.props), backdrops: by(k.backdrops), species: by(k.species), cast: c.cast };
  return CATALOG;
}
export const catalog = () => CATALOG;

export class Stage {
  constructor(host) {
    this.host = host;
    this.svg = el('svg', { viewBox: `0 0 ${VW} ${VH}`, class: 'stage-svg', preserveAspectRatio: 'xMidYMid meet',
      style: `display:block;width:100%;height:100%;background:${T.bg}` }, host);
    this.n = 0; this.player = null; this.raf = 0; this.lastT = 0;
    this.ro = typeof ResizeObserver !== 'undefined' ? new ResizeObserver(() => this.render(this.lastT)) : null;
    if (this.ro) this.ro.observe(host);
  }

  build(n) {
    this.svg.innerHTML = '';
    const w = VW / n, panes = [];
    for (let i = 0; i < n; i++) {
      const s = el('svg', { x: String(i * w), y: '0', width: String(w), height: String(VH), viewBox: `0 0 ${w} ${VH}`, overflow: 'hidden', class: 'stage-pane' }, this.svg);
      const bd = el('g', { class: 'st-bd' }, s), world = el('g', { class: 'st-world' }, s);
      panes.push({ svg: s, bd, world, far: el('g', { class: 'st-far' }, world), near: el('g', { class: 'st-near' }, world), over: el('g', { class: 'st-over' }, s), w });
    }
    for (let i = 1; i < n; i++) el('line', { x1: String(i * w), y1: '0', x2: String(i * w), y2: String(VH), stroke: '#ffffff', 'stroke-width': '4' }, this.svg);
    this.n = n;
    this.player = new Player(panes, CATALOG, el('g', { class: 'st-top' }, this.svg));
  }

  apply(patch) {
    const n = patch.view === 'split' ? (patch.panes || []).length || 1 : 1;
    if (n !== this.n || !this.player) this.build(n);
    this.player.still = !!this.still;  // a still (dev sheets): no ease from the last patch, no entrance fade
    this.player.apply(patch);
    return this;
  }

  render(t) { this.lastT = t; if (this.player) this.player.render(t); }

  // clock: () => stage seconds
  play(clock) {
    this.stop();
    const step = () => { this.render(clock()); this.raf = requestAnimationFrame(step); };
    step();
  }
  stop() { cancelAnimationFrame(this.raf); this.raf = 0; }
  destroy() { this.stop(); if (this.ro) this.ro.disconnect(); this.svg.remove(); }
}

export async function mountStage(host, opts = {}) {
  await loadStage(opts);
  return new Stage(host);
}
