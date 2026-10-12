"""Quiz / test questions from recorded lectures (F-011), without the app.

    .venv/Scripts/python tools/quiz_check.py <session> [<session> ...] [--count 15]     # 0 tokens: the prompt + size
    .venv/Scripts/python tools/quiz_check.py <session> --live [--count 15]             # real Groq: one generation

--live prints the questions (key marked) and the tokens spent; it makes exactly one set (plus one repair if needed).
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

from copilot.assess.generator import LectureQuestions, prompt  # noqa: E402
from copilot.assess.service import Prepared, Spent  # noqa: E402
from copilot.core.config import load_config  # noqa: E402
from copilot.core.textutil import approx_tokens  # noqa: E402
from copilot.materials.archive import LectureArchive  # noqa: E402
from copilot.materials.content import lecture_content  # noqa: E402
from copilot.materials.writer import PROMPT_MAX, SYSTEM, Writer  # noqa: E402


async def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--count", type=int, default=15)
    ap.add_argument("--live", action="store_true", help="call the real LLM (uses free quota)")
    ap.add_argument("--out", help="write the questions as JSON here (--live)")
    args = ap.parse_args()
    archive = LectureArchive(ROOT / "data" / "sessions", ROOT / "data" / "archive.json")
    records = [archive.load(s) for s in args.sessions]
    if any(r is None for r in records):
        print("not a lecture:", [s for s, r in zip(args.sessions, records) if r is None])
        return 2
    lectures = [lecture_content(r, n) for n, r in enumerate(records, start=1)]
    for lec in lectures:
        said = sum(approx_tokens(" ".join(s.said)) for s in lec.subtopics)
        print(f"{lec.id}: {lec.title} · {len(lec.topics)} topics · {len(lec.subtopics)} subtopics · "
              f"transcript ~{said} tokens")
    text = prompt(lectures, args.count, [])
    tokens = approx_tokens(SYSTEM) + approx_tokens(text) + 8
    print(f"--- prompt: ~{tokens} tokens in (limit {PROMPT_MAX}), answer up to {min(4000, 200 + 95 * args.count)}")
    if not args.live:
        print(text[:1600] + (" ..." if len(text) > 1600 else ""))
        print("\n0 tokens spent")
        return 0

    import httpx

    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger

    config = load_config()
    async with httpx.AsyncClient() as http:
        router = build_router(config, http, None,
                              UsageLedger(ROOT / config.get("llm", "usage_file", "data/llm_usage.json")))
        spent = Spent()
        source = LectureQuestions(None, Writer(router))
        qs = await source.questions(Prepared(" + ".join(l.title for l in lectures), [l.id for l in lectures],
                                             lectures), args.count, [], spent)
    for n, q in enumerate(qs, start=1):
        print(f"{n}. {q.text}")
        for i, o in enumerate(q.options):
            print(f"   {'*' if i == q.answer else ' '} {'ABCD'[i]}) {o}")
    keys = [q.answer for q in qs]
    print(f"\n{len(qs)} of {args.count} questions · keys A-D: {[keys.count(i) for i in range(4)]} · "
          f"{spent.calls} LLM call(s), {spent.tokens:,} tokens spent")
    if args.out:
        Path(args.out).write_text(json.dumps([q.model_dump() for q in qs], indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
