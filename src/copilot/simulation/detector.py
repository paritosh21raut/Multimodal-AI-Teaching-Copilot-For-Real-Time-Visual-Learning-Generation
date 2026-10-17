"""Transcript lines -> RepresentationIntent for Concept Simulation (F-014 S0), deterministic, 0 tokens, < 1 s.

A spoken cue alone never shows anything: it must come with a template's setup (simulation.templates, `setup`), in
the same line or, for a "show" cue ("let me show you", "let's see what happens"), in one of the two lines before it.

    cue      "Consider a block of 5 kg on a rough surface." / "Imagine an inclined plane at 30 degrees."
             "Let me show you." after "a box is pushed along the floor"
    setup    a template's scenario without a cue ("Now tilt the surface to 30 degrees."): the engine only uses it to
             switch a simulation that is already open
    values   only quantities ("I push it with 20 newtons."): for the open simulation, if any

Context guards: each template's `guard` vetoes it on that line (traps from the recordings and the obvious ones:
"block diagram", "block of code", "slope of the line", "axial tilt"). Lines the filter flags as possible meta
talk are skipped; nothing runs during a pause (understanding publishes no ConceptSignal then).

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
from copilot.simulation.values import heard

log = logging.getLogger(__name__)

MAX_LINES = 300
SHOW_CUE_LOOKBACK = 2  # lines before a "let me show you" that may hold its setup

# "consider / imagine / suppose / assume / picture / take a <setup>", "let's say we have a ..."
_SETUP_CUE = re.compile(
    r"\b(?:consider(?:ing)?|imagine|suppose|assume|picture|visuali[sz]e|think of|take|say)\b"
    r"(?:\s+(?:that|now|here|we have|we've got|you have|i have|there is|there's|an?\s+example of))*"
    r"\s+(?:a|an|the|one|this|some)\b"
    r"|\blet(?:'s| us) (?:say|assume|consider|imagine|take|suppose)\b", re.IGNORECASE)
# "let me show you", "let's see what happens", "let's simulate"
_SHOW_CUE = re.compile(
    r"\b(?:let me show you|i(?:'ll| will) show you|let(?:'s| us) (?:see|look at|watch) what happens|watch what happens|"
    r"let(?:'s| us) (?:simulate|visuali[sz]e|animate)|let me (?:simulate|demonstrate)|see it in action)\b",
    re.IGNORECASE)
_REVEAL = (("friction", re.compile(r"\bfriction\w*\b", re.I)), ("normal", re.compile(r"\bnormal (?:force|reaction)\b", re.I)),
           ("weight", re.compile(r"\b(?:weight|gravity|gravitational force|mg)\b", re.I)),
           ("applied", re.compile(r"\b(?:push\w*|pull\w*|applied force)\b", re.I)),
           ("components", re.compile(r"\b(?:components?|resolve\w*|sin(?:e)? theta|cos(?:ine)? theta)\b", re.I)))


@dataclass(frozen=True)
class Detection:
    template: str = ""                     # "" = values only
    strength: str = ""                     # cue | setup | values ("" = nothing)
    values: dict[str, dict] = field(default_factory=dict)
    reveal: tuple[str, ...] = ()
    cue: str = ""                          # the cue words (logs)

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


def detect(text: str, before: tuple[str, ...] = ()) -> Detection:
    """What one content line proposes. `before`: the previous lines (oldest first), for a show cue's setup."""
    values = {h.kind: {"value": h.value, "said": h.said, "text": h.text} for h in heard(text)}
    reveal = tuple(e for e, rx in _REVEAL if rx.search(text))
    tid = _setup(text)
    m = _SETUP_CUE.search(text)
    if tid and m:
        return Detection(tid, "cue", values, reveal, m.group(0))
    show = _SHOW_CUE.search(text)
    if show:
        found = tid or next((x for x in (_setup(b) for b in reversed(before[-SHOW_CUE_LOOKBACK:])) if x), "")
        if found:
            return Detection(found, "cue", values, reveal, show.group(0))
    if tid:
        return Detection(tid, "setup", values, reveal)
    if values:
        return Detection("", "values", values, reveal)
    return Detection()


class SimulationDetector:
    """Runs detect() on each content line the understanding service accepted (its ConceptSignal) and publishes a
    RepresentationIntent for every line that proposes something. Holds no deck state."""

    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self._text: OrderedDict[str, str] = OrderedDict()
        self._meta: set[str] = set()
        self._recent: deque[str] = deque(maxlen=SHOW_CUE_LOOKBACK)
        self.intents = 0

    def attach(self) -> None:
        self.bus.subscribe("simulation_detector", self._on_event, [TranscriptFinal, UtteranceClassified, ConceptSignal])

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, TranscriptFinal):
            self._text[event.segment.id] = event.segment.text
            while len(self._text) > MAX_LINES:
                self._text.popitem(last=False)
            return
        if isinstance(event, UtteranceClassified):
            if event.maybe_meta or event.kind != "content":
                self._meta.add(event.segment_id)
                if len(self._meta) > MAX_LINES:
                    self._meta.clear()
            return
        assert isinstance(event, ConceptSignal)
        text = self._text.get(event.segment_id)
        if text is None or event.segment_id in self._meta:
            return
        d = detect(text, tuple(self._recent))
        self._recent.append(text)
        if d.empty:
            return
        self.intents += 1
        log.info("[SIM] %s %s%s %s", d.strength, d.template or "-", f" ({d.cue!r})" if d.cue else "",
                 {k: v["said"] for k, v in d.values.items()})
        await self.bus.publish(RepresentationIntent(
            segment_ids=[event.segment_id], visual_kind="simulation", template=d.template,
            strength=d.strength,  # type: ignore[arg-type]
            values=d.values, reveal=list(d.reveal), origin="cue", text=text[:300]))


def candidate(text: str) -> Optional[str]:
    """The template a line would show with a cue (evaluation helper)."""
    return _setup(text) or None
