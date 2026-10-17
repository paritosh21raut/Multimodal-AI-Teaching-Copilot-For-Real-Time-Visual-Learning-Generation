"""The recap after a simulation (F-014 S1), deterministic: what the teacher taught while the simulation ran, without
the talk about its parameters.

While simulation mode is on the interpretations still run, but their pieces are collected instead of placed. When the
mode ends, `recap_pieces` keeps the key points, principles, definitions, formulas and conclusions ("friction opposes
the tendency to move", "a = (F - μmg)/m") and drops the parameter talk ("we apply a force of 20 N", "now make it 30",
"the angle is 45 degrees", "let's see what happens", "so a = 2.04 m/s²"):
    - a line that states a value (a quantity the values parser reads, "μ = 0.3", "5 kg") is dropped unless it states
      a general rule too ("... always opposes ...", "... is proportional to ...")
    - a line that sets up or changes the scene ("let's assume", "imagine", "make it", "if we push it with") is dropped
    - a formula is kept unless it only substitutes numbers ("f = 0.2 × 49 = 9.8 N", "a = 2.04 m/s²")
    - definitions are kept; duplicates (same words) are dropped
The kept pieces are the model's own content of what was said (V1's truthfulness rules apply upstream); nothing is
added here. No piece kept -> no recap slide.
"""
from __future__ import annotations

import re
from dataclasses import replace
from typing import Iterable

from copilot.presentation.content import Piece
from copilot.simulation.values import NUM, heard

_CHATTER = re.compile(
    r"\b(?:let'?s (?:see|assume|say|take|consider|imagine|suppose|change|make|try|put|set|increase|decrease|apply|"
    r"push|pull|look at what)|let us (?:see|assume|say|take|consider|imagine|suppose|change)|now (?:make|assume|take|"
    r"change|set|increase|decrease|double|halve)|(?:make|change|set|put) it\b|what happens|see what happens|what if|"
    r"imagine|suppose|assume|consider|if (?:we|i|you) (?:apply|push|pull|give|make|take|change|increase|decrease)|"
    r"is applied|(?:we|i) (?:apply|push|pull|exert|give)|double (?:it|the)|halve (?:it|the)|"
    r"(?:in|on) (?:the|this) simulation|the simulation|slider|on the screen|in this case|back to the (?:slides|notes))\b", re.IGNORECASE)
# a general rule: these keep a line even when it names a value
_RULE = re.compile(
    r"\b(?:always|never|oppos\w*|proportional|inversely|independent of|depends? on|directly|increas\w*|decreas\w*|"
    r"greater|less|larger|smaller|more|fewer|faster|slower|because|therefore|hence|law|limit\w*|maximum|minimum|"
    r"tendency|perpendicular|parallel|regardless|whatever|any)\b", re.IGNORECASE)
_ASSIGN = re.compile(rf"(?:^|[\s(])[A-Za-zμθα-ω](?:_?\w)?\s*(?:=|is|equals)\s*{NUM}", re.IGNORECASE)
_NUMBER_WITH_UNIT_OR_CALC = re.compile(r"\d\s*(?:[×x*/+−-]\s*\d|[a-zA-Zμ°%²]|$)")


def _states_value(text: str) -> bool:
    """A line that names a quantity's value: "5 kg", "an angle of 30 degrees", "μ = 0.3", "a = 2.04 m/s²"."""
    if any(h.kind not in ("rough", "force_dir", "force_mode") for h in heard(text)):
        return True
    return bool(_ASSIGN.search(text))


def chatter(text: str) -> bool:
    """Parameter talk (dropped from the recap), not a key point."""
    t = " ".join(text.split())
    if not t:
        return True
    if _CHATTER.search(t):
        return True
    return _states_value(t) and not _RULE.search(t)


def _formula_kept(p: Piece) -> bool:
    f = p.formula
    if f is None:
        return False
    if f.standard:  # a named equation from the library: the law itself
        return True
    expr = f.latex or f.expression
    # "f = 0.2 × 49 = 9.8 N" / "a = 2.04 m/s²": numbers substituted, not the relation
    return not _NUMBER_WITH_UNIT_OR_CALC.search(re.sub(r"\\frac\{1\}\{2\}|1/2|\^\{?\d\}?|_\{?\w+\}?", "", expr))


def _key(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s]", " ", text.lower()).split())


def recap_pieces(pieces: Iterable[Piece]) -> tuple[list[Piece], int]:
    """(the pieces worth keeping, how many items were dropped as parameter talk)."""
    kept: list[Piece] = []
    seen: set[str] = set()
    dropped = 0

    def new(text: str) -> bool:
        k = _key(text)
        if not k or k in seen:
            return False
        seen.add(k)
        return True

    for p in pieces:
        if p.kind == "formula":
            if _formula_kept(p) and new(p.formula.expression if p.formula else ""):
                kept.append(p)
            else:
                dropped += 1
            continue
        if p.kind == "definition":
            if p.term and p.definition and not _CHATTER.search(p.definition) and new(p.term + " " + p.definition):
                kept.append(p)
            else:
                dropped += 1
            continue
        if p.kind == "example":  # the simulation itself was the example: its numbers are parameter talk
            texts = [x for x in p.texts if not chatter(x)]
            dropped += len(p.texts) - len(texts)
            texts = [x for x in texts if new(x)]
            if texts:
                kept.append(p.with_texts(texts))
            continue
        if p.kind in ("comparison", "timeline", "tree", "groups"):
            if any(chatter(x) for x in p.all_text() if x):
                dropped += 1
                continue
            if new(" ".join(p.all_text())):
                kept.append(p)
            continue
        if p.kind in ("facts", "causes") and p.pairs:  # (label, value) pairs: a value is a parameter
            pairs = tuple(pr for pr in p.pairs if not chatter(f"{pr[0]}: {pr[1]}"))  # "Coefficient of friction: 0.2"
            dropped += len(p.pairs) - len(pairs)
            pairs = tuple(pr for pr in pairs if new(f"{pr[0]} {pr[1]}"))
            if pairs:
                kept.append(replace(p, pairs=pairs))
            continue
        # points / steps / causes: item by item
        texts = [x for x in p.texts if not chatter(x)]
        dropped += len(p.texts) - len(texts)
        texts = [x for x in texts if new(x)]
        if texts:
            kept.append(p.with_texts(texts))
    return kept, dropped
