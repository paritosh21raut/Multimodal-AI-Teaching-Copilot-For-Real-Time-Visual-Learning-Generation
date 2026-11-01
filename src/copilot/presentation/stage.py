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
from collections import Counter, deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from copilot.core.events import RepresentationIntent, SimulationNotice, StageWords
from copilot.diagram import extract as dextract
from copilot.diagram import fastpath as dfast
from copilot.diagram import ops as dops
from copilot.diagram import mech as dmech
from copilot.diagram import parts as dparts
from copilot.diagram import patch as dpatch
from copilot.diagram.graph import DiagramLog
from copilot.diagram.route import route as diagram_route
from copilot.diagram.solvers import run as drun
from copilot.diagram.validate import check_delta
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
SHAPE_KINDS = ("circle", "square", "triangle", "rectangle", "pentagon", "hexagon")
REPEAT_S = 60.0                       # M0 (test36: 3 moon slides): a cue naming the open scene's things this soon = it


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
    fbd: str = ""                       # F-019 M2: the free-body view ("" off, "all", a body id)
    dtitle: str = ""                    # the diagram's title (from its first line)
    cues: list[tuple[float, frozenset[str]]] = field(default_factory=list)  # M0: (lecture time, words) of its cues
    dqueue: deque = field(default_factory=deque)  # M3: diagram lines for the LLM (line id, text, heard_at, draft ops)
    dtask: Optional[asyncio.Task] = None

    def drawn(self) -> bool:
        """Something is on the slide (stage entities or diagram parts)."""
        return bool(self.patch and self.patch.get("entities")) or bool(self.dpatch and self.dpatch.get("parts"))


@dataclass
class StageController:
    e: "PresentationEngine"
    director: Any = None                 # stage.director_llm.StageDirector (the app sets it), None: fast path only
    extractor: Any = None                # M3: diagram.extract.Extractor (the app sets it), None: diagram fast path only
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
        fixed = dfast.concept_mishear(ev.text)
        if fixed is not None and diagram_route(fixed) == "diagram":  # M0: "a laptop of sodium" -> an atom of sodium
            log.info("[STAGE] %r read as %r (an element said with an unknown noun)", ev.text[:60], fixed[:60])
            ev = ev.model_copy(update={"text": fixed})
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
        if cue and g.ents and not same_scene(d, g) and _drawable(d) and not self._repeat(o, ev.text):
            # "now think of an elephant on a sofa": a new picture, not the open one (F-016 §2: in Imagine Mode the
            # next scene keeps the mode; else the open stage ends with its recap)
            await self.start(origin="cue", title=_title_from(ev.text), cue_segment=next(iter(ev.segment_ids), ""))
            o = self._live()
            if o is None:
                return
            g = o.log.fold()
            d = fastpath.draft(ev.text, g)
        if cue:
            o.cues.append((self.e.now(), cue_words(ev.text)))
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
        if dia and _FBD.search(ev.text) and not dfast.draft(_FBD_PHRASE.sub(" ", ev.text)).ops:
            dia = False  # M2: "draw the free body diagram" with no mechanics diagram open is no new diagram
        if o is not None and o.frozen:  # the teacher's Freeze: speech changes nothing, opens nothing
            if o.mode != "diagram":
                return False  # the stage's own frozen handling
            self._heard()
            log.info("[STAGE] frozen: %r is not drawn", ev.text[:60])
            return True
        if o is not None and o.mode == "diagram" and self._fbd_line(o, ev.text):
            await self._publish_diagram(o)  # the view turns; the rest of the line (a value, a cue) still goes on
            rest = dfast.draft(_FBD_PHRASE.sub(" ", ev.text), o.dlog.fold())
            if not any(op.get("op") == "qty" for op in rest.ops):  # only a value goes on ("of both blocks" drew
                self._heard()                                       # two more blocks, test42)
                return True
        if o is not None and o.mode == "diagram" and not cue:
            if self.imagine and diagram_route(ev.text) is None and _drawable(fastpath.draft(ev.text)) \
                    and not dfast.draft(ev.text, o.dlog.fold()).ops:
                return False  # Imagine Mode: "a dog runs in" is a scene (the stage opens its own slide)
            dd = dfast.draft(ev.text, o.dlog.fold())
            if _recount(dd, o.dlog.fold().parts) and not any(op.get("op") == "qty" for op in dd.ops):
                self._heard()  # test46: the cue said again as "imaging two masses ..." (no cue) drew two more masses
                log.info("[STAGE] diagram repeat (its things are drawn): %r", ev.text[:60])
                return True
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
        if o is not None and o.mode == "diagram":
            dd = dfast.draft(ev.text, o.dlog.fold())
            # the same picture said again ("two circles C1 and C2" twice, "an atom of" after the sodium atom), or more
            # of it (M0: "another circle of C3", "three circles C1, C2 and C3" with C1 and C2 open)
            # M1: a cue naming only the open diagram's things (no "the" / "it") is the same picture only within
            # REPEAT_S (a Whisper repeat); minutes later "imagine a block on the floor" is the next diagram
            soon = bool(o.cues) and self.e.now() - o.cues[-1][0] <= REPEAT_S
            parts = o.dlog.fold().parts
            ground = bool(dd.old) and not dd.new and all(parts[i].kind == "floor" for i in dd.old if i in parts)
            if soon and _recount(dd, parts):  # test42: a cut cue said again whole ("two blocks, one on top of the
                lines = [i for i, _ in o.dlog.lines if i not in o.dlog.undone]  # other") drew two more blocks
                if len(lines) == 1:  # only the cut cue so far: this one says it all (the stack), drawn instead
                    o.dlog.undo(lines[0], int(self.e.now() * 1000))
                    o.dtitle = ""
                    log.info("[STAGE] diagram repeat redraws the first cue: %r", ev.text[:60])
                    await self._diagram_line(o, ev)
                    return True
                self._heard()  # later: the same things are already there
                o.cues.append((self.e.now(), cue_words(ev.text)))
                log.info("[STAGE] diagram repeat (its things are drawn): %r", ev.text[:60])
                return True
            if dd.refers or _same_diagram(dd) and (soon or ground) or dd.named or dd.more \
                    or self._repeat(o, ev.text, diagram=True):
                await self._diagram_line(o, ev)
                return True
            if self._upgrade(o, dd):  # test37: "a box on an ink-like plane" drew a box; "... inclined plane" says it all
                o.dtitle = ""
                await self._diagram_line(o, ev)
                return True
        self.e.stats.ops["diagram_start"] += 1
        d = dfast.draft(ev.text)
        await self.start(origin="cue", title=d.title or IMAGINE_TITLE, cue_segment=next(iter(ev.segment_ids), ""),
                         draw="diagram")
        o = self._live()
        if o is not None:
            await self._diagram_line(o, ev)
        return True

    def _fbd_line(self, o: _Open, text: str) -> bool:
        """M2: "draw the free body diagram (of the top block)" turns the free-body view on (that body, else all);
        "back to the picture" turns it off. True: the line was that."""
        if _FBD_OFF.search(text) and o.fbd:
            o.fbd = ""
        elif _FBD.search(text):
            g = o.dlog.fold()
            res = drun(g) if dmech.wants(g) else None
            bodies = dmech.free_bodies(g, res, "all")
            if not bodies:  # nothing to draw alone: the line changes nothing (it never opens a "Body" slide)
                log.info("[SIM] free-body view: no body with forces in %r", text[:60])
                return True
            low = _FBD_PHRASE.sub(" ", text.lower())  # review: "a" in "diagram", "b" in "body" named no block
            named = [b for b in bodies if any(re.search(rf"\b{re.escape(w.lower())}\b", low)
                                              for w in (dmech._name(g, b, res), g.parts[b].label) if w)]
            o.fbd = named[0] if len(named) == 1 else "all"
        else:
            return False
        log.info("[SIM] free-body view: %s", o.fbd or "off")
        return True

    def _repeat(self, o: _Open, text: str, diagram: bool = False) -> bool:
        """M0 (test36: 3 moon slides, 2 student slides, "Atom" between two atoms): a cue within REPEAT_S of the open
        scene's last cue that names only its things ("jump on the surface of the moon" after "jump on the moon").
        A stage also keeps a cue that says an earlier cue again with more ("teaching students" -> "in a classroom
        teaching students"); a diagram does not (an atom of oxygen after an atom is the next diagram)."""
        if not o.cues or self.e.now() - o.cues[-1][0] > REPEAT_S:
            return False
        w = cue_words(text)
        if not w:
            return False
        if w <= frozenset().union(*(c for _, c in o.cues)):
            return True
        return not diagram and any(c and c <= w for _, c in o.cues)

    def _upgrade(self, o: _Open, d: dfast.Draft) -> bool:
        """A cue within REPEAT_S that names the open diagram's only part again and adds more: the first cue was cut
        or misheard (test37), this one is the whole picture: the same slide, the new title."""
        parts = o.dlog.fold().parts
        return bool(o.cues) and self.e.now() - o.cues[-1][0] <= REPEAT_S and len(parts) == 1 \
            and next(iter(parts)) in d.old and bool(d.new)

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
        if ev.strength == "cue" or _IMAGINE.match(ev.text):
            o.cues.append((self.e.now(), cue_words(ev.text)))
        line_id = next(iter(ev.segment_ids), "") or f"l{o.n}"
        o.dlog.say(line_id, ev.text)
        d = dfast.draft(ev.text, o.dlog.fold())
        for sym, q in d.unattached:  # F-019 §2: asked, not guessed (which part it belongs to was not said)
            log.info("[SIM] value unattached: %s %r in %r", sym, q, ev.text[:60])
        if not o.dtitle and d.title:
            o.dtitle = d.title
        why = dextract.needs_llm(ev.text, d, cue=ev.strength == "cue") if self.extractor is not None else ""
        if why:  # M3: the fast path left part of the line unread: the LLM reads the whole line (its draft stays meanwhile)
            log.info("[SIM] llm asked for %s (%s): %r", line_id, why, ev.text[:60])
            o.dqueue.append((line_id, ev.text, heard, d.ops))
            while len(o.dqueue) > QUEUE_MAX:
                old = o.dqueue.popleft()
                log.info("[SIM] llm queue full: %r keeps its draft", old[1][:50])
            if o.dtask is None or o.dtask.done():
                o.dtask = asyncio.create_task(self._ddrain(o), name="diagram:extract")
        if not d.ops:
            log.info("[STAGE] diagram: nothing new in %r", ev.text[:60])
            return
        res = o.dlog.delta(d.ops, line_id, "fast", t_ms=int(self.e.now() * 1000), text=ev.text)
        for raw, why in res.rejected:
            log.info("[STAGE] diagram.rejected %s: %s", raw, why)
        g = o.dlog.fold()
        o.dtitle = shapes_title(g) or o.dtitle  # test37: "Two circles C1 and C2" with C3 added
        await self._publish_diagram(o)
        o.nouns = diagram_nouns(g)  # test38: Whisper heard "pentagon" as "Zagon", "outside" as
        await self._words(o)                        # "inside": primed with the diagram's own words
        self.stats.draft_s.append(time.perf_counter() - heard)
        log.info("[STAGE] diagram %s: %d op(s), %d refused (fast path, 0 tokens)", line_id, len(res.ok),
                 len(res.rejected))

    async def _ddrain(self, o: _Open) -> None:
        """M3: one extraction call per queued line, in order; an answer the validator takes whole replaces the line's
        fast draft; a refused op, a failed call, a closed diagram or an undone line: the draft stays."""
        while o.dqueue and self._live() is o:
            line_id, text, heard, draft = o.dqueue.popleft()
            before = [t for i, t in o.dlog.lines if i != line_id][-2:]
            try:
                res = await self.extractor.delta(o.dlog.fold(skip_fast_of=line_id), before, text, draft)
            except asyncio.CancelledError:
                raise
            except Exception as err:  # every model failed: the draft stays (no fake fallback)
                self.stats.failed += 1
                log.warning("[SIM] llm call failed for %s (the draft stays): %s", line_id, err)
                continue
            self.stats.calls += 1
            self.stats.tokens += res.tokens
            self.stats.counted += res.counted
            try:
                await self._dland(o, res, line_id, text, heard)
            except Exception:  # a layout / commit fault: logged, the next lines still go
                log.exception("[SIM] llm answer for %s could not be drawn", line_id)

    async def _dland(self, o: _Open, res: Any, line_id: str, text: str, heard: float) -> None:
        async with self.e._lock:
            if self._live() is not o or o.mode != "diagram" or o.frozen or line_id in o.dlog.undone:
                log.info("[SIM] llm answer for %s dropped (the diagram moved on)", line_id)
                return
            g = o.dlog.fold(skip_fast_of=line_id)
            raws, dropped = dextract.clean(res.ops, text, g)
            chk = check_delta(raws, g, o.dlog.recent(), text, max_ops=dops.MAX_OPS)
            refused = dropped + list(chk.rejected)
            lost = dextract.lost_ids(o.dlog, line_id, g, raws)
            if lost:  # review: a late answer must keep the parts the lines said since then stand on
                refused.append(({"lost": lost}, "later lines use these parts"))
            for raw, why in refused:
                log.info("[SIM] llm refused %s: %s", raw, why)
            if not chk.ok or chk.rejected or lost:  # all or nothing: half an answer never mixes with half a draft
                log.info("[SIM] llm %s: answer not taken (%d ok, %d refused), the draft stays, %d tokens, %.2f s",
                         line_id, len(chk.ok), len(refused), res.tokens, time.perf_counter() - heard)
                return
            o.dlog.delta(raws, line_id, "llm", t_ms=int(self.e.now() * 1000), text=text)
            g = o.dlog.fold()
            o.dtitle = shapes_title(g) or o.dtitle
            await self._publish_diagram(o)
            o.nouns = diagram_nouns(g)
            await self._words(o)
            self.stats.full_s.append(time.perf_counter() - heard)
            log.info("[SIM] llm %s: %d op(s) replace the draft, %d dropped, %d tokens (%d in, %d out, %d counted), "
                     "%.2f s", line_id, len(chk.ok), len(dropped), res.tokens, res.prompt_tokens,
                     res.tokens - res.prompt_tokens, res.counted, time.perf_counter() - heard)

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
        m = self.e._sims.mode
        if m is not None and m.kind == "stage" and m.block_id == o.block_id:  # M0: the recap leaves the picture out
            m.picture = picture_words(o.dlog.fold())
        try:
            patch = dpatch.build(o.dlog.fold(), rev=o.rev + 1, nogo=_title_nogo(spec.title) if b.full else None,
                                 fbd=o.fbd)
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
        o.dqueue.clear()  # M3 review: lines from before the switch are not sent to the LLM again
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
        if o is not None and o.dtask is not None and not o.dtask.done():
            o.dtask.cancel()

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
            elif kind == "stage_fbd":  # M2: the control's Free body button (off -> all -> each body -> off)
                o.fbd = str(args.get("on") or "")[:40]
                log.info("teacher: free-body view %s", o.fbd or "off")
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


# M2: "the free body diagram of the top block" (test42: Whisper's "freeboard diagram")
_FBD = re.compile(r"\bfree[\s-]*(?:bod(?:y|ies)|board)\b", re.IGNORECASE)
_FBD_PHRASE = re.compile(r"\b(?:(?:draw|show)\s+)?(?:(?:the|a)\s+)?free[\s-]*(?:bod(?:y|ies)|board)(?:\s+diagrams?)?\b",
                         re.IGNORECASE)
_FBD_OFF = re.compile(r"\bback to the (?:picture|diagram|scene|figure|setup)\b", re.IGNORECASE)
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


_CUE_STOP = {"imagine", "imager", "picture", "visualise", "visualize", "suppose", "think", "consider", "you", "your",
             "you're", "are", "is", "was", "were", "be", "the", "and", "with", "of", "on", "in", "at", "to", "into",
             "this", "that", "there", "here", "now", "so", "okay", "ok", "then", "surface", "top", "side", "some", "very",
             "if", "we", "our", "us", "it", "its", "has", "have", "having", "for", "from", "who", "which", "what", "just"}


def cue_words(text: str) -> frozenset[str]:
    """A cue's content words, normalised ("Imagine you jump on the surface of the moon" -> {jump, moon}): no cue
    word, article, count or filler; plurals and -ing folded ("teaching students" -> {teach, student})."""
    out = set()
    for w in re.findall(r"[a-z][a-z0-9']*", text.lower()):
        if w in _CUE_STOP or w in dfast.COUNT or (len(w) < 3 and not any(c.isdigit() for c in w)):
            continue
        if w.endswith("ing") and len(w) > 5:
            w = w[:-3]
        elif w.endswith("s") and not w.endswith("ss") and len(w) > 3:
            w = w[:-1]
        out.add(w)
    return frozenset(out)


def picture_words(g: Any) -> frozenset[str]:
    """What a diagram draws, in words: its parts' kind words and labels ("box", "inclined", "plane", "c3")."""
    out: set[str] = set()
    for p in g.parts.values():
        for w in (list((dparts.kind(p.kind) or {}).get("words", [])) + [p.kind.replace("_", " "), p.label or ""]):
            out |= set(re.findall(r"[a-z][a-z0-9]*", w.lower()))
    return frozenset(out)


def diagram_nouns(g: Any) -> list[str]:
    """The words Whisper is primed with while a diagram is open: its labels and part words; with shapes, the shape
    family and the place words said about them."""
    out: list[str] = []
    for p in g.parts.values():
        out += [w for w in ((dparts.kind(p.kind) or {}).get("words", [])[:1] + [p.label]) if w]
    if any(p.kind in SHAPE_KINDS for p in g.parts.values()):
        out += [k for k in SHAPE_KINDS if k != "rectangle"] + ["inside", "outside"]
    return list(dict.fromkeys(out))[:16]


def shapes_title(g: Any) -> str:
    """A diagram of labelled shapes of one kind, titled by them ("Three circles C1, C2, C3"); the shapes inside them
    are not counted. "" otherwise (the title of the first line stays)."""
    top = [p for p in g.parts.values() if p.kind in SHAPE_KINDS and g.rels.get(p.id, ("",))[0] != "inside"]
    kinds = {p.kind for p in top}
    if len(top) < 2 or len(kinds) != 1 or not all(p.label for p in top):
        return ""
    names = [p.label for p in top]
    joined = " and ".join(names) if len(names) == 2 else ", ".join(names)
    return f"{dfast._num(len(top)).capitalize()} {top[0].kind}s {joined}"[:48]


def _recount(d: dfast.Draft, parts: dict) -> bool:
    """The cue draws again exactly what the open diagram has ("two blocks ... on the floor" with those drawn), and it
    says neither "another" nor a new name (M0: "another circle C3" adds one)."""
    if not d.new or d.more or d.named:
        return False
    def sig(kind: str, attr: dict) -> tuple:  # a beaker of NaOH is not the beaker of HCl
        return kind, attr.get("chem"), attr.get("element"), attr.get("name")
    said = Counter(sig(o["kind"], o.get("attr") or {}) for o in d.ops if o.get("op") == "part" and o.get("id") in d.new)
    said.update(sig(parts[i].kind, parts[i].attr) for i in d.old if i in parts)  # "on the floor": the floor drawn
    # test45: a pulley's implied support is never said ("two masses ... over a pulley" again drew two more masses)
    said -= Counter(sig(o["kind"], o.get("attr") or {}) for o in d.ops if o.get("op") == "part"
                    and o.get("id") in d.new and (o.get("attr") or {}).get("implied"))
    have = Counter(sig(p.kind, p.attr) for p in parts.values() if not p.attr.get("implied"))
    return said == have  # the same picture said again (test36's "imagine a square" after C1–C3 is the next one)


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
