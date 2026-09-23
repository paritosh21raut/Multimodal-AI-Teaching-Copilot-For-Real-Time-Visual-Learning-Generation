from __future__ import annotations

from app.semantic.local_pass import resolve_local, split_sentences
from app.semantic.semantic_gate import SemanticGate
from app.semantic.semantic_types import (
    CandidateConcept,
    SentenceSpan,
)


def _spans(text: str):
    return tuple(split_sentences(text))


def _candidate(
    label: str,
    *,
    concept_id: str = "cid",
    lexical: float = 0.0,
    embedding: float = 0.0,
    proximity: int = 2,
) -> CandidateConcept:
    return CandidateConcept(
        concept_id=concept_id,
        label=label,
        embedding_score=embedding,
        lexical_score=lexical,
        lsi_proximity=proximity,
    )


def test_empty_chunk_is_skip():

    gate = SemanticGate()
    text = ""
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation=None,
        local_extraction=None,
        candidates=[],
    )
    assert decision == "SKIP"


def test_irrelevant_relation_is_skip():

    gate = SemanticGate()
    text = "Some random sentence."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="irrelevant",
        local_extraction=None,
        candidates=[],
    )
    assert decision == "SKIP"


def test_safe_local_definition():

    gate = SemanticGate()
    text = "Velocity is defined as the rate of change of position."
    extraction = resolve_local(text)
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="continuation",
        local_extraction=extraction,
        candidates=[],
    )
    assert decision == "SAFE_LOCAL"


def test_structural_transition_enqueues():

    gate = SemanticGate()
    text = "We now move on to a new topic."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="new_topic",
        local_extraction=None,
        candidates=[],
    )
    assert decision == "QUEUE_FOR_LLM"


def test_no_candidates_enqueues():

    gate = SemanticGate()
    text = "Mercury is the closest planet to the Sun."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="continuation",
        local_extraction=None,
        candidates=[],
    )
    assert decision == "QUEUE_FOR_LLM"


def test_repetition_is_skip():

    gate = SemanticGate()
    text = "Mercury is the closest planet to the Sun."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="continuation",
        local_extraction=None,
        candidates=[
            _candidate(
                "Mercury",
                lexical=1.0,
                embedding=0.95,
                proximity=0,
            )
        ],
    )
    assert decision == "SKIP"


def test_weak_candidate_enqueues():

    gate = SemanticGate()
    text = "Mercury is the closest planet to the Sun."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="continuation",
        local_extraction=None,
        candidates=[
            _candidate(
                "Mercury",
                lexical=0.0,
                embedding=0.4,
                proximity=2,
            )
        ],
    )
    assert decision == "QUEUE_FOR_LLM"


def test_short_chunk_is_skip():

    gate = SemanticGate()
    text = "Ok."
    decision = gate.decide(
        chunk_text=text,
        sentences=_spans(text),
        lsi_relation="continuation",
        local_extraction=None,
        candidates=[],
    )
    assert decision == "SKIP"