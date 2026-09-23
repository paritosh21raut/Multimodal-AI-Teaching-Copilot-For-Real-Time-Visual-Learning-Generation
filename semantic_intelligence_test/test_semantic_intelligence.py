from __future__ import annotations

import time
from typing import List, Optional

from app.semantic.semantic_intelligence import SemanticIntelligence
from app.semantic.semantic_reasoner import (
    SemanticReasoner,
    SemanticReasonerError,
)
from app.semantic.semantic_types import (
    CandidateConcept,
    Certainty,
    ConceptProposal,
    ConceptType,
    InformationType,
    Polarity,
    RelationProposal,
    RelationToPrior,
    SemanticContextSnapshot,
    SemanticProposal,
    SemanticRole,
)


# ==========================================================
# MOCKS
# ==========================================================

class _NullEmbeddingModel:
    """
    Minimal embedder stub. Returns None-ish deterministic objects.
    Semantic tests do not exercise embedding similarity.
    """

    def encode(self, text: str, convert_to_tensor: bool = True):
        # Return a tiny deterministic object. Only used for storage.
        return _StubEmbedding(text)


class _StubEmbedding:
    def __init__(self, text: str) -> None:
        self.text = text


class _RecordingReasoner(SemanticReasoner):

    def __init__(self, proposal: Optional[SemanticProposal] = None):
        self._proposal = proposal or SemanticProposal()
        self.calls: List[SemanticContextSnapshot] = []

    def reason(self, *, snapshot, candidate_concepts):
        self.calls.append(snapshot)
        return self._proposal


class _RaisingReasoner(SemanticReasoner):

    def __init__(self, error_message: str = "boom"):
        self._error_message = error_message
        self.calls = 0

    def reason(self, *, snapshot, candidate_concepts):
        self.calls += 1
        raise SemanticReasonerError(self._error_message)


class _FirstRaisesThenSucceeds(SemanticReasoner):

    def __init__(self, proposal: SemanticProposal):
        self._proposal = proposal
        self.calls = 0

    def reason(self, *, snapshot, candidate_concepts):
        self.calls += 1
        if self.calls == 1:
            raise SemanticReasonerError("simulated 429 rate limit")
        return self._proposal


def _make_topic_decision(relation: str = "new_topic"):
    class _TD:
        def __init__(self):
            self.relation = relation
            self.node_id = "node_x"
            self.topic = "Test Node"
            self.parent_node_id = None
            self.depth = 0
    return _TD()


def _build_sidecar(reasoner, fallback=None, enabled=True):
    return SemanticIntelligence(
        embedding_model=_NullEmbeddingModel(),
        lsi_registry_getter=lambda _id: None,
        reasoner=reasoner,
        fallback_reasoner=fallback,
        max_queue_size=16,
        batch_size=1,
        batch_timeout=0.5,
        enabled=enabled,
    )


def _wait_for(predicate, timeout=4.0):
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        if predicate():
            return True
        time.sleep(0.05)
    return False


# ==========================================================
# TESTS
# ==========================================================

def test_enqueue_is_non_blocking_and_starts_worker():

    reasoner = _RecordingReasoner()
    sidecar = _build_sidecar(reasoner)
    sidecar.start()

    try:
        for i in range(5):
            sidecar.enqueue(
                f"Chunk number {i}.",
                _make_topic_decision(),
            )

        ok = _wait_for(
            lambda: len(reasoner.calls) >= 1,
            timeout=4.0,
        )
        assert ok, "reasoner was not called"
    finally:
        sidecar.stop()


def test_safe_local_commits_to_ledger():

    # Reasoner not called for SAFE_LOCAL chunks.
    reasoner = _RecordingReasoner()
    sidecar = _build_sidecar(reasoner)
    sidecar.start()

    try:
        sidecar.enqueue(
            "Velocity is defined as the rate of change of position.",
            _make_topic_decision("continuation"),
        )

        ok = _wait_for(
            lambda: sidecar.snapshot()["counts"]["concepts"] >= 1,
            timeout=4.0,
        )
        assert ok, "ledger did not receive local extraction"

        snap = sidecar.snapshot()
        assert snap["counts"]["concepts"] >= 1
        assert snap["counts"]["assertions"] >= 1
    finally:
        sidecar.stop()


def test_reasoner_exception_does_not_crash_worker():

    reasoner = _RaisingReasoner("simulated persistent failure")
    sidecar = _build_sidecar(reasoner)
    sidecar.start()

    try:
        sidecar.enqueue(
            "A sentence that will be processed but fails.",
            _make_topic_decision("new_topic"),
        )
        # Wait for at least one call attempt
        ok = _wait_for(lambda: reasoner.calls >= 1, timeout=3.0)
        assert ok

        # Worker should still be alive
        time.sleep(0.5)
        # Enqueue another
        sidecar.enqueue(
            "Another chunk.",
            _make_topic_decision("new_topic"),
        )
        ok = _wait_for(lambda: reasoner.calls >= 2, timeout=6.0)
        assert ok, "worker did not survive earlier failure"
    finally:
        sidecar.stop()


def test_malformed_proposal_does_not_commit():

    # Proposal contains a relation with an invalid evidence span.
    bad_proposal = SemanticProposal(
        concepts=[
            ConceptProposal(
                tmp_id="tmp_1",
                canonical_label="Mercury",
                aliases=[],
                concept_type=ConceptType.ENTITY.value,
            )
        ],
        relations=[
            RelationProposal(
                subject_tmp_id="tmp_1",
                predicate="is_close_to",
                object_tmp_id=None,
                object_literal="Sun",
                polarity=Polarity.POSITIVE.value,
                certainty=Certainty.ASSERTED.value,
                relation_to_prior=RelationToPrior.NEW.value,
                information_type=InformationType.FACT.value,
                semantic_role=SemanticRole.CORE_CONCEPT.value,
                sentence_index=0,
                span_start=9999,
                span_end=99999,
                confidence_hint=0.8,
            )
        ],
    )

    reasoner = _RecordingReasoner(bad_proposal)
    sidecar = _build_sidecar(reasoner)
    sidecar.start()

    try:
        sidecar.enqueue(
            "Mercury is close to the Sun.",
            _make_topic_decision("new_topic"),
        )

        ok = _wait_for(lambda: len(reasoner.calls) >= 1, timeout=4.0)
        assert ok

        time.sleep(0.6)
        snap = sidecar.snapshot()
        # Concept may exist (created before evidence check), but
        # the assertion must be rejected.
        assert snap["counts"]["assertions"] == 0
    finally:
        sidecar.stop()


def test_reset_clears_ledger():

    reasoner = _RecordingReasoner(
        SemanticProposal(
            concepts=[
                ConceptProposal(
                    tmp_id="tmp_1",
                    canonical_label="Something",
                    aliases=[],
                    concept_type=ConceptType.ENTITY.value,
                )
            ],
            relations=[],
        )
    )
    sidecar = _build_sidecar(reasoner)
    sidecar.start()

    try:
        sidecar.enqueue(
            "Anything that will produce a concept.",
            _make_topic_decision("new_topic"),
        )
        ok = _wait_for(
            lambda: sidecar.snapshot()["counts"]["concepts"] >= 1,
            timeout=4.0,
        )
        assert ok

        sidecar.reset()

        snap = sidecar.snapshot()
        assert snap["counts"]["concepts"] == 0
        assert snap["counts"]["assertions"] == 0
        assert snap["counts"]["evidence"] == 0
    finally:
        sidecar.stop()


def test_disabled_sidecar_does_nothing():

    reasoner = _RecordingReasoner()
    sidecar = _build_sidecar(reasoner, enabled=False)

    sidecar.enqueue(
        "Velocity is defined as the rate of change of position.",
        _make_topic_decision(),
    )
    time.sleep(0.5)

    assert len(reasoner.calls) == 0
    assert sidecar.snapshot()["counts"]["concepts"] == 0


def test_fallback_reasoner_used_on_429():

    class _FallbackOk(SemanticReasoner):
        def __init__(self):
            self.calls = 0
        def reason(self, *, snapshot, candidate_concepts):
            self.calls += 1
            return SemanticProposal()

    primary = _RaisingReasoner("429 rate limit")
    fallback = _FallbackOk()

    sidecar = _build_sidecar(primary, fallback=fallback)
    sidecar.start()

    try:
        sidecar.enqueue(
            "A chunk that triggers the primary to fail.",
            _make_topic_decision("new_topic"),
        )

        ok = _wait_for(lambda: fallback.calls >= 1, timeout=5.0)
        assert ok, "fallback was not invoked"
    finally:
        sidecar.stop()