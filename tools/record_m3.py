"""F-019 M3: record the diagram extractor's answers for the paraphrase set (one small live run), then score it.

    .venv/Scripts/python tools/record_m3.py          # pings the keys, calls Groq only for the lines the fast path
                                                     # leaves unread, writes tests/fixtures/diagram/m3_llm_answers.json
    .venv/Scripts/python tools/record_m3.py --score  # 0 tokens: replays the recorded answers and scores

Score = lines whose scene (diagram.extract.scene_key) equals the reference fixture's after the same line (gate ≥ 90 %).
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from copilot.core.config import load_config  # noqa: E402
from copilot.diagram.extract import Extractor, ReplayExtractor, replay, scene_key  # noqa: E402
from copilot.llm.router import build_router  # noqa: E402
from copilot.llm.usage import UsageLedger  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "diagram"
ANSWERS = FIX / "m3_llm_answers.json"


class Recorder:
    """The live extractor, keeping each answer as JSONL text by line (and the tokens)."""

    def __init__(self, inner: Extractor) -> None:
        self.inner = inner
        self.answers: dict[str, str] = {}
        self.tokens = self.counted = self.calls = 0

    async def delta(self, g, before, line, draft):
        res = await self.inner.delta(g, before, line, draft)
        self.calls += 1
        self.tokens += res.tokens
        self.counted += res.counted
        self.answers[line.strip()] = "\n".join(json.dumps(o, separators=(",", ":")) for o in res.ops)
        print(f"  [llm {res.entry}, {res.tokens} tokens ({res.counted} counted), {res.total_s:.2f} s] {line}")
        return res


async def score(extractor) -> tuple[int, int]:
    scenes = json.loads((FIX / "m3_paraphrase.json").read_text(encoding="utf-8"))["scenes"]
    same = n = 0
    for s in scenes:
        ref = [x["say"] for x in json.loads((FIX / f"{s['ref']}.json").read_text(encoding="utf-8"))["lines"]]
        want = await replay(ref[:len(s["lines"])])
        got = await replay(s["lines"], extractor)
        for (gr, _), (gp, why), line in zip(want, got, s["lines"]):
            n += 1
            ok = scene_key(gr) == scene_key(gp)
            same += ok
            print(("ok   " if ok else "DIFF ") + (f"[{why}] " if why else "") + line)
            if not ok:
                print(f"       want {scene_key(gr)}\n       got  {scene_key(gp)}")
    return same, n


async def main() -> None:
    if "--score" in sys.argv:
        same, n = await score(ReplayExtractor(json.loads(ANSWERS.read_text(encoding="utf-8"))))
        print(f"replay: {same}/{n} same scene ({same / n:.0%}), 0 tokens")
        return
    config = load_config()
    order = list(config.get("llm", "stage", {}).get("order", ["groq_stage", "groq_main"]))
    async with httpx.AsyncClient() as http:
        router = build_router(config, http, None, UsageLedger(ROOT / config.get("llm", "usage_file",
                                                                                 "data/llm_usage.json")), order=order)
        dead = await router.ping(http)
        print(f"keys: {len({e.env for e in router.entries})}, dead at start: {', '.join(dead) or 'none'}")
        rec = Recorder(Extractor(router))
        same, n = await score(rec)
    ANSWERS.write_text(json.dumps(rec.answers, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"live: {same}/{n} same scene ({same / n:.0%}); {rec.calls} calls, {rec.tokens} tokens "
          f"({rec.counted} counted); answers -> {ANSWERS.relative_to(ROOT)}")


if __name__ == "__main__":
    asyncio.run(main())
