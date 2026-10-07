// Slide export page (F-010): copilot.materials.render calls window.showSlide(spec, theme) for every slide of a PPTX.
// The slide is drawn by the same renderer as the projector, at 1920x1080, then measured and photographed.
import { html, render } from "../vendor/htm-preact-standalone.mjs";
import { Slide } from "../shared/slide.js";

const root = document.getElementById("root");
const frame = () => new Promise((r) => requestAnimationFrame(() => r()));

window.showSlide = async (spec, theme) => {
  document.documentElement.dataset.theme = theme;
  render(null, root);
  render(html`<div class="stage"><${Slide} key=${spec.id} spec=${spec} /></div>`, root);
  await document.fonts.ready;
  await Promise.all([...root.querySelectorAll("img")].map((img) => (img.complete ? 0
    : new Promise((r) => { img.addEventListener("load", r, { once: true }); img.addEventListener("error", r, { once: true }); }))));
  for (let i = 0; i < 8; i++) await frame();  // auto-fit measures and settles over a few frames
  await new Promise((r) => setTimeout(r, 250));
  return true;
};
window.__ready = true;
