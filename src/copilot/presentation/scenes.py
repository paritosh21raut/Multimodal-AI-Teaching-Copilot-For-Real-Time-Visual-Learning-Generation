"""The presentation engine's Live Scene part (F-015 L1). Called by PresentationEngine under its lock; the engine stays
the only writer of the deck.

    RepresentationIntent(scene) cue  -> Auto: a new scene (simulation mode, shared with the templates: one at a time,
                                        the recap when it ends) · Suggest: a /control chip · Off: nothing
    RepresentationIntent(scene) edit -> lines collected until a pause (EDIT_PAUSE_S) or the end of a sentence, then
                                        one call; lines said during a call wait for the next one
    teacher commands                 -> sim_play / sim_pause / sim_step / sim_reset / sim_set speed / sim_remove on a
                                        scene's slide; sim_end (Back to slides) ends whichever mode is open

The scene's slide appears at once (titled by the cue's noun); the compiler's ops stream in and each valid one is
applied, solved (scene.layout) and committed, so the shapes morph in while the model is still writing. The LLM call
runs outside the engine's lock. Without an LLM there is no scene (no fake fallback).
"""
from __future__ import annotations

import asyncio
import logging
import re
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Optional

from copilot.core.events import RepresentationIntent, SimulationNotice, SimulationSuggestion
from copilot.presentation.spec import SceneBlock, SlideSpec
from copilot.scene import layout
from copilot.scene.compiler import SceneCompiler
from copilot.scene.detector import _ANY_NOUN, wants_edit
from copilot.scene.ops import apply
from copilot.scene.spec import SceneOp, SceneSpec
from copilot.scene.validate import Corpus, check

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

EDIT_PAUSE_S = 1.2     # lecture seconds without a line before collected edit lines are sent
MAX_CORPUS = 30        # lines kept per scene for the said-number and label checks
SUGGEST_S = 30.0


@dataclass
class _Open:
    """The open scene: its block, the lines heard while it is open, edits waiting for a call."""
    block_id: str
    slide_id: str
    lines: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    last_at: float = 0.0
    task: Optional[asyncio.Task] = None


@dataclass
class _Clock:
    at: float = 0.0
    t: float = 0.0


@dataclass
class _Suggestion:
    id: str
    lines: list[str]
    until: float


@dataclass
class SceneStats:
    calls: int = 0
    tokens: int = 0
    ops: int = 0
    rejected: int = 0
    first_op_s: list[float] = field(default_factory=list)


@dataclass
class SceneController:
    e: "PresentationEngine"
    compiler: Optional[SceneCompiler] = None     # set by the app when an LLM is configured
    open: Optional[_Open] = None
    clocks: dict[str, _Clock] = field(default_factory=dict)
    suggestion: Optional[_Suggestion] = None
    stats: SceneStats = field(default_factory=SceneStats)
    _warned: bool = False

    # ---- lookup ---------------------------------------------------------------------------------------------
    def _live(self) -> Optional[_Open]:
        """The open scene while its mode runs (the shared mode may have ended or moved on to something else)."""
        m = self.e._sims.mode
        o = self.open
        if o is None or m is None or m.kind != "scene" or m.block_id != o.block_id:
            return None
        return o

    def _block(self, slide_id: str) -> tuple[Optional[SlideSpec], Optional[SceneBlock]]:
        spec = self.e._spec(slide_id)
        b = next((x for x in spec.blocks if x.type == "scene"), None) if spec is not None else None
        return spec, b  # type: ignore[return-value]

    def owns(self, kind: str, args: dict) -> bool:
        """A teacher's command for a scene: on a slide with a scene, or this controller's Suggest chip."""
        if kind in ("sim_accept", "sim_dismiss"):
            return self.suggestion is not None and args.get("id") == self.suggestion.id
        return self._block(str(args.get("slide_id") or ""))[1] is not None

    def about(self, title: str) -> bool:
        """An announced title that is about the open scene ("the graph of y equals x squared"): not a new topic."""
        o = self._live()
        if o is None:
            return False
        _, b = self._block(o.slide_id)
        names = [x.name for x in b.scene.entities if x.name] if b is not None else []
        low = title.lower()
        return any(re.search(rf"\b{re.escape(n.lower())}", low) for n in names)

    def now_t(self, b: SceneBlock) -> float:
        pb = b.scene.playback
        c = self.clocks.get(b.id)
        if pb.state != "playing" or c is None:
            return pb.t
        return c.t + max(0.0, self.e.clock() - c.at) * pb.speed

    # ---- writing --------------------------------------------------------------------------------------------
    async def _replace(self, spec: SlideSpec, b: SceneBlock, scene: SceneSpec) -> None:
        scene = scene.model_copy(update={"version": b.scene.version + 1})
        new = b.model_copy(update={"scene": scene})
        upd: dict[str, Any] = {"blocks": [new if x.id == b.id else x for x in spec.blocks]}
        # an emptied scene ("remove all") goes back to its cue's title, not the last thing removed
        title = layout.title_of(scene) or (scene.title if not scene.entities else None)
        if title and spec.id not in self.e._teacher_titles and spec.title != title:
            upd["title"] = title
            m = self.e._sims.mode
            if m is not None and m.block_id == b.id:
                m.names[-1] = title  # the recap is titled by what the scene became ("Recap: Square and circle")
        await self.e._commit(spec.model_copy(update=upd))
        if scene.playback.rev != b.scene.playback.rev:
            self.clocks[b.id] = _Clock(self.e.clock(), scene.playback.t)

    # ---- intents --------------------------------------------------------------------------------------------
    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "scene" or not self.e.s.scenes:
            return
        if ev.strength == "cue":
            if self.compiler is None:
                if not self._warned:
                    log.warning("[SCENE] no LLM configured: no live scenes")
                    self._warned = True
                return
            setting = self.e.s.simulations
            if setting == "off":
                log.info("[SCENE] cue ignored (setting off): %r", ev.text[:60])
                return
            if setting == "suggest":
                await self._suggest([ev.text])
                return
            self.e.stats.ops["scene_start"] += 1
            await self.start([ev.text], origin="cue", cue_segment=next(iter(ev.segment_ids), ""))
            return
        if ev.strength != "edit":
            return
        o = self._live()
        if o is None:
            return
        o.lines = (o.lines + [ev.text])[-MAX_CORPUS:]
        _, b = self._block(o.slide_id)
        names = [x.name for x in b.scene.entities if x.name] if b is not None else []
        if not wants_edit(ev.text, names):
            log.info("[SCENE] not an edit: %r", ev.text[:60])
            return
        m = self.e._sims.mode
        if m is not None:
            m.heard_at = self.e.now()
        o.pending.append(ev.text)
        o.last_at = self.e.now()
        if ev.text.rstrip().endswith((".", "?", "!")):
            self._flush(o)

    async def start(self, lines: list[str], *, origin: str, cue_segment: str = "") -> None:
        """Scene mode: a new slide with an empty stage at once; the ops of the cue's call fill it."""
        e = self.e
        title = _title_from(lines[-1] if lines else "")
        scene = SceneSpec(title=title, origin=origin if origin in ("cue", "policy", "teacher") else "cue")  # type: ignore[arg-type]
        block = SceneBlock(scene=scene)
        mode = await e._sims.begin("scene", "scene", block.id, title, origin, cue_segment)
        spec = await e._sims.place(mode, block, title, "spoken cue" if origin == "cue" else origin)
        self.open = _Open(block.id, spec.id, [x for x in lines if x][-MAX_CORPUS:], [], e.now())
        self.clocks[block.id] = _Clock(e.clock(), 0.0)
        await self._clear_suggestion()
        o = self.open
        o.pending = [x for x in lines if x]
        self._flush(o)

    def _flush(self, o: _Open) -> None:
        """One call for the lines waiting, unless a call is running (they go with the next one)."""
        if not o.pending or (o.task is not None and not o.task.done()) or self.compiler is None:
            return
        lines, o.pending = o.pending, []
        o.task = asyncio.create_task(self._compile(o, lines), name="scene:compile")

    async def _compile(self, o: _Open, lines: list[str]) -> None:
        e = self.e
        compiler = self.compiler
        assert compiler is not None
        _, b = self._block(o.slide_id)
        before = b.scene if b is not None else None
        first = before is None or not before.entities
        corpus = Corpus.of(o.lines)
        applied = rejected = 0

        async def on_op(op: SceneOp) -> None:
            nonlocal applied, rejected
            async with e._lock:
                if self._live() is not o:
                    return
                spec, blk = self._block(o.slide_id)
                if spec is None or blk is None:
                    return
                checked, why = check(op, blk.scene, corpus)
                if checked is None:
                    rejected += 1
                    log.info("[SCENE] scene.rejected %s: %s", op.model_dump(exclude_defaults=True), why)
                    return
                for note in checked.notes:
                    log.info("[SCENE] scene.rejected %s %s: %s", op.op, op.id or op.target, note)
                applied += 1
                await self._replace(spec, blk, layout.solve(apply(blk.scene, checked)))

        try:
            topic = e._sims.mode.frame.topic if e._sims.mode is not None else ""
            res = await compiler.compile(lines, before, topic, on_op)
        except asyncio.CancelledError:
            raise
        except Exception as err:  # AllProvidersFailed, a provider error: no scene change, /control is told
            log.warning("[SCENE] the call failed: %s", err)
            async with e._lock:
                await e.bus.publish(SimulationNotice(slide_id=o.slide_id, text="Scene: the model did not answer"))
            return
        finally:
            async with e._lock:
                o.task = None
                spec, blk = self._block(o.slide_id)
                if first and self._live() is o and blk is not None and not blk.scene.entities:
                    # a cue that drew nothing ("imagine the human body ..."): no empty stage, slides resume
                    log.info("[SCENE] the cue drew nothing: the scene closes")
                    self.open = None
                    await e._sims.end("the scene drew nothing")
                    if spec is not None:
                        await e._sims.take_off(spec)
                elif self._live() is o and o.pending:  # lines said during the call: the next call, now
                    self._flush(o)
        self.stats.calls += 1
        self.stats.tokens += res.tokens
        self.stats.ops += applied
        self.stats.rejected += rejected + len(res.bad)
        if res.first_op_s is not None:
            self.stats.first_op_s.append(res.first_op_s)
        for bad in res.bad:
            log.info("[SCENE] scene.rejected (not an op) %s", bad)
        first = f"{res.first_op_s:.2f} s" if res.first_op_s is not None else "-"
        log.info("[SCENE] call %s: %d op(s) applied, %d refused, %d tokens, first op %s, done %.2f s",
                 res.entry, applied, rejected + len(res.bad), res.tokens, first, res.total_s)

    async def tick(self) -> None:
        if self.open is not None and self._live() is None:  # its mode ended (Back to slides, another one began)
            if self.open.task is not None and not self.open.task.done():
                self.open.task.cancel()
                log.info("[SCENE] the scene ended: its running call is cancelled")
            self.open = None
        o = self._live()
        if o is not None and o.pending and self.e.now() - o.last_at >= EDIT_PAUSE_S:
            self._flush(o)
        if self.suggestion is not None and self.e.now() > self.suggestion.until:
            await self._clear_suggestion()

    # ---- Suggest -------------------------------------------------------------------------------------------
    async def _suggest(self, lines: list[str]) -> None:
        await self._clear_suggestion()
        self.suggestion = _Suggestion(uuid.uuid4().hex[:12], list(lines), self.e.now() + SUGGEST_S)
        await self.e.bus.publish(SimulationSuggestion(id=self.suggestion.id, template="scene",
                                                      name=_title_from(lines[-1]), text=lines[-1][:200]))
        log.info("[SCENE] suggested: %r", lines[-1][:60])

    async def _clear_suggestion(self) -> None:
        s, self.suggestion = self.suggestion, None
        if s is not None:
            await self.e.bus.publish(SimulationSuggestion(id=s.id, template="scene", active=False))

    # ---- the teacher's commands -----------------------------------------------------------------------------
    async def on_command(self, kind: str, args: dict) -> None:
        from copilot.presentation.simulations import next_playback

        if kind in ("sim_accept", "sim_dismiss"):
            s = self.suggestion
            if s is None:
                return
            if kind == "sim_dismiss":
                await self._clear_suggestion()
                return
            self.e.stats.ops["teacher_scene_accept"] += 1
            await self.start(s.lines, origin="policy")
            return
        spec, b = self._block(str(args.get("slide_id") or ""))
        if spec is None or b is None:
            return
        self.e.stats.ops[f"teacher_scene_{kind}"] += 1
        m = self.e._sims.mode
        mine = m is not None and m.kind == "scene" and m.block_id == b.id
        if mine:
            m.heard_at = self.e.now()  # type: ignore[union-attr]
        if kind == "sim_remove":
            if mine:
                await self.e._sims.end("the teacher removed the scene")
            await self.e._sims.take_off(spec)
            log.info("teacher removed the scene %r", spec.title)
            return
        pb = next_playback(kind, b.scene.playback, self.now_t(b), args)
        if pb is not None:
            await self._replace(spec, b, b.scene.model_copy(update={"playback": pb}))


def _title_from(line: str) -> str:
    """The first drawable noun of the cue ("Imagine a square ..." -> "Square"), else "Scene"."""
    m = _ANY_NOUN.search(line)
    if not m:
        return "Scene"
    w = re.sub(r"\s+of\b.*$", "", m.group(0).strip())  # "graph of y" -> "graph"
    w = "Graph" if w.lower().startswith("y") else w
    return w[:1].upper() + w[1:]
