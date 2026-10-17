"""F-013 quality + responsiveness metrics from recorded sessions, zero LLM tokens.

    .venv/Scripts/python tools/v1_eval.py [test1 test2 ... | <session id> ...] [--out f.json] [--compare base.json]
    .venv/Scripts/python tools/v1_eval.py --replay [test1 ...]   # engine only: recorded answers, cues off vs on
    .venv/Scripts/python tools/v1_eval.py --gate [test1 ...]     # gate only: recorded speech timing, call floors
    .venv/Scripts/python tools/v1_eval.py --structure [names] [--out f.json]   # S2: replay (cues on), boundary P/R
                                                                 # vs the annotators, part rate, reused titles
    .venv/Scripts/python tools/v1_eval.py --s3 [names] [--recorded] [--list verbatim,garbage,dup,def,table,formula]
                                         [--out f.json]          # S3: replay (cues on) with the post-model guards
                                                                 # run again (--recorded: as recorded); verbatim
                                                                 # copies, guard lines, garbage, duplicates, bad
                                                                 # definition cards / tables / formulas

With no names: every verify_results/test<N>. A name is a validation test folder (verify_results/<name>) or a session id
under data/sessions. Everything comes from the session's event log (the slides as they ended, the transcript, the
interpretations), so a new simulated run is measured exactly like the recorded live tests.

Per lecture and in total:
  latency      speech end -> first slide patch after the unit's interpretation (median, p90); same as paper_eval
  announce     a spoken topic announcement (understanding.cues) -> first slide whose title carries the announced name
               (median, p90, share never shown within 60 s)
  parts        share of slides that are a "(part N)" continuation
  def_repeat   definition cards whose term repeats the slide title
  compare      comparison announcements heard (cues) and comparison blocks on the slides
  dup_items    items on a slide that repeat another item of the same slide (numbers / powers normalised)
  as_said      units where the coverage guard added sentences "shown as said" (InterpretationReady acts are not
               logged per source, so this counts the guard's log line in terminal_log.txt when it exists)
  images       image blocks, and the same image repeated on another slide
  relations    the model's relation labels
  fallback     units answered by the deterministic fallback
"""
from __future__ import annotations

import json
import re
import sqlite3
import statistics as st
import sys
from collections import Counter
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.core.memory import same_title, titles_match  # noqa: E402
from copilot.understanding.cues import detect_all as detect  # noqa: E402

ANNOUNCE_WINDOW_S = 60.0


def session_dir(name: str) -> Path:
    test = ROOT / "verify_results" / name
    return test if (test / "session" / "session.sqlite").exists() else ROOT / "data" / "sessions" / name


def events(name: str) -> list[tuple[int, float, str, dict]]:
    d = session_dir(name)
    db = sqlite3.connect(d / "session" / "session.sqlite" if (d / "session").exists() else d / "session.sqlite")
    try:
        return [(s, t, ty, json.loads(p)) for s, t, ty, p in
                db.execute("select seq, ts, type, payload from events order by seq")]
    finally:
        db.close()


def pct(a, q) -> float:
    return round(float(np.percentile(a, q)), 2) if len(a) else float("nan")


def _norm(text: str) -> str:
    """Item text for duplicate checks: spoken powers / numbers / units written the same way."""
    t = text.lower().replace("×", "x").replace("−", "-").replace("⁻", "-")
    t = re.sub(r"\bto the power (of )?(minus |negative )?", lambda m: "^-" if m.group(2) else "^", t)
    t = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹]", lambda m: str("⁰¹²³⁴⁵⁶⁷⁸⁹".index(m.group())), t)
    t = re.sub(r"[^a-z0-9^\- ]", " ", t)
    return " ".join(w for w in t.split() if w not in {"the", "a", "an", "of", "is", "are", "and", "in", "its", "it"})


def _similar(a: str, b: str) -> bool:
    wa, wb = set(_norm(a).split()), set(_norm(b).split())
    if len(wa) < 3 or len(wb) < 3:
        return False
    return len(wa & wb) / min(len(wa), len(wb)) >= 0.8


def _texts(spec: dict) -> list[str]:
    out = []
    for b in spec.get("blocks", []):
        t = b.get("type")
        if t == "definition":
            out.append(f"{b['term']}: {b['definition']}")
        elif t in ("points", "example"):
            out += [i["text"] for i in b.get("items", [])]
        elif t == "facts":
            out += [f"{f['label']}: {f.get('value', '')}" for f in b.get("facts", [])]
    return out


def final_slides(ev) -> list[dict]:
    """The deck as it ended: last spec per slide, removed slides dropped, in deck order."""
    specs: dict[str, dict] = {}
    order: list[str] = []
    for _, _, ty, p in ev:
        if ty == "SlidePatch":
            sid = p["slide_id"]
            if p["op"] == "remove":
                specs.pop(sid, None)
            elif p.get("spec"):
                specs[sid] = p["spec"]
        elif ty == "DeckState":
            order = p["slide_ids"]
    return [specs[s] for s in order if s in specs] or list(specs.values())


def latency_rows(ev) -> list[dict]:
    tf = {p["segment"]["id"]: (t, (p.get("stt_latency_ms") or 0) / 1000) for _, t, ty, p in ev if ty == "TranscriptFinal"}
    req = {p["request_id"]: (t, p["segment_ids"]) for _, t, ty, p in ev if ty == "InterpretRequested"}
    patches = [(s, t) for s, t, ty, _ in ev if ty == "SlidePatch"]
    rows = []
    for s, t, ty, p in ev:
        if ty != "InterpretationReady" or p["request_id"] not in req:
            continue
        t_req, segs = req[p["request_id"]]
        shown = next((pt for ps, pt in patches if ps > s), None)
        if shown is None or shown - t > 30:
            continue
        for sid in segs:
            if sid in tf:
                t_text, stt = tf[sid]
                rows.append(dict(fb=bool(p.get("fallback")), wait=t_req - t_text, llm=t - t_req,
                                 total=shown - (t_text - stt)))
    return rows


def _shows(spec: dict, name: str) -> bool:
    title = spec.get("title", "")
    if titles_match(title, name):
        return True
    words = [w for w in re.findall(r"[a-z0-9\-]{4,}", name.lower())]
    tl = title.lower()
    return bool(words) and all(w[:6] in tl for w in words[:2])


def announce_rows(ev) -> list[float | None]:
    """Seconds from the end of an announcement's speech to a slide titled by it (None = not within the window;
    negative = shown while the sentence was still being spoken)."""
    patches = [(t, p["spec"]) for _, t, ty, p in ev if ty == "SlidePatch" and p.get("spec")]
    out: list[float | None] = []
    for _, t, ty, p in ev:
        if ty != "TranscriptFinal":
            continue
        cue = detect(p["segment"]["text"]).of("topic")
        if cue is None:
            continue
        spoken_end = t - (p.get("stt_latency_ms") or 0) / 1000
        spoken_start = spoken_end - max(0.0, p["segment"]["end"] - p["segment"]["start"])
        # with live partials (S1b) the title can be up before the sentence ends: negative values
        hit = next((pt for pt, spec in patches if spoken_start <= pt <= t + ANNOUNCE_WINDOW_S
                    and _shows(spec, cue.name)), None)
        out.append(round(hit - spoken_end, 2) if hit is not None else None)
    return out


def measure(name: str) -> dict:
    ev = events(name)
    slides = final_slides(ev)
    lat = [r["total"] for r in latency_rows(ev)]
    ann = announce_rows(ev)
    shown = [x for x in ann if x is not None]
    defs = rep = cmp_blocks = dups = imgs = 0
    seen_imgs: Counter = Counter()
    for s in slides:
        base = re.sub(r"^(what is|what are)\s+", "", s.get("title", "").lower()).rstrip("?")
        for b in s.get("blocks", []):
            if b.get("type") == "definition":
                defs += 1
                if titles_match(b["term"], base) or _norm(b["term"]) in _norm(base) or _norm(base) in _norm(b["term"]):
                    rep += 1
            elif b.get("type") == "comparison":
                cmp_blocks += 1
            elif b.get("type") == "image":
                imgs += 1
                seen_imgs[b.get("src") or b.get("url") or b.get("title", "")] += 1
        texts = _texts(s)
        dups += sum(1 for i, a in enumerate(texts) if any(_similar(a, b) for b in texts[:i]))
    interp = [p for _, _, ty, p in ev if ty == "InterpretationReady"]
    rel = Counter(p["interpretation"].get("relation", "") for p in interp)
    cmp_cues = sum(1 for _, _, ty, p in ev if ty == "TranscriptFinal" and detect(p["segment"]["text"]).of("compare"))
    log = session_dir(name) / "terminal_log.txt"
    as_said = log.read_text(encoding="utf-8", errors="replace").count("model left out") if log.exists() else None
    parts = sum(1 for s in slides if s.get("part"))
    return dict(
        name=name, slides=len(slides), units=len(interp),
        latency_median=pct(lat, 50), latency_p90=pct(lat, 90),
        announcements=len(ann), announce_median=pct(shown, 50), announce_p90=pct(shown, 90),
        announce_missed=sum(1 for x in ann if x is None),
        parts=parts, part_rate=round(parts / len(slides), 3) if slides else 0.0,
        definitions=defs, def_repeat=rep, compare_cues=cmp_cues, compare_blocks=cmp_blocks,
        dup_items=dups, as_said=as_said, images=imgs, image_repeats=sum(c - 1 for c in seen_imgs.values() if c > 1),
        fallback=sum(1 for p in interp if p.get("fallback")), relations=dict(rel),
        _lat=lat, _ann=ann,
    )


def total(rows: list[dict]) -> dict:
    lat = [x for r in rows for x in r["_lat"]]
    ann = [x for r in rows for x in r["_ann"]]
    shown = [x for x in ann if x is not None]
    s = lambda k: sum(r[k] or 0 for r in rows)  # noqa: E731
    rel: Counter = Counter()
    for r in rows:
        rel.update(r["relations"])
    return dict(
        name="TOTAL", lectures=len(rows), slides=s("slides"), units=s("units"),
        latency_median=pct(lat, 50), latency_p90=pct(lat, 90),
        announcements=len(ann), announce_median=pct(shown, 50), announce_p90=pct(shown, 90),
        announce_missed=sum(1 for x in ann if x is None),
        parts=s("parts"), part_rate=round(s("parts") / max(1, s("slides")), 3),
        definitions=s("definitions"), def_repeat=s("def_repeat"),
        def_repeat_rate=round(s("def_repeat") / max(1, s("definitions")), 3),
        compare_cues=s("compare_cues"), compare_blocks=s("compare_blocks"), dup_items=s("dup_items"),
        as_said=s("as_said"), images=s("images"), image_repeats=s("image_repeats"), fallback=s("fallback"),
        relations=dict(rel),
    )


# ---------------------------------------------------------------------------------------------- engine replay
def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def _guard_act(it, lines) -> int:
    """Index of the coverage guard's act in a recorded interpretation (-1 = none): the last act, an explanation
    whose every point is a spoken sentence of the unit as the guard tidies it."""
    from copilot.understanding.interpreter import _LEAD_FILLERS
    from difflib import SequenceMatcher

    if not it.acts:
        return -1
    a = it.acts[-1]
    if a.act != "explanation" or a.added or not a.items.points or a.items != a.items.model_copy(
            update={"points": a.items.points}):
        return -1
    sents = [_words(_LEAD_FILLERS.sub("", s))[:30] for l in lines
             for s in re.split(r"(?<=[.!?])\s+", " ".join(l.text.split()))]
    ok = all(any(SequenceMatcher(None, _words(p), s).ratio() >= 0.95 for s in sents) for p in a.items.points)
    return len(it.acts) - 1 if ok else -1


def rerun_guards(it, lines, slide_context: str, state, fallback: bool):
    """The recorded model answer through the CURRENT post-model guards (0 tokens): the recorded coverage-guard act
    is removed and the guard runs again; a fallback unit is interpreted again by the current fallback. Returns the
    interpretation and the texts the guard added."""
    from copilot.understanding import interpreter as I

    if fallback:
        return I.fallback_interpretation(state, lines), []
    g = _guard_act(it, lines)
    base = it.model_copy(update={"acts": [a for i, a in enumerate(it.acts) if i != g]}) if g >= 0 else it
    if hasattr(I, "_strip_meta_notes"):  # F-013 S3
        base = I._strip_meta_notes(base)
        base = base.model_copy(update={"concerns": [c for c in base.concerns if not (
            I.problem(c.right) == "meta" or I.problem(c.suggested_correction) == "meta")]})
    out = I._cover_dropped_sentences(base, lines, slide_context)
    added = [p for a in out.acts[len(base.acts):] for p in a.items.points]
    return out, added


async def replay(name: str, cues: bool, setup=None, guards: bool = False) -> dict:
    """The recorded transcript cues + interpretations, on their recorded clock, through the current presentation
    engine (0 tokens). Measures what the engine alone changes; the gate / LLM timing stays as recorded.
    guards: the recorded answers also go through the current post-model guards again (`rerun_guards`)."""
    from copilot.core.bus import EventBus
    from copilot.core.events import ConceptSignal, InterpretationReady, SlidePatch
    from copilot.core.state import LectureSetup, LectureStateStore
    from copilot.presentation.deck import Deck
    from copilot.presentation.engine import PresentationEngine, PresentationSettings

    class Clock:
        t = 0.0

        def __call__(self):
            return self.t

    ev = events(name)
    bus = EventBus()
    store = LectureStateStore(bus, "eval", setup or LectureSetup())
    store.attach()
    deck = Deck(bus)
    deck.attach()
    clock = Clock()
    eng = PresentationEngine(bus, store, deck, PresentationSettings(provisional=False, title_slide=False, cues=cues),
                             clock=clock)
    eng.attach()
    patches: list[tuple[int, float, str, dict]] = []
    t0 = next(t for _, t, ty, _ in ev if ty in ("ConceptSignal", "InterpretationReady"))

    utt = {p["segment"]["id"]: i for i, p in enumerate((p for _, _, ty, p in ev if ty == "TranscriptFinal"), 1)}
    opened: dict[str, int] = {}  # slide id -> utterance number of the line that opened it (boundary scoring)
    cause: list[str] = []         # segments of the event being published (a cue line, or a unit's lines)

    async def tap(e):
        patches.append((0, t0 + clock.t, "SlidePatch", {"spec": e.spec if isinstance(e.spec, dict) or e.spec is None else e.spec.model_dump()}))
        lines = sorted(utt[x] for x in cause if x in utt)
        if e.op == "add" and lines:
            opened.setdefault(e.slide_id, lines[0])
    bus.subscribe("eval", tap, [SlidePatch])
    text = {p["segment"]["id"]: p["segment"]["text"] for _, _, ty, p in ev if ty == "TranscriptFinal"}

    async def release():
        async with eng._lock:
            while eng._pending and eng._dwell_ok():
                await eng._add_to_deck(eng._pending.pop(0))
            await eng._expire_cues()
        await bus.drain()

    from copilot.understanding.gate import BufferedLine

    seg = {p["segment"]["id"]: p["segment"] for _, _, ty, p in ev if ty == "TranscriptFinal"}
    flags: dict[str, tuple[bool, bool]] = {}
    slide_context = req_context = ""
    guard_texts: list[str] = []
    for _, t, ty, p in ev:
        if ty == "UtteranceClassified":
            flags[p["segment_id"]] = (p.get("maybe_meta", False), p["kind"] == "question_to_class")
        elif ty == "SlideContextChanged":
            slide_context = p["text"]
        elif ty == "InterpretRequested":
            req_context = slide_context
        if ty not in ("ConceptSignal", "InterpretationReady"):
            continue
        clock.t = t - t0
        if ty == "InterpretationReady":
            from copilot.core.interpretation import Interpretation
            lines = [BufferedLine(s, seg[s]["text"], seg[s]["start"], seg[s]["end"], *flags.get(s, (False, False)))
                     for s in p["segment_ids"] if s in seg]
            rec = Interpretation.model_validate(p["interpretation"])
            if guards:
                it, added = rerun_guards(rec, lines, req_context, store.snapshot(), bool(p.get("fallback")))
                guard_texts += added
                p = {**p, "interpretation": it.model_dump()}
            elif not p.get("fallback") and (g := _guard_act(rec, lines)) >= 0:
                guard_texts += rec.acts[g].items.points
        await release()
        p = {k: v for k, v in p.items() if k not in ("id", "ts", "session_id")}
        cause[:] = [p["segment_id"]] if ty == "ConceptSignal" else p.get("segment_ids", [])
        if ty == "ConceptSignal":
            c = detect(text.get(p["segment_id"], ""))
            topic, compare, lst = c.of("topic"), c.of("compare"), c.of("list")
            p.update(announce=(compare.name if compare else "") or (topic.name if topic else ""),
                     announce_rule="compare" if compare else topic.rule if topic else "",
                     compare=list(compare.items) if compare else [], list_head=lst.name if lst else "",
                     list_items=list(lst.items) if lst else [], list_count=lst.count if lst else 0, item=c.item)
            p["boundary"] = p.get("boundary") or bool(p["announce"])
            await bus.publish(ConceptSignal.model_validate(p))
        else:
            await bus.publish(InterpretationReady.model_validate(p))
        await bus.drain()
        lines = sorted(utt[x] for x in cause if x in utt)
        for sp in eng._pending:  # a slide waiting for the dwell time was opened by this event's lines
            if lines:
                opened.setdefault(sp.id, lines[0])
    for _ in range(90):
        clock.t += 1.0
        await release()
    await eng.flush_pending()
    await eng.stop()
    tf = [e for e in ev if e[2] == "TranscriptFinal"]
    ann = announce_rows(sorted(tf + patches, key=lambda e: e[1]))
    shown = [x for x in ann if x is not None]
    slides = deck.slides
    parts = sum(1 for s in slides if s.part)
    return dict(name=name, slides=len(slides), part_rate=round(parts / max(1, len(slides)), 3),
                announcements=len(ann), announce_median=pct(shown, 50), announce_p90=pct(shown, 90),
                announce_missed=sum(1 for x in ann if x is None), cue_slides=eng.stats.ops.get("cue_slide", 0),
                _ann=ann, _deck=slides, _opened=opened, _outline=store.snapshot().outline, _guard=guard_texts,
                _sents=[_words(x) for t in text.values() for x in re.split(r"(?<=[.!?])\s+", t)],
                _fallback={p["request_id"] for _, _, ty, p in ev if ty == "InterpretationReady" and p.get("fallback")})


def report_replay(names: list[str]) -> None:
    import asyncio
    import logging
    logging.basicConfig(level=logging.ERROR)
    tot = {False: [], True: []}
    print(f"{'name':8s} {'slides':>13s} {'part_rate':>13s} {'ann_median':>13s} {'ann_missed':>11s} cue_slides")
    for n in names:
        a, b = asyncio.run(replay(n, False)), asyncio.run(replay(n, True))
        tot[False].append(a)
        tot[True].append(b)
        print(f"{n:8s} {a['slides']:>5} -> {b['slides']:<5} {a['part_rate']:>5} -> {b['part_rate']:<5} "
              f"{a['announce_median']:>5} -> {b['announce_median']:<5} {a['announce_missed']:>3} -> "
              f"{b['announce_missed']:<4} {b['cue_slides']}")
    for k in (False, True):
        rows = tot[k]
        ann = [x for r in rows for x in r["_ann"]]
        shown = [x for x in ann if x is not None]
        sl = sum(r["slides"] for r in rows)
        print(f"{'cues on ' if k else 'cues off'}: slides {sl}, announcements {len(ann)}, title shown median "
              f"{pct(shown, 50)} s, p90 {pct(shown, 90)} s, never {sum(1 for x in ann if x is None)}")


# ---------------------------------------------------------------------------------------------- structure (S2)
def structure_row(name: str, r: dict, anns: dict | None) -> dict:
    """Boundaries of a replayed deck scored like eval_sheets.score (overflow parts are not boundaries), plus the
    structure measures of F-013 S2: part rate, a title reused for a later, separate run of slides, outline depth."""
    from eval_sheets import ANNOTATORS, boundary_prf

    bounds, prev, runs = set(), None, []
    for s in r["_deck"]:
        if s.origin != "lecture" or s.layout == "title":
            continue
        overflow = (s.part or 1) > 1 and prev is not None and s.facet == prev.facet
        if not overflow and s.id in r["_opened"]:
            bounds.add(r["_opened"][s.id])
        if prev is None or s.title != prev.title:
            runs.append(s.title)
        prev = s
    reused = sum(1 for i, t in enumerate(runs) if any(same_title(t, u) for u in runs[:i]))
    children = sum(1 for s in r["_deck"] if s.parent)  # slides placed under a parent subtopic
    row = dict(name=name, slides=r["slides"], part_rate=r["part_rate"], bounds=len(bounds), reused_titles=reused,
               child_slides=children)
    if anns:
        vals = np.array([boundary_prf(anns[w], sorted(bounds)) for w in ANNOTATORS if anns.get(w)])
        row.update(P=round(float(vals[:, 0].mean()), 3), R=round(float(vals[:, 1].mean()), 3),
                   F1=round(float(vals[:, 2].mean()), 3))
    return row


def report_structure(names: list[str], out: Path | None = None) -> None:
    """S2 structure check on recorded answers (0 tokens): the annotated lectures (eval_sheets.ANNOTATE) by default."""
    import asyncio
    import logging

    sys.path.insert(0, str(ROOT / "tools"))
    from eval_sheets import ANNOTATE, ANNOTATORS, EVAL, read_workbook

    logging.basicConfig(level=logging.ERROR)
    rows = []
    for n in names or ANNOTATE:
        if not (session_dir(n) / "session").exists() and not (session_dir(n) / "session.sqlite").exists():
            continue
        a = {w: (read_workbook(EVAL / "annotation" / w / f"{n}_{w}.xlsx") or {}).get("bounds") for w in ANNOTATORS}
        rows.append(structure_row(n, asyncio.run(replay(n, True)), a if any(a.values()) else None))
    cols = ["slides", "bounds", "P", "R", "F1", "part_rate", "reused_titles", "child_slides"]
    print("name    " + " ".join(f"{c[:9]:>9}" for c in cols))
    for r in rows:
        print(f"{r['name'][:7]:7s} " + " ".join(f"{str(r.get(c, '')):>9}" for c in cols))
    scored = [r for r in rows if "P" in r]
    tot = dict(lectures=len(rows), scored=len(scored),
               P=round(float(np.mean([r["P"] for r in scored])), 3) if scored else None,
               R=round(float(np.mean([r["R"] for r in scored])), 3) if scored else None,
               F1=round(float(np.mean([r["F1"] for r in scored])), 3) if scored else None,
               slides=sum(r["slides"] for r in rows),
               part_rate=round(sum(r["part_rate"] * r["slides"] for r in rows) / max(1, sum(r["slides"] for r in rows)), 3),
               reused_titles=sum(r["reused_titles"] for r in rows),
               child_slides=sum(r["child_slides"] for r in rows))
    print("total:", tot)
    if out is not None:
        out.write_text(json.dumps(dict(total=tot, lectures=rows), indent=1), encoding="utf-8")
        print(f"-> {out}")


# ---------------------------------------------------------------------------------------------- S3 representation
# Fixed measuring rules, independent of the code under test (the garbage gate in the app may differ); every flagged
# line is listed with --list so the counts can be checked by hand.
_M_META = re.compile(r"\[[^\]]*[a-z]{4,}[^\]]*\]|\bmis-?heard\b|\bunclear\b|\binaudible\b", re.I)
_M_OPENER = re.compile(r"^(?:recall that|as (?:previously|already|we) (?:discussed|mentioned|saw)|before discussing|"
                       r"in today'?s world|that'?s it|there you (?:go|went)|let'?s|let us|recently|again|sometimes|"
                       r"however|finally|thus|therefore|hence|so|well|okay|now)\b(?!-)|\b(?:will be discussed|"
                       r"we (?:will|shall) (?:see|discuss|learn))\b", re.I)
_M_YOU = re.compile(r"\b(?:you|your|we|our|us)\b|(?<!War )(?<!Type )\bI\b(?! \()")
_M_CODE = re.compile(r"\b(?:semicolon|inverted comma|bracket (?:open|close)|(?:round|curly|square) bracket|"
                     r"end ?module|begin end)\b", re.I)
_M_VAGUE = re.compile(r"^(?:it|this|that|these|those|they|he|she)\b(?! (?:is|are) (?:called|known))", re.I)
_M_GREEK = "αβγδεζηθικλμνξπρστυφχψωΔΘΛΞΠΣΦΨΩ"


def m_garbage(text: str) -> str:
    """Why a slide line is not slide text ("" = fine). "vague" (a bare pronoun subject) is counted apart: it reads
    badly on a slide but is not garbage."""
    t = text.strip()
    if _M_META.search(t):
        return "meta"
    if _M_CODE.search(t):
        return "spoken code"
    if _M_OPENER.search(t):
        return "opener"
    if _M_YOU.search(t):
        return "speaker"
    if re.match(r"^[A-Z][a-z]+, (?:as|the|in|while|this|it|a)\b", t):
        return "glued heading"
    return ""


def m_vague(text: str) -> bool:
    return bool(_M_VAGUE.match(text.strip())) and len(text.split()) >= 4


_UNITS = [(r"centimet(?:er|re)s?", "cm"), (r"millimet(?:er|re)s?", "mm"), (r"kilomet(?:er|re)s?", "km"),
          (r"met(?:er|re)s?", "m"), (r"kilograms?", "kg"), (r"grams?", "g"), (r"degrees? (?:celsius|centigrade)", "c"),
          (r"percent|per cent", "%"), (r"coulombs?", "c"), (r"seconds?", "s"), (r"hertz", "hz")]


_SUP = {c: d for c, d in zip("⁰¹²³⁴⁵⁶⁷⁸⁹⁻", "0123456789-")}


def m_norm(text: str) -> str:
    t = re.sub(r"[⁰¹²³⁴⁵⁶⁷⁸⁹⁻]+", lambda m: " to the power " + "".join(_SUP[c] for c in m.group()), text)
    t = t.replace("°", " ").replace("%", " percent ").replace("−", "-").replace("~", " ")
    t = re.sub(r"\b(?:minus|negative)\s+(?=\d)", "-", t.lower())
    t = re.sub(r"\bto the power (?:of )?", "^", t)
    t = re.sub(r"(?<=\d)\s*\^\s*", "^", t)
    t = re.sub(r"(?<=\d)\s+(?:into|x|times|×)\s+(?=\d)", "x", t)
    for a, b in _UNITS:
        t = re.sub(rf"\b{a}\b", b, t)
    return " ".join(w for w in re.findall(r"[a-z0-9^.\-]+", t) if w.strip(".-") and w not in _M_FILLER)


_M_FILLER = {"the", "a", "an", "of", "is", "are", "and", "in", "its", "it", "order", "about", "approximately"}


def m_dup(a: str, b: str) -> bool:
    """The same item twice: one item's words all inside the other's (plurals folded), or nearly the same words."""
    wa, wb = {_fold(w) for w in m_norm(a).split()}, {_fold(w) for w in m_norm(b).split()}
    if len(wa) < 3 or len(wb) < 3:
        return False
    return wa <= wb or wb <= wa or len(wa & wb) / len(wa | wb) >= 0.75


def _fold(w: str) -> str:
    return w[:-2] if w.endswith("es") and len(w) > 4 else w[:-1] if w.endswith("s") and len(w) > 3 else w


def m_term_repeats(title: str, term: str) -> bool:
    """The term says what the title says (plural, a bracketed acronym, "What is ...?")."""
    strip = lambda s: [_fold(w) for w in _words(re.sub(r"\([^)]*\)", " ", s)) if w not in ("what", "is", "are", "a", "an", "the")]  # noqa: E731
    a, b = strip(title), strip(term)
    return bool(a) and bool(b) and (a == b or f" {' '.join(b)} " in f" {' '.join(a)} ")


def display_hides_term(title: str, term: str) -> bool:
    """web/shared/slide.js titleNames (F-013 S3: plurals folded, a bracketed acronym ignored). Before S3 the display
    needed the exact words; that figure is in s3_before.json (measured on the S2 code)."""
    def fold(w: str) -> str:
        if len(w) > 4 and re.search(r"(ses|xes|ches|shes)$", w):
            return w[:-2]
        return w[:-1] if len(w) > 3 and w.endswith("s") and not re.search(r"(ss|us|is)$", w) else w
    a = " ".join(fold(w) for w in _words(re.sub(r"\([^)]*\)", " ", title)))
    b = " ".join(fold(w) for w in _words(re.sub(r"\([^)]*\)", " ", term)))
    return bool(b) and f" {b} " in f" {a} "


_NOT_DEF = re.compile(r"^(?:was|were|has|had|have|can|could|will|would|did|does)\b", re.I)


def m_formula_bad(latex: str, spoken: str) -> str:
    if not latex:
        return "not rendered"
    if re.search(rf"\\text\{{[^}}]*[{_M_GREEK}]", latex):
        return "greek as text"
    if re.search(r"\b(?:s i n|c o s|t a n|l o g|l n)\b", latex):
        return "function split"
    return ""


def s3_row(name: str, r: dict) -> dict:
    """S3 measures of one replayed deck: verbatim copies, guard lines shown, garbage lines, duplicates, definition
    cards that repeat the title or are not definitions, unusable tables, formulas that do not render properly."""
    from difflib import SequenceMatcher

    guard = {" ".join(_words(g)) for g in r["_guard"]}
    sents = [s for s in r["_sents"] if len(s) >= 6]
    out = Counter()
    lists: dict[str, list[str]] = {k: [] for k in ("verbatim", "garbage", "dup", "def", "table", "formula")}
    for spec in r["_deck"]:
        s = spec.model_dump()
        title = s["title"]
        texts, other = [], []  # other: definitions / facts, only for the duplicate check
        defs = [b for b in s["blocks"] if b["type"] == "definition"]
        for b in s["blocks"]:
            t = b["type"]
            if t in ("points",):
                texts += [i["text"] for i in b["items"]]
            elif t == "callout":
                texts.append(b["text"])
            elif t == "example":
                texts.append(b["text"])
            elif t == "facts":
                other += [f"{f['label']}: {f['value']}" for f in b["facts"]]
            elif t == "definition":
                other.append(f"{b['term']}: {b['definition']}")
                texts += [n["text"] for n in b["notes"]]
                out["definitions"] += 1
                lone = len(defs) == 1
                why = ("repeats title" if lone and m_term_repeats(title, b["term"]) and not display_hides_term(
                    title, b["term"]) else
                       "term twice" if b["definition"].lower().startswith(b["term"].lower() + ":") else
                       "not a definition" if _NOT_DEF.match(b["definition"]) or b["definition"].count(";") >= 2 else "")
                if why:
                    out["def_bad"] += 1
                    lists["def"].append(f"{name} {why}: {title!r} | {b['term']} :: {b['definition'][:80]}")
            elif t == "comparison":
                out["tables"] += 1
                heads = [c["heading"] for c in b["columns"]]
                why = ("empty heading" if any(not h for h in heads) else "one column" if len(heads) < 2 else
                       "no rows" if not b["rows"] else
                       "prefixed cells" if any(re.match(r"^[A-Z]{2,6}:", c) for row in b["rows"] for c in row["cells"])
                       else "")
                if why:
                    out["tables_bad"] += 1
                    lists["table"].append(f"{name} {why}: {title!r} {heads}")
            elif t == "formula":
                out["formulas"] += 1
                why = m_formula_bad(b["latex"], b["spoken"])
                if why:
                    out["formulas_bad"] += 1
                    lists["formula"].append(f"{name} {why}: {b['spoken']!r} -> {b['latex']!r}")
        for i, x in enumerate(texts):
            out["items"] += 1
            w = _words(x)
            if " ".join(w) in guard:
                out["guard_shown"] += 1
            if len(w) >= 8 and any(SequenceMatcher(None, w, y).ratio() >= 0.85 for y in sents
                                   if abs(len(y) - len(w)) < len(w)):
                out["verbatim"] += 1
                lists["verbatim"].append(f"{name} {'G' if ' '.join(w) in guard else 'M'}: {x[:120]}")
            if m_vague(x):
                out["vague"] += 1
            why = m_garbage(x)
            if why:
                out["garbage"] += 1
                lists["garbage"].append(f"{name} {why}: {x[:120]}")
            twin = next((y for y in other + texts[:i] if m_dup(x, y)), None)
            if twin is not None:
                out["dup_items"] += 1
                lists["dup"].append(f"{name}: {twin[:70]} || {x[:70]}")
    return dict(name=name, slides=r["slides"], **out, _lists=lists)


def report_s3(names: list[str], out: Path | None, show: str = "", guards: bool = True) -> None:
    """S3 check on recorded answers (0 tokens): the decks rebuilt by the current engine, with the post-model guards
    run again (guards=True), every test by default."""
    import asyncio
    import logging

    logging.basicConfig(level=logging.ERROR)
    keys = ["slides", "items", "verbatim", "guard_shown", "garbage", "vague", "dup_items", "definitions", "def_bad", "tables",
            "tables_bad", "formulas", "formulas_bad"]
    rows = [s3_row(n, asyncio.run(replay(n, True, guards=guards))) for n in names]
    print("name    " + " ".join(f"{k[:11]:>11}" for k in keys))
    for r in rows:
        print(f"{r['name'][:7]:7s} " + " ".join(f"{r.get(k, 0):>11}" for k in keys))
    tot = {k: sum(r.get(k, 0) for r in rows) for k in keys}
    tot.update(verbatim_rate=round(tot["verbatim"] / max(1, tot["items"]), 3),
               garbage_rate=round(tot["garbage"] / max(1, tot["items"]), 3))
    print("total:", tot)
    for k in [x for x in show.split(",") if x]:
        print(f"\n--- {k}")
        for r in rows:
            for line in r["_lists"][k]:
                print(" ", line)
    if out is not None:
        out.write_text(json.dumps(dict(total=tot, lectures=[{k: v for k, v in r.items() if k != "_lists"} for r in rows],
                                       lists={k: [x for r in rows for x in r["_lists"][k]] for k in rows[0]["_lists"]}
                                       if rows else {}), indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"-> {out}")


# ---------------------------------------------------------------------------------------------- gate replay
GATE_TICK = 0.05
CALL_S = 1.9  # median LLM call (e2e_d2)


def gate_replay(name: str, floor_s: float, announce_cut: bool) -> dict:
    """The recorded transcript (lecture times, STT latencies, boundary signals) through the gate on a simulated clock,
    the way UnderstandingService._maybe_interpret runs it: VAD silence, the call-rate floor with sealing, one call in
    flight. Returns how long each line waited before its unit was sent, calls per minute and the units that mixed
    lines from before and after an announcement."""
    from copilot.understanding.gate import BufferedLine, DiscourseBuffer, Gate, GateConfig
    from copilot.understanding.service import vad_silence

    ev = events(name)
    content = {p["segment_id"] for _, _, ty, p in ev if ty == "UtteranceClassified" and p["kind"] == "content"}
    bound = {p["segment_id"] for _, _, ty, p in ev if ty == "ConceptSignal" and p.get("boundary")}
    segs = [p for _, _, ty, p in ev if ty == "TranscriptFinal" and p["segment"]["id"] in content]
    rows = [(s["segment"]["text"], s["segment"]["start"], s["segment"]["end"], s.get("stt_latency_ms", 600))
            for s in segs]
    ann = {i for i, r in enumerate(rows) if detect(r[0]).of("topic") or detect(r[0]).of("compare")}
    bnd = {i for i, s in enumerate(segs) if s["segment"]["id"] in bound} | ann
    cfg = GateConfig()
    gate, buf = Gate(cfg), DiscourseBuffer(min_unit_words=cfg.min_unit_words, whole_sentences=True)
    arrivals = sorted((e + 0.4 + lat / 1000, i) for i, (_, _, e, lat) in enumerate(rows))
    arrived: dict[int, float] = {}
    waits: list[float] = []
    calls: list[float] = []
    straddle = 0
    last_voice = None
    last_arrival = last_end = busy_until = 0.0
    last_call = None
    pending = None
    t, k = 0.0, 0
    end_t = (arrivals[-1][0] + 40) if arrivals else 0
    while t < end_t:
        if any(s + 0.2 <= t <= e - 0.2 for _, s, e, _ in rows[max(0, k - 2):k + 2]):
            last_voice = t
        while k < len(arrivals) and arrivals[k][0] <= t:
            i = arrivals[k][1]
            text, s0, e0, _ = rows[i]
            buf.add(BufferedLine(str(i), text, s0, e0), boundary=i in bnd, announce=announce_cut and i in ann)
            arrived[i] = t
            last_end, last_arrival = max(last_end, e0), t
            k += 1
        if pending is None and t >= busy_until and not buf.empty:
            now = last_end + (t - last_arrival)
            silence = vad_silence(t, last_voice, last_arrival) if last_voice is not None else None
            reason = gate.check(buf, now, silence, k == len(arrivals) and t > arrivals[-1][0] + 20)
            if reason:
                wait = 0.0 if last_call is None else last_call + floor_s - t
                if wait > 0 and reason != "words":
                    buf.seal()
                pending = t + max(0.0, wait)
        if pending is not None and t >= pending:
            lines = buf.take(cfg.buffer_cap_tokens)
            ids = [int(l.segment_id) for l in lines]
            waits += [t - arrived[i] for i in ids]
            if any(i in ann and pos > 0 and sum(len(rows[j][0].split()) for j in ids[:pos]) >= 3
                   for pos, i in enumerate(ids)):
                straddle += 1
            calls.append(t)
            last_call, busy_until, pending = t, t + CALL_S, None
        t = round(t + GATE_TICK, 4)
    minutes = max((rows[-1][2] if rows else 0) / 60, 1e-9)
    per_min = [sum(1 for c in calls if a <= c < a + 60) for a in calls]
    return dict(waits=waits, calls=len(calls), per_min=len(calls) / minutes, max_per_min=max(per_min or [0]),
                straddle=straddle, minutes=minutes)


def report_gate(names: list[str]) -> None:
    variants = [("now: floor 8 s", 8.0, False), ("floor 8 s + cut", 8.0, True), ("floor 5 s + cut", 5.0, True),
                ("floor 4 s + cut", 4.0, True), ("floor 3 s + cut", 3.0, True)]
    for label, floor, cut in variants:
        res = [gate_replay(n, floor, cut) for n in names]
        w = [x for r in res for x in r["waits"]]
        mins = sum(r["minutes"] for r in res)
        print(f"{label:16s} wait median {pct(w, 50):5.2f} s  p90 {pct(w, 90):5.2f} s  calls/min "
              f"{sum(r['calls'] for r in res) / mins:4.2f} (max {max(r['max_per_min'] for r in res)})  "
              f"units mixing an announcement {sum(r['straddle'] for r in res)}")


COLS = ["slides", "latency_median", "latency_p90", "announcements", "announce_median", "announce_missed",
        "part_rate", "def_repeat", "compare_cues", "compare_blocks", "dup_items", "as_said", "images",
        "image_repeats", "fallback"]


def main(argv: list[str]) -> None:
    out = None
    if "--gate" in argv:
        argv.remove("--gate")
        report_gate(argv or sorted((p.name for p in (ROOT / "verify_results").glob("test*") if p.is_dir()),
                                   key=lambda n: int(re.sub(r"\D", "", n) or 0)))
        return
    if "--s3" in argv:
        argv.remove("--s3")
        show, guards = "", "--recorded" not in argv
        argv = [a for a in argv if a != "--recorded"]
        if "--list" in argv:
            i = argv.index("--list")
            show = argv[i + 1]
            del argv[i:i + 2]
        if "--out" in argv:
            i = argv.index("--out")
            out = Path(argv[i + 1])
            del argv[i:i + 2]
        report_s3(argv or sorted((p.name for p in (ROOT / "verify_results").glob("test*") if p.is_dir()),
                                 key=lambda n: int(re.sub(r"\D", "", n) or 0)), out, show, guards)
        return
    if "--structure" in argv:
        argv.remove("--structure")
        if "--out" in argv:
            i = argv.index("--out")
            out = Path(argv[i + 1])
            del argv[i:i + 2]
        report_structure(argv, out)
        return
    if "--replay" in argv:
        argv.remove("--replay")
        names = argv or sorted((p.name for p in (ROOT / "verify_results").glob("test*") if p.is_dir()),
                               key=lambda n: int(re.sub(r"\D", "", n) or 0))
        report_replay(names)
        return
    base = None
    if "--out" in argv:
        i = argv.index("--out")
        out = Path(argv[i + 1])
        del argv[i:i + 2]
    if "--compare" in argv:
        i = argv.index("--compare")
        base = json.loads(Path(argv[i + 1]).read_text(encoding="utf-8"))
        del argv[i:i + 2]
    names = argv or sorted((p.name for p in (ROOT / "verify_results").glob("test*") if p.is_dir()),
                           key=lambda n: int(re.sub(r"\D", "", n) or 0))
    rows = [measure(n) for n in names]
    print("name    " + " ".join(f"{c[:10]:>10}" for c in COLS))
    for r in rows + [total(rows)]:
        print(f"{r['name'][:7]:7s} " + " ".join(f"{str(r.get(c, ''))[:10]:>10}" for c in COLS))
    tot = total(rows)
    print("relations:", tot["relations"])
    if base is not None:
        b = base["total"]
        print("\nvs baseline:")
        for k in ("latency_median", "latency_p90", "announce_median", "announce_p90", "announce_missed", "part_rate",
                  "def_repeat_rate", "compare_blocks", "dup_items", "as_said", "image_repeats", "fallback"):
            print(f"  {k:16s} {b.get(k)!s:>10} -> {tot.get(k)!s:>10}")
    if out is not None:
        out.write_text(json.dumps(dict(total=tot, lectures=[{k: v for k, v in r.items() if not k.startswith("_")}
                                                             for r in rows]), indent=1), encoding="utf-8")
        print(f"-> {out}")


if __name__ == "__main__":
    main(sys.argv[1:])
