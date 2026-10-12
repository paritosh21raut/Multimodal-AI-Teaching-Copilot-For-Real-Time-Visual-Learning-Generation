"""Quiz / test questions from what was taught (F-011, slice 2): the only LLM part of a quiz or test.

`From` (this lecture / lectures / chapters) is resolved by the materials service; the prompt holds the lectures'
taught content within a fixed budget (`content.budgeted` via the materials writer: slides, then what was said,
never the whole transcript), ≤ PROMPT_MAX tokens. The answer is strict JSON, validated (4 distinct options, a key
0–3, no repeated question), repaired once; nothing is made up when the model cannot answer. The core shuffles each
question's options (seeded by its text), so where the key sits is not the model's habit.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import random
import re
from typing import Any, Optional, Sequence

from pydantic import BaseModel

from copilot.assess.model import OPTION_MAX, OPTIONS, TEXT_MAX, AssessError, Question
from copilot.assess.service import Prepared, Spent
from copilot.core.events import new_id
from copilot.core.textutil import approx_tokens
from copilot.materials.content import _STOP, Lecture
from copilot.materials.writer import (MATERIAL_BUDGET, PROMPT_MAX, SYSTEM, MaterialError, Usage, Writer, _clean,
                                      _header, _material)

log = logging.getLogger(__name__)

AVOID_BUDGET = 500      # tokens of "do not repeat" stems in a regenerate prompt (taken from the material budget)
PER_QUESTION_OUT = 95    # answer tokens per MCQ (question + 4 options + key, as JSON)
REFERENCE_BUDGET = 400   # F-012: the teacher's reference passages matched to the taught subtopics
REFERENCE_KEEP = 100     # prompt room kept free (estimate slack)


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


def _stems(text: str) -> set[str]:
    """Content words (≥ 4 letters, or numbers), lightly stemmed: "ventricles" = "ventricle"."""
    out = set()
    for w in re.findall(r"[a-z0-9]+", text.lower()):
        if not (w.isdigit() or (len(w) >= 4 and w not in _STOP)):
            continue
        for suffix in ("ing", "es", "ed", "s"):
            if w.endswith(suffix) and len(w) - len(suffix) >= 4:
                w = w[: -len(suffix)]
                break
        out.add(w)
    return out


def taught_text(lectures: Sequence[Lecture]) -> str:
    """Everything that was taught (slides, then what was said) as one text, for the untaught-answer guard."""
    return " ".join(" ".join([s.topic, s.title, *s.lines(), *s.said]) for lec in lectures for s in lec.subtopics)


def untaught(q: Question, taught: set[str], reference: set[str]) -> bool:
    """F-012 guard: the correct answer comes from the teacher's reference, not from the lecture — most of its
    content words were never taught but are in the reference passages the prompt held."""
    words = _stems(q.options[q.answer])
    if not words:
        return False
    new = words - taught
    return len(new) * 2 > len(words) and len(new & reference) * 2 >= len(new)


def reference_passages(reference: Any, lectures: Sequence[Lecture]) -> list[str]:
    """One query per taught subtopic: only the study-material passages clearly about what was taught (GROUND_MIN,
    ≤ GROUND_TOKENS). Blocking (MiniLM): run in a thread."""
    texts = [" ".join([s.title, *s.lines()])[:600] for lec in lectures for s in lec.subtopics]
    return [p.text for p in reference.grounding(texts)]


def reference_block(passages: Sequence[str], max_tokens: int) -> str:
    """The teacher's reference passages, clearly secondary to what was taught ("" when none fits)."""
    # live 2026-10-12: a wrong taught fact was keyed as the right answer although the reference said otherwise →
    # such a point gets no question at all (neither the wrong key nor untaught content)
    head = ("REFERENCE (the teacher's own notes; ONLY to check that facts and wording are right; never ask about "
            "anything that is not in WHAT WAS TAUGHT; where WHAT WAS TAUGHT contradicts REFERENCE, write no "
            "question on that point):")
    out, used = [], approx_tokens(head) + 2
    for p in passages:
        line = f"- {' '.join(p.split())}"
        if used + approx_tokens(line) + 1 > max_tokens:
            continue
        out.append(line)
        used += approx_tokens(line) + 1
    return head + "\n" + "\n".join(out) if out else ""


def prompt(lectures: Sequence[Lecture], count: int, avoid: Sequence[str],
           reference: Sequence[str] = ()) -> str:
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
    if reference:  # F-012: what is left of the prompt budget (≤ REFERENCE_BUDGET), after the taught content
        room = min(REFERENCE_BUDGET, PROMPT_MAX - REFERENCE_KEEP - approx_tokens(SYSTEM) - approx_tokens(text))
        block = reference_block(reference, room) if room > 40 else ""
        if block:
            text = text.replace("\n\nWrite exactly", f"\n\n{block}\n\nWrite exactly", 1)
    return text


class LectureQuestions:
    """QuestionSource for AssessService: the materials service resolves From and reads the lectures; the materials
    writer (same keys, same bounded prompts, one repair) asks the LLM."""

    def __init__(self, materials: Any, writer: Optional[Writer] = None, reference: Any = None) -> None:
        self.materials = materials
        self._writer = writer
        self.reference = reference  # notes.reference.ReferenceIndex (F-012): checks facts, never adds topics

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
        passages: list[str] = []
        if self.reference is not None and args.get("reference", True):
            try:
                passages = await asyncio.to_thread(reference_passages, self.reference, lectures)
            except Exception:  # the questions are still written from what was taught
                log.exception("quiz reference passages failed")
        return Prepared(title=title, sources=ids, material=lectures, reference=passages)

    async def questions(self, prepared: Prepared, count: int, avoid: list[str], spent: Spent) -> list[Question]:
        lectures: list[Lecture] = prepared.material
        usage = Usage()
        found: list[Question] = []
        text = prompt(lectures, count, avoid, prepared.reference)
        taught = _stems(taught_text(lectures))
        ref = _stems(" ".join(prepared.reference)) if "REFERENCE (" in text else set()
        dropped: list[str] = []

        def keep(o: _MCQs) -> list[Question]:
            qs = usable(o, avoid)
            if not ref:
                return qs
            out = [q for q in qs if not untaught(q, taught, ref)]
            dropped[:] = [q.text for q in qs if q not in out]
            return out

        def check(o: _MCQs) -> Optional[str]:
            n = len(keep(o))
            if n >= count:
                return None
            why = f"{n} usable questions (4 different options, answer 0-3, none repeated"
            if dropped:
                why += "; answers only in REFERENCE are not allowed: ask only about WHAT WAS TAUGHT"
            return why + f"); exactly {count} needed"
        try:
            out = await self.writer.ask(text, _MCQs, min(4000, 200 + PER_QUESTION_OUT * count), usage, check)
            found = keep(out)[:count]
            if dropped:
                log.info("quiz: %d question(s) about untaught reference content dropped: %s", len(dropped),
                         " | ".join(d[:80] for d in dropped))
        except MaterialError as e:
            raise AssessError(str(e)) from e
        finally:
            spent.calls += usage.calls
            spent.tokens += usage.tokens
        return found
