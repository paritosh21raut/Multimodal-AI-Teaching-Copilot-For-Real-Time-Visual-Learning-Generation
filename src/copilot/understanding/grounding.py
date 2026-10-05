"""Deterministic grounding guard: no silent changes to what the teacher said.

LLMs "helpfully" fix what they believe was mis-heard ("6H2" → "6H2O") without saying so. The projector shows the
correct form (truthful slides), but the teacher must always know: a formula-like token in the model's items that
was not said, with a close spoken variant in the same place, gets a `transcription` concern (wrong = spoken form,
right = shown form) unless the model already raised one. The content itself is not changed here.

Only tokens with an upper-case letter and a digit are checked (CO2, 6H2O, C6H12O6, H2SO4). Symbol forms of
spoken words ("carbon dioxide" → CO2) have no close variant in the transcript and are left alone.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher
from typing import Optional, Sequence

from copilot.core.interpretation import ConcernItem, ContentItems, DiscourseAct, Interpretation

_TOKEN = re.compile(r"[A-Za-z0-9]+")
_FORMULA = re.compile(r"^\d*(?:[A-Z][a-z]?\d*)+$")
_SUBSCRIPTS = str.maketrans("₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹", "01234567890123456789")
_NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve".split())}
MIN_SIMILARITY = 0.6
# Connector words skipped when comparing a token's neighbours ("6CO2 plus 6H2 plus light" ~ "6CO2 + 6H2O + light").
_CONNECTORS = {"plus", "and", "gives", "give", "is", "are", "was", "the", "a", "an", "of", "equals", "yields", "to",
               "produce", "produces", "us", "makes", "into", "with", "or", "in"}
CONCERN_CONFIDENCE = 0.5


def _formula_like(tok: str) -> bool:
    return bool(_FORMULA.match(tok)) and any(c.isdigit() for c in tok) and any(c.isupper() for c in tok)


def _tokens(text: str) -> list[str]:
    return _TOKEN.findall(text.translate(_SUBSCRIPTS))


Candidate = tuple[str, int, str, str]  # spoken token, line, previous and next content word


def _neighbours(toks: list[str], i: int) -> tuple[str, str]:
    prev = next((t.lower() for t in reversed(toks[:i]) if t.lower() not in _CONNECTORS), "")
    nxt = next((t.lower() for t in toks[i + 1:] if t.lower() not in _CONNECTORS), "")
    return prev, nxt


def _same_place(a: tuple[str, str], b: tuple[str, str]) -> bool:
    """Both tokens sit between the same content words (every side known in both must match, at least one)."""
    sides = [(x, y) for x, y in zip(a, b) if x and y]
    return bool(sides) and all(x == y for x, y in sides)


def _source_forms(lines: Sequence[str]) -> tuple[set[str], list[Candidate]]:
    """All spoken forms (adjacent tokens joined, so "6 CO2" and "H 2 O" count) and formula-like candidates."""
    forms: set[str] = set()
    candidates: list[Candidate] = []
    for n, line in enumerate(lines, start=1):
        toks = [_NUMBER_WORDS.get(t.lower(), t) for t in _tokens(line)]
        for i in range(len(toks)):
            for k in range(1, 4):
                if i + k <= len(toks):
                    joined = "".join(toks[i:i + k])
                    forms.add(joined)
                    forms.add(_strip_coeff(joined))  # "6CO2" was said, so "CO2" is grounded too
        candidates += [(t, n, *_neighbours(toks, i)) for i, t in enumerate(toks) if _formula_like(t)]
    return forms, candidates


def _small_edit(model: str, said: str) -> bool:
    """A plausible mis-hearing: an element/digit appended or dropped at the end (6H2 / 6H2O, C6H12O / C6H12O6),
    or only the last character differs (H2SO3 / H2SO4)."""
    short, long_ = sorted((model, said), key=len)
    if long_.startswith(short) and 0 < len(long_) - len(short) <= 2:
        return True
    return len(model) == len(said) and model[:-1] == said[:-1]


def _strip_coeff(tok: str) -> str:
    return tok.lstrip("0123456789")


class _Grounder:
    def __init__(self, lines: Sequence[str], model_tokens: frozenset[str] = frozenset()) -> None:
        self.model_tokens = model_tokens  # tokens the model itself wrote (anywhere in its items)
        self.forms, self.candidates = _source_forms(lines)
        self.mapping: dict[str, tuple[str, int]] = {}  # model token -> (spoken token, line)

    def _closest(self, tok: str, place: tuple[str, str]) -> Optional[tuple[str, int]]:
        """Spoken token the model most likely 'corrected': a small edit of it (6H2 -> 6H2O), starting with the same
        element, in the same place (same neighbouring content words). Never a different molecule the teacher
        named in words ("Water is H2O. Hydrogen peroxide ..." -> model "H2O2" stays)."""
        best, best_r = None, MIN_SIMILARITY
        lead = _strip_coeff(tok)[:1]
        for cand, line, prev, nxt in self.candidates:
            if (_strip_coeff(cand)[:1] != lead or not _small_edit(tok, cand) or cand in self.model_tokens
                    or not _same_place(place, (prev, nxt))):
                continue
            r = SequenceMatcher(None, tok, cand).ratio()
            if r > best_r or (r == best_r and best is None):
                best, best_r = (cand, line), r
        return best

    def fix(self, text: str) -> str:
        if not text:
            return text
        out = text.translate(_SUBSCRIPTS) if any(c in text for c in "₀₁₂₃₄₅₆₇₈₉") else text
        toks = [_NUMBER_WORDS.get(t.lower(), t) for t in _tokens(out)]
        for i, tok in enumerate(toks):
            if not _formula_like(tok) or tok in self.forms:
                continue
            said = self.mapping.get(tok) or self._closest(tok, _neighbours(toks, i))
            if said is None:
                continue
            self.mapping[tok] = said
            bare_tok, bare_said = _strip_coeff(tok), _strip_coeff(said[0])
            if bare_tok != tok and bare_tok not in self.forms and bare_said:
                self.mapping.setdefault(bare_tok, (bare_said, said[1]))  # e.g. variable "H2O" -> "H2"
            out = re.sub(rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])", said[0], out)
        return out

    def items(self, it: ContentItems) -> ContentItems:
        f = self.fix
        formula = it.formula
        if formula is not None:  # expression first: its mapping also covers coefficient-free variable symbols
            expr = f(formula.expression)
            formula = formula.model_copy(update={
                "expression": expr,
                "variables": [v.model_copy(update={"symbol": f(v.symbol), "meaning": f(v.meaning)})
                              for v in formula.variables],
            })
        return it.model_copy(update={
            "term": f(it.term), "definition": f(it.definition),
            "points": [f(x) for x in it.points], "steps": [f(x) for x in it.steps],
            "compare": [f(x) for x in it.compare], "examples": [f(x) for x in it.examples],
            "pairs": [p.model_copy(update={"aspect": f(p.aspect), "left": f(p.left), "right": f(p.right)})
                      for p in it.pairs],
            "events": [e.model_copy(update={"when": f(e.when), "what": f(e.what)}) for e in it.events],
            "causes": [c.model_copy(update={"cause": f(c.cause), "effect": f(c.effect)}) for c in it.causes],
            "formula": formula,
        })


def _act_texts(it: ContentItems) -> list[str]:
    out = [it.term, it.definition, *it.points, *it.steps, *it.compare, *it.examples]
    out += [x for p in it.pairs for x in (p.aspect, p.left, p.right)]
    out += [x for e in it.events for x in (e.when, e.what)]
    out += [x for c in it.causes for x in (c.cause, c.effect)]
    if it.formula:
        out += [it.formula.expression, *(x for v in it.formula.variables for x in (v.symbol, v.meaning))]
    return [t for t in out if t]


def enforce_grounding(it: Interpretation, lines: Sequence[str]) -> tuple[Interpretation, list[str]]:
    """Report silent corrections of formula-like tokens as concerns; the shown content stays as the model wrote it.

    Returns the interpretation (with any added concerns) and the changes found ("6H2->6H2O") for logging.
    """
    model_tokens = frozenset(t for a in it.acts for text in _act_texts(a.items) for t in _tokens(text))
    g = _Grounder(lines, model_tokens)
    for a in it.acts:
        g.items(a.items)  # detection only (fills g.mapping); the result is discarded
    if not g.mapping:
        return it, []
    concerns = list(it.concerns)
    changes: list[str] = []
    raised: set[str] = set()
    for tok, (said, line) in g.mapping.items():
        changes.append(f"{said}->{tok}")
        if any(o != tok and _strip_coeff(o) == tok for o in g.mapping):
            continue  # coefficient-free twin ("H2O" of "6H2O"): one concern covers both
        mentioned = any({tok, said} & set(_tokens(f"{c.claim} {c.issue} {c.suggested_correction} {c.wrong} {c.right}"))
                        for c in concerns)
        if mentioned or said in raised:
            continue  # the model already raised it
        raised.add(said)
        concerns.append(ConcernItem(
            claim=said, issue=f"Heard “{said}”; the slide shows “{tok}”.", suggested_correction=tok,
            confidence=CONCERN_CONFIDENCE, lines=[line], kind="transcription", wrong=said, right=tok,
        ))
    return it.model_copy(update={"concerns": concerns}), changes
