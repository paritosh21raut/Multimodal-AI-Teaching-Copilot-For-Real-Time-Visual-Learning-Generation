"""The presentation engine's Concept Simulation part (F-014). Called by PresentationEngine under its lock; the engine
stays the only writer of the deck.

    RepresentationIntent -> simulation.policy -> show / suggest / switch / update / end
    teacher commands     -> sim_show / sim_set / sim_play / sim_pause / sim_step / sim_reset / sim_toggle / sim_pick /
                            sim_remove / sim_end / sim_accept / sim_dismiss (sim_full is a display flag: the Deck)

Simulation mode (S1, user 2026-10-17: slides made from the talk during a simulation were unwanted):
- It starts when a simulation is shown (spoken cue, the dock's Simulation, an accepted Suggest chip): the simulation
  gets a slide of its own (only the stage, titled by the template, under the topic's crumb). Every new use makes a
  new simulation slide; an old one is never reused. A switch ("imagine it on an incline") stays on that slide.
- While it is on the engine makes no new slides and changes no content slide: the interpretations still run, their
  pieces are collected (`collect`). Values and setup lines keep updating the simulation.
- It ends on "let's get back to the slides" / "end the simulation" (detector, end cue), Back to slides in /control
  (`sim_end`), removing the simulation, an announced new topic, the teacher's New slide, the lecture's end, or
  SAFETY_S without a word about the simulation (a /control notice says so).
- Then slides resume: first the recap of what was taught meanwhile (presentation.recap: key points, rules,
  definitions, formulas, conclusions; parameter talk dropped), in parts when it is long; nothing worth keeping -> no
  recap slide. Logged (SimulationModeChanged, the event log) and on the Deck (`sim_mode`, so /control shows
  "Simulation running" whichever slide is on screen).

Clock: the server keeps where the motion is (Playback.t at the anchor + the time since, at Playback.speed) so pause
and step give every page the same frame; a change of values never touches the clock (the clients tween to the new
values and keep running).
"""
from __future__ import annotations

import dataclasses

import logging
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from pydantic import ValidationError

from copilot.core.events import (
    InterpretationReady, RepresentationIntent, SimulationModeChanged, SimulationNotice, SimulationSuggestion,
)
from copilot.core.memory import titles_match
from copilot.presentation.composer import frame_slide, sim_of, with_simulation
from copilot.presentation.content import Piece
from copilot.presentation.planner import Frame
from copilot.presentation.recap import recap_pieces
from copilot.presentation.spec import SimulationBlock, SlideSpec
from copilot.simulation import registry
from copilot.simulation.base import SimBase, fmt, known
from copilot.simulation.policy import decide
from copilot.simulation.values import resolve

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

STEP_S = 0.25        # simulation seconds per Step
ROUGH_MU = 0.3       # "a rough surface", value not said: friction is drawn with this (never printed)
SPEEDS = (0.25, 0.5, 1.0, 1.5, 2.0)
SAFETY_S = 180.0     # simulation mode ends after this long (lecture time) without a word about the simulation
SUGGEST_S = 30.0     # a Suggest chip stays this long
RECAP_PREFIX = "Recap: "


@dataclass
class SimMode:
    """A running simulation mode: the simulation's own slide and what was taught meanwhile."""
    block_id: str
    slide_id: str
    template: str
    frame: Frame                       # the lecture's topic (the crumb of the simulation and recap slides)
    before_id: Optional[str]           # the working slide when it started (content said before the cue goes there)
    start_seq: int                     # arrival number of the cue line (engine._seg_order)
    heard_at: float                    # lecture time of the last word about the simulation
    names: list[str] = field(default_factory=list)   # template names shown (a switch adds one)
    collected: list[Piece] = field(default_factory=list)
    last: Optional[str] = None         # the slot changed or mentioned last (a bare number goes there)
    origin: str = "cue"


@dataclass
class Ended:
    """The last simulation mode, for interpretations that arrive after it ended (the model answers seconds later):
    their lines said during the simulation join its recap."""
    start_seq: int
    end_seq: int
    frame: Frame
    name: str
    slide_id: str
    recap_last: Optional[str]


@dataclass
class Suggestion:
    id: str
    template: str
    lines: list[str]                   # the line that suggested it (its values are used on Show)
    until: float


@dataclass
class _Clock:
    at: float = 0.0     # server clock when Playback.t was last set
    t: float = 0.0


@dataclass
class SimulationController:
    e: "PresentationEngine"
    mode: Optional[SimMode] = None
    where: dict[str, str] = field(default_factory=dict)            # block id -> slide id
    toggled: dict[str, dict[str, bool]] = field(default_factory=dict)  # block id -> the teacher's element choices
    revealed: dict[str, set[str]] = field(default_factory=dict)    # block id -> elements the teacher named
    clocks: dict[str, _Clock] = field(default_factory=dict)
    removed: set[tuple[str, str]] = field(default_factory=set)     # (topic, template) the teacher removed
    setups: dict[tuple[str, str], int] = field(default_factory=dict)  # (topic, template) -> setups heard, none open
    suggestion: Optional[Suggestion] = None
    ended: Optional[Ended] = None
    shown: int = 0                                                 # simulation slides made in this lecture

    @property
    def collecting(self) -> bool:
        return self.mode is not None

    # ---- lookup ---------------------------------------------------------------------------------------------
    def _block(self, block_id: str) -> tuple[Optional[SlideSpec], Optional[SimulationBlock]]:
        spec = self.e._spec(self.where.get(block_id, ""))
        b = sim_of(spec) if spec is not None else None
        return (spec, b) if b is not None and b.id == block_id else (None, None)

    def _on_slide(self, slide_id: str) -> tuple[Optional[SlideSpec], Optional[SimulationBlock]]:
        spec = self.e._spec(slide_id)
        return (spec, sim_of(spec)) if spec is not None else (None, None)

    def _topic_frame(self) -> Frame:
        """The topic the lecture is on (the working slide's, else the store's): the simulation slide's crumb."""
        meta = self.e._meta.get(self.e._working_id or "")
        if meta is not None and not meta.is_title:
            return Frame(meta.frame.topic, meta.frame.topic)
        snap = self.e.store.snapshot()
        topic = snap.topic(snap.current_topic_id)
        name = (topic.title if topic is not None else "") or snap.setup.expected_topic or "Simulation"
        return Frame(name, name)

    @staticmethod
    def _key(topic: str, template: str) -> tuple[str, str]:
        return " ".join(topic.lower().split()), template

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
    async def _replace(self, spec: SlideSpec, b: SimulationBlock, sim: SimBase, title: Optional[str] = None
                       ) -> SimulationBlock:
        new = b.model_copy(update={"sim": sim})
        upd: dict[str, Any] = {"blocks": [new if x.id == b.id else x for x in spec.blocks]}
        if title and spec.id not in self.e._teacher_titles:
            upd["title"] = title
        await self.e._commit(spec.model_copy(update=upd))
        if sim.playback.rev != b.sim.playback.rev:
            self._anchor(new)
        return new

    async def _take_off(self, block_id: str) -> None:
        spec, b = self._block(block_id)
        if spec is None:
            return
        rest = spec.model_copy(update={"blocks": [x for x in spec.blocks if x.type != "simulation"]})
        if rest.blocks:
            from copilot.presentation.composer import without_simulation
            await self.e._commit(without_simulation(spec))
        elif self.e._in_deck(spec.id):
            await self.e.deck.remove(spec.id)  # the simulation's own slide
            self.e._meta.pop(spec.id, None)
        else:
            self.e._pending = [p for p in self.e._pending if p.id != spec.id]

    # ---- values -------------------------------------------------------------------------------------------------
    async def _values(self, sim: SimBase, lines: list[str], slide_id: str) -> list[tuple[str, Any, str]]:
        """What the lines say for this template -> (slot, value, source). A slot the teacher set is final; a value out
        of range is not used and /control says so. Updates the mode's last slot (the next bare number's)."""
        t = registry.template_of(sim)
        fields = type(sim.params).model_fields
        out: list[tuple[str, Any, str]] = []
        last = self.mode.last if self.mode is not None else None
        for line in lines:
            # current values for "double it" / "increase it by 10": only those said (or standard): doubling a
            # default nobody said would print it as said (pendulum check 2026-10-17)
            params = {s.name: float(getattr(sim.params, s.name)) for s in t.slots
                      if known(sim.param_source, t.slot_map, s.name)}
            for slot, v, _ in out:  # a second line builds on the first ("double it" after "make it 10")
                if isinstance(v, (int, float)) and slot in params:
                    params[slot] = float(v)
            friction = "friction" in sim.shown or last == "mu" or getattr(sim.params, "mu", 0) > 0
            r = resolve(t, line, last, friction_context=friction, params=params)
            if r.why:
                log.info("[SIM] %r -> %s", line[:80], "; ".join(r.why))
            last = r.last or last
            if r.rough and "mu" in fields and sim.param_source.get("mu", "default") == "default" \
                    and sim.params.mu == 0:  # type: ignore[attr-defined]
                out.append(("mu", ROUGH_MU, "default"))
            for role, name, words in t.force_dirs:  # S2: each force's direction (up the slope, against the motion)
                value = words.get(r.dirs.get(role, ""))
                if value and name in fields and sim.param_source.get(name) != "teacher":
                    out = [x for x in out if x[0] != name] + [(name, value, "said")]
            for name, value in r.mentioned:  # "from a cliff": drawn, its number unknown
                if sim.param_source.get(name) not in ("said", "teacher") and name not in {x[0] for x in out}:
                    out.append((name, value, "mentioned"))
            for name, value in r.choices.items():  # "in parallel": the circuit's arrangement
                if name in fields and sim.param_source.get(name) != "teacher":
                    out = [x for x in out if x[0] != name] + [(name, value, "said")]
            for slot_name, v, said in r.values:
                slot = t.slot(slot_name)
                if sim.param_source.get(slot_name) == "teacher":
                    log.info("[SIM] heard %s, but the teacher set %s: kept", said, slot.label)
                    continue
                if not slot.lo <= v <= slot.hi:
                    unit = slot.unit if slot.unit in ("°", "") else f" {slot.unit}"
                    msg = f"Heard “{said}” - not used ({slot.symbol} {fmt(slot.lo)}–{fmt(slot.hi)}{unit})"
                    log.info("[SIM] %s", msg)
                    await self.e.bus.publish(SimulationNotice(slide_id=slide_id, text=msg))
                    continue
                # S2: a value worked out from another form ("the period is 0.2 s": f) is computed, not said
                out = [x for x in out if x[0] != slot_name] + [(slot_name, v, "computed" if slot_name in r.computed
                                                                else "said")]
        if self.mode is not None:
            self.mode.last = last
        return out

    # ---- intents --------------------------------------------------------------------------------------------
    async def on_signal(self, segment_id: str) -> None:
        """A content line: a word about the open simulation keeps simulation mode alive (SAFETY_S)."""
        m = self.mode
        if m is None:
            return
        t = registry.get(m.template)
        text = self.e._said.get(segment_id, "")
        if t is not None and text and t.lexicon.search(text):
            m.heard_at = self.e.now()

    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "simulation":
            return
        m = self.mode
        if m is not None and self._block(m.block_id)[1] is None:  # its slide went away (removed by the teacher)
            await self.end("the simulation's slide was removed")
            m = None
        tid = ev.template or (m.template if m is not None else "")
        if tid and registry.get(tid) is None:
            log.warning("[SIM] unknown template %r", tid)
            return
        topic = m.frame.topic if m is not None else self._topic_frame().topic
        repeated = False
        t_ = registry.get(tid) if tid else None
        # a setup counts toward the repeat only with two of the template's own words: "Slope." in a maths lecture or
        # "the windward slope" in geography is not a lecture on the incline (v2_eval test28 / web3, 2026-10-17)
        words = {w.lower() for w in t_.lexicon.findall(ev.text)} if t_ is not None else set()
        if m is None and tid and ev.strength == "setup" and len(words) >= 2:
            k = self._key(topic, tid)
            self.setups[k] = self.setups.get(k, 0) + 1
            repeated = self.setups[k] >= 2
        action = decide(tid, ev.strength, open_template=m.template if m is not None else None,
                        removed=bool(tid) and self._is_removed(topic, tid),
                        setting=self.e.s.simulations, mode_on=m is not None,  # type: ignore[arg-type]
                        repeated=repeated)
        if action.kind == "switch" and ev.strength != "cue" and m is not None:
            open_t = registry.get(m.template)  # "the block is pulled up the slope" fits the open incline too: stay
            if open_t is not None and open_t.setup.search(ev.text):
                action = dataclasses.replace(action, kind="update", reason="fits the open simulation too")
                tid = m.template
        log.info("[SIM] %s %s: %s (%s)", ev.strength, tid or "-", action.kind, action.reason)
        if action.kind == "ignore":
            return
        self.e.stats.ops[f"sim_{action.kind}"] += 1
        if action.kind == "end":
            await self.end(f"heard {ev.text[:60]!r}")
            return
        if action.kind == "suggest":
            await self._suggest(tid, [ev.text])
            return
        if action.kind == "show":
            # "A ball is thrown at 20 m/s at 30 degrees." (a chip) ... "Let me show you": the values said with the
            # setup come along (projectile screenshot 2026-10-17)
            sg = self.suggestion
            lines = (sg.lines if sg is not None and sg.template == tid else []) + [ev.text]
            await self.start(tid, lines, origin="cue", reveal=ev.reveal, cue_segment=next(iter(ev.segment_ids), ""))
            return
        assert m is not None
        m.heard_at = self.e.now()
        spec, b = self._block(m.block_id)
        if spec is None or b is None:
            return
        sim = b.sim
        title = None
        if action.kind == "switch":
            sim = registry.switched(sim, tid, "cue")
            m.template = tid
            m.names.append(sim.title)
            title = sim.title
            self.toggled.pop(b.id, None)
            self.revealed[b.id] = set()
        self.revealed.setdefault(b.id, set()).update(ev.reveal)
        vals = await self._values(sim, [ev.text], spec.id)
        sim = registry.with_values(sim, vals, self._toggles(b.id))
        if sim.model_dump(exclude={"version"}) != b.sim.model_dump(exclude={"version"}):
            await self._replace(spec, b, sim, title)
            log.info("[SIM] %s %s: %s", action.kind, sim.template, {s: v for s, v, _ in vals})

    # ---- simulation mode ------------------------------------------------------------------------------------
    async def start(self, tid: str, lines: list[str], *, origin: str, reveal: Optional[list[str]] = None,
                    cue_segment: str = "") -> None:
        """Simulation mode: the simulation on a new slide of its own; the slides wait until it ends."""
        e = self.e
        if self.mode is not None:
            await self.end("another simulation was started")
        self.ended = None
        await self._clear_suggestion()
        while e._pending:  # slides waiting for the dwell time go first: the simulation comes after them
            await e._add_to_deck(e._pending.pop(0))
        if e._prov:
            await e._clear_provisional()
        await e._drop_cue(keep_working=True)
        frame = self._topic_frame()
        sim = registry.build(tid, origin=origin)  # type: ignore[arg-type]
        block = SimulationBlock(sim=sim)
        self.revealed[block.id] = set(reveal or ())
        mode = SimMode(block.id, "", tid, frame, e._working_id,
                       e._seg_order.get(cue_segment, e._seg_n + 1), e.now(), [sim.title], origin=origin)
        self.mode = mode
        sim = registry.with_values(sim, await self._values(sim, [x for x in lines if x], ""), self._toggles(block.id))
        block = block.model_copy(update={"sim": sim})
        spec = with_simulation(frame_slide(frame.topic, sim.title, continuation_of=e._working_id), block)
        spec = spec.model_copy(update={"title": sim.title})
        from copilot.presentation.engine import SlideMeta  # the engine imports this module

        await e._open(spec, SlideMeta(Frame(frame.topic, sim.title), is_title=True), exempt=True)
        e._working_id = spec.id
        mode.slide_id = spec.id
        self.where[block.id] = spec.id
        self._anchor(block)
        self.removed.discard(self._key(frame.topic, tid))
        self.shown += 1
        await e.deck.set_sim_mode(spec.id)
        await e.bus.publish(SimulationModeChanged(on=True, slide_id=spec.id, template=tid,
                                                  reason="spoken cue" if origin == "cue" else origin))
        log.info("[SIM] simulation mode on: %s on its own slide (%s)", sim.title, origin)

    def split_early(self, ev: InterpretationReady, pieces: list[Piece]) -> tuple[list[Piece], list[Piece]]:
        """Pieces of lines said before the simulation's cue (they belong on the slide before it) and the rest."""
        m = self.mode
        assert m is not None
        early, later = [], []
        for p in pieces:
            seqs = [self.e._seg_order.get(ev.segment_ids[i - 1], 10 ** 9) for i in p.lines
                    if 0 < i <= len(ev.segment_ids)]
            (early if seqs and max(seqs) < m.start_seq else later).append(p)
        return early, later

    def collect(self, pieces: list[Piece]) -> None:
        if self.mode is not None:
            self.mode.collected.extend(pieces)
            log.info("[SIM] simulation mode: %d piece(s) collected for the recap (%d so far)", len(pieces),
                     len(self.mode.collected))

    async def end(self, reason: str) -> list[str]:
        """Slides resume: the recap first (if anything worth keeping was said). Returns the recap slide ids."""
        m, self.mode = self.mode, None
        if m is None:
            return []
        e = self.e
        await e.deck.set_sim_mode(None)
        kept, dropped = recap_pieces(m.collected)
        ids: list[str] = []
        name = m.names[-1] if m.names else "Simulation"
        last: Optional[str] = None
        if kept:
            frame = Frame(m.frame.topic, RECAP_PREFIX + name)
            spec = frame_slide(frame.topic, frame.facet, continuation_of=m.slide_id)
            spec = spec.model_copy(update={"title": RECAP_PREFIX + name})
            before = {s.id for s in e.deck.slides} | {p.id for p in e._pending}
            last = await e._place(spec, True, frame, kept, exempt=True)
            ids = [s.id for s in e.deck.slides if s.id not in before] + [p.id for p in e._pending if p.id not in before]
            e._working_id = last
        else:
            e._working_id = m.before_id if e._spec(m.before_id) is not None else None
        self.ended = Ended(m.start_seq, e._seg_n + 1, m.frame, name, m.slide_id, last)
        items = sum(max(1, len(p.texts) + len(p.pairs)) for p in kept)
        await e.bus.publish(SimulationModeChanged(on=False, slide_id=m.slide_id, template=m.template, reason=reason,
                                                  recap_ids=ids, kept=items, dropped=dropped))
        log.info("[SIM] simulation mode off (%s): recap %s (%d kept, %d dropped as parameter talk)", reason,
                 f"{len(ids)} slide(s)" if ids else "none", items, dropped)
        return ids

    async def take_late(self, ev: InterpretationReady, pieces: list[Piece]) -> list[Piece]:
        """Pieces of lines said during the last simulation that arrive after it ended go to its recap (kept as the
        recap keeps them); the rest is returned for the slides."""
        x = self.ended
        if x is None or not pieces:
            return pieces
        late, rest = [], []
        for p in pieces:
            seqs = [self.e._seg_order.get(ev.segment_ids[i - 1], -1) for i in p.lines if 0 < i <= len(ev.segment_ids)]
            (late if seqs and x.start_seq <= max(seqs) < x.end_seq else rest).append(p)
        if not late:
            return pieces
        kept, dropped = recap_pieces(late)
        if kept:
            e = self.e
            frame = Frame(x.frame.topic, RECAP_PREFIX + x.name)
            spec = e._spec(x.recap_last)
            if spec is None:
                spec = frame_slide(frame.topic, frame.facet, continuation_of=x.slide_id)
                spec = spec.model_copy(update={"title": RECAP_PREFIX + x.name})
                x.recap_last = await e._place(spec, True, frame, kept, exempt=True, adopt=False)
            else:
                x.recap_last = await e._place(spec, False, frame, kept, adopt=False)
        log.info("[SIM] %d late piece(s) of the simulation: %d to its recap, %d dropped", len(late), len(kept), dropped)
        return rest

    async def tick(self) -> None:
        """Ticker: a forgotten simulation ends after SAFETY_S; a Suggest chip expires."""
        now = self.e.now()
        if self.mode is not None and now - self.mode.heard_at > SAFETY_S:
            await self.end(f"{int(SAFETY_S // 60)} min without a word about the simulation")
            await self.e.bus.publish(SimulationNotice(  # "" = whichever slide /control shows
                slide_id="", text=f"Back to slides: nothing about the simulation for {int(SAFETY_S // 60)} min"))
        if self.suggestion is not None and now > self.suggestion.until:
            await self._clear_suggestion()

    async def _suggest(self, tid: str, lines: list[str]) -> None:
        t = registry.get(tid)
        if t is None:
            return
        if self.suggestion is not None and self.suggestion.template == tid:
            self.suggestion.lines += lines
            self.suggestion.until = self.e.now() + SUGGEST_S
            return
        await self._clear_suggestion()
        self.suggestion = Suggestion(uuid.uuid4().hex[:12], tid, list(lines), self.e.now() + SUGGEST_S)
        await self.e.bus.publish(SimulationSuggestion(id=self.suggestion.id, template=tid, name=t.name,
                                                      text=(lines[-1] if lines else "")[:200]))
        log.info("[SIM] suggested: %s", t.name)

    async def _clear_suggestion(self) -> None:
        s, self.suggestion = self.suggestion, None
        if s is not None:
            await self.e.bus.publish(SimulationSuggestion(id=s.id, template=s.template, active=False))

    # ---- the teacher's commands ---------------------------------------------------------------------------------
    async def on_command(self, kind: str, args: dict) -> None:
        if kind == "sim_show":
            await self._show(str(args.get("template") or ""))
            return
        if kind == "sim_end":
            self.e.stats.ops["teacher_sim_end"] += 1
            await self.end("Back to slides")
            return
        if kind in ("sim_accept", "sim_dismiss"):
            s = self.suggestion
            if s is None or (args.get("id") and args.get("id") != s.id):
                return
            if kind == "sim_dismiss":
                await self._clear_suggestion()
                return
            self.e.stats.ops["teacher_sim_accept"] += 1
            await self.start(s.template, s.lines, origin="policy")
            return
        spec, b = self._on_slide(str(args.get("slide_id") or ""))
        if spec is None or b is None:
            log.warning("%s: no simulation on slide %r", kind, args.get("slide_id"))
            return
        self.e.stats.ops[f"teacher_{kind}"] += 1
        sim, pb = b.sim, b.sim.playback
        t_now = self.now_t(b)
        if self.mode is not None and self.mode.block_id == b.id:
            self.mode.heard_at = self.e.now()  # the teacher is using it
        if kind == "sim_remove":
            mine = self.mode is not None and self.mode.block_id == b.id
            meta = self.e._meta.get(spec.id)
            topic = meta.frame.topic if meta is not None else self._topic_frame().topic
            self.removed.add(self._key(topic, sim.template))
            if mine:
                await self.end("the teacher removed the simulation")
            await self._take_off(b.id)
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
            if self.mode is not None and self.mode.block_id == b.id:
                self.mode.template = tid
                self.mode.names.append(new.title)
            await self._replace(spec, b, new, new.title if spec.title == sim.title else None)
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
            fields = type(sim.params).model_fields
            if slot in fields and slot not in registry.template_of(sim).slot_map:  # a choice (direction, circuit kind)
                value: Any = str(args.get("value") or "")  # the params model refuses a value outside its Literal
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
        """/control Simulation: the running simulation becomes this template, else simulation mode starts with it."""
        if registry.get(tid) is None:
            log.warning("sim_show: unknown template %r", tid)
            return
        self.e.stats.ops["teacher_sim_show"] += 1
        m = self.mode
        if m is not None and self._block(m.block_id)[1] is not None:
            await self.on_command("sim_pick", {"slide_id": m.slide_id, "template": tid})
            return
        await self.start(tid, [], origin="teacher")
        log.info("teacher sim_show %s", tid)


def _num(v: Any) -> Optional[float]:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None
