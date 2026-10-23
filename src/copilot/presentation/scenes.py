"""The presentation engine's Live Scene part (F-015 L1). Called by PresentationEngine under its lock; the engine stays
the only writer of the deck.

    RepresentationIntent(scene) cue  -> Auto: a new scene (simulation mode, shared with the templates: one at a time,
                                        the recap when it ends) · Suggest: a /control chip · Off: nothing
    RepresentationIntent(scene) edit -> lines collected until a pause (EDIT_PAUSE_S) or the end of a sentence, then
                                        one call; lines said during a call wait for the next one
    teacher commands                 -> sim_play / sim_pause / sim_step / sim_reset / sim_set speed / sim_remove on a
                                        scene's slide; sim_end (Back to slides) ends whichever mode is open;
                                        scene_look {id, icon | image | own} (Picture), scene_frame {id} (Seen from)

A body's picture (scene.assets): an icon for its noun at once; no icon: one glyph call in the background (cached by
noun, at most MAX_GLYPHS per scene), the scene is patched when it arrives.

F-016 canvas:
- a thing's picture (scene.pictures): a cached Fluent 3D emoji at once; else its icon first and the emoji fetched in a
  thread (the scene is patched when it lands); no emoji: the icon, else a glyph.
- C1 part 2 photos (scene.photos; the app sets `photos`): a noun with no 3D picture gets a photo cutout (search +
  CLIP + u2netp) before any glyph call ("fill"; photo_first: every non-person noun); a place gets a landscape photo for
  its backdrop. Both land in the background and patch the scene; none found: the 3D picture / icon / glyph stays.
- safety (scene.safety): a line with a blocked word is never sent; the model's `unsafe` op drops the call's ops and
  puts the scene back as it was (nothing drawn, logged).
- a canvas cue while a scene is open: an edit when it refers to the open scene (a name in it, "it", "there"), else a
  new scene.
- Imagine Mode (`imagine_mode {on}`, /control Imagine / End): a canvas slide at once; every picturable line (0-token
  filter) goes to the open scene, in batches (a sentence's end, MAX_BATCH lines, or EDIT_PAUSE_S quiet); a canvas cue
  that does not refer to it starts the next scene in the same mode; only End (or Back to slides) ends it, then one
  recap.

The scene's slide appears at once (titled by the cue's noun); the compiler's ops stream in and each valid one is
applied, solved (scene.layout) and committed, so the shapes morph in while the model is still writing. The LLM call
runs outside the engine's lock. Without an LLM there is no scene (no fake fallback).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from copilot.core.events import RepresentationIntent, SimulationNotice, SimulationSuggestion
from copilot.presentation.spec import SceneBlock, SlideSpec
from copilot.scene import assets, layout, safety
from copilot.scene import pictures as pics
from copilot.scene.compiler import SceneCompiler
from copilot.scene.detector import _ANY_NOUN, cue as cue_world, wants_edit
from copilot.scene.ops import apply
from copilot.scene.spec import BODY_KINDS, SceneOp, SceneSpec
from copilot.scene.validate import Corpus, check

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

EDIT_PAUSE_S = 1.2     # lecture seconds without a line before collected edit lines are sent
MAX_CORPUS = 30        # lines kept per scene for the said-number and label checks
SUGGEST_S = 30.0
MAX_GLYPHS = 2         # LLM glyph calls per scene (a noun with no icon); a cached glyph costs nothing
MAX_FETCH = 8          # picture downloads per scene (F-016); a cached picture costs nothing
MAX_PHOTOS = 6         # photo searches per scene (C1 part 2): ~5 s each, in the background
MAX_BATCH = 3          # Imagine Mode: lines per call at most
IMAGINE_TITLE = "Imagine"
_PRONOUNS = frozenset({"you", "yourself", "yourselves", "me", "myself", "i", "we", "us", "ourselves", "he", "she",
                       "him", "her", "they", "them"})
_REFERS = re.compile(r"\b(?:it|its|it's|them|this one|that one|the same one)\b", re.IGNORECASE)


@dataclass
class _Open:
    """The open scene: its block, the lines heard while it is open, edits waiting for a call."""
    block_id: str
    slide_id: str
    lines: list[str] = field(default_factory=list)
    pending: list[str] = field(default_factory=list)
    last_at: float = 0.0
    task: Optional[asyncio.Task] = None
    glyphs: set[str] = field(default_factory=set)  # nouns whose glyph was asked for
    glyph_tasks: list[asyncio.Task] = field(default_factory=list)
    fetching: set[str] = field(default_factory=set)  # emoji names being downloaded (F-016)
    failed: set[str] = field(default_factory=set)    # ... and those that did not come (offline, not an image)
    photos: set[str] = field(default_factory=set)    # nouns / places whose photo was asked for (C1 part 2)
    no_photo: set[str] = field(default_factory=set)  # ... and found none
    heard_at: float = 0.0  # when the first line waiting for a call arrived (perf_counter): line end -> first shape


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
    shape_s: list[float] = field(default_factory=list)  # a line's arrival (its end of speech) -> its first shape


@dataclass
class SceneController:
    e: "PresentationEngine"
    compiler: Optional[SceneCompiler] = None     # set by the app when an LLM is configured
    open: Optional[_Open] = None
    clocks: dict[str, _Clock] = field(default_factory=dict)
    suggestion: Optional[_Suggestion] = None
    stats: SceneStats = field(default_factory=SceneStats)
    pictures: assets.Pictures = field(default_factory=assets.Pictures)  # the app gives it the embedder
    glyph_dir: Optional[Path] = None             # None: assets.GLYPH_DIR
    emoji: pics.Emoji = field(default_factory=pics.Emoji)  # the app gives it the embedder
    pics_dir: Optional[Path] = None              # None: pics.PICS_DIR
    fetch_pictures: bool = True                  # False: cached pictures only (tests, offline screenshots)
    photos: Any = None                           # scene.photos.Photos (the app gives it the image finder), None: off
    photo_first: bool = False                    # photos before 3D pictures (config images.scene_photos "first")
    place_photos: bool = True                    # a place's backdrop is a photo when one is found
    imagine: bool = False                        # Imagine Mode is on (F-016)
    unsafe: int = 0                              # calls the model refused as unsafe
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
    def _refers(self, text: str) -> bool:
        """The line talks about the open scene: a thing's name in it, or "it" / "them" before any new picture noun
        ("now imagine it on the moon" refers; "you're on a bus and it brakes" is a new scene)."""
        o = self._live()
        if o is None:
            return False
        _, b = self._block(o.slide_id)
        # "you" / "yourself" in a new line is the listener again, not the open scene's "you" (test32: "imagine you are
        # riding a rocket" was drawn into the car scene)
        # ... nor is the place alone ("imagine a rocket in space" after "a car in space" is a new scene)
        names = [x.name or x.look.noun for x in b.scene.entities
                 if (x.name or x.look.noun).lower() not in _PRONOUNS and x.kind != "place"] if b is not None else []
        low = text.lower()
        if any(n and re.search(rf"\b{re.escape(n.lower())}(?:e?s)?\b", low) for n in names):
            return True
        m = _REFERS.search(text)
        if m is None:
            return False
        before = [assets.singular(w) for w in re.findall(r"[a-z]+", low[:m.start()])]
        return not any(w in pics.words() for w in before)

    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "scene" or not self.e.s.scenes:
            return
        heard = time.perf_counter()  # the line's arrival: the latency clock starts before any slide work (review)
        bad = safety.blocked(ev.text)
        if bad:
            log.info("[SCENE] safety: a line with %r is not drawn", bad)
            return
        if ev.strength == "cue" and self._live() is not None and self._refers(ev.text):
            ev = ev.model_copy(update={"strength": "edit"})  # "now imagine the cube on the moon": the open scene
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
            await self.start([ev.text], origin="cue", cue_segment=next(iter(ev.segment_ids), ""), heard_at=heard)
            return
        if ev.strength != "edit":
            return
        o = self._live()
        if o is None:
            return
        o.lines = (o.lines + [ev.text])[-MAX_CORPUS:]
        _, b = self._block(o.slide_id)
        names = [x.name or x.look.noun for x in b.scene.entities if x.name or x.look.noun] if b is not None else []
        if self.imagine and not pics.picturable(ev.text, names):  # Imagine Mode's 0-token filter
            log.info("[SCENE] imagine: nothing to picture in %r", ev.text[:60])
            return
        if not self.imagine and not wants_edit(ev.text, names):
            log.info("[SCENE] not an edit: %r", ev.text[:60])
            return
        m = self.e._sims.mode
        if m is not None:
            m.heard_at = self.e.now()
        if not o.pending:
            o.heard_at = heard
        o.pending.append(ev.text)
        o.last_at = self.e.now()
        if ev.text.rstrip().endswith((".", "?", "!")) or len(o.pending) >= MAX_BATCH:
            self._flush(o)

    async def start(self, lines: list[str], *, origin: str, cue_segment: str = "", title: str = "",
                    imagine: bool = False, heard_at: float = 0.0) -> None:
        """Scene mode: a new slide with an empty stage at once; the ops of the cue's call fill it. In Imagine Mode
        the next scene stays in the same mode (one recap at its End)."""
        e = self.e
        title = title or _title_from(lines[-1] if lines else "")
        scene = SceneSpec(title=title, origin=origin if origin in ("cue", "policy", "teacher") else "cue")  # type: ignore[arg-type]
        if self.imagine or imagine or any(cue_world(x) == "canvas" for x in lines[-1:]):
            # a canvas from the start: the whole slide is its stage before the first thing lands (no jump)
            scene = layout.solve(scene.model_copy(update={"world": "canvas"}))
        block = SceneBlock(scene=scene)
        m = e._sims.mode
        if self.imagine and m is not None and m.kind == "scene" and m.imagine:
            old = self.open
            if old is not None and old.task is not None and not old.task.done():
                old.task.cancel()
            for t in old.glyph_tasks if old is not None else []:
                t.cancel()  # its photo searches and downloads stop too (review)
            spec_old, b_old = self._block(old.slide_id) if old is not None else (None, None)
            if spec_old is not None and b_old is not None and not b_old.scene.entities:
                await e._sims.take_off(spec_old)  # an empty stage ("Imagine", nothing drawn) does not stay
                if m.names and m.names[-1] == b_old.scene.title:
                    m.names.pop()
            m.block_id = block.id
            m.names.append(title)
            mode = m
        else:
            if self.imagine and not imagine:  # its mode ended before the ticker saw it: Imagine is over
                self.imagine = False
                await e.deck.set_imagine(False)
            old = self.open
            if old is not None:  # C1 live: the boy's call came after the dog's cue; its empty slide stayed
                if old.task is not None and not old.task.done():
                    old.task.cancel()
                for t in old.glyph_tasks:
                    t.cancel()
                spec_old, b_old = self._block(old.slide_id)
                if spec_old is not None and b_old is not None and not b_old.scene.entities:
                    log.info("[SCENE] another scene began before this one drew anything: its slide goes")
                    await e._sims.take_off(spec_old)
                self.open = None
            mode = await e._sims.begin("scene", "scene", block.id, title, origin, cue_segment)
            mode.imagine = imagine
        spec = await e._sims.place(mode, block, title, "spoken cue" if origin == "cue" else origin)
        self.open = _Open(block.id, spec.id, [x for x in lines if x][-MAX_CORPUS:], [], e.now())
        self.clocks[block.id] = _Clock(e.clock(), 0.0)
        await self._clear_suggestion()
        o = self.open
        o.pending = [x for x in lines if x]
        o.heard_at = heard_at or time.perf_counter()
        self._flush(o)

    def _flush(self, o: _Open) -> None:
        """One call for the lines waiting, unless a call is running (they go with the next one)."""
        if not o.pending or (o.task is not None and not o.task.done()) or self.compiler is None:
            return
        lines, o.pending = o.pending, []
        o.task = asyncio.create_task(self._compile(o, lines, o.heard_at), name="scene:compile")

    async def _compile(self, o: _Open, lines: list[str], heard_at: float = 0.0) -> None:
        e = self.e
        compiler = self.compiler
        assert compiler is not None
        _, b = self._block(o.slide_id)
        before = b.scene if b is not None else None
        first = before is None or not before.entities
        corpus = Corpus.of(o.lines)
        applied = rejected = 0
        refused = False

        async def on_op(op: SceneOp) -> None:
            nonlocal applied, rejected, refused
            async with e._lock:
                if self._live() is not o or refused:
                    return
                spec, blk = self._block(o.slide_id)
                if spec is None or blk is None:
                    return
                if op.op == "unsafe":  # the model refuses the lines: this call's ops go, nothing is drawn
                    refused = True
                    self.unsafe += 1
                    log.warning("[SCENE] unsafe: the model refused %r; the scene is put back", lines[-1][:60])
                    back = before if before is not None else blk.scene.model_copy(update={
                        "entities": [], "relations": [], "behaviors": [], "focus": []})
                    picked = {x.id: x.look for x in blk.scene.entities if x.look.pick == "teacher"}
                    back = back.model_copy(update={"playback": blk.scene.playback, "entities": [
                        x.model_copy(update={"look": picked[x.id]}) if x.id in picked else x
                        for x in back.entities]})
                    await self._replace(spec, blk, layout.solve(back.model_copy(update={"rev": blk.scene.rev + 1})))
                    return
                checked, why = check(op, blk.scene, corpus)
                if checked is None:
                    rejected += 1
                    log.info("[SCENE] scene.rejected %s: %s", op.model_dump(exclude_defaults=True), why)
                    return
                for note in checked.notes:
                    log.info("[SCENE] scene.rejected %s %s: %s", op.op, op.id or op.target, note)
                applied += 1
                scene = self._emoji(o, self.pictures.resolve(apply(blk.scene, checked), self.glyph_dir))
                await self._replace(spec, blk, layout.solve(scene))
                if applied == 1 and heard_at:  # the first shape is laid out and published
                    self.stats.shape_s.append(time.perf_counter() - heard_at)
                self._glyphs(o, scene)

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
                if first and self._live() is o and blk is not None and not blk.scene.entities and not self.imagine:
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
        shape = f"{self.stats.shape_s[-1]:.2f} s" if applied and heard_at and self.stats.shape_s else "-"
        log.info("[SCENE] call %s: %d op(s) applied, %d refused, %d tokens, first op %s, done %.2f s, line -> first "
                 "shape %s", res.entry, applied, rejected + len(res.bad), res.tokens, first, res.total_s, shape)

    def _glyphs(self, o: _Open, scene: SceneSpec) -> None:
        """A body whose noun has no icon: its glyph is drawn by one call in the background (a few per scene)."""
        if self.compiler is None or not hasattr(self.compiler, "router"):
            return
        for e in scene.entities:
            noun = assets.head(e.look.noun)
            if not assets.needs_glyph(e) or noun in o.glyphs or len(o.glyphs) >= MAX_GLYPHS:
                continue
            if e.look.photo or e.look.noun in o.photos and e.look.noun not in o.no_photo:
                continue  # its photo is here or on the way
            name = self._pic_name(e, scene)
            if name and (name in o.fetching and name not in o.failed or pics.cached(name, self.pics_dir)):
                continue  # its picture is here or on the way
            o.glyphs.add(noun)
            o.glyph_tasks.append(asyncio.create_task(self._glyph(o, noun), name="scene:glyph"))

    async def _glyph(self, o: _Open, noun: str) -> None:
        router = getattr(self.compiler, "router", None)
        try:
            d = await assets.glyph(router, noun, self.glyph_dir)
        except Exception as err:  # a failed call: the kind's own drawing stays
            log.info("[SCENE] glyph %r failed: %s", noun, err)
            return
        if not d:
            return
        async with self.e._lock:
            spec, b = self._block(o.slide_id)
            if spec is None or b is None or self._live() is not o:
                return
            ents = [x.model_copy(update={"look": x.look.model_copy(update={"glyph": d})})
                    if assets.needs_glyph(x) and assets.head(x.look.noun) == noun else x for x in b.scene.entities]
            if ents != b.scene.entities:
                await self._replace(spec, b, layout.solve(b.scene.model_copy(update={"entities": ents})))

    def _pic_name(self, e: Any, scene: SceneSpec, noun: str = "") -> str:
        """The emoji name for a thing or a body's noun: a person whole-body, posed by what they do (walking, running,
        bouncing a held ball), else the noun's match."""
        noun = noun or e.look.noun
        if not noun or (e.kind != "thing" and e.kind not in BODY_KINDS):
            return ""
        if e.kind != "thing" and layout.world_of(scene) != "canvas":
            return ""  # a body in the motion / relative worlds keeps its icon or glyph (review)
        act = next((b.kind for b in scene.behaviors if b.target == e.id and b.kind != "emit"), "")
        held = next((x.look.noun for r in scene.relations if r.kind == "holding" and r.b == e.id
                     for x in scene.entities if x.id == r.a), "")
        return pics.person(noun, act, held) if noun == e.look.noun and pics.person(noun) else self.emoji.match(noun)

    def _emoji(self, o: _Open, scene: SceneSpec) -> SceneSpec:
        """F-016: each thing's (and body's) Fluent 3D picture (and the one it turns into): cached -> on it now; else
        fetched in a thread (at most MAX_FETCH per scene) and the scene patched when it lands. A person's picture
        follows their action (standing -> walking)."""
        ents: list[Any] = []
        changed = False
        canvas = layout.world_of(scene) == "canvas"  # a body has a 3D picture on the canvas; its own worlds draw icons
        for x in scene.entities:
            lk = x.look
            if x.kind == "place" and self.photos is not None and self.place_photos:
                where = lk.noun or x.name
                url = self.photos.cached_place(where)
                if url and url != lk.photo:
                    x = x.model_copy(update={"look": lk.model_copy(update={"photo": url})})
                    changed = True
                elif not lk.photo:
                    self._ask_photo(o, where, place=True)
            body = canvas and x.kind in BODY_KINDS
            if (x.kind != "thing" and not body) or lk.pick == "teacher" or lk.form and not lk.to_noun:
                ents.append(x)
                continue
            upd: dict[str, str] = {}
            noun = lk.noun
            if self.photos is not None and noun and not lk.form and self.photos.wanted(noun):
                name = self._pic_name(x, scene, noun)
                if self.photo_first or not name or name in o.failed:  # "fill": only where no 3D picture comes
                    url = self.photos.cached(noun)
                    if url and url != lk.photo:
                        upd["photo"] = url
                    elif not url:
                        self._ask_photo(o, noun)
            for noun, key in ((lk.noun, "emoji"), (lk.to_noun, "to_emoji")):
                if not noun or key == "emoji" and lk.form:
                    continue
                name = self._pic_name(x, scene, noun)
                if not name:
                    continue
                url = pics.cached(name, self.pics_dir)
                if url and url == getattr(lk, key):
                    continue
                if url:
                    upd[key] = url
                elif self.fetch_pictures and name not in o.fetching and len(o.fetching) < MAX_FETCH:
                    o.fetching.add(name)
                    o.glyph_tasks.append(asyncio.create_task(self._fetch(o, name), name="scene:picture"))
            if upd:
                x = x.model_copy(update={"look": lk.model_copy(update=upd)})
                changed = True
            ents.append(x)
        return scene.model_copy(update={"entities": ents}) if changed else scene

    def _ask_photo(self, o: _Open, noun: str, place: bool = False) -> None:
        if not self.fetch_pictures or noun in o.photos or len(o.photos) >= MAX_PHOTOS:
            return
        o.photos.add(noun)
        o.glyph_tasks.append(asyncio.create_task(self._photo(o, noun, place), name="scene:photo"))

    async def _photo(self, o: _Open, noun: str, place: bool) -> None:
        try:
            url = await (self.photos.place(noun) if place else self.photos.thing(noun))
        except Exception as err:  # offline, the model missing: the 3D picture / icon / glyph stays
            log.info("[SCENE] photo %r failed: %s", noun, err)
            url = ""
        async with self.e._lock:
            spec, b = self._block(o.slide_id)
            if spec is None or b is None or self._live() is not o:
                return
            if not url:
                o.no_photo.add(noun)
                self._glyphs(o, b.scene)
                return
            kinds = ("place",) if place else ("thing",) + BODY_KINDS
            ents = [x.model_copy(update={"look": x.look.model_copy(update={"photo": url})})
                    if x.kind in kinds and (x.look.noun or x.name) == noun and x.look.pick != "teacher" else x
                    for x in b.scene.entities]
            if ents != b.scene.entities:
                await self._replace(spec, b, layout.solve(b.scene.model_copy(update={"entities": ents})))

    async def _fetch(self, o: _Open, name: str) -> None:
        url = await asyncio.to_thread(pics.fetch, name, self.pics_dir)
        log.info("[SCENE] picture %r: %s", name, url or "not fetched (the icon stays, else a glyph)")
        async with self.e._lock:
            spec, b = self._block(o.slide_id)
            if spec is None or b is None or self._live() is not o:
                return
            if not url:
                o.failed.add(name)
                self._emoji(o, b.scene)  # "fill": a noun whose 3D picture did not come asks for its photo (review)
                self._glyphs(o, b.scene)  # ... the glyph only when no photo is on the way
                return
            scene = self._emoji(o, b.scene)
            if scene is not b.scene:
                await self._replace(spec, b, layout.solve(scene))

    async def imagine_mode(self, on: bool) -> None:
        """/control Imagine / End (F-016): a canvas slide at once, every picturable line drawn until End; End:
        slides resume after one recap."""
        e = self.e
        if on == self.imagine:
            return
        self.imagine = on
        await e.deck.set_imagine(on)
        m = e._sims.mode
        if on:
            log.info("teacher: Imagine Mode on")
            if self._live() is not None and m is not None:
                m.imagine = True  # the open scene goes on in Imagine Mode
            elif self.compiler is not None:
                await self.start([], origin="teacher", title=IMAGINE_TITLE, imagine=True)
            return
        log.info("teacher: Imagine Mode ended")
        if m is not None and m.kind == "scene":
            await e._sims.end("Imagine Mode ended")

    async def tick(self) -> None:
        if self.imagine and (self.e._sims.mode is None or self.e._sims.mode.kind != "scene"):
            self.imagine = False  # its mode ended another way (Back to slides, removed, the lecture's end)
            await self.e.deck.set_imagine(False)
        if self.open is not None and self._live() is None:  # its mode ended (Back to slides, another one began)
            if self.open.task is not None and not self.open.task.done():
                self.open.task.cancel()
                log.info("[SCENE] the scene ended: its running call is cancelled")
            for t in self.open.glyph_tasks:
                t.cancel()
            spec, b = self._block(self.open.slide_id)
            if spec is not None and b is not None and not b.scene.entities:
                # live run 2026-10-22: the cue's call failed, then "back to the slides": no empty stage is left
                log.info("[SCENE] the scene ended before it drew anything: its slide goes")
                await self.e._sims.take_off(spec)
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

        if kind == "imagine_mode":
            await self.imagine_mode(bool(args.get("on")))
            return
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
        if kind == "scene_look":
            await self._look(spec, b, args)
            return
        if kind == "scene_frame":
            fid = str(args.get("id") or "")
            f = b.scene.get(fid)
            if (fid == "" or f is not None and f.kind in BODY_KINDS + ("river",)) and fid != b.scene.frame:
                log.info("teacher: the scene seen from %r", fid or "the ground")
                await self._replace(spec, b, layout.solve(b.scene.model_copy(update={"frame": fid})))
            return
        if kind == "sim_remove":
            if mine:
                await self.e._sims.end("the teacher removed the scene")
            await self.e._sims.take_off(spec)
            log.info("teacher removed the scene %r", spec.title)
            return
        pb = next_playback(kind, b.scene.playback, self.now_t(b), args)
        if pb is not None:
            await self._replace(spec, b, b.scene.model_copy(update={"playback": pb}))


    async def _look(self, spec: SlideSpec, b: SceneBlock, args: dict) -> None:
        """The teacher's picture for a body: an icon of the set, an uploaded image (/media/<id>.jpg), or `own` (the
        kind's own drawing). Kept across edits (look.pick "teacher")."""
        e = b.scene.get(str(args.get("id") or ""))
        if e is None or e.kind not in BODY_KINDS + ("thing",):  # F-016: a thing too
            return
        icon, image = str(args.get("icon") or ""), str(args.get("image") or "")
        if icon and icon not in assets.icons():
            log.warning("scene_look: unknown icon %r", icon)
            return
        if image and not _MEDIA.fullmatch(image):
            log.warning("scene_look: bad image %r", image)
            return
        if not (icon or image or args.get("own")):
            return
        look = e.look.model_copy(update={"icon": icon, "image": image, "glyph": "", "emoji": "", "form": "", "pick": "teacher"})
        ents = [x.model_copy(update={"look": look}) if x.id == e.id else x for x in b.scene.entities]
        log.info("teacher: picture of %s -> %s", e.id, icon or image or "its own drawing")
        await self._replace(spec, b, layout.solve(b.scene.model_copy(update={"entities": ents})))


_MEDIA = re.compile(r"/media/[0-9a-f]{8,64}\.jpg")


def _title_from(line: str) -> str:
    """The first drawable noun of the cue ("Imagine a square ..." -> "Square"), else "Scene"."""
    m = _ANY_NOUN.search(line)
    if not m:
        return "Scene"
    w = re.sub(r"\s+of\b.*$", "", m.group(0).strip())  # "graph of y" -> "graph"
    w = "Graph" if w.lower().startswith("y") else w
    return w[:1].upper() + w[1:]
