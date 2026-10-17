"""F-013 S5: the human body is drawn, never photographed (user 2026-10-17: a close-up photo of a mouth on the
digestive-system slide "looks gross; prefer pictorial images"), and a figure of the teacher's notes goes onto the
slide with a click (its place on the page is kept; any part of a page can be rendered). The /control layout fixes of
the same day are browser tests (test_control_layout_browser.py, test_notes_figures_browser.py)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from copilot.visuals.finder import (BODY_PHOTO, DISTRACTORS, STYLE_DRAWING, STYLE_PHOTO, ImageFinder, real_photo)
from copilot.visuals.policy import body_subject
from tests.unit.test_presentation_engine import make, ready, send
from tests.unit.test_presentation_images import Requests, act, image, with_visual

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "drawn_figures.pdf"


# ---- which pictures are of the body ------------------------------------------------------------------------------
def test_body_subjects_by_query_topic_or_subtopic():
    assert body_subject("Mouth", "Digestive system")            # the user's slide
    assert body_subject("teeth and tongue")
    assert body_subject("Saturn", "Organs of the body")          # the topic decides too
    assert body_subject("", "Circulatory system", "Heart")
    assert body_subject("stomach ulcers")
    for q in ("Saturn", "Motherboard", "Router", "Mouse", "Heartbeat sensor", "Analysis of algorithms", "Earth"):
        assert not body_subject(q, "Solar System"), q


def test_real_photo_rules_from_the_measured_scores():
    # (style, body) of cached images with the final prompts, CLIP ViT-B/32 int8, one image per batch (F-013 S5)
    assert real_photo(-0.013, 0.088, False) == "a photo of the body"     # inside of a mouth, on any slide
    assert real_photo(0.027, 0.076, False) == "a photo of the body"      # the same photo with labels drawn on it
    assert real_photo(-0.011, 0.043, False) == "a photo of the body"     # an ulcer
    assert real_photo(-0.014, -0.001, True) == "a photo (the body is drawn)"  # a real skeleton, body subject
    assert real_photo(-0.014, -0.001, False) == ""                       # ... is fine where the body is not the subject
    assert real_photo(-0.004, -0.060, False) == ""                       # Saturn: a photo stays a photo
    assert real_photo(0.004, 0.017, True) == ""                          # a 3D render of the stomach
    assert real_photo(0.023, 0.026, True) == ""                          # a drawing of the salivary glands
    assert real_photo(0.028, 0.060, True) == ""                          # skin layers, the highest-body drawing


# ---- the finder ----------------------------------------------------------------------------------------------------
class StyleScorer:
    """CLIP stand-in: texts are unit vectors; every image matches the query (0.3) and the style prompt it is given."""

    def __init__(self, style: str) -> None:
        self.style = style

    def embed_texts(self, texts):
        return np.eye(len(texts), 40, dtype=np.float32)

    def embed_images(self, images):
        d = 1 + len(DISTRACTORS)
        k = {"drawing": d, "photo": d + len(STYLE_DRAWING),
             "body": d + len(STYLE_DRAWING) + len(STYLE_PHOTO)}[self.style]
        v = np.zeros((len(images), 40), dtype=np.float32)
        v[:, 0] = 0.3
        v[:, k] = 0.2
        if self.style == "body":  # a photo of a body part: photo-like and close to the close-up prompt
            v[:, d + len(STYLE_DRAWING)] = 0.2
        return v


async def test_a_body_subject_takes_drawings_only_and_a_body_photo_is_refused_anywhere(tmp_path):
    from copilot.visuals.cache import ImageCache
    from tests.unit.test_visuals_finder import Replay

    assert len(BODY_PHOTO) == 1
    photo = await ImageFinder(ImageCache(tmp_path / "a"), StyleScorer("photo"), transport=Replay("heart_diagram")
                              ).find("human heart", "diagram", pictorial=True)
    assert photo.images == [] and any("the body is drawn" in why for _, why in photo.rejected)
    drawn = await ImageFinder(ImageCache(tmp_path / "b"), StyleScorer("drawing"), transport=Replay("heart_diagram")
                              ).find("human heart", "diagram", pictorial=True)
    assert drawn.images
    plain = await ImageFinder(ImageCache(tmp_path / "c"), StyleScorer("photo"), transport=Replay("heart_diagram")
                              ).find("human heart", "diagram")
    assert plain.images  # not a body subject (as the engine judges it): a photo is fine
    body = await ImageFinder(ImageCache(tmp_path / "d"), StyleScorer("body"), transport=Replay("heart_diagram")
                             ).find("human heart", "diagram")
    assert body.images == [] and any(why.startswith("a photo of the body") for _, why in body.rejected)
    # a pictorial answer is remembered apart from a plain one (the photo answer cached before S5 is not reused)
    cache = ImageCache(tmp_path / "b")
    assert cache.load_query("human heart", "diagram+labels+pic") or cache.load_query("human heart", "diagram+pic")


# ---- the engine asks for drawings where the body is the subject ----------------------------------------------------
async def test_the_engine_asks_for_drawings_on_a_body_topic_only():
    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    reqs = Requests(bus)
    await send(bus, with_visual(ready("Digestive System", "Mouth", [act("explanation", points=[
        "Teeth and tongue break food into small pieces"])], relation="new_topic"), "mouth teeth tongue"))
    assert [(r.query, r.pictorial) for r in reqs.items] == [("mouth teeth tongue", True)]
    for point in ("Saturn has beautiful rings", "Saturn is a gas giant"):  # a new topic needs 2 units
        await send(bus, with_visual(ready("Solar System", "Saturn", [act("explanation", points=[point])],
                                          relation="new_topic"), "Saturn"))
    assert [(r.query, r.pictorial) for r in reqs.items if r.query == "Saturn"][:1] == [("Saturn", False)]
    await eng.stop()


async def test_a_figure_from_my_notes_takes_the_wide_column():
    from copilot.core.events import Command, CommandReceived

    bus, store, deck, eng, clock = await make(min_dwell_s=0.0)
    await send(bus, ready("ESP32", "Architecture", [act("explanation", points=["The CPU talks to flash over SPI"])],
                          relation="new_topic"))
    live = deck.live
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": live.id, "image_id": "ab" * 8, "aspect": 1.6, "alt": "Block diagram of a microcontroller",
        "large": True})))
    img = image(deck.get(live.id))
    assert img is not None and img.large and img.origin == "teacher" and img.alt == "Block diagram of a microcontroller"
    await send(bus, CommandReceived(command=Command(kind="set_image", args={
        "slide_id": live.id, "image_id": "cd" * 8, "aspect": 1.6})))  # Add image: the normal column
    assert not image(deck.get(live.id)).large
    await eng.stop()


# ---- the place of each figure on its page, and any part of a page ----------------------------------------------------
@pytest.fixture
def indexed(tmp_path):
    from copilot.notes.library import NotesLibrary
    from copilot.notes.reference import ReferenceIndex
    from tests.unit.test_reference import HashEmbedder

    library = NotesLibrary(tmp_path / "notes")
    doc = library.add(FIXTURE.read_bytes(), "drawn_figures.pdf")
    ReferenceIndex(library, HashEmbedder()).build(doc)
    return library, doc


def test_each_figure_keeps_its_place_on_the_page(indexed):
    from copilot.notes.reference import page_figures

    library, doc = indexed
    (block,) = page_figures(library, doc.id, 1)   # the block diagram; not the framed note, not the table
    assert block.caption == "Block diagram of a microcontroller"
    # the chip outline: x 70..520, y 540..750 pt on a 595 x 842 page (top-left origin), give or take the wires
    assert block.box == pytest.approx([70 / 595, 1 - 750 / 842, 520 / 595, 1 - 540 / 842], abs=0.03)
    (circuit,) = page_figures(library, doc.id, 2)  # drawn inside a form XObject scaled 1.4 at (120, 500)
    assert circuit.caption == "Reset circuit"
    assert circuit.box == pytest.approx([134 / 595, 1 - 633 / 842, 498 / 595, 1 - 514 / 842], abs=0.03)
    assert page_figures(library, doc.id, 3) == [] and page_figures(library, "0" * 16, 1) == []


def test_a_part_of_a_page_is_rendered_sharp_even_on_a_turned_page(tmp_path, indexed):
    import pypdfium2 as pdfium

    library, doc = indexed
    part = library.render_region(doc.id, 1, [0.5, 0.5, 1.0, 1.0])
    assert part.size[0] >= 1100 and part.size[0] / part.size[1] == pytest.approx(595 / 842, abs=0.01)
    assert library.render_region(doc.id, 1, [0.2, 0.2, 0.205, 0.5]) is None  # too thin: a click, not a part
    assert library.render_region(doc.id, 9, [0, 0, 1, 1]) is None
    # a page turned by 90 degrees (the ESP32 datasheet's schematic page): the part of the page as the teacher sees it
    pdf = pdfium.PdfDocument(str(FIXTURE))
    pdf[0].set_rotation(90)
    turned = tmp_path / "turned.pdf"
    pdf.save(str(turned))
    pdf.close()
    tdoc = library.add(turned.read_bytes(), "turned.pdf")
    whole = library.render_region(tdoc.id, 1, [0.0, 0.0, 1.0, 1.0])
    assert whole.size[0] > whole.size[1]  # landscape, as shown
    left = library.render_region(tdoc.id, 1, [0.0, 0.0, 0.5, 1.0])
    assert left.size[0] / left.size[1] == pytest.approx(0.5 * 842 / 595, abs=0.02)
