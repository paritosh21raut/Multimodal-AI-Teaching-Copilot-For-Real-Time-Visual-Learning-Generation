// Story view (V3 ST1, docs/v3/ST1-story-core.md): plays a slide's `story` block (copilot/story/spec.py) on the whole
// 1920x1080 slide. The shown scene: its picture (or its noun's 3D emoji) under a slow camera (Ken Burns, one move per
// scene), crossfading from the scene before; who stands in it; their speech bubbles (the words type out, the speaker
// bobs while talking, the tail points at the speaker); the said caption; a strip of the scenes so far.
// The strip labels only the shown scene with its said time (test51: labels collided).
// ST2: each cast member's own colour (look-0..5); a scene with no said year / place shows the last said one, dimmed
// (a relative time like "years later" ends the old year); >= 2 said years: a timeline; >= 2 said places: a route;
// a talk of 3+ speakers shows its last 3 bubbles, stacked (2 lines each; the timeline / route step aside).
// still (the story ended / an export): the last frame, no motion. prefers-reduced-motion: no camera, no typing.
import { html, useEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";

const W = 1920;
const TYPE_MS = 32;          // a bubble's words type out at this pace
const SHOWN_BUBBLES = 2;     // the last two bubbles stay; the older one is dimmed (3 in a talk of 3+)
const STACK_PX = 170;        // a talk of 3+: each older bubble sits this much higher (stacked words: 2 lines max)
const isYear = (w) => /^\d{3,4}$/.test(w || "");
const reducedMotion = () => typeof matchMedia === "function" && matchMedia("(prefers-reduced-motion: reduce)").matches;

// x centres of n people standing across the stage
export function castXs(n) {
  if (n <= 0) return [];
  const gap = Math.min(560, 1500 / Math.max(1, n));
  return Array.from({ length: n }, (_, i) => W / 2 + (i - (n - 1) / 2) * gap);
}

// the chips of scene i: its said time / place, else the last said one (carried: dimmed)
export function chipsFor(scenes, i) {
  const out = { when: "", whenCarried: false, where: "", whereCarried: false };
  const sc = scenes[i] || {};
  if (sc.when) out.when = sc.when;
  else {
    for (let j = i - 1; j >= 0; j -= 1) {
      const w = scenes[j].when;
      if (!w) continue;
      if (isYear(w)) { out.when = w; out.whenCarried = true; }
      break;  // "years later": the old year is over
    }
  }
  if (sc.where) out.where = sc.where;
  else {
    for (let j = i - 1; j >= 0; j -= 1) {
      if (scenes[j].where) { out.where = scenes[j].where; out.whereCarried = true; break; }
      if (scenes[j].when && !isYear(scenes[j].when)) break;
    }
  }
  return out;
}

// the said years in order of first saying (>= 2: a timeline), with the scene index each one starts at
export function timelineOf(scenes) {
  const seen = new Map();
  scenes.forEach((s, k) => { if (isYear(s.when) && !seen.has(s.when)) seen.set(s.when, k); });
  return [...seen].map(([year, at]) => ({ year: Number(year), label: year, at }));
}

// the said places in order (the same place again is not repeated): >= 2 is a route
export function routeOf(scenes) {
  const out = [];
  const key = (w) => w.toLowerCase().replace(/^(the|a|an|its|his|her|their|our)\s+/, "");
  scenes.forEach((s, k) => {
    if (!s.where) return;
    const prev = out[out.length - 1];
    if (prev && key(prev.where) === key(s.where)) return;
    if (out.some((x) => key(x.where) === key(s.where))) { out.push({ where: s.where, at: k, again: true }); return; }
    out.push({ where: s.where, at: k });
  });
  return out;
}

function Timeline({ years, now }) {
  const lo = Math.min(...years.map((y) => y.year));
  const hi = Math.max(...years.map((y) => y.year));
  const pos = (y) => (hi === lo ? 50 : 4 + ((y - lo) / (hi - lo)) * 92);
  return html`<div class="story-timeline">
    <div class="tl-line"></div>
    ${years.map((y) => html`<span key=${y.label} class=${`tl-year${y.label === now ? " on" : ""}`}
      style=${{ left: `${pos(y.year)}%` }}><i></i><em>${y.label}</em></span>`)}
  </div>`;
}

function Route({ stops, now }) {
  return html`<div class="story-route">
    ${stops.map((r, k) => html`${k > 0 && html`<span class="route-arrow">→</span>`}<span key=${`${r.where}-${r.at}`}
      class=${`route-stop${r.where === now ? " on" : ""}`}>${r.where}</span>`)}
  </div>`;
}

function Backdrop({ sc, on, still }) {
  const cls = `story-back ${on ? "on" : "off"} cam-${sc.camera}${still ? " still" : ""}`;
  if (sc.image) {
    return html`<div class=${cls} data-scene=${sc.id}>
      <img class="story-img" src=${sc.image} alt=${sc.image_alt || sc.query} draggable="false" />
    </div>`;
  }
  return html`<div class=${`${cls} plain`} data-scene=${sc.id}>
    ${sc.emoji && html`<img class="story-emoji" src=${sc.emoji} alt=${sc.query} draggable="false" />`}
  </div>`;
}

function Typed({ text, still }) {
  const [n, setN] = useState(still || reducedMotion() ? text.length : 0);
  useEffect(() => {
    if (still || reducedMotion()) { setN(text.length); return undefined; }
    setN(0);
    let i = 0;
    const t = setInterval(() => {
      i += 1;
      setN(i);
      if (i >= text.length) clearInterval(t);
    }, TYPE_MS);
    return () => clearInterval(t);
  }, [text, still]);
  return html`<span class="typed">${text.slice(0, n)}</span><span class="typed-rest">${text.slice(n)}</span>`;
}

function Person({ c, x, talking }) {
  const initial = (c.name.replace(/^(a|an|the|one)\s+/i, "")[0] || "?").toUpperCase();
  return html`<div class=${`story-person look-${(c.look || 0) % 6}${talking ? " talking" : ""}`} data-cast=${c.id}
      data-gender=${c.gender || ""} style=${{ left: `${x}px` }}>
    <div class="story-face">
      ${c.picture ? html`<img src=${c.picture} alt=${c.name} draggable="false" />` : html`<span>${initial}</span>`}
    </div>
    <div class="story-name">${c.name}</div>
  </div>`;
}

function SpeechBubble({ bub, x, who, look, older, raised, level, stacked, still }) {
  const right = x < W / 2;  // a bubble opens away from the middle (two talkers' bubbles never cross): its tail end
  const style = right ? { right: `${W - x - 60}px` } : { left: `${x - 60}px` };
  if (level > 0) style.bottom = `${512 + level * STACK_PX}px`;
  return html`<div class=${`story-bubble look-${look % 6} kind-${bub.kind}${older ? " older" : ""}${raised ? " raised" : ""}${stacked ? " stacked" : ""}${right ? " from-right" : ""}${still ? " still" : ""}`}
      data-bubble=${bub.id} data-speaker=${bub.speaker} style=${style}>
    <div class="bubble-who">${who}</div>
    <div class="bubble-text"><${Typed} text=${bub.text} still=${still || older} /></div>
  </div>`;
}

export function StoryView({ b, onClick }) {
  const story = b.story || {};
  const scenes = story.scenes || [];
  const still = !!b.still;
  const i = Math.max(0, Math.min(scenes.length - 1, story.shown || 0));
  const sc = scenes[i];
  const prev = useRef({ id: "", before: null });
  if (sc && prev.current.id !== sc.id) prev.current = { id: sc.id, before: prev.current.id ? prev.current.last : null };
  if (sc) prev.current.last = sc;
  if (!sc) {
    return html`<div class="sim-stage story-stage empty" onClick=${onClick}><div class="story-wait">${story.title || "Story"}</div></div>`;
  }
  const cast = (sc.cast || []).map((id) => (story.cast || []).find((c) => c.id === id)).filter(Boolean);
  const xs = castXs(cast.length);
  const at = Object.fromEntries(cast.map((c, k) => [c.id, xs[k]]));
  const talkers = new Set((sc.bubbles || []).map((x) => x.speaker)).size;
  const bubbles = (sc.bubbles || []).slice(talkers >= 3 ? -3 : -SHOWN_BUBBLES);
  const stack = bubbles.length >= 3;
  const lastSpeaker = bubbles.length ? bubbles[bubbles.length - 1].speaker : "";
  const before = prev.current.before && prev.current.before.id !== sc.id ? prev.current.before : null;
  const ch = chipsFor(scenes, i);
  const chips = [ch.when && html`<span class=${`story-chip when${ch.whenCarried ? " carried" : ""}`}>${ch.when}</span>`,
                 ch.where && html`<span class=${`story-chip where${ch.whereCarried ? " carried" : ""}`}>${ch.where}</span>`]
    .filter(Boolean);
  const years = timelineOf(scenes);
  const stops = routeOf(scenes);
  return html`<div class=${`sim-stage story-stage${still ? " still" : ""}${cast.length ? " has-cast" : ""}`} onClick=${onClick} data-shown=${i}>
    ${before && !still && html`<${Backdrop} key=${`b-${before.id}`} sc=${before} on=${false} still=${still} />`}
    <${Backdrop} key=${sc.id} sc=${sc} on=${true} still=${still} />
    <div class="story-shade"></div>
    ${chips.length > 0 && html`<div class="story-chips">${chips}</div>`}
    ${!stack && stops.length >= 2 && html`<${Route} stops=${stops} now=${ch.where} />`}
    ${!stack && years.length >= 2 && html`<${Timeline} years=${years} now=${ch.when} />`}
    <div class="story-cast">
      ${cast.map((c) => html`<${Person} key=${c.id} c=${c} x=${at[c.id]} talking=${!still && c.id === lastSpeaker} />`)}
    </div>
    <div class="story-bubbles">
      ${bubbles.map((bub, k) => at[bub.speaker] !== undefined && html`<${SpeechBubble} key=${bub.id} bub=${bub}
        x=${at[bub.speaker]} who=${(cast.find((c) => c.id === bub.speaker) || {}).name || ""}
        look=${(cast.find((c) => c.id === bub.speaker) || {}).look || 0}
        level=${stack ? bubbles.length - 1 - k : 0} stacked=${stack}
        older=${k < bubbles.length - 1} raised=${!stack && k < bubbles.length - 1 && bub.speaker === lastSpeaker}
        still=${still} />`)}
    </div>
    ${sc.caption && html`<div class="story-caption" key=${`cap-${sc.id}-${sc.caption}`}>${sc.caption}</div>`}
    ${sc.credit && html`<div class="story-credit">${sc.credit}</div>`}
    <div class="story-strip">
      ${scenes.map((s, k) => html`<span key=${s.id} class=${`strip-dot${k === i ? " on" : ""}${k < i ? " past" : ""}`}>
        ${s.when && k === i ? html`<em>${s.when}</em>` : ""}</span>`)}
    </div>
  </div>`;
}
