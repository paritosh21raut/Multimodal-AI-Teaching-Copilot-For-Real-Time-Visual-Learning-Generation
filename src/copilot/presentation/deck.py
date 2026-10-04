"""Deck: the session's slides and what is on screen (docs/architecture/presentation.md).

The Deck is the single writer of slides. The planner (M4) calls add/update; the teacher's commands
arrive as CommandReceived events. Every change is published as SlidePatch / DeckState.

Display flags:
- following: the live slide jumps to each new slide (off when the teacher navigates back)
- pinned:    stay on the current slide; in-place updates still show; new slides queue behind it
- frozen:    the projector keeps exactly what it shows now (the display client holds its last render)
- blank:     the projector shows an empty screen
"""
from __future__ import annotations

import logging
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, DeckState, Event, SlidePatch
from copilot.presentation.spec import SlideSpec

log = logging.getLogger(__name__)

NAV_COMMANDS = {"next", "prev", "goto", "pin", "unpin", "freeze", "unfreeze", "blank", "unblank"}


class Deck:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._slides: dict[str, SlideSpec] = {}
        self._order: list[str] = []
        self.live_id: Optional[str] = None
        self.following = True
        self.pinned = False
        self.frozen = False
        self.blank = False

    def attach(self) -> None:
        self._bus.subscribe("deck", self._on_command, [CommandReceived])

    # ---- queries --------------------------------------------------------------------------
    def get(self, slide_id: str) -> SlideSpec:
        return self._slides[slide_id]

    @property
    def slides(self) -> list[SlideSpec]:
        return [self._slides[i] for i in self._order]

    @property
    def live(self) -> Optional[SlideSpec]:
        return self._slides.get(self.live_id) if self.live_id else None

    def state_event(self) -> DeckState:
        return DeckState(
            live_id=self.live_id, slide_ids=list(self._order), following=self.following,
            pinned=self.pinned, frozen=self.frozen, blank=self.blank,
        )

    # ---- slide ops (planner) --------------------------------------------------------------
    async def add(self, spec: SlideSpec) -> SlideSpec:
        if spec.id in self._slides:
            raise ValueError(f"slide {spec.id} already exists")
        spec = spec.model_copy(update={"version": 1})
        self._slides[spec.id] = spec
        self._order.append(spec.id)
        await self._bus.publish(SlidePatch(slide_id=spec.id, version=1, op="add", spec=spec.model_dump()))
        if self.live_id is None or (self.following and not self.pinned):
            self.live_id = spec.id
        await self._publish_state()
        return spec

    async def update(self, spec: SlideSpec) -> SlideSpec:
        old = self._slides.get(spec.id)
        if old is None:
            raise KeyError(f"unknown slide {spec.id}")
        spec = spec.model_copy(update={"version": old.version + 1})
        self._slides[spec.id] = spec
        await self._bus.publish(SlidePatch(slide_id=spec.id, version=spec.version, op="update", spec=spec.model_dump()))
        return spec

    # ---- teacher commands -----------------------------------------------------------------
    async def _on_command(self, event: Event) -> None:
        assert isinstance(event, CommandReceived)
        cmd = event.command
        if cmd.kind not in NAV_COMMANDS:
            return
        if self._apply_command(cmd.kind, cmd.args):
            await self._publish_state()

    def _apply_command(self, kind: str, args: dict) -> bool:
        idx = self._order.index(self.live_id) if self.live_id in self._order else -1
        if kind in ("next", "prev", "goto"):
            if not self._order:
                return False
            if kind == "next":
                target = min(idx + 1, len(self._order) - 1)
            elif kind == "prev":
                target = max(idx - 1, 0)
            else:
                target_id = args.get("slide_id")
                if target_id not in self._order:
                    log.warning("goto unknown slide %r", target_id)
                    return False
                target = self._order.index(target_id)
            self.live_id = self._order[target]
            self.following = target == len(self._order) - 1
            return True
        flag, value = {
            "pin": ("pinned", True), "unpin": ("pinned", False),
            "freeze": ("frozen", True), "unfreeze": ("frozen", False),
            "blank": ("blank", True), "unblank": ("blank", False),
        }[kind]
        if getattr(self, flag) == value:
            return False
        setattr(self, flag, value)
        if kind == "unpin" and self.following and self._order:
            self.live_id = self._order[-1]  # catch up with slides queued while pinned
        return True

    async def _publish_state(self) -> None:
        await self._bus.publish(self.state_event())
