"""Spoken structure cues (F-013 S1): what a single transcript line announces, decided without the LLM.

    topic    "Now let's learn about chemical bonding." / "The second topic is differential calculus." /
             "What is economics?" / "Classification of matter."               -> name
    list     "Matter can be classified into pure substances and mixtures."   -> head + items (items may come later:
             "There are two types of extrinsic semiconductors." then "The first type is ...")
    compare  "Difference between ethical hacking and penetration testing."   -> items (2-4)
    figure   "Let's look at the block diagram of STM32." / "Here is the circuit diagram of a full adder."
             -> name "STM32", items ("block diagram",): the figure is fetched at once (F-013 S4, user 2026-10-17)

Used for the instant display (the engine shows the announced title / list items before the interpretation arrives),
for cutting the gate's unit at a topic announcement and for naming topics when no LLM answer is available. The
interpretation stays the authority: everything shown from a cue is provisional until it confirms it.
Precision over recall: a cue that is not clearly an announcement is not one.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal, Optional

CueKind = Literal["topic", "list", "compare", "figure"]

MAX_NAME_WORDS = 6
MAX_ITEM_WORDS = 5
MAX_ITEMS = 8

_NUM = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "2": 2, "3": 3, "4": 4,
        "5": 5, "6": 6, "7": 7, "8": 8}
_COUNT = r"(?:two|three|four|five|six|seven|eight|[2-8]|several|many|different|various)"
_ORDINALS = ("first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|eleventh|twelfth|thirteenth|"
             "fourteenth|fifteenth|next|last|\\d+(?:st|nd|rd|th)")
_GROUP = (r"(?:types?|kinds?|sub-?categories|categories|category|sub-?types|classes|groups?|forms?|parts?|branches|"
          r"modes|stages|layers|sectors)")

# a name must not run into a clause: stop at these words
_STOP_AT = re.compile(
    r"\s+(?:which|that|where|who|whose|because|so|then|and then|in which|is|are|was|were|has|have|can|will|"
    r"would|should|means|refers|today|now|first|here|in this|in detail|briefly|one by one|used|called|known|"
    r"named)\b.*$|,\s+(?:the|a|an|also|which|that)\s.*$", re.IGNORECASE)
_LEAD = re.compile(r"^(?:(?:the|a|an|about|on|with|into|to|some|one|our|its|their|of)\s+)+",
                   re.IGNORECASE)
_VERBISH = re.compile(r"\b(?:is|are|was|were|be|been|has|have|had|do|does|did|can|could|will|would|should|may|"
                      r"must|it|they|them|we|you|i|he|she|this|that|these|those|there|not|individually)\b",
                      re.IGNORECASE)
_QUESTION_LEAD = re.compile(r"^(?:what|which)\s+(?:is|are)\s+(?:an?\s+|the\s+)?", re.IGNORECASE)
_TRAIL = re.compile(r"\s+(?:and|or|of|with|the|a|an|in|for|to)$", re.IGNORECASE)

_ANNOUNCE = [
    # "now let's (learn|talk|study|...) about X", "we will discuss X", "moving on to X"
    re.compile(r"(?:^|[,;]\s+)(?:so\s+|now\s+|okay\s+|ok\s+|well\s+|and\s+|next\s+)*(?:let'?s|let us|we will|we'll|we are going to|"
               r"we're going to|now we will|i will|i'll)\s+(?:now\s+)?(?:start with|talk about|learn about|learn|study about|"
               r"study|look at|discuss|understand|see|move on to|move to|go to|begin with|focus on|read about|cover)"
               # "let's see what happens" / "...whether it moves" names no heading (F-014 S0 incline_live run)
               r"\s+(?!(?:what (?:happens|will happen|would happen|happened)|whether|if)\b)(?P<n>[^.?!;:]{2,80})",
               re.IGNORECASE),
    re.compile(r"^(?:so\s+|now\s+|and\s+)*(?:moving on to|coming to|next we have|next is|next comes|"
               r"(?:the\s+)?next topic is|(?:the\s+)?next topic,?|our next topic is|today'?s topic is|"
               r"(?:the\s+)?topic (?:for today|of today'?s lecture) is|introduction to)\s+(?P<n>[^.?!;:]{2,80})",
               re.IGNORECASE),
    re.compile(rf"^(?:so\s+|now\s+|and\s+)*(?:the\s+)?(?:{_ORDINALS})\s+(?:topic|chapter|unit|section|concept)\s+"
               r"(?:is|will be|we will study is)?\s*(?P<n>[^.?!;:]{2,80})", re.IGNORECASE),
]
_ORDINAL_TOPIC = _ANNOUNCE[2]  # "The 7th topic is Jupiter": one of a numbered series (rule "ordinal", F-013 S2)
# "What is economics?" / "What are semiconductors?" / "What do you mean by inertia?": short, opens the line
_WHAT_IS = re.compile(r"^(?:so\s+|now\s+|and\s+)*(?:what is meant by|what do (?:you|we) mean by|what\s+(?:is|are)|"
                      r"define)\s+(?P<n>[^.?!;:,]{2,60})\s*[?.]?$", re.IGNORECASE)
WHAT_IS_MAX_WORDS = 4
# a short heading line: "Classification of matter." / "Types of pollination." / "Applications of VLSI"
_HEADING = re.compile(rf"^(?:the\s+)?(?P<n>(?:classification|{_GROUP}|properties|characteristics|applications|"
                      r"advantages|disadvantages|limitations|uses|functions|structure|features|importance|"
                      r"working|principle|laws|history|introduction|overview|examples)\s+of\s+[^.?!;:,]{2,50})"
                      r"\s*[.:]?$", re.IGNORECASE)
_COMPARE = [
    re.compile(r"^(?:(?:so|now|and|then|next|let'?s see|let us see|we will see|we'll see|here is|what is|the)\s+){0,3}"
               r"(?:main\s+|major\s+|key\s+)?(?:difference|differences|comparison|distinction)s?\s+"
               r"(?:between|of)\s+(?P<a>[^.?!;:]{2,120})", re.IGNORECASE),
    re.compile(r"^(?:(?:so|now|and|okay|next)\s*,?\s+)*(?:let'?s|let us|we will|we'll|we are going to)\s+(?:now\s+)?(?:compare|differentiate(?: between)?|"
               r"distinguish(?: between)?)\s+(?P<a>[^.?!;:]{2,120})", re.IGNORECASE),
    re.compile(r"^(?P<a>[^.?!;:]{2,40}\s+(?:vs\.?|versus)\s+[^.?!;:]{2,40})$", re.IGNORECASE),
]
# "X can be classified into A, B and C" / "X is divided into two types: A and B" / "There are three types of X"
_CLASSIFY = re.compile(
    r"^(?P<head>[^.?!;:]{2,80}?)\s+(?:can be|could be|is|are|may be|has been|have been)\s+(?:further\s+|mainly\s+|"
    r"broadly\s+|basically\s+|majorly\s+|mostly\s+|generally\s+)?(?:classified|divided|categori[sz]ed|grouped|split|sub-?divided)\s+(?:in|into)\s+"
    rf"(?:(?P<count>{_COUNT})\s+)?(?:(?:main\s+|major\s+|broad\s+)?{_GROUP}\s*)?(?:,|:|namely|which are|they are|like)?\s*"
    r"(?P<items>[^.?!;]*)", re.IGNORECASE)
_THERE_ARE = re.compile(
    rf"^(?:so\s+|now\s+|and\s+)*(?:there are|we have|it has|they are of)\s+(?P<count>{_COUNT})\s+(?:main\s+|major\s+)?"
    rf"{_GROUP}(?:\s+of\s+(?P<head>[^.?!;:,]{{2,60}}))?\s*(?:(?:,|:|namely|which are|they are|like|such as)\s*"
    r"(?P<items>[^.?!;]*))?$", re.IGNORECASE)
_TYPES_OF = re.compile(
    rf"^(?:the\s+)?(?:(?P<count>{_COUNT})\s+)?(?:main\s+|major\s+|different\s+)?{_GROUP}\s+of\s+(?P<head>[^.?!;:,]{{2,60}}?)"
    r"\s+(?:are|include)\s*(?:,|:|namely)?\s*(?P<items>[^.?!;]*)$", re.IGNORECASE)
_OF_TYPES = re.compile(
    rf"^(?P<head>[^.?!;:]{{2,60}}?)\s+(?:is|are|can be)\s+of\s+(?P<count>{_COUNT})\s+{_GROUP}\s*(?:,|:|namely|which are)?"
    r"\s*(?P<items>[^.?!;]*)", re.IGNORECASE)
# "Branches of chemistry can be inorganic, organic, physical or analytical." (>= 3 short items)
_CAN_BE = re.compile(r"^(?P<head>[^.?!;:]{2,60}?)\s+(?:can be|may be|are|include|includes)\s+(?:either\s+)?"
                     r"(?P<items>[^.?!;]+)$", re.IGNORECASE)
# an item said on its own line after a list cue: "The first type is self-pollination." / "Second is cross pollination"
_ORDINAL_ITEM = re.compile(
    rf"^(?:so\s+|and\s+|now\s+)*(?:the\s+)?(?:{_ORDINALS}|another|other)\s+(?:one\s+|{_GROUP}\s+)?(?:is|are|will be)\s+"
    r"(?:called\s+)?(?P<n>[^.?!;:,]{2,60})", re.IGNORECASE)


# F-013 S4: a figure the teacher turns to. The kind of figure ("block diagram", "pin diagram", "circuit diagram",
# "flowchart", plain "diagram" / "figure") and what it is of; "look at the diagram" alone names nothing: no cue.
_FIG_KIND = (r"(?:(?:functional|internal|simplified|basic|labell?ed|detailed|neat|complete|general)\s+)?"
             r"(?:(?:block|circuit|schematic|pin|ray|flow|free[- ]body|energy[- ]level|timing|logic|wiring|connection|"
             r"architecture|architectural|structural|cross[- ]sectional|labell?ed|internal)\s+)?"
             r"(?:diagram|schematic|figure|flowchart|flow chart|architecture|pinout|pin ?out|layout)")
_FIG_VERB = (r"(?:look at|see|show you|draw|study|observe|check|refer to|here is|here's|this is|consider|discuss|"
             r"understand|explain|go through|have a look at|take a look at)")
_FIGURE_OF = re.compile(rf"{_FIG_VERB}\s+(?:the|a|an|this|its|our)\s+(?P<t>{_FIG_KIND})\s+(?:of|for)\s+"
                        r"(?P<n>[^.?!;:,]{2,60})", re.IGNORECASE)
_FIGURE_PRE = re.compile(rf"{_FIG_VERB}\s+(?:the|a|an|this)\s+(?P<n>[A-Za-z0-9][\w\-+]*(?:\s+[\w\-+]+){{0,3}}?)"
                         rf"(?:'s)?\s+(?P<t>{_FIG_KIND})\b", re.IGNORECASE)
_NOT_FIGURE_OF = {"following", "above", "below", "next", "given", "same", "previous", "last", "first", "second",
                  "simple", "whole", "entire", "complete", "basic", "neat", "general"}


def figure_cue(body: str) -> Optional[Cue]:
    """F-013 S4: "let's look at the block diagram of STM32" -> Cue("figure", "STM32", ("block diagram",))."""
    for rx in (_FIGURE_OF, _FIGURE_PRE):
        m = rx.search(body)
        if not m:
            continue
        name = tidy_name(re.sub(r"^(?:(?:a|an|the)\s+)?(?:typical|simple|basic|general|generic)\s+", "", m.group("n"),
                                flags=re.IGNORECASE))
        if not name or name.lower() in _NOT_FIGURE_OF or len(name.split()) > 5:
            continue
        kind = " ".join(m.group("t").lower().replace("-", " ").split())
        kind = re.sub(r"^(?:functional|internal|simplified|basic|labell?ed|detailed|neat|complete|general)\s+(?=\w+\s)",
                      "", kind)
        kind = "diagram" if kind in ("figure", "layout") else kind.replace("pin out", "pinout")
        return Cue("figure", name, (kind,), rule="figure")
    return None


def figure_query(cue: Cue) -> str:
    """The image search for a figure cue: "STM32 block diagram"."""
    return f"{cue.name} {cue.items[0] if cue.items else 'diagram'}"


_VAGUE_HEADS = {"most", "some", "all", "main", "other", "others", "many", "few", "example", "examples"}


@dataclass(frozen=True)
class Cue:
    kind: CueKind
    name: str = ""                    # topic name / list head / "A vs B"
    items: tuple[str, ...] = ()       # list or comparison members heard in this line
    count: int = 0                    # announced number of members ("three types"), 0 = not said
    rule: str = ""


@dataclass(frozen=True)
class LineCues:
    cues: tuple[Cue, ...] = field(default_factory=tuple)
    item: str = ""                    # one member said on its own ("The second type is ..."), for an open list

    def of(self, kind: CueKind) -> Optional[Cue]:
        return next((c for c in self.cues if c.kind == kind), None)


def _plain(text: str) -> str:
    t = " ".join(text.replace("’", "'").split())
    t = re.sub(r"^topic\s+\d+[.:,]?\s+", "", t, flags=re.IGNORECASE)  # "Topic 9 FPGA vs ASIC"
    return re.sub(r"^(?:um+|uh+|okay|ok|so|well|right|alright)[, ]+", "", t, flags=re.IGNORECASE)


def tidy_name(raw: str) -> str:
    """A spoken name as a slide title: clause cut off, leading articles dropped, ≤ MAX_NAME_WORDS, first letter up."""
    s = _QUESTION_LEAD.sub("", raw.strip(" ,-–'\""))
    s = re.sub(r"^what\s+(.+?)\s+(?:is|are)$", r"\1", s, flags=re.IGNORECASE)  # "(understand) what chemistry is"
    # "our first chapter, basic concepts of chemistry" / "chapter two: thermodynamics" -> what follows
    s = re.sub(r"^(?:(?:our|the|this)\s+)?(?:(?:first|second|third|next|new|last)\s+)?(?:chapter|topic|unit|lesson|"
               r"module)(?:\s+(?:\d+|one|two|three|four|five))?\s*[,:\-]\s*", "", s, flags=re.IGNORECASE)
    s = _STOP_AT.sub("", s)
    s = re.sub(r"\s+(?:in|for|of)\s+(?:detail|today|this (?:class|lecture|chapter))\b.*$", "", s, flags=re.IGNORECASE)
    while True:
        t = _LEAD.sub("", s)
        if t == s:
            break
        s = t
    s = _TRAIL.sub("", _TRAIL.sub("", s)).strip(" ,")
    words = s.split()
    for k in range(1, len(words) // 2 + 1):  # Whisper joins a heading to its sentence: "Ethical Hacking Ethical hacking"
        if [w.lower() for w in words[:k]] == [w.lower() for w in words[k:2 * k]]:
            words = words[:k]
            s = " ".join(words)
            break
    if not words or len(words) > MAX_NAME_WORDS or _VERBISH.search(s) or s.lower() in {"what", "how", "why", "which"}:
        return ""
    if not re.search(r"[A-Za-z]{3}", s):
        return ""
    return s[:1].upper() + s[1:]


def _items(raw: str) -> tuple[str, ...]:
    """'A, B and C' / 'A or B' -> (A, B, C); each a short noun phrase, else nothing (not a clean list)."""
    raw = re.sub(r"^(?:namely|which are|they are|like|i\.e\.|that is)\s+", "", raw.strip(" ,:"), flags=re.IGNORECASE)
    parts = [p for p in re.split(r"\s*,\s*(?:and\s+|or\s+)?|\s+(?:and|or)\s+", raw) if p.strip()]
    if len(parts) < 2 or len(parts) > MAX_ITEMS:
        return ()
    out = []
    for p in parts:
        p = _LEAD.sub("", p.strip(" .-"))
        if not p or len(p.split()) > MAX_ITEM_WORDS or _VERBISH.search(p) or not re.search(r"[A-Za-z]{2}", p):
            return ()
        out.append(p[:1].upper() + p[1:])
    return tuple(dict.fromkeys(out))


def _count(word: Optional[str]) -> int:
    return _NUM.get((word or "").lower(), 0)


def detect(text: str) -> LineCues:
    """The cues one transcript line carries (empty when it is ordinary content)."""
    t = _plain(text)
    body = t.rstrip(".?! ")
    cues: list[Cue] = []
    for rx in _COMPARE:
        m = rx.search(body)
        if m:
            raw = re.split(r"\s+(?:vs\.?|versus|with)\s+", m.group("a"), flags=re.IGNORECASE)
            items = _items(", ".join(raw)) if len(raw) >= 2 else _items(m.group("a"))
            items = tuple(tidy_name(i) for i in items)
            if 2 <= len(items) <= 4 and all(items):
                cues.append(Cue("compare", " vs ".join(items), items, rule="compare"))
                break
    topic = ""
    for rx in _ANNOUNCE:
        m = rx.search(body)
        if m:
            topic = tidy_name(m.group("n"))
            if topic:
                cues.append(Cue("topic", topic, rule="ordinal" if rx is _ORDINAL_TOPIC else "announce"))
                break
    if not topic:
        first = re.split(r"(?<=\?)\s+", t, maxsplit=1)[0]  # "What is Economics? Economics is the study of ..."
        m = _WHAT_IS.match(first)
        if m and (first.rstrip().endswith("?") or len(body.split()) <= 5):
            topic = tidy_name(m.group("n"))
            topic = topic if len(topic.split()) <= WHAT_IS_MAX_WORDS else ""
            if topic:
                cues.append(Cue("topic", topic, rule="what is"))
    if not topic and len(body.split()) <= 8:
        m = _HEADING.match(body)
        if m:
            topic = tidy_name(m.group("n"))
            if topic:
                cues.append(Cue("topic", topic, rule="heading"))
    for rx, rule in ((_CLASSIFY, "classified"), (_THERE_ARE, "there are"), (_TYPES_OF, "types of"),
                     (_OF_TYPES, "of n types")):
        m = rx.search(body)
        if not m:
            continue
        head = tidy_name(m.group("head") or "") if m.groupdict().get("head") else ""
        items = _items(m.group("items") or "")
        count = _count(m.groupdict().get("count"))
        if items or count:
            cues.append(Cue("list", head, items, count, rule))
            break
    else:
        m = None if re.search(r"\b(?:classified|divided|categori[sz]ed)\b", body, re.IGNORECASE) else _CAN_BE.match(body)
        if m:
            items = _items(m.group("items"))
            head = tidy_name(m.group("head"))
            if len(items) >= 3 and head and head.lower() not in _VAGUE_HEADS:
                cues.append(Cue("list", head, items, rule="can be"))
    fig = figure_cue(body)
    if fig is not None:
        cues.append(fig)
    item = ""
    m = _ORDINAL_ITEM.match(body)
    if m:
        item = tidy_name(m.group("n"))
    return LineCues(tuple(cues), item)


# ---- a definition being said (F-013 S1b): "Chemistry is the branch of science which ..." ------------------------
_DEFINING = re.compile(
    r"^(?:so\s+|now\s+|and\s+|well\s+)*(?:the\s+|an?\s+)?(?P<term>[A-Za-z][\w\-']*(?:\s+[\w\-']+){0,3}?)\s+"
    r"(?:is|are|can be|may be)\s+(?:defined as|known as|called|referred to as\s+)?\s*"
    r"(?P<def>(?:the|an?|any|anything|that|those|a type of|a kind of|a form of|a branch of|a process|the process)\b.*)$"
    r"|^(?:so\s+|now\s+|and\s+)*(?:the\s+|an?\s+)?(?P<term2>[A-Za-z][\w\-']*(?:\s+[\w\-']+){0,3}?)\s+"
    r"(?:means|refers to|is defined as|are defined as|can be defined as|is described as)\s+(?P<def2>.+)$",
    re.IGNORECASE)
_NOT_TERM = re.compile(r"^(?:it|this|that|these|those|there|they|he|she|we|you|i|which|what|here|one|another|"
                       r"each|every|some|all|its|their|example|for example|the reason|the answer|the result)$",
                       re.IGNORECASE)
DEF_MIN_WORDS = 3  # of the definition said so far, before it is worth showing


def live_definition(text: str) -> tuple[str, str]:
    """(term, definition so far) when a line is defining something by name, else ("", "")."""
    t = _plain(text).rstrip(" ,")
    m = _DEFINING.match(t)
    if not m:
        return "", ""
    term = (m.group("term") or m.group("term2") or "").strip()
    body = (m.group("def") or m.group("def2") or "").strip()
    if not term or _NOT_TERM.match(term) or _VERBISH.search(term) or len(body.split()) < DEF_MIN_WORDS:
        return "", ""
    body = re.split(r"(?<=[.?!])\s+", body)[0]  # this sentence only
    return term[:1].upper() + term[1:], body[:1].upper() + body[1:]


# ---- an enumerated section heading (F-013 S2): "1. Social. The social conditions ...", "Stage 2, ...",
# "3. Mixed Economy" -------------------------------------------------------------------------------------------
_SECTION_NUM = re.compile(r"^(?:so\s+|and\s+|now\s+)?(?P<num>\d{1,2})\s*[.)]\s+(?P<n>[^.?!;:,]{2,60}?)\s*"
                          r"(?:[.?!;:,]\s*(?P<rest>.*))?$", re.IGNORECASE)
_SECTION_GROUP = re.compile(r"^(?:so\s+|and\s+|now\s+)?(?P<g>stage|step|phase|level|layer|law|rule|principle|part|"
                            r"type|unit|chapter|section)\s+(?P<num>\d{1,2}|one|two|three|four|five|six|seven|eight|"
                            r"nine|ten)\b\s*[.,:)\-]?\s*(?P<rest>.*)$", re.IGNORECASE)
SECTION_MAX_WORDS = 4


def section(text: str) -> str:
    """The heading a line opens with when it is one of a numbered series: a short noun phrase after "N." that is the
    whole line or is taken up by the next sentence ("2. Opportunity Cost. Opportunity cost is ..."), or "Stage N" /
    "Step N" (titled "Stage N"). A numbered step said as a sentence ("1. The user enters a domain name.") is no
    heading: its words are not repeated after it. "" when the line opens no section."""
    t = _plain(text)
    m = _SECTION_GROUP.match(t)
    if m and len((m.group("rest") or "").split()) >= 3:  # "Type 2." alone is a fragment (test10), not a section
        num = m.group("num")
        num = str(_NUM.get(num.lower(), num)) if not num.isdigit() else num
        return f"{m.group('g').capitalize()} {num}"
    m = _SECTION_NUM.match(t)
    if not m:
        return ""
    name = tidy_name(m.group("n"))
    if not name or len(name.split()) > SECTION_MAX_WORDS:
        return ""
    rest = (m.group("rest") or "").strip()
    if rest:
        words = {w[:5] for w in re.findall(r"[a-z]{4,}", name.lower())}
        head = {w[:5] for w in re.findall(r"[a-z]{4,}", " ".join(rest.split()[:12]).lower())}
        if not words or not words & head:
            return ""
    return name


_SENTENCE_END = re.compile(r"(?<=[.?!])\s+(?=[A-Za-z0-9])")


def sentences(text: str) -> list[str]:
    return [s for s in _SENTENCE_END.split(" ".join(text.split())) if s.strip()]


def detect_all(text: str, latest_first: bool = False) -> LineCues:
    """detect() on every sentence of a line (Whisper joins sentences when the speaker does not pause: 25 % of the lines
    in tests 1-30): the first cue of each kind (the latest with latest_first, for a partial transcript growing at its
    end); an item said on its own is taken from the last sentence that has one."""
    found: dict[str, Cue] = {}
    item = ""
    head = section(text)  # the whole line: sentence splitting would cut "1." from its heading
    if head:
        found["topic"] = Cue("topic", head, rule="section")
    parts = sentences(text) or [text]
    for s in (reversed(parts) if latest_first else parts):
        lc = detect(s)
        for c in lc.cues:
            found.setdefault(c.kind, c)
        if lc.item and (not item or not latest_first):
            item = lc.item if not item or not latest_first else item
    return LineCues(tuple(found.values()), item)


def live_definition_any(text: str) -> tuple[str, str]:
    """live_definition() of the last sentence that defines something (the one being said)."""
    for s in reversed(sentences(text) or [text]):
        term, body = live_definition(s)
        if term:
            return term, body
    return "", ""
