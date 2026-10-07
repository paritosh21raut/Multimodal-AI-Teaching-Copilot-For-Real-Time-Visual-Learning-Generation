"""Lecture materials from recorded lectures (F-010), without the app.

    .venv/Scripts/python tools/materials_check.py <session> [<session> ...]          # 0 tokens: every prompt + size
    .venv/Scripts/python tools/materials_check.py <session> --live [--kinds summary,concepts,notes,assignment,pptx]
                                                 [--questions 10] [--theme dark]    # real Groq: files to artifacts/

--live writes the files to artifacts/materials/live/ (PDF pages also as PNG, to look at) and prints the tokens spent.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from copilot.core.config import load_config  # noqa: E402
from copilot.core.textutil import approx_tokens  # noqa: E402
from copilot.materials.archive import LectureArchive  # noqa: E402
from copilot.materials.content import lecture_content  # noqa: E402
from copilot.materials.writer import SYSTEM, Usage, Writer  # noqa: E402

OUT = ROOT / "artifacts" / "materials" / "live"


class Recorder:
    """A router that only records the prompts (dry run): answers the shape the writer expects, with no content."""

    def __init__(self) -> None:
        self.prompts: list[str] = []

    async def complete(self, messages, *, est_tokens, max_tokens, deadline, timeout_s=None):
        import re

        from copilot.llm.providers import LLMResponse
        from copilot.llm.router import RouterResult

        user = messages[1]["content"]
        self.prompts.append(user)
        if '"sections"' in user:
            text = json.dumps({"sections": [{"id": i, "text": "-"} for i in re.findall(r"^\[(L[\d.TS]+)\]", user, re.M)]})
        elif '"questions"' in user:
            n = int(re.search(r"exactly (\d+)", user).group(1))
            text = json.dumps({"questions": [{"text": "-", "type": "short"}] * n})
        elif '"concepts"' in user:
            text = json.dumps({"concepts": [{"term": "-", "meaning": "-"}]})
        elif '"topics"' in user:
            text = json.dumps({"topics": [{"title": "-", "points": ["-"]}]})
        else:
            text = json.dumps({"points": ["-"]})
        return RouterResult(LLMResponse(text=text), "dry", [])


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("sessions", nargs="+")
    ap.add_argument("--live", action="store_true", help="call the real LLM (uses free quota)")
    ap.add_argument("--kinds", default="summary,concepts,notes,assignment")
    ap.add_argument("--questions", type=int, default=10)
    ap.add_argument("--theme", default="light")
    args = ap.parse_args()
    kinds = args.kinds.split(",")
    archive = LectureArchive(ROOT / "data" / "sessions", ROOT / "data" / "archive.json")
    records = [archive.load(s) for s in args.sessions]
    if any(r is None for r in records):
        print("not a lecture:", [s for s, r in zip(args.sessions, records) if r is None])
        return 2
    lectures = [lecture_content(r, n) for n, r in enumerate(records, start=1)]
    for lec in lectures:
        print(f"{lec.id}: {lec.title} · {len(lec.topics)} topics · {len(lec.subtopics)} subtopics · "
              f"{sum(len(s.said) for s in lec.subtopics)} lines")

    if not args.live:
        rec = Recorder()
        w, usage = Writer(rec), Usage()
        if "summary" in kinds:
            await w.topic_summary(lectures[0], lectures[0].topics[-1], usage)
            await w.lecture_summary(lectures, usage)
        if "concepts" in kinds or "notes" in kinds:
            await w.key_concepts(lectures, usage)
        if "notes" in kinds:
            await w.note_sections(lectures, usage)
        if "assignment" in kinds:
            await w.questions(lectures, args.questions, usage)
        sys_t = approx_tokens(SYSTEM)
        for p in rec.prompts:
            kind = next((k for k in ("sections", "questions", "concepts", "topics", "points") if f'"{k}"' in p), "?")
            print(f"--- {kind}: {sys_t + approx_tokens(p)} tokens in (system {sys_t})")
            print(p[:1200] + (" ..." if len(p) > 1200 else ""))
        total = sum(sys_t + approx_tokens(p) for p in rec.prompts)
        print(f"\n{len(rec.prompts)} prompts, ~{total} input tokens (answers come on top); 0 tokens spent")
        return 0

    import httpx

    from copilot.llm.router import build_router
    from copilot.llm.usage import UsageLedger
    from copilot.materials.render import assignment_html, notes_html
    from copilot.materials.slides import key_concepts_slides, lecture_summary_slides, topic_summary_slide
    from display_harness import display_harness

    config = load_config()
    OUT.mkdir(parents=True, exist_ok=True)
    async with httpx.AsyncClient() as http:
        router = build_router(config, http, None, UsageLedger(ROOT / config.get("llm", "usage_file", "data/llm_usage.json")))
        w = Writer(router)
        title = " + ".join(l.title for l in lectures)
        stamp = time.strftime("%H%M%S")
        spent: dict[str, Usage] = {}
        async with display_harness(args.theme) as h:
            from copilot.materials.render import Renderer

            renderer = Renderer(h.url)
            concepts = None
            if "summary" in kinds:
                u = spent["summary"] = Usage()
                pts = await w.topic_summary(lectures[0], lectures[0].topics[-1], u)
                topics = await w.lecture_summary(lectures, u)
                specs = [topic_summary_slide(lectures[0].topics[-1].name, pts)] + lecture_summary_slides(title, topics)
                print("topic summary:", json.dumps(pts, indent=1))
                print("lecture summary:", json.dumps(topics, indent=1))
                await renderer.pptx([s.model_dump() for s in specs], args.theme, OUT / f"{stamp}_summary.pptx",
                                    title, frames_dir=OUT)
            if "concepts" in kinds or "notes" in kinds:
                u = spent["concepts"] = Usage()
                concepts = await w.key_concepts(lectures, u)
                print("key concepts:", json.dumps([c.model_dump() for c in concepts], indent=1))
                if "concepts" in kinds:
                    await renderer.pptx([s.model_dump() for s in key_concepts_slides(title, concepts)], args.theme,
                                        OUT / f"{stamp}_concepts.pptx", title, frames_dir=OUT)
            if "notes" in kinds:
                u = spent["notes"] = Usage()
                sections = await w.note_sections(lectures, u)
                await renderer.pdf(notes_html(title, lectures, sections, concepts or []), OUT / f"{stamp}_notes.pdf",
                                   f"{title} · Study notes")
            if "assignment" in kinds:
                u = spent["assignment"] = Usage()
                qs = await w.questions(lectures, args.questions, u)
                print("questions:", json.dumps([q.model_dump() for q in qs], indent=1))
                await renderer.pdf(assignment_html(title, lectures, qs), OUT / f"{stamp}_assignment.pdf",
                                   f"{title} · Assignment")
            if "pptx" in kinds:
                n = await renderer.pptx([s for r in records for s in r.slides], args.theme, OUT / f"{stamp}_slides.pptx",
                                        title)
                print(f"slides.pptx: {n} slides")
        import pypdfium2

        for pdf_path in OUT.glob(f"{stamp}_*.pdf"):
            pdf = pypdfium2.PdfDocument(str(pdf_path))
            for i in range(len(pdf)):
                pdf[i].render(scale=1.3).to_pil().save(pdf_path.with_name(f"{pdf_path.stem}_p{i + 1}.png"))
            pdf.close()
        total = sum(u.tokens for u in spent.values())
        for k, u in spent.items():
            print(f"[TOKENS] {k}: {u.calls} calls, {u.tokens} tokens")
        print(f"[TOKENS] total {total} tokens; files in {OUT.relative_to(ROOT)} ({stamp}_*)")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")  # lecture text has arrows, subscripts …
    sys.exit(asyncio.run(main()))
