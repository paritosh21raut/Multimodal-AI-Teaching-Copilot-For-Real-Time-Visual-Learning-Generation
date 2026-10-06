// /control — the teacher's laptop view: live preview, deck, controls, transcript, status.
// It never changes state itself; every action is a command sent to the server.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { Slide, ZoomedImage, imageOf, partLabel, useStageScale } from "../shared/slide.js";
import { connect, initialState, reduce } from "../shared/ws.js";

const KEYS = {
  ArrowRight: ["next"], ArrowLeft: ["prev"],
  f: ["freeze", "unfreeze", "frozen"], p: ["pin", "unpin", "pinned"], b: ["blank", "unblank", "blank"],
  n: ["force_new_slide"],
};

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
  pin: "M9 3h6M10 3v6l-4 4h12l-4-4V3M12 13v8",
  freeze: "M12 2v20M3.3 7l17.4 10M20.7 7L3.3 17M9 4l3 3 3-3M9 20l3-3 3 3",
  blank: "M3 5h18v12H3zM8 21h8M12 17v4M5 3l14 16",
  newSlide: "M4 5h16v14H4zM12 9v6M9 12h6",
  end: "M7 7h10v10H7z",
};

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

function Preview({ spec, deck, slides, choices, status, send, notice, onNotice }) {
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
    ${zoomed && html`<button class="back" onClick=${() => send("unzoom_image")} title="Back to the slide (Esc)">
      ${svg(ICON.back)}<span>Back to slide</span><kbd>Esc</kbd></button>`}
    ${spec && spec.layout !== "title" && !zoomed && !drag && html`<${ImageBar} spec=${spec} image=${image}
      choices=${choices} status=${status} send=${send} onNotice=${onNotice} />`}
    ${line && !drag && html`<div class=${"image-status" + (line.error ? " error" : "")}>
      ${line.busy && html`<span class="dot"></span>`}${line.text}</div>`}
    ${deck && (deck.blank || deck.frozen || deck.pinned) && html`<div class="flags">
      ${deck.blank && html`<span class="flag warn">BLANK</span>`}
      ${deck.frozen && html`<span class="flag warn">FROZEN</span>`}
      ${deck.pinned && html`<span class="flag">PINNED</span>`}
    </div>`}
  </div>`;
}

// Teacher controls under the preview. DOCK_CONTROLS = false brings back the earlier plain button row (kept on
// purpose: the teacher may prefer it; its styles are `.buttons` in control.css).
const DOCK_CONTROLS = true;
const endLecture = (send) => () => confirm("End the lecture?") && send("end");

function Dock({ deck, send, toggle }) {
  const ids = deck ? deck.slide_ids : [];
  const at = deck ? ids.indexOf(deck.live_id) : -1;
  const flag = (name, on, off, key, icon, label, warn) => {
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
      ${flag("pinned", "pin", "unpin", "P", ICON.pin, "Pin")}
      ${flag("frozen", "freeze", "unfreeze", "F", ICON.freeze, "Freeze", true)}
      ${flag("blank", "blank", "unblank", "B", ICON.blank, "Blank", true)}
    </div>
    <div class="group">
      <button onClick=${() => send("force_new_slide")} title="Start a new slide (N)">${svg(ICON.newSlide)}<span>New slide</span></button>
    </div>
    <button class="end" onClick=${endLecture(send)} title="End the lecture">${svg(ICON.end)}<span>End lecture</span></button>
  </div>`;
}

function ClassicButtons({ deck, send, toggle }) {
  return html`<div class="buttons">
    <button onClick=${() => send("prev")} title="←">◀ Prev</button>
    <button onClick=${() => send("next")} title="→">Next ▶</button>
    <button class=${deck && deck.pinned ? "on" : ""} onClick=${toggle("pin", "unpin", "pinned")} title="P">Pin</button>
    <button class=${deck && deck.frozen ? "on" : ""} onClick=${toggle("freeze", "unfreeze", "frozen")} title="F">Freeze</button>
    <button class=${deck && deck.blank ? "on" : ""} onClick=${toggle("blank", "unblank", "blank")} title="B">Blank</button>
    <button onClick=${() => send("force_new_slide")} title="N">New slide</button>
    <button class="danger" onClick=${endLecture(send)}>End lecture</button>
  </div>`;
}

function Meter({ audio }) {
  const db = audio ? 20 * Math.log10(Math.max(audio.rms, 1e-6)) : -120;
  const pct = Math.max(0, Math.min(100, ((db + 70) / 60) * 100));
  return html`<div class="meter" title=${`${db.toFixed(0)} dBFS`}>
    <div class=${"meter-fill" + (audio && audio.speaking ? " speaking" : "")} style=${{ width: `${pct}%` }}></div>
  </div>`;
}

// Mistakes and suspected mis-hearings: the projector stays truthful (it shows the correction when the model is
// confident); this panel tells the teacher what was said and what the slide shows, with a one-click switch.
function Concerns({ concerns, send }) {
  if (!concerns.length) return null;
  const act = (id, action) => send("resolve_concern", { id, action });
  return html`<section class="concerns">
    <h2>Check this <span class="count">${concerns.length}</span></h2>
    ${concerns.map((c) => {
      const mishear = c.kind === "transcription";
      const shows = c.applied ? (c.right || c.suggested_correction) : (c.wrong || c.claim);
      return html`<article key=${c.id} class=${"concern " + (c.kind || "factual")}>
        <div class="concern-head">
          <span class="kind">${mishear ? "Possible mis-hearing" : "Possible mistake"}</span>
          <span class="conf">${Math.round((c.confidence || 0) * 100)}%</span>
        </div>
        <p class="said"><span>${mishear ? "Heard" : "You said"}</span> “${c.claim}”</p>
        ${c.suggested_correction && html`<p class="fix"><span>Correct</span> ${c.suggested_correction}</p>`}
        ${c.issue && html`<p class="issue">${c.issue}</p>`}
        <p class=${"status " + (c.applied ? "fixed" : "as-said")}>
          ${c.applied ? "The slide shows the correction" : "The slide shows what you said"}${shows ? `: “${shows}”` : ""}
        </p>
        <div class="concern-actions">
          ${c.applied
            ? html`<button class="accept" onClick=${() => act(c.id, "dismiss")} title="Keep the correction on the slide">OK</button>
                   <button onClick=${() => act(c.id, "keep")} title="Put back what you said">Show as I said</button>`
            : html`<button class="accept" disabled=${!c.suggested_correction} onClick=${() => act(c.id, "accept")}
                     title="Show the corrected version on the slide">Show correction</button>
                   <button onClick=${() => act(c.id, "dismiss")} title="Keep what you said">OK</button>`}
        </div>
      </article>`;
    })}
  </section>`;
}

function App() {
  const [state, dispatch] = useReducer(reduce, initialState);
  const [notice, setNotice] = useState("");
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
      const k = KEYS[e.key] || KEYS[e.key.toLowerCase()];
      if (!k) return;
      e.preventDefault();
      if (k.length === 3) send(deck && deck[k[2]] ? k[1] : k[0]);
      else send(k[0]);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [deck]);

  const transcriptRef = useRef(null);
  useEffect(() => { const el = transcriptRef.current; if (el) el.scrollTop = el.scrollHeight; }, [state.transcript.length]);

  const liveSpec = deck && deck.live_id ? state.slides[deck.live_id] : null;
  const ids = deck ? deck.slide_ids : [];
  const toggle = (on, off, flag) => () => send(deck && deck[flag] ? off : on);

  return html`<div class="control">
    <header class="bar">
      <strong>Teaching Copilot</strong>
      <span class=${"pill " + state.lifecycle}>${state.lifecycle}</span>
      <span class=${"pill " + (state.connected ? "ok" : "bad")}>${state.connected ? "connected" : "offline"}</span>
      <${Meter} audio=${state.audio} />
      <a class="open-display" href="/display" target="classroom-display">Open classroom display ↗</a>
    </header>
    <main class="grid">
      <section class="left">
        <${Preview} spec=${liveSpec} deck=${deck} slides=${state.slides} send=${send} notice=${notice} onNotice=${setNotice}
          status=${liveSpec && state.images[liveSpec.id]} choices=${liveSpec && state.choices[liveSpec.id]} />
        ${DOCK_CONTROLS ? html`<${Dock} deck=${deck} send=${send} toggle=${toggle} />`
                        : html`<${ClassicButtons} deck=${deck} send=${send} toggle=${toggle} />`}
        <ol class="deck">
          ${ids.map((id, i) => {
            const s = state.slides[id];
            return html`<li key=${id} class=${id === (deck && deck.live_id) ? "live" : ""} onClick=${() => send("goto", { slide_id: id })}>
              <span class="n">${i + 1}</span><span class="t">${s ? s.title : "…"}${s && s.part ? html` <span class="part">${partLabel(s.part)}</span>` : ""}</span>${s && s.facet && html`<span class="f">${s.facet}</span>`}
            </li>`;
          })}
        </ol>
      </section>
      <section class="right">
        <${Concerns} concerns=${state.concerns} send=${send} />
        <h2>Transcript</h2>
        <div class="transcript" ref=${transcriptRef}>
          ${state.transcript.map((l, i) => html`<p key=${i} class=${l.dropped ? "dropped" : ""}>
            <span class="ts">${formatTime(l.t)}</span>${l.dropped ? `(${l.dropped}) ${l.text || ""}` : l.text}
          </p>`)}
        </div>
        <p class="hint">Keys: ← → navigate · P pin · F freeze · B blank · N new slide</p>
      </section>
    </main>
  </div>`;
}

function formatTime(t) {
  const m = Math.floor(t / 60), s = Math.floor(t % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

render(html`<${App} />`, document.getElementById("root"));
