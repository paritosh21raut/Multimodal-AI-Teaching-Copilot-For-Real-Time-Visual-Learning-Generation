"""AssessService (F-011): the single writer of the quiz / test. Teacher commands come on the bus (from /control);
students' calls come from the server (`join` / `me` / `answer` / `submit`, by token). A ticker advances the clock.
Every change publishes `AssessState`: `control` (keys included) for /control, `public` (no keys before due) for
/display and /view. The LLM only writes the questions (a `QuestionSource`, slice 2); everything else is code.

Commands: assess_create {kind, count, seconds, minutes, show_answers, current, lectures, chapters}, assess_edit {qid,
text?, options?, answer?}, assess_add {text, options, answer, after?}, assess_delete {qid}, assess_regen {qid},
assess_open, assess_start, assess_pause, assess_resume, assess_hold {on}, assess_next, assess_end, assess_close,
assess_discard, assess_release {roll}.
Opening the lobby pauses a live lecture; closing resumes it (only when the assessment paused it).
"""
from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional, Protocol

from copilot.assess.model import (
    DEFAULT_COUNT, DEFAULT_MINUTES, DEFAULT_SECONDS, MAX_COUNT, MAX_MINUTES, MAX_SECONDS, MIN_MINUTES, MIN_SECONDS,
    OPTIONS, AssessError, Assessment, Question,
)
from copilot.assess.store import AssessmentStore
from copilot.core.bus import EventBus
from copilot.core.events import (
    AssessState, Command, CommandReceived, Event, Lifecycle, LifecycleChanged, new_id,
)

log = logging.getLogger(__name__)

COMMANDS = {"assess_create", "assess_edit", "assess_add", "assess_delete", "assess_regen", "assess_open",
            "assess_start", "assess_pause", "assess_resume", "assess_hold", "assess_next", "assess_end",
            "assess_close", "assess_discard", "assess_release"}
TICK_S = 0.25


@dataclass
class Prepared:
    """What the questions are written from (kept for Regenerate)."""
    title: str
    sources: list[str]
    material: Any = None  # the source's own content (slice 2: the lectures' taught content)


@dataclass
class Spent:
    calls: int = 0
    tokens: int = 0


class QuestionSource(Protocol):
    """The gated LLM part (slice 2). `prepare` resolves From (this lecture / lectures / chapters) to bounded
    content; `questions` writes `count` MCQs from it, avoiding the given stems."""
    @property
    def available(self) -> bool: ...

    async def prepare(self, args: dict[str, Any]) -> Prepared: ...

    async def questions(self, prepared: Prepared, count: int, avoid: list[str], spent: Spent) -> list[Question]: ...


def _int(v: Any, default: int, lo: int, hi: int) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return default


@dataclass
class _Job:
    task: asyncio.Task
    qid: str = ""  # "" = the whole set


class AssessService:
    def __init__(self, bus: EventBus, store: AssessmentStore, session_id: str,
                 source: Optional[QuestionSource] = None, clock: Callable[[], float] = time.time,
                 tick_s: float = TICK_S) -> None:
        self._bus = bus
        self.store = store
        self.session_id = session_id
        self.source = source
        self.clock = clock
        self.tick_s = tick_s
        self.current: Optional[Assessment] = None
        self._prepared: dict[str, Prepared] = {}
        self._jobs: list[_Job] = []
        self._notice = ""                 # why the teacher's last action was refused / failed (control only)
        self._lifecycle = Lifecycle.STARTING
        self._paused_lecture = False      # this assessment paused the lecture: resume it on close
        self._dirty = False
        self._ticker: Optional[asyncio.Task] = None
        self.on_generated: Optional[Callable[[Assessment, Spent], None]] = None  # terminal line (app)

    def attach(self, ticker: bool = True) -> None:
        self._bus.subscribe("assess", self._on_event, [CommandReceived, LifecycleChanged])
        if ticker:
            self._ticker = asyncio.create_task(self._tick_loop(), name="assess:ticker")

    async def close(self) -> None:
        for job in self._jobs:
            job.task.cancel()
        if self._ticker is not None:
            self._ticker.cancel()
            try:
                await self._ticker
            except asyncio.CancelledError:
                pass
        self.flush()

    # ---- state ------------------------------------------------------------------------------------------
    def state(self) -> AssessState:
        a, now = self.current, self.clock()
        control: dict[str, Any] = {}
        public: dict[str, Any] = {}
        if a is not None:
            control = a.control_view(now)
            control["regenerating"] = [j.qid for j in self._jobs if j.qid]
            if a.status not in ("generating", "draft"):  # students see it from the lobby on
                public = a.public_view(now)
        return AssessState(control=control, public=public, notice=self._notice,
                           llm=bool(self.source and self.source.available), now=now)

    async def announce(self) -> None:
        await self._bus.publish(self.state())

    def flush(self) -> None:
        if self._dirty and self.current is not None:
            self.store.save(self.current)
        self._dirty = False

    def _save(self) -> None:
        self._dirty = True

    async def step(self) -> None:
        """One clock step: deadlines, then publish + save when something changed."""
        a = self.current
        if a is not None and a.tick(self.clock()):
            self._save()
            await self.announce()
        self.flush()

    async def _tick_loop(self) -> None:
        while True:
            await asyncio.sleep(self.tick_s)
            try:
                await self.step()
            except Exception:  # a bug must not stop the clock of a running quiz
                log.exception("assessment tick failed")

    # ---- teacher commands -------------------------------------------------------------------------------
    async def _on_event(self, event: Event) -> None:
        if isinstance(event, LifecycleChanged):
            self._lifecycle = event.state
            return
        assert isinstance(event, CommandReceived)
        kind, args = event.command.kind, event.command.args
        if kind not in COMMANDS:
            return
        self._notice = ""
        try:
            await self._command(kind, args)
        except AssessError as e:
            self._notice = str(e)
            log.info("%s refused: %s", kind, e)
        await self.announce()

    def _need(self, *status: str) -> Assessment:
        a = self.current
        if a is None or (status and a.status not in status):
            raise AssessError("no quiz or test " + ("open" if status else "prepared"))
        return a

    async def _command(self, kind: str, args: dict[str, Any]) -> None:
        now = self.clock()
        if kind == "assess_create":
            await self._create(args)
            return
        a = self._need()
        if kind == "assess_edit":
            a.edit(str(args.get("qid", "")), args.get("text"), args.get("options"), args.get("answer"))
        elif kind == "assess_add":
            q = Question(id=new_id(), text=str(args.get("text") or "").strip(),
                         options=[str(o or "").strip() for o in (args.get("options") or [])][:OPTIONS],
                         answer=_int(args.get("answer"), -1, -1, OPTIONS - 1))
            a.add(q, str(args.get("after") or "") or None)
        elif kind == "assess_delete":
            a.delete(str(args.get("qid", "")))
        elif kind == "assess_regen":
            self._regen(a, str(args.get("qid", "")))
        elif kind == "assess_open":
            a.open(now)
            await self._pause_lecture()
        elif kind == "assess_start":
            a.start(now)
        elif kind == "assess_pause":
            a.pause(now)
        elif kind == "assess_resume":
            a.resume(now)
        elif kind == "assess_hold":
            a.hold(bool(args.get("on")))
        elif kind == "assess_next":
            a.next(now)
        elif kind == "assess_end":
            a.end(now)
        elif kind == "assess_release":
            a.release(str(args.get("roll", "")))
        elif kind in ("assess_close", "assess_discard"):
            if kind == "assess_close" and a.status in ("lobby", "running"):
                raise AssessError("end it first")
            self._cancel_jobs()
            self._save()
            self.flush()
            self.current = None
            await self._resume_lecture()
            return
        self._save()

    async def _create(self, args: dict[str, Any]) -> None:
        if self.current is not None and self.current.status in ("lobby", "running"):
            raise AssessError("a quiz or test is open: end it first")
        kind = "test" if args.get("kind") == "test" else "quiz"
        self._cancel_jobs()
        a = Assessment(id=f"{time.strftime('%Y%m%d-%H%M%S')}-{new_id()[:4]}", kind=kind,
                       lecture_id=self.session_id, created=self.clock(),
                       count=_int(args.get("count"), DEFAULT_COUNT, 1, MAX_COUNT),
                       seconds=_int(args.get("seconds"), DEFAULT_SECONDS, MIN_SECONDS, MAX_SECONDS),
                       minutes=_int(args.get("minutes"), DEFAULT_MINUTES, MIN_MINUTES, MAX_MINUTES),
                       show_answers=bool(args.get("show_answers", True)), status="generating")
        self.current = a
        if self.source is None or not self.source.available:
            a.set_questions([], "Writing questions needs the LLM, which is off in this run. Add questions yourself.")
            self._save()
            return
        self._jobs.append(_Job(asyncio.create_task(self._generate(a, dict(args)), name="assess:generate")))

    async def _generate(self, a: Assessment, args: dict[str, Any]) -> None:
        assert self.source is not None
        spent = Spent()
        try:
            prepared = await self.source.prepare(args)
            a.title, a.sources = prepared.title, list(prepared.sources)
            self._prepared[a.id] = prepared
            qs = await self.source.questions(prepared, a.count, [], spent)
            short = f"{len(qs)} of {a.count} questions written" if len(qs) < a.count else ""
            a.set_questions(qs, short)
        except AssessError as e:
            a.set_questions([], str(e))
        except asyncio.CancelledError:
            raise
        except Exception as e:  # a bug: the teacher sees why, the draft stays usable by hand
            log.exception("question generation failed")
            a.set_questions([], f"unexpected error: {type(e).__name__}: {e}")
        finally:
            self._jobs = [j for j in self._jobs if j.task is not asyncio.current_task()]
        a.tokens += spent.tokens
        log.info("%s questions: %d written (%d LLM calls, %d tokens)%s", a.kind, len(a.questions), spent.calls,
                 spent.tokens, f"; {a.error}" if a.error else "")
        if self.on_generated is not None:
            self.on_generated(a, spent)
        self._save()
        self.flush()
        if self.current is a:
            await self.announce()

    def _regen(self, a: Assessment, qid: str) -> None:
        a.question(qid)
        if a.status not in ("draft", "lobby"):
            raise AssessError("questions can be changed only before Start")
        prepared = self._prepared.get(a.id)
        if prepared is None or self.source is None or not self.source.available:
            raise AssessError("Regenerate needs the LLM and the lectures this set was written from")
        if any(j.qid == qid for j in self._jobs):
            return
        self._jobs.append(_Job(asyncio.create_task(self._regen_one(a, qid, prepared), name="assess:regen"), qid))

    async def _regen_one(self, a: Assessment, qid: str, prepared: Prepared) -> None:
        assert self.source is not None
        spent = Spent()
        try:
            avoid = [q.text for q in a.questions]
            qs = await self.source.questions(prepared, 1, avoid, spent)
            if not qs:
                raise AssessError("no new question came back")
            a.replace(qid, qs[0].model_copy(update={"id": qid}))
        except AssessError as e:
            self._notice = f"Regenerate: {e}"
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log.exception("regenerate failed")
            self._notice = f"Regenerate: unexpected error: {type(e).__name__}: {e}"
        finally:
            self._jobs = [j for j in self._jobs if j.task is not asyncio.current_task()]
        a.tokens += spent.tokens
        log.info("regenerated one question (%d LLM calls, %d tokens)", spent.calls, spent.tokens)
        self._save()
        if self.current is a:
            await self.announce()

    def _cancel_jobs(self) -> None:
        for job in self._jobs:
            job.task.cancel()
        self._jobs = []

    async def _pause_lecture(self) -> None:
        if self._lifecycle == Lifecycle.LIVE:
            self._paused_lecture = True
            await self._bus.publish(CommandReceived(command=Command(kind="pause", origin="system")))

    async def _resume_lecture(self) -> None:
        if self._paused_lecture and self._lifecycle == Lifecycle.PAUSED:
            await self._bus.publish(CommandReceived(command=Command(kind="resume", origin="system")))
        self._paused_lecture = False

    # ---- students (from the server; answers are theirs only, by token) -----------------------------------
    def _open(self) -> Assessment:
        a = self.current
        if a is None or a.status in ("generating", "draft"):
            raise AssessError("No quiz or test is open.")
        return a

    async def _after_student(self) -> None:
        self._save()
        a = self.current
        if a is not None:
            a.tick(self.clock())  # every student answered: the question closes now, not on the next tick
        await self.announce()

    async def join(self, name: str, roll: str, token: str = "") -> dict[str, Any]:
        a = self._open()
        p = a.join(name, roll, token, self.clock())
        await self._after_student()
        return a.student_view(p.token, self.clock())

    def me(self, token: str) -> dict[str, Any]:
        return self._open().student_view(token, self.clock())

    async def answer(self, token: str, qid: str, choice: Any) -> dict[str, Any]:
        a = self._open()
        a.answer(token, qid, choice, self.clock())
        await self._after_student()
        return a.student_view(token, self.clock())

    async def submit(self, token: str) -> dict[str, Any]:
        a = self._open()
        a.submit(token, self.clock())
        await self._after_student()
        return a.student_view(token, self.clock())
