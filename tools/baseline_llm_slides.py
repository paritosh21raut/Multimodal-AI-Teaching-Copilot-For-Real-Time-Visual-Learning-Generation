"""Paper baseline: an LLM that controls the slides itself, on the same lecture units as a recorded live session.

    .venv/Scripts/python tools/baseline_llm_slides.py <session> [--limit N]     # real LLM (free Groq), ~1k tokens / unit
    .venv/Scripts/python tools/baseline_llm_slides.py <session> --metrics       # 0 tokens: compare with the live log

For every InterpretRequested of the session (the units the live gate formed), the LLM gets the slide it showed last and
the teacher's recent lines (the last 60 s of transcript, a bounded window like the copilot's) and returns the whole slide
to show now plus whether it is a new slide. No planner, confirmation, dwell or composer: the LLM decides. Answers are
saved to artifacts/baseline/<session>.json. --metrics compares slide changes, renames and content churn of the
baseline with the copilot's own slide patches in the same session.
"""
from __future__ import annotations

import asyncio
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "baseline"
WINDOW_S = 60.0

SYSTEM = (
    "You turn a live lecture into slides projected for students while the teacher speaks. You receive the slide that "
    "is shown now (or none) and the teacher's most recent sentences. Return only JSON: "
    '{"action": "update" | "new", "title": "...", "bullets": ["...", ...]}. '
    "\"update\" replaces the shown slide with your version (keep what is still right, add what was just taught); "
    "\"new\" starts a new slide because the teacher moved to a different topic or subtopic. At most 6 short bullets, "
    "only what the teacher said.")


def load(session: str):
    db = sqlite3.connect(ROOT / "data" / "sessions" / session / "session.sqlite")
    ev = [(t, ty, json.loads(p)) for t, ty, p in db.execute("select ts, type, payload from events order by seq")]
    lines = {p["segment"]["id"]: (p["segment"]["start"], p["segment"]["end"], p["segment"]["text"])
             for _, ty, p in ev if ty == "TranscriptFinal"}
    units = [(t, p["segment_ids"]) for t, ty, p in ev if ty == "InterpretRequested"]
    return ev, lines, units


def window(lines: dict, seg_ids: list[str]) -> str:
    known = [lines[s] for s in seg_ids if s in lines]
    if not known:
        return ""
    end = max(e for _, e, _ in known)
    ordered = sorted(lines.values())
    return " ".join(text for start, e, text in ordered if end - WINDOW_S <= e <= end)


async def run(session: str, limit: int | None) -> None:
    import httpx

    from copilot.core.config import load_config
    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger

    config = load_config()
    _, lines, units = load(session)
    units = units[:limit] if limit else units
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{session}.json"
    done = json.loads(path.read_text()) if path.exists() else []
    slide = None
    if done:
        slide = done[-1].get("slide")
    tokens = 0
    async with httpx.AsyncClient() as http:
        router = build_router(config, http, None, UsageLedger(ROOT / config.get("llm", "usage_file", "data/llm_usage.json")))
        for i, (t, segs) in enumerate(units):
            if i < len(done):
                continue
            shown = json.dumps(slide) if slide else "none"
            user = f"SHOWN SLIDE: {shown}\nTEACHER (last {int(WINDOW_S)} s): {window(lines, segs)}"
            msgs = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
            t0 = time.perf_counter()
            try:
                r = await router.complete(msgs, est_tokens=len(SYSTEM + user) // 4, max_tokens=500,
                                          deadline=time.monotonic() + 60)
                text = r.response.text
                m = re.search(r"\{.*\}", text, re.S)
                ans = json.loads(m.group(0)) if m else {}
                used = (r.response.prompt_tokens or 0) + (r.response.completion_tokens or 0)
                entry = r.entry
            except Exception as e:  # noqa: BLE001 - recorded, the unit keeps the old slide
                ans, used, entry = {}, 0, f"failed: {type(e).__name__}: {e}"[:200]
            tokens += used
            if ans.get("title"):
                slide = {"title": ans["title"], "bullets": [str(b) for b in ans.get("bullets", [])][:6]}
            done.append(dict(ts=t, segs=segs, action=ans.get("action", "keep" if not ans else "update"), answer=ans,
                             slide=slide, entry=entry, tokens=used, s=time.perf_counter() - t0))
            path.write_text(json.dumps(done, indent=1))
            print(f"{i + 1}/{len(units)} {done[-1]['action']:6s} {slide and slide['title']!r} {used} tok {entry}")
            await asyncio.sleep(2.0)  # stay under the per-minute limits
    print("tokens this run:", tokens, " total:", sum(d["tokens"] for d in done))


# ---------------------------------------------------------------------------------------------- metrics (0 tokens)
def _texts(spec: dict) -> list[str]:
    out = []

    def walk(x):
        if isinstance(x, dict):
            if x.get("provisional") or str(x.get("id", "")).startswith("prov-"):
                return  # a key-phrase teaser, replaced by design when the interpretation arrives
            for k, v in x.items():
                if k in ("text", "label", "definition", "value", "spoken") and isinstance(v, str) and v:
                    out.append(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(spec.get("blocks", []))
    return out


def churn(versions: list[tuple[str, list[str]]]) -> tuple[int, int, int]:
    """(updates, renames, previously shown texts that were rewritten or removed) over consecutive versions."""
    upd = ren = lost = 0
    for (t0, a), (t1, b) in zip(versions, versions[1:]):
        upd += 1
        ren += t0 != t1
        lost += sum(1 for x in a if x not in b)
    return upd, ren, lost


def metrics(session: str) -> None:
    ev, _, units = load(session)
    minutes = (units[-1][0] - units[0][0]) / 60
    base = json.loads((OUT / f"{session}.json").read_text())
    # baseline: slides as the LLM made them
    slides, cur = [], None
    for d in base:
        if not d["answer"].get("title"):
            continue
        s = (d["answer"]["title"], [str(b) for b in d["answer"].get("bullets", [])])
        if d["action"] == "new" or cur is None:
            slides.append([s])
        else:
            slides[-1].append(s)
        cur = s
    b_upd = b_ren = b_lost = b_shown = 0
    for vs in slides:
        u, r, lo = churn(vs)
        b_upd += u; b_ren += r; b_lost += lo; b_shown += sum(len(a) for _, a in vs[:-1])
    # copilot: its slide patches in the live run
    vers: dict[str, list] = {}
    for _, ty, p in ev:
        if ty == "SlidePatch" and p["spec"].get("layout") != "title":
            vers.setdefault(p["slide_id"], []).append((p["spec"]["title"], _texts(p["spec"])))
    c_upd = c_ren = c_lost = c_shown = 0
    for vs in vers.values():
        u, r, lo = churn(vs)
        c_upd += u; c_ren += r; c_lost += lo; c_shown += sum(len(a) for _, a in vs[:-1])
    b_final = {x for vs in slides for x in vs[-1][1]}
    b_ever = {x for vs in slides for _, a in vs for x in a}
    c_final = {x for vs in vers.values() for x in vs[-1][1]}
    c_ever = {x for vs in vers.values() for _, a in vs for x in a}
    fails = sum(1 for d in base if str(d["entry"]).startswith("failed"))
    print(f"session {session}: {len(units)} units, {minutes:.1f} min; baseline answers {len(base)} (failed {fails}), "
          f"tokens {sum(d['tokens'] for d in base)}")
    print(f"{'':10s} {'slides':>7s} {'/min':>6s} {'updates':>8s} {'renames':>8s} {'lost/shown':>12s} "
          f"{'not in final deck':>18s}")
    print(f"{'baseline':10s} {len(slides):7d} {len(slides) / minutes:6.2f} {b_upd:8d} {b_ren:8d} "
          f"{b_lost:5d}/{b_shown:<5d} {b_lost / max(b_shown, 1):.2f}  {len(b_ever - b_final):4d}/{len(b_ever)} "
          f"{len(b_ever - b_final) / max(len(b_ever), 1):.2f}")
    print(f"{'copilot':10s} {len(vers):7d} {len(vers) / minutes:6.2f} {c_upd:8d} {c_ren:8d} "
          f"{c_lost:5d}/{c_shown:<5d} {c_lost / max(c_shown, 1):.2f}  {len(c_ever - c_final):4d}/{len(c_ever)} "
          f"{len(c_ever - c_final) / max(len(c_ever), 1):.2f}")


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--metrics" in sys.argv:
        metrics(args[0])
    else:
        lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else None
        asyncio.run(run(args[0], lim))
