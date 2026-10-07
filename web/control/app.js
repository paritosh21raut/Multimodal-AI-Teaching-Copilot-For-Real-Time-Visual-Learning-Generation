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
  // a stack of books (F-010b #15: the archive box read as a drawer)
  lectures: "M4 4h4v16H4zM8 4h4v16H8zM14.2 5.3l3.9-1 3.9 15.4-3.9 1zM4 8h8M4 16h8",
  word: "M7 3h7l5 5v13H7zM14 3v5h5M9.5 12l1.2 5 1.3-3.5 1.3 3.5 1.2-5",
  text: "M7 3h7l5 5v13H7zM14 3v5h5M10 12h6M10 15h6M10 18h4",
  image: "M4 5h16v14H4zM4 16l5-5 4 4 2-2 5 5M15.5 9.5a1 1 0 1 0 0-.01",
  web: "M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18zM3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z",
  link: "M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1",
  project: "M3 4h18v12H3zM8 20h8M12 16v4M10 8l4 2-4 2z",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  sortDown: "M7 4v16M3 16l4 4 4-4M14 6h7M14 11h5M14 16h3",
  sortUp: "M7 20V4M3 8l4-4 4 4M14 6h3M14 11h5M14 16h7",
  grip: "M9 6h.01M15 6h.01M9 12h.01M15 12h.01M9 18h.01M15 18h.01",
  folder: "M3 6a1 1 0 0 1 1-1h5l2 2h9a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1z",
  play: "M7 4.5v15l12-7.5z",
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

// ---- styled tooltip (F-010b #11): every `title` in /control shows in the app's style instead of the native box ----
// As soon as an element gets a title (render or update) the title becomes its aria-label (its accessible name, unless
// it has one) and data-tip, so the browser never shows a box of its own.
const TIP_DELAY_MS = 450;
function untitle(root) {
  const els = root.querySelectorAll ? [...(root.hasAttribute && root.hasAttribute("title") ? [root] : []), ...root.querySelectorAll("[title]")] : [];
  for (const el of els) {
    const t = el.getAttribute("title");
    el.removeAttribute("title");
    if (!t) continue;
    el.dataset.tip = t;
    if (!el.hasAttribute("aria-label") || el.dataset.tipLabel) { el.setAttribute("aria-label", t); el.dataset.tipLabel = "1"; }
  }
}
function Tooltip() {
  const [tip, setTip] = useState(null);  // {text, x, y, below}
  useEffect(() => {
    untitle(document.body);
    const watch = new MutationObserver((records) => {
      for (const r of records) untitle(r.target);  // a new title, or new elements under r.target
    });
    watch.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["title"] });
    return () => watch.disconnect();
  }, []);
  useEffect(() => {
    let timer = null, target = null;
    const hide = () => { clearTimeout(timer); timer = null; target = null; setTip(null); };
    const over = (e) => {
      const el = e.target.closest && e.target.closest("[data-tip]");
      if (el === target) return;
      hide();
      if (!el || !el.dataset.tip) return;
      target = el;
      timer = setTimeout(() => {
        if (!target || !target.isConnected) return;
        const r = target.getBoundingClientRect();
        const below = r.top < 64;
        setTip({ text: target.dataset.tip, x: r.left + r.width / 2, y: below ? r.bottom + 8 : r.top - 8, below });
      }, TIP_DELAY_MS);
    };
    document.addEventListener("pointerover", over);
    for (const ev of ["pointerdown", "keydown", "scroll", "blur"]) window.addEventListener(ev, hide, true);
    return () => {
      document.removeEventListener("pointerover", over);
      for (const ev of ["pointerdown", "keydown", "scroll", "blur"]) window.removeEventListener(ev, hide, true);
      clearTimeout(timer);
    };
  }, []);
  const ref = useRef(null);
  const [shift, setShift] = useState(0);
  useEffect(() => {  // keep it inside the window
    if (!tip || !ref.current) return;
    const r = ref.current.getBoundingClientRect();
    setShift(r.left < 8 ? 8 - r.left : r.right > innerWidth - 8 ? innerWidth - 8 - r.right : 0);
  }, [tip && tip.text, tip && tip.x]);
  if (!tip) return null;
  return html`<div ref=${ref} class=${"tooltip" + (tip.below ? " below" : "")} role="tooltip"
    style=${{ left: `${tip.x + shift}px`, top: `${tip.y}px` }}>${tip.text}</div>`;
}

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
      <button onClick=${() => input.current.click()} title="Choose an image file for this slide (or drop one on the slide)">${svg(ICON.add)}Add image</button>
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

// ---- before the lecture (F-010b §1): pick the chapter, then Start (no Enter in the terminal needed) ----
function StartCard({ lifecycle, materials, send }) {
  const chapters = (materials && materials.chapters) || [];
  const testRun = !!(materials && materials.current && materials.current.test_run);
  const [chosen, setChosen] = useState(null);       // null: not picked yet → the last one used
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const [shown, setShown, ref] = usePopover();
  const last = materials && chapters.some((c) => c.id === materials.last_chapter) ? materials.last_chapter : "";
  const pick = chosen === null ? last : chosen;
  const current = chapters.find((c) => c.id === pick);
  const ready = lifecycle === "ready";
  const [sent, setSent] = useState(false);  // Start pressed: no second press while the app goes live
  const start = () => {
    if (sent) return;
    setSent(true);
    if (naming && name.trim()) send("chapter_create", { name: name.trim(), start: true });
    else send("lecture_move", { id: "", chapter: pick, start: true });
    send("start");
  };
  return html`<div class="start-card" role="dialog" aria-label="Start the lecture">
    <h3>Ready to start</h3>
    <label class="start-label">Chapter</label>
    ${naming
      ? html`<div class="new-chapter">
          <span class="new-number">Chapter ${chapters.length + 1} ·</span>
          <input value=${name} placeholder="Name, e.g. Cell biology" maxlength="80"
            ref=${(el) => el && !el.dataset.f && (el.dataset.f = "1", el.focus())}
            onInput=${(e) => setName(e.target.value)}
            onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter" && ready) start(); if (e.key === "Escape") setNaming(false); }} />
          <button class="icon" onClick=${() => setNaming(false)} title="Back to the chapters">${svg(ICON.remove)}</button>
        </div>`
      : html`<div class="menu-wrap" ref=${ref}>
          <button class=${"menu-button" + (shown ? " on" : "")} onClick=${() => setShown(!shown)} aria-expanded=${shown}>
            ${svg(ICON.folder)}<span class="label">${current ? current.label : "No chapter (Unsorted)"}</span>${svg(ICON.chevron, "chev")}</button>
          ${shown && html`<div class="menu" role="menu">
            ${[...chapters].reverse().map((c) => html`<button key=${c.id} role="menuitem" class=${"menu-row" + (c.id === pick ? " on" : "")}
                onClick=${() => { setChosen(c.id); setShown(false); }}>
              ${svg(c.id === pick ? ICON.check : ICON.folder)}<span>${c.label}</span></button>`)}
            <button role="menuitem" class=${"menu-row" + (!pick ? " on" : "")} onClick=${() => { setChosen(""); setShown(false); }}>
              ${svg(!pick ? ICON.check : ICON.folder)}<span>No chapter (Unsorted)</span></button>
            <div class="menu-sep"></div>
            <button role="menuitem" class="menu-row add" onClick=${() => { setShown(false); setNaming(true); }}>
              ${svg(ICON.add)}<span>New chapter</span></button>
          </div>`}
        </div>`}
    ${testRun && html`<p class="start-note">Test run: it stays in Unsorted</p>`}
    <button class="primary start" onClick=${start} disabled=${!ready || sent || (naming && !name.trim())}>
      ${svg(ICON.play)}${sent ? "Starting…" : "Start lecture"}</button>
  </div>`;
}

// A page of the teacher's notes on the projector (F-010b §5): the preview shows it as the projector does.
function NotesOnScreen({ shown, send }) {
  if (!shown || !shown.on) return null;
  return html`<div class="notes-shown">
    <img src=${`/api/notes/shown/${shown.doc_id}/${shown.page}?w=1280`} alt=${`${shown.name}, page ${shown.page}`} />
  </div>
  <button class="back" onClick=${() => send("notes_project", { on: false })} title="Back to the slide (Esc)">
    ${svg(ICON.back)}<span>Back to slide</span><kbd>Esc</kbd></button>`;
}

function Preview({ spec, deck, lifecycle, slides, choices, status, send, notice, onNotice, adding, onAdded, theme,
                   materials, notesShown }) {
  const ref = useRef(null);
  const scale = useStageScale(ref);
  const [drag, setDrag] = useState(null); // null | "over" | "uploading"
  const depth = useRef(0);
  const onScreen = !!(notesShown && notesShown.on);  // a notes page covers the slide on the projector
  const zoomed = deck && deck.zoom && !onScreen ? imageOf(slides[deck.zoom]) : null;
  const before = lifecycle === "ready";  // waiting for Start (while models load the glass loader shows)
  const canDrop = spec && spec.layout !== "title" && !zoomed && !onScreen;
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
    ${spec && !zoomed && !drag && !onScreen && html`<${EditLayer} host=${ref} spec=${spec} send=${send} adding=${adding} onAdded=${onAdded} />`}
    ${zoomed && html`<button class="back" onClick=${() => send("unzoom_image")} title="Back to the slide (Esc)">
      ${svg(ICON.back)}<span>Back to slide</span><kbd>Esc</kbd></button>`}
    ${spec && spec.layout !== "title" && !zoomed && !drag && !onScreen && html`<${ImageBar} spec=${spec} image=${image}
      choices=${choices} status=${status} send=${send} onNotice=${onNotice} />`}
    <${NotesOnScreen} shown=${notesShown} send=${send} />
    ${before && html`<${StartCard} lifecycle=${lifecycle} materials=${materials} send=${send} />`}
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
// Any file (F-010b): PDF, Word, PowerPoint, text, images — the server makes a PDF of it; links: a PDF snapshot.
const NOTES_MAX_MB = 50;
const NOTES_ACCEPT = ".pdf,.docx,.doc,.rtf,.odt,.pptx,.ppt,.odp,.txt,.md,.png,.jpg,.jpeg,.webp,.gif";
const NOTES_EXT = new Set(NOTES_ACCEPT.split(","));
const DOC_ICON = { pdf: ICON.pdf, word: ICON.word, slides: ICON.pptx, text: ICON.text, image: ICON.image, web: ICON.web };
const docIcon = (d) => DOC_ICON[d.kind] || ICON.pdf;
const pagesOf = (d) => (d.kind === "image" ? "image" : `${d.pages} p.`);
const hasDrop = (e) => e.dataTransfer && [...e.dataTransfer.types].some((t) => t === "Files" || t === "text/uri-list");
const droppedLink = (e) => {
  const raw = (e.dataTransfer.getData("text/uri-list") || e.dataTransfer.getData("text/plain") || "").trim();
  return raw.split(/\r?\n/).find((l) => /^https?:\/\//i.test(l)) || "";
};

async function uploadNotes(file, send) {
  const ext = (file.name.match(/\.[^.]+$/) || [""])[0].toLowerCase();
  if (!NOTES_EXT.has(ext)) throw new Error("Use a PDF, Word, PowerPoint, text or image file");
  if (file.size > NOTES_MAX_MB * 1024 * 1024) throw new Error(`The file is larger than ${NOTES_MAX_MB} MB`);
  const r = await fetch("/api/notes", {
    method: "POST", body: file, headers: { "Content-Type": file.type || "application/octet-stream", "X-File-Name": encodeURIComponent(file.name).slice(0, 120) },
  });
  const res = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(res.error || `Upload failed (${r.status})`);
  send("notes_open", { id: res.id });
}

async function addLink(url, send) {
  const r = await fetch("/api/notes/link", { method: "POST", body: JSON.stringify({ url }), headers: { "Content-Type": "application/json" } });
  const res = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(res.error || `Could not save the page (${r.status})`);
  send("notes_open", { id: res.id });
}

// "Add link": paste a web address (a dropped link needs no field)
function LinkField({ onAdd, onCancel }) {
  const [url, setUrl] = useState("");
  return html`<div class="link-field">
    ${svg(ICON.link)}
    <input value=${url} placeholder="Paste a web link (https://…)" ref=${(el) => el && !el.dataset.f && (el.dataset.f = "1", el.focus())}
      onInput=${(e) => setUrl(e.target.value)}
      onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter" && url.trim()) onAdd(url.trim()); if (e.key === "Escape") onCancel(); }} />
    <button class="primary small" disabled=${!/^https?:\/\/\S+/i.test(url.trim())} onClick=${() => onAdd(url.trim())}>Add</button>
    <button class="icon" onClick=${onCancel} title="Cancel">${svg(ICON.remove)}</button>
  </div>`;
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
function DocMenu({ docs, open, onOpen, onAdd, onLink, busy }) {
  const [shown, setShown, ref] = usePopover();
  return html`<div class="menu-wrap doc-menu" ref=${ref}>
    <button class=${"menu-button" + (shown ? " on" : "")} onClick=${() => setShown(!shown)} aria-expanded=${shown}>
      ${svg(docIcon(open))}<span class="label">${open.name}</span><em>${pagesOf(open)}</em>${svg(ICON.chevron, "chev")}</button>
    ${shown && html`<div class="menu" role="menu">
      ${docs.map((d) => html`<button key=${d.id} role="menuitem" class=${"menu-row" + (d.id === open.id ? " on" : "")}
          onClick=${() => { setShown(false); if (d.id !== open.id) onOpen(d.id); }}>
        ${svg(d.id === open.id ? ICON.check : docIcon(d))}<span>${d.name}</span><em>${pagesOf(d)}</em></button>`)}
      <div class="menu-sep"></div>
      <button role="menuitem" class="menu-row add" disabled=${busy} onClick=${() => { setShown(false); onAdd(); }}>
        ${svg(ICON.add)}<span>Add a file</span></button>
      <button role="menuitem" class="menu-row add" disabled=${busy} onClick=${() => { setShown(false); onLink(); }}>
        ${svg(ICON.link)}<span>Add a web link</span></button>
    </div>`}
  </div>`;
}

// Page turns without a blink (F-010b #12): one <img> whose src changes (the old page stays until the new one is
// decoded), and the pages around it fetched ahead so a turn is instant.
function usePreload(urls) {
  useEffect(() => { urls.filter(Boolean).forEach((u) => { const i = new Image(); i.src = u; }); }, [urls.join("|")]);
}

function Notes({ notes, send, wide, onWide }) {
  const input = useRef(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [over, setOver] = useState(false);
  const [linking, setLinking] = useState(false);
  const n = notes || { docs: [], open: "", page: 0, pages: 0, follow: true, reason: "", matched: "", projecting: false };
  const doc = n.docs.find((d) => d.id === n.open);
  const run = async (job, label) => {
    setBusy(label); setError(""); setLinking(false);
    try { await job(); } catch (err) { setError(err.message); } finally { setBusy(false); }
  };
  const add = (file) => file && run(() => uploadNotes(file, send), /\.pdf$/i.test(file.name) ? "Adding…" : "Converting…");
  const link = (url) => run(() => addLink(url, send), "Saving the page…");
  const pick = (e) => { const f = e.target.files && e.target.files[0]; e.target.value = ""; add(f); };
  const drop = (e) => {
    e.preventDefault(); setOver(false);
    const f = e.dataTransfer.files && e.dataTransfer.files[0];
    if (f) add(f);
    else { const url = droppedLink(e); if (url) link(url); }
  };
  const w = wide ? 1280 : 960;
  const pageUrl = (p) => (doc && p >= 1 && p <= n.pages ? `/api/notes/${doc.id}/page/${p}?w=${w}` : "");
  const src = pageUrl(n.page);
  usePreload([pageUrl(n.page + 1), pageUrl(n.page - 1)]);
  const turn = (page) => send("notes_page", { page });
  const keys = (e) => {  // inside the notes, arrows turn its pages (not the slides)
    if (!doc) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); e.stopPropagation(); if (n.page < n.pages) turn(n.page + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); e.stopPropagation(); if (n.page > 1) turn(n.page - 1); }
  };
  const file = html`<input ref=${input} type="file" accept=${NOTES_ACCEPT} hidden onChange=${pick} />`;
  const addFile = () => input.current.click();
  const note = n.projecting ? "On the projector: only you turn its pages"
    : n.reason || (n.follow ? (n.matched ? html`Matched to <b>${n.matched}</b>` : "Waiting for a slide that matches a page")
      : "Following is off: turn the pages yourself");
  return html`<div class=${"notes" + (over ? " over" : "")} tabindex="0" onKeyDown=${keys}
      onDragOver=${(e) => { if (hasDrop(e)) { e.preventDefault(); setOver(true); } }}
      onDragLeave=${() => setOver(false)} onDrop=${drop}>
    ${file}
    ${!doc ? html`<div class="notes-empty">
        <div class="notes-art">${svg(ICON.notes)}</div>
        ${linking ? html`<${LinkField} onAdd=${link} onCancel=${() => setLinking(false)} />`
          : html`<div class="notes-add">
            <button class="primary" onClick=${addFile} disabled=${!!busy}>
              ${svg(ICON.add, busy ? "pulse" : "")}${busy || "Add notes"}</button>
            <button class="ghost-pill" onClick=${() => setLinking(true)} disabled=${!!busy}>${svg(ICON.link)}Web link</button>
          </div>`}
        <span class="or">PDF, Word, PowerPoint, text, images or a web link · drop one here · only you see it</span>
        ${n.docs.length > 0 && html`<div class="notes-recent">${n.docs.map((d) => html`
          <button key=${d.id} class="doc-row" onClick=${() => send("notes_open", { id: d.id })}>
            ${svg(docIcon(d))}<span>${d.name}</span><em>${pagesOf(d)}</em></button>`)}</div>`}
      </div>`
    : html`<div class="notes-head">
        <${DocMenu} docs=${n.docs} open=${doc} onOpen=${(id) => send("notes_open", { id })} onAdd=${addFile}
          onLink=${() => setLinking(true)} busy=${!!busy} />
        ${doc.kind === "web" && doc.source && html`<a class="icon" href=${doc.source} target="_blank" rel="noopener"
          title="Open the original page">${svg(ICON.open)}</a>`}
        <button class="icon" onClick=${onWide} title=${wide ? "Narrower notes" : "Wider notes"} aria-pressed=${wide}>
          ${svg(wide ? "M9 4v16M4 9l5 3-5 3M20 9l-5 3 5 3" : "M4 4v16M20 4v16M9 12h6M9 12l2-2M9 12l2 2M15 12l-2-2M15 12l-2 2")}</button>
        <button class="icon" onClick=${() => confirm(`Remove “${doc.name}” from your notes?`) && send("notes_remove", { id: doc.id })}
          title="Remove these notes from the list">${svg(ICON.bin)}</button>
      </div>
      ${linking && html`<${LinkField} onAdd=${link} onCancel=${() => setLinking(false)} />`}
      ${busy && html`<p class="notes-busy"><span class="spinner"></span>${busy}</p>`}
      <div class="notes-page">
        <img src=${src} alt=${`${doc.name}, page ${n.page}`} />
      </div>
      <div class="notes-foot">
        <div class="steps">
          <button class="icon" disabled=${n.page <= 1} onClick=${() => turn(n.page - 1)} title="Previous page">${svg(ICON.prev)}</button>
          <span class="count">${n.page} / ${n.pages}</span>
          <button class="icon" disabled=${n.page >= n.pages} onClick=${() => turn(n.page + 1)} title="Next page">${svg(ICON.next)}</button>
        </div>
        <button class=${"project" + (n.projecting ? " on" : "")} aria-pressed=${n.projecting}
          onClick=${() => send("notes_project", { on: !n.projecting })}
          title=${n.projecting ? "Back to the slide on the projector (Esc)" : "Show this page on the projector and to the students"}>
          ${svg(ICON.project)}<span>${n.projecting ? "On projector" : "Project"}</span></button>
        <label class=${"switch" + (n.follow ? " on" : "")} title="Open the page that matches the slide on screen">
          <input type="checkbox" checked=${n.follow} onChange=${(e) => send("notes_follow", { on: e.target.checked })} />
          <span class="track"><span class="knob"></span></span>Follow</label>
      </div>
      <p class=${"notes-note" + (n.reason && !n.projecting ? " off" : "")}>${note}</p>`}
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
// `live` (the running lecture's slide count) refreshes the list too, a moment later (its log is written meanwhile).
function useLectures(active, version, live) {
  const [list, setList] = useState(null);
  const seen = useRef(null);  // the version loaded last: a change of it (a chapter edit) loads at once
  useEffect(() => {
    if (!active) { seen.current = null; return undefined; }
    let gone = false, t = null, tries = 0;
    const load = () => fetch("/api/lectures", { cache: "no-store" }).then((r) => r.json())
      .then((res) => {
        if (gone) return;
        const rows = res.lectures || [];
        setList(rows);
        // slides on screen but the running lecture not listed yet (its log is still being written): look again
        if (live > 0 && !rows.some((l) => l.current) && tries++ < 4) t = setTimeout(load, 1500);
      }).catch(() => { if (!gone) setList((l) => l || []); });
    t = setTimeout(load, seen.current === version ? 1200 : 0);
    seen.current = version;
    return () => { gone = true; clearTimeout(t); };
  }, [active, version, live]);
  return list;
}

function Segmented({ value, options, onChange }) {
  return html`<div class="segmented" role="radiogroup">${options.map(([v, label]) => html`<button key=${v}
    role="radio" aria-checked=${value === v} class=${value === v ? "on" : ""} onClick=${() => onChange(v)}>${label}</button>`)}</div>`;
}

// A checklist in a menu (F-010b #7): lectures (this one first) or chapters; the button sums up what is picked.
function Checklist({ label, empty, rows, picked, onToggle }) {
  const [shown, setShown, ref] = usePopover();
  return html`<div class="menu-wrap pick-wrap" ref=${ref}>
    <button class=${"menu-button" + (shown ? " on" : "")} onClick=${() => setShown(!shown)} aria-expanded=${shown}>
      <span class="label">${label}</span>${svg(ICON.chevron, "chev")}</button>
    ${shown && html`<div class="menu" role="menu">
      ${rows === null ? html`<p class="menu-empty">Loading…</p>`
        : !rows.length ? html`<p class="menu-empty">${empty}</p>`
        : rows.map((r) => html`<button key=${r.id} role="menuitemcheckbox" aria-checked=${picked.includes(r.id)}
            class=${"menu-row" + (picked.includes(r.id) ? " on" : "")} onClick=${() => onToggle(r.id)}>
          <span class=${"check-box" + (picked.includes(r.id) ? " on" : "")}>${picked.includes(r.id) && svg(ICON.check)}</span>
          <span>${r.title}</span><em>${r.note}</em></button>`)}
    </div>`}
  </div>`;
}
const toggled = (list, id) => (list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

function MadeRow({ m, send }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(m.name);
  const k = KIND[m.kind] || {};
  const save = () => { setEditing(false); if (name.trim() && name.trim() !== m.name) send("materials_rename", { id: m.id, name: name.trim() }); };
  const pdf = k.file === ".pdf";
  // no token counts here (user 2026-10-07: the terminal shows them)
  const meta = m.status === "working" ? (m.detail || "working") : m.status === "failed" ? m.detail
    : [ago(m.created), m.kind === "assignment" ? `${m.count} questions` : m.kind === "pptx" ? `${m.count} slides` : "",
      m.detail].filter(Boolean).join(" · ");
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
  const st = materials || { items: [], current: { id: "", title: "" }, llm: false, chapters: [] };
  const chapters = st.chapters || [];
  const [ticks, setTicks] = useState({});
  const [opts, setOpts] = useState({ scope: "topic", count: DEFAULT_QUESTIONS, theme: "light" });
  const [names, setNames] = useState({});
  // From (F-010b #7): this lecture · picked lectures (this one among them) · whole chapters
  const [mode, setMode] = useState("this");
  const [picked, setPicked] = useState([]);       // lecture ids ("now" = this lecture)
  const [pickedCh, setPickedCh] = useState([]);   // chapter ids
  useEffect(() => {  // "Make materials" in a past lecture: that lecture alone
    if (!preselect) return;
    setMode("lectures"); setPicked([preselect]); onPreselected();
  }, [preselect]);
  useEffect(() => {  // the chapter of this lecture is the first guess for Pick chapters
    if (!pickedCh.length && st.current && st.current.chapter) setPickedCh([st.current.chapter]);
  }, [st.current && st.current.chapter]);
  const past = (lectures || []).filter((l) => !l.current);
  const nameOf = (id) => (id === "now" ? st.current.title || "This lecture" : (past.find((l) => l.id === id) || {}).title || "Past lecture");
  const chapterIds = pickedCh.filter((id) => chapters.some((c) => c.id === id));
  const current = mode === "this" || (mode === "lectures" && picked.includes("now"))
    || (mode === "chapters" && chapterIds.includes(st.current.chapter || "-"));
  const pastIds = mode === "lectures" ? picked.filter((id) => id !== "now") : [];
  const title = mode === "chapters"
    ? joinedTitle(chapterIds.map((id) => (chapters.find((c) => c.id === id) || {}).label))
    : joinedTitle(mode === "this" ? [nameOf("now")] : picked.map(nameOf));
  const chosen = KINDS.filter((k) => ticks[k.kind]);
  const blocked = (k) => (k.llm && !st.llm) || (k.kind === "summary" && opts.scope === "topic" && !current);
  const sources = mode === "this" ? 1 : mode === "lectures" ? picked.length : chapterIds.length;
  const ready = chosen.length > 0 && sources > 0 && !chosen.some(blocked);
  const create = () => {
    const items = chosen.map((k) => ({
      kind: k.kind, name: k.file ? (names[k.kind] || "").trim() || autoName(k.kind, title) : "",
      ...(k.kind === "summary" ? { scope: opts.scope } : {}),
      ...(k.kind === "assignment" ? { count: opts.count } : {}),
      ...(k.kind === "pptx" ? { theme: opts.theme } : {}),
    }));
    send("materials_create", mode === "chapters" ? { items, lectures: [], current: false, chapters: chapterIds }
      : { items, lectures: pastIds, current });
    setTicks({}); setNames({});
  };
  const lectureRows = lectures === null ? null : [{ id: "now", title: st.current.title || "This lecture", note: "now" },
    ...past.map((l) => ({ id: l.id, title: l.title, note: l.date.split(",")[0] }))];
  const chapterRows = chapters.map((c) => {
    const n = (lectures || []).filter((l) => l.chapter === c.id).length;
    return { id: c.id, title: c.label, note: c.id === st.current.chapter ? "this lecture's" : `${n} lecture${n === 1 ? "" : "s"}` };
  });
  const summary = (ids, rows, none, word) => (!ids.length ? none : ids.length === 1
    ? ((rows || []).find((r) => r.id === ids[0]) || {}).title || `1 ${word}` : `${ids.length} ${word}s`);
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
        <${Segmented} value=${mode} options=${[["this", "This lecture"], ["lectures", "Pick lectures"], ["chapters", "Pick chapters"]]}
          onChange=${setMode} />
        ${mode === "lectures" && html`<${Checklist} rows=${lectureRows} picked=${picked} empty="No lectures yet"
          label=${summary(picked, lectureRows, "Choose lectures…", "lecture")} onToggle=${(id) => setPicked(toggled(picked, id))} />`}
        ${mode === "chapters" && html`<${Checklist} rows=${chapterRows} picked=${chapterIds}
          empty="No chapters yet: make one in the Lectures tab"
          label=${summary(chapterIds, chapterRows, "Choose chapters…", "chapter")} onToggle=${(id) => setPickedCh(toggled(chapterIds, id))} />`}
      </div>
      <ul class="kinds">${KINDS.map((k) => html`<li key=${k.kind} class=${"kind" + (ticks[k.kind] ? " on" : "") + (blocked(k) ? " off" : "")}>
        <button class="kind-head" role="checkbox" aria-checked=${!!ticks[k.kind]} disabled=${k.llm && !st.llm}
            title=${k.llm && !st.llm ? "Needs the LLM (this run has none)" : ""}
            onClick=${() => setTicks({ ...ticks, [k.kind]: !ticks[k.kind] })}>
          <span class="tile-check">${svg(ICON.check)}</span>
          <span class="kind-icon">${svg(k.icon)}</span>
          <span class="kind-text"><b>${k.label}</b><small>${k.note}</small></span>
        </button>
        ${option(k)}
      </li>`)}</ul>
      <div class="make-foot">
        <span class="make-note">${!st.llm ? "No LLM in this run: only the PowerPoint can be made"
          : !sources ? (mode === "chapters" ? "Choose the chapters" : "Choose the lectures")
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
// Chapters (F-010b §2): "Chapter N · name" in the teacher's order (drag a chapter to renumber it); lectures drag
// between chapters; Unsorted last. Search (titles + slide content) and sort (date / name, both directions).
const DRAG_LECTURE = "application/x-copilot-lecture";
const DRAG_CHAPTER = "application/x-copilot-chapter";
const dragKind = (e) => (e.dataTransfer.types.includes(DRAG_CHAPTER) ? "chapter" : e.dataTransfer.types.includes(DRAG_LECTURE) ? "lecture" : "");

function useSearch(query, version) {
  const [res, setRes] = useState(null);  // null: no search; else {id: {hits, count}}
  useEffect(() => {
    const q = query.trim();
    if (!q) { setRes(null); return undefined; }
    let gone = false;
    const t = setTimeout(() => {
      fetch(`/api/lectures/search?q=${encodeURIComponent(q)}`, { cache: "no-store" }).then((r) => r.json())
        .then((d) => { if (!gone) setRes(Object.fromEntries((d.results || []).map((x) => [x.id, x]))); })
        .catch(() => { if (!gone) setRes({}); });
    }, 220);
    return () => { gone = true; clearTimeout(t); };
  }, [query, version]);
  return res;
}

function LectureRow({ l, hits, onOpen, send }) {
  return html`<li class=${"lecture-row" + (l.current ? " now" : "")} draggable="true"
      onDragStart=${(e) => { e.dataTransfer.setData(DRAG_LECTURE, l.id); e.dataTransfer.effectAllowed = "move"; }}>
    <span class="grip" aria-hidden="true">${svg(ICON.grip)}</span>
    <button class="lecture-open" onClick=${() => onOpen(l.id, 0)} title="Open the slides of this lecture">
      <span class="lecture-title">${l.title}${l.current ? html`<em class="now-tag">now</em>` : ""}</span>
      <small>${l.date} · ${l.slides} slide${l.slides === 1 ? "" : "s"} · ${Math.max(1, Math.round(l.minutes))} min
        ${l.simulated ? html` · <i>test run</i>` : ""}</small>
    </button>
    ${l.materials > 0 && html`<em class="badge" title="Materials made from it">${l.materials}</em>`}
    ${!l.current && html`<button class="icon hide" title="Take it off this list (nothing is deleted)"
      onClick=${() => confirm(`Hide “${l.title}” (${l.date}) from the list?`) && send("lecture_hide", { id: l.id })}>${svg(ICON.hide)}</button>`}
    ${hits && hits.hits.length > 0 && html`<ol class="hits">${hits.hits.map((h) => html`<li key=${h.index}>
      <button onClick=${() => onOpen(l.id, h.index)} title="Open the lecture at this slide">
        <span class="n">${h.index + 1}</span><span>${h.title}</span></button></li>`)}
      ${hits.count > hits.hits.length && html`<li class="more">+ ${hits.count - hits.hits.length} more slides</li>`}</ol>`}
  </li>`;
}

function ChapterGroup({ chapter, items, hits, open, onToggle, onOpen, send, total, searching }) {
  const [over, setOver] = useState(false);
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState(chapter ? chapter.name : "");
  const id = chapter ? chapter.id : "";
  const save = () => { setNaming(false); if (chapter && name.trim() !== chapter.name) send("chapter_rename", { id, name: name.trim() }); };
  const drop = (e) => {
    e.preventDefault(); setOver(false);
    const lecture = e.dataTransfer.getData(DRAG_LECTURE), moved = e.dataTransfer.getData(DRAG_CHAPTER);
    if (lecture) send("lecture_move", { id: lecture, chapter: id });
    else if (moved && chapter && moved !== id) send("chapter_move", { id: moved, index: chapter.number - 1 });
  };
  const accepts = (e) => { const k = dragKind(e); return k === "lecture" || (k === "chapter" && !!chapter); };
  const remove = () => confirm(`Delete “${chapter.label}”?\n\nIts ${items.length} lecture${items.length === 1 ? "" : "s"} move to Unsorted. `
    + "No lecture, slide or material is deleted.\nThe chapters after it are renumbered.") && send("chapter_delete", { id });
  return html`<section class=${"chapter" + (over ? " over" : "") + (open ? " open" : "") + (chapter ? "" : " unsorted")}
      onDragOver=${(e) => { if (accepts(e)) { e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOver(true); } }}
      onDragLeave=${(e) => { if (!e.currentTarget.contains(e.relatedTarget)) setOver(false); }} onDrop=${drop}>
    <header class="chapter-head" draggable=${!!chapter && !naming}
        onDragStart=${(e) => { if (!chapter) return; e.dataTransfer.setData(DRAG_CHAPTER, id); e.dataTransfer.effectAllowed = "move"; }}>
      ${chapter && html`<span class="grip" aria-hidden="true">${svg(ICON.grip)}</span>`}
      <button class="chapter-toggle" onClick=${onToggle} aria-expanded=${open}>
        ${svg(ICON.chevron, "chev")}
        ${naming ? null : html`<span class="chapter-name">${chapter
          ? html`<span class="chapter-no">Chapter ${chapter.number}</span>${chapter.name ? html`<span class="dot-sep">·</span>${chapter.name}` : ""}`
          : "Unsorted"}</span>`}
      </button>
      ${naming && html`<input class="chapter-input" value=${name} maxlength="80" onInput=${(e) => setName(e.target.value)} onBlur=${save}
        ref=${(el) => el && !el.dataset.f && (el.dataset.f = "1", el.focus(), el.select())}
        onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter") save(); if (e.key === "Escape") { setName(chapter.name); setNaming(false); } }} />`}
      <em class="chapter-count">${searching ? `${items.length} / ${total}` : items.length}</em>
      ${chapter && !naming && html`<span class="chapter-tools">
        <button class="icon" title="Rename the chapter" onClick=${() => { setName(chapter.name); setNaming(true); }}>${svg(ICON.edit)}</button>
        <button class="icon danger" title="Delete the chapter (its lectures move to Unsorted)" onClick=${remove}>${svg(ICON.bin)}</button>
      </span>`}
    </header>
    ${open && html`<ul class="chapter-lectures">
      ${items.map((l) => html`<${LectureRow} key=${l.id} l=${l} hits=${hits && hits[l.id]} onOpen=${onOpen} send=${send} />`)}
      ${!items.length && html`<li class="chapter-empty">${chapter ? "Drag lectures here" : "Every lecture is in a chapter"}</li>`}
    </ul>`}
  </section>`;
}

function Lectures({ lectures, chapters, onOpen, send, version }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState({ by: "date", dir: "desc" });
  const [closed, setClosed] = useState({});  // chapter id ("" = Unsorted) → collapsed
  const [naming, setNaming] = useState(false);
  const [name, setName] = useState("");
  const hits = useSearch(query, version);
  if (lectures === null) return html`<div class="lectures"><p class="made-empty">Loading…</p></div>`;
  const cmp = sort.by === "name" ? (a, b) => a.title.localeCompare(b.title, undefined, { sensitivity: "base" })
    : (a, b) => a.started - b.started;
  const dir = sort.dir === "asc" ? 1 : -1;
  const shown = hits ? lectures.filter((l) => hits[l.id]) : lectures;
  const inChapter = (id) => shown.filter((l) => (l.chapter || "") === id).sort((a, b) => dir * cmp(a, b));
  const known = new Set(chapters.map((c) => c.id));
  const order = [...chapters].sort(sort.by === "name"
    ? (a, b) => dir * (a.name || a.label).localeCompare(b.name || b.label, undefined, { sensitivity: "base" })
    : (a, b) => dir * (a.number - b.number));
  const unsorted = shown.filter((l) => !known.has(l.chapter || "")).sort((a, b) => dir * cmp(a, b));
  const create = () => { if (name.trim()) send("chapter_create", { name: name.trim() }); setName(""); setNaming(false); };
  const groups = [...order.map((c) => ({ chapter: c, items: inChapter(c.id), total: lectures.filter((l) => l.chapter === c.id).length })),
    { chapter: null, items: unsorted, total: lectures.filter((l) => !known.has(l.chapter || "")).length }]
    .filter((g) => !hits || g.items.length);
  return html`<div class="lectures">
    <div class="lectures-tools">
      <label class="search">${svg(ICON.search)}
        <input type="search" value=${query} placeholder="Search lectures and slides" onInput=${(e) => setQuery(e.target.value)}
          onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Escape") setQuery(""); }} /></label>
      <${Segmented} value=${sort.by} options=${[["date", "Date"], ["name", "Name"]]} onChange=${(by) => setSort({ ...sort, by })} />
      <button class="icon sort-dir" onClick=${() => setSort({ ...sort, dir: sort.dir === "asc" ? "desc" : "asc" })}
        title=${sort.dir === "asc" ? (sort.by === "name" ? "A → Z (click for Z → A)" : "Oldest first (click for newest first)")
          : (sort.by === "name" ? "Z → A (click for A → Z)" : "Newest first (click for oldest first)")}>
        ${svg(sort.dir === "asc" ? ICON.sortUp : ICON.sortDown)}</button>
    </div>
    ${naming ? html`<div class="new-chapter">
        <span class="new-number">Chapter ${chapters.length + 1} ·</span>
        <input value=${name} placeholder="Name, e.g. Cell biology" maxlength="80" ref=${(el) => el && !el.dataset.f && (el.dataset.f = "1", el.focus())}
          onInput=${(e) => setName(e.target.value)} onKeyDown=${(e) => { e.stopPropagation(); if (e.key === "Enter") create(); if (e.key === "Escape") setNaming(false); }} />
        <button class="primary small" onClick=${create} disabled=${!name.trim()}>Create</button>
        <button class="icon" onClick=${() => setNaming(false)} title="Cancel">${svg(ICON.remove)}</button>
      </div>`
      : html`<button class="ghost-pill new-chapter-btn" onClick=${() => setNaming(true)}>${svg(ICON.add)}New chapter</button>`}
    ${hits && !groups.length && html`<p class="made-empty">Nothing found for “${query.trim()}”.</p>`}
    ${!lectures.length && html`<p class="made-empty">Lectures appear here.</p>`}
    ${groups.map((g) => html`<${ChapterGroup} key=${g.chapter ? g.chapter.id : "unsorted"} chapter=${g.chapter} items=${g.items}
      total=${g.total} searching=${!!hits} hits=${hits} open=${!!hits || !closed[g.chapter ? g.chapter.id : ""]}
      onToggle=${() => setClosed({ ...closed, [g.chapter ? g.chapter.id : ""]: !closed[g.chapter ? g.chapter.id : ""] })}
      onOpen=${onOpen} send=${send} />`)}
  </div>`;
}

function LectureViewer({ id, start = 0, made, onClose, onMake, send }) {
  const [data, setData] = useState(null);
  const [at, setAt] = useState(start);  // a search hit opens the lecture at its slide
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
  const [viewing, setViewing] = useState(null);      // {id, at}: a lecture open in the viewer (F-010)
  const [preselect, setPreselect] = useState(null);  // "Make materials" from that lecture
  const materials = state.materials;
  const listVersion = `${materials ? materials.lectures_changed : 0}:${materials ? materials.items.length : 0}`;
  const lectures = useLectures(tab === "materials" || tab === "lectures", listVersion,
    state.deck ? state.deck.slide_ids.length : 0);
  const notesOpen = state.notes && state.notes.open;
  useEffect(() => { if (!notesOpen) setWide(false); }, [notesOpen]);  // F-010b #6: no notes, default width

  const deck = state.deck;
  const shownNotes = state.notesShown && state.notesShown.on;
  useEffect(() => {
    const onKey = (e) => {
      if (e.target.tagName === "INPUT" || e.target.tagName === "TEXTAREA") return;
      if (e.key === "Escape") {
        if (shownNotes) { e.preventDefault(); send("notes_project", { on: false }); }
        else if (deck && deck.zoom) { e.preventDefault(); send("unzoom_image"); }
        return;
      }
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
  }, [deck, state.lifecycle, state.theme, shownNotes]);

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
          materials=${materials} notesShown=${state.notesShown}
          notice=${notice} onNotice=${setNotice} adding=${adding} onAdded=${() => setAdding(false)}
          status=${liveSpec && state.images[liveSpec.id]} choices=${liveSpec && state.choices[liveSpec.id]} />
        <${Dock} deck=${deck} lifecycle=${state.lifecycle} send=${send} toggle=${toggle} theme=${state.theme}
          canAdd=${!!liveSpec && !(deck && deck.zoom)} onAdd=${() => setAdding(true)} />
        <p class="hint">Keys: ← → navigate · Space pause / resume · B blank · N new slide · T light / dark slides · hover or double-click a slide item to edit it</p>
      </section>
      <section class="right">
        <${Concerns} concerns=${state.concerns} send=${send} />
        <${SidePanel} tab=${tab} onTab=${setTab}>
          <${Tab} id="structure" label="Lecture structure" icon=${ICON.tree} badge=${deck && deck.slide_ids.length ? deck.slide_ids.length : ""}>
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
            <${Lectures} lectures=${lectures} chapters=${(materials && materials.chapters) || []} version=${listVersion}
              onOpen=${(id, at) => setViewing({ id, at })} send=${send} />
          </${Tab}>
        </${SidePanel}>
      </section>
    </main>
    <${TranscriptStrip} lines=${state.transcript} />
    ${viewing && html`<${LectureViewer} key=${viewing.id + ":" + viewing.at} id=${viewing.id} start=${viewing.at || 0}
      send=${send} onClose=${() => setViewing(null)}
      made=${(materials ? materials.items : []).filter((m) => m.lectures.includes(viewing.id))}
      onMake=${(id) => { setViewing(null); setPreselect(id === (materials && materials.current.id) ? "now" : id); setTab("materials"); }} />`}
    <${Tooltip} />
  </div>`;
}

function formatTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

render(html`<${App} />`, document.getElementById("root"));
