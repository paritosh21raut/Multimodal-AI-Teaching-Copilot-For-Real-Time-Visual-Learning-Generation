"""The story's LLM beat reading (V3 ST3, docs/v3/ST3-groq-beats.md): a story line the fast path left partly unread
(STT-garbled speech "We have said, let us work together", "The farmer adds the boy. Where is the cow?", a free time
or place wording) -> one JSON object: speech {who, to, kind, words} · narration {when, where, people, new_scene} ·
aside. The validator takes it whole or not at all; every word it carries is a span of THIS line (a speaker may also be
a cast name or a pronoun: who a garbled name is, is the model's call; Python resolves pronouns and draws).

    when     needs_llm(): a speech verb / quote mark with no speech read, a time word with no said time, a place
             phrase with no said place. Every other line: no call (0 tokens).
    prompt   PREFIX first, never changed per call (Groq caches a byte-identical prefix); then the cast, the open
             scene, the last two lines, the line and the fast reading. Never the transcript (RULES).
"""
from __future__ import annotations

import asyncio
import re
import time
from dataclasses import dataclass
from typing import Any, Optional

from copilot.scene.compiler import JsonlStream
from copilot.story import beats

MAX_TOKENS = 400       # gpt-oss reasons (low) before the object: 120 cut it off (400s), 260 too (test55: no JSON)
EST_PROMPT = 700
TIMEOUT_S = 4.0
KINDS = ("say", "ask", "reply", "shout", "whisper")
PRONOUNS = ("he", "she", "they")
_NOT_PEOPLE = {"we", "i", "you", "us", "me", "it", "everyone", "everybody", "class", "students", "sorry", "okay", "ok",
               "hello", "yes", "no", "please", "thanks", "oh", "well", "right", "alright"}
_LEAD_PREP = re.compile(r"^(?:in|at|to|into|onto|inside|near|towards|toward|through|across|on)\s+", re.IGNORECASE)

_SPEECH_VERB = re.compile(r"\b(?:said|says|say|told|tells|added|adds|explained|explains|asked|asks|wondered|replied|"
                          r"replies|answered|answers|responded|shouted|shouts|yelled|yells|exclaimed|cried|screamed|"
                          r"whispered|whispers|murmured|saying|asking|telling|replying|answering|shouting|yelling|"
                          r"whispering|calling out)\b(?!\s+that\b)", re.IGNORECASE)
_TIME_WORD = re.compile(r"\b(?:decades?|centur(?:y|ies)|childhood|age of|as a (?:child|boy|girl|young \w+)|"
                        r"when (?:he|she|they|i|we) (?:was|were)|(?:that|the following|next|every|each) "
                        r"(?:spring|summer|autumn|winter|year|week|month)|morning|evening|night|dawn|sunrise|sunset|"
                        r"years? (?:after|before|on)|later in (?:life|his life|her life))\b", re.IGNORECASE)
_PLACE_PHRASE = re.compile(r"\b(?:to|into|onto|at|in|inside|near|towards|toward|through|across|reached|reaches|"
                           r"arrived at|arrives at)\s+(?:the|a|an)\s+"
                           r"(?:[a-z]+\s+)?([a-z]+)\b")
_NOT_PLACE = frozenset("""end beginning middle same way time moment age past future first last start hope order case
fact dark morning evening night year years day days week month summer winter spring autumn while lot rest idea
slides slide board lesson topic class chapter story tutorial""".split())  # "back to the slides" is the teacher's
_CLASS_TALK = re.compile(r"\b(?:everyone|everybody|class|students|you|your|let me|let's|let us|sorry|okay|ok|"
                         r"listen|look at|page|slide|board)\b", re.IGNORECASE)  # the teacher talking to the room
_NOT_HEAD = frozenset("now then again too here there today".split())  # a trailing adverb is no place noun


def _norm(s: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", s.lower()))


def said(part: str, line: str) -> bool:
    """`part` is a run of whole words of the line (case, punctuation and quote marks aside)."""
    return bool(span(part, line))


def span(part: str, line: str) -> str:
    """The line's own text for `part` (review: what is shown is cut from the line, never the model's string: a "-5"
    or "2/5" it wrote shows as the said "5" / "2.5" words; a word in another script is not in the line). "" = not said."""
    want = re.findall(r"[a-z0-9]+", part.lower())
    if not want or re.search(r"[^\x00-\x7f]", re.sub(r"[“”‘’…–—]", "", part)):
        return ""
    toks = list(re.finditer(r"[a-z0-9]+", line.lower()))
    words = [m.group(0) for m in toks]
    for i in range(len(words) - len(want) + 1):
        if words[i:i + len(want)] == want:
            end = toks[i + len(want) - 1].end()
            tail = re.match(r"[?!]+", line[end:])  # test55: "Are you tired" lost its said question mark
            return line[toks[i].start():end + (tail.end() if tail else 0)]
    return ""


# ---- when to call --------------------------------------------------------------------------------------------------
def needs_llm(text: str, sp: Optional[beats.Speech], b: beats.Beat) -> str:
    """Why the fast path leaves part of the line unread ("" = no call)."""
    if sp is None and (_SPEECH_VERB.search(text) or any(q in text for q in "\"“”")):
        return "speech unread"
    if sp is not None:
        return ""
    if not b.when and _TIME_WORD.search(text):
        return "time unread"
    if not b.where:
        for m in _PLACE_PHRASE.finditer(text):
            ws = m.group(0).lower().split()[-2:]  # "at the board now": either word may be the noun
            if not any(w in _NOT_PLACE or w in beats.PERSON_NOUNS or w in _NOT_HEAD for w in ws):
                return "place unread"
    return ""


# ---- the prompt ----------------------------------------------------------------------------------------------------
PREFIX = """You read one line a teacher says while telling a story to a class, heard by speech-to-text (words can be
misheard: "We have said" may be "Pierre said", "adds" may be "asks"). Output ONLY one JSON object, no prose.

{"type":"speech","who":"Pierre Curie","to":"","kind":"say","words":"let us work together"}
  someone IN the story speaks. who = the speaker: a cast name, he / she / they, or the line's own words for a new
  person ("the farmer"); a misheard name = the cast member it most likely is. to = who is spoken to ("" if not said).
  kind: say ask reply shout whisper. words = exactly the spoken words as they are in the line.
{"type":"narration","when":"","where":"","people":[],"new_scene":false}
  the story goes on. when / where = the line's own words for a time / place ("" if none); people = the people
  newly named in the line (its words); new_scene = true when time or place moves on.
{"type":"aside"}
  the teacher talks to the class, not the story ("okay, everyone listen").

Rules: every value is copied from THIS line (or a cast name); never add a word, a number, a name or a place that is
not there. Not sure: narration with empty values.

Any "<someone> <said / asked / was shouting / was whispering / misheard verb>, <words>" is speech, even with two
sentences. One object for the whole line.

Examples:
Cast: c1 Ravi (he) | c2 Asha (?)
Line: Ash I said, see you tomorrow.
{"type":"speech","who":"Asha","to":"","kind":"say","words":"see you tomorrow"}
Cast: c1 king (he) | c2 queen (she)
Line: The king adds the queen. Where is my crown?
{"type":"speech","who":"the king","to":"the queen","kind":"ask","words":"Where is my crown?"}
Cast: c1 old man (?)
Line: The old man was whispering, the river is rising.
{"type":"speech","who":"the old man","to":"","kind":"whisper","words":"the river is rising"}
Cast: c1 Ravi (he)
Line: A decade after that, Ravi became a teacher in the city.
{"type":"narration","when":"A decade after that","where":"the city","people":[],"new_scene":true}
Cast: c1 goat (?)
Line: Then the goat slipped into a deep well.
{"type":"narration","when":"","where":"a deep well","people":[],"new_scene":true}
Cast: (none)
Line: Sorry, okay, everyone listen carefully now.
{"type":"aside"}
"""


def messages(cast: list[tuple[str, str]], scene: str, before: list[str], line: str, fast: str) -> list[dict[str, str]]:
    tail = ["Cast: " + (" | ".join(f"c{k + 1} {n} ({g or '?'})" for k, (n, g) in enumerate(cast)) or "(none)")]
    if scene:
        tail.append(f"Scene: {scene}")
    if before:
        tail.append("Before: " + " / ".join(before[-2:]))
    tail.append(f"Line: {line}")
    tail.append(f"Fast: {fast or '(nothing read)'}")
    return [{"role": "system", "content": PREFIX}, {"role": "user", "content": "\n".join(tail)}]


def fast_reading(sp: Optional[beats.Speech], b: beats.Beat) -> str:
    if sp is not None:
        return f"speech who={sp.who!r} words={sp.words!r}"
    bits = [f"{k}={v!r}" for k, v in (("when", b.when), ("where", b.where)) if v]
    if b.names or b.people:
        bits.append(f"people={b.names + b.people}")
    return "narration " + " ".join(bits) if bits else ""


# ---- the validator -------------------------------------------------------------------------------------------------
def _person(who: str, line: str, cast: list[str]) -> bool:
    w = who.strip()
    if not w or w.lower() in _NOT_PEOPLE:
        return False
    return w.lower() in PRONOUNS or w.lower() in {c.lower() for c in cast} or said(w, line)


def check(ans: Any, line: str, cast: list[str], b: beats.Beat) -> tuple[Optional[dict], str]:
    """(the answer, cleaned) or (None, why it is refused). All or nothing."""
    if not isinstance(ans, dict):
        return None, "no answer"
    t = ans.get("type")
    if t == "aside":
        if b.names or b.people or b.when or b.where or b.marker or beats.pronoun(line):
            return None, "aside but the line has story words"
        if not _CLASS_TALK.search(line):  # review: "The water rushed into the old mill" is no aside
            return None, "aside but the line does not talk to the class"
        return {"type": "aside"}, ""
    if t == "speech":
        who, to = str(ans.get("who") or "").strip(), str(ans.get("to") or "").strip()
        words, kind = str(ans.get("words") or "").strip(), str(ans.get("kind") or "say")
        if not _person(who, line, cast):
            return None, f"speaker {who!r} not said"
        if to and to.lower() in _NOT_PEOPLE:
            to = ""  # "told everyone, ...": spoken to nobody of the cast
        if to and not _person(to, line, cast):
            return None, f"addressee {to!r} not said"
        words = span(words, line)
        if not words:
            return None, "words not in the line"
        if kind not in KINDS:
            return None, f"kind {kind!r}"
        return {"type": "speech", "who": who, "to": to, "kind": kind, "words": words}, ""
    if t == "narration":
        when, where = str(ans.get("when") or "").strip(), str(ans.get("where") or "").strip()
        where = _LEAD_PREP.sub("", where)  # "in a cold shed" -> "a cold shed" (the chip and the picture query)
        people = ans.get("people") or []
        if not isinstance(people, list):
            return None, "people not a list"
        people = [str(p).strip() for p in people if str(p).strip()]
        for v in (when, where):
            if v and not said(v, line):
                return None, f"{v!r} not in the line"
        when, where = span(when, line), span(where, line)
        for p in people:  # review: newly named = named in THIS line (a cast name alone is no new person here)
            if p.lower() in _NOT_PEOPLE or p.lower() in PRONOUNS or not said(p, line):
                return None, f"person {p!r} not said"
        people = [span(p, line) for p in people]
        return {"type": "narration", "when": when, "where": where, "people": people,
                "new_scene": bool(ans.get("new_scene"))}, ""
    return None, f"type {t!r}"


# ---- the call ------------------------------------------------------------------------------------------------------
@dataclass
class BeatResult:
    answer: Optional[dict] = None
    tokens: int = 0
    cached_tokens: int = 0
    total_s: float = 0.0
    entry: str = ""
    text: str = ""            # the streamed text (logged when no object came)

    @property
    def counted(self) -> int:
        return self.tokens - self.cached_tokens


def _first(text: str) -> Optional[dict]:
    p = JsonlStream()
    objs = p.feed(text) + p.finish()
    return objs[0] if objs else None


class StoryExtractor:
    def __init__(self, router: Any) -> None:
        self.router = router

    async def read(self, msgs: list[dict[str, str]], line: str) -> BeatResult:
        t0 = time.monotonic()
        parser = JsonlStream()
        objs: list[dict] = []
        got: list[str] = []

        def on_text(piece: Optional[str]) -> None:  # streamed = plain text (no JSON mode: a slip is refused, not retried)
            if piece is None:  # a retry streams again from the start
                parser.reset()
                objs.clear()
                got.clear()
                return
            got.append(piece)
            objs.extend(parser.feed(piece))

        r = await self.router.complete(msgs, est_tokens=EST_PROMPT, max_tokens=MAX_TOKENS,
                                       deadline=time.monotonic() + TIMEOUT_S + 1, timeout_s=TIMEOUT_S, on_text=on_text)
        objs.extend(parser.finish())
        res = BeatResult(answer=objs[0] if objs else None, entry=r.entry, total_s=time.monotonic() - t0,
                         text="".join(got)[:200])
        res.tokens = r.response.prompt_tokens + r.response.completion_tokens
        res.cached_tokens = r.response.cached_tokens
        return res


class ReplayStoryExtractor:
    """Recorded answers instead of a call (0 tokens): tests and fixture replays. answers: line -> JSON text."""

    def __init__(self, answers: dict[str, str], delay_s: float = 0.0) -> None:
        self.answers = answers
        self.delay_s = delay_s
        self.calls: list[list[dict[str, str]]] = []

    async def read(self, msgs: list[dict[str, str]], line: str) -> BeatResult:
        self.calls.append(msgs)
        if self.delay_s:
            await asyncio.sleep(self.delay_s)
        return BeatResult(answer=_first(self.answers.get(line.strip(), "")), entry="replay")
