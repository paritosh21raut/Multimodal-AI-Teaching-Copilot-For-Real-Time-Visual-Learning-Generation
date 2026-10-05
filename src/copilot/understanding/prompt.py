"""Bounded interpretation prompt. The budget is enforced here, in code, before anything is sent."""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Sequence

from copilot.core.state import LectureState
from copilot.core.textutil import approx_tokens
from copilot.understanding.gate import BufferedLine

SYSTEM_PROMPT = """You turn a live classroom lecture into clear projector slides that follow the teacher.
You get the lecture context, the CURRENT SLIDE (its items numbered [S1], [S2], ...) and a few NEW numbered
transcript lines from speech recognition (they can be fragments of one sentence). Reply with ONE JSON object only.

Topic and continuity:
- topic = the main subject (e.g. "Photosynthesis"). subtopic = the concept or facet now being taught: a facet
  ("Definition", "Process", "Importance") or a concept name ("Matter", "Planets"). Two concepts introduced
  together get one subtopic naming both ("Elements and Compounds"); a newly introduced term or concept
  ("natural satellites") gets its own subtopic. Reuse the exact outline title while the
  teacher stays on it. Titles: 1-4 words, Title Case.
- A line tagged (announces: X) names what the teacher moves to next: use X as the new topic (new_topic) when it is
  not part of the CURRENT topic (e.g. galaxies after the solar system), else as the new subtopic.
- A different facet or concept of the same topic = sibling_concept (its subtopic must differ from CURRENT); if the
  NEW lines span two, use the later one. A comparison with an earlier topic stays under the CURRENT topic.
- relation: same_concept (continues), elaboration (adds detail), sub_concept (narrower concept inside it),
  sibling_concept, new_topic (different main topic; also when there is no current topic), digression (aside).

Slide content (acts):
- Only what the teacher taught in the NEW lines; no facts beyond the lecture or the grade level.
- Items are slide text, not transcript: short, clear, complete phrases (max 12 words) a student can recall fast.
  Drop fillers ("so", "now", "we have", "it is"), replace pronouns with what they refer to, join a sentence split
  across lines (or across the CURRENT SLIDE), and simplify wording for the grade. Keep facts, names and numbers.
- Definitions stay exact: the term and the teacher's definition wording (only fillers removed).
- If NEW lines complete or change a CURRENT SLIDE item, return a revision {"ref": "S2", "text": "full new item"}
  instead of a new item (e.g. S2 "Black hole has huge gravity" + NEW "because of which light cannot escape"
  -> revise S2 to "Its gravity is so strong that light cannot escape").
- Transitions/announcements ("now let's learn about X", "today we will ...") and questions to the class are acts
  with NO items. If the teacher corrects themselves ("Uranus, sorry, Neptune ...") use only the corrected words.
- Pick the item type that best fits (fill only what applies):
  definition: term, definition (one act per term; two terms defined -> two definition acts)
  facts: [{label, value}] ONLY for short parallel attributes of different named things (superlatives, records,
    properties), never yes/no or general statements (those are points):
    "Mercury is the smallest planet" -> {"label": "Smallest planet", "value": "Mercury"};
    "Saturn has rings" -> {"label": "Saturn", "value": "Has rings"}
  classification: label (what is classified, e.g. "Branches of chemistry") + points (the kinds), or groups
    [{label, items}] when things are split into named groups (e.g. "Inner planets": Mercury, Venus, Earth, Mars)
  process: steps in order, for any ordered procedure or input -> process -> output flow (never points/examples);
    if the CURRENT SLIDE is a process and the NEW lines continue it, give only the NEW steps
  comparison: compare (the 2 things compared) + pairs (aspect, left, right) | timeline: events (when, what)
  formula: {expression, variables [{symbol, meaning}]} | cause_effect: causes [{cause, effect}]
  explanation, recap: points | example, application: examples (only what the teacher offers as examples)
  act is one of: definition, explanation, process, comparison, example, formula, cause_effect, timeline,
  classification, application, question, recap, transition, other.
- added = true only for a small clarifying addition the teacher did not say (rare).
- meta_lines: lines that are classroom management or talk about the display/board. (maybe-meta) = suspected.

Truthful slides (concerns):
- Acts always hold the CORRECT content. Check every NEW statement; when the teacher states something clearly
  wrong (reversed, wrong name or quantity, wrong cause), put the corrected statement in acts and add a concern:
  kind "factual", claim = what the teacher said, suggested_correction = the correct statement, wrong = the
  wrong word(s) as said, right = the word(s) used instead in acts, issue, confidence (0-1), lines.
- Speech recognition can mis-hear words or formulas ("Omo atomic" for "monoatomic", "6H2" where "6H2O" fits):
  use the intended form in acts and add a concern of kind "transcription" (claim = as heard, wrong/right as
  above, confidence 0.3-0.7).
- Not concerns: grade-level simplifications, facts that depend on definition or where sources differ, and
  anything the teacher already corrected.

Also: representation_hint (definition, concept, key_points, process_flow, comparison, timeline, hierarchy,
cause_effect, formula, example, application, narrative, none); summary_delta (one sentence, max 25 words, on
what the NEW lines taught); level_estimate (e.g. "Grade 7"; keep a given grade); subject_estimate.

JSON shape:
{"topic": "", "subtopic": "", "relation": "", "acts": [{"act": "", "lines": [1], "items": {"term": "",
"definition": "", "label": "", "points": [""], "facts": [{"label": "", "value": ""}], "groups": [{"label": "",
"items": [""]}], "steps": [""], "compare": ["", ""], "pairs": [{"aspect": "", "left": "", "right": ""}],
"events": [{"when": "", "what": ""}], "formula": {"expression": "", "variables": [{"symbol": "", "meaning": ""}]},
"causes": [{"cause": "", "effect": ""}], "examples": [""]}, "added": false}], "revisions": [{"ref": "S1",
"text": ""}], "representation_hint": "", "meta_lines": [], "concerns": [{"kind": "factual", "claim": "",
"issue": "", "suggested_correction": "", "wrong": "", "right": "", "confidence": 0.9, "lines": [1]}],
"level_estimate": "", "subject_estimate": "", "summary_delta": ""}
Omit empty fields; revisions and concerns are [] when there are none."""

OUTLINE_MAX_TOKENS = 150
SUMMARY_MAX_TOKENS = 120
SLIDE_MAX_TOKENS = 160  # numbered items, so revisions can refer to them
_FIELD_MAX_CHARS = 60


_ANNOUNCE = re.compile(
    r"(?:let'?s|let us|we will|we'll|we are going to|now we)\s+(?:now\s+)?(?:talk|learn|study|look|move on|discuss|"
    r"see)\s+(?:about|at|to|on)?\s*(?P<a>[^.?!,;]{2,60})|(?:the\s+)?next topic is\s+(?P<b>[^.?!,;]{2,60})",
    re.IGNORECASE)


def announced_subject(text: str) -> str:
    """"Now let's talk about galaxies." -> "galaxies" (deterministic hint for the model; it decides topic vs facet)."""
    m = _ANNOUNCE.search(text)
    if not m:
        return ""
    subject = (m.group("a") or m.group("b") or "").strip()
    while True:
        stripped = re.sub(r"^(?:the|a|an|how|what|why)\s+", "", subject, flags=re.IGNORECASE)
        if stripped == subject:
            break
        subject = stripped
    return " ".join(subject.split()[:6])


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
        f"[{i}]{' (maybe-meta)' if l.maybe_meta else ''}{' (question)' if l.question else ''}"
        f"{f' (announces: {a})' if (a := announced_subject(l.text)) else ''} {' '.join(l.text.split())}"
        for i, l in enumerate(lines, start=1)
    )
    fixed = "\n".join([header, current, "NEW LINES:", numbered])
    room = dynamic_budget - approx_tokens(fixed) - 12  # 12 ≈ section labels and newlines
    outline = _fit_outline(outline_lines(state), max(0, min(OUTLINE_MAX_TOKENS, room)))
    room -= approx_tokens(outline)
    slide = _clip_tokens(state.slide_context, max(0, min(SLIDE_MAX_TOKENS, room - 4)))
    room -= approx_tokens(slide) + (4 if slide else 0)
    summary = _clip_tokens(state.rolling_summary, max(0, min(SUMMARY_MAX_TOKENS, room)))

    parts = [header]
    if outline:
        parts += ["OUTLINE (topic: subtopics):", outline]
    parts.append(current)
    if slide:
        parts.append(f"CURRENT SLIDE: {slide}")
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
