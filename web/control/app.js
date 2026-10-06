// /control — the teacher's laptop view: live preview, deck, controls, transcript, status.
// It never changes state itself; every action is a command sent to the server.
import { html, render, useEffect, useReducer, useRef, useState } from "../vendor/htm-preact-standalone.mjs";
import { Slide, partLabel, useStageScale } from "../shared/slide.js";
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

function Preview({ spec, deck, send, onNotice }) {
  const ref = useRef(null);
  const scale = useStageScale(ref);
  const [drag, setDrag] = useState(null); // null | "over" | "uploading"
  const depth = useRef(0);
  const canDrop = spec && spec.layout !== "title";
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
      ${shown ? html`<${Slide} key=${spec.id} spec=${shown} />` : html`<div class="waiting">No slide yet</div>`}
    </div>
    ${deck && (deck.blank || deck.frozen || deck.pinned) && html`<div class="flags">
      ${deck.blank && html`<span class="flag warn">BLANK</span>`}
      ${deck.frozen && html`<span class="flag warn">FROZEN</span>`}
      ${deck.pinned && html`<span class="flag">PINNED</span>`}
    </div>`}
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

const SEARCH_TEXT = { searching: "Finding an image…", none: "No suitable image found" };

function ImageTools({ spec, status, send, notice, onNotice }) {
  const input = useRef(null);
  if (!spec || spec.layout === "title") return null;
  const image = spec.blocks.find((b) => b.type === "image");
  const pick = async (e) => {
    const file = e.target.files && e.target.files[0];
    e.target.value = "";
    if (!file) return;
    try { await placeImage(file, spec.id, send); onNotice(""); } catch (err) { onNotice(err.message); }
  };
  const info = notice || (status && SEARCH_TEXT[status.state]) || (image ? (image.origin === "teacher" ? "Your image" : "Image chosen automatically") : "No image · drag one onto the slide or");
  return html`<div class="image-tools">
    <span class="label">Image</span>
    <span class=${"info" + (notice ? " error" : "")}>${info}</span>
    <input ref=${input} type="file" accept=${UPLOAD_TYPES.join(",")} hidden onChange=${pick} />
    <button onClick=${() => input.current.click()} title="Choose an image file for this slide">${image ? "Use my image" : "Add image"}</button>
    ${image && html`<button onClick=${() => { onNotice(""); send("change_image", { slide_id: spec.id }); }}
      disabled=${status && status.state === "searching"} title="Show a different image for this topic">Change image</button>
      <button onClick=${() => { onNotice(""); send("remove_image", { slide_id: spec.id }); }} title="Take the image off this slide">Remove image</button>`}
  </div>`;
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
        <${Preview} spec=${liveSpec} deck=${deck} send=${send} onNotice=${setNotice} />
        <${ImageTools} spec=${liveSpec} status=${liveSpec && state.images[liveSpec.id]} send=${send}
          notice=${notice} onNotice=${setNotice} />
        <div class="buttons">
          <button onClick=${() => send("prev")} title="←">◀ Prev</button>
          <button onClick=${() => send("next")} title="→">Next ▶</button>
          <button class=${deck && deck.pinned ? "on" : ""} onClick=${toggle("pin", "unpin", "pinned")} title="P">Pin</button>
          <button class=${deck && deck.frozen ? "on" : ""} onClick=${toggle("freeze", "unfreeze", "frozen")} title="F">Freeze</button>
          <button class=${deck && deck.blank ? "on" : ""} onClick=${toggle("blank", "unblank", "blank")} title="B">Blank</button>
          <button onClick=${() => send("force_new_slide")} title="N">New slide</button>
          <button class="danger" onClick=${() => confirm("End the lecture?") && send("end")}>End lecture</button>
        </div>
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
