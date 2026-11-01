"""The presentation engine's Story part (V3 ST1, docs/v3/ST1-story-core.md). Called by PresentationEngine under its
lock; the engine stays the only writer of the deck. 0 tokens.

    RepresentationIntent(story) cue   -> Auto: a story slide (the shared visual mode: one at a time, slides pause,
                                         the recap when it ends) · Suggest: a /control chip · Off: nothing
    RepresentationIntent(story) setup -> a Suggest chip (a year and a narrative opener, no cue)
    RepresentationIntent(story) edit  -> narration: the open scene grows, or a new scene at a beat (a time / place /
                                         sequence marker, a new character, MAX_SCENE_LINES lines); speech ("Ravi
                                         said, ...") -> a bubble at the speaker in the scene on screen
    RepresentationIntent(story) end   -> "that's the end of the story": the mode ends (the shared "back to the
                                         slides" is simulation.detector's)
    teacher commands                  -> sim_prev / sim_next {slide_id} (the scene shown), sim_remove, the chip

ST3: a line the fast path leaves partly unread (story.extract.needs_llm) waits for one Groq reading (validated whole,
else the fast reading); the lines after it queue behind it, so the speech order is kept.

A newer scene waits until the shown one has stayed DWELL_S. Pictures: the beat's said words go to the image service
(the teacher's files, then Wikimedia / Openverse, CLIP); meanwhile and as the fallback a Fluent 3D emoji of the beat's
noun. Cast members get an emoji of their noun; a name alone gets the neutral person (no face is guessed from a name).
"""
from __future__ import annotations

import asyncio
import difflib
import logging
import re
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from copilot.core.events import ImageReady, ImageRequested, RepresentationIntent, SimulationSuggestion
from copilot.presentation.content import Piece
from copilot.presentation.spec import SlideSpec, StoryBlock
from copilot.scene import pictures as pics
from copilot.scene import safety
from copilot.story import beats
from copilot.story import extract as sx
from copilot.story.detector import ends as story_ends
from copilot.story.spec import CAMERAS, Bubble, CastMember, StoryboardSpec, StoryScene

if TYPE_CHECKING:
    from copilot.presentation.engine import PresentationEngine

log = logging.getLogger(__name__)

DWELL_S = 6.0          # a scene stays at least this long (lecture seconds) before a newer one shows
MAX_SCENE_LINES = 3    # narrative lines per scene; the next one starts a new scene
MAX_SCENES = 16
MAX_CAST = 6
MAX_BUBBLES = 4        # kept per scene (the display shows the last two, three in a talk of 3+)
LOOKS = 6              # ST2: cast colours (web/shared/slide.css .look-0 .. .look-5)
NEUTRAL_FACES = ("person", "person curly hair", "person red hair", "person blonde hair")  # a name, gender not said
FACES = {"he": "man", "she": "woman"}
YOUNG = {"boy": "boy", "girl": "girl", "child": "child", "kid": "child"}
SUGGEST_S = 30.0
_PRONOUN = {"he", "she", "they", "him", "her", "them"}
_STOP = frozenset("""who that which in from through as and when on at to into was is will would has had goes went
travels travelled traveled starts started begins began lived lives with but where while this""".split())
_PROTAGONIST = re.compile(
    r"\b(?:story|tale|journey|life|adventures?) of\s+|\bimagine (?:that )?you are\s+|\bimagine (?:yourself|you) as\s+"
    r"|\bfollow\s+", re.IGNORECASE)


@dataclass
class _Open:
    block_id: str
    slide_id: str
    shown_at: float = 0.0
    held: bool = False                         # the teacher stepped with Prev / Next: no auto-advance till a new scene
    protagonist: str = ""                      # cast id of the cue's "a drop of water" / "Albert Einstein"
    last_speaker: str = ""
    waiting: Optional[beats.Speech] = None     # "Ravi said," : the words are the next line
    fragment: str = ""                         # "In 1905," : joins the next line
    retried: set[str] = field(default_factory=set)  # scene ids whose image search was tried again
    requests: dict[str, str] = field(default_factory=dict)   # image request id -> scene id
    images: dict[str, tuple[str, str, str]] = field(default_factory=dict)  # query -> (url, alt, credit)
    used: list[str] = field(default_factory=list)            # image ids shown (not offered again)
    tasks: list[asyncio.Task] = field(default_factory=list)
    fetching: set[str] = field(default_factory=set)
    scene_emoji: dict[str, str] = field(default_factory=dict)  # scene id -> its emoji name (filled when fetched)
    outbox: list[ImageRequested] = field(default_factory=list)  # searches asked while building, sent after the put
    mentioned: list[str] = field(default_factory=list)       # ST2: cast ids, the most recently said last
    member_emoji: dict[str, str] = field(default_factory=dict)  # ST2: cast id -> its figure's emoji name
    queue: deque = field(default_factory=deque)               # ST3: (id, line, why the LLM is asked) in said order
    n: int = 0
    dtask: Optional[asyncio.Task] = None                      # ST3: the queue's drain (one LLM call at a time)
    recent: list[str] = field(default_factory=list)           # ST3: the last lines heard (the prompt's "Before")


@dataclass
class _Suggestion:
    id: str
    text: str
    until: float


@dataclass
class StoryStats:
    stories: int = 0
    scenes: int = 0
    bubbles: int = 0
    images: int = 0
    llm_calls: int = 0     # ST3
    llm_tokens: int = 0
    llm_counted: int = 0
    llm_taken: int = 0
    llm_refused: int = 0
    llm_failed: int = 0


@dataclass
class StoryController:
    e: "PresentationEngine"
    open: Optional[_Open] = None
    suggestion: Optional[_Suggestion] = None
    stats: StoryStats = field(default_factory=StoryStats)
    emoji: pics.Emoji = field(default_factory=pics.Emoji)  # the app gives it the embedder
    pics_dir: Optional[Path] = None              # None: pics.PICS_DIR
    fetch_pictures: bool = True                  # False: cached pictures only (tests, offline screenshots)
    images: bool = True                          # False: no image searches (tests without an image service)
    asked: dict[str, tuple[str, str]] = field(default_factory=dict)  # image request id -> (slide id, scene id), kept
    #                                            after the story ends: a late answer is never the slide's own image
    extractor: object = None                     # ST3: story.extract.StoryExtractor (the app sets it); None: fast only

    # ---- lookup ---------------------------------------------------------------------------------------------
    def _live(self) -> Optional[_Open]:
        m = self.e._sims.mode
        o = self.open
        if o is None or m is None or m.kind != "story" or m.block_id != o.block_id:
            return None
        return o

    def _block(self, slide_id: str) -> tuple[Optional[SlideSpec], Optional[StoryBlock]]:
        spec = self.e._spec(slide_id)
        b = next((x for x in spec.blocks if x.type == "story"), None) if spec is not None else None
        return spec, b  # type: ignore[return-value]

    def owns(self, kind: str, args: dict) -> bool:
        if kind in ("sim_accept", "sim_dismiss"):
            return self.suggestion is not None and args.get("id") == self.suggestion.id
        return self._block(str(args.get("slide_id") or ""))[1] is not None

    def story(self) -> Optional[StoryboardSpec]:
        o = self._live()
        if o is None:
            return None
        _, b = self._block(o.slide_id)
        return b.story if b is not None else None

    # ---- intents --------------------------------------------------------------------------------------------
    async def on_intent(self, ev: RepresentationIntent) -> None:
        if ev.visual_kind != "story":
            return
        bad = safety.blocked(ev.text)
        if bad:
            log.info("[STORY] safety: a line with %r is not shown", bad)
            return
        o = self._live()
        if ev.strength == "end":
            if o is not None:
                await self.e._sims.end(f"heard {ev.text[:60]!r}")
            return
        if ev.strength == "cue" and o is not None and self._another(o, ev.text):
            o = None  # "Once upon a time ..." while a story is open: the next story (the last one keeps its figure)
        if ev.strength in ("cue", "setup") and o is None and (self.e._stage.imagine or self.e._scenes.imagine):
            log.info("[STORY] Imagine Mode is on: %r stays the stage's", ev.text[:60])  # only its End ends it
            return
        if ev.strength in ("cue", "setup") and o is None:
            setting = self.e.s.simulations
            if setting == "off":
                log.info("[STORY] cue ignored (setting off): %r", ev.text[:60])
                return
            if setting == "suggest" or ev.strength == "setup":
                await self._suggest(ev.text)
                return
            self.e.stats.ops["story_start"] += 1
            await self.start(ev.text, origin="cue", cue_segment=next(iter(ev.segment_ids), ""))
            return
        if o is None:
            return
        m = self.e._sims.mode
        if m is not None:
            m.heard_at = self.e.now()
            m.lines += 1
        await self.line(o, ev.text)

    def _another(self, o: _Open, text: str) -> bool:
        """A strong cue heard while a story is open starts the next story, unless it names the open story's hero."""
        p = protagonist(text)
        story = self._story(o)
        return not (p and self._find(story, p) is not None and self._find(story, p).id == o.protagonist)

    async def start(self, text: str, *, origin: str, cue_segment: str = "") -> None:
        e = self.e
        title = title_of(text)
        block = StoryBlock(story=StoryboardSpec(title=title))
        old = self.open
        mode = await e._sims.begin("story", "story", block.id, title, origin, cue_segment)
        if old is not None:  # another story began: the last one keeps its last scene as a figure
            await self._retire(old)
        mode.cues = (text,)  # test51: a recap bullet restating the cue ("Albert Einstein story begins") is dropped
        spec = await e._sims.place(mode, block, title, "spoken cue" if origin == "cue" else origin)
        self.open = o = _Open(block.id, spec.id, shown_at=e.now())
        await self._clear_suggestion()
        self.stats.stories += 1
        log.info("[STORY] open: %s (%s)", title, origin)
        who = protagonist(text)
        if who:
            story = self._story(o)
            story, cid = self._member(o, story, who)
            o.protagonist = cid
            self._said(o, [cid])
            await self._put(o, story)
        await self.line(o, text)

    # ---- lines ----------------------------------------------------------------------------------------------
    async def line(self, o: _Open, text: str) -> None:
        why = self._gate(o, text) if self.extractor is not None else ""
        if not why and not o.queue:
            await self._line(o, text)
            o.recent = (o.recent + [text])[-2:]
            return
        o.n += 1  # review: an id per queued line (a repeated line is another item)
        o.queue.append((o.n, text, why))  # ST3: behind a line that waits for its reading, every later line waits too
        if why:
            log.info("[STORY] llm asked (%s): %r", why, text[:60])
        if o.dtask is None or o.dtask.done():
            o.dtask = asyncio.create_task(self._drain(o), name="story:extract")

    def _gate(self, o: _Open, text: str) -> str:
        if o.waiting is not None or o.fragment or _FRAGMENT.fullmatch(text):
            return ""  # the words after "Ravi said," / a cut-off "In 1905," are read with their line
        key = _norm(text)
        if any(_norm(x) == key for sc in self._story(o).scenes for x in sc.lines):
            return ""  # a repeat changes nothing
        return sx.needs_llm(text, beats.speech(text), beats.beat(text))

    async def _drain(self, o: _Open) -> None:
        while o.queue:
            n, text, _ = o.queue[0]
            ans = None
            try:
                why = self._gate(o, text)  # review: at the head every line before it has landed (waiting, repeat)
                ans = await self._ask(o, text, why) if why else None
            except asyncio.CancelledError:
                raise
            except Exception:  # review: one fault never blocks the story's later lines
                log.exception("[STORY] llm reading failed for %r (the fast reading stays)", text[:60])
            async with self.e._lock:
                if self._live() is not o:
                    log.info("[STORY] llm: the story moved on, %d queued line(s) dropped", len(o.queue))
                    o.queue.clear()
                    return
                if not o.queue or o.queue[0][0] != n:
                    continue  # flushed meanwhile (the end cue)
                o.queue.popleft()
                try:
                    await self._line(o, text, ans)
                except Exception:
                    log.exception("[STORY] line %r could not be drawn", text[:60])
                o.recent = (o.recent + [text])[-2:]

    async def _ask(self, o: _Open, text: str, why: str) -> Optional[dict]:
        story = self._story(o)
        sp, b = beats.speech(text), beats.beat(text)
        cur = story.scenes[-1] if story.scenes else None
        scene = ""
        if cur is not None:
            names = [m.name for m in (story.member(c) for c in cur.cast) if m is not None]
            scene = " · ".join(x for x in (cur.when, cur.where, ", ".join(names)) if x)
        msgs = sx.messages([(c.name, c.gender) for c in story.cast], scene, o.recent, text, sx.fast_reading(sp, b))
        t0 = time.perf_counter()
        try:
            res = await asyncio.wait_for(self.extractor.read(msgs, text), sx.TIMEOUT_S + 2)  # type: ignore[attr-defined]
        except asyncio.CancelledError:
            raise
        except Exception as err:  # every model failed / too late: the fast reading stays (no fake fallback)
            self.stats.llm_failed += 1
            log.warning("[STORY] llm call failed (the fast reading stays): %s", err or type(err).__name__)
            return None
        self.stats.llm_calls += 1
        self.stats.llm_tokens += res.tokens
        self.stats.llm_counted += res.counted
        ans, bad = sx.check(res.answer, text, [c.name for c in story.cast], b)
        if ans is None:
            self.stats.llm_refused += 1
            log.info("[STORY] llm refused %s: %s (the fast reading stays), %d tokens, %.2f s%s", res.answer, bad,
                     res.tokens, time.perf_counter() - t0,
                     f"; text {res.text!r}" if res.answer is None else "")  # test55: what came instead of JSON
            return None
        self.stats.llm_taken += 1
        log.info("[STORY] llm answer taken: %s, %d tokens, %.2f s", ans, res.tokens, time.perf_counter() - t0)
        return ans

    async def flush(self) -> None:
        """ST3: the story ends: its queued lines land on the fast path first (the recap keeps every line)."""
        o = self._live()
        if o is None or not o.queue:
            return
        if o.dtask is not None and not o.dtask.done():
            o.dtask.cancel()
        while o.queue:
            _, text, _ = o.queue.popleft()
            await self._line(o, text)
        log.info("[STORY] llm: queued lines read on the fast path (the story ends)")

    async def settle(self) -> None:
        """Tests and replays: wait until every queued line has landed."""
        o = self.open
        while o is not None and o.dtask is not None and not o.dtask.done():
            await asyncio.gather(o.dtask, return_exceptions=True)

    async def _line(self, o: _Open, text: str, ans: Optional[dict] = None) -> None:
        story = self._story(o)
        if ans is not None and ans["type"] == "aside":
            log.info("[STORY] aside (llm): %r is not a story line", text[:60])
            return
        sp = beats.speech(text) if ans is None or ans["type"] != "narration" else None
        if ans is not None and ans["type"] == "speech":
            sp = beats.Speech(ans["who"], ans["kind"], ans["to"], beats.quote_only(ans["words"]))
        if o.waiting is not None and sp is None:  # the words after "Ravi said,"
            sp, o.waiting = beats.Speech(o.waiting.who, o.waiting.kind, o.waiting.to, beats.quote_only(text)), None
        if sp is not None and not sp.words:
            o.waiting = sp
            return
        if sp is not None:
            await self._put(o, self._bubble(o, story, sp))
            return
        if _FRAGMENT.fullmatch(text):  # test51: Whisper cut "In 1905," off its sentence: it joins the next line
            o.fragment = (o.fragment + " " + text.strip()).strip()
            return
        if o.fragment:
            first, _, rest = text.strip().partition(" ")
            joined = first.lower() if first.lower() in ("a", "an", "the", "his", "her", "their") else first
            text, o.fragment = f"{o.fragment} {joined} {rest}".strip(), ""
        b = beats.beat(text)
        if ans is not None and ans["type"] == "narration":
            b = _with(b, ans)
        if not b.caption and story.scenes:
            return
        lone = _LONE.fullmatch(text)
        if lone and story.scenes and not story.scenes[-1].where and self._find(story, lone.group(1)) is None \
                and lone.group(1).lower() not in beats.PERSON_NOUNS and lone.group(1).split()[0].lower() not in beats._NOT_NAME:
            # test55: Whisper cut "... taught at the Sorbonne" into "Sorbonne." alone: the open scene's place, no person
            cur = story.scenes[-1]
            b.where, b.names = lone.group(1), []
            new = self._picture(o, story, cur.model_copy(update={"where": b.where, "lines": cur.lines + [text]}), b)
            log.info("[STORY] %r alone: the place of scene %d", b.where, len(story.scenes))
            await self._put(o, story.model_copy(update={"scenes": story.scenes[:-1] + [new]}))
            return
        key = _norm(text)
        if any(_norm(x) == key for sc in story.scenes for x in sc.lines):
            log.info("[STORY] repeat: %r changes nothing", text[:60])  # M0: a repeated line is the same picture
            return
        await self._put(o, self._narrate(o, story, b, text))

    def _narrate(self, o: _Open, story: StoryboardSpec, b: beats.Beat, text: str) -> StoryboardSpec:
        cur = story.scenes[-1] if story.scenes else None
        known = {c.id for c in story.cast}
        here: list[str] = []
        for who in b.names + b.people:
            if len(story.cast) >= MAX_CAST and self._find(story, who) is None:
                continue
            story, cid = self._member(o, story, who)
            if cid not in here:
                here.append(cid)
        newcomer = any(cid not in known for cid in here)
        pr = beats.pronoun(text) if not here else beats.subject(text)
        if pr in ("he", "she"):  # ST2: "she moved to Berlin": her figure, not everyone of the scene before
            story, cid = self._resolve(o, story, pr, not_=here[0] if len(here) == 1 else "",
                                       learn=beats.subject(text) == pr,  # "Her dream was ...": not learned
                                       pool=None if not here else [c.id for c in story.cast if c.id not in here])
            here = ([cid] if cid and cid not in here else []) + here  # "in 1895, she met Pierre": both stand there
        elif pr == "they" and cur is not None and not here:
            here = list(cur.cast)
        self._said(o, here)
        place = _bare(b.where)
        back = next((j for j in range(len(story.scenes) - 2, -1, -1) if place and _bare(story.scenes[j].where) == place),
                    None) if not (b.marker or b.when or newcomer) else None
        if back is not None and (cur is None or _bare(cur.where) != place):
            # test51: "the drop starts in the ocean" again: that scene shows again (a place said twice is one scene)
            sc = story.scenes[back]
            sc = sc.model_copy(update={"caption": b.caption or sc.caption, "lines": sc.lines + [text],
                                       "cast": sc.cast + [c for c in here if c not in sc.cast]})
            o.shown_at, o.held = self.e.now(), False
            log.info("[STORY] %r again: scene %d shows again", b.where, back + 1)
            return story.model_copy(update={"scenes": story.scenes[:back] + [sc] + story.scenes[back + 1:],
                                            "shown": back})
        if cur is not None and cur.lines and cur.where and b.where and b.where.lower() == cur.where.lower() \
                and not b.marker and not b.when:
            cut = False  # "in Bern" again: the same place
        else:
            cut = cur is None or bool(cur.lines) and (b.cuts or newcomer or len(cur.lines) >= MAX_SCENE_LINES)
        if not cut and cur is not None:
            cast = cur.cast + [c for c in here if c not in cur.cast]
            new = cur.model_copy(update={"caption": b.caption or cur.caption, "lines": cur.lines + [text],
                                         "when": cur.when or b.when, "where": cur.where or b.where, "cast": cast})
            if not cur.query:
                new = self._picture(o, story, new, b)
            return story.model_copy(update={"scenes": story.scenes[:-1] + [new]})
        if len(story.scenes) >= MAX_SCENES:
            log.info("[STORY] %d scenes: the last one grows", MAX_SCENES)
            return story
        if not here:  # "he wrote four papers": the people of the scene before (a journey: its traveller)
            here = list(cur.cast) if cur is not None else []
        if o.protagonist and o.protagonist not in here and (not here or self._journey(story, o)):
            here = [o.protagonist] + here
        scene = StoryScene(caption=b.caption, lines=[text], when=b.when, where=b.where, cast=here[:MAX_CAST],
                           camera=CAMERAS[len(story.scenes) % len(CAMERAS)])
        scene = self._picture(o, story, scene, b)
        self.stats.scenes += 1
        log.info("[STORY] scene %d: %r (when %r, where %r, query %r)", len(story.scenes) + 1, b.caption[:50],
                 b.when, b.where, scene.query)
        story = story.model_copy(update={"scenes": story.scenes + [scene]})
        return self._advance(o, story)

    def _journey(self, story: StoryboardSpec, o: _Open) -> bool:
        p = story.member(o.protagonist)
        return p is not None and not p.name[:1].isupper()  # "a drop of water": in every scene; a named person not

    def _bubble(self, o: _Open, story: StoryboardSpec, sp: beats.Speech) -> StoryboardSpec:
        story, who = self._speaker(o, story, sp.who)
        if not who:
            return story
        to = ""
        if sp.to:
            story, to = self._speaker(o, story, sp.to, not_=who)
        if not story.scenes:
            story = story.model_copy(update={"scenes": [StoryScene(camera=CAMERAS[0])]})
        i = story.shown if 0 <= story.shown < len(story.scenes) else len(story.scenes) - 1
        i = len(story.scenes) - 1 if not o.held else i  # the newest scene is where the talk happens
        sc = story.scenes[i]
        cast = list(sc.cast)
        for c in (who, to):
            if c and c not in cast:
                if len(cast) >= MAX_CAST:  # room for the speaker: the first one who is not in this talk steps out
                    out = next((x for x in cast if x not in (who, to, o.last_speaker)), cast[0])
                    cast.remove(out)
                cast.append(c)
        if sc.bubbles and sc.bubbles[-1].speaker == who and _norm(sc.bubbles[-1].text) == _norm(sp.words):
            log.info("[STORY] repeat: %r again changes nothing", sp.words[:60])  # test55: the line said twice
            return story
        bub = Bubble(speaker=who, text=sp.words, kind=sp.kind, to=to)  # type: ignore[arg-type]
        sc = sc.model_copy(update={"cast": cast[:MAX_CAST], "bubbles": (sc.bubbles + [bub])[-MAX_BUBBLES:]})
        o.last_speaker = who
        self._said(o, [x for x in (to, who) if x])
        self.stats.bubbles += 1
        log.info("[STORY] %s %s: %r", (story.member(who) or CastMember(id="", name="?")).name, sp.kind, sp.words[:60])
        scenes = story.scenes[:i] + [sc] + story.scenes[i + 1:]
        story = story.model_copy(update={"scenes": scenes})
        if story.shown != i:  # the talk is happening now: its scene shows at once
            story = story.model_copy(update={"shown": i})
            o.shown_at = self.e.now()
        return story

    # ---- cast -----------------------------------------------------------------------------------------------
    def _find(self, story: StoryboardSpec, said: str) -> Optional[CastMember]:
        low = said.lower().strip()
        bare = re.sub(r"^(?:a|an|the|his|her|their|my|our|one)\s+", "", low)
        named = said[:1].isupper() and bare == low  # ST2: "The boy" at a sentence start is no name
        for c in story.cast:
            n = c.name.lower()
            nb = re.sub(r"^(?:a|an|the|his|her|their|my|our|one)\s+", "", n)
            ws, wn = set(bare.split()), set(nb.split())
            if bare == nb or named and (ws <= wn or wn <= ws) and c.name[:1].isupper():
                return c  # "Einstein" is "Albert Einstein"; ST2: "Pierre Curie" is not "Marie Curie"
            if not named and beats.head_noun(bare) and beats.head_noun(bare) == beats.head_noun(nb):
                return c  # "the clerk" is "a young clerk"
        return None

    def _member(self, o: _Open, story: StoryboardSpec, said: str) -> tuple[StoryboardSpec, str]:
        c = self._find(story, said) or self._near(o, story, said)
        if c is not None:
            return story, c.id
        name = said.strip()
        noun = beats.picture_noun(name)
        cid = f"c{len(story.cast) + 1}"
        member = CastMember(id=cid, name=name, noun=noun, gender=beats.gender_of(name),  # type: ignore[arg-type]
                            look=len(story.cast) % LOOKS)
        fig = self._figure(story, member, o)
        o.member_emoji[cid] = fig
        member = member.model_copy(update={"picture": self._emoji_url(o, fig)})
        return story.model_copy(update={"cast": story.cast + [member]}), cid

    def _near(self, o: _Open, story: StoryboardSpec, said: str) -> Optional[CastMember]:
        """test53: Whisper heard "Mary" for Marie: a single new first name very like a name word of the hero or of
        someone in the scene (same first letter) is that person."""
        w = said.strip()
        if not re.fullmatch(r"[A-Z][a-z]+", w):
            return None
        scene = story.scenes[-1] if story.scenes else None
        ids = {o.protagonist} | set(scene.cast if scene is not None else [])
        for c in story.cast:
            if c.id not in ids or not c.name[:1].isupper():
                continue
            for part in c.name.split():
                if part[:1] == w[:1] and part != w and difflib.SequenceMatcher(None, w.lower(), part.lower()).ratio() >= NEAR_NAME:
                    log.info("[STORY] %r read as %r (a name like it)", w, c.name)
                    return c
        return None

    def _figure(self, story: StoryboardSpec, c: CastMember, o: _Open) -> str:
        """ST2: a cast member's emoji: a face of the said gender; a name of unsaid gender gets a neutral face of its
        own (two people never share one); else its noun's picture."""
        young = YOUNG.get(beats.head_noun(c.name), "")
        if young:
            return young
        if c.gender and (c.noun in ("person", "man", "woman") or c.name[:1].isupper()):
            return FACES[c.gender]
        if c.noun == "person":
            used = {v for k, v in o.member_emoji.items() if k != c.id}
            free = [f for f in NEUTRAL_FACES if f not in used]  # review: a learned gender must not free a face twice
            n = sum(1 for x in story.cast if x.id != c.id and x.noun == "person")
            return free[0] if free else NEUTRAL_FACES[n % len(NEUTRAL_FACES)]
        own = self._emoji_name(c.noun)
        return own or (FACES[c.gender] if c.gender else "")  # "a king" with no picture of its own: a man's face

    def _person(self, c: CastMember) -> bool:
        return bool(c.gender) or c.name[:1].isupper() or beats.head_noun(c.name) in beats.PERSON_NOUNS

    def _fits(self, story: StoryboardSpec, cid: str, g: str) -> bool:
        c = story.member(cid)
        return c is not None and self._person(c) and c.gender in ("", g)

    def _resolve(self, o: _Open, story: StoryboardSpec, g: str, not_: str = "",
                 pool: Optional[list[str]] = None, learn: bool = True) -> tuple[StoryboardSpec, str]:
        """ST2: "he" / "she" -> the most recently said person of that gender; else the one person of unsaid gender
        (whose gender is then learned: said words); several of unsaid gender -> the most recent one, nothing learned."""
        order = {cid: k for k, cid in enumerate(o.mentioned)}
        people = [c for c in story.cast if c.id != not_ and self._person(c) and (pool is None or c.id in pool)]
        people.sort(key=lambda c: order.get(c.id, -1), reverse=True)
        same = [c for c in people if c.gender == g]
        if same:
            return story, same[0].id
        unknown = [c for c in people if not c.gender]
        if len(unknown) == 1:
            return (self._learn(o, story, unknown[0].id, g) if learn else story), unknown[0].id
        if o.protagonist in [c.id for c in unknown]:
            return story, o.protagonist  # test53: several of unsaid gender: "she" is the story's hero
        return story, (unknown[0].id if unknown else "")

    def _learn(self, o: _Open, story: StoryboardSpec, cid: str, g: str) -> StoryboardSpec:
        c = story.member(cid)
        if c is None or c.gender or g not in ("he", "she"):
            return story
        c = c.model_copy(update={"gender": g})
        fig = self._figure(story, c, o)
        if fig != o.member_emoji.get(cid):
            o.member_emoji[cid] = fig
            c = c.model_copy(update={"picture": self._emoji_url(o, fig)})
        log.info("[STORY] %r is %r (said)", c.name, g)
        return story.model_copy(update={"cast": [c if x.id == cid else x for x in story.cast]})

    def _said(self, o: _Open, ids: list[str]) -> None:
        for cid in ids:
            if cid in o.mentioned:
                o.mentioned.remove(cid)
            o.mentioned.append(cid)

    def _speaker(self, o: _Open, story: StoryboardSpec, said: str, not_: str = "") -> tuple[StoryboardSpec, str]:
        g = {"him": "he", "her": "she", "them": "they"}.get(said.lower(), said.lower())
        if g in ("he", "she"):
            # ST2: "she replied": the one the last speaker spoke to, else the one of her gender in the talk
            scene = story.scenes[-1] if story.scenes else None
            last = scene.bubbles[-1] if scene is not None and scene.bubbles else None
            if last is not None and last.to and last.to != not_ and self._fits(story, last.to, g):
                return self._learn(o, story, last.to, g), last.to
            story, cid = self._resolve(o, story, g, not_=not_ or o.last_speaker,
                                       pool=list(scene.cast) if scene is not None else None)
            if cid:
                return story, cid
            log.info("[STORY] %r: nobody of that gender in the talk: no bubble", said)
            return story, ""
        if said.lower() in _PRONOUN:  # the other one of the talk (pronouns are never guessed further)
            scene = story.scenes[-1] if story.scenes else None
            pool = [c for c in (scene.cast if scene is not None else [x.id for x in story.cast])
                    if c != (not_ or o.last_speaker)]
            if pool:
                return story, pool[0]
            if o.last_speaker and o.last_speaker != not_:
                return story, o.last_speaker
            if o.protagonist and o.protagonist != not_:
                return story, o.protagonist
        if said[:1].isupper() and self._find(story, said) is None:
            # test51: Whisper heard "Harsha said, me too" for Asha: a name very like one in the scene is that one
            scene = story.scenes[-1] if story.scenes else None
            near = [(difflib.SequenceMatcher(None, said.lower(), c.name.lower()).ratio(), c) for c in story.cast
                    if c.id != not_ and c.name[:1].isupper() and (scene is None or c.id in scene.cast)]
            best = max(near, key=lambda x: x[0], default=(0.0, None))
            if best[1] is not None and best[0] >= SAME_NAME:
                log.info("[STORY] %r read as %r (a name in the scene)", said, best[1].name)
                return story, best[1].id
        return self._member(o, story, said)

    # ---- pictures -------------------------------------------------------------------------------------------
    def _picture(self, o: _Open, story: StoryboardSpec, scene: StoryScene, b: beats.Beat) -> StoryScene:
        q, noun = self._query(story, scene, b)
        upd: dict = {"query": q}
        if noun:
            upd["emoji"] = self._emoji(o, noun)
            o.scene_emoji[scene.id] = self._emoji_name(noun)
        scene = scene.model_copy(update=upd)
        if q and q.lower() in o.images:  # the same place again: the same picture, no search
            url, alt, credit = o.images[q.lower()]
            return scene.model_copy(update={"image": url, "image_alt": alt, "credit": credit})
        if q and self.images:
            rid = uuid.uuid4().hex[:12]
            o.requests[rid] = scene.id
            self.asked[rid] = (o.slide_id, scene.id)
            while len(self.asked) > 64:
                self.asked.pop(next(iter(self.asked)))
            o.outbox.append(ImageRequested(request_id=rid, slide_id=o.slide_id, query=q, reason=f"story:{scene.id}",
                                           exclude=list(o.used)))
        return scene

    def _query(self, story: StoryboardSpec, scene: StoryScene, b: beats.Beat) -> tuple[str, str]:
        """(the image search, the emoji noun) from said words only."""
        where = b.where or scene.where
        bare = re.sub(r"^(?:the|a|an|its|his|her|their|our)\s+", "", where)
        if where and where[:1].isupper():
            return where, ""
        if bare:  # "at the park": the place is the backdrop, the people stand in it
            return bare, bare
        names = [story.member(c).name for c in scene.cast if story.member(c) and story.member(c).name[:1].isupper()]  # type: ignore[union-attr]
        if b.names and names:
            # test55: "Mary" read as Marie Curie: the search is the person in the scene, not the misheard word
            full = next((n for n in names if set(n.split()) & set(b.names[0].split())), names[0])
            return full, "person"
        if b.people:
            p = re.sub(r"^(?:a|an|the|one|his|her|their|my)\s+", "", b.people[0])
            return p, beats.picture_noun(p)
        p = story.member(scene.cast[0]) if scene.cast else None
        if p is not None:
            if p.name[:1].isupper():
                return p.name, "person"
            return re.sub(r"^(?:a|an|the|one)\s+", "", p.name), p.noun
        return "", ""

    def _emoji_name(self, noun: str) -> str:
        return (pics.person(noun) or self.emoji.match(noun)) if noun else ""

    def _emoji(self, o: _Open, noun: str) -> str:
        return self._emoji_url(o, self._emoji_name(noun))

    def _emoji_url(self, o: _Open, name: str) -> str:
        if not name:
            return ""
        url = pics.cached(name, self.pics_dir)
        if url or not self.fetch_pictures or name in o.fetching:
            return url
        o.fetching.add(name)
        o.tasks.append(asyncio.create_task(self._fetch(o, name), name="story:emoji"))
        return ""

    async def _fetch(self, o: _Open, name: str) -> None:
        url = await asyncio.to_thread(pics.fetch, name, self.pics_dir)
        if not url:
            return
        async with self.e._lock:
            if self._live() is not o:
                return
            story = self._story(o)
            # the picture now on disk: fill every cast member / scene that waited for it
            cast = [c.model_copy(update={"picture": url}) if not c.picture and o.member_emoji.get(c.id) == name
                    else c for c in story.cast]
            scenes = [s.model_copy(update={"emoji": url}) if not s.emoji and o.scene_emoji.get(s.id) == name
                      else s for s in story.scenes]
            await self._put(o, story.model_copy(update={"cast": cast, "scenes": scenes}))

    async def on_image(self, ev: ImageReady) -> bool:
        """An image for a story scene (True: it was one of ours)."""
        if self.asked.pop(ev.request_id, None) is None:
            return False
        o = self.open
        if o is None or ev.request_id not in o.requests:
            log.info("[STORY] image %r came after its story ended: not shown", ev.query)
            return True
        sid = o.requests.pop(ev.request_id)
        if self._live() is not o:
            return True
        if not ev.images:
            log.info("[STORY] image %r: none (%s)", ev.query, ev.reason)
            if sid not in o.retried and re.search(r"download|network|timeout|internal", ev.reason or "", re.I):
                o.retried.add(sid)  # test51: "downloads failed" 3x on a flaky network: one more try
                rid = uuid.uuid4().hex[:12]
                o.requests[rid] = sid
                self.asked[rid] = (o.slide_id, sid)
                await self.e.bus.publish(ImageRequested(request_id=rid, slide_id=o.slide_id, query=ev.query,
                                                        reason=f"story:{sid}", exclude=list(o.used), deeper=True))
            return True
        i = ev.images[0]
        url = f"/media/{i.get('id')}.jpg"
        credit = " · ".join(x for x in (str(i.get("source") or ""), str(i.get("licence") or ""),
                                        str(i.get("author") or "")) if x)
        alt = str(i.get("alt") or ev.query)[:160]
        o.images[ev.query.lower()] = (url, alt, credit)
        o.used.append(str(i.get("id")))
        story = self._story(o)
        scenes = [s.model_copy(update={"image": url, "image_alt": alt, "credit": credit}) if s.id == sid else s
                  for s in story.scenes]
        self.stats.images += 1
        log.info("[STORY] image for %r in %.1f s (%s)", ev.query, ev.seconds, credit or "?")
        await self._put(o, story.model_copy(update={"scenes": scenes}))
        return True

    # ---- the clock ------------------------------------------------------------------------------------------
    def _advance(self, o: _Open, story: StoryboardSpec) -> StoryboardSpec:
        last = len(story.scenes) - 1
        if last < 0:
            return story
        o.held = False
        if story.shown < last and (self.e.now() - o.shown_at >= DWELL_S or not story.scenes[story.shown].lines):
            o.shown_at = self.e.now()
            return story.model_copy(update={"shown": last})  # the narration is here now (no queue behind it)
        if story.shown > last:
            return story.model_copy(update={"shown": last})
        return story

    async def tick(self) -> None:
        o = self.open
        if o is not None and self._live() is None:  # its mode ended (Back to slides, another one began)
            await self._retire(o)
            o = None
        if o is not None and not o.held:
            story = self._story(o)
            if story.shown < len(story.scenes) - 1 and self.e.now() - o.shown_at >= DWELL_S:
                o.shown_at = self.e.now()
                await self._put(o, story.model_copy(update={"shown": len(story.scenes) - 1}))
        if self.suggestion is not None and self.e.now() > self.suggestion.until:
            await self._clear_suggestion()

    async def _retire(self, o: _Open) -> None:
        if self.open is o:
            self.open = None
        for t in o.tasks + ([o.dtask] if o.dtask is not None else []):
            if not t.done():
                t.cancel()
        spec, b = self._block(o.slide_id)
        if spec is None or b is None:
            return
        if not b.story.scenes:
            log.info("[STORY] the story ended before any scene: its slide goes")
            await self.e._sims.take_off(spec)
        elif not b.still:
            still = b.model_copy(update={"still": True})
            await self.e._commit(spec.model_copy(update={"blocks": [still if x.id == b.id else x for x in spec.blocks]}))

    # ---- writing --------------------------------------------------------------------------------------------
    def _story(self, o: _Open) -> StoryboardSpec:
        _, b = self._block(o.slide_id)
        return b.story if b is not None else StoryboardSpec()

    async def _put(self, o: _Open, story: StoryboardSpec) -> None:
        spec, b = self._block(o.slide_id)
        if spec is None or b is None:
            return
        if story.model_dump(exclude={"version"}) != b.story.model_dump(exclude={"version"}):
            new = b.model_copy(update={"story": story.model_copy(update={"version": b.story.version + 1})})
            await self.e._commit(spec.model_copy(update={"blocks": [new if x.id == b.id else x for x in spec.blocks]}))
        m = self.e._sims.mode
        if m is not None and m.block_id == o.block_id:
            m.own_recap = recap(story)  # ST2 (test52): the recap is the said captions, not the model's paraphrase
        o.tasks = [t for t in o.tasks if not t.done()]
        out, o.outbox = o.outbox, []
        for req in out:  # after the commit: an answer always finds its scene
            await self.e.bus.publish(req)

    # ---- Suggest -------------------------------------------------------------------------------------------
    async def _suggest(self, text: str) -> None:
        await self._clear_suggestion()
        self.suggestion = _Suggestion(uuid.uuid4().hex[:12], text, self.e.now() + SUGGEST_S)
        await self.e.bus.publish(SimulationSuggestion(id=self.suggestion.id, template="story",
                                                      name=title_of(text), text=text[:200]))
        log.info("[STORY] suggested: %r", text[:60])

    async def _clear_suggestion(self) -> None:
        s, self.suggestion = self.suggestion, None
        if s is not None:
            await self.e.bus.publish(SimulationSuggestion(id=s.id, template="story", active=False))

    # ---- the teacher's commands -----------------------------------------------------------------------------
    async def on_command(self, kind: str, args: dict) -> None:
        if kind in ("sim_accept", "sim_dismiss"):
            s = self.suggestion
            if s is None:
                return
            if kind == "sim_dismiss":
                await self._clear_suggestion()
                return
            self.e.stats.ops["teacher_story_accept"] += 1
            await self.start(s.text, origin="policy")
            return
        spec, b = self._block(str(args.get("slide_id") or ""))
        if spec is None or b is None:
            return
        self.e.stats.ops[f"teacher_story_{kind}"] += 1
        m = self.e._sims.mode
        mine = m is not None and m.kind == "story" and m.block_id == b.id
        if kind == "sim_remove":
            if mine:
                await self.e._sims.end("the teacher removed the story")
            await self.e._sims.take_off(spec)
            log.info("teacher removed the story %r", spec.title)
            return
        if kind in ("sim_prev", "sim_next") and b.story.scenes:
            to = max(0, min(len(b.story.scenes) - 1, b.story.shown + (1 if kind == "sim_next" else -1)))
            if to != b.story.shown:
                o = self.open if mine else None
                if o is not None:
                    o.held, o.shown_at = True, self.e.now()
                new = b.model_copy(update={"story": b.story.model_copy(update={"shown": to,
                                                                                "version": b.story.version + 1})})
                await self.e._commit(spec.model_copy(update={"blocks": [new if x.id == b.id else x
                                                                        for x in spec.blocks]}))


_FRAGMENT = re.compile(r"\W*[\w']+(?:\s+[\w']+){0,3}\s*,\s*")  # "In 1905," / "One day," alone on a line
_LONE = re.compile(r"\W*((?:[A-Z][a-z]+)(?:\s+[A-Z][a-z]+){0,2})\W*")  # "Sorbonne." alone on a line
_ARTICLE = re.compile(r"^(?:the|a|an|its|his|her|their|our)\s+")
NEAR_NAME = 0.6        # test53: "Mary" (0.67) for "Marie" with the same first letter
SAME_NAME = 0.75       # a speaker this similar to a name in the scene is that one (Whisper: "Harsha" for "Asha")


def _with(b: beats.Beat, ans: dict) -> beats.Beat:
    """ST3: the fast beat plus what the LLM read in the same line (said words only, checked by story.extract)."""
    when = ans["when"]
    if when and not b.when:
        y = re.search(r"\b(?:1[0-9]|20)\d{2}\b", when)
        b.when = y.group(0) if y else when.lower()
    if ans["where"] and not b.where:
        b.where = ans["where"]
    have = {x.lower() for x in b.names + b.people}
    for p in ans["people"]:
        if p.lower() not in have:
            (b.names if p[:1].isupper() else b.people).append(p if p[:1].isupper() else p.lower())
    if ans["new_scene"] and not b.cuts:
        b.marker = "then"
    return b


def _bare(where: str) -> str:
    return _ARTICLE.sub("", where.lower().strip())


def _norm(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def protagonist(text: str) -> str:
    """The cue's traveller / hero as said: "a drop of water", "Albert Einstein", "a red blood cell" ("" = none)."""
    m = _PROTAGONIST.search(text)
    if not m:
        return ""
    words = re.findall(r"[A-Za-z']+|[,.;:!?]", text[m.end():])
    out: list[str] = []
    for w in words:
        if w in ",.;:!?" or (out and w.lower() in _STOP):
            break
        if w.lower() == "of" and (not out or "of" in [x.lower() for x in out]):
            break
        out.append(w)
        if len(out) >= 5:
            break
    while out and out[-1].lower() in ("of", "a", "an", "the"):
        out.pop()
    if not out or (len(out) == 1 and out[0].lower() in ("a", "an", "the", "one")):
        return ""
    return " ".join(out)


def recap(story: StoryboardSpec) -> list[Piece]:
    """ST2: the story's recap: one bullet per scene, its said caption (its said year in front). Nothing else."""
    texts: list[str] = []
    for sc in story.scenes:
        dated = False
        for line in sc.lines:  # test53: every narrative line (a later line of the scene no longer hides one)
            t = beats.caption(line)
            if len(t.split()) < 4 or story_ends(line, open_=True):
                continue  # "Marie Curie": the cue's name alone is the title; the end line is no point
            if sc.when[:1].isdigit() and not dated:
                dated = True
                t = t if sc.when in t else f"{sc.when}: {t}"
            if t not in texts:
                texts.append(t)
    return [Piece(kind="points", texts=tuple(texts))] if texts else []


def title_of(text: str) -> str:
    """The story's title from its cue (said words): its hero ("A drop of water"), else a said name or place and year
    ("Bern, 1905"), else "Story"."""
    p = protagonist(text)
    if not p:
        b = beats.beat(text)
        head = " and ".join(b.names[:2]) or (b.where if b.where[:1].isupper() else "")
        return ", ".join(x for x in (head, b.when if b.when[:1].isdigit() else "") if x) or "Story"
    return p[:1].upper() + p[1:]
