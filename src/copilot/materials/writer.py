"""The LLM part of the lecture materials (F-010): bounded prompts → LLMRouter → strict JSON → one repair.

Every prompt holds only what was taught (`content.budgeted`), never more than PROMPT_MAX tokens; a lecture too long
for one prompt is written in several calls (notes) or given a fair share per topic (summary, concepts, questions).
A failure is a `MaterialError` with the reason: nothing is made up when the model cannot answer.
"""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Callable, Literal, Optional, Sequence, TypeVar

from pydantic import BaseModel, ValidationError, field_validator

from copilot.core.textutil import approx_tokens
from copilot.llm.router import AllProvidersFailed, LLMRouter
from copilot.materials.content import Lecture, Subtopic, Topic, budgeted

log = logging.getLogger(__name__)

PROMPT_MAX = 3000        # whole prompt (system + material), like the live interpretation's budget
MATERIAL_BUDGET = 2200   # lecture material in one prompt
NOTES_BUDGET = 1800      # lecture material per notes call (the answer is longer)
CALL_TIMEOUT_S = 45.0    # one HTTP attempt (live interpretation: 6 s)
CALL_DEADLINE_S = 150.0  # one call with its retries / waits for a free per-minute window
DEFAULT_QUESTIONS = 10
MAX_QUESTIONS = 30

SYSTEM = (
    "You write study material for a teacher from the teacher's own lecture. Use ONLY the lecture material given: "
    "never add facts, numbers, names, dates, formulas or examples that are not in it. Correct obvious speech-to-text "
    "slips silently. Clear, simple, correct English for students. Plain text: no markdown, no LaTeX. "
    "Reply with one JSON object only."
)


class MaterialError(Exception):
    """The material could not be made (no LLM, quota spent, invalid answers); the message says why."""


@dataclass
class Usage:
    calls: int = 0
    tokens: int = 0


def _clean(s: str) -> str:
    s = re.sub(r"\*\*|__|`", "", s or "")
    return re.sub(r"\s+", " ", s).strip()


class _Points(BaseModel):
    points: list[str]

    @field_validator("points")
    @classmethod
    def _some(cls, v: list[str]) -> list[str]:
        v = [_clean(p) for p in v if _clean(p)]
        if not v:
            raise ValueError("no points")
        return v


class _SummaryTopic(BaseModel):
    title: str
    points: list[str]


class _LectureSummary(BaseModel):
    topics: list[_SummaryTopic]


class Concept(BaseModel):
    term: str
    meaning: str


class _Concepts(BaseModel):
    concepts: list[Concept]


class _Section(BaseModel):
    id: str
    text: str


class _Sections(BaseModel):
    sections: list[_Section]


class Question(BaseModel):
    text: str
    type: Literal["short", "long"]


class _Questions(BaseModel):
    questions: list[Question]


T = TypeVar("T", bound=BaseModel)


def parse_json(text: str, model: type[T]) -> T:
    """The first JSON object in the answer, validated; ValueError says what is wrong (for the repair prompt)."""
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no JSON object in the answer")
    try:
        return model.model_validate(json.loads(text[start:end + 1]))
    except json.JSONDecodeError as e:
        raise ValueError(f"invalid JSON: {e}") from e
    except ValidationError as e:
        err = e.errors()[0]
        raise ValueError(f"{'.'.join(str(p) for p in err['loc'])}: {err['msg']}") from e


def _header(lectures: Sequence[Lecture]) -> str:
    if len(lectures) == 1:
        lec = lectures[0]
        return f"LECTURE: {lec.title}" + (f" ({lec.date})" if lec.date else "")
    return "LECTURES:\n" + "\n".join(f"L{n}: {lec.title}" + (f" ({lec.date})" if lec.date else "")
                                     for n, lec in enumerate(lectures, start=1))


def _material(lectures: Sequence[Lecture], budget: int, said: bool = False) -> str:
    """Every lecture gets an equal share of the budget (the unused rest passes on)."""
    parts, left = [], budget
    for n, lec in enumerate(lectures):
        share = left // (len(lectures) - n)
        text = budgeted(lec.subtopics, share, said=said)
        parts.append(text)
        left -= approx_tokens(text)
    return "\n\n".join(p for p in parts if p)


class Writer:
    def __init__(self, router: Optional[LLMRouter], timeout_s: float = CALL_TIMEOUT_S,
                 deadline_s: float = CALL_DEADLINE_S) -> None:
        self.router = router
        self.timeout_s = timeout_s
        self.deadline_s = deadline_s

    @property
    def available(self) -> bool:
        return self.router is not None

    async def ask(self, user: str, model: type[T], max_tokens: int, usage: Usage,
                  check: Optional[Callable[[T], Optional[str]]] = None) -> T:
        """One answer for this prompt; one repair when it is invalid (or `check` objects); else MaterialError."""
        if self.router is None:
            raise MaterialError("the LLM is off (the app was started without understanding)")
        messages = [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}]
        tokens = approx_tokens(SYSTEM) + approx_tokens(user) + 8
        if tokens > PROMPT_MAX:  # a bug in the budgeting, never sent
            raise MaterialError(f"prompt over budget ({tokens} > {PROMPT_MAX} tokens)")
        deadline = time.monotonic() + self.deadline_s
        problem = ""
        for attempt in range(2):
            try:
                res = await self.router.complete(messages, est_tokens=tokens, max_tokens=max_tokens,
                                                 deadline=deadline, timeout_s=self.timeout_s)
            except AllProvidersFailed as e:
                raise MaterialError(f"no LLM answer: {e}") from e
            r = res.response
            usage.calls += 1
            usage.tokens += (r.prompt_tokens + r.completion_tokens) or (tokens + approx_tokens(r.text))
            try:
                out = parse_json(r.text, model)
                problem = check(out) if check else None
            except ValueError as e:
                problem = str(e)
            if not problem:
                return out
            log.warning("material answer from %s invalid (%s)%s", res.entry, problem,
                        "; one repair" if attempt == 0 else "")
            echo = r.text
            while approx_tokens(echo) > 900:
                echo = echo[: int(len(echo) * 0.8)]
            messages = messages[:2] + [{"role": "assistant", "content": echo},
                                       {"role": "user", "content": f"That answer was not right: {problem[:300]}. "
                                                                   "Reply with the corrected JSON object only."}]
            tokens = sum(approx_tokens(m["content"]) for m in messages) + 8
        raise MaterialError(f"the LLM's answer was not usable: {problem}")

    # ---- summary slides ---------------------------------------------------------------------------------
    async def topic_summary(self, lecture: Lecture, topic: Topic, usage: Usage) -> list[str]:
        user = (f"{_header([lecture])}\nTOPIC: {topic.name}\n\nWHAT WAS TAUGHT ON THIS TOPIC:\n"
                f"{budgeted(topic.subtopics, MATERIAL_BUDGET, said=True)}\n\n"
                "Write a SHORT summary of this topic for one slide: 3 to 5 points, each one sentence of at most 18 "
                'words, the most important ideas first.\nJSON: {"points": ["..."]}')
        out = await self.ask(user, _Points, 700, usage,
                             lambda o: None if len(o.points) <= 6 else f"{len(o.points)} points; at most 5")
        return out.points[:5]

    async def lecture_summary(self, lectures: Sequence[Lecture], usage: Usage) -> list[tuple[str, list[str]]]:
        user = (f"{_header(lectures)}\n\nWHAT WAS TAUGHT (topic > subtopic, then the slide content):\n"
                f"{_material(lectures, MATERIAL_BUDGET)}\n\n"
                "Write a COMPLETE summary of the whole lecture for slides: one entry per main topic, in teaching order, "
                "at most 8 topics; each with 2 to 4 points of at most 18 words. Use the topic names as taught.\n"
                'JSON: {"topics": [{"title": "...", "points": ["..."]}]}')

        def check(o: _LectureSummary) -> Optional[str]:
            if not o.topics or not any(t.points for t in o.topics):
                return "no topics with points"
            return None
        out = await self.ask(user, _LectureSummary, 1400, usage, check)
        return [(_clean(t.title), [_clean(p) for p in t.points if _clean(p)][:4]) for t in out.topics[:8]
                if t.points]

    # ---- key concepts -----------------------------------------------------------------------------------
    async def key_concepts(self, lectures: Sequence[Lecture], usage: Usage) -> list[Concept]:
        user = (f"{_header(lectures)}\n\nWHAT WAS TAUGHT:\n{_material(lectures, MATERIAL_BUDGET)}\n\n"
                "List the KEY CONCEPTS a student must know: 5 to 10 terms that were taught, each with its meaning in "
                "one sentence of at most 16 words, as taught. Most important first.\n"
                'JSON: {"concepts": [{"term": "...", "meaning": "..."}]}')
        out = await self.ask(user, _Concepts, 900, usage,
                             lambda o: None if o.concepts else "no concepts")
        seen, concepts = set(), []
        for c in out.concepts:
            term, meaning = _clean(c.term), _clean(c.meaning)
            if term and meaning and term.lower() not in seen:
                seen.add(term.lower())
                concepts.append(Concept(term=term, meaning=meaning))
        return concepts[:10]

    # ---- notes ------------------------------------------------------------------------------------------
    async def note_sections(self, lectures: Sequence[Lecture], usage: Usage,
                            progress: Optional[Callable[[int, int], None]] = None) -> dict[str, str]:
        """An explanation per subtopic ("L1.T2.S1" -> paragraph), written from its slides and what was said;
        the subtopics are packed into as few calls as the notes budget allows."""
        batches: list[list[Subtopic]] = []
        size = 0
        for sub in (s for lec in lectures for s in lec.subtopics):
            cost = approx_tokens(budgeted([sub], NOTES_BUDGET, said=True))
            if batches and size + cost <= NOTES_BUDGET:
                batches[-1].append(sub)
                size += cost
            else:
                batches.append([sub])
                size = cost
        out: dict[str, str] = {}
        for n, batch in enumerate(batches):
            if progress:
                progress(n, len(batches))
            keys = [s.key for s in batch]
            user = (f"{_header(lectures)}\n\nWHAT WAS TAUGHT (each part: [id] topic > subtopic, the slide content, "
                    f"then what the teacher said):\n{budgeted(batch, NOTES_BUDGET, said=True)}\n\n"
                    "Write STUDY NOTES: for every id above, a clear explanation of 2 to 5 sentences that a student can "
                    "learn from, connecting the ideas as the teacher explained them. Do not repeat the heading. "
                    'One entry per id, same ids.\nJSON: {"sections": [{"id": "' + keys[0] + '", "text": "..."}]}')

            def check(o: _Sections, keys=keys) -> Optional[str]:
                got = {s.id for s in o.sections if _clean(s.text)}
                missing = [k for k in keys if k not in got]
                return f"missing ids {', '.join(missing)}" if missing else None
            try:
                ans = await self.ask(user, _Sections, 1800, usage, check)
            except MaterialError as e:
                raise MaterialError(f"notes part {n + 1} of {len(batches)}: {e}") from e
            for s in ans.sections:
                if s.id in keys and _clean(s.text):
                    out[s.id] = _clean(s.text)
        return out

    # ---- assignment -------------------------------------------------------------------------------------
    async def questions(self, lectures: Sequence[Lecture], count: int, usage: Usage) -> list[Question]:
        count = max(1, min(MAX_QUESTIONS, count))
        long_n = max(1, round(count * 0.4)) if count > 1 else 0
        short_n = count - long_n
        user = (f"{_header(lectures)}\n\nWHAT WAS TAUGHT:\n{_material(lectures, MATERIAL_BUDGET)}\n\n"
                f"Write an ASSIGNMENT of exactly {count} theory questions on what was taught: {short_n} short-answer "
                f"questions (a few lines: define, state, name, list) and {long_n} long-answer questions (explain, "
                "describe, compare, give reasons). Cover all topics, no two questions alike, answerable from the "
                "lecture. No answers.\n"
                'JSON: {"questions": [{"text": "...", "type": "short"}, {"text": "...", "type": "long"}]}')

        def check(o: _Questions) -> Optional[str]:
            n = len([q for q in o.questions if _clean(q.text)])
            return None if n >= count else f"{n} questions; exactly {count} needed"
        out = await self.ask(user, _Questions, min(4000, 300 + 90 * count), usage, check)
        qs = [Question(text=_clean(q.text), type=q.type) for q in out.questions if _clean(q.text)]
        return qs[:count]
