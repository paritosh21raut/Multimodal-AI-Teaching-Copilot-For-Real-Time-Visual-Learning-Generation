"""F-013 S4: images (a figure the teacher turns to, a picture per concept card, no repeat across topics, pictures for
the subtopics of a visual topic), figures from the teacher's own PDFs (drawn figures, captions), educational web
pages, and robustness on a full disk. Real lines from the user's material and the tests 1-30 where there are any."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pytest

from copilot.core.events import ConceptSignal
from tests.unit.test_presentation_engine import make, ready, send
from tests.unit.test_presentation_images import Requests, act, answer, image, img, with_visual

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "drawn_figures.pdf"


# ---- the figure cue ----------------------------------------------------------------------------------------------
def test_a_figure_the_teacher_turns_to_is_a_cue():
    from copilot.understanding.cues import detect, figure_query

    def fig(line):
        c = detect(line).of("figure")
        return figure_query(c) if c else None
    assert fig("Now let's look at the block diagram of STM32.") == "STM32 block diagram"  # user 2026-10-17
    assert fig("Let us see the STM32 block diagram.") == "STM32 block diagram"
    assert fig("This is the pin diagram of 8051 microcontroller.") == "8051 microcontroller pin diagram"
    assert fig("So now we will draw the ray diagram for a convex lens.") == "Convex lens ray diagram"
    assert fig("Let us see the diagram of a typical cell.") == "Cell diagram"
    for line in ("Look at the diagram.", "Let's look at the following diagram.", "Let us study the structure of the heart.",
                 "The block diagram is very important."):
        assert fig(line) is None, line


async def _signal(bus, figure, seg="sig-1"):
    await send(bus, ConceptSignal(segment_id=seg, shift_score=0.0, figure=figure))


async def test_the_asked_figure_lands_even_on_a_slide_no_automatic_image_could_take():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await send(bus, ready("STM32", "Boot sequence", [act("process", steps=["Reset", "Load vector table", "Run main"])],
                          relation="new_topic"))
    assert not reqs.items  # a process diagram needs the full width: no automatic image
    await _signal(bus, "STM32 block diagram")
    assert [(r.query, r.kind, r.reason) for r in reqs.items] == [("STM32 block diagram", "diagram", "asked")]
    await answer(bus, reqs.items[0], [img(7, title="STM32F405 Block Diagram.png")])
    shown = [s for s in deck.slides if image(s) is not None]
    assert shown and image(shown[0]).image_id == f"{7:016x}"
    await eng.stop()


# ---- D2: no repeat across topics ---------------------------------------------------------------------------------
async def test_an_image_of_one_topic_is_not_offered_to_another():
    """test30: 13 images repeated, several across topics (a semiconductor diagram on the p-n junction slides)."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Solar System", "Saturn", [act("explanation", points=["Saturn has rings"])],
                                      relation="new_topic"), "Saturn"))
    await answer(bus, reqs.items[0], [img(1)])
    for point in ("Rings form from orbiting dust", "Ice and rock make up the rings"):  # a new topic needs 2 units
        await send(bus, with_visual(ready("Rings in Physics", "Ring structures", [act("explanation", points=[point])],
                                          relation="new_topic"), "planetary rings"))
    req = next(r for r in reqs.items if r.query == "planetary rings")
    assert f"{1:016x}" in req.exclude  # shown under "Solar System"
    await answer(bus, req, [img(1), img(2)])  # a cached answer still holds it: the next one is taken
    assert image(deck.live).image_id == f"{2:016x}"
    await eng.stop()


# ---- D1: a picture for each concept card / each subtopic of a visual topic ----------------------------------------
PLANETS = [act("definition", term=t, definition=d) for t, d in (
    ("Mars", "The red planet, fourth from the Sun"), ("Jupiter", "The largest planet, a gas giant"),
    ("Saturn", "A gas giant known for its rings"))]


async def _visual_topic(bus, reqs):
    """test21: the Solar System lecture's first slide got its picture from the model's hint."""
    await send(bus, with_visual(ready("Solar System", "Overview", [act("explanation", points=[
        "The Sun and eight planets"])], relation="new_topic"), "solar system"))
    await answer(bus, reqs.items[-1], [img(30)])


async def test_each_planet_card_gets_its_picture_together():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await _visual_topic(bus, reqs)
    before = len(reqs.items)
    await send(bus, ready("Solar System", "Planets", PLANETS, relation="sibling_concept"))
    items = [r for r in reqs.items[before:] if r.reason.startswith("item:")]
    assert [r.query for r in items] == ["Mars planet", "Jupiter planet", "Saturn planet"]
    for k, r in enumerate(items[:2]):
        await answer(bus, r, [img(40 + k)])
    defs = [b for b in deck.live.blocks if b.type == "definition"]
    assert all(d.image is None for d in defs)  # all or none: the third is still on its way
    await answer(bus, items[2], [img(42)])
    defs = [b for b in deck.live.blocks if b.type == "definition"]
    assert [d.image.image_id for d in defs] == [f"{40 + k:016x}" for k in range(3)]
    await eng.stop()


async def test_no_card_pictures_when_one_concept_has_none():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await _visual_topic(bus, reqs)
    before = len(reqs.items)
    await send(bus, ready("Solar System", "Planets", PLANETS, relation="sibling_concept"))
    items = [r for r in reqs.items[before:] if r.reason.startswith("item:")]
    await answer(bus, items[0], [img(50)])
    await answer(bus, items[1], [], reason="no relevant image")
    await answer(bus, items[2], [img(52)])
    assert all(b.image is None for b in deck.live.blocks if b.type == "definition")
    await eng.stop()


async def test_abstract_concepts_get_no_card_pictures():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await _visual_topic(bus, reqs)
    before = len(reqs.items)
    await send(bus, ready("Solar System", "Laws", [act("definition", term=t, definition="...") for t in (
        "Kinetic energy", "Potential energy")], relation="sibling_concept"))
    assert not [r for r in reqs.items[before:] if r.reason.startswith("item:")]
    await eng.stop()


async def test_a_subtopic_naming_a_thing_in_a_visual_topic_gets_a_picture():
    """test13: Forebrain and Hindbrain had pictures; Hypothalamus, Tectum and Pons none (no hint from the model)."""
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Human Brain", "Forebrain", [act("explanation", points=[
        "The forebrain is the largest part of the brain"])], relation="new_topic"), "forebrain diagram", "diagram"))
    await answer(bus, reqs.items[-1], [img(60)])
    await send(bus, ready("Human Brain", "Hypothalamus", [act("explanation", points=[
        "The hypothalamus controls body temperature and hunger"])], relation="sibling_concept"))
    # the sibling rule names it after Forebrain's hint ("forebrain diagram" -> "Hypothalamus diagram")
    assert (reqs.items[-1].query, reqs.items[-1].kind, reqs.items[-1].reason) == ("Hypothalamus diagram", "diagram", "auto")
    await send(bus, ready("Human Brain", "Pons", [act("explanation", points=[
        "The pons relays signals between the cerebrum and the cerebellum"])], relation="sibling_concept"))
    assert reqs.items[-1].query in ("Pons diagram", "Pons")
    await eng.stop()


async def test_the_topic_rule_names_a_subtopic_when_no_sibling_hint_fits():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Human Brain", "Overview", [act("explanation", points=[
        "The brain controls the whole body"])], relation="new_topic"), "human brain", "diagram"))
    await answer(bus, reqs.items[-1], [img(61)])
    await send(bus, ready("Human Brain", "Medulla Oblongata", [act("explanation", points=[
        "The medulla oblongata controls breathing and heart rate"])], relation="sibling_concept"))
    assert (reqs.items[-1].query, reqs.items[-1].kind) == ("Medulla Oblongata", "diagram")
    await eng.stop()


# ---- figures from the teacher's PDFs ------------------------------------------------------------------------------
def test_caption_lines():
    from copilot.notes.reference import caption_text
    # lines of the user's PDFs (STM32 IDE book, ESP-WROOM-32 datasheet)
    assert caption_text("Figure 3.1: The Target Selection wizard - STEP 1") == "The Target Selection wizard - STEP 1"
    assert caption_text("Figure 1: ESP32-WROOM-32 Pin Layout (Top View)") == "ESP32-WROOM-32 Pin Layout (Top View)"
    assert caption_text("Fig. 2 - Block diagram") == "Block diagram"
    assert caption_text("Figure 3.5 shows what appears in the STM32CubeIDE after the project") == ""  # a sentence
    assert caption_text("Table 2: Pin Definitions") == ""


def test_drawn_figures_come_out_without_the_table_or_the_note(tmp_path):
    """The ESP-WROOM-32 datasheet has no image objects: its pin layout and schematics are drawings (6 now found)."""
    from copilot.notes.reference import extract_figures

    figs = extract_figures(FIXTURE, tmp_path, "pdf", "drawn_figures.pdf")
    assert [(f.page, f.caption, f.drawn) for f in figs] == [
        (1, "Block diagram of a microcontroller", True), (2, "Reset circuit", True)]
    w, h = figs[0].width, figs[0].height
    assert 1.5 < w / h < 2.2  # the diagram (450 x 210 pt + margin), not diagram + note + table (~1:1.3)
    assert figs[0].label.startswith("Figure 1: Block diagram of a microcontroller")
    # page 2's circuit is a form XObject scaled 1.4: placed where the page shows it, not at the form's origin
    assert 2.2 < figs[1].width / figs[1].height < 3.4
    assert (tmp_path / "f1.png").is_file() and (tmp_path / "f2.png").is_file()


def test_own_figure_caption_gate():
    from copilot.visuals.service import caption_matches
    assert caption_matches("ESP32-WROOM-32 Pin Layout (Top View)", "ESP32 pin layout")
    assert caption_matches("STM32F405 Block Diagram", "STM32 block diagram")
    assert not caption_matches("ESP32-WROOM-32 Schematics", "ESP32 block diagram")  # a schematic is not asked
    assert not caption_matches("Reflow Profile", "ESP32 pin layout")


# ---- educational web pages ---------------------------------------------------------------------------------------
PAGE = """<html><head><title>STM32 Memory Map - STM32World Wiki</title></head><body>
<img src="/logo.png" alt="STM32World logo" width="120" height="40">
<h2>Block diagram</h2>
<figure><img src="/images/f/fa/STM32F405_Block_Diagram.png" width="800" height="600" alt="">
<figcaption>STM32F405 Block Diagram</figcaption></figure>
<h2>Memory</h2><img data-src="/images/memory_map.png" alt="STM32 memory map" width="700" height="900">
<img src="/images/author.jpg" alt="author photo" width="300" height="300"></body></html>"""


def test_figures_named_on_a_page():
    from copilot.visuals.webpages import match_score, page_figures

    got = page_figures(PAGE, "https://stm32world.com/wiki/STM32_Memory_Map", "STM32 block diagram")
    assert [c.image_url for c in got] == ["https://stm32world.com/images/f/fa/STM32F405_Block_Diagram.png"]
    assert got[0].source == "web" and got[0].licence == "© stm32world.com" and got[0].title == "STM32F405 Block Diagram"
    assert match_score("STM32 memory map", "STM32 block diagram") == 0  # the figure type was asked
    assert match_score("ESP32 function block diagram", "STM32 block diagram") == 0  # another chip


def test_search_results_that_do_not_name_the_subject_are_dropped():
    """Bing sometimes answers a script with unrelated pages ("nephron diagram" -> Chrome downloads, 2026-10-17)."""
    import base64

    from copilot.visuals.webpages import _bing_results, _bing_target

    target = "https://www.kenhub.com/en/library/anatomy/nephron"
    href = "https://www.bing.com/ck/a?!&amp;&amp;p=1&amp;u=a1" + base64.urlsafe_b64encode(target.encode()).decode().rstrip("=")
    assert _bing_target(href.replace("&amp;", "&")) == target
    html = (f'<li class="b_algo"><h2><a href="{href}">Nephron - Kenhub</a></h2></li>'
            '<li class="b_algo"><h2><a href="https://www.google.com/chrome/">Google Chrome</a></h2></li>')
    assert [u for u, _ in _bing_results(html)] == [target, "https://www.google.com/chrome/"]


def test_web_figures_are_not_refused_for_their_licence_and_block_diagrams_meet_fair_decoys():
    from copilot.visuals.filters import reject_reason
    from copilot.visuals.finder import DISTRACTORS, FIGURE_DISTRACTORS
    from copilot.visuals.sources import Candidate
    from copilot.visuals.webpages import figure_type

    c = Candidate(source="web", title="STM32F405 Block Diagram", image_url="https://x/a.png", mime="image/png",
                  width=800, height=600, licence="© stm32world.com", description="STM32F405 Block Diagram | Block diagram")
    assert reject_reason(c, "STM32 block diagram", "diagram") is None
    assert reject_reason(Candidate(source="commons", title="File:X.png", image_url="u", mime="image/png", width=800,
                                   height=600, licence="All rights reserved"), "x", "photo").startswith("licence")
    assert figure_type("STM32 block diagram") == "block diagram" and figure_type("human heart") == ""
    assert "a page of text" in DISTRACTORS and "a page of text" not in FIGURE_DISTRACTORS


# ---- robustness: a full disk (G1, test15) -------------------------------------------------------------------------
async def test_a_full_disk_keeps_the_events_and_never_raises(tmp_path, monkeypatch, caplog):
    from copilot.core.bus import EventBus
    from copilot.core.events import TranscriptFinal
    from copilot.persistence.event_log import EventLog, read_events

    bus = EventBus()
    log = EventLog(tmp_path / "s.sqlite", flush_interval_s=60)
    await log.open(bus)
    real = log._write
    monkeypatch.setattr(log, "_write", lambda batch: (_ for _ in ()).throw(sqlite3.OperationalError(
        "database or disk is full")))
    seg = {"id": "a", "text": "hello", "start": 0.0, "end": 1.0, "words": [], "avg_logprob": 0.0}
    await bus.publish(TranscriptFinal.model_validate({"segment": seg, "utterance": 1}))
    await bus.drain()
    with caplog.at_level(logging.WARNING):
        await log.flush(force=True)
        await log.flush(force=True)
    assert log.failing and log._buffer and "cannot be written" in caplog.text
    assert caplog.text.count("cannot be written") == 1  # once per failure streak
    monkeypatch.setattr(log, "_write", real)  # the disk has room again
    await log.flush(force=True)
    assert not log.failing and log.written >= 1
    await bus.close()
    await log.close()
    assert any(t == "TranscriptFinal" for _, t, _ in read_events(tmp_path / "s.sqlite"))


def test_usage_file_on_a_full_disk_is_one_line_without_a_traceback(tmp_path, monkeypatch, caplog):
    from copilot.llm.usage import UsageLedger

    ledger = UsageLedger(tmp_path / "llm_usage.json")
    monkeypatch.setattr(Path, "write_text", lambda *a, **k: (_ for _ in ()).throw(OSError(28, "No space left on device")))
    with caplog.at_level(logging.WARNING):
        ledger.save()
        ledger.save()
    assert caplog.text.count("could not save LLM usage") == 1 and "Traceback" not in caplog.text


def test_low_disk_is_said_at_the_start(tmp_path, monkeypatch):
    import shutil as sh

    from copilot.app.main import disk_warning

    monkeypatch.setattr(sh, "disk_usage", lambda p: type("U", (), {"free": 0.4e9})())
    assert "0.40 GB free" in disk_warning(tmp_path / "data", 1.0)
    monkeypatch.setattr(sh, "disk_usage", lambda p: type("U", (), {"free": 5.2e9})())
    assert disk_warning(tmp_path / "data", 1.0) == ""


# ---- /control: the study-material lines reach it ------------------------------------------------------------------
async def test_reading_progress_and_used_passage_reach_control():
    from copilot.core.bus import EventBus
    from copilot.core.events import NotesState
    from copilot.display.hub import DisplayHub

    bus = EventBus()
    hub = DisplayHub(bus)
    hub.attach()
    ctl = hub.connect("control")
    await ctl.next_batch()
    await bus.publish(NotesState(indexing={"d1": 0.4}, used="byjus.com p.3", notice="At most 10 files"))
    await bus.drain()
    msg = [m for m in await ctl.next_batch() if m["type"] == "notes"][-1]
    assert (msg["indexing"], msg["used"], msg["notice"]) == ({"d1": 0.4}, "byjus.com p.3", "At most 10 files")
    await bus.close()


@pytest.mark.parametrize("text, fine", [("Figure 2.12: Perspective switcher toolbar", True)])
def test_caption_gate_kept_simple(text, fine):
    from copilot.notes.reference import caption_text
    assert bool(caption_text(text)) is fine


def test_a_card_picture_is_named_with_its_set():
    from copilot.presentation.engine import item_query
    assert item_query("Mars", "Planets") == "Mars planet"          # test21
    assert item_query("Frontal lobe", "Cerebrum") == "Frontal lobe"  # test13: a two-word term says enough
    assert item_query("Neuron", "Types") == "Neuron"                # a generic set name adds nothing
    assert item_query("Femur", "Bones") == "Femur bone"


def test_card_terms_a_photo_can_show():
    from copilot.visuals.policy import names_an_object
    for t in ("Mars", "Router", "Network Switch", "Occipital lobe", "Corpus callosum", "Wireless Access Point"):
        assert names_an_object(t), t
    # test24 replay: these got a hash tree, a block chart and a network sketch
    for t in ("Encryption", "Authentication", "SSID", "Protocols", "Network Devices", "Kinetic energy", "Gray matter"):
        assert not names_an_object(t), t


async def test_a_card_that_joins_without_a_picture_takes_the_others_away():
    from tests.unit.test_presentation_engine import act as eact
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await _visual_topic(bus, reqs)
    await send(bus, ready("Solar System", "Planets", PLANETS[:2], relation="sibling_concept"))
    first = [r for r in reqs.items if r.reason.startswith("item:")]
    for k, r in enumerate(first):
        await answer(bus, r, [img(70 + k)])
    assert all(b.image is not None for b in deck.live.blocks if b.type == "definition")
    await send(bus, ready("Solar System", "Planets", [PLANETS[2]], relation="same_concept"))
    late = [r for r in reqs.items if r.reason.startswith("item:") and r not in first]
    assert [r.query for r in late] == ["Saturn planet"]
    await answer(bus, late[0], [], reason="no relevant image")
    defs = [b for s in deck.slides for b in s.blocks if b.type == "definition"]
    assert len(defs) == 3 and all(d.image is None for d in defs)
    await eng.stop()


async def test_a_card_picture_lost_to_the_network_is_searched_again():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await _visual_topic(bus, reqs)
    await send(bus, ready("Solar System", "Planets", PLANETS[:2], relation="sibling_concept"))
    first = [r for r in reqs.items if r.reason.startswith("item:")]
    await answer(bus, first[0], [img(80)])
    await answer(bus, first[1], [], reason="downloads failed")
    assert all(b.image is None for b in deck.live.blocks if b.type == "definition")
    await send(bus, ready("Solar System", "Planets", [act("explanation", points=["Both are visible at night"])],
                          relation="same_concept"))
    again = [r for r in reqs.items if r.reason.startswith("item:") and r not in first]
    assert [r.query for r in again] == ["Jupiter planet"]
    await answer(bus, again[0], [img(81)])
    assert [b.image.image_id for b in deck.live.blocks if b.type == "definition"] == [f"{80:016x}", f"{81:016x}"]
    await eng.stop()
