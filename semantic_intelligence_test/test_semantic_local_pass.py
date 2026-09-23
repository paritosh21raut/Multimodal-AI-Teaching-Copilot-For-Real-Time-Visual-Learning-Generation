from __future__ import annotations

from app.semantic.local_pass import (
    resolve_local,
    split_sentences,
)
from app.semantic.semantic_types import InformationType


def test_definition_defined_as():

    r = resolve_local(
        "Velocity is defined as the rate of change of position."
    )

    assert r.action == "RESOLVE"
    assert r.kind == "definition"
    assert r.subject == "Velocity"
    assert r.object_ == "the rate of change of position"
    assert r.information_type == InformationType.DEFINITION.value


def test_definition_is_called():

    r = resolve_local(
        "The process by which plants make food is called photosynthesis."
    )

    assert r.action == "RESOLVE"
    assert r.kind == "definition"
    assert r.predicate == "is_called"


def test_alias_also_called():

    r = resolve_local(
        "The inner planets, also called terrestrial planets, are rocky."
    )

    assert r.action == "RESOLVE"
    assert r.kind == "alias"
    assert r.subject == "The inner planets"
    assert r.object_ == "terrestrial planets"


def test_safe_formula():

    r = resolve_local("F = ma.")

    assert r.action == "RESOLVE"
    assert r.kind == "formula"
    assert r.information_type == InformationType.FORMULA.value
    assert r.subject == "F"


def test_unsafe_formula_abstains():

    r = resolve_local("The result is that latency = high.")

    assert r.action == "ABSTAIN"


def test_ambiguous_pronoun_abstains():

    r = resolve_local("It has four chambers.")
    assert r.action == "ABSTAIN"


def test_asr_fragment_abstains():

    r = resolve_local("which is why the and then it")
    assert r.action == "ABSTAIN"


def test_question_abstains():

    r = resolve_local("Does anyone know what causes this?")
    assert r.action == "ABSTAIN"


def test_empty_string_abstains():

    assert resolve_local("").action == "ABSTAIN"
    assert resolve_local("   ").action == "ABSTAIN"


def test_too_short_abstains():

    assert resolve_local("Okay.").action == "ABSTAIN"


def test_negation_phrase_abstains():

    r = resolve_local("Light does not require a medium to propagate.")
    assert r.action == "ABSTAIN"


def test_generic_is_a_abstains():

    r = resolve_local(
        "A microcontroller is a compact programmable embedded system."
    )
    assert r.action == "ABSTAIN"


def test_split_sentences_basic():

    spans = split_sentences("First sentence. Second sentence! Third?")

    assert len(spans) == 3
    assert [s.index for s in spans] == [0, 1, 2]
    assert spans[0].text == "First sentence."
    assert spans[1].text == "Second sentence!"
    assert spans[2].text == "Third?"


def test_split_sentences_empty():

    assert split_sentences("") == []
    assert split_sentences("   ") == []