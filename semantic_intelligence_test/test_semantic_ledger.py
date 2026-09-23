from __future__ import annotations

import threading

from app.semantic.semantic_ledger import SemanticLedger
from app.semantic.semantic_types import (
    ConceptType,
    InformationType,
    Polarity,
    Certainty,
    RelationToPrior,
    SemanticRole,
    Source,
)


def _fresh_ledger() -> SemanticLedger:
    return SemanticLedger()


def test_add_and_retrieve_concept():

    ledger = _fresh_ledger()

    cid = ledger.add_concept(
        canonical_label="Mercury",
        aliases=["the closest planet"],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id="node_root",
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    assert cid
    assert ledger.get_concept(cid) is not None

    found = ledger.find_concept_by_label("Mercury")
    assert found is not None
    assert found.id == cid


def test_find_concept_by_label_is_case_insensitive():

    ledger = _fresh_ledger()

    ledger.add_concept(
        canonical_label="Mercury",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id=None,
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    assert ledger.find_concept_by_label("mercury") is not None
    assert ledger.find_concept_by_label("MERCURY") is not None
    assert ledger.find_concept_by_label("Mars") is None


def test_find_concepts_by_lsi_node():

    ledger = _fresh_ledger()

    ledger.add_concept(
        canonical_label="Mercury",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id="node_a",
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    ledger.add_concept(
        canonical_label="Venus",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id="node_a",
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    ledger.add_concept(
        canonical_label="Unrelated",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id="node_b",
        embedding=None,
        chunk_id="chunk_2",
        evidence_ids=[],
    )

    in_a = ledger.find_concepts_by_lsi_node("node_a")
    assert len(in_a) == 2
    assert {c.canonical_label for c in in_a} == {"Mercury", "Venus"}


def test_add_evidence_and_retrieve():

    ledger = _fresh_ledger()

    eid = ledger.add_evidence(
        chunk_id="chunk_1",
        sentence_index=0,
        span_start=0,
        span_end=17,
        text="Mercury is a planet",
        relation_to_prior=RelationToPrior.NEW.value,
    )

    ev = ledger.get_evidence(eid)
    assert ev is not None
    assert ev.text == "Mercury is a planet"
    assert ev.source == Source.TEACHER_TRANSCRIPT.value


def test_add_assertion_and_retrieve_by_concept():

    ledger = _fresh_ledger()

    cid = ledger.add_concept(
        canonical_label="Mercury",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id=None,
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    eid = ledger.add_evidence(
        chunk_id="chunk_1",
        sentence_index=0,
        span_start=0,
        span_end=17,
        text="Mercury is a planet",
    )

    aid = ledger.add_assertion(
        concept_id=cid,
        information_type=InformationType.DEFINITION.value,
        semantic_role=SemanticRole.CORE_CONCEPT.value,
        predicate="is_a",
        object_concept_id=None,
        object_literal="planet",
        polarity=Polarity.POSITIVE.value,
        certainty=Certainty.ASSERTED.value,
        relation_to_prior=RelationToPrior.NEW.value,
        evidence_ids=[eid],
        chunk_id="chunk_1",
        confidence_hint=0.9,
    )

    assert aid
    assertions = ledger.all_assertions_for_concept(cid)
    assert len(assertions) == 1
    assert assertions[0].predicate == "is_a"


def test_record_concept_mention_updates_count_and_evidence():

    ledger = _fresh_ledger()

    cid = ledger.add_concept(
        canonical_label="Mercury",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id=None,
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    eid = ledger.add_evidence(
        chunk_id="chunk_2",
        sentence_index=0,
        span_start=0,
        span_end=5,
        text="hello",
    )

    ledger.record_concept_mention(cid, "chunk_2", [eid])

    concept = ledger.get_concept(cid)
    assert concept is not None
    assert concept.mention_count == 2
    assert eid in concept.evidence_ids


def test_snapshot_and_reset():

    ledger = _fresh_ledger()

    ledger.add_concept(
        canonical_label="Mercury",
        aliases=[],
        concept_type=ConceptType.ENTITY.value,
        lsi_node_id=None,
        embedding=None,
        chunk_id="chunk_1",
        evidence_ids=[],
    )

    snap = ledger.snapshot()
    assert snap["counts"]["concepts"] == 1

    ledger.reset()

    snap2 = ledger.snapshot()
    assert snap2["counts"]["concepts"] == 0
    assert snap2["counts"]["assertions"] == 0
    assert snap2["counts"]["evidence"] == 0
    assert ledger.find_concept_by_label("Mercury") is None


def test_thread_safety_concurrent_writes():

    ledger = _fresh_ledger()

    def worker(worker_id: int, n: int):
        for i in range(n):
            ledger.add_concept(
                canonical_label=f"Concept_{worker_id}_{i}",
                aliases=[],
                concept_type=ConceptType.ENTITY.value,
                lsi_node_id=None,
                embedding=None,
                chunk_id=f"chunk_{worker_id}",
                evidence_ids=[],
            )

    threads = [
        threading.Thread(target=worker, args=(wid, 40))
        for wid in range(5)
    ]

    for t in threads:
        t.start()
    for t in threads:
        t.join()

    snap = ledger.snapshot()
    assert snap["counts"]["concepts"] == 200