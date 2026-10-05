"""Interpreter: bounded prompt → LLM router → strict JSON validation → one repair → deterministic fallback."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence, get_args

from pydantic import ValidationError

from copilot.core.interpretation import (
    ActKind,
    ContentItems,
    DiscourseAct,
    Interpretation,
    Representation,
)
from copilot.core.memory import titles_match
from copilot.core.state import LectureState
from copilot.core.textutil import approx_tokens, ends_sentence
from copilot.llm.router import AllProvidersFailed, LLMRouter
from copilot.understanding.gate import BufferedLine
from copilot.understanding.grounding import enforce_grounding
from copilot.understanding.prompt import BuiltPrompt, PromptBudgetError, build_prompt

log = logging.getLogger(__name__)

_ACTS = set(get_args(ActKind))
_REPRS = set(get_args(Representation))
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class InvalidInterpretation(ValueError):
    pass


@dataclass
class InterpreterSettings:
    dynamic_budget_tokens: int = 1200
    prompt_budget_tokens: int = 3000
    max_output_tokens: int = 1400
    interpret_deadline_s: float = 15.0
    min_concern_confidence: float = 0.6
    min_transcription_confidence: float = 0.3  # suspected mis-hearings are cheap to show the teacher


@dataclass
class InterpretResult:
    interpretation: Interpretation
    provider: str = ""
    latency_ms: float = 0.0
    fallback: bool = False
    fallback_reason: str = ""
    prompt_tokens: int = 0
    repaired: bool = False
    attempts: list[str] = field(default_factory=list)


def _normalise(data: Any) -> Any:
    """Tolerate harmless deviations (case, unknown act/hint names) before strict validation."""
    if not isinstance(data, dict):
        return data
    for key in ("relation", "representation_hint"):
        if isinstance(data.get(key), str):
            data[key] = data[key].strip().lower().replace(" ", "_").replace("-", "_")
    hint = data.get("representation_hint")
    if not (isinstance(hint, str) and hint in _REPRS):
        data["representation_hint"] = "none"
    acts = data.get("acts")
    if isinstance(acts, list):
        for a in acts:
            if isinstance(a, dict) and isinstance(a.get("act"), str):
                act = a["act"].strip().lower().replace(" ", "_").replace("-", "_")
                a["act"] = act if act in _ACTS else "other"
            if isinstance(a, dict) and isinstance(a.get("items"), dict):
                _normalise_items(a["items"])
    for key in ("topic", "subtopic"):
        if data.get(key) is None:
            data[key] = ""
    revs = data.get("revisions")
    if isinstance(revs, list):
        data["revisions"] = [r for r in revs if isinstance(r, dict) and isinstance(r.get("ref"), str)
                             and isinstance(r.get("text"), str) and r["text"].strip()]
    elif revs is not None:
        data["revisions"] = []
    concerns = data.get("concerns")
    if isinstance(concerns, list):
        for c in concerns:
            if isinstance(c, dict):
                for k in ("wrong", "right", "suggested_correction", "claim", "issue"):
                    if c.get(k) is None:
                        c[k] = ""
                    elif not isinstance(c[k], str):
                        c[k] = str(c[k])
    return data


_STR_LISTS = ("points", "steps", "compare", "examples")
_SHAPED = {"pairs": ("aspect", "left", "right"), "events": ("when", "what"), "causes": ("cause", "effect")}


def _normalise_items(items: dict) -> None:
    """Shape-only fixes that keep every value the model produced (no content is invented or dropped)."""
    for key in _STR_LISTS:
        v = items.get(key)
        if isinstance(v, str):
            items[key] = [p.strip() for p in re.split(r"\s+vs\.?\s+", v) if p.strip()] if key == "compare" else [v]
        elif isinstance(v, list):
            items[key] = [x if isinstance(x, str) else " ".join(str(y) for y in x.values()) if isinstance(x, dict)
                          else str(x) for x in v if x is not None]
    for key, fields in _SHAPED.items():
        v = items.get(key)
        if isinstance(v, list):
            items[key] = [dict(zip(fields, x)) if isinstance(x, (list, tuple)) and len(x) == len(fields) else x
                          for x in v]
    for key in ("term", "definition", "label"):
        if items.get(key) is None:
            items[key] = ""
    facts = items.get("facts")
    if isinstance(facts, list):
        out = []
        for f in facts:
            if isinstance(f, (list, tuple)) and len(f) == 2:
                f = {"label": str(f[0]), "value": str(f[1])}
            elif isinstance(f, str):
                label, _, value = f.partition(":")
                f = {"label": label.strip(), "value": value.strip()}
            if isinstance(f, dict) and str(f.get("label") or "").strip():
                out.append({"label": str(f["label"]), "value": str(f.get("value") or "")})
        items["facts"] = out
    groups = items.get("groups")
    if isinstance(groups, list):
        out = []
        for g in groups:
            if isinstance(g, dict) and str(g.get("label") or "").strip():
                its = g.get("items") or []
                its = its if isinstance(its, list) else [its]
                out.append({"label": str(g["label"]), "items": [str(x) for x in its if x is not None]})
        items["groups"] = out


def parse_interpretation(text: str) -> Interpretation:
    raw = _FENCE.sub("", text.strip())
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end <= start:
        raise InvalidInterpretation("no JSON object in output")
    try:
        data = json.loads(raw[start: end + 1])
    except json.JSONDecodeError as e:
        raise InvalidInterpretation(f"invalid JSON: {e}") from e
    try:
        data = _normalise(data)
    except Exception as e:  # odd shapes must lead to repair/fallback, never escape
        raise InvalidInterpretation(f"unexpected shape: {type(e).__name__}: {e}") from e
    try:
        return Interpretation.model_validate(data)
    except ValidationError as e:
        raise InvalidInterpretation(f"schema: {e.errors(include_url=False)[:3]}") from e


def _sanitise(it: Interpretation, n_lines: int, min_conf: float, state: LectureState,
              min_transcription_conf: float = 0.3) -> Interpretation:
    """Deterministic post-processing: drop out-of-range line numbers and low-confidence concerns, and make
    relation and subtopic agree (a new facet under the same subtopic title is treated as a continuation)."""
    def ok(lines: list[int]) -> list[int]:
        return [i for i in lines if 1 <= i <= n_lines]

    relation = it.relation
    topic, sub = state.topic(state.current_topic_id), state.subtopic()
    if (relation in ("sibling_concept", "sub_concept") and topic and titles_match(it.topic, topic.title)
            and titles_match(it.subtopic or topic.title, sub.title if sub else topic.title)):
        log.info("relation %s with unchanged subtopic %r -> same_concept", relation, it.subtopic)
        relation = "same_concept"
    concerns = []
    for c in it.concerns:
        if c.confidence < (min_transcription_conf if c.kind == "transcription" else min_conf):
            continue
        upd: dict = {"lines": ok(c.lines)}
        if not (c.wrong and c.right):  # derive the minimal differing words from claim vs correction
            wrong, right = minimal_change(c.claim, c.suggested_correction)
            upd.update({"wrong": c.wrong or wrong, "right": c.right or right})
        concerns.append(c.model_copy(update=upd))
    refs = state.slide_refs
    revisions = [r for r in it.revisions if r.ref.strip().upper() in refs]
    if len(revisions) != len(it.revisions):
        log.info("dropped %d revision(s) with unknown refs", len(it.revisions) - len(revisions))
    return it.model_copy(update={
        "relation": relation,
        "acts": [a.model_copy(update={"lines": ok(a.lines)}) for a in it.acts],
        "meta_lines": ok(it.meta_lines),
        "concerns": concerns,
        "revisions": [r.model_copy(update={"ref": r.ref.strip().upper()}) for r in revisions],
    })




def minimal_change(said: str, corrected: str) -> tuple[str, str]:
    """The smallest differing word span between what was said and the correction ("Neptune" -> "Uranus")."""
    from difflib import SequenceMatcher

    a, b = said.split(), corrected.split()
    norm = lambda ws: [w.lower().strip(".,;:!?") for w in ws]  # noqa: E731
    ops = [o for o in SequenceMatcher(None, norm(a), norm(b)).get_opcodes() if o[0] != "equal"]
    if not ops:
        return "", ""
    i1, i2, j1, j2 = ops[0][1], ops[-1][2], ops[0][3], ops[-1][4]
    wrong = " ".join(a[i1:i2]).strip(".,;:!?")
    right = " ".join(b[j1:j2]).strip(".,;:!?")
    if len(wrong.split()) > 6 or len(right.split()) > 6:  # not a small substitution: no safe token toggle
        return "", ""
    return wrong, right


FILL_ACTS = {"explanation", "recap", "application", "example", "classification"}
FILL_MAX_WORDS = 16
_LEAD_FILLERS = re.compile(r"^(?:(?:so|and|now|okay|ok|well|also|then|basically|actually|you know|"
                           r"we have|there is|there are)[,\s]+)+", re.IGNORECASE)


def tidy_spoken(text: str) -> str:
    """Spoken line → plain slide text: leading fillers dropped, first letter capitalised, no final period."""
    t = _LEAD_FILLERS.sub("", " ".join(text.split())).strip().rstrip(".")
    return t[:1].upper() + t[1:] if t else t


def _fill_empty_acts(it: Interpretation, lines: Sequence[BufferedLine]) -> Interpretation:
    """A content act the model returned without items gets its own transcript line(s) as the point (the teacher's
    words, trimmed). Meta lines and lines already used by another act are skipped. Logged, never invented."""
    meta = set(it.meta_lines)
    used = {n for a in it.acts if a.items != ContentItems() for n in a.lines}
    acts = []
    for a in it.acts:
        if a.act in FILL_ACTS and a.items == ContentItems() and not a.added:
            # only complete sentences: a fragment ("the walls around it") is not slide content on its own
            texts = [tidy_spoken(" ".join(lines[n - 1].text.split()[:FILL_MAX_WORDS])) for n in a.lines
                     if 1 <= n <= len(lines) and n not in meta and n not in used and not lines[n - 1].maybe_meta
                     and ends_sentence(lines[n - 1].text) and len(lines[n - 1].text.split()) >= 4]
            if texts:
                log.info("act %s on lines %s had no items; using the spoken line", a.act, a.lines)
                a = a.model_copy(update={"items": ContentItems(points=texts)})
        acts.append(a)
    return it.model_copy(update={"acts": acts})


_EXAMPLE_CUE = re.compile(r"\b(?:for example|for instance|such as|e\.?g\.?|example|like)\b", re.IGNORECASE)


def _examples_need_a_cue(it: Interpretation, lines: Sequence[BufferedLine]) -> Interpretation:
    """An "example" act whose lines never present an example ("for example", "such as", ...) is a statement of
    fact: its items become points, so facts are not shown as example cards."""
    acts = []
    for a in it.acts:
        if a.act == "example" and a.items.examples:
            said = " ".join(lines[n - 1].text for n in a.lines if 1 <= n <= len(lines))
            if not _EXAMPLE_CUE.search(said):
                items = a.items.model_copy(update={"points": a.items.points + a.items.examples, "examples": []})
                a = a.model_copy(update={"act": "explanation", "items": items})
        acts.append(a)
    return it.model_copy(update={"acts": acts})


# "Atoms are the smallest particles of an element ..." -> term "Atoms" + definition (fallback only)
_DEFINES = re.compile(r"^(?P<term>[A-Z][A-Za-z-]*(?:\s+[A-Za-z-]+){0,2}?)\s+(?:is|are|means)\s+"
                      r"(?P<def>(?:the|a|an|any|anything)\b.{8,})$")
_NOT_TERMS = {"it", "this", "that", "there", "they", "these", "those", "he", "she", "we", "you", "which", "what"}


def fallback_interpretation(state: LectureState, lines: Sequence[BufferedLine]) -> Interpretation:
    """Deterministic interpretation when no LLM answer is usable: only complete spoken sentences become slide text,
    tidied (fillers dropped); "X is/are the ..." sentences become definitions; "let's learn about X" moves to the
    subtopic X. Fragments ("diatomic triatomic or ...") are not slide text; they stay in the transcript and log."""
    from copilot.understanding.prompt import announced_subject

    topic = state.topic(state.current_topic_id)
    sub = state.subtopic()
    title = topic.title if topic else (state.setup.expected_topic or "Lecture")
    acts: list[DiscourseAct] = []
    points: list[str] = []
    announced = ""
    for n, l in enumerate(lines, start=1):
        text = " ".join(l.text.split())
        if l.maybe_meta or not text:
            continue
        announced = announced or announced_subject(text)
        if not text[0].isupper() or not ends_sentence(text) or len(text.split()) < 4:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+(?=[A-Z])", text):
            tidy = tidy_spoken(" ".join(sentence.split()[:30]))
            if len(tidy.split()) < 4 or tidy.endswith("?") or announced_subject(tidy):
                continue
            m = _DEFINES.match(tidy)
            if m and m.group("term").split()[0].lower() not in _NOT_TERMS:
                acts.append(DiscourseAct(act="definition", lines=[n], items=ContentItems(
                    term=m.group("term"), definition=m.group("def"))))
            else:
                points.append(tidy)
    if points:
        acts.append(DiscourseAct(act="explanation", lines=list(range(1, len(lines) + 1)),
                                 items=ContentItems(points=points)))
    subtopic, relation = (sub.title if sub else ""), ("same_concept" if topic else "new_topic")
    if announced and topic is not None:
        small = {"and", "or", "of", "the", "in", "on", "a", "an", "to"}
        words = announced.split()
        subtopic = " ".join(w if (i and w.lower() in small) else w[:1].upper() + w[1:] for i, w in enumerate(words))
        relation = "sibling_concept"
    return Interpretation(topic=title, subtopic=subtopic, relation=relation, acts=acts,
                          representation_hint="definition" if any(a.act == "definition" for a in acts)
                          else "key_points")


class Interpreter:
    def __init__(self, router: Optional[LLMRouter], settings: Optional[InterpreterSettings] = None) -> None:
        self.router = router
        self.s = settings or InterpreterSettings()

    def build(self, state: LectureState, lines: Sequence[BufferedLine]) -> BuiltPrompt:
        return build_prompt(state, lines, dynamic_budget=self.s.dynamic_budget_tokens,
                            total_budget=self.s.prompt_budget_tokens)

    async def interpret(self, state: LectureState, lines: Sequence[BufferedLine],
                        prompt: Optional[BuiltPrompt] = None) -> InterpretResult:
        """Always returns a result for these lines: an LLM interpretation or a logged deterministic fallback."""
        t0 = time.perf_counter()
        try:
            return await self._interpret(state, lines, prompt, t0)
        except Exception as e:  # unexpected failure: the lines must still be interpreted (CancelledError passes)
            log.exception("interpreter failed unexpectedly")
            return self._fallback(state, lines, f"unexpected error: {type(e).__name__}: {e}", t0)

    async def _interpret(self, state: LectureState, lines: Sequence[BufferedLine], prompt: Optional[BuiltPrompt],
                         t0: float) -> InterpretResult:
        if prompt is None:
            try:
                prompt = self.build(state, lines)
            except PromptBudgetError as e:
                log.error("%s", e)
                return self._fallback(state, lines, str(e), t0)
        if self.router is None:
            return self._fallback(state, lines, "no LLM providers configured", t0, prompt.tokens)

        log.debug("interpretation prompt (%d tokens): %s", prompt.tokens, prompt.messages[1]["content"])
        deadline = time.monotonic() + self.s.interpret_deadline_s
        attempts: list[str] = []
        try:
            res = await self.router.complete(prompt.messages, est_tokens=prompt.tokens,
                                             max_tokens=self.s.max_output_tokens, deadline=deadline)
            attempts += res.attempts
        except AllProvidersFailed as e:
            return self._fallback(state, lines, f"llm: {e}", t0, prompt.tokens, attempts)

        log.debug("interpretation raw output from %s: %s", res.entry, res.response.text[:2000])
        repaired = False
        try:
            it = parse_interpretation(res.response.text)
        except InvalidInterpretation as first:
            log.warning("interpretation from %s invalid (%s); one repair attempt", res.entry, first)
            instruction = f"That output was invalid: {str(first)[:300]}. Reply with the corrected JSON object only."
            room = self.s.prompt_budget_tokens - prompt.tokens - approx_tokens(instruction) - 8
            if room < 50:
                return self._fallback(state, lines, f"invalid output, no budget to repair: {first}", t0,
                                      prompt.tokens, attempts)
            echo = res.response.text
            while approx_tokens(echo) > room:  # the repair prompt obeys the same budget
                echo = echo[: int(len(echo) * 0.8)]
            repair_msgs = prompt.messages + [
                {"role": "assistant", "content": echo},
                {"role": "user", "content": instruction},
            ]
            repair_tokens = prompt.tokens + approx_tokens(echo) + approx_tokens(instruction)
            try:
                res = await self.router.complete(
                    repair_msgs, est_tokens=repair_tokens,
                    max_tokens=self.s.max_output_tokens, deadline=deadline,
                )
                attempts += res.attempts
                it = parse_interpretation(res.response.text)
                repaired = True
            except (AllProvidersFailed, InvalidInterpretation) as second:
                return self._fallback(state, lines, f"invalid output after repair: {second}", t0,
                                      prompt.tokens, attempts)

        it = _fill_empty_acts(_examples_need_a_cue(it, lines), lines)
        it, changed = enforce_grounding(it, [l.text for l in lines])
        if changed:
            log.warning("interpretation from %s changed spoken tokens without saying so; concern added: %s",
                        res.entry, ", ".join(changed))
        it = _sanitise(it, len(lines), self.s.min_concern_confidence, state, self.s.min_transcription_confidence)
        return InterpretResult(it, res.entry, (time.perf_counter() - t0) * 1000, False, "",
                               prompt.tokens, repaired, attempts)

    def _fallback(self, state: LectureState, lines: Sequence[BufferedLine], reason: str, t0: float,
                  prompt_tokens: int = 0, attempts: Optional[list[str]] = None) -> InterpretResult:
        log.warning("interpretation fallback: %s", reason)
        return InterpretResult(fallback_interpretation(state, lines), "", (time.perf_counter() - t0) * 1000,
                               True, reason[:500], prompt_tokens, False, attempts or [])
