"""The teacher's PDF notes in /control (F-009 §2): stored on the laptop, rendered page by page, turned by the teacher
(F-013: following the lecture was removed). Never sent to the projector or the students."""
from pathlib import Path

import numpy as np
import pytest

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, DeckState, NotesState, SlidePatch
from copilot.display.hub import DisplayHub
from copilot.notes.library import BadNotes, NotesLibrary
from copilot.notes.service import NotesService

PDF = Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "photosynthesis_notes.pdf"


class WordsEmbedder:
    """Bag of words over a fixed vocabulary: enough to test the service's decisions without the model."""
    VOCAB = ["photosynthesis", "meaning", "needs", "water", "stomata", "steps", "glucose", "equation", "matters",
             "respiration", "lesson", "attendance", "sunlight", "chlorophyll", "oxygen", "energy"]

    def embed(self, texts):
        out = []
        for t in texts:
            words = t.lower().replace(",", " ").replace(".", " ").split()
            v = np.array([sum(w.startswith(k) for w in words) for k in self.VOCAB], dtype=np.float32) + 1e-3
            out.append(v / np.linalg.norm(v))
        return np.stack(out)


def lib(tmp_path) -> NotesLibrary:
    return NotesLibrary(tmp_path / "notes")


def test_library_stores_the_pdf_once_with_page_texts(tmp_path):
    notes = lib(tmp_path)
    data = PDF.read_bytes()
    doc = notes.add(data, "C:\\Users\\me\\photosynthesis_notes.pdf")
    assert doc.pages == 7 and doc.has_text and doc.name == "photosynthesis_notes.pdf"
    assert notes.add(data, "again.pdf").id == doc.id and len(notes.docs()) == 1
    texts = notes.page_texts(doc.id)
    assert "stomata" in texts[2] and "Respiration" in texts[6]
    png = notes.render(doc.id, 3, 700)
    assert png is not None and png.read_bytes()[:4] == b"\x89PNG" and png.name == "p3-w720.png"
    assert notes.render(doc.id, 8, 700) is None and notes.render("../../etc", 1, 700) is None
    assert notes.remove(doc.id) and notes.docs() == [] and not (tmp_path / "notes" / f"{doc.id}.pdf").exists()


def test_library_refuses_files_that_are_not_pdfs(tmp_path):
    with pytest.raises(BadNotes):
        lib(tmp_path).add(b"<html>not a pdf</html>", "x.pdf")
    with pytest.raises(BadNotes):
        lib(tmp_path).add(b"%PDF-1.7 broken", "x.pdf")


async def _service(tmp_path, embedder=WordsEmbedder()):
    bus = EventBus()
    library = lib(tmp_path)
    doc = library.add(PDF.read_bytes(), "photosynthesis_notes.pdf")
    svc = NotesService(bus, library, embedder)
    svc.attach()
    states: list[NotesState] = []

    async def grab(e):
        states.append(e)
    bus.subscribe("t_notes", grab, [NotesState])
    return bus, svc, doc, states


async def _live(bus, slide_id, title, *texts):
    spec = {"id": slide_id, "title": title, "blocks": [{"type": "points", "id": "p",
                                                         "items": [{"id": f"i{n}", "text": t} for n, t in enumerate(texts)]}]}
    await bus.publish(SlidePatch(slide_id=slide_id, version=1, op="add", spec=spec))
    await bus.publish(DeckState(live_id=slide_id, slide_ids=[slide_id], following=True, blank=False))
    await bus.drain()


async def cmd(bus, kind, **args):
    await bus.publish(CommandReceived(command=Command(kind=kind, args=args, origin="control")))
    await bus.drain()


async def test_the_lecture_never_turns_the_teachers_page(tmp_path):
    """User 2026-10-17: following turned pages early and sometimes back; only the teacher turns them now."""
    bus, svc, doc, states = await _service(tmp_path)
    await cmd(bus, "notes_open", id=doc.id)
    assert states[-1].open == doc.id and states[-1].pages == 7 and states[-1].page == 1
    await _live(bus, "s1", "What photosynthesis needs", "Sunlight, water, carbon dioxide and chlorophyll",
                "Water enters through the roots; carbon dioxide through stomata")
    await _live(bus, "s2", "Respiration", "Respiration releases energy from glucose, respiration")
    assert states[-1].page == 1 and svc.page == 1
    await cmd(bus, "notes_page", page=6)
    await _live(bus, "s3", "The equation", "glucose equation")
    assert states[-1].page == 6
    await cmd(bus, "notes_page", page=9)  # past the last page: ignored
    assert states[-1].page == 6
    await bus.close()


async def test_removed_notes_close_and_the_last_open_notes_reopen_next_time(tmp_path):
    bus, svc, doc, states = await _service(tmp_path)
    await cmd(bus, "notes_open", id=doc.id)
    again = NotesService(EventBus(), lib(tmp_path))
    again.attach()
    assert again.state().open == doc.id  # the next lecture opens the same notes
    await cmd(bus, "notes_remove", id=doc.id)
    assert states[-1].open == "" and states[-1].docs == []
    await bus.close()


async def test_notes_reach_only_the_control_view(tmp_path):
    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    conns = {r: hub.connect(r) for r in ("display", "control", "viewer")}
    for c in conns.values():
        await c.next_batch()
    await bus.publish(NotesState(docs=[{"id": "a"}], open="a", page=2, pages=7))
    await bus.publish(DeckState(live_id=None, slide_ids=[], following=True, blank=False))  # every page gets this
    await bus.drain()
    got = {r: await c.next_batch() for r, c in conns.items()}
    assert any(m["type"] == "notes" and m["page"] == 2 for m in got["control"])
    assert not any(m["type"] == "notes" for m in got["display"] + got["viewer"])
    assert hub.hello("control")["notes"]["open"] == "a" and "notes" not in hub.hello("viewer")
    await bus.close()
