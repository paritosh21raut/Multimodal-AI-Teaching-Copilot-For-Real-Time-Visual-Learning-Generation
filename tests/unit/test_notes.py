"""The teacher's PDF notes in /control (F-009 §2): stored on the laptop, rendered page by page, following the lecture.
Never sent to the projector or the students."""
from pathlib import Path

import numpy as np
import pytest

from copilot.core.bus import EventBus
from copilot.core.events import Command, CommandReceived, DeckState, NotesState, SlidePatch
from copilot.display.hub import DisplayHub
from copilot.notes.library import BadNotes, NotesLibrary
from copilot.notes.service import FOLLOW_MIN, NotesService, choose_page, slide_text

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


def test_choose_page_needs_a_clear_and_better_match():
    s = np.array([0.2, 0.8, 0.5, 0.79])
    assert choose_page(s, current=1) == 2
    assert choose_page(s, current=2) is None           # already there
    assert choose_page(s, current=4) is None           # the page shown is as good (within the margin)
    assert choose_page(np.array([0.2, FOLLOW_MIN - 0.01]), current=1) is None  # nothing clearly about the slide


def test_slide_text_reads_the_slide_not_its_plumbing():
    spec = {"id": "s1", "title": "How photosynthesis works", "subtitle": "Photosynthesis", "layout": "process_flow",
            "blocks": [{"type": "process", "id": "b", "steps": [{"id": "x", "label": "Light is absorbed"}]},
                       {"type": "image", "id": "i", "url": "/media/abc.jpg", "alt": "leaf", "image_id": "abc"}]}
    text = slide_text(spec)
    assert text.startswith("How photosynthesis works Photosynthesis") and "Light is absorbed" in text
    assert "media" not in text and "process_flow" not in text and "leaf" not in text
    # a formula: its words, not its TeX source (the real-app run matched "The equation" to the wrong page)
    formula = {"id": "f", "title": "The equation", "blocks": [{"type": "formula", "id": "f1",
               "latex": r"\text{6}\,\text{CO}_{\text{2}} \xrightarrow{\text{sunlight}}", "spoken": "6CO2 gives glucose"}]}
    assert slide_text(formula) == "The equation 6CO2 gives glucose"


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


async def test_open_notes_follow_the_live_slide_and_a_hand_turned_page_holds(tmp_path):
    bus, svc, doc, states = await _service(tmp_path)
    await cmd(bus, "notes_open", id=doc.id)
    assert states[-1].open == doc.id and states[-1].pages == 7 and states[-1].page == 1
    await _live(bus, "s1", "What photosynthesis needs", "Sunlight, water, carbon dioxide and chlorophyll",
                "Water enters through the roots; carbon dioxide through stomata")
    assert states[-1].page == 3 and states[-1].matched == "What photosynthesis needs"
    await cmd(bus, "notes_page", page=6)  # the teacher turns to another page
    await _live(bus, "s1", "What photosynthesis needs", "Sunlight, water, stomata, stomata")  # same slide grows
    assert states[-1].page == 6
    await _live(bus, "s2", "Respiration", "Respiration releases energy from glucose, respiration")  # next slide
    assert states[-1].page == 7
    await cmd(bus, "notes_follow", on=False)
    await _live(bus, "s3", "The equation", "glucose equation")
    assert states[-1].page == 7 and states[-1].follow is False
    await bus.close()


async def test_without_the_model_the_panel_says_why_following_is_off(tmp_path):
    bus, svc, doc, states = await _service(tmp_path, embedder=None)
    await cmd(bus, "notes_open", id=doc.id)
    await _live(bus, "s1", "Respiration", "Respiration releases energy")
    assert states[-1].page == 1 and "matching model" in states[-1].reason
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
