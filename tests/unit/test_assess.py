"""Quiz + test core (F-011, slice 1): the state machine on a fake clock, scoring, the roll-number registry and rejoin,
no answer key in what students get before it is due, persistence + CSV, the service's commands, the lecture pause,
and the hub's routing (keys to /control only)."""
import json

import pytest

from copilot.assess.model import REVEAL_S, AssessError, Assessment, Question, roll_key
from copilot.assess.scoring import quiz_points
from copilot.assess.service import AssessService, Prepared, Spent
from copilot.assess.store import AssessmentStore, results_csv
from copilot.core.bus import EventBus
from copilot.core.events import AssessState, Command, CommandReceived, Lifecycle, LifecycleChanged
from copilot.display.hub import DisplayHub

T0 = 1_790_000_000.0


def q(n, answer=0):
    return Question(id=f"q{n}", text=f"Question {n}?", options=[f"a{n}", f"b{n}", f"c{n}", f"d{n}"], answer=answer)


def quiz(n=3, seconds=10, **kw):
    a = Assessment(id="a1", kind="quiz", seconds=seconds, created=T0, **kw)
    a.set_questions([q(i, answer=i % 4) for i in range(1, n + 1)])
    return a


def make_test(n=3, minutes=10, **kw):
    a = Assessment(id="t1", kind="test", minutes=minutes, created=T0, **kw)
    a.set_questions([q(i, answer=i % 4) for i in range(1, n + 1)])
    return a


def keys_in(obj) -> bool:
    """Any answer key anywhere in a payload (the 'answer' / 'key' fields, or a points / right verdict). The
    'correct' counts (leaderboard, the student's own) cover closed questions only (checked on their own)."""
    text = json.dumps(obj)
    return any(f'"{k}"' in text for k in ("answer", "key", "distribution", "right", "points"))


# ---- scoring ------------------------------------------------------------------------------------------------
def test_quiz_points_faster_earns_more_slower_slightly_less_wrong_zero():
    assert quiz_points(True, 0, 15) == 1000
    assert quiz_points(True, 7.5, 15) == 850
    assert quiz_points(True, 15, 15) == 700
    assert quiz_points(True, 99, 15) == 700  # late answers are refused anyway; never below the floor
    assert quiz_points(False, 0, 15) == 0
    assert quiz_points(True, 3, 15) > quiz_points(True, 6, 15) > 0


# ---- registry + rejoin --------------------------------------------------------------------------------------
def test_join_rejoin_with_token_and_duplicate_roll_refused():
    a = quiz()
    a.open(T0)
    p = a.join("Asha", "CS 21-07", "", T0)
    assert p.token and p.key == roll_key("cs21-07") == "cs21-07"
    again = a.join("Asha K", "cs21-07", p.token, T0 + 5)  # a refresh: the same participant, name unchanged
    assert again is p and again.name == "Asha" and len(a.participants) == 1
    with pytest.raises(AssessError, match="already joined"):
        a.join("Someone", "CS21-07", "", T0 + 6)
    with pytest.raises(AssessError, match="already joined"):
        a.join("Someone", "cs21-07", "wrong-token", T0 + 6)
    with pytest.raises(AssessError, match="name and roll"):
        a.join("", "12", "", T0)
    a.release("CS21-07")  # the teacher lets it join from another device: answers kept
    moved = a.join("Asha", "cs21-07", "", T0 + 7)
    assert moved is p and moved.token != "" and len(a.participants) == 1


def test_join_refused_before_open_and_after_finish_but_rejoin_still_works():
    a = quiz()
    with pytest.raises(AssessError):
        a.join("A", "1", "", T0)  # draft: not open
    a.open(T0)
    p = a.join("A", "1", "", T0)
    a.start(T0)
    a.end(T0 + 1)
    with pytest.raises(AssessError, match="over"):
        a.join("B", "2", "", T0 + 2)
    assert a.join("A", "1", p.token, T0 + 2) is p  # a refresh after the end still shows the result


# ---- quiz flow on a fake clock ------------------------------------------------------------------------------
def test_quiz_runs_question_reveal_next_with_scores_and_early_close():
    a = quiz(n=2, seconds=10)
    a.open(T0)
    s1 = a.join("Asha", "1", "", T0)
    s2 = a.join("Ben", "2", "", T0)
    a.start(T0)
    assert a.step == "question" and a.left(T0 + 4) == 6
    a.answer(s1.token, "q1", 1, T0 + 2)        # correct (q1 answer = 1), 2 s → 940
    with pytest.raises(AssessError, match="Already answered"):
        a.answer(s1.token, "q1", 0, T0 + 3)
    assert not a.tick(T0 + 3)                  # Ben has not answered yet
    a.answer(s2.token, "q1", 0, T0 + 5)        # wrong → 0
    assert a.tick(T0 + 5) and a.step == "reveal"  # every student answered: closes before the deadline
    with pytest.raises(AssessError, match="Time is up"):
        a.answer(s2.token, "q1", 1, T0 + 5.5)
    board = a.leaderboard(a.closed_questions())
    assert [(r["name"], r["score"], r["rank"]) for r in board] == [("Asha", 940, 1), ("Ben", 0, 2)]
    assert a.distribution(a.questions[0]) == [1, 1, 0, 0]
    assert not a.tick(T0 + 5 + REVEAL_S - 0.1)
    assert a.tick(T0 + 5 + REVEAL_S) and a.index == 1 and a.step == "question"
    t1 = T0 + 5 + REVEAL_S
    assert a.tick(t1 + 10) and a.step == "reveal"  # nobody answered: closes at its deadline
    assert a.tick(t1 + 10 + REVEAL_S) and a.status == "finished"


def test_quiz_hold_next_waits_for_teacher_then_next_and_pause_freezes_time():
    a = quiz(n=2, seconds=10)
    a.open(T0)
    s = a.join("A", "1", "", T0)
    a.start(T0)
    a.pause(T0 + 4)                             # 6 s left
    with pytest.raises(AssessError, match="Paused"):
        a.answer(s.token, "q1", 1, T0 + 5)
    assert not a.tick(T0 + 100)                 # frozen
    assert a.left(T0 + 100) == 6
    a.resume(T0 + 100)
    assert a.left(T0 + 101) == 5
    a.answer(s.token, "q1", 1, T0 + 102)        # 6 s of answer time (the 96 s pause does not count) → 820
    assert a.participants["1"].answers["q1"].points == 820
    a.hold(True)
    a.tick(T0 + 102)                            # all answered → reveal
    assert a.tick(T0 + 102 + REVEAL_S) and a.held and a.step == "reveal" and a.left(T0 + 200) is None
    assert not a.tick(T0 + 500)                 # waits for the teacher
    a.next(T0 + 500)
    assert a.index == 1 and a.step == "question" and a.deadline == T0 + 510


def test_quiz_end_mid_question_counts_answers_and_ties_break_on_correct_then_time():
    a = quiz(n=3, seconds=10)
    a.open(T0)
    x = a.join("Xa", "1", "", T0)
    y = a.join("Yo", "2", "", T0)
    a.start(T0)
    a.answer(x.token, "q1", 1, T0 + 1)
    a.answer(y.token, "q1", 1, T0 + 1)
    a.tick(T0 + 1)
    a.next(T0 + 2)                              # skip the reveal
    a.answer(x.token, "q2", 2, T0 + 3)          # question 2 shown at T0+2: 1 s
    a.end(T0 + 4)
    assert a.status == "finished" and len(a.closed_questions()) == 2
    board = a.leaderboard(a.closed_questions())
    assert board[0]["name"] == "Xa" and board[0]["correct"] == 2 and board[1]["correct"] == 1


def test_students_with_no_right_answer_share_a_rank_whatever_their_answer_time():
    a = quiz(n=1, seconds=10)
    a.open(T0)
    x, y, z = (a.join(n, n, "", T0) for n in ("X", "Y", "Z"))
    a.start(T0)
    a.answer(x.token, "q1", 1, T0 + 1)  # right
    a.answer(y.token, "q1", 0, T0 + 2)  # wrong, fast
    a.answer(z.token, "q1", 3, T0 + 9)  # wrong, slow
    assert [(r["name"], r["rank"]) for r in a.leaderboard(a.closed_questions() or a.questions)] == \
        [("X", 1), ("Y", 2), ("Z", 2)]


def test_quiz_results_give_right_of_asked_and_the_average_response_time():
    a = quiz(n=3, seconds=10)
    a.open(T0)
    x = a.join("X", "1", "", T0)
    y = a.join("Y", "2", "", T0)
    a.start(T0)
    a.answer(x.token, "q1", 1, T0 + 2)        # right, 2 s
    a.next(T0 + 3)
    a.next(T0 + 3)                             # question 2 from T0+3
    a.answer(x.token, "q2", 0, T0 + 7)         # wrong, 4 s (a wrong answer still counts as a response)
    a.end(T0 + 8)                              # question 2 was the last asked
    rows = {r["name"]: r for r in a.control_view(T0 + 9)["students"]}
    assert (rows["X"]["correct"], rows["X"]["asked"], rows["X"]["avg"]) == (1, 2, 3.0)
    assert (rows["Y"]["correct"], rows["Y"]["asked"], rows["Y"]["avg"]) == (0, 2, None)  # never answered
    text = results_csv(a)
    head, first = text.splitlines()[:2]
    assert head.startswith("Rank,Name,Roll no.,Points,Score,Answered,Avg. response time (s),Q1")
    assert first.startswith("1,X,1,940,1/2,2,3.0,")


def test_test_time_taken_runs_on_the_test_clock_pauses_and_late_join_excluded():
    a = make_test(n=2, minutes=10)
    a.open(T0)
    s1 = a.join("Asha", "1", "", T0)
    a.start(T0)
    a.pause(T0 + 60)
    a.resume(T0 + 360)                         # 5 min paused: not counted
    late = a.join("Ben", "2", "", T0 + 420)    # joins 2 min into the test clock
    a.submit(s1.token, T0 + 480)               # 3 min of test clock
    a.submit(late.token, T0 + 540)             # 2 min after joining
    rows = {r["name"]: r for r in a.control_view(T0 + 541)["students"]}
    assert rows["Asha"]["taken"] == 180.0 and rows["Ben"]["taken"] == 120.0
    c = make_test(n=1, minutes=1)
    c.open(T0)
    s = c.join("C", "3", "", T0)
    c.start(T0)
    c.tick(T0 + 60)                            # auto-submitted at time out: the whole minute
    assert s.auto and s.taken == 60.0
    head, first = results_csv(a).splitlines()[:2]
    assert head.startswith("Rank,Name,Roll no.,Score,Answered,Time taken,Submitted,Auto-submitted,Q1")
    assert ",3:00," in first and ",0/2," in first


def test_quiz_public_and_student_views_never_carry_the_key_while_a_question_is_open():
    a = quiz(n=2, seconds=10)
    a.open(T0)
    s1 = a.join("Asha", "1", "", T0)
    s2 = a.join("Ben", "2", "", T0)
    assert not keys_in(a.public_view(T0))       # lobby
    a.start(T0)
    a.answer(s1.token, "q1", 1, T0 + 1)
    pub, mine = a.public_view(T0 + 2), a.student_view(s1.token, T0 + 2)
    assert not keys_in(pub) and not keys_in(mine)
    assert mine["me"]["choice"] == 1 and mine["me"]["score"] == 0  # the 970 points stay hidden until the reveal
    assert all(r["score"] == 0 and r["correct"] == 0 for r in pub["leaderboard"] + mine["leaderboard"])
    assert mine["me"]["correct"] == 0
    assert a.control_view(T0 + 2)["answer"] == 1  # the teacher sees the key
    a.answer(s2.token, "q1", 3, T0 + 3)
    a.tick(T0 + 3)
    pub, mine = a.public_view(T0 + 3), a.student_view(s1.token, T0 + 3)
    assert pub["answer"] == 1 and pub["distribution"] == [0, 1, 0, 1]
    assert mine["me"]["right"] is True and mine["me"]["points"] == 970 and mine["me"]["rank"] == 1
    assert mine["me"]["score"] == 970 and mine["me"]["correct"] == 1
    assert "roll" not in json.dumps(pub["leaderboard"]) and "token" not in json.dumps(pub)
    with pytest.raises(AssessError):
        a.student_view("not-a-token", T0)


# ---- test flow -----------------------------------------------------------------------------------------------
def test_test_answers_change_until_submit_then_locked_and_auto_submit_at_time_out():
    a = make_test(n=3, minutes=1, show_answers=True)
    a.open(T0)
    s1 = a.join("Asha", "1", "", T0)
    s2 = a.join("Ben", "2", "", T0)
    a.start(T0)
    view = a.student_view(s1.token, T0 + 1)
    assert [p["id"] for p in view["paper"]] == ["q1", "q2", "q3"] and not keys_in(view)
    a.answer(s1.token, "q1", 0, T0 + 2)
    a.answer(s1.token, "q1", 1, T0 + 3)         # changed its mind
    a.answer(s1.token, "q2", 2, T0 + 4)
    assert a.progress(s1) == "in progress" and a.progress(s2) == "joined"
    a.submit(s1.token, T0 + 5)
    with pytest.raises(AssessError, match="Already submitted"):
        a.answer(s1.token, "q3", 3, T0 + 6)
    mine = a.student_view(s1.token, T0 + 6)["me"]
    assert mine["submitted"] and mine["score"] == 2 and mine["key"] == {"q1": 1, "q2": 2, "q3": 3}
    assert not keys_in(a.student_view(s2.token, T0 + 6))  # Ben still writing: no key for him
    a.answer(s2.token, "q3", 3, T0 + 30)
    assert not a.tick(T0 + 59)
    assert a.tick(T0 + 60) and a.status == "finished"
    assert s2.submitted == T0 + 60 and s2.auto and a.student_view(s2.token, T0 + 61)["me"]["score"] == 1


def test_test_show_answers_off_gives_the_score_only_and_pause_freezes_the_clock():
    a = make_test(n=2, minutes=1, show_answers=False)
    a.open(T0)
    s = a.join("A", "1", "", T0)
    a.start(T0)
    a.pause(T0 + 20)
    assert not a.tick(T0 + 1000) and a.left(T0 + 1000) == 40
    a.resume(T0 + 1000)
    a.submit(s.token, T0 + 1001)
    mine = a.student_view(s.token, T0 + 1002)["me"]
    assert mine["score"] == 0 and "key" not in mine
    assert a.tick(T0 + 1040) and a.status == "finished"


def test_questions_editable_only_before_start_and_invalid_edits_refused():
    a = quiz(n=2)
    a.edit("q1", text="  What is ATP?  ", options=["energy", "sugar", "salt", "water"], answer=0)
    assert a.questions[0].text == "What is ATP?"
    with pytest.raises(AssessError, match="same"):
        a.edit("q1", options=["x", "x", "y", "z"])
    with pytest.raises(AssessError, match="4 options"):
        a.edit("q1", options=["x", "y"])
    a.add(Question(id="n", text="New?", options=["1", "2", "3", "4"], answer=2), after="q1")
    assert [x.id for x in a.questions] == ["q1", "n", "q2"]
    with pytest.raises(AssessError):
        a.add(Question(id="m", text="", options=["1", "2", "3", "4"], answer=0))
    a.delete("n")
    a.open(T0)
    a.edit("q2", text="Still editable in the lobby?")
    a.start(T0)
    with pytest.raises(AssessError, match="before Start"):
        a.delete("q1")


# ---- persistence + CSV --------------------------------------------------------------------------------------
def test_store_round_trip_keeps_answers_tokens_and_timer_and_csv_has_results(tmp_path):
    store = AssessmentStore(tmp_path / "assessments")
    a = quiz(n=2, seconds=10, lecture_id="L1", title="Photosynthesis")
    a.open(T0)
    s = a.join("Asha, K", "1", "", T0)
    a.start(T0)
    a.answer(s.token, "q1", 1, T0 + 2)
    store.save(a)
    b = store.load("a1")
    assert b is not None and b.deadline == a.deadline and b.participants["1"].token == s.token
    assert b.participants["1"].answers["q1"].points == 940
    assert [x.id for x in store.for_lecture("L1")] == ["a1"] and store.for_lecture("L2") == []
    b.tick(T0 + 2)
    text = results_csv(b)
    assert '"Asha, K"' in text and "940" in text and "B" in text.splitlines()[1]
    assert store.load("../etc") is None


# ---- service: commands, students, lecture pause, hub routing --------------------------------------------------
class Clock:
    def __init__(self) -> None:
        self.t = T0

    def __call__(self) -> float:
        return self.t


class FakeSource:
    available = True

    def __init__(self) -> None:
        self.asked: list[tuple[int, list[str]]] = []

    async def prepare(self, args):
        return Prepared(title="Photosynthesis", sources=["L1"])

    async def questions(self, prepared, count, avoid, spent: Spent):
        self.asked.append((count, list(avoid)))
        spent.calls += 1
        spent.tokens += 100
        base = len(self.asked) * 100
        return [q(base + i, answer=i % 4) for i in range(count)]


async def make(tmp_path, source=None):
    bus = EventBus()
    clock = Clock()
    hub = DisplayHub(bus)
    hub.attach()
    svc = AssessService(bus, AssessmentStore(tmp_path / "assessments"), "L1", source=source, clock=clock)
    svc.attach(ticker=False)
    seen: list = []

    async def grab(e):
        seen.append(e)
    bus.subscribe("test", grab, [CommandReceived])
    return bus, clock, hub, svc, seen


async def cmd(bus, command, **args):
    await bus.publish(CommandReceived(command=Command(kind=command, args=args, origin="control")))
    await bus.drain()


async def settle(bus, svc):
    for _ in range(5):
        for job in list(svc._jobs):
            await job.task
        await bus.drain()


async def test_service_generates_previews_opens_pauses_lecture_and_runs_a_quiz(tmp_path):
    source = FakeSource()
    bus, clock, hub, svc, seen = await make(tmp_path, source)
    await bus.publish(LifecycleChanged(state=Lifecycle.LIVE))
    await cmd(bus, "assess_create", kind="quiz", count=3, seconds=10)
    await settle(bus, svc)
    a = svc.current
    assert a is not None and a.status == "draft" and len(a.questions) == 3 and a.title == "Photosynthesis"
    assert hub.assess_public == {}              # a draft is the teacher's only
    await cmd(bus, "assess_regen", qid=a.questions[1].id)
    await settle(bus, svc)
    assert a.questions[1].text == "Question 200?" and a.questions[1].id == "q101"
    assert source.asked[-1][0] == 1 and len(source.asked[-1][1]) == 3  # avoids the set's stems
    await cmd(bus, "assess_open")
    assert a.status == "lobby" and hub.assess_public["status"] == "lobby"
    pauses = [e.command.kind for e in seen if e.command.origin == "system"]
    assert pauses == ["pause"]
    await bus.publish(LifecycleChanged(state=Lifecycle.PAUSED))  # the app acts on the pause command
    p1 = await svc.join("Asha", "1")
    p2 = await svc.join("Ben", "2")
    with pytest.raises(AssessError, match="already joined"):
        await svc.join("Imposter", " 1 ")
    await bus.drain()
    assert hub.assess_public["joined"] == 2
    await cmd(bus, "assess_start")
    first = a.questions[0]
    assert hub.assess_public["question"]["id"] == first.id and "answer" not in hub.assess_public
    assert hub.assess_control["control"]["answer"] == first.answer  # /control has the key
    await svc.answer(p1["me"]["token"], first.id, first.answer)
    await svc.answer(p2["me"]["token"], first.id, (first.answer + 1) % 4)
    await bus.drain()
    assert hub.assess_public["step"] == "reveal" and hub.assess_public["distribution"][first.answer] == 1
    clock.t += REVEAL_S
    await svc.step()
    await bus.drain()
    assert hub.assess_public["index"] == 1
    await cmd(bus, "assess_end")
    await cmd(bus, "assess_close")
    assert svc.current is None and hub.assess_public == {}
    kinds = [e.command.kind for e in seen if e.command.origin == "system"]
    assert kinds == ["pause", "resume"]
    saved = svc.store.load(a.id)
    assert saved is not None and saved.status == "finished" and len(saved.participants) == 2


async def test_service_refusals_reach_the_teacher_and_no_llm_leaves_an_editable_draft(tmp_path):
    bus, clock, hub, svc, seen = await make(tmp_path, source=None)
    await cmd(bus, "assess_open")
    assert "no quiz" in hub.assess_control["notice"]
    await cmd(bus, "assess_create", kind="test", count=5, minutes=2)
    a = svc.current
    assert a.status == "draft" and a.questions == [] and "LLM" in a.error and not hub.assess_control["llm"]
    await cmd(bus, "assess_open")
    assert "at least one question" in hub.assess_control["notice"]
    await cmd(bus, "assess_add", text="Which gas do plants take in?", options=["CO2", "O2", "N2", "He"], answer=0)
    await cmd(bus, "assess_open")
    assert a.status == "lobby" and hub.assess_control["notice"] == ""
    assert [e for e in seen if e.command.origin == "system"] == []  # the lecture was not live: nothing paused
    await cmd(bus, "assess_create", kind="quiz")
    assert "end it first" in hub.assess_control["notice"]
    await cmd(bus, "assess_close")
    assert "end it first" in hub.assess_control["notice"] and svc.current is a
    await cmd(bus, "assess_discard")
    assert svc.current is None


async def test_hub_sends_keys_to_control_only(tmp_path):
    bus, clock, hub, svc, seen = await make(tmp_path, FakeSource())
    await cmd(bus, "assess_create", kind="quiz", count=2)
    await settle(bus, svc)
    await cmd(bus, "assess_open")
    me = await svc.join("A", "1")
    await cmd(bus, "assess_start")
    viewer, display, control = hub.connect("viewer"), hub.connect("display"), hub.connect("control")
    for conn in (viewer, display):
        assert not keys_in(hub.hello(conn.role)["assess"])
        assert "questions" not in json.dumps(hub.hello(conn.role)["assess"])
    assert hub.hello("control")["assess"]["control"]["questions"][0]["answer"] == svc.current.questions[0].answer
    viewer.push({"type": "x"}); display.push({"type": "x"})
    await svc.answer(me["me"]["token"], svc.current.questions[0].id, 0)  # → reveal: the key is due now
    await bus.drain()
    batch = [m for m in await viewer.next_batch() if m.get("type") == "assess"]
    assert batch and "answer" in batch[-1]["public"] and "control" not in batch[-1]
    assert isinstance(AssessState().control, dict)


async def test_the_projector_gets_the_join_link_only_while_a_quiz_is_open(tmp_path):
    from copilot.core.events import ShareChanged

    bus, clock, hub, svc, seen = await make(tmp_path, FakeSource())
    await bus.publish(ShareChanged(state="on", url="https://x.trycloudflare.com/view"))
    await bus.drain()
    assert "join_url" not in hub.hello("display")["assess"]           # nothing open: the share stays the teacher's
    await cmd(bus, "assess_create", kind="quiz", count=2)
    await settle(bus, svc)
    assert "join_url" not in hub.hello("display")["assess"]           # a draft is not on the projector
    await cmd(bus, "assess_open")
    assert hub.hello("display")["assess"]["join_url"] == "https://x.trycloudflare.com/view"
    assert "join_url" not in hub.hello("viewer")["assess"] and "share" not in hub.hello("display")
    await bus.publish(ShareChanged(state="off"))
    await bus.drain()
    assert "join_url" not in hub.hello("display")["assess"]
