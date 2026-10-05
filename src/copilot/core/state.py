"""LectureState and its single writer. Contract: docs/contracts/lecture-state.md."""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Literal, Optional

from pydantic import BaseModel, Field

from copilot.core.bus import EventBus
from copilot.core.events import (
    CommandReceived,
    ConcernRaised,
    ConcernResolved,
    Event,
    InterpretationReady,
    Lifecycle,
    LifecycleChanged,
    SlideContextChanged,
    StateChanged,
    TranscriptFinal,
    new_id,
)
from copilot.core.memory import evict_oldest, find_title, rebuild_summary, title_key

log = logging.getLogger(__name__)

MAX_TOPICS = 20
MAX_SUBTOPICS = 8
SUMMARY_MAX_TOKENS = 120
MAX_CONCERNS = 50
NODE_SUMMARY_MAX_WORDS = 25


class LectureSetup(BaseModel):
    subject: str = ""
    grade_level: str = ""
    expected_topic: str = ""
    output_language: str = "en"
    theme: Literal["light", "dark"] = "light"


class TopicNode(BaseModel):
    id: str = Field(default_factory=new_id)
    title: str
    summary: str = ""
    subtopics: list["TopicNode"] = Field(default_factory=list)
    first_seen: float = 0.0
    last_seen: float = 0.0


class Concern(BaseModel):
    id: str = Field(default_factory=new_id)
    claim: str
    issue: str
    suggested_correction: str = ""
    confidence: float = 0.5
    status: Literal["open", "accepted", "kept", "dismissed"] = "open"
    kind: Literal["factual", "transcription"] = "factual"
    segment_id: str = ""        # first line the concern refers to
    segment_ids: list[str] = Field(default_factory=list)  # every line it refers to (content there is held back)
    request_id: str = ""        # interpretation that raised it


class LectureStats(BaseModel):
    segments: int = 0
    words: int = 0
    llm_calls: int = 0
    fallbacks: int = 0


class LectureState(BaseModel):
    session_id: str
    version: int = 0
    lifecycle: Lifecycle = Lifecycle.STARTING
    setup: LectureSetup = Field(default_factory=LectureSetup)
    level_estimate: str = ""
    subject_estimate: str = ""
    outline: list[TopicNode] = Field(default_factory=list)
    current_topic_id: Optional[str] = None
    current_subtopic_id: Optional[str] = None
    rolling_summary: str = ""
    summary_deltas: list[str] = Field(default_factory=list)  # sentences behind rolling_summary (bounded by its budget)
    concerns: list[Concern] = Field(default_factory=list)
    stats: LectureStats = Field(default_factory=LectureStats)
    slide_context: str = ""       # summary of the slide receiving content (presentation engine), for the prompt
    lecture_clock_s: float = 0.0  # end time of the latest transcript segment
    last_interpretation_id: Optional[str] = None

    def topic(self, topic_id: Optional[str]) -> Optional[TopicNode]:
        return next((t for t in self.outline if t.id == topic_id), None)

    def subtopic(self) -> Optional[TopicNode]:
        t = self.topic(self.current_topic_id)
        return next((s for s in t.subtopics if s.id == self.current_subtopic_id), None) if t else None


class LectureStateStore:
    """The only component allowed to mutate LectureState (ADR-0004).

    Subscribes to events, applies them, bumps the version, publishes StateChanged.
    Readers get deep copies via snapshot().
    """

    def __init__(self, bus: EventBus, session_id: str, setup: Optional[LectureSetup] = None) -> None:
        self._bus = bus
        self._state = LectureState(session_id=session_id, setup=setup or LectureSetup())
        self._outbox: list[Event] = []  # events produced while applying (published after StateChanged)
        self._applied: deque[str] = deque(maxlen=64)
        self._waiters: dict[str, asyncio.Event] = {}

    def attach(self) -> None:
        self._bus.subscribe(
            "state_store",
            self._on_event,
            [LifecycleChanged, TranscriptFinal, CommandReceived, InterpretationReady, SlideContextChanged],
        )

    def snapshot(self) -> LectureState:
        return self._state.model_copy(deep=True)

    @property
    def version(self) -> int:
        return self._state.version

    async def wait_applied(self, request_id: str, timeout: float) -> bool:
        """Wait until the InterpretationReady with this request id has been applied (or failed to apply)."""
        if request_id in self._applied:
            return True
        ev = self._waiters.setdefault(request_id, asyncio.Event())
        waiter = asyncio.ensure_future(ev.wait())
        try:
            # asyncio.wait (not wait_for): on Python 3.10 wait_for can swallow a cancellation
            done, _ = await asyncio.wait({waiter}, timeout=timeout)
            return waiter in done
        finally:
            waiter.cancel()
            self._waiters.pop(request_id, None)

    def _mark_applied(self, request_id: str) -> None:
        self._applied.append(request_id)
        ev = self._waiters.get(request_id)
        if ev is not None:
            ev.set()

    async def _on_event(self, event: Event) -> None:
        try:
            changes = self._apply(event)
            if changes:
                self._state.version += 1
        except Exception:
            self._outbox = []  # never publish side events of a half-applied change
            raise
        finally:
            if isinstance(event, InterpretationReady):
                # Release the understanding worker as soon as the state reflects this result (it reads a
                # snapshot), before downstream publishes that may block on slow subscribers.
                self._mark_applied(event.request_id)
        if changes:
            await self._bus.publish(StateChanged(version=self._state.version, changes=changes))
        outbox, self._outbox = self._outbox, []
        for e in outbox:
            await self._bus.publish(e)

    def _apply(self, event: Event) -> list[str]:
        s = self._state
        if isinstance(event, LifecycleChanged):
            if s.lifecycle != event.state:
                s.lifecycle = event.state
                return ["lifecycle"]
        elif isinstance(event, TranscriptFinal):
            seg = event.segment
            s.stats.segments += 1
            s.stats.words += len(seg.text.split())
            s.lecture_clock_s = max(s.lecture_clock_s, seg.end)
            return ["stats"]
        elif isinstance(event, CommandReceived):
            # Lifecycle commands are executed by the app; slide commands by the planner (M4).
            if event.command.kind == "resolve_concern":
                return self._resolve_concern(event.command.args)
            return []
        elif isinstance(event, InterpretationReady):
            return self._apply_interpretation(event)
        elif isinstance(event, SlideContextChanged):
            if s.slide_context != event.text:
                s.slide_context = event.text
                return ["slide_context"]
        return []

    def _resolve_concern(self, args: dict) -> list[str]:
        status = {"accept": "accepted", "keep": "kept", "dismiss": "dismissed"}.get(str(args.get("action")))
        for c in self._state.concerns:
            if c.id == args.get("id") and status and c.status == "open":
                c.status = status  # type: ignore[assignment]
                self._outbox.append(ConcernResolved(concern_id=c.id, status=status))  # type: ignore[arg-type]
                return ["concerns"]
        log.warning("resolve_concern ignored: %s", args)
        return []

    def _apply_interpretation(self, ev: InterpretationReady) -> list[str]:
        s = self._state
        it = ev.interpretation
        now = s.lecture_clock_s
        changes = ["stats"]
        if ev.provider:
            s.stats.llm_calls += 1
        if ev.fallback:
            s.stats.fallbacks += 1
        s.last_interpretation_id = ev.request_id

        if it.relation != "digression":
            topic = self._touch_node(s.outline, it.topic, MAX_TOPICS, now)
            sub: Optional[TopicNode] = None
            # A subtopic equal to its topic's title is not a separate node.
            if it.subtopic and title_key(it.subtopic) != title_key(topic.title):
                sub = self._touch_node(topic.subtopics, it.subtopic, MAX_SUBTOPICS, now)
            if it.summary_delta:
                node = sub or topic
                if not node.summary:
                    node.summary = " ".join(it.summary_delta.split()[:NODE_SUMMARY_MAX_WORDS])
            new_sub_id = sub.id if sub else None
            if topic.id != s.current_topic_id:
                changes.append("topic")
            if new_sub_id != s.current_subtopic_id:
                changes.append("subtopic")
            s.current_topic_id, s.current_subtopic_id = topic.id, new_sub_id
            changes.append("outline")

        if it.summary_delta:
            s.rolling_summary, s.summary_deltas = rebuild_summary(
                [*s.summary_deltas, it.summary_delta], SUMMARY_MAX_TOKENS
            )
            changes.append("summary")
        if it.level_estimate:
            s.level_estimate = it.level_estimate
        if it.subject_estimate:
            s.subject_estimate = it.subject_estimate

        for item in it.concerns:
            segs = [ev.segment_ids[n - 1] for n in item.lines if 1 <= n <= len(ev.segment_ids)]
            concern = Concern(
                claim=item.claim, issue=item.issue, suggested_correction=item.suggested_correction,
                confidence=item.confidence, kind=item.kind, segment_id=segs[0] if segs else "",
                segment_ids=segs, request_id=ev.request_id,
            )
            s.concerns.append(concern)
            self._outbox.append(ConcernRaised(concern=concern.model_dump()))
        if it.concerns:
            self._prune_concerns()
            changes.append("concerns")
        return changes

    @staticmethod
    def _touch_node(nodes: list[TopicNode], title: str, cap: int, now: float) -> TopicNode:
        idx = find_title(nodes, title)
        if idx is not None:
            node = nodes[idx]
            node.last_seen = now
            return node
        node = TopicNode(title=title, first_seen=now, last_seen=now)
        nodes.append(node)
        evict_oldest(nodes, cap, keep_id=node.id)
        return node

    def _prune_concerns(self) -> None:
        cs = self._state.concerns
        while len(cs) > MAX_CONCERNS:
            resolved = [c for c in cs if c.status != "open"]
            cs.remove(resolved[0] if resolved else cs[0])
