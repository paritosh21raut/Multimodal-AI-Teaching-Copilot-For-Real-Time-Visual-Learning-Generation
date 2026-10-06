// WebSocket client with automatic reconnect. The server is authoritative: every (re)connect
// starts with a full "hello" snapshot, so the client never has to replay missed messages.
// A tab left open across app runs reconnects on its own but keeps its old scripts: reload when the server's
// client files differ from the ones this page was served with (live tests 2026-10-06 ran the pre-V1a renderer).
async function reloadIfOutdated() {
  const mine = document.querySelector('meta[name="client-version"]')?.content;
  if (!mine) return;
  try {
    const r = await fetch("/api/client-version", { cache: "no-store" });
    const { version } = await r.json();
    if (version && version !== mine) location.reload();
  } catch (e) { console.warn("client version check failed", e); }
}

export function connect(role, onMessage, onStatus) {
  let ws = null;
  let retry = 0;
  let closed = false;

  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?role=${role}`);
    ws.onopen = () => { retry = 0; onStatus && onStatus("connected"); reloadIfOutdated(); };
    ws.onmessage = (ev) => {
      try { onMessage(JSON.parse(ev.data)); } catch (e) { console.error("bad message", e); }
    };
    ws.onclose = () => {
      onStatus && onStatus("disconnected");
      if (closed) return;
      // capped at 2 s: a tab left open from an earlier run reconnects before the app decides to open a new one
      const delay = Math.min(2000, 300 * 2 ** retry++);
      setTimeout(open, delay);
    };
  };
  open();

  return {
    send(msg) { if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)); },
    close() { closed = true; ws && ws.close(); },
  };
}

// Reducer shared by both pages: applies server messages to a plain state object.
export const initialState = { theme: "light", lifecycle: "starting", slides: {}, deck: null, transcript: [], audio: null, connected: false, concerns: [], images: {}, choices: {},
  share: { state: "off", url: "", detail: "" }, viewers: 0 };

export function reduce(state, msg) {
  switch (msg.type) {
    case "hello":
      return { ...state, theme: msg.theme, lifecycle: msg.lifecycle, slides: msg.slides || {}, deck: msg.deck, transcript: msg.transcript || [], concerns: msg.concerns || [], choices: msg.image_choices || {},
        share: msg.share || initialState.share, viewers: msg.viewers || 0 };
    case "share": return { ...state, share: { state: msg.state, url: msg.url, detail: msg.detail } };  // control only (F-008)
    case "viewers": return { ...state, viewers: msg.count };
    case "patch": {
      const cur = state.slides[msg.slide_id];
      if (cur && cur.version >= msg.version) return state; // stale
      return { ...state, slides: { ...state.slides, [msg.slide_id]: msg.spec } };
    }
    case "deck": return { ...state, deck: msg.deck };
    case "lifecycle": return { ...state, lifecycle: msg.lifecycle };
    case "transcript": return { ...state, transcript: [...state.transcript.slice(-39), msg.line] };
    case "audio": return { ...state, audio: { rms: msg.rms, speaking: msg.speaking } };
    case "connection": return { ...state, connected: msg.connected };
    case "concern":  // new or updated (switched) concern
      return state.concerns.some((c) => c.id === msg.concern.id)
        ? { ...state, concerns: state.concerns.map((c) => (c.id === msg.concern.id ? msg.concern : c)) }
        : { ...state, concerns: [...state.concerns, msg.concern] };
    case "concern_resolved": return { ...state, concerns: state.concerns.filter((c) => c.id !== msg.id) };
    case "image_status":  // control only: image search state per slide (F-007b)
      return { ...state, images: { ...state.images, [msg.slide_id]: { state: msg.state, request: msg.request, reason: msg.reason, at: Date.now() } } };
    case "image_choices":  // control only: images this slide has shown, for the previous / next arrows
      return { ...state, choices: { ...state.choices, [msg.slide_id]: { index: msg.index, count: msg.count } } };
    default: return state;
  }
}
