"""Quiz / test questions (F-011, slice 2): a bounded prompt (never the whole transcript), strict JSON validation with
one repair and nothing made up, the key kept right through the core's shuffle, regenerate avoiding the set, and the
service end to end with a fake LLM (0 tokens)."""
import json

import pytest

from copilot.assess.generator import LectureQuestions, prompt, to_question, usable, _MCQ, _MCQs
from copilot.assess.model import AssessError
from copilot.assess.service import AssessService, Prepared, Spent
from copilot.assess.store import AssessmentStore
from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived
from copilot.core.textutil import approx_tokens
from copilot.llm.providers import LLMResponse
from copilot.llm.router import RouterResult
from copilot.materials.content import Lecture, Subtopic, Topic
from copilot.materials.writer import PROMPT_MAX, SYSTEM, MaterialError, Writer

SAID = "the teacher explains chlorophyll absorbs red and blue light while green light is reflected " * 40


def lecture(subtopics=12) -> Lecture:
    subs = [Subtopic(f"L1.T1.S{n}", "Photosynthesis", f"Part {n}",
                     slides=[{"id": f"s{n}", "title": f"Part {n}", "blocks": [
                         {"type": "points", "items": [{"text": f"Fact {n}.{k} about leaves and light energy"}
                                                      for k in range(8)]}]}],
                     said=[SAID]) for n in range(1, subtopics + 1)]
    return Lecture("L1", "Photosynthesis", "12 Oct 2026", [Topic("Photosynthesis", subs)])


def mcq(n, answer=0, options=None):
    return {"q": f"Which statement about part {n} is right?",
            "options": options or [f"right {n}", f"wrong {n}a", f"wrong {n}b", f"wrong {n}c"], "answer": answer}


class FakeRouter:
    def __init__(self, *answers) -> None:
        self.answers = list(answers)
        self.prompts: list[list[dict]] = []

    async def complete(self, messages, *, est_tokens, max_tokens, deadline, timeout_s=None):
        self.prompts.append(messages)
        text = self.answers.pop(0)
        return RouterResult(LLMResponse(text=text if isinstance(text, str) else json.dumps(text),
                                        prompt_tokens=est_tokens, completion_tokens=50), "fake", [])


def test_prompt_is_bounded_and_never_the_whole_transcript():
    lec = lecture(subtopics=40)
    full = sum(approx_tokens(" ".join(s.said)) for s in lec.subtopics)
    avoid = [f"An earlier question number {n} about light and leaves and chlorophyll?" for n in range(40)]
    for p in (prompt([lec], 40, []), prompt([lec], 1, avoid), prompt([lec, lecture(5)], 15, avoid)):
        assert approx_tokens(SYSTEM) + approx_tokens(p) + 8 <= PROMPT_MAX
    assert full > 10 * PROMPT_MAX  # the transcript alone would be far over budget
    p = prompt([lec], 1, avoid)
    assert "Do NOT repeat" in p and avoid[0] in p and '"answer"' in p


def test_shuffle_keeps_the_right_option_marked_and_is_deterministic():
    m = _MCQ(**mcq(1, answer=2, options=["w1", "w2", "RIGHT", "w3"]))
    a, b = to_question(m), to_question(m)
    assert a.options[a.answer] == "RIGHT" and a.options == b.options
    keys = {to_question(_MCQ(**mcq(n))).answer for n in range(30)}  # the model put every key at 0
    assert len(keys) >= 3


def test_invalid_questions_are_dropped_not_fixed_up():
    out = _MCQs(questions=[_MCQ(**mcq(1)), _MCQ(**mcq(2, options=["x", "x", "y", "z"])),
                           _MCQ(**mcq(3, answer=4)), _MCQ(**mcq(4, options=["a", "b", "c"])),
                           _MCQ(**mcq(1)), _MCQ(**mcq(5))])
    qs = usable(out, avoid=["Which statement about part 5 is right"])
    assert [q.text for q in qs] == ["Which statement about part 1 is right?"]


async def test_one_repair_then_the_set_and_a_failure_makes_nothing_up():
    lec = lecture(4)
    bad = {"questions": [mcq(1), mcq(2, options=["a", "a", "b", "c"])]}
    good = {"questions": [mcq(n, answer=1, options=[f"wrong {n}a", f"right {n}", f"wrong {n}b", f"wrong {n}c"])
                          for n in range(1, 4)]}
    router = FakeRouter("no json here", good)
    src = LectureQuestions(None, Writer(router))
    spent = Spent()
    qs = await src.questions(Prepared("T", ["L1"], [lec]), 3, [], spent)
    assert len(qs) == 3 and spent.calls == 2 and spent.tokens > 0
    assert "not right" in router.prompts[1][-1]["content"]
    for q, n in zip(qs, range(1, 4)):
        assert q.options[q.answer] == f"right {n}"
    router = FakeRouter(bad, bad)
    with pytest.raises(AssessError, match="not usable"):
        await LectureQuestions(None, Writer(router)).questions(Prepared("T", ["L1"], [lec]), 2, [], Spent())
    with pytest.raises(AssessError, match="LLM is off"):
        await LectureQuestions(None, Writer(None)).questions(Prepared("T", ["L1"], [lec]), 2, [], Spent())


class FakeMaterials:
    def __init__(self, writer, lectures=None, fail=None) -> None:
        self.writer = writer
        self.lectures = lectures if lectures is not None else [lecture(3)]
        self.fail = fail
        self.args = None

    def resolve(self, args):
        self.args = args
        if not args.get("current", True) and not args.get("lectures"):
            return None
        return ["L1"], True, "Photosynthesis"

    async def taught(self, ids, current):
        if self.fail:
            raise MaterialError(self.fail)
        return self.lectures


async def test_service_generates_from_the_from_choice_and_regenerates_one(tmp_path):
    router = FakeRouter({"questions": [mcq(n) for n in range(1, 4)]}, {"questions": [mcq(9)]})
    mats = FakeMaterials(Writer(router))
    bus = EventBus()
    svc = AssessService(bus, AssessmentStore(tmp_path), "L1", source=LectureQuestions(mats))
    svc.attach(ticker=False)

    async def cmd(command, **args):
        await bus.publish(CommandReceived(command=Command(kind=command, args=args, origin="control")))
        await bus.drain()
        for job in list(svc._jobs):
            await job.task
        await bus.drain()
    await cmd("assess_create", kind="quiz", count=3, current=False, lectures=["L0"], chapters=[])
    a = svc.current
    assert mats.args["lectures"] == ["L0"] and a.title == "Photosynthesis" and a.sources == ["L1"]
    assert len(a.questions) == 3 and a.status == "draft" and a.error == "" and a.tokens > 0
    old = [q.text for q in a.questions]
    await cmd("assess_regen", qid=a.questions[0].id)
    assert a.questions[0].text == "Which statement about part 9 is right?" and a.questions[1].text == old[1]
    assert all(t in router.prompts[1][1]["content"] for t in old)  # the regenerate prompt avoids the set
    # nothing taught / no lecture chosen: the teacher sees why, no questions made up
    svc.source = LectureQuestions(FakeMaterials(Writer(FakeRouter()), lectures=[Lecture("L1", "x", "", [])]))
    await cmd("assess_create", kind="test", count=3)
    assert svc.current.questions == [] and "nothing taught" in svc.current.error
    svc.source = LectureQuestions(FakeMaterials(Writer(FakeRouter())))
    await cmd("assess_create", kind="test", count=3, current=False)
    assert "choose at least one lecture" in svc.current.error
