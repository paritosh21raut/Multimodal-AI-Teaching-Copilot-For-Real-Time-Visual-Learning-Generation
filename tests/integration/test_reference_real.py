"""F-012 calibration with the real models on tests/fixtures/notes/reference_biology.pdf: MiniLM for passages and figure
labels (SNIPPET_MIN, FIG_LABEL_MIN), CLIP for the figure gate (the web images' min_similarity). Marked slow."""
from pathlib import Path

import pytest
from PIL import Image

from copilot.core.config import PROJECT_ROOT
from copilot.notes.library import NotesLibrary
from copilot.notes.reference import FIG_LABEL_MIN, SNIPPET_MIN, ReferenceIndex, load_vocab
from copilot.understanding.embedder import MiniLmEmbedder

pytestmark = pytest.mark.slow
PDF = Path(__file__).resolve().parents[1] / "fixtures" / "notes" / "reference_biology.pdf"


@pytest.fixture(scope="module")
def ref(tmp_path_factory):
    e = MiniLmEmbedder(PROJECT_ROOT / "models" / "minilm")
    e.load()
    lib = NotesLibrary(tmp_path_factory.mktemp("notes"))
    doc = lib.add(PDF.read_bytes(), "Biology notes.pdf")
    r = ReferenceIndex(lib, e, load_vocab(PROJECT_ROOT / "models" / "minilm" / "tokenizer.json"))
    r.build(doc)
    return r


@pytest.mark.parametrize("said,page", [
    ("The heart has four chambers, two atria and two ventricles", 1),
    ("The pacemaker of the heart starts each beat", 1),
    ("Chlorophyll absorbs light in the thylakoids", 2),
    ("Our skeleton has 206 bones and protects organs", 3),
])
def test_what_the_teacher_says_finds_its_passage(ref, said, page):
    s = ref.snippet(said)
    assert s is not None and s.page == page and s.score >= SNIPPET_MIN + 0.1


@pytest.mark.parametrize("said", ["Today we talk about Newton's laws of motion",
                                  "Let us start the class, good morning everyone",
                                  "The French revolution began in 1789"])
def test_unrelated_lines_get_no_passage(ref, said):
    assert ref.snippet(said) is None
    assert not ref._best(said, True, 1) or ref._best(said, True, 1)[0].score < SNIPPET_MIN - 0.3


@pytest.mark.parametrize("query,page", [("human heart", 1), ("heart chambers diagram", 1),
                                        ("chloroplast structure", 2), ("skeleton", 3)])
def test_a_figure_label_matches_its_query(ref, query, page):
    m = ref.figures(query)
    assert m and m[0].figure.page == page


@pytest.mark.parametrize("query", ["Saturn rings", "STM32 microcontroller", "red blood cells", "plant cell"])
def test_no_figure_for_other_things(ref, query):
    assert ref.figures(query) == []
    assert FIG_LABEL_MIN >= 0.5


def test_terms_of_the_material(ref):
    terms = [t.lower() for t in ref.terms()]
    assert {"sinoatrial", "thylakoid", "chlorophyll"} <= set(terms) and "heart" not in terms


def test_clip_confirms_the_matching_figure_only(ref, tmp_path):
    from copilot.visuals.cache import ImageCache
    from copilot.visuals.clip import ClipScorer
    from copilot.visuals.finder import FinderSettings, ImageFinder

    clip = ClipScorer(PROJECT_ROOT / "models" / "clip")
    clip.load()
    f = ImageFinder(ImageCache(tmp_path), clip)
    s = FinderSettings()
    for query, kind in [("human heart", "diagram"), ("chloroplast structure", "diagram"), ("human skeleton", "photo")]:
        m = ref.figures(query)[0]
        (sim, margin), = f._score(query, kind, [(None, Image.open(m.path).convert("RGB"))])
        assert sim >= s.min_similarity and margin >= s.min_margin, (query, sim, margin)
