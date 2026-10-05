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
