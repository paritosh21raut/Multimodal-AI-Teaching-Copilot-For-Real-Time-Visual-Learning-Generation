"""UtteranceFilter: deterministic classroom-talk vs. content classification.

A lexicon/pattern match only *decides* a non-content class when little lecture content remains
once the matched phrase and function words are removed. Otherwise the utterance stays `content`
with `maybe_meta=True`, and the Interpreter makes the final call (never lose content on a guess).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from copilot.core.events import UtteranceKind

_PATTERNS: dict[str, list[str]] = {
    "classroom_management": [
        r"\bgood (morning|afternoon|evening)\b(,? (everyone|everybody|class|students|children|all))?",
        r"\b(take|get) out your( \w+){0,2} (books?|notebooks?|copies|textbooks?)\b",
        r"\b(open|close|put away) your( \w+){0,2} (books?|notebooks?|copies|textbooks?|laptops?|phones?)\b",
        r"\b(turn|go) to page( number)? \w+\b",
        r"\b(be|keep|stay) quiet\b", r"\bsilence\b", r"\bno talking\b", r"\bsettle down\b",
        r"\b(sit|stand) (down|up)\b", r"\battendance\b", r"\broll call\b",
        r"\b(submit|hand in) (your )?(homework|assignments?)\b", r"\bpay attention\b",
        r"\b(write|note|copy) (this|that|it) down\b", r"\braise your hands?\b",
        r"\blet'?s (begin|start)( the class| today'?s class)?\b", r"\bcome in\b",
    ],
    "meta": [
        r"\blook at the (screen|board|slide|projector|diagram|picture)\b",
        r"\b(on|at) the (screen|board|projector)\b", r"\bnext slide\b",
        r"\bcan (you|everyone|everybody)( all)? (see|hear)( (this|me|it))?\b", r"\bis (this|it) visible\b",
        r"\bas you can see( here)?\b",
    ],
    "question_to_class": [
        r"\bany (questions?|doubts?)\b", r"\b(do|did) you (all )?understand\b", r"\bis (that|this|it) clear\b",
        r"\bare you (all )?following\b", r"\b(can|could) (anyone|anybody|someone) tell me\b",
        r"\b(who|does anyone|does anybody) (can )?(know|tell me)\b",
    ],
}
_COMPILED = {k: [re.compile(p, re.IGNORECASE) for p in v] for k, v in _PATTERNS.items()}

_FILLERS = {"um", "uh", "uhh", "umm", "hmm", "ok", "okay", "so", "right", "alright", "yes", "yeah", "no",
            "well", "and", "now", "good", "fine", "huh", "mm", "erm", "ah", "oh"}
# Function words and politeness: not lecture content.
_STOP = {
    "a", "an", "the", "and", "or", "but", "so", "to", "of", "in", "on", "at", "for", "with", "from", "by", "is",
    "are", "was", "were", "be", "been", "it", "this", "that", "these", "those", "i", "you", "we", "they", "he",
    "she", "me", "us", "your", "our", "my", "please", "everyone", "everybody", "all", "now", "today", "okay",
    "ok", "right", "students", "class", "children", "let's", "lets", "can", "will", "just", "here", "there",
    "do", "does", "did", "what", "then", "very", "also", "up", "out", "down", "again", "one", "some", "kindly",
    "thank", "thanks", "quickly", "first",
}
_WORD = re.compile(r"[a-z][a-z'\-]*")
CONTENT_WORDS_MAX = 2  # a match decides the class only if ≤ this many content words remain


@dataclass(frozen=True)
class Classification:
    kind: UtteranceKind
    maybe_meta: bool = False
    rule: str = ""

    @property
    def to_buffer(self) -> bool:
        """Content and questions to the class are lecture discourse; the rest is excluded."""
        return self.kind in ("content", "question_to_class")


def content_words(text: str) -> list[str]:
    return [w for w in _WORD.findall(text.lower()) if w not in _STOP and w not in _FILLERS]


class UtteranceFilter:
    def classify(self, text: str) -> Classification:
        words = _WORD.findall(text.lower())
        if not words:
            if re.search(r"\d", text):  # "9.8", "1, 2, 3": numbers are lecture content
                return Classification("content", maybe_meta=True, rule="numeric")
            return Classification("filler", rule="empty")
        if len(words) <= 3 and all(w in _FILLERS for w in words):
            return Classification("filler", rule="filler_words")

        for kind, patterns in _COMPILED.items():
            remainder = text
            hit = ""
            for p in patterns:
                if p.search(remainder):
                    hit = hit or p.pattern
                    remainder = p.sub(" ", remainder)
            if not hit:
                continue
            if len(content_words(remainder)) <= CONTENT_WORDS_MAX:
                return Classification(kind, rule=f"{kind}:{hit}")  # type: ignore[arg-type]
            return Classification("content", maybe_meta=kind != "question_to_class", rule=f"maybe_{kind}:{hit}")
        return Classification("content", rule="default")
