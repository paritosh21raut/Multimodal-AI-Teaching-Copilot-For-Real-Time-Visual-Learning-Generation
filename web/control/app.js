// /control — the teacher's laptop view: live preview, deck, controls, transcript, status.
// It never changes state itself; every action is a command sent to the server.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { Slide, ZoomedImage, editableText, imageOf, partLabel, shownTitle, useStageScale } from "../shared/slide.js";
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
};

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

function Preview({ spec, deck, lifecycle, slides, choices, status, send, notice, onNotice, adding, onAdded }) {
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
  return html`<div class=${"preview" + (drag ? " dragging" : "")} ref=${ref}
      onDragEnter=${(e) => { if (!hasFiles(e)) return; e.preventDefault(); depth.current += 1; if (drag !== "uploading") setDrag("over"); }}
      onDragOver=${(e) => { if (hasFiles(e)) { e.preventDefault(); e.dataTransfer.dropEffect = canDrop ? "copy" : "none"; } }}
      onDragLeave=${() => { depth.current = Math.max(0, depth.current - 1); if (!depth.current && drag === "over") setDrag(null); }}
      onDrop=${drop}>
    <div class="stage" style=${{ transform: `translate(-50%, -50%) scale(${scale})` }}>
      ${shown ? html`<${Slide} key=${spec.id} spec=${shown}
        onImageClick=${drag ? undefined : () => send("zoom_image", { slide_id: spec.id })} />` : html`<div class="waiting">No slide yet</div>`}
      ${zoomed && html`<${ZoomedImage} key=${zoomed.image_id || zoomed.url} image=${zoomed} onClose=${() => send("unzoom_image")} />`}
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

function Dock({ deck, lifecycle, send, toggle, canAdd, onAdd }) {
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
  useEffect(() => { document.documentElement.dataset.theme = state.theme; }, [state.theme]);

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
      const k = KEYS[e.key] || KEYS[e.key.toLowerCase()];
      if (!k) return;
      e.preventDefault();
      if (k.length === 3) send(deck && deck[k[2]] ? k[1] : k[0]);
      else send(k[0]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deck, state.lifecycle]);

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
    </header>
    <main class="grid">
      <section class="left">
        <${Preview} spec=${liveSpec} deck=${deck} lifecycle=${state.lifecycle} slides=${state.slides} send=${send}
          notice=${notice} onNotice=${setNotice} adding=${adding} onAdded=${() => setAdding(false)}
          status=${liveSpec && state.images[liveSpec.id]} choices=${liveSpec && state.choices[liveSpec.id]} />
        <${Dock} deck=${deck} lifecycle=${state.lifecycle} send=${send} toggle=${toggle}
          canAdd=${!!liveSpec && !(deck && deck.zoom)} onAdd=${() => setAdding(true)} />
        <p class="hint">Keys: ← → navigate · Space pause / resume · B blank · N new slide · hover or double-click a slide item to edit it</p>
      </section>
      <section class="right">
        <${Concerns} concerns=${state.concerns} send=${send} />
        <${Structure} deck=${deck} slides=${state.slides} send=${send} />
      </section>
    </main>
    <${TranscriptStrip} lines=${state.transcript} />
  </div>`;
}

function formatTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

render(html`<${App} />`, document.getElementById("root"));
