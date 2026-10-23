"""Transcript lines -> RepresentationIntent for Concept Simulation (F-014), deterministic, 0 tokens, < 1 s.

A spoken cue alone never shows anything: it must come with a template's setup (simulation.templates, `setup`), in
the same line or, for a "show" cue ("let me show you", "let's see what happens"), in one of the two lines before it.

    cue      "Consider a block of 5 kg on a rough surface." / "Let's imagine a box on a plane."
             "Let me show you." after "a box is pushed along the floor"
    score    a setup with its quantities but no cue ("A 5 kg box is pushed with 20 N across the floor."): the scenario
             score (setup + the template's quantities + its words) -> a Suggest chip, never shown by itself (S1)
    setup    a template's scenario without a cue ("Now tilt the surface to 30 degrees."): the engine only uses it to
             switch a simulation that is already open
    values   quantities, a value named without a unit, a bare number, "double it", a slot only mentioned: for the open
             simulation (simulation.values.resolve reads them against it), if any
    end      "let's get back to the slides", "end / close the simulation", "back to the notes": simulation mode ends.
             Heard on any line (the filter calls these classroom talk); not when it is said for later ("we will get
             back to the slides later", "before we close the simulation ...")

Context guards: each template's `guard` vetoes it on that line (traps from the recordings and the obvious ones:
"block diagram", "block of code", "slope of the line", "axial tilt"). Lines the filter flags as possible meta talk
("0.3" alone, the user's lecture of 2026-10-17) give values only, never a cue; nothing runs during a pause
(understanding publishes no ConceptSignal then).

The detector only proposes. The presentation engine owns the decision (simulation.policy) and the deck.
"""
from __future__ import annotations

import logging
import re
from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.events import ConceptSignal, Event, RepresentationIntent, TranscriptFinal, UtteranceClassified
from copilot.simulation.registry import TEMPLATES, ORDER
from copilot.simulation.values import NUM, heard

log = logging.getLogger(__name__)

MAX_LINES = 300
SHOW_CUE_LOOKBACK = 2  # lines before a "let me show you" that may hold its setup
SCORE_MIN = 4          # setup 2 + a quantity of the template 1 each (≤ 2) + its words 1

# "consider / imagine / suppose / assume / picture / take a <setup>", "let's say we have a ..."
_SETUP_CUE = re.compile(
    r"\b(?:consider(?:ing)?|imagine|suppose|assume|picture|visuali[sz]e|think of|take|say)\b"
    r"(?:\s+(?:that|now|here|we have|we've got|you have|i have|there is|there's|an?\s+example of))*"
    r"\s+(?:a|an|the|one|this|some)\b"
    r"|\blet(?:'?s| us) (?:say|assume|consider|imagine|take|suppose|picture|visuali[sz]e)\b", re.IGNORECASE)
# "let me show you", "let's see what happens", "let's simulate"
_SHOW_CUE = re.compile(
    r"\b(?:let me show you|i(?:'ll| will) show you|let(?:'?s| us) (?:see|look at|watch) what happens|watch what happens|"
    r"let(?:'?s| us) (?:simulate|visuali[sz]e|animate)|let me (?:simulate|demonstrate)|see it in action)\b",
    re.IGNORECASE)
# S3 processes: "let's see how the heart pumps blood", "let's trace the path of the blood", "let me walk you through
# the water cycle": a cue only for a process template (a mechanics setup needs the cues above)
_PROCESS_CUE = re.compile(
    r"\blet(?:'?s| us) (?:see|look at|watch|understand|explore|trace|follow) how\b"
    r"|\blet(?:'?s| us) (?:trace|follow|track) the (?:path|flow|journey|route|movement)\b"
    r"|\blet me (?:walk you|take you) through\b|\blet(?:'?s| us) (?:walk|go) through\b"
    r"|\b(?:here|this) is how\b", re.IGNORECASE)
# an announced topic ("today we will learn about the water cycle", "the next topic is the human heart"): for a process
# template a Suggest chip at once (user 2026-10-19), never a show
_ANNOUNCE = re.compile(
    r"\b(?:the (?:next |new |first |second |third |main )?topic (?:is|of today)|today'?s topic|"
    r"(?:going to|will|shall|let(?:'?s| us)|we) (?:now )?(?:learn|study|discuss|talk|read|start)(?: about| with)?|"
    r"introduction to|chapter on|lesson on)\b", re.IGNORECASE)
# "let's get back to the slides", "end the simulation", "back to the notes"
_END_CUE = re.compile(
    r"\b(?:get|go|come|move|head|switch|turn|going|getting|coming)\s+back\s+to\s+(?:the\s+|our\s+)?"
    r"(?:slides?|notes|lecture|theory|board|presentation|topic|lesson)\b"
    r"|\b(?:end|close|stop|exit|finish|leave|quit)\s+(?:the|this|our)\s+(?:simulation|animation|demo(?:nstration)?)\b"
    r"|^\W*(?:ok(?:ay)?\W+|so\W+|now\W+|right\W+)*back to (?:the\s+)?(?:slides?|notes|lecture|theory)\b"
    r"|\b(?:enough|that's (?:it|all)) (?:with|for|of) (?:the|this) simulation\b"
    r"|\breturn to (?:the\s+)?(?:slides|notes|lecture)\b", re.IGNORECASE)
_END_LATER = re.compile(r"\b(?:later|afterwards|after (?:this|that|the break)|in a (?:minute|moment|bit|while)|"
                        r"once we|before we|we(?:'ll| will) (?:then )?(?:get|go|come) back|tomorrow|next class|"
                        r"when (?:we|i|you)|until)\b", re.IGNORECASE)
_REVEAL = (("friction", re.compile(r"\bfriction\w*\b", re.I)), ("normal", re.compile(r"\bnormal (?:force|reaction)\b", re.I)),
           ("weight", re.compile(r"\b(?:weight|gravity|gravitational force|mg)\b", re.I)),
           ("applied", re.compile(r"\b(?:push\w*|applied force)\b", re.I)),
           # S2: the pull is its own force; verbs only: "a larger pull down the slope" (gravity) and pulleys are not it
           ("pull", re.compile(r"\b(?:pull(?:ed|ing|s)|drag(?:ged|ging|s)?|rope)\b|\bpull\s+(?:it|on|the|this|a|an)\b"
                               r"|\b(?:we|you|i|they|to|and|then|now)\s+pull\b", re.I)),
           ("components", re.compile(r"\b(?:components?|resolve\w*|sin(?:e)? theta|cos(?:ine)? theta)\b", re.I)),
           ("graph", re.compile(r"\b(?:graphs?|plot(?:ted)?)\b", re.I)))  # S2: the graph strip under the motion
_NUMBER = re.compile(NUM, re.IGNORECASE)
_RELATIVE_WORDS = re.compile(r"\b(?:double|triple|halve|half|twice|increase|decrease|reduce|raise|lower|remove the push|"
                             r"no push|stop pushing|frictionless|smooth|rough|no friction)\b", re.IGNORECASE)
# S3: a step or part of any process ("then the water vapour condenses", "the left ventricle"): for the open one
_STEP_WORDS = re.compile("|".join([f"(?:{w})" for t in TEMPLATES.values() for d in t.steps
                                   for w in (d.words, d.weak) if w]
                                  + [f"(?:{p.words})" for t in TEMPLATES.values() for p in t.parts]) or "(?!)",
                         re.IGNORECASE)
_SLOT_WORDS = re.compile(r"\b(?:" + "|".join(f"(?:{s.names})" for t in TEMPLATES.values() for s in t.slots if s.names)
                         + r")\b", re.IGNORECASE)  # whole words: the projectile's "u" is not in "you"


@dataclass(frozen=True)
class Detection:
    template: str = ""                     # "" = values only
    strength: str = ""                     # cue | score | setup | values | end ("" = nothing)
    values: dict[str, dict] = field(default_factory=dict)
    reveal: tuple[str, ...] = ()
    cue: str = ""                          # the cue words (logs)
    score: int = 0

    @property
    def empty(self) -> bool:
        return not self.strength


def _setup(text: str) -> str:
    """The first template (priority order) whose setup the line names and whose guard does not veto it."""
    for tid in ORDER:
        t = TEMPLATES[tid]
        if t.guard is not None and t.guard.search(text):
            continue
        if t.setup.search(text):
            return tid
    return ""


ANNOUNCE_GAP = 40  # characters between "the topic is" and the process it names


def _announced(tid: str, text: str) -> bool:
    """Is the process the announced topic ("today we will learn about the water cycle"), not only mentioned beside one
    ("the next topic is respiration, quite different from photosynthesis")?"""
    setup = TEMPLATES[tid].setup
    for m in _ANNOUNCE.finditer(text):
        s = setup.search(text, m.end())
        if s is not None and s.start() - m.end() <= ANNOUNCE_GAP and not re.search(r"[,;]", text[m.end():s.start()]):
            return True
    return False


def score(tid: str, text: str) -> int:
    """The scenario score of a line for a template: its setup 2, each of its quantities stated 1 (at most 2), two or
    more of its words 1."""
    t = TEMPLATES[tid]
    kinds = {s.kind for s in t.slots}
    n = 2 if t.setup.search(text) else 0
    n += min(2, len({h.kind for h in heard(text) if h.kind in kinds}))
    n += 1 if len({m.group(0).lower() for m in t.lexicon.finditer(text)}) >= 2 else 0
    return n


def end_cue(text: str) -> str:
    """The words of an end cue ("let's get back to the slides"), "" when there is none or it is meant for later."""
    m = _END_CUE.search(text)
    if m is None or _END_LATER.search(text):
        return ""
    return m.group(0)


def _values(text: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for h in heard(text):
        key = h.kind if h.kind not in out else f"{h.kind}#{len(out)}"
        out[key] = {"kind": h.kind, "value": h.value, "said": h.said, "text": h.text}
    return out


# words that set a choice or a value without a number ("in parallel", "thrown horizontally", "from a cliff")
_WORD_VALUES = re.compile("|".join([f"(?:{rx})" for t in TEMPLATES.values() for rx, _, _ in t.said_as]
                                   + [f"(?:{s.present})" for t in TEMPLATES.values() for s in t.slots if s.present]
                                   + [f"(?:{t.listens})" for t in TEMPLATES.values() if t.listens])
                          or "(?!)", re.IGNORECASE)


def _maybe_values(text: str) -> bool:
    """Could the line say something to an open simulation ("make it 30", "0.3", "double it", "the pushing force",
    "now connect them in parallel")?"""
    return bool(_NUMBER.search(text) or _RELATIVE_WORDS.search(text) or _SLOT_WORDS.search(text)
                or _WORD_VALUES.search(text) or _STEP_WORDS.search(text))


def detect(text: str, before: tuple[str, ...] = (), meta: bool = False) -> Detection:
    """What one line proposes. `before`: the previous lines (oldest first), for a show cue's setup. meta: the filter
    flagged it as possible meta talk (values only)."""
    end = end_cue(text)
    if end:
        return Detection("", "end", cue=end)
    values = _values(text)
    reveal = tuple(e for e, rx in _REVEAL if rx.search(text))
    if meta:
        return Detection("", "values", values, reveal) if values or _maybe_values(text) else Detection()
    tid = _setup(text)
    m = _SETUP_CUE.search(text)
    process = bool(tid) and TEMPLATES[tid].process
    if tid and m:
        return Detection(tid, "cue", values, reveal, m.group(0))
    pm = _PROCESS_CUE.search(text) if process else None
    if pm:
        return Detection(tid, "cue", values, reveal, pm.group(0))
    if process and _announced(tid, text) and not _SHOW_CUE.search(text):
        return Detection(tid, "score", values, reveal, "announced", score=SCORE_MIN)  # a chip at once (S3)
    show = _SHOW_CUE.search(text)
    proc_show = None if show else _PROCESS_CUE.search(text)
    if show or proc_show:
        found = tid or next((x for x in (_setup(b) for b in reversed(before[-SHOW_CUE_LOOKBACK:])) if x), "")
        if found and TEMPLATES[found].process and not tid:
            # its setup only in the lines before ("... through tiny pores called stomata." "Now let's see how the
            # process actually happens"): a Suggest chip, not a show (user 2026-10-19; V1's demo lecture unchanged);
            # a bare "let me show you" after a process line proposes nothing (a picture, maybe; the S0 rule)
            if proc_show:
                return Detection(found, "score", values, reveal, proc_show.group(0), score=SCORE_MIN)
            found = ""
        if found and show:
            return Detection(found, "cue", values, reveal, show.group(0))
    if tid:
        s = score(tid, text)
        return Detection(tid, "score" if s >= SCORE_MIN else "setup", values, reveal, score=s)
    if values or "graph" in reveal or _maybe_values(text):  # "let's look at the graph" reaches an open simulation
        return Detection("", "values", values, reveal)
    return Detection()


class SimulationDetector:
    """Runs detect() on each content line the understanding service accepted (its ConceptSignal) and publishes a
    RepresentationIntent for every line that proposes something; an end cue on any classified line. Holds no deck
    state."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._text: OrderedDict[str, str] = OrderedDict()
        self._meta: set[str] = set()
        self._recent: deque[str] = deque(maxlen=SHOW_CUE_LOOKBACK)
        self.intents = 0

    def attach(self) -> None:
        self.bus.subscribe("simulation_detector", self._on_event, [TranscriptFinal, UtteranceClassified, ConceptSignal])

    async def _publish(self, segment_id: str, text: str, d: Detection) -> None:
        self.intents += 1
        log.info("[SIM] %s %s%s %s", d.strength, d.template or "-", f" ({d.cue!r})" if d.cue else "",
                 {k: v["said"] for k, v in d.values.items()})
        await self.bus.publish(RepresentationIntent(
            segment_ids=[segment_id], visual_kind="simulation", template=d.template,
            strength=d.strength,  # type: ignore[arg-type]
            values=d.values, reveal=list(d.reveal), origin="cue", text=text[:300]))

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            self._text[event.segment.id] = event.segment.text
            while len(self._text) > MAX_LINES:
                self._text.popitem(last=False)
            return
        if isinstance(event, UtteranceClassified):
            text = self._text.get(event.segment_id, "")
            if event.kind != "filler" and text and end_cue(text):  # classroom talk too ("back to the slides")
                self._meta.add(event.segment_id)  # its ConceptSignal (if any) must not propose it again
                await self._publish(event.segment_id, text, Detection("", "end", cue=end_cue(text)))
                return
            if event.kind != "content":
                self._meta.add(event.segment_id)
            elif event.maybe_meta:
                self._meta.add("meta:" + event.segment_id)
            if len(self._meta) > MAX_LINES:
                self._meta.clear()
            return
        assert isinstance(event, ConceptSignal)
        text = self._text.get(event.segment_id)
        if text is None or event.segment_id in self._meta:
            return
        d = detect(text, tuple(self._recent), meta="meta:" + event.segment_id in self._meta)
        self._recent.append(text)
        if not d.empty:
            await self._publish(event.segment_id, text, d)


def candidate(text: str) -> Optional[str]:
    """The template a line would show with a cue (evaluation helper)."""
    return _setup(text) or None
