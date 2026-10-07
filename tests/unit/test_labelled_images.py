"""Labelled diagrams first (F-009 §3, user 2026-10-07): for a structure / organ / system / cycle the finder also
searches for labelled diagrams, gives them the first preview slots and ranks an accepted labelled image above an
unlabelled one; without one it shows the best unlabelled image as before. Photos of planets / animals unchanged."""
import httpx
import pytest

pytest.importorskip("PIL")

from copilot.visuals.cache import ImageCache  # noqa: E402
from copilot.visuals.filters import is_labelled, language, reject_reason, wants_labels  # noqa: E402
from copilot.visuals.finder import FinderSettings, ImageFinder  # noqa: E402
from tests.unit.test_visuals_finder import cand  # noqa: E402


def test_labelled_means_labels_said_or_english_labels():
    assert is_labelled(cand("File:Heart labelled.svg"))
    assert is_labelled(cand("File:Plant cell structure-en.svg"))
    assert is_labelled(cand("File:Eye.svg", description="Annotated diagram of the human eye"))
    assert is_labelled(cand("File:Flower.svg", categories="Labeled diagrams|Flowers"))
    assert not is_labelled(cand("File:Saturn during Equinox.jpg"))
    assert not is_labelled(cand("File:Record labels of 1990.jpg"))  # "labels" alone is not a labelled diagram
    assert is_labelled(cand("File:Kidney.png", description="Kidney section with labels"))


def test_labels_wanted_only_where_they_teach():
    for q in ("human heart", "plant cell", "parts of a flower", "water cycle", "digestive system", "leaf stomata"):
        assert wants_labels(q, "photo"), q
    assert wants_labels("photosynthesis", "diagram")
    for q in ("Saturn", "tiger", "Mount Everest", "Taj Mahal"):
        assert not wants_labels(q, "photo"), q


def test_diagram_labelled_in_another_language_named_in_the_title_is_refused():
    c = cand("File:Parts of a flower in kashmiri language.jpg", mime="image/jpeg")
    assert language(c) == "kashmiri"
    assert reject_reason(c, "parts of a flower", "diagram") == "labels in kashmiri"
    assert language(cand("File:Parts of a flower in English language.png")) == "en" or \
        reject_reason(cand("File:Parts of a flower in English language.png"), "parts of a flower", "diagram") is None


def finder(**kw) -> ImageFinder:
    return ImageFinder(ImageCache(__import__("pathlib").Path(__import__("tempfile").mkdtemp())), None,
                       FinderSettings(**kw))


def test_labelled_candidates_get_the_first_preview_slots_but_not_all():
    f = finder(max_candidates=8, labelled_slots=5)
    plain = [cand(f"File:Heart photo {i}.jpg") for i in range(6)]
    lab = [cand(f"File:Heart diagram {i}-en.svg") for i in range(7)]
    kept = plain + lab
    chosen = f._previews(kept, labels=True)
    assert [c.title for c in chosen[:5]] == [c.title for c in lab[:5]]
    assert [c.title for c in chosen[5:]] == [c.title for c in plain[:3]]  # room left for plain pictures
    assert f._previews(kept, labels=False) == kept[:8]


def test_an_accepted_labelled_image_ranks_first_otherwise_the_best_plain_one():
    f = finder(alt_within=0.03)
    photo = (0.33, cand("File:Heart photo.jpg"), None)
    photo2 = (0.315, cand("File:Heart photo 2.jpg"), None)
    lab = (0.27, cand("File:Heart diagram-en.svg"), None)
    lab2 = (0.20, cand("File:Heart labelled old.svg"), None)
    ranked = f._rank([photo, lab, photo2, lab2], labels=True)
    assert [a[1].title for a in ranked] == ["File:Heart diagram-en.svg", "File:Heart photo.jpg", "File:Heart photo 2.jpg"]
    assert [a[1].title for a in f._rank([photo, photo2], labels=True)] == ["File:Heart photo.jpg", "File:Heart photo 2.jpg"]
    assert [a[1].title for a in f._rank([photo, lab], labels=False)] == ["File:Heart photo.jpg"]  # as before


class Record(httpx.AsyncBaseTransport):
    def __init__(self) -> None:
        self.searches: list[str] = []

    async def handle_async_request(self, request):
        q = request.url.params.get("gsrsearch")
        if q:
            self.searches.append(q)
        return httpx.Response(200, json={"query": {"pages": []}}, request=request)


async def test_a_labelled_diagram_search_runs_beside_the_others_for_structures_only():
    t = Record()
    f = ImageFinder(ImageCache(__import__("pathlib").Path(__import__("tempfile").mkdtemp())), None,
                    FinderSettings(), transport=t)
    await f.find("human heart chambers", "photo")
    assert any(s.startswith("human heart chambers labelled diagram") for s in t.searches), t.searches
    t.searches.clear()
    await f.find("Saturn", "photo")
    assert not any("labelled" in s for s in t.searches), t.searches
