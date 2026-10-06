"""Old-vs-new interpretation prompt A/B on recorded lecture units (F-007b step 4).

    .venv/Scripts/python tools/prompt_ab.py --dry SESSION[:i,j] ...    # rebuild prompts, 0 tokens
    .venv/Scripts/python tools/prompt_ab.py SESSION[:i,j] ...          # new prompt on gpt-oss-120b (real Groq)
    .venv/Scripts/python tools/prompt_ab.py --old SESSION[:i,j] ...    # the old prompt again (sampling variance)

A recorded session is replayed into a LectureStateStore; at every InterpretRequested the prompt is rebuilt from
that state and the request's transcript lines. The OLD arm is what the model returned live (recorded
InterpretationReady, same model, same prompt — the rebuilt old prompt must match the recorded prompt size). The NEW
arm sends the same user message with the new system prompt through the real Interpreter (same post-processing),
groq_main entries only. Prints validity, agreement, real tokens and both item lists for a truthfulness review;
results → artifacts/prompt_ab/<time>.json.
"""
from __future__ import annotations

import asyncio
import json
import sqlite3
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from copilot.core.bus import EventBus  # noqa: E402
from copilot.core.config import load_config  # noqa: E402
from copilot.core.events import InterpretationReady, InterpretRequested, decode_event  # noqa: E402
from copilot.core.interpretation import Interpretation  # noqa: E402
from copilot.core.state import LectureSetup, LectureState, LectureStateStore  # noqa: E402
from copilot.core.textutil import approx_tokens  # noqa: E402
from copilot.llm.router import build_router  # noqa: E402
from copilot.llm.usage import UsageLedger  # noqa: E402
from copilot.understanding import prompt as P  # noqa: E402
from copilot.understanding.gate import BufferedLine  # noqa: E402
from copilot.understanding.interpreter import Interpreter, InterpreterSettings  # noqa: E402

OUT = ROOT / "artifacts" / "prompt_ab"
STORE_TYPES = {"LifecycleChanged", "TranscriptFinal", "CommandReceived", "InterpretationReady", "SlideContextChanged"}


@dataclass
class Unit:
    session: str
    index: int
    state: LectureState
    lines: list[BufferedLine]
    recorded_tokens: int
    old: Interpretation
    old_provider: str
    old_fallback: bool


async def rebuild(session: str) -> list[Unit]:
    db = sqlite3.connect(ROOT / "data" / "sessions" / session / "session.sqlite")
    rows = db.execute("select type, payload from events order by seq").fetchall()
    store = LectureStateStore(EventBus(), session, LectureSetup())
    segs, kinds, pending, units = {}, {}, {}, []
    for kind, payload in rows:
        ev = decode_event(kind, payload)
        if ev is None:
            continue
        if kind == "TranscriptFinal":
            segs[ev.segment.id] = ev.segment
        elif kind == "UtteranceClassified":
            kinds[ev.segment_id] = ev
        elif isinstance(ev, InterpretRequested):
            state = store.snapshot()
            lines = [BufferedLine(s, segs[s].text, segs[s].start, segs[s].end,
                                  kinds[s].maybe_meta if s in kinds else False,
                                  kinds[s].kind == "question_to_class" if s in kinds else False)
                     for s in ev.segment_ids if s in segs]
            pending[ev.request_id] = (state, lines, ev.prompt_tokens)
        elif isinstance(ev, InterpretationReady) and ev.request_id in pending:
            state, lines, tok = pending.pop(ev.request_id)
            units.append(Unit(session, len(units), state, lines, tok, ev.interpretation, ev.provider, ev.fallback))
        if kind in STORE_TYPES:
            await store._on_event(ev)  # the store's own apply path (single writer), no bus subscribers needed
    return units


def build(u: Unit, visual: bool, settings: InterpreterSettings) -> P.BuiltPrompt:
    saved = P.SYSTEM_PROMPT
    P.SYSTEM_PROMPT = P.system_prompt(visual)  # build_prompt reads the module constant
    try:
        return P.build_prompt(u.state, u.lines, dynamic_budget=settings.dynamic_budget_tokens,
                              total_budget=settings.prompt_budget_tokens)
    finally:
        P.SYSTEM_PROMPT = saved


def items(it: Interpretation) -> list[str]:
    out = []
    for a in it.acts:
        x = a.items
        out += [f"{a.act}:def {x.term}: {x.definition}"] if x.definition else []
        out += [f"{a.act}:{t}" for t in x.points + x.steps + x.examples]
        out += [f"{a.act}:fact {f.label}={f.value}" for f in x.facts]
        out += [f"{a.act}:formula {x.formula.expression}"] if x.formula else []
        out += [f"{a.act}:{c.cause} -> {c.effect}" for c in x.causes]
        out += [f"{a.act}:group {g.label}: {', '.join(g.items)}" for g in x.groups]
    return out


def summary(it: Interpretation) -> dict:
    return {"topic": it.topic, "subtopic": it.subtopic, "relation": it.relation,
            "kinds": sorted({a.act for a in it.acts}), "items": items(it), "concerns": len(it.concerns),
            "visual": it.visual.model_dump() if it.visual else None}


def select(units: list[Unit], spec: str) -> list[Unit]:
    if ":" not in spec:
        return units
    want = {int(x) for x in spec.split(":", 1)[1].split(",")}
    return [u for u in units if u.index in want]


async def main(args: list[str]) -> None:
    dry = "--dry" in args
    resend_old = "--old" in args  # send the OLD prompt again (is a difference the rule or sampling variance?)
    specs = [a for a in args if not a.startswith("--")]
    cfg = load_config()
    settings = InterpreterSettings(**{k: v for k, v in cfg.section("understanding").items()
                                      if k in InterpreterSettings.__dataclass_fields__})
    chosen: list[Unit] = []
    for spec in specs:
        session = spec.split(":")[0]
        units = await rebuild(session)
        for u in select(units, spec):
            old = build(u, False, settings)
            new = build(u, True, settings)
            match = "OK" if old.tokens == u.recorded_tokens else f"MISMATCH (recorded {u.recorded_tokens})"
            print(f"{session}#{u.index}: old prompt {old.tokens} tok {match}; new {new.tokens}; "
                  f"{u.old_provider or 'fallback'} | {u.old.topic} > {u.old.subtopic} | "
                  f"{' / '.join(l.text for l in u.lines)[:110]}")
            if old.tokens == u.recorded_tokens and not u.old_fallback and u.old_provider.startswith("groq_main"):
                chosen.append(u)
    print(f"{len(chosen)} unit(s) usable for the A/B")
    if dry or not chosen:
        return
    cfg = load_config(overrides={"llm": {"order": ["groq_main"]}})  # gpt-oss-120b only (every Groq key)
    results, spent = [], 0
    async with httpx.AsyncClient() as http:
        router = build_router(cfg, http, usage=UsageLedger(ROOT / cfg.get("llm", "usage_file", "data/llm_usage.json")))
        real_complete = router.complete
        calls: list = []

        async def complete(*a, **kw):
            r = await real_complete(*a, **kw)
            calls.append(r)
            return r

        router.complete = complete  # type: ignore[method-assign]
        need = 2600 * len(chosen)  # ≈ prompt + output per unit
        free = sum(max(0, q["tpd"] - q["used"]) for q in router.quota() if not q["spent"])
        print(f"quota: {router.quota()}; need ≈ {need}, free {free}")
        if free < need:
            print("not enough gpt-oss-120b quota for this A/B; nothing sent")
            return
        interp = Interpreter(router, settings)
        for u in chosen:
            calls.clear()
            prompt = build(u, not resend_old, settings)
            t0 = time.perf_counter()
            res = await interp.interpret(u.state, u.lines, prompt)
            used = sum(c.response.prompt_tokens + c.response.completion_tokens for c in calls)
            spent += used
            row = {"unit": f"{u.session}#{u.index}", "lines": [l.text for l in u.lines],
                   "old": summary(u.old), "new": summary(res.interpretation), "new_provider": res.provider,
                   "valid": not res.fallback, "fallback_reason": res.fallback_reason, "repaired": res.repaired, "tokens": used,
                   "seconds": round(time.perf_counter() - t0, 1)}
            results.append(row)
            o, n = row["old"], row["new"]
            print(f"\n=== {row['unit']} valid={row['valid']} repaired={res.repaired} tokens={used} "
                  f"via {res.provider} | visual={n['visual']}")
            print(f"  topic {o['topic']} > {o['subtopic']} ({o['relation']})  |  {n['topic']} > {n['subtopic']} "
                  f"({n['relation']})")
            print("  OLD: " + "\n       ".join(o["items"]))
            print("  NEW: " + "\n       ".join(n["items"]))
            # stay below the 8k TPM of one key (2026-10-06: only one key had quota; 2 s pacing hit the TPM limit
            # after 4 units and the rest fell back without being sent)
            await asyncio.sleep(max(2.0, 60.0 * used / 7000))
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    agree = lambda k: sum(r["old"][k] == r["new"][k] for r in results)  # noqa: E731
    print(f"\n{len(results)} units: valid {sum(r['valid'] for r in results)}, repaired "
          f"{sum(r['repaired'] for r in results)}, same topic {agree('topic')}, same subtopic {agree('subtopic')}, "
          f"same relation {agree('relation')}, same act kinds {agree('kinds')}, with visual "
          f"{sum(bool(r['new']['visual']) for r in results)}; real tokens {spent} "
          f"(≈ {approx_tokens(P.VISUAL_RULE + P.VISUAL_SHAPE)} prompt tokens added per call) → {path}")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
