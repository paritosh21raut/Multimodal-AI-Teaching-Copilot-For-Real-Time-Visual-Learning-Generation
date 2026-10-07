"""Lecture materials + past lectures (F-010): rebuilt lectures, taught content per topic, bounded LLM prompts with one
repair and no made-up fallback, the materials store, summary / key-concepts slides, the service end to end."""
import json
import re
import sqlite3
from pathlib import Path

import pytest

from copilot.core.bus import EventBus
from copilot.core.events import (
    Command, CommandReceived, DeckState, MaterialsState, SlidePatch, TranscriptFinal, TranscriptSegment,
)
from copilot.core.textutil import approx_tokens
from copilot.display.hub import DisplayHub
from copilot.llm.providers import LLMResponse
from copilot.llm.router import AllProvidersFailed, RouterResult
from copilot.materials.archive import LectureArchive, rebuild
from copilot.materials.content import budgeted, lecture_content, topic_of
from copilot.materials.service import MaterialsService
from copilot.materials.slides import _balanced, key_concepts_slides, lecture_summary_slides, topic_summary_slide
from copilot.materials.store import MaterialStore, auto_name, clean_name
from copilot.materials.writer import (
    NOTES_BUDGET, PROMPT_MAX, Concept, MaterialError, Usage, Writer, parse_json, _Points,
)
from copilot.persistence.event_log import EventLog
from copilot.presentation.deck import Deck
from copilot.presentation.spec import (
    DefinitionBlock, FormulaBlock, Item, PointsBlock, ProcessBlock, SlideSpec, Step, Variable,
)

T0 = 1_790_000_000.0


def slide(sid, topic, title, *blocks, layout="concept", version=1):
    return SlideSpec(id=sid, title=title, subtitle=topic, layout=layout, blocks=list(blocks), version=version)


def pts(*texts):
    return PointsBlock(items=[Item(text=t) for t in texts])


PHOTO = [
    slide("t0", "", "Photosynthesis", layout="title"),
    slide("s1", "Photosynthesis", "What is photosynthesis?",
          DefinitionBlock(term="Photosynthesis", definition="The process by which green plants make food using sunlight.")),
    slide("s2", "Photosynthesis", "How it happens",
          ProcessBlock(steps=[Step(label="Light is absorbed"), Step(label="Water is split"),
                              Step(label="Glucose is made")])),
    slide("s3", "Photosynthesis", "The equation",
          FormulaBlock(latex=r"6CO_2 + 6H_2O \to C_6H_{12}O_6 + 6O_2", spoken="6CO2 + 6H2O gives C6H12O6 + 6O2",
                       variables=[Variable(symbol="CO2", meaning="carbon dioxide")])),
    slide("s4", "Respiration", "What is respiration?", pts("Glucose is broken down", "Energy is released")),
]
SAID = {"s1": ["Photosynthesis is how plants make their own food.", "They use sunlight, water and carbon dioxide."],
        "s2": ["First the chlorophyll absorbs light.", "Then water splits into hydrogen and oxygen."],
        "s3": ["Let us write the equation for it."],
        "s4": ["Now respiration is the opposite.", "Glucose is broken down to release energy."]}


async def write_lecture(sessions: Path, sid: str, slides=PHOTO, said=SAID, removed=(), extra_versions=()):
    """A session's event log as the app writes it: each slide's lines are spoken, then the slide is patched."""
    bus = EventBus()
    log = EventLog(sessions / sid / "session.sqlite")
    await log.open(bus)
    t, clock = T0, 0.0
    for s in slides:
        for line in said.get(s.id, []):
            t += 3; clock += 3
            seg = TranscriptSegment(text=line, start=clock, end=clock + 2, source="mic")
            await bus.publish(TranscriptFinal(segment=seg, ts=t))
        t += 2
        await bus.publish(SlidePatch(slide_id=s.id, version=1, op="add", spec=s.model_dump(), ts=t))
    for s in extra_versions:  # a later edit of a slide
        t += 1
        await bus.publish(SlidePatch(slide_id=s.id, version=s.version, op="update", spec=s.model_dump(), ts=t))
    order = [s.id for s in slides if s.id not in removed]
    await bus.publish(DeckState(live_id=order[-1], slide_ids=order, following=True, blank=False, ts=t + 1))
    await bus.drain()
    await bus.close()
    await log.close()


# ---- archive ------------------------------------------------------------------------------------------------------
async def test_a_past_lecture_is_its_final_deck_and_transcript(tmp_path):
    edited = slide("s2", "Photosynthesis", "How it happens", pts("edited by the teacher"), version=3)
    await write_lecture(tmp_path, "L1", removed=("s3",), extra_versions=[edited])
    rec = rebuild(tmp_path / "L1" / "session.sqlite", "L1")
    assert [s["id"] for s in rec.slides] == ["t0", "s1", "s2", "s4"]       # removed slide gone, deck order
    assert rec.slides[2]["blocks"][0]["items"][0]["text"] == "edited by the teacher"  # latest version
    assert rec.title == "Photosynthesis" and len(rec.transcript) == 7 and not rec.simulated
    assert [s["id"] for s in rec.content_slides] == ["s1", "s2", "s4"]


async def test_sessions_without_a_lecture_are_not_listed_and_hidden_ones_go(tmp_path):
    await write_lecture(tmp_path, "L1")
    await write_lecture(tmp_path, "empty", slides=[PHOTO[0]], said={})
    await write_lecture(tmp_path, "now")
    arch = LectureArchive(tmp_path, tmp_path / "archive.json", current_id="now")
    assert [r.id for r in arch.lectures()] == ["L1"]   # the empty start and the running lecture are not listed
    assert json.loads((tmp_path / "L1" / "lecture.json").read_text())["record"]["title"] == "Photosynthesis"
    arch.hide("L1")
    assert arch.lectures() == [] and (tmp_path / "L1").is_dir()  # nothing deleted


async def test_the_cache_is_rebuilt_when_the_log_grows(tmp_path):
    await write_lecture(tmp_path, "L1", slides=PHOTO[:3])
    arch = LectureArchive(tmp_path, tmp_path / "a.json")
    assert len(arch.load("L1").slides) == 3
    await write_lecture(tmp_path, "L1", slides=PHOTO)  # the same session got more events
    assert len(LectureArchive(tmp_path, tmp_path / "a.json").load("L1").slides) == 5


# ---- content ------------------------------------------------------------------------------------------------------
async def test_topics_subtopics_and_what_was_said_on_each(tmp_path):
    await write_lecture(tmp_path, "L1")
    lec = lecture_content(rebuild(tmp_path / "L1" / "session.sqlite", "L1"))
    assert [t.name for t in lec.topics] == ["Photosynthesis", "Respiration"]
    subs = {s.title: s for s in lec.subtopics}
    assert subs["How it happens"].said == SAID["s2"]          # each line went to the slide patched after it
    assert subs["What is respiration?"].said == SAID["s4"]
    assert subs["How it happens"].lines() == ["1. Light is absorbed", "2. Water is split", "3. Glucose is made"]
    assert "Formula: 6CO2 + 6H2O gives C6H12O6 + 6O2" in subs["The equation"].lines()
    assert topic_of(lec, PHOTO[2].model_dump()).name == "Photosynthesis"
    assert topic_of(lec, PHOTO[4].model_dump()).name == "Respiration"


async def test_a_line_goes_to_the_slide_it_is_about_not_the_one_still_being_refined(tmp_path):
    """Real lecture 2026-10-06: the octet-rule sentence landed on "What is a chemical bond?" because that slide got
    its refined version just after the sentence; the octet-rule slide came 5 s later."""
    bond = slide("b1", "Chemical Bonding", "What is chemical bond?",
                 DefinitionBlock(term="Chemical bond", definition="Attractive force holding atoms together"))
    octet = slide("b2", "Chemical Bonding", "Octet Rule",
                  DefinitionBlock(term="Octet rule", definition="Atoms attain an inert gas electronic configuration"))
    bus = EventBus()
    log = EventLog(tmp_path / "C" / "session.sqlite")
    await log.open(bus)
    seq = [("line", "A chemical bond is the attractive force holding atoms together."),
           ("add", bond),
           ("line", "According to the octet rule atoms attain an inert gas electronic configuration."),
           ("update", bond.model_copy(update={"version": 2})),
           ("add", octet), ("line", "They gain, lose or share electrons."), ("update", octet)]
    for n, (kind, x) in enumerate(seq):
        ts = T0 + 3 * n
        if kind == "line":
            await bus.publish(TranscriptFinal(segment=TranscriptSegment(text=x, start=n, end=n + 1), ts=ts))
        else:
            await bus.publish(SlidePatch(slide_id=x.id, version=x.version, op=kind, spec=x.model_dump(), ts=ts))
    await bus.publish(DeckState(live_id="b2", slide_ids=["b1", "b2"], following=True, blank=False, ts=T0 + 30))
    await bus.drain(); await bus.close(); await log.close()
    subs = {s.title: s for s in lecture_content(rebuild(tmp_path / "C" / "session.sqlite", "C")).subtopics}
    assert subs["Octet Rule"].said[0].startswith("According to the octet rule")
    assert subs["What is chemical bond?"].said == ["A chemical bond is the attractive force holding atoms together."]


async def test_budgeted_material_never_exceeds_its_budget_and_covers_every_subtopic(tmp_path):
    long_slides = [slide(f"x{i}", f"Topic {i // 4}", f"Part {i}", pts(*[f"point {i}.{j} " + "word " * 12
                                                                        for j in range(6)])) for i in range(40)]
    said = {s.id: ["the teacher explains this part in some detail " * 6] for s in long_slides}
    await write_lecture(tmp_path, "big", slides=long_slides, said=said)
    lec = lecture_content(rebuild(tmp_path / "big" / "session.sqlite", "big"))
    assert approx_tokens(budgeted(lec.subtopics, 400, said=True)) <= 400  # too small for 40 parts: cut, never over
    for budget in (1800, 2200):  # the budgets the writer uses
        text = budgeted(lec.subtopics, budget, said=True)
        assert approx_tokens(text) <= budget
        assert all(f"[{s.key}]" in text for s in lec.subtopics)   # a fair share each, none dropped


# ---- writer -------------------------------------------------------------------------------------------------------
class FakeRouter:
    """Answers like a model would, from the prompt (or a script of answers / errors)."""

    def __init__(self, script=()):
        self.script = list(script)
        self.prompts: list[str] = []

    async def complete(self, messages, *, est_tokens, max_tokens, deadline, timeout_s=None):
        self.prompts.append(messages[-1]["content"])  # the prompt, or the repair instruction
        user = messages[1]["content"]
        text = self.script.pop(0) if self.script else self.answer(user)
        if isinstance(text, Exception):
            raise text
        return RouterResult(LLMResponse(text=text, prompt_tokens=est_tokens, completion_tokens=100), "fake", [])

    @staticmethod
    def answer(user: str) -> str:
        if '"sections"' in user:
            ids = re.findall(r"^\[(L\d+\.T\d+\.S\d+)\]", user, re.M)
            return json.dumps({"sections": [{"id": i, "text": f"Explanation of {i}."} for i in ids]})
        if '"questions"' in user:
            n = int(re.search(r"exactly (\d+)", user).group(1))
            return json.dumps({"questions": [{"text": f"Question {k}?", "type": "short" if k % 2 else "long"}
                                             for k in range(1, n + 1)]})
        if '"concepts"' in user:
            return json.dumps({"concepts": [{"term": "Photosynthesis", "meaning": "Plants making food."},
                                            {"term": "Chlorophyll", "meaning": "Green pigment."}]})
        if '"topics"' in user:
            return json.dumps({"topics": [{"title": "Photosynthesis", "points": ["Plants make food."]},
                                          {"title": "Respiration", "points": ["Glucose is broken down."]}]})
        return json.dumps({"points": ["Plants make food from light.", "Oxygen is released."]})


async def photo_lecture(tmp_path):
    await write_lecture(tmp_path, "L1")
    return lecture_content(rebuild(tmp_path / "L1" / "session.sqlite", "L1"))


async def test_an_invalid_answer_gets_one_repair_then_fails_without_inventing(tmp_path):
    lec = await photo_lecture(tmp_path)
    usage = Usage()
    good = json.dumps({"points": ["Plants make food."]})
    out = await Writer(FakeRouter(["not json at all", good])).topic_summary(lec, lec.topics[0], usage)
    assert out == ["Plants make food."] and usage.calls == 2
    with pytest.raises(MaterialError, match="not usable"):
        await Writer(FakeRouter(["nope", '{"points": []}'])).topic_summary(lec, lec.topics[0], Usage())
    with pytest.raises(MaterialError, match="no LLM answer"):
        await Writer(FakeRouter([AllProvidersFailed("quota")])).topic_summary(lec, lec.topics[0], Usage())
    with pytest.raises(MaterialError, match="LLM is off"):
        await Writer(None).topic_summary(lec, lec.topics[0], Usage())


async def test_prompts_hold_only_the_lecture_and_stay_in_budget(tmp_path):
    long_slides = [slide(f"x{i}", f"Topic {i // 5}", f"Part {i}", pts(*[f"fact {i}.{j} " + "detail " * 15
                                                                        for j in range(6)])) for i in range(60)]
    await write_lecture(tmp_path, "big", slides=long_slides, said={s.id: ["spoken words " * 40] for s in long_slides})
    lec = lecture_content(rebuild(tmp_path / "big" / "session.sqlite", "big"))
    router = FakeRouter()
    w, usage = Writer(router), Usage()
    sections = await w.note_sections([lec], usage)
    assert set(sections) == {s.key for s in lec.subtopics}       # every part explained
    assert usage.calls > 1                                       # written in several calls
    await w.lecture_summary([lec], usage)
    await w.key_concepts([lec], usage)
    await w.questions([lec], 12, usage)
    assert all(approx_tokens(p) + 100 <= PROMPT_MAX for p in router.prompts)
    assert all(approx_tokens(p) < NOTES_BUDGET + 600 for p in router.prompts if '"sections"' in p)


async def test_missing_note_sections_and_short_question_lists_are_repaired(tmp_path):
    lec = await photo_lecture(tmp_path)
    keys = [s.key for s in lec.subtopics]
    partial = json.dumps({"sections": [{"id": keys[0], "text": "Only one."}]})
    router = FakeRouter([partial])  # then the full answer
    sections = await Writer(router).note_sections([lec], Usage())
    assert set(sections) == set(keys)
    assert "missing ids" in router.prompts[1]
    few = json.dumps({"questions": [{"text": "Only?", "type": "short"}]})
    qs = await Writer(FakeRouter([few])).questions([lec], 6, Usage())
    assert len(qs) == 6 and {q.type for q in qs} == {"short", "long"}


def test_parse_json_explains_what_is_wrong():
    assert parse_json('Sure! {"points": ["a"]} done', _Points).points == ["a"]
    with pytest.raises(ValueError, match="points"):
        parse_json('{"points": []}', _Points)
    with pytest.raises(ValueError, match="no JSON"):
        parse_json("nothing", _Points)


# ---- store + slides -----------------------------------------------------------------------------------------------
def test_names_rename_share_and_remove(tmp_path):
    assert auto_name("notes", "Photosynthesis", T0).startswith("Photosynthesis - Notes - ")
    assert auto_name("notes", "Photosynthesis", T0).endswith(".pdf")
    assert clean_name('My: notes/v2?.pdf', "notes") == "My notes v2.pdf"
    assert clean_name("", "pptx") == "Slides.pptx"
    store = MaterialStore(tmp_path)
    m = store.new("notes", "", "Photosynthesis", ["L1"])
    store.file_for(m).write_bytes(b"%PDF-1.4")
    assert store.rename(m.id, "Chapter 1 notes") and store.get(m.id).name == "Chapter 1 notes.pdf"
    assert store.share(m.id, True) and store.get(m.id).shared
    p = store.new("pptx", "", "Photosynthesis", ["L1"])
    assert not store.share(p.id, True)                         # only PDFs go to students
    again = MaterialStore(tmp_path)
    assert again.get(p.id).status == "failed" and "interrupted" in again.get(p.id).detail  # was working
    assert again.remove(m.id) and not (tmp_path / f"{m.id}.pdf").exists()


def test_summary_and_concept_slides_are_marked_and_split_evenly():
    assert [len(c) for c in _balanced(list(range(7)), 3)] == [3, 2, 2]
    assert [len(c) for c in _balanced(list(range(4)), 3)] == [2, 2]
    s = topic_summary_slide("Photosynthesis", ["a", "b"])
    assert s.origin == "materials" and s.subtitle == "Photosynthesis"
    parts = lecture_summary_slides("Bio", [(f"T{i}", ["x"]) for i in range(5)])
    assert [p.part for p in parts] == [1, 2] and parts[1].continuation_of == parts[0].id
    assert parts[0].blocks[0].style == "list" and len(parts[0].blocks[0].groups) == 3
    ks = key_concepts_slides("Bio", [Concept(term=f"t{i}", meaning="m") for i in range(8)])
    assert [len(k.blocks[0].facts) for k in ks] == [4, 4] and ks[0].blocks[0].style == "terms"


# ---- service ------------------------------------------------------------------------------------------------------
class FakeRenderer:
    def __init__(self):
        self.pdfs: list[str] = []
        self.pptx_calls: list[tuple[int, str]] = []

    async def pdf(self, page_html, out, footer_title):
        self.pdfs.append(page_html)
        out.write_bytes(b"%PDF-1.4 fake")

    async def pptx(self, slides, theme, out, title="", frames_dir=None):
        self.pptx_calls.append((len(slides), theme))
        out.write_bytes(b"PK fake")
        return len(slides)


async def service_stack(tmp_path, router, current_slides=PHOTO):
    sessions = tmp_path / "sessions"
    await write_lecture(sessions, "past", slides=PHOTO[1:3])
    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    log = EventLog(sessions / "now" / "session.sqlite")
    await log.open(bus)
    for s in current_slides:
        await deck.add(s.model_copy())
    for lines in SAID.values():
        for line in lines:
            await bus.publish(TranscriptFinal(segment=TranscriptSegment(text=line, start=1, end=2)))
    await bus.drain()
    renderer = FakeRenderer()
    svc = MaterialsService(bus, MaterialStore(tmp_path / "materials"), LectureArchive(sessions, tmp_path / "a.json",
                           current_id="now"), deck, Writer(router), renderer, "now", flush=log.flush)
    svc.attach()
    states: list[MaterialsState] = []

    async def keep(e):
        states.append(e)
    bus.subscribe("t", keep, [MaterialsState])
    return bus, deck, svc, renderer, states, log


async def create(bus, svc, items, lectures=(), current=True):
    await bus.publish(CommandReceived(command=Command(kind="materials_create", args={
        "items": items, "lectures": list(lectures), "current": current})))
    await bus.drain()
    assert await svc.wait_idle(10)
    await bus.drain()


async def test_a_topic_summary_is_shown_on_the_projector_and_the_lecture_goes_on(tmp_path):
    router = FakeRouter()
    bus, deck, svc, _, states, log = await service_stack(tmp_path, router)
    await bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": "s2"})))
    await create(bus, svc, [{"kind": "summary", "scope": "topic"}])
    live = deck.live
    assert live.origin == "materials" and live.subtitle == "Photosynthesis" and live.title == "Summary"
    assert "Respiration" not in router.prompts[0] and "TOPIC: Photosynthesis" in router.prompts[0]
    assert deck.following                                 # the next lecture slide takes the screen again
    m = svc.store.items()[0]
    assert m.status == "ready" and m.tokens > 0 and m.slide_ids == [live.id]
    await svc.close(); await bus.close(); await log.close()


async def test_notes_and_concepts_together_write_the_concepts_once(tmp_path):
    router = FakeRouter()
    bus, deck, svc, renderer, states, log = await service_stack(tmp_path, router)
    await create(bus, svc, [{"kind": "concepts"}, {"kind": "notes", "name": "My notes"}], lectures=["past"])
    assert sum('"concepts"' in p for p in router.prompts) == 1
    notes = next(m for m in svc.store.items() if m.kind == "notes")
    assert notes.status == "ready" and notes.name == "My notes.pdf" and notes.shared and notes.lectures == ["now", "past"]
    page = renderer.pdfs[0]
    assert "Explanation of L1.T1.S1." in page and "Key concepts" in page and "Chlorophyll" in page
    assert "Lecture 2" in page                             # two lectures: one part each
    assert deck.live.layout == "facts" and deck.live.blocks[0].style == "terms"
    assert states[-1].shared and states[-1].shared[0]["name"] == "My notes.pdf"
    await svc.close(); await bus.close(); await log.close()


async def test_without_the_llm_only_the_pptx_is_made_and_the_reason_is_shown(tmp_path):
    bus, deck, svc, renderer, states, log = await service_stack(tmp_path, None)
    await create(bus, svc, [{"kind": "assignment", "count": 5}, {"kind": "pptx", "theme": "dark"}])
    by = {m.kind: m for m in svc.store.items()}
    assert by["assignment"].status == "failed" and "LLM" in by["assignment"].detail
    assert by["pptx"].status == "ready" and renderer.pptx_calls == [(5, "dark")] and not by["pptx"].shared
    assert states[-1].llm is False
    await svc.close(); await bus.close(); await log.close()


async def test_an_assignment_has_the_chosen_number_of_questions(tmp_path):
    bus, deck, svc, renderer, states, log = await service_stack(tmp_path, FakeRouter())
    await create(bus, svc, [{"kind": "assignment", "count": 7}])
    m = svc.store.items()[0]
    assert m.status == "ready" and m.count == 7 and renderer.pdfs[0].count('class="marks"') == 7
    await svc.close(); await bus.close(); await log.close()


async def test_material_slides_are_not_taught_content(tmp_path):
    router = FakeRouter()
    bus, deck, svc, _, _, log = await service_stack(tmp_path, router)
    await create(bus, svc, [{"kind": "summary", "scope": "lecture"}])
    await create(bus, svc, [{"kind": "notes"}])
    notes_prompt = next(p for p in router.prompts if '"sections"' in p)
    assert "Lecture summary" not in notes_prompt and "Plants make food." not in notes_prompt
    await svc.close(); await bus.close(); await log.close()


async def test_rename_share_remove_and_hide_by_command(tmp_path):
    bus, deck, svc, _, states, log = await service_stack(tmp_path, FakeRouter())
    await create(bus, svc, [{"kind": "notes"}])
    mid = svc.store.items()[0].id
    for kind, args in (("materials_rename", {"id": mid, "name": "Week 1"}), ("materials_share", {"id": mid, "on": False})):
        await bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await bus.drain()
    assert svc.store.get(mid).name == "Week 1.pdf" and not svc.store.get(mid).shared and states[-1].shared == []
    await bus.publish(CommandReceived(command=Command(kind="lecture_hide", args={"id": "past"})))
    await bus.publish(CommandReceived(command=Command(kind="materials_remove", args={"id": mid})))
    await bus.drain()
    assert svc.store.items() == [] and states[-1].lectures_changed == 1 and svc.archive.lectures() == []
    await svc.close(); await bus.close(); await log.close()


async def test_the_hub_sends_materials_to_control_and_only_shared_pdfs_to_students():
    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    control, viewer = hub.connect("control"), hub.connect("viewer")
    await control.next_batch(); await viewer.next_batch()
    await bus.publish(MaterialsState(items=[{"id": "a", "name": "secret plan.pptx"}], shared=[{"id": "b", "name": "Notes.pdf"}],
                                     current={"id": "now", "title": "Photosynthesis"}, llm=True))
    await bus.drain()
    c = await control.next_batch()
    v = await viewer.next_batch()
    assert any(m["type"] == "materials" and m["items"][0]["name"] == "secret plan.pptx" for m in c)
    assert v == [{"type": "shared", "items": [{"id": "b", "name": "Notes.pdf"}]}]
    assert hub.hello("viewer")["shared"] == [{"id": "b", "name": "Notes.pdf"}] and "materials" not in hub.hello("viewer")
    await bus.close()


async def test_deck_present_shows_the_first_new_slide():
    bus = EventBus()
    deck = Deck(bus)
    deck.attach()
    for s in PHOTO[:3]:
        await deck.add(s.model_copy())
    await bus.publish(CommandReceived(command=Command(kind="goto", args={"slide_id": "s1"})))
    await bus.drain()
    added = await deck.present([topic_summary_slide("P", ["a"]), topic_summary_slide("P", ["b"])])
    assert deck.live_id == added[0].id and not deck.following and deck.slides[-1].id == added[1].id
    await bus.close()


def test_only_a_peer_reset_while_closing_is_quiet():
    """Real app 2026-10-07: 'Exception in callback _ProactorBasePipeTransport._call_connection_lost' after the PPTX
    renderer's Edge closed. That case alone is quiet; other loop errors still reach the default handler."""
    from copilot.app.main import quiet_peer_resets

    reported = []

    class Loop:
        def default_exception_handler(self, context):
            reported.append(context)

    class Handle:
        def __repr__(self):
            return "<Handle _ProactorBasePipeTransport._call_connection_lost(None)>"
    quiet_peer_resets(Loop(), {"exception": ConnectionResetError(10054, "reset"), "handle": Handle()})
    assert reported == []
    quiet_peer_resets(Loop(), {"exception": ConnectionResetError(10054, "reset"), "handle": "<Handle other()>"})
    quiet_peer_resets(Loop(), {"exception": ValueError("a real bug"), "handle": Handle()})
    assert len(reported) == 2


async def test_router_takes_a_longer_timeout_for_one_call():
    from copilot.llm.providers import ProviderConfig
    from copilot.llm.ratelimit import RateLimiter
    from copilot.llm.router import Entry, LLMRouter

    seen = []

    class P:
        name = "p"
        cfg = ProviderConfig(name="p", base_url="http://x", model="m")

        async def complete(self, messages, *, max_tokens, timeout):
            seen.append(timeout)
            return LLMResponse(text="{}")
    router = LLMRouter([Entry(P(), RateLimiter(30, 8000))])
    import time
    await router.complete([], est_tokens=10, max_tokens=10, deadline=time.monotonic() + 100)
    await router.complete([], est_tokens=10, max_tokens=10, deadline=time.monotonic() + 100, timeout_s=45)
    assert seen == [6.0, 45]
