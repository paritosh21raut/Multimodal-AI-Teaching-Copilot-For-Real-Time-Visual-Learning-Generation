"""DisplayHub: bus events → WebSocket clients; client commands → bus (F-003).

The hub caches the latest deck so any (re)connecting client gets the full current state.
Each connection has a coalescing outbox: a newer patch for the same slide replaces an unsent older one,
so a slow client never falls behind the live state.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from typing import Any, Literal, Optional

from pydantic import ValidationError

from copilot.core.bus import EventBus
from copilot.core.events import (
    AudioLevel,
    Command,
    CommandReceived,
    ConcernRaised,
    ConcernResolved,
    DeckState,
    Event,
    ImageChoices,
    ImageReady,
    ImageRequested,
    LifecycleChanged,
    SlideOverflow,
    SlidePatch,
    TranscriptFinal,
    UtteranceDropped,
)

log = logging.getLogger(__name__)

Role = Literal["display", "control"]
TRANSCRIPT_LINES = 40


class Connection:
    def __init__(self, role: Role) -> None:
        self.role = role
        self._outbox: dict[Any, dict] = {}
        self._seq = 0
        self._ready = asyncio.Event()
        self.closed = False

    def push(self, msg: dict, key: Any = None) -> None:
        """Queue a message. Messages with the same key coalesce (latest wins, original position kept)."""
        if self.closed:
            return
        if key is None:
            self._seq += 1
            key = ("seq", self._seq)
        self._outbox[key] = msg
        self._ready.set()

    async def next_batch(self) -> list[dict]:
        await self._ready.wait()
        batch = list(self._outbox.values())
        self._outbox.clear()
        self._ready.clear()
        return batch


class DisplayHub:
    def __init__(self, bus: EventBus, theme: str = "light") -> None:
        self._bus = bus
        self.theme = theme
        self.connections: set[Connection] = set()
        self.slides: dict[str, dict] = {}  # slide_id -> spec dump (latest version)
        self.deck: Optional[dict] = None
        self.lifecycle = "starting"
        self.transcript: deque[dict] = deque(maxlen=TRANSCRIPT_LINES)
        self.concerns: dict[str, dict] = {}  # open concerns (control view only; never sent to the display)
        self.image_choices: dict[str, dict] = {}  # slide_id -> {index, count} (control only)
        self._image_requests: dict[str, str] = {}  # running image searches: request_id -> auto | change
        self.connects: dict[str, int] = {"display": 0, "control": 0}  # connections ever made, per role

    def attach(self) -> None:
        self._bus.subscribe(
            "display_hub", self._on_event,
            [SlidePatch, DeckState, LifecycleChanged, TranscriptFinal, UtteranceDropped, ConcernRaised,
             ConcernResolved, ImageRequested, ImageReady, ImageChoices],
        )
        # Audio levels are high-rate and only matter "now": drop old ones if the hub lags.
        self._bus.subscribe("display_hub_audio", self._on_event, [AudioLevel], queue_size=4, overflow="drop_oldest")

    # ---- client side ---------------------------------------------------------------------
    def connect(self, role: Role) -> Connection:
        conn = Connection(role)
        self.connections.add(conn)
        self.connects[role] = self.connects.get(role, 0) + 1
        conn.push(self.hello(role))
        return conn

    def disconnect(self, conn: Connection) -> None:
        conn.closed = True
        self.connections.discard(conn)

    def hello(self, role: Role = "display") -> dict:  # fail closed: concerns only on explicit request
        msg = {
            "type": "hello",
            "theme": self.theme,
            "lifecycle": self.lifecycle,
            "slides": self.slides,
            "deck": self.deck,
            "transcript": list(self.transcript),
        }
        if role == "control":  # doubtful claims never reach the projector
            msg["concerns"] = list(self.concerns.values())
            msg["image_choices"] = dict(self.image_choices)
        return msg

    async def handle_client_message(self, conn: Connection, msg: dict) -> Optional[str]:
        """Returns an error string for the client, or None."""
        if msg.get("type") == "overflow":  # display auto-fit could not fit the slide
            slide_id = msg.get("slide_id")
            if not isinstance(slide_id, str) or slide_id not in self.slides:
                return "overflow: unknown slide"
            version = msg.get("version")
            await self._bus.publish(SlideOverflow(slide_id=slide_id, version=version if isinstance(version, int) else 0))
            return None
        if msg.get("type") != "command":
            return f"unknown message type {msg.get('type')!r}"
        if conn.role != "control":
            return "only the control view may send commands"
        try:
            cmd = Command(kind=msg.get("kind"), args=msg.get("args") or {}, origin="control")
        except ValidationError as e:
            return f"invalid command: {e.errors()[0]['msg']}"
        await self._bus.publish(CommandReceived(command=cmd))
        return None

    # ---- bus side ------------------------------------------------------------------------
    def _broadcast(self, msg: dict, key: Any = None, roles: tuple[Role, ...] = ("display", "control")) -> None:
        for conn in list(self.connections):
            if conn.role in roles:
                conn.push(msg, key)

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, SlidePatch):
            self.slides[event.slide_id] = event.spec
            self._broadcast({"type": "patch", "slide_id": event.slide_id, "version": event.version, "spec": event.spec},
                            key=("patch", event.slide_id))
        elif isinstance(event, DeckState):
            self.deck = event.model_dump(include={"live_id", "slide_ids", "following", "pinned", "frozen", "blank", "zoom"})
            for sid in [s for s in self.slides if s not in event.slide_ids]:  # removed slides
                del self.slides[sid]
            self._broadcast({"type": "deck", "deck": self.deck}, key=("deck",))
        elif isinstance(event, LifecycleChanged):
            self.lifecycle = event.state.value
            self._broadcast({"type": "lifecycle", "lifecycle": self.lifecycle}, key=("lifecycle",))
        elif isinstance(event, TranscriptFinal):
            line = {"t": event.segment.start, "text": event.segment.text, "latency_ms": event.stt_latency_ms}
            self.transcript.append(line)
            self._broadcast({"type": "transcript", "line": line}, roles=("control",))
        elif isinstance(event, UtteranceDropped):
            line = {"t": event.start, "text": event.text, "dropped": event.reason}
            self.transcript.append(line)
            self._broadcast({"type": "transcript", "line": line}, roles=("control",))
        elif isinstance(event, ConcernRaised):
            c = event.concern
            if c.get("status", "open") == "open":
                self.concerns[c["id"]] = c
                self._broadcast({"type": "concern", "concern": c}, roles=("control",))
        elif isinstance(event, ConcernResolved):
            c = self.concerns.get(event.concern_id)
            if event.status == "dismissed" or c is None:  # OK: the teacher has seen it
                self.concerns.pop(event.concern_id, None)
                self._broadcast({"type": "concern_resolved", "id": event.concern_id, "status": event.status},
                                roles=("control",))
            else:  # switched: stays listed so the teacher can switch back
                c = {**c, "status": event.status, "applied": event.status == "accepted"}
                self.concerns[event.concern_id] = c
                self._broadcast({"type": "concern", "concern": c}, roles=("control",))
        elif isinstance(event, ImageRequested):  # control only: the teacher sees "searching…" under the slide
            self._image_requests[event.request_id] = event.reason
            self._broadcast({"type": "image_status", "slide_id": event.slide_id, "state": "searching",
                             "request": event.reason, "reason": ""}, key=("image", event.slide_id), roles=("control",))
        elif isinstance(event, ImageReady):  # request: auto | change (the teacher's Find / Change); reason: why none
            self._broadcast({"type": "image_status", "slide_id": event.slide_id,
                             "state": "found" if event.images else "none",
                             "request": self._image_requests.pop(event.request_id, "auto"), "reason": event.reason},
                            key=("image", event.slide_id), roles=("control",))
        elif isinstance(event, ImageChoices):  # control only: the previous / next image arrows
            self.image_choices[event.slide_id] = {"index": event.index, "count": event.count}
            self._broadcast({"type": "image_choices", "slide_id": event.slide_id, "index": event.index,
                             "count": event.count}, key=("choices", event.slide_id), roles=("control",))
        elif isinstance(event, AudioLevel):
            self._broadcast({"type": "audio", "rms": event.rms, "speaking": event.speaking},
                            key=("audio",), roles=("control",))
