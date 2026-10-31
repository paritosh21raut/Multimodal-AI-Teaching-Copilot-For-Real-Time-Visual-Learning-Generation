"""E3 live measurement (spends Groq free-tier tokens): the 20 lines of tests/fixtures/stage/live/e3_lines.jsonl through the
fast path and the real stage director ([llm.stage] order), one line after another as in class. Prints per call: the
model entry, counted tokens (prompt - cached + completion), first op / total seconds, ops kept / rejected, and whether
the LLM's nouns, verbs and laws match the recorded answer. Writes the answers to artifacts/stage/e3_live.jsonl.

    .venv/Scripts/python tools/stage/e3_live.py [--lines N]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "src")]

import httpx  # noqa: E402

from copilot.core.config import load_config  # noqa: E402
from copilot.llm.router import build_router  # noqa: E402
from copilot.stage import director, fastpath  # noqa: E402
from copilot.stage.director_llm import StageDirector  # noqa: E402
from copilot.stage.log import EventLog  # noqa: E402

LIVE = ROOT / "tests" / "fixtures" / "stage" / "live" / "e3_lines.jsonl"


def facts(ops: list[dict]) -> set[str]:
    """What a scene says, ignoring ids: the nouns added, the verbs acted, the laws named."""
    out = set()
    for o in ops:
        if o.get("op") == "add":
            out.add("add:" + str(o.get("w")))
        elif o.get("op") == "act":
            out.add("act:" + str(o.get("verb")))
        elif o.get("op") == "law":
            out.add("law:" + str(o.get("name")))
    return out


async def main(n: int) -> None:
    rows = [json.loads(s) for s in LIVE.read_text(encoding="utf-8").splitlines() if s.strip()][1:][:n]
    config = load_config()
    order = list(config.get("llm", "stage", {}).get("order", ["groq_stage", "groq_main"]))
    async with httpx.AsyncClient(timeout=20) as http:
        d = StageDirector(build_router(config, http, order=order))
        log, said, out, stats = EventLog(), [], [], []
        for i, r in enumerate(rows):
            lid = f"l{i}"
            log.say(lid, r["say"])
            t = time.perf_counter()
            dr = fastpath.draft(r["say"], log.fold())
            draft_s = time.perf_counter() - t
            gone = director.room(log.fold(), dr.ops)
            if gone:
                log.delta(gone, lid, "director")
            log.delta(dr.ops, lid, "fast")
            try:
                res = await d.delta(log.fold(skip_fast_of=lid), said[-2:], r["say"], dr.ops)
            except Exception as e:  # noqa: BLE001 - report it, keep the draft (as the controller does)
                print(f"{i:2} FAILED {e}  | {r['say']}")
                stats.append({"failed": True, "draft_s": draft_s})
                said.append(r["say"])
                continue
            gone = director.room(log.fold(skip_fast_of=lid), res.ops)
            if gone:
                log.delta(gone, lid, "director")
            dl = log.delta(res.ops, lid, "llm")
            want = {f for f in facts(json.loads(s) for s in r["answer"].splitlines() if s.strip())}
            got = facts(res.ops)
            ok = want <= got or (not want and not any(o.get("op") in ("add", "act") for o in res.ops))
            st = {"entry": res.entry, "counted": res.counted, "prompt": res.prompt_tokens, "cached": res.cached_tokens,
                  "out": res.tokens - res.prompt_tokens if res.tokens else 0, "first_op_s": res.first_op_s,
                  "total_s": res.total_s, "draft_s": draft_s, "kept": len(dl.ok), "n_rejected": len(dl.rejected),
                  "ok": ok}
            stats.append(st)
            out.append({"say": r["say"], "ops": res.ops, "rejected": [x.reason for x in dl.rejected], **st})
            print(f"{i:2} {res.entry:16} counted {res.counted:5} (cached {res.cached_tokens:5}) first {res.first_op_s or 0:4.2f}s "
                  f"total {res.total_s:4.2f}s kept {len(dl.ok):2} rej {len(dl.rejected)} {'OK ' if ok else 'BAD'} "
                  f"missing {sorted(want - got)} | {r['say']}")
            said.append(r["say"])
            await asyncio.sleep(2.1)  # 30 rpm on the stage model: stay under it as one teacher would
    (ROOT / "artifacts" / "stage").mkdir(parents=True, exist_ok=True)
    with open(ROOT / "artifacts" / "stage" / "e3_live.jsonl", "w", encoding="utf-8") as f:
        f.writelines(json.dumps(x) + "\n" for x in out)
    good = [s for s in stats if not s.get("failed")]
    tot = [s["total_s"] for s in good]
    q = (lambda xs, p: sorted(xs)[min(len(xs) - 1, int(p * len(xs)))]) if tot else None
    print(f"\ncalls {len(good)}/{len(stats)}  counted tokens {sum(s['counted'] for s in good)} "
          f"(mean {statistics.mean(s['counted'] for s in good):.0f}/call)  scene-correct {sum(s['ok'] for s in good)}/{len(good)}")
    if tot:
        print(f"draft p95 {q([s['draft_s'] for s in stats], .95) * 1000:.1f} ms  full p50 {q(tot, .5):.2f}s p95 {q(tot, .95):.2f}s  "
              f"entries {sorted({s['entry'] for s in good})}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=20)
    asyncio.run(main(ap.parse_args().lines))
