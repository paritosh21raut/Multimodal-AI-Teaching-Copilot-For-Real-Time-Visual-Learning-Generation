"""DisplayHub: bus events → WebSocket clients; client commands → bus (F-003).

The hub caches the latest deck so any (re)connecting client gets the full current state.
Each connection has a coalescing outbox: a newer patch for the same slide replaces an unsent older one,
so a slow client never falls behind the live state.
"""
from __future__ import annotations

import asyncio
import logging
from collections import OrderedDict, deque
from typing import Any, Literal, Optional

from pydantic import ValidationError

from copilot.core.bus import EventBus
from copilot.core.events import (
    AssessState,
    AudioLevel,
    Command,
    CommandReceived,
    ConcernRaised,
    ConcernResolved,
    CorrectionPlaced,
    DeckState,
    Event,
    ImageChoices,
    ImageReady,
    ImageRequested,
    LifecycleChanged,
    MaterialsState,
    ModeChanged,
    NotesProjected,
    NotesState,
    ShareChanged,
    SimulationNotice,
    SimulationSettingChanged,
    SimulationSuggestion,
    SlideOverflow,
    SlidePatch,
    ThemeChanged,
    TranscriptFinal,
    UtteranceDropped,
)

log = logging.getLogger(__name__)

Role = Literal["display", "control", "viewer"]  # viewer: a student's /view page (F-008), receives what the display does
SLIDE_ROLES: tuple[Role, ...] = ("display", "control", "viewer")
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


def shown_as(card: dict, shows: str) -> dict:
    """A mistake card with what the slides show (F-013 S3, E1): "correction" | "said" | "rewritten" | "absent".
    `applied` stays the card's switch state: true when the slide carries the correction (or says it correctly)."""
    return {**card, "shows": shows, "applied": shows in ("correction", "rewritten")}


class DisplayHub:
    def __init__(self, bus: EventBus, theme: str = "light") -> None:
        self._bus = bus
        self.theme = theme
        self.connections: set[Connection] = set()
        self.slides: dict[str, dict] = {}  # slide_id -> spec dump (latest version)
        self.deck: Optional[dict] = None
        self.lifecycle = "starting"
        self.transcript: deque[dict] = deque(maxlen=TRANSCRIPT_LINES)
        self.concerns: dict[str, dict] = {}  # open mistake cards (control view only; never sent to the display)
        self._placed: OrderedDict[str, str] = OrderedDict()  # F-013 S3 (E1): what the slides show, per concern
        self.image_choices: dict[str, dict] = {}  # slide_id -> {index, count} (control only)
        self._image_requests: dict[str, str] = {}  # running image searches: request_id -> auto | change
        self.connects: dict[str, int] = {"display": 0, "control": 0, "viewer": 0}  # connections ever made, per role
        self.share: dict = {"state": "off", "url": "", "detail": ""}  # control only (F-008)
        self.notes: Optional[dict] = None  # the teacher's PDF notes (F-009), control only
        self.mode = ""  # performance mode (F-013), control only; "" until the app says
        self.sim_setting = ""  # F-014 S1: auto | suggest | off, control only; "" until the app says
        self.sim_suggestion: Optional[dict] = None  # the open Suggest chip (control only)
        self.materials: Optional[dict] = None  # lecture materials (F-010), control only
        self.shared: list[dict] = []  # PDFs the students may download (F-010), to every viewer
        self.notes_shown: dict = {"on": False, "doc_id": "", "page": 0, "name": ""}  # F-010b, every role
        self.assess_control: dict = {}  # the quiz / test with its answer keys (F-011), control only
        self.assess_public: dict = {}   # the same without keys before they are due: display + students

    def attach(self) -> None:
        self._bus.subscribe(
            "display_hub", self._on_event,
            [SlidePatch, DeckState, LifecycleChanged, TranscriptFinal, UtteranceDropped, ConcernRaised,
             ConcernResolved, CorrectionPlaced, ImageRequested, ImageReady, ImageChoices, ShareChanged, ThemeChanged, ModeChanged, NotesState,
             NotesProjected,
             MaterialsState, AssessState, SimulationNotice, SimulationSettingChanged, SimulationSuggestion],
        )
        # Audio levels are high-rate and only matter "now": drop old ones if the hub lags.
        self._bus.subscribe("display_hub_audio", self._on_event, [AudioLevel], queue_size=4, overflow="drop_oldest")

    # ---- client side ---------------------------------------------------------------------
    def connect(self, role: Role) -> Connection:
        conn = Connection(role)
        self.connections.add(conn)
        self.connects[role] = self.connects.get(role, 0) + 1
        conn.push(self.hello(role))
        if role == "viewer":
            self._viewers_changed()
        return conn

    def disconnect(self, conn: Connection) -> None:
        conn.closed = True
        self.connections.discard(conn)
        if conn.role == "viewer":
            self._viewers_changed()

    @property
    def viewers(self) -> int:
        return sum(1 for c in self.connections if c.role == "viewer")

    def _viewers_changed(self) -> None:  # the teacher sees how many students are watching
        self._broadcast({"type": "viewers", "count": self.viewers}, key=("viewers",), roles=("control",))

    def hello(self, role: Role = "display") -> dict:  # fail closed: concerns only on explicit request
        msg = {
            "type": "hello",
            "theme": self.theme,
            "lifecycle": self.lifecycle,
            "slides": self.slides,
            "deck": self.deck,
            "transcript": list(self.transcript) if role != "viewer" else [],  # students get the slides only
            "notes_shown": dict(self.notes_shown),  # a notes page the teacher put on the projector (F-010b)
        }
        if role == "control":  # doubtful claims never reach the projector
            msg["concerns"] = list(self.concerns.values())
            msg["image_choices"] = dict(self.image_choices)
            msg["share"] = dict(self.share)
            msg["viewers"] = self.viewers
            msg["notes"] = self.notes
            msg["mode"] = self.mode
            msg["sim_setting"] = self.sim_setting
            msg["sim_suggestion"] = self.sim_suggestion
            msg["materials"] = self.materials
            msg["assess"] = dict(self.assess_control)
        else:  # the projector and the students: never an answer key before it is due (F-011)
            msg["assess"] = self._assess_for(role)
        if role == "viewer":  # the PDFs the teacher shares (F-010)
            msg["shared"] = list(self.shared)
        return msg

    def _assess_for(self, role: Role) -> dict:
        """The quiz / test for the projector or a student (no keys before due). The projector also gets the students'
        join link while one is open (its lobby QR); the share state itself stays the teacher's (F-008)."""
        msg: dict = {"public": dict(self.assess_public)}
        if role == "display" and self.assess_public and self.share.get("state") == "on":
            msg["join_url"] = self.share.get("url", "")
        return msg

    async def handle_client_message(self, conn: Connection, msg: dict) -> Optional[str]:
        """Returns an error string for the client, or None."""
        if conn.role == "viewer":  # a student's page only watches
            return "view only"
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
    def _broadcast(self, msg: dict, key: Any = None, roles: tuple[Role, ...] = SLIDE_ROLES) -> None:
        for conn in list(self.connections):
            if conn.role in roles:
                conn.push(msg, key)

    async def _on_event(self, event: Event) -> None:
        if isinstance(event, SlidePatch):
            self.slides[event.slide_id] = event.spec
            self._broadcast({"type": "patch", "slide_id": event.slide_id, "version": event.version, "spec": event.spec},
                            key=("patch", event.slide_id))
        elif isinstance(event, DeckState):
            self.deck = event.model_dump(include={"live_id", "slide_ids", "following", "blank", "zoom", "sim_full", "sim_mode"})
            for sid in [s for s in self.slides if s not in event.slide_ids]:  # removed slides
                del self.slides[sid]
            self._broadcast({"type": "deck", "deck": self.deck}, key=("deck",))
        elif isinstance(event, LifecycleChanged):
            self.lifecycle = event.state.value
            self._broadcast({"type": "lifecycle", "lifecycle": self.lifecycle}, key=("lifecycle",))
        elif isinstance(event, TranscriptFinal):
            line = {"t": event.segment.start, "text": event.segment.text, "latency_ms": event.stt_latency_ms}
            if self.lifecycle == "paused":  # said during a pause: shown to the teacher, not interpreted
                line["dropped"] = "paused"
            self.transcript.append(line)
            self._broadcast({"type": "transcript", "line": line}, roles=("control",))
        elif isinstance(event, UtteranceDropped):
            line = {"t": event.start, "text": event.text, "dropped": event.reason}
            self.transcript.append(line)
            self._broadcast({"type": "transcript", "line": line}, roles=("control",))
        elif isinstance(event, ConcernRaised):
            c = event.concern
            # misheard words (spelling / pronunciation) are corrected without asking (user 2026-10-06; terminal
            # log only); the teacher sees a card only for a factual, conceptual or formula mistake
            if c.get("status", "open") == "open" and c.get("kind") != "transcription":
                if c["id"] in self._placed:  # the engine placed it before this card arrived
                    c = shown_as(c, self._placed[c["id"]])
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
        elif isinstance(event, CorrectionPlaced):  # F-013 S3 (E1): the card says what the slide really shows
            self._placed[event.concern_id] = event.shows
            while len(self._placed) > 128:
                self._placed.popitem(last=False)
            c = self.concerns.get(event.concern_id)
            if c is not None:
                c = shown_as(c, event.shows)
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
        elif isinstance(event, SimulationNotice):  # control only (F-014): "heard 95° - not used"
            self._broadcast({"type": "sim_notice", "slide_id": event.slide_id, "text": event.text},
                            key=("sim_notice",), roles=("control",))
        elif isinstance(event, ImageChoices):  # control only: the previous / next image arrows
            self.image_choices[event.slide_id] = {"index": event.index, "count": event.count}
            self._broadcast({"type": "image_choices", "slide_id": event.slide_id, "index": event.index,
                             "count": event.count}, key=("choices", event.slide_id), roles=("control",))
        elif isinstance(event, ShareChanged):  # control only: the student link and its state
            self.share = {"state": event.state, "url": event.url, "detail": event.detail}
            self._broadcast({"type": "share", **self.share}, key=("share",), roles=("control",))
            if self.assess_public:  # an open quiz / test shows the join link on the projector (F-011)
                self._broadcast({"type": "assess", **self._assess_for("display")}, key=("assess",), roles=("display",))
        elif isinstance(event, NotesState):  # control only: the teacher's own notes never reach a slide page
            # F-013 S4: the study-material lines (reading %, the passage a slide used, a refused toggle) reach /control too
            self.notes = event.model_dump(include={"docs", "open", "page", "pages", "projecting", "indexing", "used",
                                                   "notice"})
            self._broadcast({"type": "notes", **self.notes}, key=("notes",), roles=("control",))
        elif isinstance(event, NotesProjected):  # the teacher shows a notes page on the projector (F-010b)
            self.notes_shown = event.model_dump(include={"on", "doc_id", "page", "name"})
            self._broadcast({"type": "notes_shown", **self.notes_shown}, key=("notes_shown",))
        elif isinstance(event, MaterialsState):  # control: everything made; students: the shared PDFs only
            self.materials = event.model_dump(include={"items", "current", "llm", "lectures_changed", "chapters",
                                                       "last_chapter"})
            self._broadcast({"type": "materials", **self.materials}, key=("materials",), roles=("control",))
            if event.shared != self.shared:
                self.shared = list(event.shared)
                self._broadcast({"type": "shared", "items": self.shared}, key=("shared",), roles=("viewer",))
        elif isinstance(event, AssessState):  # control: the whole quiz / test; display + students: the public part
            self.assess_control = event.model_dump(include={"control", "public", "notice", "llm", "now"})
            self._broadcast({"type": "assess", **self.assess_control}, key=("assess",), roles=("control",))
            if event.public != self.assess_public:
                self.assess_public = dict(event.public)
                for role in ("display", "viewer"):
                    self._broadcast({"type": "assess", **self._assess_for(role)}, key=("assess",), roles=(role,))
        elif isinstance(event, SimulationSettingChanged):  # F-014 S1: Auto / Suggest / Off
            self.sim_setting = event.setting
            self._broadcast({"type": "sim_setting", "setting": event.setting}, key=("sim_setting",), roles=("control",))
        elif isinstance(event, SimulationSuggestion):  # F-014 S1: the chip, or its end
            self.sim_suggestion = event.model_dump(include={"id", "template", "name", "text"}) if event.active else None
            self._broadcast({"type": "sim_suggestion", "suggestion": self.sim_suggestion}, key=("sim_suggestion",),
                            roles=("control",))
        elif isinstance(event, ModeChanged):  # the teacher's performance switch (F-013)
            self.mode = event.mode
            self._broadcast({"type": "mode", "mode": self.mode}, key=("mode",), roles=("control",))
        elif isinstance(event, ThemeChanged):  # every slide page repaints; students follow the teacher's theme
            self.theme = event.theme
            self._broadcast({"type": "theme", "theme": self.theme}, key=("theme",))
        elif isinstance(event, AudioLevel):
            self._broadcast({"type": "audio", "rms": event.rms, "speaking": event.speaking},
                            key=("audio",), roles=("control",))
