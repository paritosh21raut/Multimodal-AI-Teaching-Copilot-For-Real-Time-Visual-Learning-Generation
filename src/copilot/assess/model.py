"""The quiz / test state machine (F-011): deterministic, no I/O, no clock of its own — every method takes `now`.

Flow: generating → draft (preview / edit) → lobby (students join) → running → finished. A quiz runs question by
question (`question` until its deadline or every student answered → `reveal` for REVEAL_S → the next one, or held
for the teacher's Next); a test has one global deadline and every student submits (or is submitted at time out).
Views: `control_view` (everything), `public_view` (never an answer key before it is due), `student_view` (one
student's own state, by token). Spec: docs/specs/F-011-quiz-test.md.
"""
from __future__ import annotations

import re
import secrets
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from copilot.assess.scoring import quiz_points

Kind = Literal["quiz", "test"]
Status = Literal["generating", "draft", "lobby", "running", "finished"]

DEFAULT_COUNT = 15
MAX_COUNT = 40
DEFAULT_SECONDS = 15      # quiz: per question
MIN_SECONDS, MAX_SECONDS = 5, 120
DEFAULT_MINUTES = 15      # test: whole test
MIN_MINUTES, MAX_MINUTES = 1, 180
REVEAL_S = 6.0            # quiz: correct answer + distribution + leaderboard, then the next question
OPTIONS = 4
NAME_MAX, ROLL_MAX, TEXT_MAX, OPTION_MAX = 40, 24, 400, 160
PUBLIC_TOP = 5            # leaderboard rows on the projector / students' pages during a quiz
FINAL_TOP = 10


class AssessError(Exception):
    """A refused action; the message is shown to whoever asked (teacher or student)."""


def roll_key(roll: str) -> str:
    """Roll numbers compare without spaces and case: 'cs 21-07' == 'CS21-07'."""
    return re.sub(r"\s+", "", roll or "").lower()


def _clip(s: Any, n: int) -> str:
    return re.sub(r"\s+", " ", str(s or "")).strip()[:n]


class Question(BaseModel):
    id: str
    text: str
    options: list[str]
    answer: int  # index of the correct option

    def check(self) -> Optional[str]:
        """Why this question cannot be used (None = fine)."""
        if not self.text.strip():
            return "the question has no text"
        if len(self.options) != OPTIONS or any(not o.strip() for o in self.options):
            return f"a question needs {OPTIONS} options, none empty"
        if len({o.strip().lower() for o in self.options}) != OPTIONS:
            return "two options are the same"
        if not 0 <= self.answer < OPTIONS:
            return "no correct option chosen"
        return None

    def public(self) -> dict[str, Any]:  # never the key
        return {"id": self.id, "text": self.text, "options": list(self.options)}


class Answer(BaseModel):
    choice: int
    at: float = 0.0       # quiz: seconds after the question appeared; test: seconds after the test started
    points: int = 0       # quiz only, decided when answered, shown only after the reveal


class Participant(BaseModel):
    key: str              # roll_key(roll)
    roll: str
    name: str
    token: str
    joined: float
    answers: dict[str, Answer] = Field(default_factory=dict)  # question id -> answer
    submitted: Optional[float] = None  # test: when (or quiz: never)
    auto: bool = False    # test: submitted at time out / End


class Assessment(BaseModel):
    id: str
    kind: Kind
    title: str = ""
    lecture_id: str = ""                    # the lecture it was run in
    sources: list[str] = Field(default_factory=list)  # lectures the questions come from
    created: float = 0.0
    count: int = DEFAULT_COUNT              # questions asked for
    seconds: int = DEFAULT_SECONDS          # quiz: per question
    minutes: int = DEFAULT_MINUTES          # test: whole test
    show_answers: bool = True               # test: the correct answers after submitting
    status: Status = "draft"
    error: str = ""                         # why generation failed / came back short
    tokens: int = 0                         # LLM tokens spent on its questions (terminal / logs only)
    questions: list[Question] = Field(default_factory=list)
    participants: dict[str, Participant] = Field(default_factory=dict)  # roll_key -> participant
    started: Optional[float] = None
    ended: Optional[float] = None
    deadline: Optional[float] = None        # quiz: end of the current step; test: end of the test
    paused: bool = False
    paused_left: float = 0.0
    paused_at: Optional[float] = None
    index: int = 0                          # quiz: current question
    step: Literal["question", "reveal"] = "question"
    step_started: float = 0.0               # quiz: when the current question appeared (pauses excluded)
    hold_next: bool = False                 # quiz: wait for the teacher's Next after this reveal
    held: bool = False                      # quiz: the reveal is over, waiting for Next
    seq: int = 0                            # bumps on every change (views, saving)

    # ---- teacher: questions -----------------------------------------------------------------------------
    def _editable(self) -> None:
        if self.status not in ("draft", "lobby"):
            raise AssessError("questions can be changed only before Start")

    def question(self, qid: str) -> Question:
        for q in self.questions:
            if q.id == qid:
                return q
        raise AssessError("no such question")

    def set_questions(self, questions: list[Question], error: str = "") -> None:
        self.questions = [q for q in questions if q.check() is None]
        self.error = error
        self.status = "draft"
        self._changed()

    def edit(self, qid: str, text: Any = None, options: Any = None, answer: Any = None) -> None:
        self._editable()
        q = self.question(qid)
        new = q.model_copy(deep=True)
        if text is not None:
            new.text = _clip(text, TEXT_MAX)
        if options is not None:
            if not isinstance(options, list) or len(options) != OPTIONS:
                raise AssessError(f"a question needs {OPTIONS} options")
            new.options = [_clip(o, OPTION_MAX) for o in options]
        if answer is not None:
            try:
                new.answer = int(answer)
            except (TypeError, ValueError):
                raise AssessError("no correct option chosen") from None
        problem = new.check()
        if problem:
            raise AssessError(problem)
        self.questions[self.questions.index(q)] = new
        self._changed()

    def add(self, q: Question, after: Optional[str] = None) -> None:
        """A question the teacher writes (or a regenerated one): placed after `after`, else at the end."""
        self._editable()
        problem = q.check()
        if problem:
            raise AssessError(problem)
        at = len(self.questions)
        if after:
            at = self.questions.index(self.question(after)) + 1
        self.questions.insert(at, q)
        self._changed()

    def replace(self, qid: str, q: Question) -> None:
        self._editable()
        problem = q.check()
        if problem:
            raise AssessError(problem)
        self.questions[self.questions.index(self.question(qid))] = q
        self._changed()

    def delete(self, qid: str) -> None:
        self._editable()
        self.questions.remove(self.question(qid))
        self._changed()

    # ---- teacher: flow ----------------------------------------------------------------------------------
    def open(self, now: float) -> None:
        if self.status != "draft":
            raise AssessError("only a prepared quiz / test can be opened")
        if not self.questions:
            raise AssessError("add at least one question first")
        bad = [n for n, q in enumerate(self.questions, 1) if q.check()]
        if bad:
            raise AssessError(f"question {bad[0]} is not complete")
        self.status = "lobby"
        self._changed()

    def start(self, now: float) -> None:
        if self.status != "lobby":
            raise AssessError("open the lobby first")
        self.status = "running"
        self.started = now
        if self.kind == "quiz":
            self._ask(0, now)
        else:
            self.deadline = now + self.minutes * 60
        self._changed()

    def pause(self, now: float) -> None:
        if self.status != "running" or self.paused:
            raise AssessError("nothing to pause")
        self.paused, self.paused_at = True, now
        self.paused_left = max(0.0, (self.deadline or now) - now)
        self._changed()

    def resume(self, now: float) -> None:
        if self.status != "running" or not self.paused:
            raise AssessError("not paused")
        gap = now - (self.paused_at or now)
        self.paused, self.paused_at = False, None
        if not self.held:
            self.deadline = now + self.paused_left
        if self.kind == "quiz" and self.step == "question":
            self.step_started += gap  # the pause does not count as answer time
        self._changed()

    def hold(self, on: bool) -> None:
        if self.kind != "quiz" or self.status not in ("lobby", "running"):
            raise AssessError("only a running quiz can hold before the next question")
        self.hold_next = bool(on)
        self._changed()

    def next(self, now: float) -> None:
        """Quiz: close the open question now, or go on from its reveal (held or not)."""
        if self.kind != "quiz" or self.status != "running":
            raise AssessError("no quiz running")
        if self.paused:
            raise AssessError("resume first")
        if self.step == "question":
            self._reveal(now)
        else:
            self._advance(now)
        self._changed()

    def end(self, now: float) -> None:
        if self.status == "lobby":  # nobody answered anything: nothing to keep running
            self.status, self.ended = "finished", now
        elif self.status == "running":
            self._finish(now)
        else:
            raise AssessError("not running")
        self._changed()

    def release(self, roll: str) -> None:
        """The teacher lets a roll number join again from another device (answers kept)."""
        p = self.participants.get(roll_key(roll))
        if p is None:
            raise AssessError("no such roll number")
        p.token = ""
        self._changed()

    # ---- clock ------------------------------------------------------------------------------------------
    def tick(self, now: float) -> bool:
        """Advance on deadlines. True when something changed."""
        if self.status != "running" or self.paused:
            return False
        if self.kind == "test":
            if self.deadline is None or now < self.deadline:
                return False
            self._finish(now)
        elif self.step == "question" and (now >= (self.deadline or now) or self._all_answered()):
            self._reveal(now)
        elif self.step == "reveal" and not self.held and now >= (self.deadline or now):
            if self.hold_next and self.index + 1 < len(self.questions):
                self.held, self.deadline = True, None
            else:
                self._advance(now)
        else:
            return False
        self._changed()
        return True

    def _ask(self, index: int, now: float) -> None:
        self.index, self.step, self.held = index, "question", False
        self.step_started = now
        self.deadline = now + self.seconds

    def _reveal(self, now: float) -> None:
        self.step = "reveal"
        self.held = False
        self.deadline = now + REVEAL_S

    def _advance(self, now: float) -> None:
        if self.index + 1 < len(self.questions):
            self._ask(self.index + 1, now)
        else:
            self.status, self.ended, self.deadline, self.held = "finished", now, None, False

    def _finish(self, now: float) -> None:
        if self.kind == "test":
            for p in self.participants.values():
                if p.submitted is None:
                    p.submitted, p.auto = now, True
        elif self.step == "question":
            self.step = "reveal"  # the open question is closed (its answers count)
        self.status, self.ended, self.deadline = "finished", now, None
        self.paused, self.held = False, False

    def _all_answered(self) -> bool:
        if not self.participants or not self.questions:
            return False
        qid = self.questions[self.index].id
        return all(qid in p.answers for p in self.participants.values())

    def _changed(self) -> None:
        self.seq += 1

    # ---- students ---------------------------------------------------------------------------------------
    def join(self, name: str, roll: str, token: str, now: float) -> Participant:
        key = roll_key(roll)
        p = self.participants.get(key)
        if p is not None and token and p.token and secrets.compare_digest(token, p.token):
            return p  # the same student again (a refresh): answers and the timer are kept
        if p is not None and p.token:
            raise AssessError("This roll number has already joined. Use the device you joined on, "
                              "or ask the teacher.")
        if self.status not in ("lobby", "running"):
            raise AssessError("The quiz is over." if self.kind == "quiz" else "The test is over.")
        name = _clip(name, NAME_MAX)
        roll = _clip(roll, ROLL_MAX)
        if not name or not key:
            raise AssessError("Enter your name and roll number.")
        if len(key) > ROLL_MAX:
            raise AssessError("That roll number is too long.")
        if p is not None:  # released by the teacher: a new device takes it over, answers kept
            p.token, p.name = secrets.token_urlsafe(16), name
        else:
            p = Participant(key=key, roll=roll, name=name, token=secrets.token_urlsafe(16), joined=now)
            self.participants[key] = p
        self._changed()
        return p

    def by_token(self, token: str) -> Participant:
        for p in self.participants.values():
            if token and p.token and secrets.compare_digest(token, p.token):
                return p
        raise AssessError("Join first.")

    def answer(self, token: str, qid: str, choice: Any, now: float) -> None:
        p = self.by_token(token)
        try:
            choice = int(choice)
        except (TypeError, ValueError):
            raise AssessError("Pick an option.") from None
        if not 0 <= choice < OPTIONS:
            raise AssessError("Pick an option.")
        if self.status != "running":
            raise AssessError("Not running." if self.status != "finished" else "Time is up.")
        if self.paused:
            raise AssessError("Paused by the teacher.")
        if self.kind == "quiz":
            q = self.questions[self.index]
            if qid != q.id or self.step != "question":
                raise AssessError("Time is up for this question.")
            if qid in p.answers:
                raise AssessError("Already answered.")
            at = max(0.0, now - self.step_started)
            p.answers[qid] = Answer(choice=choice, at=round(at, 2),
                                    points=quiz_points(choice == q.answer, at, self.seconds))
        else:
            if p.submitted is not None:
                raise AssessError("Already submitted.")
            self.question(qid)  # a real question of this test
            p.answers[qid] = Answer(choice=choice, at=round(now - (self.started or now), 2))
        self._changed()

    def submit(self, token: str, now: float) -> None:
        p = self.by_token(token)
        if self.kind != "test":
            raise AssessError("Nothing to submit.")
        if p.submitted is not None:
            raise AssessError("Already submitted.")
        if self.status != "running":
            raise AssessError("Time is up.")
        p.submitted = now
        self._changed()

    # ---- results ----------------------------------------------------------------------------------------
    def closed_questions(self) -> list[Question]:
        """Quiz: the questions whose answers are out (asked and revealed). Test: all, once finished."""
        if self.kind == "test":
            return list(self.questions) if self.status == "finished" else []
        if self.status == "finished":
            return list(self.questions[: self.index + 1]) if self.started else []
        if self.status != "running":
            return []
        return list(self.questions[: self.index + (1 if self.step == "reveal" else 0)])

    def score(self, p: Participant, upto: Optional[list[Question]] = None) -> dict[str, Any]:
        qs = self.questions if upto is None else upto
        correct = sum(1 for q in qs if q.id in p.answers and p.answers[q.id].choice == q.answer)
        if self.kind == "quiz":
            points = sum(p.answers[q.id].points for q in qs if q.id in p.answers)
            # tie-break: answer time of the right answers only (two students with no right answer share a rank)
            time_s = sum(p.answers[q.id].at for q in qs if q.id in p.answers and p.answers[q.id].choice == q.answer)
            return {"score": points, "correct": correct, "answered": sum(1 for q in qs if q.id in p.answers),
                    "time": round(time_s, 1)}
        return {"score": correct, "correct": correct, "answered": len(p.answers), "total": len(self.questions)}

    def leaderboard(self, upto: Optional[list[Question]] = None) -> list[dict[str, Any]]:
        """Ranked: score, then more correct, then less answer time (quiz) / earlier submit (test)."""
        rows = []
        for p in self.participants.values():
            s = self.score(p, upto)
            tie = s.get("time", 0.0) if self.kind == "quiz" else (p.submitted or float("inf"))
            rows.append((-s["score"], -s["correct"], tie, p.name.lower(), p, s))
        rows.sort(key=lambda r: r[:4])
        out, rank, prev = [], 0, None
        for n, (*key, p, s) in enumerate(rows, start=1):
            if tuple(key[:3]) != prev:
                rank, prev = n, tuple(key[:3])
            out.append({"rank": rank, "name": p.name, "roll": p.roll, **s})
        return out

    def distribution(self, q: Question) -> list[int]:
        counts = [0] * OPTIONS
        for p in self.participants.values():
            a = p.answers.get(q.id)
            if a is not None:
                counts[a.choice] += 1
        return counts

    def progress(self, p: Participant) -> str:
        if self.kind == "test":
            if p.submitted is not None:
                return "submitted"
            return "in progress" if p.answers else "joined"
        return "joined"

    # ---- views ------------------------------------------------------------------------------------------
    def left(self, now: float) -> Optional[float]:
        if self.paused:
            return round(self.paused_left, 2)
        if self.deadline is None:
            return None
        return round(max(0.0, self.deadline - now), 2)

    def _base(self, now: float) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id, "kind": self.kind, "title": self.title, "status": self.status, "seq": self.seq,
            "total": len(self.questions), "seconds": self.seconds, "minutes": self.minutes,
            "joined": len(self.participants), "paused": self.paused, "left": self.left(now),
            "names": [p.name for p in sorted(self.participants.values(), key=lambda p: p.joined)],
        }
        if self.kind == "test":
            out["submitted"] = sum(1 for p in self.participants.values() if p.submitted is not None)
        return out

    def _quiz_round(self, now: float, keys: bool) -> dict[str, Any]:
        """The current question (no key while it is open, unless `keys`), its distribution after it closed."""
        if self.status not in ("running", "finished") or not self.questions or self.started is None:
            return {}
        q = self.questions[self.index]
        revealed = self.step == "reveal" or self.status == "finished"
        out: dict[str, Any] = {"index": self.index, "step": self.step if self.status == "running" else "final",
                               "held": self.held, "hold_next": self.hold_next, "question": q.public(),
                               "answered": sum(1 for p in self.participants.values() if q.id in p.answers)}
        if revealed or keys:
            out["answer"] = q.answer
        if revealed:
            out["distribution"] = self.distribution(q)
        return out

    def public_view(self, now: float) -> dict[str, Any]:
        """For /display and every /view: never an answer key before it is due."""
        out = self._base(now)
        if self.kind == "quiz":
            out.update(self._quiz_round(now, keys=False))
            board = self.leaderboard(self.closed_questions())
            top = FINAL_TOP if self.status == "finished" else PUBLIC_TOP
            out["leaderboard"] = [{k: r[k] for k in ("rank", "name", "score", "correct")} for r in board[:top]]
        return out

    def control_view(self, now: float) -> dict[str, Any]:
        """For /control: everything, the keys included."""
        out = self._base(now)
        out.update(count=self.count, show_answers=self.show_answers, error=self.error, created=self.created,
                   sources=list(self.sources), lecture_id=self.lecture_id,
                   questions=[q.model_dump() for q in self.questions])
        if self.kind == "quiz":
            out.update(self._quiz_round(now, keys=True))
            out["round_distribution"] = self.distribution(self.questions[self.index]) \
                if self.status in ("running", "finished") and self.questions and self.started else []
        board = self.leaderboard(self.closed_questions() if self.kind == "quiz" else None)
        by_roll = {r["roll"]: r for r in board}
        out["students"] = [{**by_roll[p.roll], "status": self.progress(p), "joined_at": p.joined,
                            "submitted_at": p.submitted, "auto": p.auto, "answers_in": len(p.answers)}
                           for p in sorted(self.participants.values(), key=lambda p: by_roll[p.roll]["rank"])]
        return out

    def student_view(self, token: str, now: float) -> dict[str, Any]:
        """One student's own state (their token): their answers, and the keys only when due."""
        p = self.by_token(token)
        out = self.public_view(now)
        me: dict[str, Any] = {"name": p.name, "roll": p.roll, "token": p.token}
        if self.kind == "quiz":
            closed = self.closed_questions()
            me.update(self.score(p, closed))
            if self.status in ("running", "finished") and self.started is not None:
                q = self.questions[self.index]
                a = p.answers.get(q.id)
                me["choice"] = a.choice if a else None
                if a is not None and q.id in {c.id for c in closed}:
                    me["right"] = a.choice == q.answer  # ("correct" is the count of right answers)
                    me["points"] = a.points
            board = self.leaderboard(closed)
            me["rank"] = next((r["rank"] for r in board if r["roll"] == p.roll), None)
        else:
            me["answers"] = {qid: a.choice for qid, a in p.answers.items()}
            me["submitted"] = p.submitted is not None
            me["auto"] = p.auto
            if self.status in ("running", "finished") and self.started is not None:
                out["paper"] = [q.public() for q in self.questions]
            if p.submitted is not None or self.status == "finished":
                me.update(self.score(p))
                if self.show_answers:
                    me["key"] = {q.id: q.answer for q in self.questions}
        out["me"] = me
        return out
