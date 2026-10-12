"""Quiz / test questions from what was taught (F-011, slice 2): the only LLM part of a quiz or test.

`From` (this lecture / lectures / chapters) is resolved by the materials service; the prompt holds the lectures'
taught content within a fixed budget (`content.budgeted` via the materials writer: slides, then what was said,
never the whole transcript), ≤ PROMPT_MAX tokens. The answer is strict JSON, validated (4 distinct options, a key
0–3, no repeated question), repaired once; nothing is made up when the model cannot answer. The core shuffles each
question's options (seeded by its text), so where the key sits is not the model's habit.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any, Optional, Sequence

from pydantic import BaseModel

from copilot.assess.model import OPTION_MAX, OPTIONS, TEXT_MAX, AssessError, Question
from copilot.assess.service import Prepared, Spent
from copilot.core.events import new_id
from copilot.core.textutil import approx_tokens
from copilot.materials.content import Lecture
from copilot.materials.writer import MATERIAL_BUDGET, MaterialError, Usage, Writer, _clean, _header, _material

AVOID_BUDGET = 500       # tokens of "do not repeat" stems in a regenerate prompt (taken from the material budget)
PER_QUESTION_OUT = 95    # answer tokens per MCQ (question + 4 options + key, as JSON)


class _MCQ(BaseModel):
    q: str
    options: list[str]
    answer: int


class _MCQs(BaseModel):
    questions: list[_MCQ]


def _stem(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def to_question(m: _MCQ) -> Optional[Question]:
    """A usable question with its options shuffled (deterministically), or None."""
    opts = [_clean(o)[:OPTION_MAX] for o in m.options]
    if len(opts) != OPTIONS or not 0 <= m.answer < OPTIONS:
        return None
    order = list(range(OPTIONS))
    random.Random(int(hashlib.sha1(m.q.encode()).hexdigest()[:8], 16)).shuffle(order)
    q = Question(id=new_id(), text=_clean(m.q)[:TEXT_MAX], options=[opts[i] for i in order],
                 answer=order.index(m.answer))
    return q if q.check() is None else None


def usable(out: _MCQs, avoid: Sequence[str]) -> list[Question]:
    seen = {_stem(a) for a in avoid}
    qs = []
    for m in out.questions:
        q = to_question(m)
        if q is not None and _stem(q.text) not in seen:
            seen.add(_stem(q.text))
            qs.append(q)
    return qs


def prompt(lectures: Sequence[Lecture], count: int, avoid: Sequence[str]) -> str:
    avoid_lines: list[str] = []
    used = 0
    for a in avoid:  # the newest stems are the most likely to be repeated: keep as many as fit
        line = f"- {a[:160]}"
        if used + approx_tokens(line) + 1 > AVOID_BUDGET:
            break
        avoid_lines.append(line)
        used += approx_tokens(line) + 1
    budget = MATERIAL_BUDGET - (used + 20 if avoid_lines else 0)
    text = (f"{_header(lectures)}\n\nWHAT WAS TAUGHT:\n{_material(lectures, budget)}\n\n"
            f"Write exactly {count} multiple-choice question{'s' if count != 1 else ''} for a class quiz on what was "
            "taught. Each has 4 options with exactly one correct; the 3 wrong options are plausible (common "
            "mistakes), about as long as the right one, and clearly wrong to a student who learned the lecture. "
            "Questions short (at most 25 words), options at most 12 words, no 'all / none of the above', no "
            "trick questions. Cover the topics evenly; test understanding, not just recall of words.")
    if avoid_lines:
        text += "\nDo NOT repeat or rephrase these questions:\n" + "\n".join(avoid_lines)
    text += ('\nJSON: {"questions": [{"q": "...", "options": ["...", "...", "...", "..."], "answer": 0}]} '
             "(answer = index of the correct option, 0-3)")
    return text


class LectureQuestions:
    """QuestionSource for AssessService: the materials service resolves From and reads the lectures; the materials
    writer (same keys, same bounded prompts, one repair) asks the LLM."""

    def __init__(self, materials: Any, writer: Optional[Writer] = None) -> None:
        self.materials = materials
        self._writer = writer

    @property
    def writer(self) -> Writer:
        return self._writer if self._writer is not None else self.materials.writer

    @property
    def available(self) -> bool:
        return self.writer.available

    async def prepare(self, args: dict[str, Any]) -> Prepared:
        resolved = self.materials.resolve(args)
        if resolved is None:
            raise AssessError("choose at least one lecture")
        ids, current, title = resolved
        try:
            lectures = await self.materials.taught(ids, current)
        except MaterialError as e:
            raise AssessError(str(e)) from e
        if not any(lec.subtopics for lec in lectures):
            raise AssessError("nothing taught yet to ask about")
        return Prepared(title=title, sources=ids, material=lectures)

    async def questions(self, prepared: Prepared, count: int, avoid: list[str], spent: Spent) -> list[Question]:
        lectures: list[Lecture] = prepared.material
        usage = Usage()
        found: list[Question] = []

        def check(o: _MCQs) -> Optional[str]:
            n = len(usable(o, avoid))
            return None if n >= count else f"{n} usable questions (4 different options, answer 0-3, none " \
                                           f"repeated); exactly {count} needed"
        try:
            out = await self.writer.ask(prompt(lectures, count, avoid), _MCQs,
                                        min(4000, 200 + PER_QUESTION_OUT * count), usage, check)
            found = usable(out, avoid)[:count]
        except MaterialError as e:
            raise AssessError(str(e)) from e
        finally:
            spent.calls += usage.calls
            spent.tokens += usage.tokens
        return found
