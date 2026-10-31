"""The presentation engine's explainer-stage part (F-017 E3). Called by PresentationEngine under its lock; the engine
stays the only writer of the deck.

    RepresentationIntent(scene) cue  -> a motion / picture cue (scene.detector: world motion or canvas, or the
                                        listener "imagine you are ..."): the stage on its own slide (simulation mode:
                                        slides pause, one recap when it ends); geometry / plot cues stay F-015 scenes
    RepresentationIntent(scene) edit -> each line while the stage is open
    Imagine Mode (/control Imagine / End) -> the whole slide is the stage at once; every picturable line is drawn
                                        until End (F-016 §2 gating, kept)

Per line (contract stage-spec §1–8):
    fast path (stage.fastpath, 0 tokens) -> event log (src fast, ghosted) -> fold -> timeline -> the slide, at once
    LLM delta (stage.director_llm, one call per line, in order) -> event log (src llm: replaces that line's drafts)
                                        -> fold -> timeline -> the slide; no LLM / every model failing: the draft stays

Teacher commands (/control; the UI only sends them): stage_pin {id} (never dimmed), stage_undo (the last line's
events are undone by compensating events), stage_fix {id, w} (a `set` op from the teacher), stage_freeze {on}
(speech does not change the stage), stage_focus {id} (a `frame` op), sim_remove, imagine_mode, sim_end (shared).

When the mode ends the stage block turns `still`: the slide keeps its last frame as the figure (the recap follows).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from copilot.core.events import RepresentationIntent, SimulationNotice, StageWords
from copilot.diagram import fastpath as dfast
from copilot.diagram import patch as dpatch
from copilot.diagram.graph import DiagramLog
from copilot.diagram.route import route as diagram_route
from copilot.presentation.spec import SlideSpec, StageBlock
from copilot.scene import pictures as pics
from copilot.scene import safety
from copilot.scene.detector import cue as cue_world
from copilot.stage import director, fastpath, lookup, timeline
from copilot.stage.log import EventLog

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

IMAGINE_TITLE = "Imagine"
STAGE_WORLDS = ("motion", "canvas")   # cue worlds the stage draws (geometry / plot: F-015 scenes)
NOUNS_FOR_STT = 10                     # Whisper's prompt: the slide title + the last scene nouns
QUEUE_MAX = 3                          # lines waiting for the LLM at most (older ones keep their draft)
EMPTY_S = 20.0                         # a stage that drew nothing closes after this long (test34: 107 s "Listening…")
UNSURE_S = 30.0                        # a word Whisper was unsure of stays ghosted (with its chip) this long at most


@dataclass
class StageStats:
    lines: int = 0
    calls: int = 0
    tokens: int = 0
    counted: int = 0                  # tokens minus the cached prefix
    failed: int = 0
    draft_s: list[float] = field(default_factory=list)   # line arrival -> draft patch committed
    full_s: list[float] = field(default_factory=list)    # line arrival -> LLM patch committed
    rungs: dict[int, int] = field(default_factory=dict)  # ladder rung -> entities drawn with it


@dataclass
class _Open:
    block_id: str
    slide_id: str
    log: EventLog = field(default_factory=EventLog)
    patch: Optional[dict] = None
    rev: int = 0
    n: int = 0                          # lines heard
    queue: deque = field(default_factory=deque)  # (line id, text, heard_at, draft ops)
    task: Optional[asyncio.Task] = None
    pinned: set[str] = field(default_factory=set)
    unsure: dict[str, list[str]] = field(default_factory=dict)  # entity id -> the alternatives offered
    unsure_at: dict[str, float] = field(default_factory=dict)   # entity id -> lecture time it was marked unsure
    nouns: list[str] = field(default_factory=list)
    frozen: bool = False
    undone: set[str] = field(default_factory=set)  # line ids the teacher undid (a delta in flight is dropped)
    opened: float = 0.0                 # lecture time the stage opened (an empty one closes after EMPTY_S)
    drew: bool = False                  # it drew something once (an undone stage stays open)
    retitle: bool = True                # a cue's stage takes its title from the scene (Imagine Mode keeps "Imagine")
    mode: str = "stage"                 # F-018: "diagram" draws concept lines as a diagram on this slide
    dlog: DiagramLog = field(default_factory=DiagramLog)
    dpatch: Optional[dict] = None
    dtitle: str = ""                    # the diagram's title (from its first line)

    def drawn(self) -> bool:
        """Something is on the slide (stage entities or diagram parts)."""
        return bool(self.patch and self.patch.get("entities")) or bool(self.dpatch and self.dpatch.get("parts"))


@dataclass
class StageController:
    e: "PresentationEngine"
    director: Any = None                 # stage.director_llm.StageDirector (the app sets it), None: fast path only
    open: Optional[_Open] = None
    imagine: bool = False
    stats: StageStats = field(default_factory=StageStats)
    unsafe: int = 0

    # ---- lookup ---------------------------------------------------------------------------------------------
    def _live(self) -> Optional[_Open]:
        m = self.e._sims.mode
        o = self.open
        if o is None or m is None or m.kind != "stage" or m.block_id != o.block_id:
            return None
        return o

    def _block(self, slide_id: str) -> tuple[Optional[SlideSpec], Optional[StageBlock]]:
        spec = self.e._spec(slide_id)
        b = next((x for x in spec.blocks if x.type == "stage"), None) if spec is not None else None
        return spec, b  # type: ignore[return-value]

    def owns(self, kind: str, args: dict) -> bool:
        if kind.startswith("stage_"):
            return True
        return self._block(str(args.get("slide_id") or ""))[1] is not None

    def wants(self, ev: RepresentationIntent) -> bool:
        """This intent is the stage's (the F-015 scene controller leaves it): Imagine Mode, an open stage's edit, or
        a motion / picture cue."""
        if not self.e.s.stage:
            return False
        if self.imagine:
            return True
        if ev.strength == "edit":
            return self._live() is not None
        if ev.strength != "cue":
            return False
        sc = self.e._scenes
        if self._live() is None and (self.e.s.simulations == "suggest"
                                     or (sc._live() is not None and sc._refers(ev.text))):
            return False  # the Suggest chip, or an edit of the open F-015 scene ("now the cube on the moon")
        world = cue_world(ev.text)
        if world == "diagram" or diagram_route(ev.text) == "diagram":
            return True  # F-018: a concept line is a diagram (also a geometry cue without a measurement: "two circles")
        return world in STAGE_WORLDS or (self._live() is not None and world not in ("geometry", "plot"))

    def about(self, title: str) -> bool:
        o = self._live()
        if o is None:
            return False
        low = title.lower()
        return any(re.search(rf"\b{re.escape(x.w.lower())}(?:e?s)?\b", low) for x in o.log.fold().ents.values())

    # ---- intents --------------------------------------------------------------------------------------------
    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "scene" or not self.e.s.scenes or not self.wants(ev):
            return
        heard = time.perf_counter()
        bad = safety.blocked(ev.text)
        if bad:
            log.info("[STAGE] safety: a line with %r is not drawn", bad)
            return
        if await self._diagram_intent(ev):
            return
        o = self._live()
        if o is None:
            if ev.strength != "cue" and not self.imagine:
                return
            setting = self.e.s.simulations
            if setting == "off" and not self.imagine:
                log.info("[STAGE] cue ignored (setting off): %r", ev.text[:60])
                return
            if not self.imagine and not _drawable(fastpath.draft(ev.text)):
                log.info("[STAGE] cue with nothing to draw: %r opens no stage", ev.text[:60])
                return
            self.e.stats.ops["stage_start"] += 1
            await self.start(origin="cue", title=_title_from(ev.text), cue_segment=next(iter(ev.segment_ids), ""))
            o = self._live()
            if o is None:
                return
        elif o.mode == "diagram":  # a stage line while a diagram is open: the stage on its own slide
            await self.start(origin="cue", title=_title_from(ev.text), cue_segment=next(iter(ev.segment_ids), ""))
            o = self._live()
            if o is None:
                return
        m = self.e._sims.mode
        if m is not None:  # every line heard while the stage is on counts for its recap (also frozen, unpictured)
            m.heard_at = self.e.now()
            m.lines += 1
        if o.frozen:
            log.info("[STAGE] frozen: %r is not drawn", ev.text[:60])
            return
        g = o.log.fold()
        d = fastpath.draft(ev.text, g)
        cue = ev.strength == "cue" or bool(_IMAGINE.match(ev.text))  # "Imagine a kettle ...": no world, still a cue
        if cue and g.ents and not same_scene(d, g) and _drawable(d):
            # "now think of an elephant on a sofa": a new picture, not the open one (F-016 §2: in Imagine Mode the
            # next scene keeps the mode; else the open stage ends with its recap)
            await self.start(origin="cue", title=_title_from(ev.text), cue_segment=next(iter(ev.segment_ids), ""))
            o = self._live()
            if o is None:
                return
            g = o.log.fold()
            d = fastpath.draft(ev.text, g)
        if self.imagine and not d.ops and not d.prefetch and not pics.picturable(ev.text, [x.w for x in g.ents.values()]):
            log.info("[STAGE] imagine: nothing to picture in %r", ev.text[:60])
            return
        m = self.e._sims.mode
        o.n += 1
        self.stats.lines += 1
        line_id = next(iter(ev.segment_ids), "") or f"l{o.n}"
        o.log.say(line_id, ev.text)
        for noun in d.prefetch:
            lookup.ladder().prefetch(noun)
        unsure = [w.lower() for w in getattr(ev, "unsure", []) or []]
        for eid in [i for i in o.unsure if i in d.old and g.ents[i].w.lower() not in unsure]:
            self._sure(o, eid)  # said again, surely this time
        stand_in = _stand_in(d, g)
        if stand_in:  # "imagine you are pushing a box" then "a man pushing a heavy box": the man takes your place
            log.info("[STAGE] %s takes the place of %s", stand_in[1], stand_in[0])
            o.log.delta([{"op": "remove", "id": stand_in[0]}], line_id, "director", int(self.e.now() * 1000))
        if d.ops:
            self._make_room(o, d.ops, line_id)
            o.log.delta(d.ops, line_id, "fast", t_ms=int(self.e.now() * 1000))
            await self._publish(o, unsure=unsure)
            self.stats.draft_s.append(time.perf_counter() - heard)
        o.nouns = (o.nouns + d.nouns)[-NOUNS_FOR_STT:]
        await self._words(o)
        if self.director is not None:
            o.queue.append((line_id, ev.text, heard, d.ops, unsure))
            while len(o.queue) > QUEUE_MAX:
                old = o.queue.popleft()
                log.info("[STAGE] LLM queue full: %r keeps its draft", old[1][:50])
            self._kick(o)

    def _kick(self, o: _Open) -> None:
        if o.task is None or o.task.done():
            o.task = asyncio.create_task(self._drain(o), name="stage:delta")

    async def _drain(self, o: _Open) -> None:
        while o.queue and self._live() is o:
            line_id, text, heard, draft, unsure = o.queue.popleft()
            before = [t for i, t in o.log.lines if i != line_id][-2:]
            g = o.log.fold(skip_fast_of=line_id)
            try:
                res = await self.director.delta(g, before, text, draft)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # every model failed: the draft stays (no fake fallback)
                self.stats.failed += 1
                log.warning("[STAGE] the delta call failed (the draft stays): %s", err)
                if self._live() is o:
                    async with self.e._lock:
                        await self.e.bus.publish(SimulationNotice(slide_id=o.slide_id,
                                                                  text="Stage: the model did not answer"))
                continue
            self.stats.calls += 1
            self.stats.tokens += res.tokens
            self.stats.counted += getattr(res, "counted", res.tokens)
            try:
                await self._land(o, res, line_id, text, heard, draft, unsure)
            except Exception:  # a layout / commit fault: logged, the next lines still go
                log.exception("[STAGE] the delta for %s could not be drawn", line_id)

    async def _land(self, o: _Open, res: Any, line_id: str, text: str, heard: float, draft: list[dict],
                    unsure: list[str]) -> None:
        async with self.e._lock:
            if self._live() is not o or o.frozen or line_id in o.undone or o.mode == "diagram":
                return
            if not res.ops and not draft:
                return
            self._make_room(o, res.ops, line_id, skip_fast_of=line_id)
            d = o.log.delta(res.ops, line_id, "llm", t_ms=int(self.e.now() * 1000))
            if d.dropped == "unsafe":
                self.unsafe += 1
                log.warning("[STAGE] unsafe: the model refused %r", text[:60])
            for rj in d.rejected:
                log.info("[STAGE] stage.rejected %s: %s", rj.raw, rj.reason)
            for raw, _, why in d.repaired:
                log.info("[STAGE] stage.repaired %s: %s", raw, why)
            for op, _ in d.ok:  # the model corrected an unsure word ("not crate, crane"): it is sure now
                if op.op == "set" and op.w and op.id in o.unsure:
                    self._sure(o, op.id)
            await self._publish(o, unsure=unsure)
            self.stats.full_s.append(time.perf_counter() - heard)
            log.info("[STAGE] delta %s: %d op(s), %d refused, %d tokens (%d counted), first op %s, %.2f s",
                     res.entry, len(d.ok), len(d.rejected), res.tokens, getattr(res, "counted", res.tokens),
                     f"{res.first_op_s:.2f} s" if res.first_op_s is not None else "-", time.perf_counter() - heard)

    def _make_room(self, o: _Open, raws: list[dict], line_id: str, skip_fast_of: Optional[str] = None) -> None:
        """At most MAX_ENTITIES visible (F-017 §7): the director's removes go into the log before the line's ops."""
        gone = director.room(o.log.fold(skip_fast_of=skip_fast_of), raws, o.pinned)
        if gone:
            log.info("[STAGE] room for the new line: %s go", ", ".join(r["id"] for r in gone))
            o.log.delta(gone, line_id, "director", int(self.e.now() * 1000))

    # ---- F-018 concept diagrams (diagram mode on the same slide, sim mode and recap) -------------------------------
    async def _diagram_intent(self, ev: RepresentationIntent) -> bool:
        """A concept line (only concept parts, ADR-0013: also with "imagine" / "you") opens a diagram; a follow-up line
        stays on the open diagram ("and you're adding water to it"); a stage line while a diagram is open is left to
        the stage (False). True: the line was the diagram's."""
        o = self._live()
        cue = ev.strength == "cue" or bool(_IMAGINE.match(ev.text))
        dia = cue and diagram_route(ev.text) == "diagram"
        if o is not None and o.frozen:  # the teacher's Freeze: speech changes nothing, opens nothing
            if o.mode != "diagram":
                return False  # the stage's own frozen handling
            self._heard()
            log.info("[STAGE] frozen: %r is not drawn", ev.text[:60])
            return True
        if o is not None and o.mode == "diagram" and not cue:
            if self.imagine and diagram_route(ev.text) is None and _drawable(fastpath.draft(ev.text)) \
                    and not dfast.draft(ev.text, o.dlog.fold()).ops:
                return False  # Imagine Mode: "a dog runs in" is a scene (the stage opens its own slide)
            await self._diagram_line(o, ev)
            return True
        if not dia:
            if o is not None and o.mode == "diagram" and not _drawable(fastpath.draft(ev.text)):
                self._heard()  # "Imagine you are studying": nothing to draw, the diagram stays
                return True
            return False
        if self.e.s.simulations == "off" and not self.imagine:
            log.info("[STAGE] diagram cue ignored (setting off): %r", ev.text[:60])
            return True
        if o is not None and o.mode == "diagram" and _same_diagram(dfast.draft(ev.text, o.dlog.fold())):
            await self._diagram_line(o, ev)  # the same picture said again ("two circles C1 and C2" twice)
            return True
        self.e.stats.ops["diagram_start"] += 1
        d = dfast.draft(ev.text)
        await self.start(origin="cue", title=d.title or IMAGINE_TITLE, cue_segment=next(iter(ev.segment_ids), ""),
                         draw="diagram")
        o = self._live()
        if o is not None:
            await self._diagram_line(o, ev)
        return True

    def _heard(self) -> None:
        m = self.e._sims.mode
        if m is not None:  # every line heard while the diagram is on counts for its recap
            m.heard_at = self.e.now()
            m.lines += 1

    async def _diagram_line(self, o: _Open, ev: RepresentationIntent) -> None:
        heard = time.perf_counter()
        self._heard()
        if o.frozen:
            log.info("[STAGE] frozen: %r is not drawn", ev.text[:60])
            return
        o.n += 1
        self.stats.lines += 1
        line_id = next(iter(ev.segment_ids), "") or f"l{o.n}"
        o.dlog.say(line_id, ev.text)
        d = dfast.draft(ev.text, o.dlog.fold())
        if not o.dtitle and d.title:
            o.dtitle = d.title
        if not d.ops:
            log.info("[STAGE] diagram: nothing new in %r", ev.text[:60])
            return
        res = o.dlog.delta(d.ops, line_id, "fast", t_ms=int(self.e.now() * 1000), text=ev.text)
        for raw, why in res.rejected:
            log.info("[STAGE] diagram.rejected %s: %s", raw, why)
        await self._publish_diagram(o)
        self.stats.draft_s.append(time.perf_counter() - heard)
        log.info("[STAGE] diagram %s: %d op(s), %d refused (fast path, 0 tokens; the LLM delta comes in K5)",
                 line_id, len(res.ok), len(res.rejected))

    async def _publish_diagram(self, o: _Open) -> None:
        spec, b = self._block(o.slide_id)
        if spec is None or b is None:
            return
        title = o.dtitle if o.retitle and o.dtitle and not b.still else spec.title
        if title != spec.title:
            spec = spec.model_copy(update={"title": title})
            m = self.e._sims.mode
            if m is not None and m.kind == "stage" and m.block_id == o.block_id and m.names:
                m.names[-1] = title
        try:
            patch = dpatch.build(o.dlog.fold(), rev=o.rev + 1, nogo=_title_nogo(spec.title) if b.full else None)
        except Exception:  # a layout fault: the last good diagram stays, the log keeps the line
            log.exception("[STAGE] diagram layout failed; the last diagram stays")
            return
        o.rev += 1
        o.dpatch = patch
        o.drew = o.drew or bool(patch["parts"])
        new = b.model_copy(update={"diagram": patch, "mode": "diagram", "patch": {"rev": o.rev, "entities": []},
                                   "frozen": o.frozen, "unsure": []})
        await self.e._commit(spec.model_copy(update={"blocks": [new if x.id == b.id else x for x in spec.blocks]}))

    async def _switch(self, o: _Open, to: str) -> None:
        """The teacher's Diagram | Scene switch: the slide's lines (not the undone ones, not the teacher's fixes) are
        drawn again the other way (0 tokens); a stage LLM delta still in flight is dropped."""
        undone = o.dlog.undone if o.mode == "diagram" else o.undone
        lines = [(i, t) for i, t in (o.dlog.lines if o.mode == "diagram" else o.log.lines)
                 if i not in undone and i != "teacher"]
        self._close_task()
        o.queue.clear()
        o.mode = to
        o.log, o.dlog, o.patch, o.dpatch = EventLog(), DiagramLog(), None, None
        t_ms = int(self.e.now() * 1000)
        for line_id, text in lines:
            if to == "diagram":
                o.dlog.say(line_id, text)
                d = dfast.draft(text, o.dlog.fold())
                o.dtitle = o.dtitle or d.title
                if d.ops:
                    o.dlog.delta(d.ops, line_id, "fast", t_ms, text=text)
            else:
                o.log.say(line_id, text)
                d = fastpath.draft(text, o.log.fold())
                if d.ops:
                    o.log.delta(d.ops, line_id, "fast", t_ms)
        log.info("teacher: the slide is drawn as a %s (%d line(s))", "diagram" if to == "diagram" else "scene", len(lines))
        if to == "diagram":
            await self._publish_diagram(o)
            return
        spec, b = self._block(o.slide_id)
        if spec is not None and b is not None:
            await self.e._commit(spec.model_copy(update={"blocks": [
                b.model_copy(update={"diagram": {}, "mode": "stage"}) if x.id == b.id else x for x in spec.blocks]}))
        await self._publish(o)

    # ---- writing --------------------------------------------------------------------------------------------
    def _graph(self, o: _Open, unsure: list[str] = ()) -> Any:
        g = o.log.fold()
        now = self.e.now()
        for i in [i for i, at in o.unsure_at.items() if now - at > UNSURE_S or i not in g.ents]:
            self._sure(o, i)  # test34: ghosts that never cleared (sofa, bird ...)
        for e in g.ents.values():
            e.pinned = e.id in o.pinned
            if e.w.lower() in unsure or e.id in o.unsure:
                e.ghost = True
                o.unsure.setdefault(e.id, _options(e.w))
                o.unsure_at.setdefault(e.id, now)
        return g

    @staticmethod
    def _sure(o: _Open, eid: str) -> None:
        o.unsure.pop(eid, None)
        o.unsure_at.pop(eid, None)

    async def _publish(self, o: _Open, unsure: list[str] = ()) -> None:
        spec, b = self._block(o.slide_id)
        if spec is None or b is None:
            return
        g = self._graph(o, unsure)
        title = _title_of(g) if o.retitle and not b.still else ""
        if title and title != spec.title:  # the scene's main actor / thing, retitled as the scene grows
            spec = spec.model_copy(update={"title": title})
            m = self.e._sims.mode
            if m is not None and m.kind == "stage" and m.block_id == o.block_id and m.names:
                m.names[-1] = title
        try:
            if not g.visible():  # all of it undone / removed: the empty stage ("Listening…")
                patch = {"rev": o.rev + 1, "entities": [], "overlays": [], "laws": {}}
            else:
                patch = timeline.build(g, o.patch, nogo=_title_nogo(spec.title) if b.full else None, rev=o.rev + 1)
        except Exception:  # a solver / layout fault: the last good patch stays, the log keeps the line
            log.exception("[STAGE] timeline failed; the last patch stays")
            return
        o.rev += 1
        o.patch = patch
        o.drew = o.drew or bool(patch.get("entities"))
        uns = [{"id": i, "w": g.ents[i].w, "options": opts} for i, opts in o.unsure.items() if i in g.ents]
        new = b.model_copy(update={"patch": patch, "unsure": uns, "frozen": o.frozen})
        await self.e._commit(spec.model_copy(update={"blocks": [new if x.id == b.id else x for x in spec.blocks]}))

    async def _words(self, o: _Open) -> None:
        spec, _ = self._block(o.slide_id)
        await self.e.bus.publish(StageWords(title=spec.title if spec is not None else "", nouns=list(o.nouns)))

    async def start(self, *, origin: str, title: str = "", cue_segment: str = "", imagine: bool = False,
                    draw: str = "stage") -> None:
        """The stage on its own slide (simulation mode); in Imagine Mode a cue that starts a new scene keeps the mode."""
        e = self.e
        title = title or IMAGINE_TITLE
        block = StageBlock(full=True)
        m = e._sims.mode
        if self.open is not None:
            await self._retire(self.open)
        if self.imagine and m is not None and m.kind == "stage" and m.imagine:
            m.block_id = block.id
            m.names.append(title)
            mode = m
        else:
            mode = await e._sims.begin("stage", "stage", block.id, title, origin, cue_segment)
            mode.imagine = imagine or self.imagine
        spec = await e._sims.place(mode, block, title, "spoken cue" if origin == "cue" else origin)
        self.open = _Open(block.id, spec.id, opened=e.now(), retitle=not imagine, mode=draw)
        log.info("[STAGE] %s open: %s (%s)", "diagram" if draw == "diagram" else "stage", title, origin)

    def _close_task(self) -> None:
        o = self.open
        if o is not None and o.task is not None and not o.task.done():
            o.task.cancel()

    async def imagine_mode(self, on: bool) -> None:
        e = self.e
        if on == self.imagine:
            return
        self.imagine = on
        await e.deck.set_imagine(on)
        m = e._sims.mode
        if on:
            log.info("teacher: Imagine Mode on (stage)")
            if self._live() is not None and m is not None:
                m.imagine = True
            else:
                await self.start(origin="teacher", title=IMAGINE_TITLE, imagine=True)
            return
        log.info("teacher: Imagine Mode ended")
        if m is not None and m.kind == "stage":
            await e._sims.end("Imagine Mode ended")

    async def tick(self) -> None:
        if self.imagine and (self.e._sims.mode is None or self.e._sims.mode.kind != "stage"):
            self.imagine = False
            await self.e.deck.set_imagine(False)
        o = self.open
        if o is not None and self._live() is None:  # its mode ended
            await self._retire(o)
        elif o is not None and not self.imagine and not o.drew and not o.drawn() \
                and self.e.now() - o.opened > EMPTY_S and not (o.task is not None and not o.task.done()):
            log.info("[STAGE] nothing drawn for %d s: the stage closes", int(EMPTY_S))
            await self.e._sims.end("the stage drew nothing")
            await self._retire(o)

    async def _retire(self, o: _Open) -> None:
        """A stage that ends (its mode ended, or the next scene replaced it): the last frame stays as the slide's
        figure; a stage that drew nothing takes its slide off."""
        self._close_task()
        if self.open is o:
            self.open = None
        spec, b = self._block(o.slide_id)
        if spec is not None and b is not None:
            if not o.drawn():
                log.info("[STAGE] the stage ended before it drew anything: its slide goes")
                await self.e._sims.take_off(spec)
            elif not b.still:
                still = b.model_copy(update={"still": True, "unsure": []})
                await self.e._commit(spec.model_copy(update={"blocks": [still if x.id == b.id else x
                                                                        for x in spec.blocks]}))
        for x in o.log.fold().visible():
            self.stats.rungs[x.rung] = self.stats.rungs.get(x.rung, 0) + 1

    # ---- the teacher's commands -----------------------------------------------------------------------------
    async def on_command(self, kind: str, args: dict) -> None:
        if kind == "imagine_mode":
            await self.imagine_mode(bool(args.get("on")))
            return
        spec, b = self._block(str(args.get("slide_id") or ""))
        o = self._live()
        if spec is None or b is None:
            return
        self.e.stats.ops[f"teacher_{kind}"] += 1
        if kind == "sim_remove":
            m = self.e._sims.mode
            if m is not None and m.kind == "stage" and m.block_id == b.id:
                await self.e._sims.end("the teacher removed the stage")
            await self.e._sims.take_off(spec)
            return
        if o is None or o.slide_id != spec.id:
            return  # an ended stage is a still figure: nothing to change
        m = self.e._sims.mode
        if m is not None:
            m.heard_at = self.e.now()
        eid = str(args.get("id") or "")
        t_ms = int(self.e.now() * 1000)
        if kind == "stage_mode":  # F-018: Diagram | Scene
            to = "diagram" if args.get("to") == "diagram" else "stage"
            if to != o.mode:
                await self._switch(o, to)
            return
        if o.mode == "diagram":
            if kind == "stage_freeze":
                o.frozen = bool(args.get("on", not o.frozen))
                log.info("teacher: diagram %s", "frozen" if o.frozen else "unfrozen")
            elif kind == "stage_undo":
                last = o.dlog.last_line()
                if last is None:
                    return
                o.dlog.undo(last, t_ms)
                log.info("teacher: undo the line %s", last)
            else:
                return  # pin / fix word / focus: the stage's (the diagram's own edits come in K5)
            await self._publish_diagram(o)
            return
        if kind == "stage_pin":
            if eid not in o.log.fold().ents:
                return
            o.pinned.symmetric_difference_update({eid})
        elif kind == "stage_freeze":
            o.frozen = bool(args.get("on", not o.frozen))
            log.info("teacher: stage %s", "frozen" if o.frozen else "unfrozen")
        elif kind == "stage_undo":
            last = next((ev.line_id for ev in reversed(o.log.events)
                         if ev.ok and ev.src != "teacher" and ev.line_id not in o.undone), None)
            if last is None:
                return
            o.undone.add(last)  # a delta for it still in flight is dropped when it lands
            for ev in [x for x in o.log.events if x.ok and x.line_id == last and x.src != "teacher"]:
                o.log.undo(ev.seq, t_ms, last)
            o.queue = deque(q for q in o.queue if q[0] != last)
            log.info("teacher: undo the line %s", last)
        elif kind == "stage_fix":
            w = " ".join(str(args.get("w") or "").split())[:40]
            if not w or eid not in o.log.fold().ents:
                return
            o.log.say("teacher", w)
            d = o.log.delta([{"op": "set", "id": eid, "w": w}], "teacher", "teacher", t_ms)
            if not d.ok:
                log.info("teacher: fix word %r refused: %s", w, [r.reason for r in d.rejected])
                return
            o.unsure.pop(eid, None)
        elif kind == "stage_focus":
            if eid and eid not in o.log.fold().ents:
                return
            o.log.delta([{"op": "frame", "shot": "focus" if eid else "establish", "ids": [eid] if eid else []}],
                        "teacher", "teacher", t_ms)
        else:
            return
        await self._publish(o)


_IMAGINE = re.compile(r"^\W*(?:(?:now|so|and|okay|ok|next),?\s+)?(?:imagine|picture|visuali[sz]e|think of|suppose)(?![a-z])",
                      re.IGNORECASE)


def same_scene(d: fastpath.Draft, g: Any) -> bool:
    """A cue line goes on the open stage (E3b, test34: 51 slides for 75 lines) when it names what is there: a pronoun
    whose antecedent is not in the line ("a dog runs past him"), "the / her <thing on stage>", only things already
    on stage (a repeat or rephrase; "you" alone counts only when nothing new is said), or the same verb on the same
    object ("you push a box" -> "a man pushing a heavy box"). "Imagine a kettle on the stove ... out of it" is a new
    scene."""
    if d.pron or d.definite:
        return True
    if d.old and not d.new:
        return True
    said = {(o["verb"], o.get("obj")) for o in d.ops if o.get("op") == "act" and o.get("obj") in g.ents}
    return any((a.verb, a.obj) in said for a in g.actions.values())


def _same_diagram(d: dfast.Draft) -> bool:
    """A concept cue about the open diagram: it adds nothing new (the same cue said again: "two circles C1 and C2"),
    or refers to it ("imagine the beaker on a burner", "it"); a cue that adds things on its own ("imagine a beaker
    with NaOH" after the HCl one) is the next diagram."""
    return bool(d.old) and not d.new or d.refers


def _drawable(d: fastpath.Draft) -> bool:
    """A cue opens a stage only with a thing to draw besides "you" (test34: "Imagine you are driving a…")."""
    return bool(d.new or d.prefetch or d.old)


def _stand_in(d: fastpath.Draft, g: Any) -> Optional[tuple[str, str]]:
    """(old agent, new agent) when a new person does what another did to the same object and the line does not
    name the old one ("imagine you are pushing a box" -> "a man pushing a heavy box": one pusher, the man)."""
    new_agents = {o["id"] for o in d.ops if o.get("op") == "add" and o.get("kind") == "agent"}
    for o in d.ops:
        if o.get("op") != "act" or o.get("agent") not in new_agents or o.get("obj") not in g.ents:
            continue
        old = next((a.agent for a in g.actions.values() if a.verb == o["verb"] and a.obj == o["obj"]
                    and a.agent in g.ents and g.ents[a.agent].kind == "agent"), None)
        if old is not None and old not in d.old and old not in d.pron:
            return old, o["agent"]
    return None


def _title_nogo(title: str) -> list[list[float]]:
    """The slide title floating over a full-slide stage (slide.css .canvas-head: left 40, top 28, 52 px type, 28 px
    padding) as a box in stage units: the 1600 x 1000 stage fits the 1920 x 1080 slide at 1.08, 96 px in from the left."""
    w = 40 + 56 + 0.56 * 52 * max(6, len(title))
    k, x0 = 1080 / 1000, (1920 - 1600 * 1080 / 1000) / 2
    return [[0.0, 0.0, round(max(0.0, (w - x0) / k) + 12, 1), round((28 + 104) / k + 8, 1)]]


def _options(w: str) -> list[str]:
    """'Did you mean': catalog names close in spelling to an unsure word."""
    import difflib
    return difflib.get_close_matches(w.lower(), list(fastpath.index()), n=3, cutoff=0.6)


_ING = {"put_down": "putting down", "pick_up": "picking up", "look_at": "looking at", "fold_arms": "folding arms",
        "shake_head": "shaking head", "slide_down": "sliding down", "sit": "sitting", "run": "running",
        "swim": "swimming", "jog": "jogging", "chop": "chopping", "nod": "nodding", "shrink": "shrinking",
        "emit": "emitting"}


def _ing(v: str) -> str:
    if v in _ING:
        return _ING[v]
    return (v[:-1] if v.endswith("e") and not v.endswith("ee") else v) + "ing"


def _a(w: str) -> str:
    return ("an " if w[:1].lower() in "aeiou" else "a ") + w


def _title_of(g: Any) -> str:
    """The scene's title from its main actor (E3b, test34: "Imagine", "Boat" for an atom): the first person or animal
    that acts, with its first action on a thing (else its latest): "Man pushing a box", "Throwing a ball" ("you"),
    "Dog running after a cat", "Elephant sitting on a sofa"; else the first thing and where it is ("Box on an inclined
    plane"); "" with nothing drawn. A later actor (the dog running past) does not take the title."""
    vis = g.visible()
    if not vis:
        return ""
    acts = sorted((a for a in g.actions.values() if a.agent in g.ents), key=lambda a: (g.ents[a.agent].added, a.seq))
    lead = next((x.agent for x in acts if g.ents[x.agent].kind in ("agent", "animal")), None) or (
        acts[0].agent if acts else None)
    if lead is not None:
        mine = [x for x in acts if x.agent == lead]
        a = next((x for x in mine if x.obj in g.ents), None) or mine[-1]
        e = g.ents[lead]
        obj = g.ents[a.obj].w if a.obj in g.ents else ""
        verb = _ing(a.verb).replace("_", " ")
        if a.verb == "drive" and obj and catalog_row(g.ents[a.obj]) in ("bicycle", "horse"):
            verb = "riding"
        tail = []
        if obj:
            tail = [{"run": "after", "jog": "after", "walk": "to"}.get(a.verb, ""), _a(obj)]
        elif a.verb == "sit" and g.rel(lead, "sitting_on") and g.rel(lead, "sitting_on").b in g.ents:
            tail = ["on", _a(g.ents[g.rel(lead, "sitting_on").b].w)]
        who = [] if e.w == "you" and tail else ["you" if e.w == "you" else e.w]
        t = " ".join(x for x in who + [verb] + tail if x)
    else:
        e = next((x for x in vis if x.kind in ("agent", "animal") and x.w != "you"), None) or next(
            (x for x in vis if x.w != "you"), vis[0])
        rel = g.rel(e.id)
        t = e.w
        if rel and rel.b in g.ents and rel.kind in ("on", "sitting_on", "in", "under", "near"):
            t += " " + {"sitting_on": "on", "near": "next to"}.get(rel.kind, rel.kind) + " " + _a(g.ents[rel.b].w)
    t = t[:48]
    return t[:1].upper() + t[1:]


def catalog_row(e: Any) -> str:
    return e.draw if not e.draw.startswith(("cast:", "species:", "icon:", "backdrop:")) else e.draw.split(":", 1)[-1]


def _title_from(line: str) -> str:
    """The first stage noun of the cue ("Imagine a man pushing a box" -> "Man"), else "Imagine"; the scene's own
    title replaces it once it draws (_title_of)."""
    d = fastpath.draft(line)
    w = next((o["w"] for o in d.ops if o.get("op") == "add" and o.get("kind") != "place"), "") or (
        d.prefetch[0] if d.prefetch else "")
    return w[:1].upper() + w[1:] if w else IMAGINE_TITLE
