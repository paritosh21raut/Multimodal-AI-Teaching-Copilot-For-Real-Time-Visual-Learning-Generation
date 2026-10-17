"""Lecture glossary (F-013 S3, C5): the terms this lecture has shown or the teacher's material spells. They prime
Whisper as the lecture grows (prevention at the source) and fix a misheard term on the slide. Deterministic, 0 tokens.

Sources: the setup (subject, expected topic) and the study material's rare words (F-012) are TRUSTED spellings; from
each interpretation its topic / subtopic titles, defined terms and compared names are LECTURE terms. A lecture term
is admitted when all its words are English (wordfreq, local data; the MiniLM vocabulary lacks "valence",
"photoelectric", "scarcity"), an acronym only when the lecture spells it out ("CNN, convolutional neural network"),
so a misheard form ("Wannesbord theory") is never admitted.

Slide fixes use TRUSTED terms only: a phrase is fixed when it sounds like one and the words that differ are not
English ("photolytic effect" -> "photoelectric effect" when the material has it). Measured on the replay of tests
1-30 (recorded answers): lecture terms as the source gave 10 fixes of which 2-3 were right ("Polydentate ligand" ->
"Monodentate ligand", "PMOS" -> "CMOS", "Stichometry" -> "Chemistry": real terms the word list does not know, only
one of each pair on screen yet); acronyms with rhyming letter names ("TNN" -> "CNN") also gave "GSAT" -> "EMAC" from
a datasheet in the material, so acronyms are never fixed. Trusted terms only: 1 fix, right. Real-word mishearings
("Sky City" for "Scarcity") are never fixed. Every fix is a transcription concern
(wrong = heard, right = shown), logged [HEARD].
"""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from functools import lru_cache
from difflib import SequenceMatcher
from typing import Iterable, Optional, Sequence

from copilot.core.textutil import stem

log = logging.getLogger(__name__)

MAX_TERM_WORDS = 4
PROMPT_TERMS = 24          # newest lecture terms in Whisper's prompt (with the study terms: ≤ ~40 words)
MIN_KEY = 4                # phonetic key length of the differing part
MATCH = (0.8, 0.75, 0.7)   # sound-alike ratio of the differing part: key < 6, 6-7, >= 8 letters ("Wannesbord" 0.7)
CONSONANTS = 0.75          # ... and of its consonants ("Stichometry" ~ "Schematics" 0.74 by sound, 0.67 here)
_WORD = re.compile(r"[A-Za-z][A-Za-z'’-]*")
_ACRONYM = re.compile(r"^[A-Z]{2,5}s?$")
ENGLISH_ZIPF = 1.0         # wordfreq: a word seen about once per 100 million words or more is English


@lru_cache(maxsize=1)
def _zipf():
    try:
        from wordfreq import zipf_frequency
    except ImportError:  # no word list: nothing counts as misheard, so nothing is fixed
        log.warning("lecture glossary: wordfreq not installed, misheard terms are not fixed")
        return None
    return zipf_frequency


@lru_cache(maxsize=20000)
def english(word: str) -> bool:
    z = _zipf()
    w = word.lower().strip("'’-")
    return z is None or z(w, "en") >= ENGLISH_ZIPF or z(stem(w), "en") >= ENGLISH_ZIPF


def phonetic(text: str) -> str:
    """A coarse sound key: spelling variants that sound alike get one key ("Valence" ~ "Wallens")."""
    s = re.sub(r"[^a-z]", "", text.lower())
    for a, b in (("ph", "f"), ("ck", "k"), ("q", "k"), ("x", "ks"), ("wh", "v"), ("w", "v"), ("th", "t"),
                 ("dh", "d"), ("gh", "g"), ("z", "s"), ("y", "i")):
        s = s.replace(a, b)
    s = re.sub(r"c(?=[eiy])", "s", s).replace("c", "k")
    s = re.sub(r"(?<=[^aeiou])h", "", s)
    s = s[:1] + re.sub(r"[aeiou]+", "a", s[1:])
    return re.sub(r"(.)\1+", r"\1", s)


def _same(a: str, b: str) -> bool:
    return a.lower() == b.lower() or stem(a) == stem(b)


def initials(text: str) -> str:
    return "".join(w[0] for w in _WORD.findall(text) if w[0].isalpha()).upper()


@dataclass(frozen=True)
class Fix:
    heard: str
    shown: str


class Glossary:
    def __init__(self) -> None:
        self.terms: dict[str, str] = {}          # lower -> display form, in the order admitted
        self.trusted: dict[str, str] = {}        # the setup's and the study material's terms (they fix slides)
        self.study: list[str] = []               # the study material's rare words (Whisper's prompt)
        self._expanded: set[str] = set()         # acronyms the lecture spelled out

    # ---- admission ------------------------------------------------------------------------------------------
    def known(self, word: str) -> bool:
        return english(word)

    def add(self, term: str, trusted: bool = False) -> bool:
        """Admit a term (trusted: setup / study material). True when it is new."""
        term = " ".join(term.split()).strip(" .,:;")
        words = term.split()
        if not term or len(words) > MAX_TERM_WORDS or term.lower() in self.terms:
            return False
        if _ACRONYM.match(term):
            if not (trusted or term.rstrip("s") in self._expanded):
                return False
        elif not trusted and not all(self.known(w) or w.isdigit() for w in _WORD.findall(term)):
            return False
        self.terms[term.lower()] = term
        if trusted:
            self.trusted[term.lower()] = term
        return True

    def spelled_out(self, texts: Iterable[str]) -> None:
        """Acronyms whose expansion the lecture says ("CNN, convolutional neural network ...")."""
        for t in texts:
            words = _WORD.findall(t)
            for i, w in enumerate(words):
                if _ACRONYM.match(w):
                    a = w.rstrip("s")
                    near = words[max(0, i - 6): i] + words[i + 1: i + 1 + 6]
                    for j in range(len(near) - len(a) + 1):
                        if initials(" ".join(near[j: j + len(a)])) == a:
                            self._expanded.add(a)
                            break

    def learn(self, names: Iterable[str], texts: Iterable[str] = ()) -> list[str]:
        """Admit what an interpretation names (titles, defined terms, compared names); returns the new terms."""
        self.spelled_out(texts)
        return [n for n in names if n and self.add(n)]

    def prompt_terms(self) -> list[str]:
        lecture = [t for t in self.terms.values() if t not in self.study]
        return self.study + lecture[-PROMPT_TERMS:]

    # ---- fixing ---------------------------------------------------------------------------------------------
    def _phrase(self, words: list[str], j: int, i: int) -> Optional[tuple[float, int, str]]:
        """The best glossary term the words from j on sound like, the heard part covering the unknown word i:
        (ratio, number of words heard, term)."""
        best: Optional[tuple[float, int, str]] = None
        for term in self.trusted.values():
            tw = term.split()
            if _ACRONYM.match(term):
                continue
            for n in range(max(1, i - j + 1), len(tw) + 2):
                heard = words[j: j + n]
                if len(heard) < n:
                    break
                # shared words at the ends anchor the match; the rest is the misheard part
                h, g = list(heard), list(tw)
                while h and g and _same(h[-1], g[-1]):
                    h, g = h[:-1], g[:-1]
                while h and g and _same(h[0], g[0]):
                    h, g = h[1:], g[1:]
                if not h or not g or any(self.known(w) for w in h):
                    continue
                kh, kg = phonetic("".join(h)), phonetic("".join(g))
                if len(kh) < MIN_KEY:
                    continue
                r = SequenceMatcher(None, kh, kg).ratio()
                if r < MATCH[(len(kh) >= 6) + (len(kh) >= 8)] or SequenceMatcher(
                        None, kh.replace("a", ""), kg.replace("a", "")).ratio() < CONSONANTS:
                    continue
                if best is None or r > best[0]:
                    best = (r, n, term)
        return best

    def fix_text(self, text: str) -> tuple[str, list[Fix]]:
        if not text or not self.trusted:
            return text, []
        fixes: list[Fix] = []
        spans = list(_WORD.finditer(text))
        words = [m.group(0) for m in spans]
        glossary_words = {w.lower() for t in self.terms.values() for w in t.split()}
        out, last, done, i = [], 0, 0, 0
        while i < len(words):
            w = words[i]
            repl: Optional[tuple[int, int, str]] = None  # (first word, number of words, shown)
            if not _ACRONYM.match(w) and not self.known(w) and w.lower() not in glossary_words:
                found = [(r, j, n, t) for j in range(max(done, i - 3), i + 1)
                         if (m := self._phrase(words, j, i)) for r, n, t in [m]]
                if found:
                    _, j, n, t = max(found)
                    repl = (j, n, t)
            if repl is None:
                i += 1
                continue
            j, n, shown = repl
            start, end = spans[j].start(), spans[j + n - 1].end()
            heard = text[start:end]
            if heard[:1].islower() and not shown.isupper() and not all(x[:1].isupper() for x in shown.split()):
                shown = shown[:1].lower() + shown[1:]  # mid-sentence: "the photoelectric effect"
            elif heard[:1].isupper():
                shown = shown[:1].upper() + shown[1:]
            out.append(text[last:start])
            out.append(shown)
            fixes.append(Fix(heard, shown))
            last, done, i = end, j + n, j + n
        out.append(text[last:])
        return "".join(out), fixes


def names_of(it) -> list[str]:
    """What an interpretation names: topic, subtopic, defined terms, compared names."""
    out = [it.topic, it.subtopic]
    for a in it.acts:
        out += [a.items.term, *a.items.compare]
    split = []
    for n in out:  # "Convolutional Neural Network (CNN)" -> the name and its acronym
        m = re.match(r"^(.+?)\s*\(([^)]+)\)$", n or "")
        split += [m.group(1), m.group(2)] if m else [n]
    return [n for n in split if n]


def fix_interpretation(glossary: Glossary, it, lines: Sequence[str]):
    """Misheard terms in an interpretation's slide text, fixed from the glossary; each fix becomes a transcription
    concern. Returns (interpretation, fixes)."""
    from copilot.core.interpretation import ConcernItem, ContentItems

    fixes: list[Fix] = []

    def f(v):
        if isinstance(v, str):
            t, fx = glossary.fix_text(v)
            fixes.extend(fx)
            return t
        if isinstance(v, list):
            return [f(x) for x in v]
        if isinstance(v, dict):
            return {k: f(x) for k, x in v.items()}
        return v

    acts = []
    for a in it.acts:
        items = a.items.model_dump()
        new = f(items)
        acts.append(a if new == items else a.model_copy(update={"items": ContentItems.model_validate(new)}))
    topic, subtopic = f(it.topic), f(it.subtopic)
    if not fixes:
        return it, []
    seen: set[tuple[str, str]] = set()
    concerns = list(it.concerns)
    for fx in fixes:
        if (fx.heard.lower(), fx.shown.lower()) in seen:
            continue
        seen.add((fx.heard.lower(), fx.shown.lower()))
        line = next((n for n, l in enumerate(lines, start=1) if fx.heard.lower() in l.lower()), 1)
        concerns.append(ConcernItem(
            claim=fx.heard, issue=f"Heard “{fx.heard}”; this lecture shows “{fx.shown}”.",
            suggested_correction=fx.shown, confidence=0.6, lines=[line], kind="transcription",
            wrong=fx.heard, right=fx.shown))
    return it.model_copy(update={"acts": acts, "topic": topic, "subtopic": subtopic, "concerns": concerns}), fixes
