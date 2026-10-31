// The explainer stage on a slide (F-017 E3): a slide's `stage` block -> web/stage/ Stage, playing block.patch.
// One stage per block id, kept across the slide's re-renders; a new patch.rev restarts the stage clock (the patch's
// tracks start at t = 0) and the camera eases from where it was. still: the scene ended, the last frame is the
// slide's figure (drawn once at the patch's middle keyframe, no clock). The browser draws; it decides nothing.
import { html, useEffect, useRef } from '../vendor/htm-preact-standalone.mjs';
import { mountStage } from './stage.js';

const now = () => performance.now() / 1000;
const reduced = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
export const stillT = (p) => ((p && p.keyframes && p.keyframes.length) ? p.keyframes[Math.floor(p.keyframes.length / 2)] : 0);

export function StageView({ b, onClick }) {
  const host = useRef(null);
  const st = useRef({ stage: null, rev: -1, at: 0, gone: false, b: null });
  const s = st.current;
  s.b = b;

  const show = () => {
    const blk = s.b, stage = s.stage;
    if (!stage || !blk || !blk.patch || !blk.patch.entities) return;
    if (!blk.patch.entities.length) { stage.stop(); s.rev = -1; return; }  // all undone: "Listening…" over a hidden stage
    const rev = blk.patch.rev || 0;
    if (rev !== s.rev) { s.rev = rev; s.at = now(); stage.still = !!blk.still; stage.apply(blk.patch); }
    if (blk.still) { stage.stop(); stage.render(stillT(blk.patch)); return; }
    if (reduced()) { stage.stop(); stage.render(Math.floor((now() - s.at) * 2) / 2); return; }
    if (!stage.raf) stage.play(() => now() - s.at);
  };

  useEffect(() => {
    s.gone = false;
    mountStage(host.current).then((stage) => {
      if (s.gone) { stage.destroy(); return; }
      s.stage = stage;
      show();
    });
    return () => { s.gone = true; if (s.stage) s.stage.destroy(); s.stage = null; s.rev = -1; };
  }, []);
  useEffect(show, [b.patch && b.patch.rev, b.still]);

  const empty = !b.patch || !(b.patch.entities || []).length;
  return html`<div class=${'stage-view' + (b.still ? ' still' : '') + (b.frozen ? ' frozen' : '')} data-stage=${b.id}
    data-rev=${b.patch ? b.patch.rev || 0 : 0} onClick=${onClick}>
    <div class="stage-host" ref=${host} style=${empty ? 'visibility:hidden' : ''}></div>
    ${empty && !b.still && html`<div class="stage-listening"><span></span>Listening…</div>`}
  </div>`;
}
