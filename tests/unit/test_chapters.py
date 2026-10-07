"""Chapters of lectures + lecture search (F-010b §2, §3, §4): numbering by position, delete → Unsorted, the start
card's chapter (not stored for a test run), materials from whole chapters, search over titles + slide content only."""
from copilot.core.events import Command, CommandReceived
from copilot.materials.archive import LectureArchive, search
from copilot.materials.chapters import ChapterBook
from copilot.presentation.spec import DefinitionBlock

from tests.unit.test_materials import PHOTO, FakeRouter, service_stack, slide, write_lecture


def test_chapters_are_numbered_by_position_and_deleting_one_keeps_its_lectures(tmp_path):
    book = ChapterBook(tmp_path / "chapters.json")
    a, b = book.create("Cells"), book.create("  Plant   biology ")
    assert [c["label"] for c in book.chapters()] == ["Chapter 1 · Cells", "Chapter 2 · Plant biology"]
    assert book.move(b, 0) and [c["label"] for c in book.chapters()] == ["Chapter 1 · Plant biology",
                                                                          "Chapter 2 · Cells"]
    assert book.assign("lec1", a) and book.assign("lec2", a) and book.chapter_of("lec1") == a
    assert not book.assign("lec3", "nope")                       # an unknown chapter: nothing changes
    assert book.rename(a, "Cell structure") and not book.rename(a, "Cell structure")
    again = ChapterBook(tmp_path / "chapters.json")              # it is kept on disk
    assert again.get(a)["label"] == "Chapter 2 · Cell structure" and sorted(again.lectures_in(a)) == ["lec1", "lec2"]
    assert again.delete(a) and again.chapter_of("lec1") == "" and [c["id"] for c in again.chapters()] == [b]
    assert again.assign("lec1", b) and again.assign("lec1", "") and again.chapter_of("lec1") == ""


async def command(bus, kind, **args):
    await bus.publish(CommandReceived(command=Command(kind=kind, args=args)))
    await bus.drain()


async def test_the_start_card_puts_this_lecture_in_a_chapter_and_remembers_it(tmp_path):
    bus, deck, svc, _, states, log = await service_stack(tmp_path, FakeRouter())
    await command(bus, "chapter_create", name="Plants", start=True)
    cid = states[-1].chapters[0]["id"]
    assert states[-1].current["chapter"] == cid and states[-1].last_chapter == cid
    await command(bus, "chapter_create", name="Animals")
    other = states[-1].chapters[1]["id"]
    await command(bus, "lecture_move", id="past", chapter=other)
    assert svc.chapters.chapter_of("past") == other and states[-1].lectures_changed >= 2
    await command(bus, "chapter_delete", id=other)
    assert svc.chapters.chapter_of("past") == "" and len(states[-1].chapters) == 1
    await svc.close(); await bus.close(); await log.close()


async def test_a_test_run_stays_unsorted_but_can_be_moved_by_hand(tmp_path):
    bus, deck, svc, _, states, log = await service_stack(tmp_path, FakeRouter())
    svc.test_run = True
    await command(bus, "chapter_create", name="Plants", start=True)
    cid = states[-1].chapters[0]["id"]
    assert states[-1].current["chapter"] == ""                   # the chapter is made, the lecture not put in it
    await command(bus, "lecture_move", chapter=cid, start=True)
    assert svc.chapters.chapter_of("now") == "" and states[-1].current["test_run"] is True
    await command(bus, "lecture_move", id="now", chapter=cid)  # dragged by the teacher later: kept
    assert svc.chapters.chapter_of("now") == cid
    await svc.close(); await bus.close(); await log.close()


async def test_materials_from_whole_chapters_use_every_lecture_in_them(tmp_path):
    router = FakeRouter()
    bus, deck, svc, renderer, states, log = await service_stack(tmp_path, router)
    await write_lecture(tmp_path / "sessions", "older", slides=PHOTO[1:2])
    plants, other = svc.chapters.create("Plants"), svc.chapters.create("Other")
    for lid in ("now", "past"):
        svc.chapters.assign(lid, plants)
    svc.chapters.assign("older", other)
    await bus.publish(CommandReceived(command=Command(kind="materials_create", args={
        "items": [{"kind": "notes"}], "lectures": [], "current": False, "chapters": [plants]})))
    await bus.drain()
    assert await svc.wait_idle(10)
    m = svc.store.items()[0]
    assert m.status == "ready" and m.lectures == ["now", "past"] and m.title == "Chapter 1 · Plants"
    assert m.name.startswith("Chapter 1 · Plants - Notes")
    await svc.close(); await bus.close(); await log.close()


async def test_search_finds_titles_and_slide_content_but_not_the_transcript(tmp_path):
    sessions = tmp_path / "sessions"
    await write_lecture(sessions, "photo")
    await write_lecture(sessions, "cells", slides=[
        slide("c1", "Cells", "What is a cell?", DefinitionBlock(term="Cell", definition="The unit of life; it has a nucleus.")),
        slide("c2", "Cells", "Parts of a cell", DefinitionBlock(term="Membrane", definition="Holds the chlorophyll-free cell.")),
    ], said={"c1": ["A cell is small.", "Glucose is everywhere.", "Really."]})
    records = LectureArchive(sessions, tmp_path / "a.json").lectures()
    hits = {r["id"]: r for r in search(records, "nucleus")}
    assert list(hits) == ["cells"] and hits["cells"]["hits"][0]["index"] == 0
    assert [r["id"] for r in search(records, "photosynthesis")][0] == "photo"   # in the title first
    eq = search(records, "carbon dioxide")                       # a formula variable's meaning on slide s3
    assert [r["id"] for r in eq] == ["photo"] and eq[0]["hits"][0]["title"] == "The equation"
    assert search(records, "everywhere") == []                   # said only, never on a slide: no hit
    assert search(records, "  ") == []
