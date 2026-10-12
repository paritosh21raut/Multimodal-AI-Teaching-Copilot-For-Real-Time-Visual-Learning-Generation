// Quiz + test (F-011): the students' screens (/view), the projector (/display) and the parts /control reuses.
// Students join with name + roll number; the token from the join is kept in this browser (a refresh rejoins with the
// answers and the timer). They get the public state on the WebSocket (no answer key before it is due) and their own
// state over HTTP. Pages only send requests; the core decides everything (time, scores, what is shown).
// Class names are prefixed (as-, opt, board, …) so slide.css / control.css never style them.
import { html, useEffect, useRef, useState } from "../vendor/htm-preact-standalone.mjs";

export const LETTERS = ["A", "B", "C", "D"];
const SHAPES = [
  html`<path d="M12 3.5 21 19.5H3z" />`,
  html`<path d="M12 2.5 21.5 12 12 21.5 2.5 12z" />`,
  html`<circle cx="12" cy="12" r="9" />`,
  html`<rect x="3.5" y="3.5" width="17" height="17" rx="2" />`,
];
export const Shape = ({ i }) => html`<svg class="shape" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">${SHAPES[i]}</svg>`;
const Tick = ({ cls = "as-tick" }) => html`<svg class=${cls} viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5l4.5 4.5L19 7.5" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/></svg>`;
const Cross = () => html`<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round"/></svg>`;
export const PauseIcon = () => html`<svg viewBox="0 0 24 24" class="pause-ico" aria-hidden="true"><rect x="6" y="5" width="4" height="14" rx="1.2" fill="currentColor"/><rect x="14" y="5" width="4" height="14" rx="1.2" fill="currentColor"/></svg>`;

// seconds left on a timer that arrived as `left` at `at` (ms); frozen while paused
export function useLeft(a) {
  const [, tick] = useState(0);
  const running = a && a.left != null && !a.paused;
  useEffect(() => {
    if (!running) return;
    const t = setInterval(() => tick((n) => n + 1), 200);
    return () => clearInterval(t);
  }, [running, a && a.at]);
  if (!a || a.left == null) return null;
  if (a.paused) return a.left;
  return Math.max(0, a.left - (Date.now() - a.at) / 1000);
}

export const clock = (s) => {
  if (s == null) return "";
  const t = Math.ceil(s);
  return t >= 60 ? `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}` : `${t}`;
};

// a ring that empties as the time runs out
export function TimerRing({ left, total, paused, size = "md" }) {
  if (left == null) return null;
  const frac = total > 0 ? Math.max(0, Math.min(1, left / total)) : 0;
  const r = 44, c = 2 * Math.PI * r;
  const low = left <= Math.min(5, total * 0.25);
  const long = clock(left).length > 3;  // "10:00" needs smaller digits than "15"
  return html`<div class=${`timer ${size}${low ? " low" : ""}${paused ? " paused" : ""}${long ? " long" : ""}`} role="timer"
      aria-label=${`${Math.ceil(left)} seconds left`}>
    <svg viewBox="0 0 100 100" aria-hidden="true"><circle class="ring-track" cx="50" cy="50" r=${r} />
      <circle class="ring-run" cx="50" cy="50" r=${r} style=${{ strokeDasharray: c, strokeDashoffset: c * (1 - frac) }} /></svg>
    <b>${paused ? html`<${PauseIcon} />` : clock(left)}</b></div>`;
}

// four option tiles; after the reveal: the right one marked, the others dimmed, each tile filled by its share
export function OptionGrid({ question, answer, distribution, mine, onPick, disabled, compact }) {
  const total = distribution ? distribution.reduce((x, y) => x + y, 0) : 0;
  const revealed = answer != null && !!distribution;
  return html`<div class=${"opts" + (compact ? " compact" : "") + (revealed ? " revealed" : "")}>
    ${question.options.map((o, i) => {
      const cls = ["opt", `o${i}`, revealed && (i === answer ? "is-right" : "is-dim"), mine === i && "is-mine",
        answer != null && !distribution && i === answer && "is-key"].filter(Boolean).join(" ");
      const n = distribution ? distribution[i] : 0;
      const body = html`${revealed && html`<i class="opt-fill" style=${{ width: `${total ? (100 * n) / total : 0}%` }}></i>`}
        <${Shape} i=${i} /><span class="opt-text">${o}</span>
        ${revealed && html`<b class="opt-count">${n}</b>`}
        ${(revealed || (answer != null && !distribution)) && i === answer && html`<${Tick} />`}`;
      return onPick
        ? html`<button key=${i} class=${cls} disabled=${disabled} onClick=${() => onPick(i)} aria-label=${`${LETTERS[i]}: ${o}`}>${body}</button>`
        : html`<div key=${i} class=${cls}>${body}</div>`;
    })}
  </div>`;
}

export function Leaderboard({ rows, me, limit = 10 }) {
  if (!rows || !rows.length) return null;
  return html`<ol class="board">${rows.slice(0, limit).map((r, n) => html`<li key=${r.roll || r.name + n}
      class=${(me && r.name === me ? "is-me " : "") + (r.rank <= 3 ? `top${r.rank}` : "")} style=${{ "--i": n }}>
    <span class="rank">${r.rank}</span><span class="who">${r.name}</span>
    <b class="pts">${r.score.toLocaleString()}</b></li>`)}</ol>`;
}

function Podium({ rows }) {
  const top = (rows || []).slice(0, 3);
  if (!top.length) return html`<p class="as-muted">Nobody answered.</p>`;
  // the block's height is its place on the podium (ties keep their shared rank as the label)
  const order = [[top[1], 2], [top[0], 1], [top[2], 3]].filter(([r]) => r);
  return html`<div class="podium">${order.map(([r, place]) => html`<div key=${r.name} class=${`pod p${place}`}
      style=${{ "--d": `${{ 1: 500, 2: 250, 3: 0 }[place]}ms` }}>
    <span class="who">${r.name}</span><b>${r.score.toLocaleString()}</b><div class="pod-block"><span>${r.rank}</span></div></div>`)}</div>`;
}

const kindName = (k) => (k === "test" ? "test" : "quiz");
const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);

// ---- the projector --------------------------------------------------------------------------------------------
// "quiet-river-demo" / ".trycloudflare.com/view": two unbroken lines a student can type
const joinParts = (url) => {
  const rest = url.replace(/^https?:\/\//, "");
  const dot = rest.indexOf(".");
  return dot > 0 ? [rest.slice(0, dot), rest.slice(dot)] : [rest];
};

function JoinCode({ url, small }) {
  return html`<div class=${"join" + (small ? " is-small" : "")}>
    ${url ? html`<img class="qr" src=${`/api/share/qr.svg?u=${encodeURIComponent(url)}`} alt="QR code of the join link" />
      <div class="join-link">${joinParts(url).map((p, i) => html`<span key=${i}>${p}</span>`)}</div>`
      : html`<p class="join-off">Turn on <b>Share</b> in the teacher's screen so students can join.</p>`}
  </div>`;
}

export function ProjectorAssess({ pub, at, joinUrl }) {
  const left = useLeft({ ...pub, at });
  const url = joinUrl || "";  // the students' link while sharing is on (the hub sends it with the quiz / test)
  let body;
  if (pub.status === "lobby") {
    body = html`<div class="lobby">
      <div class="lobby-side"><p class="eyebrow">${cap(kindName(pub.kind))}${pub.title ? ` · ${pub.title}` : ""}</p>
        <h1>Join the ${kindName(pub.kind)}</h1><p class="sub">Scan, then enter your name and roll no.</p><${JoinCode} url=${url} /></div>
      <div class="lobby-people"><div class="lobby-count"><b>${pub.joined}</b><span>${pub.joined === 1 ? "student" : "students"} joined</span></div>
        ${pub.joined ? html`<ul class="names">${(pub.names || []).slice(-40).map((n) => html`<li key=${n}>${n}</li>`)}</ul>`
          : html`<p class="waiting"><span></span><span></span><span></span> Waiting for students</p>`}</div>
    </div>`;
  } else if (pub.kind === "quiz" && pub.question) {
    if (pub.status === "finished") {
      body = html`<div class="final"><p class="eyebrow">Final results</p><h1>${pub.title || "Quiz"}</h1>
        <${Podium} rows=${pub.leaderboard} /><${Leaderboard} rows=${(pub.leaderboard || []).slice(3)} limit=${7} /></div>`;
    } else {
      const reveal = pub.step === "reveal";
      body = html`<div class=${"round" + (reveal ? " is-reveal" : "")}>
        <header><span class="eyebrow">Question ${pub.index + 1} of ${pub.total}</span>
          ${!reveal && html`<${TimerRing} left=${left} total=${pub.seconds} paused=${pub.paused} size="lg" />`}</header>
        <h2 class="q" key=${pub.question.id}>${pub.question.text}</h2>
        <div class="round-body"><${OptionGrid} question=${pub.question} answer=${pub.answer} distribution=${pub.distribution} />
          ${reveal && html`<aside class="side-board"><p class="eyebrow">Leaderboard</p><${Leaderboard} rows=${pub.leaderboard} limit=${5} /></aside>`}</div>
        <footer><span class="answered"><b>${pub.answered}</b> of ${pub.joined} answered</span>
          ${pub.held && html`<span class="held">Next question when the teacher is ready</span>`}</footer>
      </div>`;
    }
  } else if (pub.kind === "test") {
    const done = pub.status === "finished";
    const frac = pub.joined ? pub.submitted / pub.joined : 0;
    body = html`<div class="test-proj">
      <div class="test-main"><p class="eyebrow">Test${pub.title ? ` · ${pub.title}` : ""}</p><h1>${done ? "Test over" : "Time left"}</h1>
        ${!done && html`<${TimerRing} left=${left} total=${pub.minutes * 60} paused=${pub.paused} size="xl" />`}
        <div class="submitted"><div class="bar"><i style=${{ width: `${100 * frac}%` }}></i></div>
          <p><b>${pub.submitted}</b> of ${pub.joined} submitted</p></div></div>
      ${!done && html`<div class="late"><p class="sub">Not joined yet?</p><${JoinCode} url=${url} small /></div>`}
    </div>`;
  }
  return html`<div class=${`assess-proj kind-${pub.kind}`}>${body}${pub.paused && html`<div class="paused-badge"><${PauseIcon} /> Paused</div>`}</div>`;
}

// ---- the student's page -------------------------------------------------------------------------------------
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k) || "null"); } catch (e) { return null; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode: no rejoin */ } },
  del(k) { try { localStorage.removeItem(k); } catch (e) { /* ignore */ } },
};

const ME_KEY = "copilot-assess:me";  // this browser's last name + roll number (no token: a new quiz is a new join)

async function call(path, body, token) {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...body, token }) }
    : { headers: { "X-Assess-Token": token || "" }, cache: "no-store" });
  let data = {};
  try { data = await r.json(); } catch (e) { /* empty */ }
  if (!r.ok) throw new Error(data.error || `error ${r.status}`);
  return data;
}

export function StudentAssess({ pub, at, onHide }) {  // onHide: "Back to the lecture" once it ended
  const key = `copilot-assess:${pub.id}`;
  const [saved, setSaved] = useState(() => store.get(key));
  const [view, setView] = useState(null);  // the server's student_view
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const token = saved && saved.token;
  const refresh = async () => {
    if (!token) return;
    try { setView(await call("/api/assess/me", null, token)); setError(""); }
    catch (e) {
      if (/join first/i.test(e.message)) { store.del(key); setSaved(null); setView(null); }
      else setError(e.message);
    }
  };
  // what changes the student's own screen (not every classmate's answer)
  const phase = `${pub.status}|${pub.index}|${pub.step}|${pub.paused}|${pub.held}`;
  useEffect(() => { refresh(); }, [pub.id, phase, token]);

  const me = view && view.me;
  const a = { ...pub, at };
  let body;
  if (!me) {
    body = pub.status === "finished"
      ? html`<div class="as-card center"><h1>The ${kindName(pub.kind)} is over</h1>
          ${pub.kind === "quiz" && html`<${Leaderboard} rows=${pub.leaderboard} limit=${10} />`}
          <button class="as-ghost" onClick=${onHide}>Back to the lecture</button></div>`
      : html`<${JoinForm} pub=${pub} saved=${saved} busy=${busy} error=${error} onJoin=${async (name, roll) => {
          setBusy(true); setError("");
          try {
            const v = await call("/api/assess/join", { name, roll }, token);
            const s = { token: v.me.token, name: v.me.name, roll: v.me.roll };
            store.set(key, s); setSaved(s); setView(v);
            store.set(ME_KEY, { name: s.name, roll: s.roll });  // the next quiz's form starts filled in
          } catch (e) { setError(e.message); }
          setBusy(false);
        }} />`;
  } else if (pub.status === "lobby") {
    body = html`<div class="as-card center lobby-me"><div class="as-pulse"><span></span><span></span><b>${pub.joined}</b></div>
      <h1>You're in, ${me.name}</h1><p class="as-muted">Roll no. ${me.roll} · waiting for the teacher to start</p></div>`;
  } else if (pub.kind === "quiz") {
    // the student's own state is for this question / step (a new one shows before the refetch lands)
    const fresh = view.index === pub.index && (view.step === pub.step || pub.status === "finished");
    body = html`<${QuizMe} pub=${pub} a=${a} me=${me} fresh=${fresh} onHide=${onHide} onAnswer=${async (i) => {
      setError("");
      try { setView(await call("/api/assess/answer", { qid: pub.question.id, choice: i }, token)); }
      catch (e) { setError(e.message); refresh(); }
    }} />`;
  } else {
    body = html`<${TestMe} pub=${pub} a=${a} view=${view} me=${me} refresh=${refresh} onHide=${onHide}
      setView=${setView} token=${token} />`;
  }
  return html`<div class=${`assess-me kind-${pub.kind}`}>
    ${!me && pub.status !== "finished" && html`<div class="banner" role="status"><b>${cap(kindName(pub.kind))} time</b>
      ${pub.title ? ` · ${pub.title}` : ""}</div>`}
    ${body}
    ${me && error && html`<p class="toast" role="alert">${error}</p>`}
    ${pub.paused && me && pub.status === "running" && html`<div class="paused-veil"><div><${PauseIcon} /><b>Paused by the teacher</b><span>Your answers and time are kept.</span></div></div>`}
  </div>`;
}

function JoinForm({ pub, saved, busy, error, onJoin }) {
  const last = saved || store.get(ME_KEY) || {};
  const [name, setName] = useState(last.name || "");
  const [roll, setRoll] = useState(last.roll || "");
  return html`<form class="as-card join-form" onSubmit=${(e) => { e.preventDefault(); onJoin(name, roll); }}>
    <h1>Join the ${kindName(pub.kind)}</h1>
    <p class="as-muted">${pub.kind === "quiz" ? `${pub.total} questions · ${pub.seconds} s each` : `${pub.total} questions · ${pub.minutes} min`}</p>
    <label>Name<input name="name" autocomplete="name" maxlength="40" required value=${name} onInput=${(e) => setName(e.target.value)} /></label>
    <label>Roll no.<input name="roll" autocomplete="off" maxlength="24" required value=${roll} onInput=${(e) => setRoll(e.target.value)} /></label>
    ${error && html`<p class="as-error" role="alert">${error}</p>`}
    <button class="as-primary big" disabled=${busy || !name.trim() || !roll.trim()}>${busy ? "Joining…" : "Join"}</button>
  </form>`;
}

function QuizMe({ pub, a, me, fresh, onAnswer, onHide }) {
  const left = useLeft(a);
  if (pub.status === "finished") {
    return html`<div class="as-card center final-me"><p class="eyebrow">Final</p>
      <div class="big-rank">${me.rank != null ? html`<span>#</span>${me.rank}` : "–"}</div>
      <p class="score-line"><b>${(me.score || 0).toLocaleString()}</b> points · ${me.correct} of ${pub.total} right</p>
      <${Leaderboard} rows=${pub.leaderboard} me=${me.name} limit=${10} />
      <button class="as-ghost" onClick=${onHide}>Back to the lecture</button></div>`;
  }
  if (!fresh && pub.step === "reveal") return html`<div class="as-card center"><p class="as-muted">Checking…</p></div>`;
  const choice = fresh ? me.choice : null;
  const q = pub.question;
  if (pub.step === "question") {
    if (choice != null) {
      return html`<div class="as-card center locked"><div class=${`lock-shape o${choice}`}><${Shape} i=${choice} /></div>
        <h1>Answer locked in</h1><p class="as-muted">Waiting for the others…</p>
        <${TimerRing} left=${left} total=${pub.seconds} paused=${pub.paused} size="sm" /></div>`;
    }
    return html`<div class="q-screen"><header><span class="eyebrow">Question ${pub.index + 1} of ${pub.total}</span>
        <${TimerRing} left=${left} total=${pub.seconds} paused=${pub.paused} size="sm" /></header>
      <h2 class="q">${q.text}</h2>
      <${OptionGrid} question=${q} onPick=${onAnswer} disabled=${pub.paused || left === 0} /></div>`;
  }
  const right = me.right === true;
  const none = choice == null;
  return html`<div class=${`as-card center verdict ${none ? "is-none" : right ? "is-yes" : "is-no"}`}>
    <div class="verdict-badge">${none ? "–" : right ? html`<${Tick} cls="" />` : html`<${Cross} />`}</div>
    <h1>${none ? "No answer" : right ? "Correct" : "Not quite"}</h1>
    ${right && html`<p class="gain">+${me.points}</p>`}
    <p class="as-muted">Answer: <b class="ink">${LETTERS[pub.answer]} · ${q.options[pub.answer]}</b></p>
    <p class="score-line"><b>${(me.score || 0).toLocaleString()}</b> points${me.rank != null ? ` · #${me.rank} of ${pub.joined}` : ""}</p>
    ${pub.held && html`<p class="as-muted">Next question when the teacher is ready</p>`}</div>`;
}

function TestMe({ pub, a, view, me, refresh, onHide, setView, token }) {
  const left = useLeft(a);
  const paper = (view && view.paper) || [];
  const [cur, setCur] = useState(0);
  const [sel, setSel] = useState(me.answers || {});
  const [confirm, setConfirm] = useState(false);
  const [err, setErr] = useState("");
  const timedOut = useRef(false);
  useEffect(() => { setSel(me.answers || {}); }, [JSON.stringify(me.answers || {})]);
  useEffect(() => {  // time out: the core submits everyone; fetch the result
    if (left === 0 && !me.submitted && !timedOut.current) { timedOut.current = true; setTimeout(refresh, 900); }
  }, [left === 0]);
  if (me.submitted || pub.status === "finished") {
    const key = me.key;
    return html`<div class="as-card result">
      <p class="eyebrow">${me.auto ? "Submitted when the time ran out" : "Submitted"}</p>
      <div class="big-score"><b>${me.score ?? "–"}</b><span>/ ${me.total ?? pub.total}</span></div>
      ${key ? html`<ol class="review">${paper.map((q, n) => {
        const mine = (me.answers || {})[q.id];
        const ok = mine === key[q.id];
        return html`<li key=${q.id} class=${ok ? "is-ok" : "is-bad"}><p><span class="qn">${n + 1}</span>${q.text}</p>
          <p class="ans">${mine == null ? html`<em>Not answered</em>` : html`Your answer: <b>${LETTERS[mine]} · ${q.options[mine]}</b>`}</p>
          ${!ok && html`<p class="ans is-right">Correct: <b>${LETTERS[key[q.id]]} · ${q.options[key[q.id]]}</b></p>`}</li>`;
      })}</ol>` : html`<p class="as-muted center-text">Your teacher will share the answers.</p>`}
      ${pub.status === "finished" ? html`<button class="as-ghost" onClick=${onHide}>Back to the lecture</button>`
        : html`<p class="as-muted center-text">The test is still running for others.</p>`}</div>`;
  }
  if (!paper.length) return html`<div class="as-card center"><p class="as-muted">Loading the test…</p></div>`;
  const q = paper[Math.min(cur, paper.length - 1)];
  const answered = paper.filter((p) => sel[p.id] != null).length;
  const pick = async (i) => {
    const before = sel[q.id];
    setSel({ ...sel, [q.id]: i }); setErr("");
    try { setView(await call("/api/assess/answer", { qid: q.id, choice: i }, token)); }
    catch (e) { setSel((s) => ({ ...s, [q.id]: before })); setErr(e.message); }
  };
  const submit = async () => {
    setConfirm(false);
    try { setView(await call("/api/assess/submit", {}, token)); } catch (e) { setErr(e.message); refresh(); }
  };
  return html`<div class="paper">
    <header class="paper-head"><div><span class="eyebrow">Test</span><b>${answered} of ${paper.length} answered</b></div>
      <${TimerRing} left=${left} total=${pub.minutes * 60} paused=${pub.paused} size="md" /></header>
    <nav class="qnav" aria-label="Questions">${paper.map((p, n) => html`<button key=${p.id}
      class=${(n === cur ? "is-cur " : "") + (sel[p.id] != null ? "is-done" : "")} onClick=${() => setCur(n)}
      aria-label=${`Question ${n + 1}${sel[p.id] != null ? ", answered" : ""}`}>${n + 1}</button>`)}</nav>
    <section class="paper-q" key=${q.id}><p class="eyebrow">Question ${cur + 1} of ${paper.length}</p><h2 class="q">${q.text}</h2>
      <div class="choices" role="radiogroup">${q.options.map((o, i) => html`<button key=${i} role="radio" aria-checked=${sel[q.id] === i}
        class=${"choice" + (sel[q.id] === i ? " is-on" : "")} disabled=${pub.paused} onClick=${() => pick(i)}>
        <span class="letter">${LETTERS[i]}</span><span>${o}</span></button>`)}</div></section>
    ${err && html`<p class="as-error" role="alert">${err}</p>`}
    <footer class="paper-foot"><button class="as-ghost" disabled=${cur === 0} onClick=${() => setCur(cur - 1)}>Previous</button>
      ${cur < paper.length - 1 ? html`<button class="as-ghost" onClick=${() => setCur(cur + 1)}>Next</button>` : html`<span></span>`}
      <button class="as-primary" onClick=${() => setConfirm(true)}>Submit</button></footer>
    ${confirm && html`<div class="confirm" role="dialog" aria-modal="true"><div class="as-card center">
      <h1>Submit the test?</h1><p class="as-muted">${answered < paper.length ? `${paper.length - answered} not answered. ` : ""}You can't change answers after.</p>
      <div class="as-row"><button class="as-ghost" onClick=${() => setConfirm(false)}>Keep working</button>
        <button class="as-primary" onClick=${submit}>Submit</button></div></div></div>`}
  </div>`;
}
