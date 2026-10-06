"""Real MiniLM ONNX embedder (downloads ~90 MB on first run) → marked slow."""
from pathlib import Path

import numpy as np
import pytest

from copilot.core.config import PROJECT_ROOT
from copilot.understanding.embedder import MiniLmEmbedder
from copilot.understanding.tracker import ConceptTracker

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def embedder():
    e = MiniLmEmbedder(PROJECT_ROOT / "models" / "minilm")
    e.load()
    return e


def test_vectors_normalised_and_semantic(embedder):
    v = embedder.embed(["Plants make food using sunlight.", "Photosynthesis produces glucose in leaves.",
                        "The French revolution began in 1789."])
    assert v.shape == (3, 384)
    assert np.allclose(np.linalg.norm(v, axis=1), 1.0, atol=1e-4)
    assert float(v[0] @ v[1]) > float(v[0] @ v[2]) + 0.2


def test_off_topic_shift_exceeds_threshold(embedder):
    t = ConceptTracker(shift_threshold=0.75)
    for s in ["Photosynthesis is how green plants make food.", "Plants use sunlight, water and carbon dioxide.",
              "Chlorophyll in the leaves traps the sunlight."]:
        sig = t.update(s, embedder.embed([s])[0])
        assert not sig.boundary
    off = "The French revolution began in 1789 with the storming of the Bastille."
    assert t.update(off, embedder.embed([off])[0]).boundary


def test_image_relevance_real(embedder):
    """Calibration of IMAGE_MIN_RELEVANCE on the live test 2026-10-06 (session 20261006-112149-411e)."""
    from copilot.app.main import text_similarity
    from copilot.presentation.engine import IMAGE_MIN_RELEVANCE
    sim = text_similarity(embedder)
    assert sim("human digestive system diagram", "What is the quadratic equation?. The quadratic equation. the "
               "second degree of polynomial equation in a single variable") < IMAGE_MIN_RELEVANCE
    assert sim("plant stomata diagram", "How photosynthesis works. Glucose is used for energy and growth. Plants "
               "absorb water through roots from soil. Plants take in carbon dioxide through stomata") > IMAGE_MIN_RELEVANCE
    assert sim("female reproductive system", "What is human Reproductive System?. Ovaries. Fallopian tubes. Uterus. "
               "Cervix. Vagina. Vulva") > IMAGE_MIN_RELEVANCE
