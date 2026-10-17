"""The presentation engine's Concept Simulation part (F-014 S0). Called by PresentationEngine under its lock; the
engine stays the only writer of the deck.

    RepresentationIntent -> simulation.policy -> show / reopen / switch / update on the slide being built
    teacher commands     -> sim_show / sim_set / sim_play / sim_pause / sim_step / sim_reset / sim_toggle / sim_pick /
                            sim_remove (sim_full is a display flag: the Deck)

Placement: the simulation is a block of the slide being built (the simulation layout: the stage ~65 % wide, the
slide's points beside it). When the slide's content does not fit beside it (or the teacher put an image there) it
opens the next part of the same slide. While it is open (same topic, spoken about within LISTEN_LINES lines) it
follows the explanation: a new slide of the topic takes it along, so the stage never stays behind on a slide the
projector has left. Anything the teacher does to it holds it where it is.

Clock: the server keeps where the motion is (Playback.t at the anchor + the time since, at Playback.speed) so pause
and step give every page the same frame; a change of values never touches the clock (the clients tween to the new
values and keep running).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from pydantic import ValidationError

from copilot.core.events import RepresentationIntent, SimulationNotice
from copilot.core.memory import titles_match
from copilot.presentation.composer import (
    element_texts, fits, frame_slide, image_of, sim_of, with_simulation, without_simulation,
)
from copilot.presentation.planner import Frame
from copilot.presentation.spec import SimulationBlock, SlideSpec
from copilot.simulation import registry
from copilot.simulation.base import SimBase, fmt
from copilot.simulation.policy import decide

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

LISTEN_LINES = 12   # content lines after the last intent for it before an open simulation stops listening
STEP_S = 0.25       # simulation seconds per Step
ROUGH_MU = 0.3      # "a rough surface", value not said: friction is drawn with this (never printed)
SPEEDS = (0.25, 0.5, 1.0, 1.5, 2.0)


@dataclass
class OpenSim:
    block_id: str
    slide_id: str
    topic: str
    template: str
    quiet: int = 0
    held: bool = False  # the teacher acted on it: it stays on its slide


@dataclass
class _Clock:
    at: float = 0.0     # server clock when Playback.t was last set
    t: float = 0.0


@dataclass
class SimulationController:
    e: "PresentationEngine"
    open: Optional[OpenSim] = None
    where: dict[str, str] = field(default_factory=dict)            # block id -> slide id
    toggled: dict[str, dict[str, bool]] = field(default_factory=dict)  # block id -> the teacher's element choices
    revealed: dict[str, set[str]] = field(default_factory=dict)    # block id -> elements the teacher named
    clocks: dict[str, _Clock] = field(default_factory=dict)
    by_topic: dict[tuple[str, str], str] = field(default_factory=dict)  # (topic, template) -> block id
    removed: set[tuple[str, str]] = field(default_factory=set)     # (topic, template) the teacher removed

    # ---- lookup ---------------------------------------------------------------------------------------------
    def _block(self, block_id: str) -> tuple[Optional[SlideSpec], Optional[SimulationBlock]]:
        spec = self.e._spec(self.where.get(block_id, ""))
        b = sim_of(spec) if spec is not None else None
        return (spec, b) if b is not None and b.id == block_id else (None, None)

    def _on_slide(self, slide_id: str) -> tuple[Optional[SlideSpec], Optional[SimulationBlock]]:
        spec = self.e._spec(slide_id)
        return (spec, sim_of(spec)) if spec is not None else (None, None)

    def _target(self) -> tuple[Optional[SlideSpec], Optional[Frame]]:
        """The slide content is going to (as for an asked figure); None for a title slide / nothing yet."""
        e = self.e
        spec = e._spec(e._open_cue_slide() or e._working_id or "") or e.deck.live
        meta = e._meta.get(spec.id) if spec is not None else None
        if spec is None or meta is None or meta.is_title:
            return None, None
        return spec, meta.frame

    def _lecture_topic(self) -> str:
        snap = self.e.store.snapshot()
        topic = snap.topic(snap.current_topic_id)
        return (topic.title if topic is not None else "") or snap.setup.expected_topic or "Simulation"

    @staticmethod
    def _key(topic: str, template: str) -> tuple[str, str]:
        return " ".join(topic.lower().split()), template

    def _find(self, topic: str, template: str) -> Optional[str]:
        for (t, tid), bid in self.by_topic.items():
            if tid == template and titles_match(t, topic) and self._block(bid)[1] is not None:
                return bid
        return None

    def _is_removed(self, topic: str, template: str) -> bool:
        return any(tid == template and titles_match(t, topic) for t, tid in self.removed)

    def now_t(self, b: SimulationBlock) -> float:
        """Where the motion is now (simulation seconds), as every page computes it."""
        pb = b.sim.playback
        c = self.clocks.get(b.id)
        if pb.state != "playing" or c is None:
            return pb.t
        return c.t + max(0.0, self.e.clock() - c.at) * pb.speed

    def _anchor(self, b: SimulationBlock) -> None:
        self.clocks[b.id] = _Clock(self.e.clock(), b.sim.playback.t)

    def _toggles(self, block_id: str) -> dict[str, bool]:
        return {**{x: True for x in self.revealed.get(block_id, ())}, **self.toggled.get(block_id, {})}

    # ---- writing --------------------------------------------------------------------------------------------
    async def _replace(self, spec: SlideSpec, b: SimulationBlock, sim: SimBase) -> SimulationBlock:
        new = b.model_copy(update={"sim": sim})
        await self.e._commit(spec.model_copy(update={"blocks": [new if x.id == b.id else x for x in spec.blocks]}))
        if sim.playback.rev != b.sim.playback.rev:
            self._anchor(new)
        return new

    async def _place(self, block: SimulationBlock, target: Optional[SlideSpec], frame: Optional[Frame]) -> str:
        """Put the block on the slide being built, or on its next part when the content does not fit beside it; a new
        slide when there is no content slide yet (a title slide). Returns the slide id."""
        e = self.e
        from copilot.presentation.engine import SlideMeta  # the engine imports this module

        if target is None or frame is None:
            topic = self._lecture_topic()
            frame = Frame(topic, topic)
            spec = with_simulation(frame_slide(topic, topic, continuation_of=e._working_id), block)
            await e._open(spec, SlideMeta(frame), exempt=True)
            e._working_id = spec.id
            return spec.id
        img = image_of(target)
        new = with_simulation(target, block)
        if (img is not None and img.origin == "teacher") or not fits(new):
            nxt = with_simulation(await e._next_part(target, frame), block)
            await e._open(nxt, SlideMeta(frame), exempt=True)
            e._working_id = nxt.id
            log.info("[SIM] no room beside %r: part %s holds the simulation", target.title, nxt.part)
            return nxt.id
        await e._commit(new)
        return target.id

    async def _take_off(self, block_id: str) -> None:
        spec, b = self._block(block_id)
        if spec is None:
            return
        rest = without_simulation(spec)
        if rest.blocks:
            await self.e._commit(rest)
        elif self.e._in_deck(spec.id):
            await self.e.deck.remove(spec.id)  # a part that held only the simulation
        else:
            self.e._pending = [p for p in self.e._pending if p.id != spec.id]

    async def _move(self, block_id: str, target: SlideSpec, frame: Frame) -> None:
        spec, b = self._block(block_id)
        if b is None or spec is None or spec.id == target.id or sim_of(target) is not None:
            return
        await self._take_off(block_id)
        target = self.e._spec(target.id) or target
        self.where[block_id] = await self._place(b, target, frame)
        if self.open is not None and self.open.block_id == block_id:
            self.open.slide_id = self.where[block_id]
        log.info("[SIM] %s follows the explanation to %r", b.sim.template, target.title)

    # ---- values -------------------------------------------------------------------------------------------------
    async def _values(self, sim: SimBase, heard: dict[str, dict[str, Any]], slide_id: str
                      ) -> list[tuple[str, Any, str]]:
        """Heard values -> (slot, value, source) for this template. A slot the teacher set is final; a value out of
        range is not used and /control says so."""
        t = registry.template_of(sim)
        by_kind = {s.kind: s for s in t.slots}
        out: list[tuple[str, Any, str]] = []
        for kind, h in heard.items():
            if kind == "rough":
                if "mu" in type(sim.params).model_fields and sim.param_source.get("mu", "default") == "default" \
                        and sim.params.mu == 0:  # type: ignore[attr-defined]
                    out.append(("mu", ROUGH_MU, "default"))
                continue
            if kind == "force_dir":
                if "applied_dir" in type(sim.params).model_fields and sim.param_source.get("applied_dir") != "teacher":
                    out.append(("applied_dir", h.get("text") or "up", "said"))
                continue
            slot = by_kind.get(kind)
            if slot is None:
                continue
            if sim.param_source.get(slot.name) == "teacher":
                log.info("[SIM] heard %s, but the teacher set %s: kept", h.get("said"), slot.label)
                continue
            v = float(h.get("value", 0.0))
            if not slot.lo <= v <= slot.hi:
                unit = slot.unit if slot.unit in ("°", "") else f" {slot.unit}"
                msg = (f"Heard “{h.get('said', '')}” - not used ({slot.symbol} {fmt(slot.lo)}–{fmt(slot.hi)}{unit})")
                log.info("[SIM] %s", msg)
                await self.e.bus.publish(SimulationNotice(slide_id=slide_id, text=msg))
                continue
            out.append((slot.name, v, "said"))
        return out

    # ---- intents --------------------------------------------------------------------------------------------
    async def on_signal(self) -> None:
        if self.open is not None:
            self.open.quiet += 1

    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "simulation":
            return
        target, frame = self._target()
        topic = frame.topic if frame is not None else self._lecture_topic()
        o = self.open
        if o is not None and (o.quiet > LISTEN_LINES or not titles_match(o.topic, topic)
                              or self._block(o.block_id)[1] is None):
            log.info("[SIM] %s stops listening (%s)", o.template,
                     "quiet" if o.quiet > LISTEN_LINES else "new topic" if not titles_match(o.topic, topic) else "gone")
            self.open = o = None
        tid = ev.template or (o.template if o is not None else "")
        if tid and registry.get(tid) is None:
            log.warning("[SIM] unknown template %r", tid)
            return
        earlier = self._find(topic, tid) if tid and o is None else None
        action = decide(tid, ev.strength, open_template=o.template if o is not None else None,
                        earlier=earlier is not None, removed=bool(tid) and self._is_removed(topic, tid),
                        setting=self.e.s.simulations)  # type: ignore[arg-type]
        log.info("[SIM] %s %s: %s (%s)", ev.strength, tid or "-", action.kind, action.reason)
        if action.kind == "ignore":
            return
        self.e.stats.ops[f"sim_{action.kind}"] += 1
        if action.kind == "show":
            sim = registry.build(tid, origin="cue")
            block = SimulationBlock(sim=sim)
            self.revealed[block.id] = set(ev.reveal)
            sim = registry.with_values(sim, await self._values(sim, ev.values, target.id if target else ""),
                                       self._toggles(block.id))
            block = block.model_copy(update={"sim": sim})
            self.where[block.id] = await self._place(block, target, frame)
            self._anchor(block)
            self.by_topic[self._key(topic, tid)] = block.id
            self.open = OpenSim(block.id, self.where[block.id], topic, tid)
            log.info("[SIM] shown: %s on %r", sim.title, self.e._spec(self.where[block.id]).title)  # type: ignore[union-attr]
            return
        bid = earlier if action.kind == "reopen" else o.block_id  # type: ignore[union-attr]
        assert bid is not None
        if action.kind == "reopen":
            self.open = OpenSim(bid, self.where[bid], topic, tid)
        assert self.open is not None
        self.open.quiet = 0
        if target is not None and frame is not None and not self.open.held and _explains(target):
            await self._move(bid, target, frame)
        spec, b = self._block(bid)
        if spec is None or b is None:
            return
        sim = b.sim
        if action.kind == "switch":
            sim = registry.switched(sim, tid, "cue")
            self.open.template = tid
            self.by_topic[self._key(topic, tid)] = bid
            self.toggled.pop(bid, None)
            self.revealed[bid] = set()
        self.revealed.setdefault(bid, set()).update(ev.reveal)
        vals = await self._values(sim, ev.values, spec.id)
        sim = registry.with_values(sim, vals, self._toggles(bid))
        if sim.model_dump(exclude={"version"}) != b.sim.model_dump(exclude={"version"}):
            await self._replace(spec, b, sim)
            log.info("[SIM] %s %s: %s", action.kind, sim.template, {s: v for s, v, _ in vals})

    async def follow(self) -> None:
        """After content was placed: an open simulation goes with the explanation to the slide now being built."""
        o = self.open
        if o is None or o.held:
            return
        target, frame = self._target()
        if target is None or frame is None or target.id == o.slide_id or not titles_match(frame.topic, o.topic):
            return
        if _explains(target):
            await self._move(o.block_id, target, frame)

    # ---- the teacher's commands ---------------------------------------------------------------------------------
    async def on_command(self, kind: str, args: dict) -> None:
        if kind == "sim_show":
            await self._show(str(args.get("template") or ""))
            return
        spec, b = self._on_slide(str(args.get("slide_id") or ""))
        if spec is None or b is None:
            log.warning("%s: no simulation on slide %r", kind, args.get("slide_id"))
            return
        if self.open is not None and self.open.block_id == b.id:
            self.open.held = True
        self.e.stats.ops[f"teacher_{kind}"] += 1
        sim, pb = b.sim, b.sim.playback
        t_now = self.now_t(b)
        if kind == "sim_remove":
            await self._take_off(b.id)
            meta = self.e._meta.get(spec.id)
            topic = meta.frame.topic if meta is not None else self._lecture_topic()
            self.removed.add(self._key(topic, sim.template))
            if self.open is not None and self.open.block_id == b.id:
                self.open = None
            self.where.pop(b.id, None)
            log.info("teacher removed the %s simulation from %r", sim.template, spec.title)
            return
        if kind == "sim_pick":
            tid = str(args.get("template") or "")
            if registry.get(tid) is None or tid == sim.template:
                return
            new = registry.switched(sim, tid, "teacher")
            self.toggled.pop(b.id, None)
            self.revealed[b.id] = set()
            if self.open is not None and self.open.block_id == b.id:
                self.open.template = tid
            meta = self.e._meta.get(spec.id)
            self.by_topic[self._key(meta.frame.topic if meta else self._lecture_topic(), tid)] = b.id
            await self._replace(spec, b, new)
            return
        if kind == "sim_set":
            if "speed" in args:
                speed = _num(args.get("speed"))
                if speed is None or not SPEEDS[0] <= speed <= SPEEDS[-1]:
                    return
                new_pb = pb.model_copy(update={"speed": speed, "t": t_now, "rev": pb.rev + 1})
                await self._replace(spec, b, sim.model_copy(update={"playback": new_pb, "version": sim.version + 1}))
                return
            slot = str(args.get("slot") or "")
            if slot == "applied_dir" and "applied_dir" in type(sim.params).model_fields:
                value: Any = "down" if args.get("value") == "down" else "up"
            else:
                t = registry.template_of(sim)
                v = _num(args.get("value"))
                if slot not in t.slot_map or v is None or not t.slot(slot).lo <= v <= t.slot(slot).hi:
                    log.warning("sim_set: bad slot / value %r = %r", slot, args.get("value"))
                    return
                value = v
            try:
                new = registry.with_values(sim, [(slot, value, "teacher")], self._toggles(b.id))
            except (ValidationError, ValueError) as err:
                log.warning("sim_set refused: %s", err)
                return
            await self._replace(spec, b, new)
            return
        if kind == "sim_toggle":
            el = str(args.get("element") or "")
            if el not in type(sim).ELEMENTS:
                return
            on = args.get("on")
            on = (el not in sim.shown) if on is None else bool(on)
            self.toggled.setdefault(b.id, {})[el] = on
            await self._replace(spec, b, registry.solved(sim, self._toggles(b.id)))
            return
        update: Optional[dict[str, Any]] = None
        if kind == "sim_play" and pb.state != "playing":
            update = {"state": "playing", "t": t_now}
        elif kind == "sim_pause" and pb.state == "playing":
            update = {"state": "paused", "t": t_now}
        elif kind == "sim_step":
            update = {"state": "paused", "t": t_now + STEP_S}
        elif kind == "sim_reset":
            update = {"t": 0.0}
        if update is not None:
            new_pb = pb.model_copy(update={**update, "rev": pb.rev + 1})
            await self._replace(spec, b, sim.model_copy(update={"playback": new_pb, "version": sim.version + 1}))

    async def _show(self, tid: str) -> None:
        """/control Simulation: the template on the live slide (or switch the one it has)."""
        e = self.e
        live = e.deck.live
        meta = e._meta.get(live.id) if live is not None else None
        if registry.get(tid) is None:
            log.warning("sim_show: unknown template %r", tid)
            return
        if live is not None and sim_of(live) is not None:
            await self.on_command("sim_pick", {"slide_id": live.id, "template": tid})
            return
        frame = meta.frame if meta is not None and not meta.is_title else None
        block = SimulationBlock(sim=registry.build(tid, origin="teacher"))
        slide_id = await self._place(block, live if frame is not None else None, frame)
        self.where[block.id] = slide_id
        self._anchor(block)
        topic = frame.topic if frame is not None else self._lecture_topic()
        self.by_topic[self._key(topic, tid)] = block.id
        self.removed.discard(self._key(topic, tid))
        self.open = OpenSim(block.id, slide_id, topic, tid, held=True)
        e.stats.ops["teacher_sim_show"] += 1
        log.info("teacher sim_show %s", tid)


def _explains(spec: SlideSpec) -> bool:
    """A slide the open simulation may move to: one with some content. A slide with only a title is not where the
    explanation is (incline_live run: "Let's see what happens" opened an announced slide 'What happens' with nothing on
    it, and the points went on on the slide the simulation was on)."""
    return any(t.strip() for t in element_texts(spec).values())


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None
