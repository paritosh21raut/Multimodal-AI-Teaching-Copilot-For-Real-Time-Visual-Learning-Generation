"""Deck: the session's slides and what is on screen (docs/architecture/presentation.md).

The Deck is the single writer of slides. The planner (M4) calls add/update; the teacher's commands
arrive as CommandReceived events. Every change is published as SlidePatch / DeckState.

Display flags:
- following: the live slide jumps to each new slide (off when the teacher navigates back)
- blank:     the projector shows an empty screen
(Freeze was replaced by Pause, user 2026-10-06: a lifecycle state, not a display flag; see app/main.py.
 Pin was removed, user 2026-10-06: Pause, Blank and navigating back cover it.)
- zoom:      a slide's image fills the projector (the teacher clicked it in /control); ends on Back / Esc, on
             navigation, or when that image leaves the slide. New content keeps arriving behind it.
"""
from __future__ import annotations

import logging
from typing import Optional

from copilot.core.bus import EventBus
from copilot.core.events import CommandReceived, DeckState, Event, SlidePatch
from copilot.presentation.annotate import annotate
from copilot.presentation.spec import SlideSpec

log = logging.getLogger(__name__)

NAV_COMMANDS = {"next", "prev", "goto", "blank", "unblank", "zoom_image", "unzoom_image"}


def _has_image(spec: SlideSpec) -> bool:
    return any(b.type == "image" for b in spec.blocks)


class Deck:
    def __init__(self, bus: EventBus) -> None:
        self._bus = bus
        self._slides: dict[str, SlideSpec] = {}
        self._order: list[str] = []
        self.live_id: Optional[str] = None
        self.following = True
        self.blank = False
        self.zoom: Optional[str] = None

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
            blank=self.blank, zoom=self.zoom,
        )

    # ---- slide ops (planner) --------------------------------------------------------------
    async def add(self, spec: SlideSpec, activate: bool = True, after: Optional[str] = None) -> SlideSpec:
        """activate=False: append without moving the live slide (e.g. late content for an earlier frame).
        after: insert right behind this slide instead of at the end (content moved off it to its next part)."""
        if spec.id in self._slides:
            raise ValueError(f"slide {spec.id} already exists")
        spec = annotate(spec).model_copy(update={"version": 1})  # formulas in text, list style
        self._slides[spec.id] = spec
        if after in self._order:
            self._order.insert(self._order.index(after) + 1, spec.id)
        else:
            self._order.append(spec.id)
        await self._bus.publish(SlidePatch(slide_id=spec.id, version=1, op="add", spec=spec.model_dump()))
        if self.live_id is None or (activate and self.following):
            self.live_id = spec.id
        await self._publish_state()
        return spec

    async def update(self, spec: SlideSpec) -> SlideSpec:
        old = self._slides.get(spec.id)
        if old is None:
            raise KeyError(f"unknown slide {spec.id}")
        spec = annotate(spec).model_copy(update={"version": old.version + 1})
        self._slides[spec.id] = spec
        await self._bus.publish(SlidePatch(slide_id=spec.id, version=spec.version, op="update", spec=spec.model_dump()))
        if self.zoom == spec.id and not _has_image(spec):  # the zoomed image was removed (or yielded to a diagram)
            self.zoom = None
            await self._publish_state()
        return spec

    async def remove(self, slide_id: str) -> None:
        """Drop a slide that ended up empty (its content moved to the right topic's slide)."""
        if slide_id not in self._slides:
            return
        idx = self._order.index(slide_id)
        self._order.remove(slide_id)
        del self._slides[slide_id]
        if self.zoom == slide_id:
            self.zoom = None
        if self.live_id == slide_id:
            self.live_id = self._order[min(idx, len(self._order) - 1)] if self._order else None
        await self._publish_state()

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
            self.zoom = None  # moving through the deck shows slides again
            return True
        if kind == "zoom_image":
            target_id = args.get("slide_id")
            if target_id not in self._slides or not _has_image(self._slides[target_id]) or self.zoom == target_id:
                return False
            self.zoom = target_id
            return True
        if kind == "unzoom_image":
            if self.zoom is None:
                return False
            self.zoom = None
            return True
        value = kind == "blank"  # blank / unblank
        if self.blank == value:
            return False
        self.blank = value
        return True

    async def _publish_state(self) -> None:
        await self._bus.publish(self.state_event())
