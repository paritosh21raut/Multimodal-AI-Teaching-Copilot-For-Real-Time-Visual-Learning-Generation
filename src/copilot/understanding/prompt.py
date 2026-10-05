"""Bounded interpretation prompt. The budget is enforced here, in code, before anything is sent."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from copilot.core.state import LectureState
from copilot.core.textutil import approx_tokens
from copilot.understanding.gate import BufferedLine

SYSTEM_PROMPT = """You analyse a live classroom lecture for a projector display that follows the teacher.
You get the lecture context and a few NEW numbered transcript lines. Reply with ONE JSON object only.

Rules:
- Represent only what the teacher said in the NEW lines. Use the context only to judge continuity.
- topic = the main subject being taught (e.g. "Photosynthesis"). subtopic = the current facet within it
  (e.g. "Definition", "Requirements", "Process", "Importance"). Reuse the exact outline title while the teacher
  stays on it. Titles: 1-4 words, Title Case.
- Start a new subtopic (sibling_concept) when the teacher moves to a different facet, e.g. from what it is to
  what it needs, how it works, why it matters, even without an explicit cue. If the NEW lines span two facets,
  use the facet of the later lines. For sibling_concept, sub_concept and new_topic the subtopic must differ from
  the CURRENT subtopic. A comparison with an earlier topic stays under the CURRENT topic unless the teacher
  clearly returns to the earlier topic.
- relation of the NEW lines to the CURRENT topic/subtopic:
  same_concept = continues the current subtopic; elaboration = adds detail or examples to it;
  sub_concept = a narrower concept inside it; sibling_concept = a new subtopic of the same topic;
  new_topic = the teacher moved to a different main topic; digression = off-topic aside.
  If there is no current topic yet, use new_topic.
- acts: what the teacher does, with line numbers and content items as short display phrases (max 12 words each),
  close to the teacher's words. Fill only the fields that apply:
  definition: term, definition | explanation, recap, classification: points | process: steps (in order) |
  comparison: compare (the things compared) + pairs (aspect, left, right) | timeline: events (when, what) |
  formula: formula {expression, variables [{symbol, meaning}]} | cause_effect: causes [{cause, effect}] |
  example, application: examples or points.
  act is one of: definition, explanation, process, comparison, example, formula, cause_effect, timeline,
  classification, application, question, recap, transition, other.
- added = true only for a small clarifying addition the teacher did not say (rare). Never go beyond the lecture's
  scope or the grade level.
- meta_lines: numbers of lines that are classroom management or talk about the display/board, not content.
  Lines marked (maybe-meta) are suspected.
- concerns: check every NEW line for factual errors. A statement that is scientifically or factually wrong
  (e.g. reversed, wrong quantity, wrong cause) is a concern: claim, issue, suggested_correction, confidence (0-1),
  lines. Grade-appropriate simplifications are not concerns. Wrong statements still go in acts as said.
- representation_hint: best visual for the NEW content, one of: definition, concept, key_points, process_flow,
  comparison, timeline, hierarchy, cause_effect, formula, example, application, narrative, none.
- summary_delta: one sentence (max 25 words) on what the NEW lines taught.
- level_estimate (e.g. "Grade 7"; keep a given grade) and subject_estimate (e.g. "Biology").

JSON shape:
{"topic": "", "subtopic": "", "relation": "", "acts": [{"act": "", "lines": [1], "items": {"term": "",
"definition": "", "points": [""], "steps": [""], "compare": ["", ""], "pairs": [{"aspect": "", "left": "",
"right": ""}], "events": [{"when": "", "what": ""}], "formula": {"expression": "", "variables": [{"symbol": "",
"meaning": ""}]}, "causes": [{"cause": "", "effect": ""}], "examples": [""]}, "added": false}],
"representation_hint": "", "meta_lines": [], "concerns": [{"claim": "", "issue": "", "suggested_correction": "",
"confidence": 0.9, "lines": [1]}], "level_estimate": "", "subject_estimate": "", "summary_delta": ""}
Omit empty item fields; concerns is [] when nothing is wrong."""

OUTLINE_MAX_TOKENS = 150
SUMMARY_MAX_TOKENS = 120
_FIELD_MAX_CHARS = 60


class PromptBudgetError(Exception):
    pass


@dataclass
class BuiltPrompt:
    messages: list[dict[str, str]]
    tokens: int          # estimate for the whole prompt
    dynamic_tokens: int  # estimate for the user message


def _clip(text: str, n: int = _FIELD_MAX_CHARS) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _clip_tokens(text: str, max_tokens: int) -> str:
    words = text.split()
    while words and approx_tokens(" ".join(words)) > max_tokens:
        words = words[:-1]
    return " ".join(words)


def outline_lines(state: LectureState) -> list[str]:
    """Current topic first, then the others by recency. One line per topic: title: subtopic; subtopic."""
    topics = sorted(state.outline, key=lambda t: (t.id != state.current_topic_id, -t.last_seen))
    out = []
    for t in topics:
        subs = "; ".join(_clip(s.title, 40) for s in sorted(t.subtopics, key=lambda s: s.first_seen))
        out.append(f"- {_clip(t.title, 50)}" + (f": {subs}" if subs else ""))
    return out


def _fit_outline(lines: list[str], max_tokens: int) -> str:
    kept: list[str] = []
    for line in lines:
        if approx_tokens("\n".join(kept + [line])) > max_tokens:
            break
        kept.append(line)
    if not kept and lines:  # even the current topic line is too long: clip it
        kept = [_clip_tokens(lines[0], max_tokens)]
    return "\n".join(kept)


def build_prompt(state: LectureState, lines: Sequence[BufferedLine], *, dynamic_budget: int,
                 total_budget: int) -> BuiltPrompt:
    setup = state.setup
    fields = [
        f"{k}={_clip(v)}" for k, v in (
            ("subject", setup.subject or state.subject_estimate),
            ("grade", setup.grade_level or state.level_estimate),
            ("expected topic", setup.expected_topic),
        ) if v
    ]
    header = "LECTURE: " + ("; ".join(fields) or "(no setup given)")
    topic = state.topic(state.current_topic_id)
    sub = state.subtopic()
    current = (f"CURRENT: topic={_clip(topic.title)}; subtopic={_clip(sub.title) if sub else '-'}"
               if topic else "CURRENT: (none yet)")
    numbered = "\n".join(
        f"[{i}]{' (maybe-meta)' if l.maybe_meta else ''}{' (question)' if l.question else ''} {' '.join(l.text.split())}"
        for i, l in enumerate(lines, start=1)
    )
    fixed = "\n".join([header, current, "NEW LINES:", numbered])
    room = dynamic_budget - approx_tokens(fixed) - 12  # 12 ≈ section labels and newlines
    outline = _fit_outline(outline_lines(state), max(0, min(OUTLINE_MAX_TOKENS, room)))
    room -= approx_tokens(outline)
    summary = _clip_tokens(state.rolling_summary, max(0, min(SUMMARY_MAX_TOKENS, room)))

    parts = [header]
    if outline:
        parts += ["OUTLINE (topic: subtopics):", outline]
    parts.append(current)
    if summary:
        parts.append(f"RECENT SUMMARY: {summary}")
    parts += ["NEW LINES:", numbered]
    user = "\n".join(parts)
    dyn = approx_tokens(user)
    total = dyn + approx_tokens(SYSTEM_PROMPT)
    if dyn > dynamic_budget or total > total_budget:
        raise PromptBudgetError(f"prompt over budget: dynamic {dyn}/{dynamic_budget}, total {total}/{total_budget}")
    return BuiltPrompt(
        [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}], total, dyn
    )
