// /control — the teacher's laptop view: live preview, deck, controls, transcript, status.
// It never changes state itself; every action is a command sent to the server.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import {
  Glass, Slide, ZoomedImage, editableText, imageOf, partLabel, shownTitle, useGlassExit, useStageScale,
} from "../shared/slide.js";
import { connect, initialState, reduce } from "../shared/ws.js";

const KEYS = {
  ArrowRight: ["next"], ArrowLeft: ["prev"],
  b: ["blank", "unblank", "blank"],  // (Pin removed, user 2026-10-06)
  n: ["force_new_slide"],
};

// Pause (replaces Freeze, user 2026-10-06): a break in the lecture. What is said while paused is not put on slides;
// the teacher can still navigate and edit. It is the lecture's state (lifecycle), not a display flag.
const canPause = (lifecycle) => lifecycle === "live" || lifecycle === "paused";
const pauseCommand = (lifecycle) => (lifecycle === "paused" ? "resume" : "pause");

// ---- images (F-007b): the teacher's own image (drag & drop / Add image), Change image, Remove image ----
const UPLOAD_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const UPLOAD_MAX_MB = 10;
const hasFiles = (e) => e.dataTransfer && [...e.dataTransfer.types].includes("Files");

// Upload the file (the server stores a re-encoded copy), then ask the server to put it on the slide.
async function placeImage(file, slideId, send) {
  if (!UPLOAD_TYPES.includes(file.type)) throw new Error("Use a JPEG, PNG, WebP or GIF image");
  if (file.size > UPLOAD_MAX_MB * 1024 * 1024) throw new Error(`The image is larger than ${UPLOAD_MAX_MB} MB`);
  const r = await fetch("/api/upload", {
    method: "POST", body: file, headers: { "Content-Type": file.type, "X-File-Name": encodeURIComponent(file.name).slice(0, 120) },
  });
  const res = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(res.error || `Upload failed (${r.status})`);
  send("set_image", { slide_id: slideId, image_id: res.image_id, aspect: res.aspect, alt: res.alt });
}

// While a file is dragged over the slide: the slide as it will look, with the image's place drawn as a drop zone.
const withGhost = (spec, label) => ({
  ...spec,
  blocks: [...spec.blocks.filter((b) => b.type !== "image"),
    { type: "image", id: "ghost", url: "", alt: label, aspect: 4 / 3, ghost: true }],
});

const svg = (d, cls = "") => html`<svg class=${"ico " + cls} viewBox="0 0 24 24" aria-hidden="true"><path d=${d}
  fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
// Dark slides: a solid crescent with a small star (user 2026-10-07: the outline moon looked hollow)
const MOON = html`<svg class="ico moon" viewBox="0 0 24 24" aria-hidden="true">
  <path d="M20.4 14.6A8.6 8.6 0 0 1 9.4 3.6a8.9 8.9 0 1 0 11 11z" fill="currentColor"/>
  <path d="M17 3.2l.75 1.85 1.85.75-1.85.75L17 8.4l-.75-1.85-1.85-.75 1.85-.75z" fill="currentColor"/></svg>`;
const ICON = {
  back: "M19 12H5M11 18l-6-6 6-6",
  prev: "M15 18l-6-6 6-6",
  next: "M9 6l6 6-6 6",
  change: "M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4",
  upload: "M12 16V5M7 10l5-5 5 5M5 19h14",
  remove: "M6 6l12 12M18 6L6 18",
  add: "M12 5v14M5 12h14",
  find: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  pause: "M8.5 5v14M15.5 5v14",
  blank: "M3 5h18v12H3zM8 21h8M12 17v4M5 3l14 16",
  newSlide: "M4 5h16v14H4zM12 9v6M9 12h6",
  end: "M14 4h4a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-4M9 8l-4 4 4 4M5 12h11",  // leave (a stop square meant nothing)
  edit: "M4 20h4L19 9l-4-4L4 16v4zM13.5 6.5l4 4",
  bin: "M5 7h14M10 7V4h4v3M7 7l1 13h8l1-13M10 11v6M14 11v6",
  point: "M5 7h.01M9 7h10M5 12h.01M9 12h10M5 17h.01M9 17h6M19 15v6M16 18h6",
  share: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z",
  copy: "M9 9h11v11H9zM5 15H4V4h11v1",
  stop: "M6 6l12 12M18 6L6 18",
  chevron: "M6 9l6 6 6-6",
  sun: "M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4",
  materials: "M12 3l2.1 4.6L19 9.7l-4.9 2.1L12 16.4l-2.1-4.6L5 9.7l4.9-2.1zM19 15l.9 2.1 2.1.9-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z",
  lectures: "M4 5h16v4H4zM5 9v10h14V9M10 13h4",
  download: "M12 4v11M7 10l5 5 5-5M5 20h14",
  open: "M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5",
  slides: "M3 4h18v12H3zM8 20h8M12 16v4",
  pdf: "M7 3h7l5 5v13H7zM14 3v5h5",
  pptx: "M4 5h16v12H4zM8 21h8M9 9h3a2 2 0 0 1 0 4H9V9z",
  students: "M16 19v-1a4 4 0 0 0-8 0v1M12 11a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM20 19v-1a3 3 0 0 0-2-2.8M17 5.2a3 3 0 0 1 0 5.6",
  check: "M5 12l5 5 9-10",
  hide: "M3 3l18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.1A9.8 9.8 0 0 1 12 5c5 0 9 5 9 7a10 10 0 0 1-2.4 3.4M6.6 6.6C4.4 8 3 10.3 3 12c0 2 4 7 9 7a9.6 9.6 0 0 0 4.4-1.1",
  tree: "M4 5h6M4 5v14M4 12h6M4 19h6M14 5h6M14 12h6M14 19h6",
  notes: "M7 3h7l5 5v13H7zM14 3v5h5M10 13h6M10 17h4",
};

// The control page's own light / dark (F-009): a per-browser preference, separate from the slide theme
const CONTROL_THEME_KEY = "copilot.controlTheme";
function useControlTheme() {
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem(CONTROL_THEME_KEY) === "dark" ? "dark" : "light"; } catch (e) { return "light"; }
  });
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(CONTROL_THEME_KEY, theme); } catch (e) { /* private window: not remembered */ }
  }, [theme]);
  return [theme, () => setTheme(theme === "dark" ? "light" : "dark")];
}

// ---- live slide editing (F-008): hover an item of the preview → pencil / bin; the title → pencil; Add point ----
// Every change is a command; the server keeps the teacher's text final (the lecture never rewrites it).
// Round 5 (user 2026-10-06: the tools vanished on the way to them): they sit INSIDE the item's top-right corner, so
// the pointer never leaves the item to reach them; they stay HOVER_GRACE_MS after the pointer leaves; a double-click
// on an item (or the title) opens the editor directly.
const HOVER_GRACE_MS = 1000;
const TOOL_W = 32;  // one round tool button + padding (control.css .edit-tools)

function EditLayer({ host, spec, send, adding, onAdded }) {
  const [hover, setHover] = useState(null);  // {id, box, deleteOnly}
  const [edit, setEdit] = useState(null);    // {id, box, text}
  const area = useRef(null);
  const grace = useRef(null);
  const boxOf = (el) => {
    const p = host.current.getBoundingClientRect(), r = el.getBoundingClientRect();
    return { left: r.left - p.left, top: r.top - p.top, width: r.width, height: r.height };
  };
  const find = (id) => host.current && host.current.querySelector(`.stage [data-edit="${CSS.escape(id)}"]`);
  const hold = () => { clearTimeout(grace.current); grace.current = null; };
  const hideSoon = () => { if (!grace.current) grace.current = setTimeout(() => { grace.current = null; setHover(null); }, HOVER_GRACE_MS); };
  useEffect(() => () => clearTimeout(grace.current), []);
  useEffect(() => {
    const el = host.current;
    if (!el) return undefined;
    const move = (e) => {
      if (edit) return;
      if (e.target.closest(".edit-tools")) { hold(); return; }  // keep the tools while the pointer is on them
      const t = e.target.closest(".stage [data-edit]");
      if (!t) { hideSoon(); return; }
      hold();
      const id = t.dataset.edit;
      setHover((h) => (h && h.id === id ? h : { id, box: boxOf(t), deleteOnly: !!t.dataset.deleteOnly }));
    };
    const dbl = (e) => {
      if (edit) return;
      const t = e.target.closest(".stage [data-edit]");
      if (!t || t.dataset.deleteOnly) return;
      e.preventDefault();
      hold();
      start({ id: t.dataset.edit, box: boxOf(t) });
    };
    el.addEventListener("mousemove", move);
    el.addEventListener("mouseleave", hideSoon);
    el.addEventListener("dblclick", dbl);
    return () => {
      el.removeEventListener("mousemove", move); el.removeEventListener("mouseleave", hideSoon);
      el.removeEventListener("dblclick", dbl);
    };
  }, [edit, spec]);
  useEffect(() => { setHover(null); setEdit(null); }, [spec.id]);  // another slide: nothing stale
  useEffect(() => {  // the slide changed in place: follow the element, or forget it when it is gone
    if (hover) { const t = find(hover.id); setHover(t ? { ...hover, box: boxOf(t) } : null); }
  }, [spec]);
  useEffect(() => { if (adding) setEdit({ id: "__new", box: null, text: "" }); }, [adding]);
  useEffect(() => {
    if (!edit || !area.current) return;
    area.current.focus();
    if (edit.id !== "__new") area.current.select();
  }, [edit && edit.id]);

  const done = useRef(false);  // Enter, then the blur of the closing box: one command, not two
  const start = (h) => { done.current = false; setEdit({ id: h.id, box: h.box, text: editableText(spec, h.id) || "" }); setHover(null); };
  useEffect(() => { if (adding) done.current = false; }, [adding]);
  const close = () => { done.current = true; if (edit && edit.id === "__new") onAdded(); setEdit(null); };
  const save = () => {
    if (!edit || done.current) return;
    const text = edit.text.trim();
    if (edit.id === "__new") { if (text) send("add_point", { slide_id: spec.id, text }); }
    else if (text && text !== editableText(spec, edit.id)) send("edit_text", { slide_id: spec.id, item_id: edit.id, text });
    close();
  };
  const keys = (e) => {
    e.stopPropagation();  // Space, arrows and letters are text here, not lecture controls
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); save(); }
    else if (e.key === "Escape") { e.preventDefault(); close(); }
  };

  if (edit) {
    const b = edit.box;
    const style = b ? { left: `${b.left - 6}px`, top: `${b.top - 6}px`, width: `${Math.max(b.width + 12, 320)}px`,
      minHeight: `${Math.max(b.height + 12, 46)}px` } : null;
    return html`<div class=${"edit-box" + (b ? "" : " new")} style=${style}>
      <textarea ref=${area} value=${edit.text} rows=${b ? Math.max(1, Math.round(b.height / 30)) : 2}
        placeholder=${edit.id === "__new" ? "Type the new point" : ""}
        onInput=${(e) => setEdit({ ...edit, text: e.target.value })} onKeyDown=${keys} onBlur=${save}></textarea>
      <span class="edit-hint">${edit.id === "__new" ? "Enter adds the point" : "Enter saves"} · Esc cancels</span>
    </div>`;
  }
  if (!hover) return null;
  const b = hover.box;
  const tools = (hover.deleteOnly || hover.id === "title" ? 1 : 2) * TOOL_W;
  // inside the item, top right (vertically centred on a low item), never outside it
  const top = b.top + Math.max(2, Math.min(6, (b.height - TOOL_W) / 2));
  return html`
    <div class="edit-outline" style=${{ left: `${b.left - 4}px`, top: `${b.top - 4}px`, width: `${b.width + 8}px`, height: `${b.height + 8}px` }}></div>
    <div class="edit-tools" onMouseEnter=${hold} style=${{ left: `${Math.max(b.left + 2, b.left + b.width - tools - 6)}px`, top: `${top}px` }}>
      ${!hover.deleteOnly && html`<button class="icon" title="Edit (your text stays as you write it)" aria-label="Edit"
        onClick=${() => start(hover)}>${svg(ICON.edit)}</button>`}
      ${hover.id !== "title" && html`<button class="icon danger" title="Delete from the slide" aria-label="Delete"
        onClick=${() => { send("delete_item", { slide_id: spec.id, item_id: hover.id }); setHover(null); }}>${svg(ICON.bin)}</button>`}
    </div>`;
}

// Small status line on the preview (bottom left): searching, nothing found after Change, upload errors.
// `request` is what started the search: auto, or change (the teacher's Find image / Change).
function useStatus(status, notice, onNotice, hasImage) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {  // re-render when a short-lived message should disappear
    const t = setTimeout(() => setNow(Date.now()), 4200);
    return () => clearTimeout(t);
  }, [status, notice]);
  useEffect(() => { if (!notice) return; const t = setTimeout(() => onNotice(""), 6000); return () => clearTimeout(t); }, [notice]);
  if (notice) return { text: notice, error: true };
  const asked = status && status.request === "change";
  if (status && status.state === "searching") return { text: asked && hasImage ? "Finding another image…" : "Finding an image…", busy: true };
  if (status && status.state === "none" && asked && now - status.at < 4000) {
    return { text: hasImage ? "No other image found" : "No suitable image found" };
  }
  return null;
}

// The image controls float on the preview (bottom right): Find image / Add image when the slide has none;
// otherwise previous / next (images this slide has shown), Change, Upload, Remove.
function ImageBar({ spec, image, choices, status, send, onNotice }) {
  const input = useRef(null);
  const pick = async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try { await placeImage(file, spec.id, send); onNotice(""); } catch (err) { onNotice(err.message); }
  };
  const cmd = (kind) => () => { onNotice(""); send(kind, { slide_id: spec.id }); };
  const file = html`<input ref=${input} type="file" accept=${UPLOAD_TYPES.join(",")} hidden onChange=${pick} />`;
  const busy = status && status.state === "searching";
  if (!image) {
    return html`<div class="image-bar">
      ${file}
      <button class="add" onClick=${cmd("change_image")} disabled=${busy} title="Search for an image for this slide">
        ${svg(ICON.find, busy ? "pulse" : "")}Find image</button>
      <span class="sep"></span>
      <button onClick=${() => input.current.click()} title="Choose an image file for this slide">${svg(ICON.add)}Add image</button>
      <span class="or">or drop one</span>
    </div>`;
  }
  const many = choices && choices.count > 1;
  return html`<div class="image-bar">
    ${file}
    ${many && html`<div class="steps">
      <button class="icon" disabled=${choices.index <= 0} onClick=${cmd("image_prev")} title="Previous image">${svg(ICON.prev)}</button>
      <span class="count">${choices.index + 1} / ${choices.count}</span>
      <button class="icon" disabled=${choices.index >= choices.count - 1} onClick=${cmd("image_next")} title="Next image">${svg(ICON.next)}</button>
    </div><span class="sep"></span>`}
    <button onClick=${cmd("change_image")} disabled=${busy} title="Find a different image for this topic">${svg(ICON.change, busy ? "spin" : "")}Change</button>
    <button class="icon" onClick=${() => input.current.click()} title="Use an image file of your own">${svg(ICON.upload)}</button>
    <button class="icon" onClick=${cmd("remove_image")} title="Take the image off this slide">${svg(ICON.remove)}</button>
  </div>`;
}

function Preview({ spec, deck, lifecycle, slides, choices, status, send, notice, onNotice, adding, onAdded, theme }) {
  const ref = useRef(null);
  const scale = useStageScale(ref);
  const [drag, setDrag] = useState(null); // null | "over" | "uploading"
  const depth = useRef(0);
  const zoomed = deck && deck.zoom ? imageOf(slides[deck.zoom]) : null;
  const canDrop = spec && spec.layout !== "title" && !zoomed;
  const image = imageOf(spec);
  const line = useStatus(status, notice, onNotice, !!image);
  const drop = async (e) => {
    e.preventDefault();
    depth.current = 0;
    const file = e.dataTransfer.files && e.dataTransfer.files[0];
    if (!file || !canDrop) { setDrag(null); return; }
    setDrag("uploading");
    try { await placeImage(file, spec.id, send); onNotice(""); }
    catch (err) { onNotice(err.message); }
    finally { setDrag(null); }
  };
  const shown = drag && canDrop ? withGhost(spec, drag === "uploading" ? "Placing the image…" : "Drop to place the image here") : spec;
  // before the first slide the preview shows what the projector shows: the slide developing behind glass
  const glass = useGlassExit(!spec && !(deck && deck.blank), !!(deck && deck.blank));
  // the preview shows the slides in the projector's theme, whatever the control page's own theme is
  return html`<div class=${"preview" + (drag ? " dragging" : "")} ref=${ref} data-theme=${theme}
      onDragEnter=${(e) => { if (!hasFiles(e)) return; e.preventDefault(); depth.current += 1; if (drag !== "uploading") setDrag("over"); }}
      onDragOver=${(e) => { if (hasFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = canDrop ? "copy" : "none"; } }}
      onDragLeave=${() => { depth.current = Math.max(0, depth.current - 1); if (!depth.current && drag === "over") setDrag(null); }}
      onDrop=${drop}>
    <div class="stage" style=${{ transform: `translate(-50%, -50%) scale(${scale})` }}>
      ${shown ? html`<${Slide} key=${spec.id} spec=${shown}
        onImageClick=${drag ? undefined : () => send("zoom_image", { slide_id: spec.id })} />` : null}
      ${zoomed && html`<${ZoomedImage} key=${zoomed.image_id || zoomed.url} image=${zoomed} onClose=${() => send("unzoom_image")} />`}
      ${glass && html`<${Glass} leaving=${glass === "leaving"} />`}
    </div>
    ${spec && !zoomed && !drag && html`<${EditLayer} host=${ref} spec=${spec} send=${send} adding=${adding} onAdded=${onAdded} />`}
    ${zoomed && html`<button class="back" onClick=${() => send("unzoom_image")} title="Back to the slide (Esc)">
      ${svg(ICON.back)}<span>Back to slide</span><kbd>Esc</kbd></button>`}
    ${spec && spec.layout !== "title" && !zoomed && !drag && html`<${ImageBar} spec=${spec} image=${image}
      choices=${choices} status=${status} send=${send} onNotice=${onNotice} />`}
    ${line && !drag && html`<div class=${"image-status" + (line.error ? " error" : "")}>
      ${line.busy && html`<span class="dot"></span>`}${line.text}</div>`}
    ${(lifecycle === "paused" || (deck && deck.blank)) && !zoomed && html`<div class="flags">
      ${lifecycle === "paused" && html`<span class="flag paused">PAUSED</span>`}
      ${deck && deck.blank && html`<span class="flag warn">BLANK</span>`}
    </div>`}
  </div>`;
}

// Teacher controls under the preview.
const endLecture = (send) => () => confirm("End the lecture?") && send("end");

function Dock({ deck, lifecycle, send, toggle, canAdd, onAdd, theme }) {
  const dark = theme === "dark";
  const ids = deck ? deck.slide_ids : [];
  const at = deck ? ids.indexOf(deck.live_id) : -1;
  const paused = lifecycle === "paused";
  const flag =(name, on, off, key, icon, label, warn) => {
    const active = !!(deck && deck[name]);
    return html`<button class=${(active ? "on" : "") + (warn ? " warn" : "")} aria-pressed=${active}
      onClick=${toggle(on, off, name)} title=${`${label} (${key})`}>${svg(icon)}<span>${label}</span></button>`;
  };
  return html`<div class="dock">
    <div class="group">
      <button class="icon" onClick=${() => send("prev")} disabled=${at <= 0} title="Previous slide (←)">${svg(ICON.prev)}</button>
      <span class="count">${ids.length ? `${at + 1} / ${ids.length}` : "– / –"}</span>
      <button class="icon" onClick=${() => send("next")} disabled=${at < 0 || at >= ids.length - 1} title="Next slide (→)">${svg(ICON.next)}</button>
    </div>
    <div class="group">
      <button class=${"pause" + (paused ? " on" : "")} aria-pressed=${paused} disabled=${!canPause(lifecycle)}
        onClick=${() => send(pauseCommand(lifecycle))}
        title=${paused ? "Resume the lecture (Space)" : "Pause: what you say is not put on slides (Space)"}>
        ${svg(ICON.pause)}<span>${paused ? "Paused" : "Pause"}</span></button>
      ${flag("blank", "blank", "unblank", "B", ICON.blank, "Blank", true)}
      <button class="theme" onClick=${() => send("set_theme", { theme: dark ? "light" : "dark" })}
        title=${dark ? "Light slides on the projector (T)" : "Dark slides on the projector (T)"}>
        ${dark ? svg(ICON.sun) : MOON}<span>${dark ? "Light" : "Dark"}</span></button>
    </div>
    <div class="group">
      <button onClick=${() => send("force_new_slide")} title="Start a new slide (N)">${svg(ICON.newSlide)}<span>New slide</span></button>
      <button class="add-point" onClick=${onAdd} disabled=${!canAdd} title="Add a point of your own to this slide">
        ${svg(ICON.point)}<span>Add point</span></button>
    </div>
    <button class="end" onClick=${endLecture(send)} title="End the lecture">${svg(ICON.end)}<span>End lecture</span></button>
  </div>`;
}

function Meter({ audio }) {
  const db = audio ? 20 * Math.log10(Math.max(audio.rms, 1e-6)) : -120;
  const pct = Math.max(0, Math.min(100, ((db + 70) / 60) * 100));
  return html`<div class="meter" title=${`${db.toFixed(0)} dBFS`}>
    <div class=${"meter-fill" + (audio && audio.speaking ? " speaking" : "")} style=${{ width: `${pct}%` }}></div>
  </div>`;
}

// Factual, conceptual or formula mistakes (user 2026-10-06): the projector shows the correction when the model is
// confident, otherwise what the teacher said; the card says both and offers the one switch. Nothing to approve:
// the card can just be closed. Misheard words are corrected without a card (the server never sends them).
function Concerns({ concerns, send }) {
  if (!concerns.length) return null;
  const act = (id, action) => send("resolve_concern", { id, action });
  return html`<section class="concerns">
    <h2>Possible mistakes <span class="count">${concerns.length}</span></h2>
    ${concerns.map((c) => html`<article key=${c.id} class=${"concern" + (c.applied ? " fixed" : " as-said")}>
      <button class="close" onClick=${() => act(c.id, "dismiss")} title="Close this card" aria-label="Close">${svg(ICON.remove)}</button>
      <p class="said"><span>You said</span> “${c.claim}”</p>
      ${c.applied
        ? html`<p class="shows"><span>The slide shows</span> “${c.suggested_correction || c.right}”</p>`
        : html`<p class="shows"><span>The slide shows what you said</span></p>
               ${c.suggested_correction && html`<p class="fix"><span>Correct</span> ${c.suggested_correction}</p>`}`}
      ${c.issue && html`<p class="issue">${c.issue}</p>`}
      <div class="concern-actions">
        ${c.applied
          ? html`<button onClick=${() => act(c.id, "keep")} title="Put back what you said on the slide">Show what I said</button>
                 <button class="keep" onClick=${() => act(c.id, "dismiss")} title="The slide stays corrected; close this card">Keep correction</button>`
          : html`<button class="accept" disabled=${!c.suggested_correction} onClick=${() => act(c.id, "accept")}
                   title="Show the corrected version on the slide">Show correction</button>
                 <button class="keep" onClick=${() => act(c.id, "dismiss")} title="The slide stays as you said it; close this card">Keep what I said</button>`}
      </div>
    </article>`)}
  </section>`;
}

// ---- lecture structure (F-008): topic → facet → slides, from the deck; click a slide to show it ----
function outline(ids, slides) {
  const topics = [];
  ids.forEach((id, i) => {
    const s = slides[id];
    if (!s) return;
    const topic = s.layout === "title" ? s.title : s.subtitle || s.title;
    let t = topics[topics.length - 1];
    if (!t || t.name.toLowerCase() !== topic.toLowerCase()) topics.push((t = { name: topic, facets: [] }));
    const facet = s.layout === "title" ? "" : s.facet || "";
    let f = t.facets[t.facets.length - 1];
    if (!f || f.name.toLowerCase() !== facet.toLowerCase()) t.facets.push((f = { name: facet, slides: [] }));
    f.slides.push({ id, n: i + 1, title: shownTitle(s), part: s.part });
  });
  return topics;
}

function Structure({ deck, slides, send }) {
  const ids = deck ? deck.slide_ids : [];
  const live = deck && deck.live_id;
  const liveRef = useRef(null);
  useEffect(() => { liveRef.current && liveRef.current.scrollIntoView({ block: "nearest" }); }, [live]);
  const row = (s, label) => html`<li key=${s.id} ref=${s.id === live ? liveRef : null}
      class=${"slide-row" + (s.id === live ? " live" : "")} onClick=${() => send("goto", { slide_id: s.id })}
      title=${`Show slide ${s.n} on the display`}>
    <span class="n">${s.n}</span><span class="t">${label || s.title}</span>${s.part && html`<span class="part">${partLabel(s.part)}</span>`}
  </li>`;
  return html`<section class="structure">
    <h2>Lecture structure ${ids.length > 0 && html`<span class="muted">${ids.length} slide${ids.length > 1 ? "s" : ""}</span>`}</h2>
    ${!ids.length ? html`<p class="empty">The slides appear here as the lecture goes on.</p>` : html`<ol class="topics">
      ${outline(ids, slides).map((t, ti) => html`<li key=${ti} class="topic">
        <div class="topic-name">${t.name}</div>
        <ol class="facets">${t.facets.map((f, fi) => {
          // a facet with one slide of the same name is one row; otherwise the facet heads its slides
          const single = f.slides.length === 1 && (!f.name || f.slides[0].title.toLowerCase() === f.name.toLowerCase());
          return single ? row(f.slides[0]) : html`<li key=${fi} class="facet">
            ${f.name && html`<div class="facet-name">${f.name}</div>`}
            <ol class="slides">${f.slides.map((s) => row(s))}</ol>
          </li>`;
        })}</ol>
      </li>`)}
    </ol>`}
  </section>`;
}

// ---- the teacher's notes (F-009): their own PDF, page by page, beside the lecture; never on the projector ----
const NOTES_MAX_MB = 50;
const hasPdf = (e) => hasFiles(e);

async function uploadNotes(file, send) {
  if (file.type !== "application/pdf" && !/\.pdf$/i.test(file.name)) throw new Error("Use a PDF file");
  if (file.size > NOTES_MAX_MB * 1024 * 1024) throw new Error(`The PDF is larger than ${NOTES_MAX_MB} MB`);
  const r = await fetch("/api/notes", {
    method: "POST", body: file, headers: { "Content-Type": "application/pdf", "X-File-Name": encodeURIComponent(file.name).slice(0, 120) },
  });
  const res = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(res.error || `Upload failed (${r.status})`);
  send("notes_open", { id: res.id });
}

// A small menu in the app's style (no native select): a button, and a floating list under it.
function usePopover() {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const away = (e) => { if (ref.current && !ref.current.contains(e.target)) setOpen(false); };
    const esc = (e) => { if (e.key === "Escape") { e.stopPropagation(); setOpen(false); } };
    document.addEventListener("pointerdown", away);
    document.addEventListener("keydown", esc, true);
    return () => { document.removeEventListener("pointerdown", away); document.removeEventListener("keydown", esc, true); };
  }, [open]);
  return [open, setOpen, ref];
}

// The notes in use; the menu lists every PDF and adds another one (user 2026-10-07: the select was out of style).
function DocMenu({ docs, open, onOpen, onAdd, busy }) {
  const [shown, setShown, ref] = usePopover();
  return html`<div class="menu-wrap doc-menu" ref=${ref}>
    <button class=${"menu-button" + (shown ? " on" : "")} onClick=${() => setShown(!shown)} aria-expanded=${shown}
        title="Choose notes">
      ${svg(ICON.pdf)}<span class="label">${open.name}</span><em>${open.pages} p.</em>${svg(ICON.chevron, "chev")}</button>
    ${shown && html`<div class="menu" role="menu">
      ${docs.map((d) => html`<button key=${d.id} role="menuitem" class=${"menu-row" + (d.id === open.id ? " on" : "")}
          onClick=${() => { setShown(false); if (d.id !== open.id) onOpen(d.id); }}>
        ${svg(d.id === open.id ? ICON.check : ICON.pdf)}<span>${d.name}</span><em>${d.pages} p.</em></button>`)}
      <div class="menu-sep"></div>
      <button role="menuitem" class="menu-row add" disabled=${busy} onClick=${() => { setShown(false); onAdd(); }}>
        ${svg(ICON.add)}<span>Add PDF</span></button>
    </div>`}
  </div>`;
}

function Notes({ notes, send, wide, onWide }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const [loaded, setLoaded] = useState("");
  const n = notes || { docs: [], open: "", page: 0, pages: 0, follow: true, reason: "", matched: "" };
  const doc = n.docs.find((d) => d.id === n.open);
  const add = async (file) => {
    if (!file) return;
    setBusy(true); setError("");
    try { await uploadNotes(file, send); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const pick = (e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; add(f); };
  const drop = (e) => { e.preventDefault(); setOver(false); add(e.dataTransfer.files && e.dataTransfer.files[0]); };
  const src = doc ? `/api/notes/${doc.id}/page/${n.page}?w=${wide ? 1280 : 960}` : "";
  const img = useRef(null);
  // a page seen before comes from the browser cache, complete before its load listener exists: check after mount
  useEffect(() => { const el = img.current; if (el && el.complete && el.naturalWidth) setLoaded(src); }, [src]);
  const turn = (page) => send("notes_page", { page });
  const keys = (e) => {  // inside the notes, arrows turn its pages (not the slides)
    if (!doc) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); e.stopPropagation(); if (n.page < n.pages) turn(n.page + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); e.stopPropagation(); if (n.page > 1) turn(n.page - 1); }
  };
  const file = html`<input ref=${input} type="file" accept="application/pdf,.pdf" hidden onChange=${pick} />`;
  const addPdf = () => input.current.click();
  return html`<div class=${"notes" + (over ? " over" : "")} tabindex="0" onKeyDown=${keys}
      onDragOver=${(e) => { if (hasPdf(e)) { e.preventDefault(); setOver(true); } }}
      onDragLeave=${() => setOver(false)} onDrop=${drop}>
    ${file}
    ${!doc ? html`<div class="notes-empty">
        <div class="notes-art">${svg(ICON.notes)}</div>
        <button class="primary" onClick=${addPdf} disabled=${busy}>
          ${svg(ICON.add, busy ? "pulse" : "")}${busy ? "Adding…" : "Add PDF notes"}</button>
        <span class="or">or drop one here · only you see it</span>
        ${n.docs.length > 0 && html`<div class="notes-recent">${n.docs.map((d) => html`
          <button key=${d.id} class="doc-row" onClick=${() => send("notes_open", { id: d.id })}>
            ${svg(ICON.pdf)}<span>${d.name}</span><em>${d.pages} p.</em></button>`)}</div>`}
      </div>`
    : html`<div class="notes-head">
        <${DocMenu} docs=${n.docs} open=${doc} onOpen=${(id) => send("notes_open", { id })} onAdd=${addPdf} busy=${busy} />
        <button class="icon" onClick=${onWide} title=${wide ? "Narrower notes" : "Wider notes"} aria-pressed=${wide}>
          ${svg(wide ? "M9 4v16M4 9l5 3-5 3M20 9l-5 3 5 3" : "M4 4v16M20 4v16M9 12h6M9 12l2-2M9 12l2 2M15 12l-2-2M15 12l-2 2")}</button>
        <button class="icon" onClick=${() => confirm(`Remove “${doc.name}” from your notes?`) && send("notes_remove", { id: doc.id })}
          title="Remove these notes from the list">${svg(ICON.bin)}</button>
      </div>
      <div class="notes-page">
        <img key=${src} ref=${img} src=${src} alt=${`${doc.name}, page ${n.page}`} class=${loaded === src ? "loaded" : ""}
          onLoad=${(e) => { if (e.currentTarget === img.current) setLoaded(src); }} />
      </div>
      <div class="notes-foot">
        <div class="steps">
          <button class="icon" disabled=${n.page <= 1} onClick=${() => turn(n.page - 1)} title="Previous page">${svg(ICON.prev)}</button>
          <span class="count">${n.page} / ${n.pages}</span>
          <button class="icon" disabled=${n.page >= n.pages} onClick=${() => turn(n.page + 1)} title="Next page">${svg(ICON.next)}</button>
        </div>
        <label class=${"switch" + (n.follow ? " on" : "")} title="Open the page that matches the slide on screen">
          <input type="checkbox" checked=${n.follow} onChange=${(e) => send("notes_follow", { on: e.target.checked })} />
          <span class="track"><span class="knob"></span></span>Follow lecture</label>
      </div>
      <p class=${"notes-note" + (n.reason ? " off" : "")}>${n.reason || (n.follow
        ? (n.matched ? html`Matched to <b>${n.matched}</b>` : "Waiting for a slide that matches a page")
        : "Following is off: turn the pages yourself")}</p>`}
    ${error && html`<p class="notes-error">${error}</p>`}
  </div>`;
}

// ---- lecture materials (F-010): tick what to make, from this lecture and / or past ones; one Create ----
const KINDS = [
  { kind: "summary", icon: ICON.slides, label: "Summary slide", note: "Shown on the projector", llm: true },
  { kind: "concepts", icon: ICON.materials, label: "Key concepts slide", note: "Shown on the projector", llm: true },
  { kind: "notes", icon: ICON.pdf, label: "Notes", note: "PDF · explanations, slides, key concepts", llm: true, file: ".pdf" },
  { kind: "assignment", icon: ICON.edit, label: "Assignment", note: "PDF · theory questions", llm: true, file: ".pdf" },
  { kind: "pptx", icon: ICON.pptx, label: "Slides", note: "PowerPoint · as on the projector", file: ".pptx" },
];
const KIND = Object.fromEntries(KINDS.map((k) => [k.kind, k]));
const LABEL = { notes: "Notes", assignment: "Assignment", pptx: "Slides" };
const DEFAULT_QUESTIONS = 10;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const joinedTitle = (titles) => {
  const t = [...new Set(titles.filter(Boolean))];
  return !t.length ? "Lecture" : t.length <= 2 ? t.join(" + ") : `${t[0]} + ${t.length - 1} more`;
};
// the same rule as copilot.materials.store.auto_name: "Photosynthesis - Notes - 7 Oct 2026.pdf"
const autoName = (kind, title) => {
  const d = new Date();
  return `${title.replace(/[\\/:*?"<>|]+/g, " ")} - ${LABEL[kind]} - ${d.getDate()} ${MONTHS[d.getMonth()]} ${d.getFullYear()}${KIND[kind].file}`;
};
const ago = (t) => {
  const s = Math.max(0, Date.now() / 1000 - t);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  const d = new Date(t * 1000);
  return `${d.getDate()} ${MONTHS[d.getMonth()]}`;
};
const fileUrl = (m, inline) => `/api/materials/${m.id}/file${inline ? "?inline=1" : ""}`;

// The past lectures (GET /api/lectures), loaded when a tab needs them, again when the list changed.
function useLectures(active, version) {
  const [list, setList] = useState(null);
  useEffect(() => {
    if (!active) return undefined;
    let gone = false;
    fetch("/api/lectures", { cache: "no-store" }).then((r) => r.json())
      .then((res) => { if (!gone) setList(res.lectures || []); }).catch(() => { if (!gone) setList([]); });
    return () => { gone = true; };
  }, [active, version]);
  return list;
}

function Segmented({ value, options, onChange }) {
  return html`<div class="segmented" role="radiogroup">${options.map(([v, label]) => html`<button key=${v}
    role="radio" aria-checked=${value === v} class=${value === v ? "on" : ""} onClick=${() => onChange(v)}>${label}</button>`)}</div>`;
}

function PastPicker({ lectures, picked, onToggle }) {
  const [shown, setShown, ref] = usePopover();
  return html`<div class="menu-wrap" ref=${ref}>
    <button class=${"chip add" + (shown ? " on" : "")} onClick=${() => setShown(!shown)} aria-expanded=${shown}>
      ${svg(ICON.add)}Past lecture</button>
    ${shown && html`<div class="menu wide" role="menu">
      ${lectures === null ? html`<p class="menu-empty">Loading…</p>`
        : !lectures.length ? html`<p class="menu-empty">No past lectures yet</p>`
        : lectures.map((l) => html`<button key=${l.id} role="menuitemcheckbox" aria-checked=${picked.includes(l.id)}
            class=${"menu-row" + (picked.includes(l.id) ? " on" : "")} onClick=${() => onToggle(l.id)}>
          ${svg(picked.includes(l.id) ? ICON.check : ICON.lectures)}<span>${l.title}</span><em>${l.date.split(",")[0]}</em></button>`)}
    </div>`}
  </div>`;
}

function MadeRow({ m, send }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(m.name);
  const k = KIND[m.kind] || {};
  const save = () => { setEditing(false); if (name.trim() && name.trim() !== m.name) send("materials_rename", { id: m.id, name: name.trim() }); };
  const pdf = k.file === ".pdf";
  const meta = m.status === "working" ? (m.detail || "working") : m.status === "failed" ? m.detail
    : [ago(m.created), m.kind === "assignment" ? `${m.count} questions` : m.kind === "pptx" ? `${m.count} slides` : "",
      m.tokens ? `${(m.tokens / 1000).toFixed(1)}k tokens` : "", m.detail].filter(Boolean).join(" · ");
  return html`<li class=${"made " + m.status}>
    <span class="made-icon">${m.status === "working" ? html`<span class="spinner"></span>` : svg(k.icon || ICON.pdf)}</span>
    <div class="made-main">
      ${editing
        ? html`<input class="rename" value=${name} onInput=${(e) => setName(e.target.value)} onBlur=${save}
            ref=${(el) => el && !el.dataset.f && (el.dataset.f = "1", el.focus(), el.select())}
            onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter") save(); if (e.key === "Escape") { setName(m.name); setEditing(false); } }} />`
        : html`<span class="made-name" title=${m.name}>${m.name}</span>`}
      <span class="made-meta" title=${meta}>${meta}</span>
    </div>
    <div class="made-actions">
      ${m.status === "ready" && m.slide_ids && m.slide_ids.length > 0 && html`<button class="icon" title="Show on the projector"
        onClick=${() => send("materials_show", { id: m.id })}>${svg(ICON.slides)}</button>`}
      ${m.status === "ready" && pdf && html`<a class="icon" href=${fileUrl(m, true)} target="_blank" rel="noopener" title="Open">${svg(ICON.open)}</a>`}
      ${m.status === "ready" && m.has_file && html`<a class="icon" href=${fileUrl(m)} download=${m.name} title="Download">${svg(ICON.download)}</a>`}
      ${m.status === "ready" && pdf && html`<button class=${"icon" + (m.shared ? " on" : "")} aria-pressed=${m.shared}
        title=${m.shared ? "Students can download it from the shared link (click to stop)" : "Let students download it from the shared link"}
        onClick=${() => send("materials_share", { id: m.id, on: !m.shared })}>${svg(ICON.students)}</button>`}
      ${m.status !== "working" && m.has_file && html`<button class="icon" title="Rename" onClick=${() => { setName(m.name); setEditing(true); }}>${svg(ICON.edit)}</button>`}
      ${m.status !== "working" && html`<button class="icon danger" title="Delete"
        onClick=${() => confirm(`Delete “${m.name}”?`) && send("materials_remove", { id: m.id })}>${svg(ICON.bin)}</button>`}
    </div>
  </li>`;
}

function Materials({ materials, lectures, send, preselect, onPreselected }) {
  const st = materials || { items: [], current: { id: "", title: "" }, llm: false };
  const [ticks, setTicks] = useState({});
  const [opts, setOpts] = useState({ scope: "topic", count: DEFAULT_QUESTIONS, theme: "light" });
  const [names, setNames] = useState({});
  const [current, setCurrent] = useState(true);
  const [past, setPast] = useState([]);
  useEffect(() => {  // "Make materials" in a past lecture: that lecture alone
    if (!preselect) return;
    setPast([preselect]); setCurrent(false); onPreselected();
  }, [preselect]);
  const titles = [...(current ? [st.current.title || "This lecture"] : []),
    ...past.map((id) => ((lectures || []).find((l) => l.id === id) || {}).title || "Past lecture")];
  const title = joinedTitle(titles);
  const chosen = KINDS.filter((k) => ticks[k.kind]);
  const blocked = (k) => (k.llm && !st.llm) || (k.kind === "summary" && opts.scope === "topic" && !current);
  const ready = chosen.length > 0 && (current || past.length > 0) && !chosen.some(blocked);
  const create = () => {
    const items = chosen.map((k) => ({
      kind: k.kind, name: k.file ? (names[k.kind] || "").trim() || autoName(k.kind, title) : "",
      ...(k.kind === "summary" ? { scope: opts.scope } : {}),
      ...(k.kind === "assignment" ? { count: opts.count } : {}),
      ...(k.kind === "pptx" ? { theme: opts.theme } : {}),
    }));
    send("materials_create", { items, lectures: past, current });
    setTicks({}); setNames({});
  };
  const setCount = (n) => setOpts({ ...opts, count: Math.max(1, Math.min(30, n || DEFAULT_QUESTIONS)) });
  const option = (k) => {
    if (!ticks[k.kind]) return null;
    const name = k.file && html`<input class="name" value=${names[k.kind] || ""} placeholder=${autoName(k.kind, title)}
      title="File name (leave it to use the one shown)" onKeyDown=${(e) => e.stopPropagation()}
      onInput=${(e) => setNames({ ...names, [k.kind]: e.target.value })} />`;
    return html`<div class="kind-options">
      ${k.kind === "summary" && html`<${Segmented} value=${current ? opts.scope : "lecture"}
        options=${current ? [["topic", "This topic"], ["lecture", "Whole lecture"]] : [["lecture", "Whole lecture"]]}
        onChange=${(v) => setOpts({ ...opts, scope: v })} />`}
      ${k.kind === "assignment" && html`<div class="stepper" title="Number of questions">
        <button class="icon" onClick=${() => setCount(opts.count - 1)} disabled=${opts.count <= 1}>−</button>
        <input type="number" min="1" max="30" value=${opts.count} onKeyDown=${(e) => e.stopPropagation()}
          onChange=${(e) => setCount(parseInt(e.target.value, 10))} />
        <button class="icon" onClick=${() => setCount(opts.count + 1)} disabled=${opts.count >= 30}>+</button>
        <span>questions</span></div>`}
      ${k.kind === "pptx" && html`<${Segmented} value=${opts.theme} options=${[["light", "Light"], ["dark", "Dark"]]}
        onChange=${(v) => setOpts({ ...opts, theme: v })} />`}
      ${name}
    </div>`;
  };
  const items = st.items || [];
  return html`<div class="materials">
    <section class="make">
      <div class="from">
        <span class="from-label">From</span>
        <button class=${"chip" + (current ? " on" : "")} aria-pressed=${current} onClick=${() => setCurrent(!current)}
          title="This lecture, up to now">${current && svg(ICON.check)}This lecture</button>
        ${past.map((id) => html`<span key=${id} class="chip on">${((lectures || []).find((l) => l.id === id) || {}).title || "Past lecture"}
          <button class="x" title="Remove" onClick=${() => setPast(past.filter((x) => x !== id))}>${svg(ICON.remove)}</button></span>`)}
        <${PastPicker} lectures=${lectures} picked=${past}
          onToggle=${(id) => setPast(past.includes(id) ? past.filter((x) => x !== id) : [...past, id])} />
      </div>
      <ul class="kinds">${KINDS.map((k) => html`<li key=${k.kind} class=${"kind" + (ticks[k.kind] ? " on" : "") + (blocked(k) ? " off" : "")}>
        <button class="kind-head" role="checkbox" aria-checked=${!!ticks[k.kind]} disabled=${k.llm && !st.llm}
            title=${k.llm && !st.llm ? "Needs the LLM (this run has none)" : ""}
            onClick=${() => setTicks({ ...ticks, [k.kind]: !ticks[k.kind] })}>
          <span class="tick">${ticks[k.kind] && svg(ICON.check)}</span>
          <span class="kind-icon">${svg(k.icon)}</span>
          <span class="kind-text"><b>${k.label}</b><small>${k.note}</small></span>
        </button>
        ${option(k)}
      </li>`)}</ul>
      <div class="make-foot">
        <span class="make-note">${!st.llm ? "No LLM in this run: only the PowerPoint can be made"
          : chosen.some(blocked) ? "A topic summary needs this lecture" : `From ${title}`}</span>
        <button class="primary" disabled=${!ready} onClick=${create}>
          ${svg(ICON.materials)}Create${chosen.length > 1 ? ` ${chosen.length}` : ""}</button>
      </div>
    </section>
    <section class="made-list">
      <h3>Made${items.length ? html` <span>${items.length}</span>` : ""}</h3>
      ${!items.length ? html`<p class="made-empty">What you create appears here.</p>`
        : html`<ul>${items.map((m) => html`<${MadeRow} key=${m.id} m=${m} send=${send} />`)}</ul>`}
    </section>
  </div>`;
}

// ---- past lectures (F-010): the list; open one to page through its slides and its materials ----
function Lectures({ lectures, onOpen, send }) {
  if (lectures === null) return html`<div class="lectures"><p class="made-empty">Loading…</p></div>`;
  if (!lectures.length) return html`<div class="lectures"><p class="made-empty">Past lectures appear here.</p></div>`;
  return html`<div class="lectures"><ul>${lectures.map((l) => html`<li key=${l.id} class="lecture-row">
    <button class="lecture-open" onClick=${() => onOpen(l.id)} title="Open the slides of this lecture">
      <b>${l.title}</b>
      <small>${l.date} · ${l.slides} slide${l.slides === 1 ? "" : "s"} · ${Math.max(1, Math.round(l.minutes))} min
        ${l.simulated ? html` · <i>test run</i>` : ""}</small>
    </button>
    ${l.materials > 0 && html`<em class="badge" title="Materials made from it">${l.materials}</em>`}
    <button class="icon hide" title="Take it off this list (nothing is deleted)"
      onClick=${() => confirm(`Hide “${l.title}” (${l.date}) from the list?`) && send("lecture_hide", { id: l.id })}>${svg(ICON.hide)}</button>
  </li>`)}</ul></div>`;
}

function LectureViewer({ id, made, onClose, onMake, send }) {
  const [data, setData] = useState(null);
  const [at, setAt] = useState(0);
  const box = useRef(null);
  const root = useRef(null);
  const scale = useStageScale(box);
  useEffect(() => {
    let gone = false;
    fetch(`/api/lectures/${id}`, { cache: "no-store" }).then((r) => r.json())
      .then((res) => { if (!gone) setData(res); }).catch(() => { if (!gone) setData({ error: "Could not load it" }); });
    return () => { gone = true; };
  }, [id]);
  useEffect(() => { root.current && root.current.focus(); }, []);
  const slides = (data && data.slides) || [];
  const keys = (e) => {
    if (e.target.tagName === "INPUT") return;
    e.stopPropagation();  // arrows page through this lecture, not the live one
    if (e.key === "Escape") onClose();
    if (e.key === "ArrowRight") setAt((a) => Math.min(slides.length - 1, a + 1));
    if (e.key === "ArrowLeft") setAt((a) => Math.max(0, a - 1));
  };
  const spec = slides[at];
  const lec = data && data.lecture;
  return html`<div class="viewer-backdrop" onClick=${(e) => { if (e.target === e.currentTarget) onClose(); }}>
    <div class="viewer" ref=${root} tabindex="0" onKeyDown=${keys} role="dialog" aria-label="Past lecture">
      <header class="viewer-head">
        <div><h2>${lec ? lec.title : "Lecture"}</h2>${lec && html`<span>${lec.date} · ${slides.length} slides</span>`}</div>
        <span class="spacer"></span>
        ${lec && html`<button class="primary" onClick=${() => onMake(id)}>${svg(ICON.materials)}Make materials</button>`}
        <button class="icon close" onClick=${onClose} title="Close (Esc)">${svg(ICON.remove)}</button>
      </header>
      <div class="viewer-body">
        <div class="viewer-main">
          <div class="preview viewer-stage" ref=${box} data-theme=${lec && lec.theme ? lec.theme : "light"}>
            ${spec && html`<div class="stage" style=${{ transform: `translate(-50%, -50%) scale(${scale})` }}>
              <${Slide} key=${spec.id} spec=${spec} /></div>`}
            ${data && data.error && html`<p class="made-empty">${data.error}</p>`}
          </div>
          <div class="viewer-nav">
            <button class="icon" disabled=${at <= 0} onClick=${() => setAt(at - 1)} title="Previous slide (←)">${svg(ICON.prev)}</button>
            <span class="count">${slides.length ? `${at + 1} / ${slides.length}` : "–"}</span>
            <button class="icon" disabled=${at >= slides.length - 1} onClick=${() => setAt(at + 1)} title="Next slide (→)">${svg(ICON.next)}</button>
          </div>
        </div>
        <aside>
          <ol class="viewer-slides">${slides.map((s, i) => html`<li key=${s.id} class=${"slide-row" + (i === at ? " live" : "")}
            onClick=${() => setAt(i)}><span class="n">${i + 1}</span><span class="t">${shownTitle(s)}</span>
            ${s.part && html`<span class="part">${partLabel(s.part)}</span>`}</li>`)}</ol>
          ${made.length > 0 && html`<div class="viewer-made"><h3>Made from it</h3>
            <ul>${made.map((m) => html`<${MadeRow} key=${m.id} m=${m} send=${send} />`)}</ul></div>`}
        </aside>
      </div>
    </div>
  </div>`;
}

// the right column: mistake cards on top, then one card with tabs (more tabs come with the V2 tools)
function SidePanel({ tab, onTab, children }) {
  const tabs = children.filter(Boolean);
  return html`<section class="side-panel">
    <nav class="tabs" role="tablist">${tabs.map((t) => html`<button key=${t.props.id} role="tab" title=${t.props.label}
        class=${t.props.id === tab ? "on" : ""} aria-selected=${t.props.id === tab} onClick=${() => onTab(t.props.id)}>
      ${t.props.icon && svg(t.props.icon)}<span>${t.props.label}</span>${t.props.badge
        ? html`<em class="badge">${t.props.badge}</em>` : null}</button>`)}</nav>
    <div class="tab-body">${tabs.find((t) => t.props.id === tab) || tabs[0]}</div>
  </section>`;
}
const Tab = ({ children }) => children;

// ---- transcript (F-008): a strip at the bottom with the last line; click to read it all ----
function TranscriptStrip({ lines }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);
  useEffect(() => { const el = ref.current; if (el) el.scrollTop = el.scrollHeight; }, [lines.length, open]);
  const last = lines[lines.length - 1];
  const text = (l) => (l.dropped ? `(${l.dropped}) ${l.text || ""}` : l.text);
  return html`<footer class=${"transcript-strip" + (open ? " open" : "")}>
    <button class="strip-head" onClick=${() => setOpen(!open)} aria-expanded=${open}
        title=${open ? "Hide the transcript" : "Show the whole transcript"}>
      <h2>Transcript</h2>
      ${!open && html`<span class=${"last" + (last && last.dropped ? " dropped" : "")}>${last
        ? html`<span class="ts">${formatTime(last.t)}</span>${text(last)}` : "Nothing heard yet"}</span>`}
      ${svg(ICON.chevron, "chev")}
    </button>
    ${open && html`<div class="transcript" ref=${ref}>
      ${lines.map((l, i) => html`<p key=${i} class=${l.dropped ? "dropped" : ""}>
        <span class="ts">${formatTime(l.t)}</span>${text(l)}</p>`)}
    </div>`}
  </footer>`;
}

// ---- share with students (F-008): a Cloudflare quick tunnel to /view ----
function Share({ share, viewers, send }) {
  const [copied, setCopied] = useState(false);
  const copy = async () => {
    try { await navigator.clipboard.writeText(share.url); setCopied(true); setTimeout(() => setCopied(false), 1600); }
    catch (e) { window.prompt("Copy the link for the students:", share.url); }
  };
  if (share.state === "on") {
    return html`<div class="share on">
      <span class="dot"></span>
      <a class="link" href=${share.url} target="_blank" rel="noopener" title="The students open this link">${share.url.replace(/^https:\/\//, "")}</a>
      <button class="icon" onClick=${copy} title="Copy the link">${svg(copied ? "M5 12l5 5 9-10" : ICON.copy)}</button>
      <span class="viewers" title="Students watching now">${viewers} watching</span>
      <button class="icon" onClick=${() => send("share_stop")} title="Stop sharing">${svg(ICON.stop)}</button>
    </div>`;
  }
  const starting = share.state === "starting";
  return html`<div class="share">
    <button onClick=${() => send("share_start")} disabled=${starting}
        title="Make a link students can open on their own devices (view only)">
      ${svg(ICON.share, starting ? "pulse" : "")}<span>${starting ? share.detail || "Starting…" : "Share with students"}</span></button>
    ${share.state === "failed" && html`<span class="share-error" title=${share.detail}>Could not share: ${share.detail}</span>`}
  </div>`;
}

function App() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [notice, setNotice] = useState("");
  const [adding, setAdding] = useState(false);
  const conn = useRef(null);
  const send = (kind, args = {}) => conn.current && conn.current.send({ type: "command", kind, args });

  useEffect(() => {  // a file dropped next to the preview must not make the browser open it (and leave the page)
    const stop = (e) => { if (hasFiles(e)) e.preventDefault(); };
    window.addEventListener("dragover", stop);
    window.addEventListener("drop", stop);
    return () => { window.removeEventListener("dragover", stop); window.removeEventListener("drop", stop); };
  }, []);

  useEffect(() => {
    conn.current = connect("control", dispatch, (s) => dispatch({ type: "connection", connected: s === "connected" }));
    return () => conn.current.close();
  }, []);
  const [controlTheme, toggleControlTheme] = useControlTheme();
  const [tab, setTab] = useState("structure");
  const [wide, setWide] = useState(false);
  const [viewing, setViewing] = useState(null);      // a past lecture open in the viewer (F-010)
  const [preselect, setPreselect] = useState(null);  // "Make materials" from that lecture
  const materials = state.materials;
  const lectures = useLectures(tab === "materials" || tab === "lectures",
    `${materials ? materials.lectures_changed : 0}:${materials ? materials.items.length : 0}`);

  const deck = state.deck;
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "Escape") { if (deck && deck.zoom) { e.preventDefault(); send("unzoom_image"); } return; }
      if (e.key === " ") {
        e.preventDefault();  // also keeps Space from pressing the focused button a second time
        if (canPause(state.lifecycle)) send(pauseCommand(state.lifecycle));
        return;
      }
      if (e.key.toLowerCase() === "t") { e.preventDefault(); send("set_theme", { theme: state.theme === "dark" ? "light" : "dark" }); return; }
      const k = KEYS[e.key] || KEYS[e.key.toLowerCase()];
      if (!k) return;
      e.preventDefault();
      if (k.length === 3) send(deck && deck[k[2]] ? k[1] : k[0]);
      else send(k[0]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deck, state.lifecycle, state.theme]);

  const liveSpec = deck && deck.live_id ? state.slides[deck.live_id] : null;
  const toggle = (on, off, flag) => () => send(deck && deck[flag] ? off : on);
  useEffect(() => setAdding(false), [liveSpec && liveSpec.id]);

  return html`<div class="control">
    <header class="bar">
      <strong>Teaching Copilot</strong>
      <span class=${"pill " + state.lifecycle}>${state.lifecycle}</span>
      <span class=${"pill " + (state.connected ? "ok" : "bad")}>${state.connected ? "connected" : "offline"}</span>
      <${Meter} audio=${state.audio} />
      <span class="spacer"></span>
      <${Share} share=${state.share} viewers=${state.viewers} send=${send} />
      <a class="open-display" href="/display" target="classroom-display">Open classroom display ↗</a>
      <button class="icon page-theme" onClick=${toggleControlTheme} aria-label="Control view theme"
        title=${controlTheme === "dark" ? "Light control view (this page only)" : "Dark control view (this page only)"}>
        ${controlTheme === "dark" ? svg(ICON.sun) : MOON}</button>
    </header>
    <main class=${"grid" + (wide && tab === "notes" ? " notes-wide" : "")}>
      <section class="left">
        <${Preview} spec=${liveSpec} deck=${deck} lifecycle=${state.lifecycle} slides=${state.slides} send=${send} theme=${state.theme}
          notice=${notice} onNotice=${setNotice} adding=${adding} onAdded=${() => setAdding(false)}
          status=${liveSpec && state.images[liveSpec.id]} choices=${liveSpec && state.choices[liveSpec.id]} />
        <${Dock} deck=${deck} lifecycle=${state.lifecycle} send=${send} toggle=${toggle} theme=${state.theme}
          canAdd=${!!liveSpec && !(deck && deck.zoom)} onAdd=${() => setAdding(true)} />
        <p class="hint">Keys: ← → navigate · Space pause / resume · B blank · N new slide · T light / dark slides · hover or double-click a slide item to edit it</p>
      </section>
      <section class="right">
        <${Concerns} concerns=${state.concerns} send=${send} />
        <${SidePanel} tab=${tab} onTab=${setTab}>
          <${Tab} id="structure" label="Structure" icon=${ICON.tree} badge=${deck && deck.slide_ids.length ? deck.slide_ids.length : ""}>
            <${Structure} deck=${deck} slides=${state.slides} send=${send} />
          </${Tab}>
          <${Tab} id="notes" label="My notes" icon=${ICON.notes} badge=${state.notes && state.notes.open ? `p. ${state.notes.page}` : ""}>
            <${Notes} notes=${state.notes} send=${send} wide=${wide} onWide=${() => setWide(!wide)} />
          </${Tab}>
          <${Tab} id="materials" label="Materials" icon=${ICON.materials}
              badge=${materials && materials.items.some((m) => m.status === "working") ? "…" : ""}>
            <${Materials} materials=${materials} lectures=${lectures} send=${send}
              preselect=${preselect} onPreselected=${() => setPreselect(null)} />
          </${Tab}>
          <${Tab} id="lectures" label="Lectures" icon=${ICON.lectures}>
            <${Lectures} lectures=${lectures} onOpen=${setViewing} send=${send} />
          </${Tab}>
        </${SidePanel}>
      </section>
    </main>
    <${TranscriptStrip} lines=${state.transcript} />
    ${viewing && html`<${LectureViewer} id=${viewing} send=${send} onClose=${() => setViewing(null)}
      made=${(materials ? materials.items : []).filter((m) => m.lectures.includes(viewing))}
      onMake=${(id) => { setViewing(null); setPreselect(id); setTab("materials"); }} />`}
  </div>`;
}

function formatTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

render(html`<${App} />`, document.getElementById("root"));
