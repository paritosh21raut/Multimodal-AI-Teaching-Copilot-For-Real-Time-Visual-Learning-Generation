"""Reference material (F-012): the My Notes files as a local index apart from the transcript — figures, passages,
terms; used for slides (one bounded passage), images (the teacher's figures first), speech (terms) and quiz facts
(never untaught questions). Real-model calibration: tests/integration/test_reference_real.py."""
import asyncio
import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from copilot.assess.generator import LectureQuestions, _MCQ, _MCQs, prompt as quiz_prompt, untaught, _stems
from copilot.assess.model import Question
from copilot.assess.service import Prepared, Spent
from copilot.core.bus import EventBus
from copilot.core.config import PROJECT_ROOT
from copilot.core.events import (Command, CommandReceived, ImageReady, ImageRequested, InterpretationReady,
                                 NotesState)
from copilot.core.interpretation import ConcernItem, Interpretation
from copilot.core.state import LectureSetup, LectureStateStore
from copilot.materials.content import Lecture, Subtopic, Topic
from copilot.notes.convert import image_pdf
from copilot.notes.library import MAX_ACTIVE, NotesLibrary
from copilot.notes.reference import ReferenceIndex, extract_figures, load_vocab, rare_terms
from copilot.notes.service import NotesService
from copilot.stt.factory import vocabulary_prompt
from copilot.understanding.gate import BufferedLine
from copilot.understanding.prompt import REFERENCE_KEEP, SYSTEM_PROMPT, build_prompt
from copilot.core.textutil import approx_tokens

FIX = Path(__file__).resolve().parents[1] / "fixtures"
REF_PDF = FIX / "notes" / "reference_biology.pdf"   # 3 pages, a real figure + caption on each (tools/make_reference_fixture.py)
NOTES_PDF = FIX / "notes" / "photosynthesis_notes.pdf"


class HashEmbedder:
    """Hashed bag of word stems: shared words → high cosine, none → ~0. Enough for the index's decisions."""
    DIM = 512

    def embed(self, texts):
        out = []
        for t in texts:
            v = np.zeros(self.DIM, dtype=np.float32)
            for w in re.findall(r"[a-z]{4,}", t.lower()):
                v[int(hashlib.md5(w[:6].encode()).hexdigest(), 16) % self.DIM] += 1.0
            v += 1e-4
            out.append(v / np.linalg.norm(v))
        return np.stack(out)


def ref_index(tmp_path, *files):
    lib = NotesLibrary(tmp_path / "notes")
    docs = [lib.add(p.read_bytes(), p.name) for p in files]
    ref = ReferenceIndex(lib, HashEmbedder())
    for d in docs:
        ref.build(d)
    return lib, ref, docs


# ---- figures ------------------------------------------------------------------------------------------------------
def test_figures_come_from_the_pdf_with_their_caption_and_labels_drawn_on_them(tmp_path):
    out = tmp_path / "figs"
    figs = extract_figures(REF_PDF, out, "pdf", "Biology notes.pdf")
    assert [f.page for f in figs] == [1, 2, 3]
    assert figs[0].label.startswith("Figure 1: Labelled diagram of the human heart")
    assert "chloroplast" in figs[1].label and "The human skeleton" in figs[2].label
    for f in figs:  # rendered from the page region at a useful size
        assert (out / f"f{f.n}.png").is_file() and f.width >= 900


def test_a_page_sized_picture_is_a_background_unless_the_teacher_added_the_image_itself(tmp_path):
    from PIL import Image
    import io

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), (200, 30, 30)).save(buf, "PNG")
    pdf = tmp_path / "x.pdf"
    pdf.write_bytes(image_pdf(buf.getvalue()))
    assert extract_figures(pdf, tmp_path / "a", "pdf", "scan.pdf") == []
    figs = extract_figures(pdf, tmp_path / "b", "image", "STM32_pinout-diagram.png")
    assert len(figs) == 1 and figs[0].label == "STM32 pinout diagram"


# ---- terms --------------------------------------------------------------------------------------------------------
def test_rare_terms_are_the_words_common_english_does_not_have():
    vocab = load_vocab(PROJECT_ROOT / "models" / "minilm" / "tokenizer.json")
    assert "heart" in vocab and "sinoatrial" not in vocab
    texts = ["The sinoatrial node starts the heart. The sinoatrial node is the pacemaker.",
             "Configure GPIO pins: GPIO mode, GPIO speed. The NVIC handles interrupts; enable the NVIC.",
             "Thylakoid once only."]
    terms = rare_terms(texts, vocab)
    assert terms[:1] == ["GPIO"] and "sinoatrial" in terms and "NVIC" in terms
    assert "Thylakoid" not in terms and "heart" not in [t.lower() for t in terms]  # seen once / common


def test_whisper_prompt_gets_the_terms_after_the_subject():
    setup = LectureSetup(subject="Embedded systems", expected_topic="STM32")
    assert vocabulary_prompt(setup) == "A classroom lecture on Embedded systems - STM32."
    assert vocabulary_prompt(setup, ["GPIO", "NVIC"]) == \
        "A classroom lecture on Embedded systems - STM32. Terms: GPIO, NVIC."
    assert vocabulary_prompt(LectureSetup(), ["GPIO"]) == "Terms: GPIO."
    assert vocabulary_prompt(LectureSetup()) is None


# ---- library flags + index ------------------------------------------------------------------------------------------
def test_files_are_study_material_by_default_at_most_ten_and_can_be_private(tmp_path):
    lib = NotesLibrary(tmp_path / "notes")
    base = NOTES_PDF.read_bytes()
    docs = [lib.add(base + f"\n%{i}".encode(), f"n{i}.pdf") for i in range(MAX_ACTIVE + 1)]
    assert [d.active for d in docs] == [True] * MAX_ACTIVE + [False]
    assert "at most" in lib.set_flags(docs[-1].id, active=True)
    assert lib.set_flags(docs[0].id, active=False) == "" and lib.set_flags(docs[-1].id, active=True) == ""
    assert lib.set_flags(docs[1].id, private=True) == "" and lib.get(docs[1].id).private
    assert lib.set_flags("0" * 16, active=True) == "unknown file"


def test_a_passage_is_found_only_when_it_clearly_matches_and_never_from_a_private_file(tmp_path):
    lib, ref, (doc,) = ref_index(tmp_path, REF_PDF)
    s = ref.snippet("the sinoatrial node starts each heartbeat, the natural pacemaker")
    assert s is not None and s.page == 1 and "sinoatrial" in s.text and s.cite == "reference_biology.pdf p.1"
    assert approx_tokens(s.text) <= 150
    assert ref.snippet("good morning everyone, let us begin today's class") is None
    lib.set_flags(doc.id, private=True)
    assert ref.snippet("the sinoatrial node starts each heartbeat") is None   # not to the LLM
    assert ref.figures("human heart chambers diagram")                        # images still use it
    lib.set_flags(doc.id, active=False)
    assert ref.figures("human heart chambers diagram") == []


def test_the_index_is_built_once_and_reloaded_from_disk_and_removed_with_the_file(tmp_path):
    lib, ref, (doc,) = ref_index(tmp_path, REF_PDF)
    again = ReferenceIndex(lib, HashEmbedder())
    assert again.pending() == [] and again.chunk_count(doc) == ref.chunk_count(doc) > 0
    assert again.figures("labelled diagram human heart")[0].figure.page == 1
    lib.remove(doc.id)
    assert not (lib.root / doc.id).exists()


def test_grounding_takes_passages_about_taught_text_within_its_budget(tmp_path):
    _, ref, _ = ref_index(tmp_path, REF_PDF)
    got = ref.grounding(["chlorophyll absorbs light in the thylakoid membranes", "the french revolution"],
                        max_tokens=200)
    assert got and all(p.page == 2 for p in got)
    assert sum(approx_tokens(p.text) + 6 for p in got) <= 200


# ---- the interpretation prompt ------------------------------------------------------------------------------------
def _lines(*texts):
    return [BufferedLine(segment_id=f"s{i}", text=t, start=float(i), end=float(i) + 1)
            for i, t in enumerate(texts)]


def test_the_prompt_holds_one_bounded_reference_block_only_when_given():
    store = LectureStateStore(EventBus(), "s", LectureSetup(subject="Biology"))
    state = store.snapshot()
    lines = _lines("The sinoatrial node starts each beat")
    plain = build_prompt(state, lines, dynamic_budget=1200, total_budget=3000)
    assert "REFERENCE" not in plain.messages[1]["content"] and plain.reference == ""
    with_ref = build_prompt(state, lines, dynamic_budget=1200, total_budget=3000,
                            reference=("Biology notes.pdf p.1", "The sinoatrial node is the natural pacemaker. " * 40))
    user = with_ref.messages[1]["content"]
    assert user.index("REFERENCE (teacher's material, Biology notes.pdf p.1)") < user.index("NEW LINES:")
    assert "never add content from it" in user and with_ref.reference == "Biology notes.pdf p.1"
    assert 0 < with_ref.tokens - plain.tokens <= 150 + 60
    # a prompt already near the budget gets no block (a repair still needs its room)
    tight = plain.tokens + REFERENCE_KEEP + 20
    t = build_prompt(state, lines, dynamic_budget=1200, total_budget=tight, reference=("x p.1", "passage " * 50))
    assert t.reference == "" and "REFERENCE" not in t.messages[1]["content"]
    assert approx_tokens(SYSTEM_PROMPT) + 1200 < 3000


async def test_a_factual_concern_raised_with_a_reference_cites_it():
    bus = EventBus()
    store = LectureStateStore(bus, "s", LectureSetup())
    store.attach()
    c = ConcernItem(claim="the heart has three chambers", issue="it has four", confidence=0.9, lines=[1],
                    suggested_correction="the heart has four chambers", wrong="three", right="four")
    t = ConcernItem(claim="sino atrial", issue="mis-heard", confidence=0.9, lines=[1], kind="transcription",
                    wrong="sino atrial", right="sinoatrial")
    await bus.publish(InterpretationReady(request_id="r1", segment_ids=["a"], provider="m",
                                          reference="Biology notes.pdf p.1",
                                          interpretation=Interpretation(topic="Heart", relation="new_topic", concerns=[c, t])))
    await bus.drain()
    got = {x.kind: x.ref for x in store.snapshot().concerns}
    assert got == {"factual": "Biology notes.pdf p.1", "transcription": ""}
    await bus.close()


# ---- quiz: facts checked, nothing untaught ------------------------------------------------------------------------
def _lecture(*said):
    sub = Subtopic(key="L1.T1.S1", topic="The heart", title="Chambers of the heart", said=list(said))
    return Lecture(id="l1", title="The heart", date="", topics=[Topic(name="The heart", subtopics=[sub])])


def _q(text, options, answer=0):
    return Question(id="q", text=text, options=options, answer=answer)


def test_an_answer_only_in_the_reference_is_untaught():
    taught = _stems("The heart has four chambers: two atria and two ventricles. Valves stop backflow.")
    ref = _stems("The sinoatrial node is the natural pacemaker. The septum separates the sides.")
    assert untaught(_q("What starts each heartbeat?", ["The sinoatrial node", "a", "b", "c"]), taught, ref)
    assert not untaught(_q("How many chambers?", ["Four chambers", "a", "b", "c"]), taught, ref)
    assert not untaught(_q("Which?", ["Ventricle", "a", "b", "c"]), taught, ref)   # "ventricles" was taught
    assert not untaught(_q("Which?", ["Aorta", "a", "b", "c"]), taught, ref)        # in neither: not this guard's call


def test_the_quiz_prompt_puts_reference_after_what_was_taught_and_inside_the_budget():
    lec = _lecture("The heart has four chambers.")
    text = quiz_prompt([lec], 5, [], ["The sinoatrial node is the natural pacemaker."])
    assert text.index("WHAT WAS TAUGHT") < text.index("REFERENCE (the teacher's own notes") < text.index("Write exactly")
    assert "never ask about anything that is not in WHAT WAS TAUGHT" in text
    # live 2026-10-12: a wrong taught fact ("three chambers") was keyed as correct although REFERENCE said four
    assert "contradicts REFERENCE, write no question on that point" in text
    assert "REFERENCE" not in quiz_prompt([lec], 5, [])


class TwoAnswerWriter:
    """The first answer, then (when `check` objects, as the real writer's one repair) the second."""
    available = True

    def __init__(self, first, second):
        self.answers, self.prompts, self.problems = [first, second], [], []

    async def ask(self, user, model, max_tokens, usage, check=None):
        self.prompts.append(user)
        out = self.answers[0]
        problem = check(out) if check else None
        if problem:
            self.problems.append(problem)
            out = self.answers[1]
        return out


async def test_quiz_questions_about_untaught_reference_content_are_dropped_and_asked_again():
    lec = _lecture("The heart has four chambers: two atria and two ventricles.")
    mcq = lambda q, a: _MCQ(q=q, options=[a, "Two rooms", "Six rooms", "One room"], answer=0)  # noqa: E731
    bad = _MCQs(questions=[mcq("What starts each heartbeat?", "The sinoatrial node"),
                           mcq("How many chambers does the heart have?", "Four chambers")])
    good = _MCQs(questions=[mcq("How many chambers does the heart have?", "Four chambers"),
                            mcq("Which chambers are at the bottom?", "The two ventricles")])
    writer = TwoAnswerWriter(bad, good)
    src = LectureQuestions(None, writer)
    prepared = Prepared(title="t", sources=["l1"], material=[lec],
                        reference=["The sinoatrial node starts each heartbeat; it is the natural pacemaker."])
    qs = await src.questions(prepared, 2, [], Spent())
    assert "REFERENCE (" in writer.prompts[0] and "answers only in REFERENCE" in writer.problems[0]
    assert sorted(q.text for q in qs) == ["How many chambers does the heart have?", "Which chambers are at the bottom?"]


async def test_without_a_reference_the_quiz_is_unchanged():
    lec = _lecture("The heart has four chambers.")
    bad = _MCQs(questions=[_MCQ(q="What starts each heartbeat?", options=["The sinoatrial node", "b", "c", "d"],
                                answer=0)])
    writer = TwoAnswerWriter(bad, bad)
    qs = await LectureQuestions(None, writer).questions(Prepared(title="t", sources=[], material=[lec]), 1, [],
                                                        Spent())
    assert len(qs) == 1 and "REFERENCE" not in writer.prompts[0] and writer.problems == []


# ---- images: the teacher's figures first --------------------------------------------------------------------------
class FakeClip:
    """CLIP stand-in: every image scores 0.3 for the query and 0 for the distractors (ok), or 0.1 / 0.3 (not ok)."""
    def __init__(self, ok):
        self.ok = ok

    def embed_texts(self, texts):
        return np.eye(len(texts), 4, dtype=np.float32)

    def embed_images(self, images):
        return np.array([[0.3, 0.0, 0.0, 0.0] if self.ok else [0.1, 0.3, 0.0, 0.0] for _ in images],
                        dtype=np.float32)


async def _image_service(tmp_path, ok=True):
    from copilot.visuals.cache import ImageCache
    from copilot.visuals.finder import ImageFinder
    from copilot.visuals.service import ImageService

    _, ref, (doc,) = ref_index(tmp_path, REF_PDF)
    bus = EventBus()
    finder = ImageFinder(ImageCache(tmp_path / "cache"), FakeClip(ok))
    web: list[str] = []

    async def no_web(query, kind="photo", **kw):
        from copilot.visuals.finder import FindResult
        web.append(query)
        return FindResult([], "no relevant image")
    finder.find = no_web
    svc = ImageService(bus, finder, reference=ref)
    got: list[ImageReady] = []

    async def grab(e):
        got.append(e)
    bus.subscribe("t", grab, [ImageReady])
    svc.attach()
    return bus, svc, doc, got, web


async def test_a_matching_figure_of_the_teacher_is_used_before_the_web(tmp_path, monkeypatch):
    import copilot.visuals.finder as finder_mod
    monkeypatch.setattr(finder_mod, "DISTRACTORS", ["a", "b", "c"])
    bus, svc, doc, got, web = await _image_service(tmp_path)
    await bus.publish(ImageRequested(request_id="r1", slide_id="s1", query="labelled diagram of the human heart",
                                     kind="diagram"))
    await bus.drain()
    assert await svc.idle(10)
    await bus.drain()
    img = got[-1].images[0]
    assert img["source"] == "reference" and img["title"] == "reference_biology.pdf p.1" and web == []
    from copilot.visuals.service import figure_image_id
    assert img["id"] == figure_image_id(doc.id, 1)
    # Change image: the figure is excluded → the web search
    await bus.publish(ImageRequested(request_id="r2", slide_id="s1", query="labelled diagram of the human heart",
                                     kind="diagram", exclude=[img["id"]], reason="change"))
    await bus.drain()
    assert await svc.idle(10)
    assert web == ["labelled diagram of the human heart"]
    await svc.stop()
    await bus.close()


async def test_a_figure_clip_does_not_confirm_is_not_used(tmp_path, monkeypatch):
    import copilot.visuals.finder as finder_mod
    monkeypatch.setattr(finder_mod, "DISTRACTORS", ["a", "b", "c"])
    bus, svc, doc, got, web = await _image_service(tmp_path, ok=False)
    await bus.publish(ImageRequested(request_id="r1", slide_id="s1", query="labelled diagram of the human heart",
                                     kind="diagram"))
    await bus.drain()
    assert await svc.idle(10)
    assert web == ["labelled diagram of the human heart"]
    await svc.stop()
    await bus.close()


# ---- the notes service: toggles, background indexing, what was used ------------------------------------------------
async def cmd(bus, kind, **args):
    await bus.publish(CommandReceived(command=Command(kind=kind, args=args, origin="control")))
    await bus.drain()


async def test_notes_index_in_the_background_toggle_and_show_the_passage_used(tmp_path):
    bus = EventBus()
    lib = NotesLibrary(tmp_path / "notes")
    doc = lib.add(REF_PDF.read_bytes(), "Biology notes.pdf")
    ref = ReferenceIndex(lib)
    svc = NotesService(bus, lib, reference=ref)
    svc.attach()
    states: list[NotesState] = []

    async def grab(e):
        states.append(e)
    bus.subscribe("t", grab, [NotesState])
    assert ref.pending() == [lib.get(doc.id)]
    svc.set_embedder(HashEmbedder())
    assert await svc.wait_indexed(30)
    await bus.drain()
    assert ref.pending() == [] and any(s.indexing for s in states) and not states[-1].indexing
    await cmd(bus, "notes_private", id=doc.id, on=True)
    assert states[-1].docs[0]["private"] is True
    await cmd(bus, "notes_use", id=doc.id, on=False)
    assert states[-1].docs[0]["active"] is False
    await bus.publish(InterpretationReady(request_id="r", segment_ids=[], interpretation=Interpretation(topic="x", relation="new_topic"),
                                          reference="Biology notes.pdf p.2"))
    await bus.drain()
    assert states[-1].used == "Biology notes.pdf p.2"
    await bus.close()
