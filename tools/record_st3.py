"""V3 ST3: record the story beat reader's answers for the paraphrase set (one small live run), then score it.

    .venv/Scripts/python tools/record_st3.py          # pings the keys, calls Groq only for the lines the gate sends,
                                                      # writes tests/fixtures/story/st3_llm_answers.json
    .venv/Scripts/python tools/record_st3.py --score  # 0 tokens: replays the recorded answers and scores

Score = items whose story after the line matches its `want` (gate >= 90 %). Each item runs on a fresh story.
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT))

from copilot.story.extract import ReplayStoryExtractor  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "story"
ANSWERS = FIX / "st3_llm_answers.json"


def _norm(s: str) -> str:
    return " ".join("".join(ch if ch.isalnum() else " " for ch in s.lower()).split())


def judge(story, line: str, want: dict) -> tuple[bool, str]:
    lines = [x for sc in story.scenes for x in sc.lines]
    bubbles = [b for sc in story.scenes for b in sc.bubbles]
    if "bubble" in want:
        who, part = want["bubble"]
        if not bubbles:
            return False, "no bubble"
        b = bubbles[-1]
        m = story.member(b.speaker)
        name = m.name if m is not None else "?"
        ok = _norm(who) in _norm(name) and _norm(part) in _norm(b.text) and line not in lines
        return ok, f"bubble {name!r}: {b.text!r}"
    if "scene" in want:
        sc = next((s for s in story.scenes if line in s.lines), None)
        if sc is None:
            return False, "line in no scene"
        bad = [f"{k}={getattr(sc, k)!r}" for k, v in want["scene"].items() if _norm(getattr(sc, k)) != _norm(v)]
        return not bad, ", ".join(bad) or f"when={sc.when!r} where={sc.where!r}"
    if want.get("narration"):
        return line in lines and not bubbles, "narration" if line in lines else "line in no scene"
    if want.get("aside"):
        return line not in lines, "aside" if line not in lines else "the line went into a scene"
    return False, "no want"


async def score(extractor, verbose: bool = True) -> tuple[int, int]:
    from tests.unit.test_story import story_lecture, story_on
    data = json.loads((FIX / "st3_paraphrase.json").read_text(encoding="utf-8"))
    same = 0
    for it in data["items"]:
        bus, deck, eng, clock, talk, asked = await story_lecture()
        for ln in data["ctx"][it["ctx"]]:
            clock.t += 8
            await talk.say(ln)
        eng._story.extractor = extractor
        clock.t += 8
        await talk.say(it["line"])
        await eng._story.settle()
        ok, why = judge(story_on(deck), it["line"], it["want"])
        same += ok
        if verbose:
            print(("ok   " if ok else "DIFF ") + f"{it['line']}  [{why}]")
    return same, len(data["items"])


class Recorder:
    def __init__(self, inner) -> None:
        self.inner = inner
        self.answers: dict[str, str] = {}
        self.tokens = self.counted = self.calls = 0

    async def read(self, msgs, line):
        res = await self.inner.read(msgs, line)
        self.calls += 1
        self.tokens += res.tokens
        self.counted += res.counted
        self.answers[line.strip()] = json.dumps(res.answer) if res.answer is not None else ""
        print(f"  [llm {res.entry}, {res.tokens} tokens ({res.counted} counted), {res.total_s:.2f} s] {line}")
        return res


async def record() -> None:
    import httpx

    from copilot.core.config import load_config
    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger
    from copilot.story.extract import StoryExtractor
    cfg = load_config()
    order = list(cfg.get("llm", "stage", {}).get("order", ["groq_stage", "groq_main"]))
    async with httpx.AsyncClient() as http:
        router = build_router(cfg, http, None, UsageLedger(ROOT / cfg.get("llm", "usage_file", "data/llm_usage.json")),
                              order=order)
        dead = await router.ping(http)
        print(f"keys: {len({e.env for e in router.entries})}, dead at start: {', '.join(dead) or 'none'}")
        rec = Recorder(StoryExtractor(router))
        same, n = await score(rec)
    ANSWERS.write_text(json.dumps(rec.answers, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\n{rec.calls} calls, {rec.tokens} tokens ({rec.counted} counted); score {same}/{n} = {same / n:.0%}")


async def replay_score() -> None:
    answers = json.loads(ANSWERS.read_text(encoding="utf-8"))
    same, n = await score(ReplayStoryExtractor(answers))
    print(f"\nscore {same}/{n} = {same / n:.0%}")


if __name__ == "__main__":
    asyncio.run(replay_score() if "--score" in sys.argv else record())
