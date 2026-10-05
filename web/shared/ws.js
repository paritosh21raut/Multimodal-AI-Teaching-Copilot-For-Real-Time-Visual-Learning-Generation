// WebSocket client with automatic reconnect. The server is authoritative: every (re)connect
// starts with a full "hello" snapshot, so the client never has to replay missed messages.
export function connect(role, onMessage, onStatus) {
  let ws = null;
  let retry = 0;
  let closed = false;

  const open = () => {
    const proto = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${proto}://${location.host}/ws?role=${role}`);
    ws.onopen = () => { retry = 0; onStatus && onStatus("connected"); };
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
export const initialState = { theme: "light", lifecycle: "starting", slides: {}, deck: null, transcript: [], audio: null, connected: false, concerns: [] };

export function reduce(state, msg) {
  switch (msg.type) {
    case "hello":
      return { ...state, theme: msg.theme, lifecycle: msg.lifecycle, slides: msg.slides || {}, deck: msg.deck, transcript: msg.transcript || [], concerns: msg.concerns || [] };
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
    default: return state;
  }
}
