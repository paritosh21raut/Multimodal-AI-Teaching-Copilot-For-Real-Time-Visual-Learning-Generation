from __future__ import annotations

from typing import List

from app.ai.groq_semantic_reasoner import (
    GroqSemanticReasoner,
    _SYSTEM_PROMPT,
    _build_schema,
)
from app.semantic.semantic_types import (
    ConceptType,
    SemanticContextSnapshot,
    is_valid_concept_type,
)


# ---------------------------------------------------------- #
# ConceptType enum contract
# ---------------------------------------------------------- #

def test_property_not_in_concept_type():
    values = {t.value for t in ConceptType}
    assert "property" not in values
    assert "attribute" not in values
    assert "behavior" not in values


def test_is_valid_concept_type_rejects_property():
    assert is_valid_concept_type("property") is False
    assert is_valid_concept_type("attribute") is False
    assert is_valid_concept_type("behavior") is False


def test_is_valid_concept_type_accepts_unknown():
    assert is_valid_concept_type("unknown") is True


def test_is_valid_concept_type_accepts_all_approved_values():
    for value in ("entity", "class", "process", "quantity", "unknown"):
        assert is_valid_concept_type(value) is True


# ---------------------------------------------------------- #
# Schema contract
# ---------------------------------------------------------- #

def test_build_schema_enum_exact():
    schema = _build_schema([])
    enum = (
        schema["properties"]["concepts"]["items"]
        ["properties"]["concept_type"]["enum"]
    )
    assert enum == ["entity", "class", "process", "quantity", "unknown"]


# ---------------------------------------------------------- #
# System prompt contract
# ---------------------------------------------------------- #

def test_system_prompt_contains_vocabulary():
    assert "entity, class, process, quantity, unknown" in _SYSTEM_PROMPT
    assert "Do NOT use 'property'" in _SYSTEM_PROMPT


# ---------------------------------------------------------- #
# schema_strict threading
# ---------------------------------------------------------- #

class _CapturingClient:
    """Minimal stub that records kwargs and returns an empty proposal."""

    def __init__(self) -> None:
        self.last_kwargs: dict = {}

    def generate_structured(self, **kwargs):
        self.last_kwargs = dict(kwargs)
        return {"concepts": [], "relations": [], "notes": ""}


def _minimal_snapshot() -> SemanticContextSnapshot:
    return SemanticContextSnapshot(
        chunk_id="c1",
        chunk_text="A capacitor stores electrical energy.",
        sentences=(),
        lsi_relation="continuation",
        lsi_node_id=None,
        lsi_node_label=None,
        lsi_parent_node_id=None,
        lsi_parent_label=None,
        lsi_depth=None,
        recent_concept_labels=(),
        candidates=(),
        local_extraction=None,
        gate_decision="QUEUE_FOR_LLM",
        rolling_context="",
    )


def test_default_reasoner_is_strict():
    client = _CapturingClient()
    reasoner = GroqSemanticReasoner(client, model="openai/gpt-oss-120b")
    reasoner.reason(snapshot=_minimal_snapshot(), candidate_concepts=[])
    assert client.last_kwargs.get("schema_strict") is True


def test_fallback_reasoner_uses_non_strict():
    client = _CapturingClient()
    reasoner = GroqSemanticReasoner(
        client,
        model="openai/gpt-oss-20b",
        schema_strict=False,
    )
    reasoner.reason(snapshot=_minimal_snapshot(), candidate_concepts=[])
    assert client.last_kwargs.get("schema_strict") is False


# ---------------------------------------------------------- #
# Invalid concept_type is dropped, valid ones survive
# ---------------------------------------------------------- #

class _FakeClientReturningPayload:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def generate_structured(self, **kwargs):
        return self._payload


def test_invalid_property_concept_is_dropped_valid_survives():
    payload = {
        "concepts": [
            {
                "tmp_id": "tmp_1",
                "canonical_label": "low power",
                "aliases": [],
                "concept_type": "property",
                "existing_concept_id": None,
            },
            {
                "tmp_id": "tmp_2",
                "canonical_label": "microcontroller",
                "aliases": [],
                "concept_type": "entity",
                "existing_concept_id": None,
            },
        ],
        "relations": [],
        "notes": "",
    }
    reasoner = GroqSemanticReasoner(
        _FakeClientReturningPayload(payload),
        model="openai/gpt-oss-20b",
        schema_strict=False,
    )
    proposal = reasoner.reason(
        snapshot=_minimal_snapshot(), candidate_concepts=[]
    )
    labels = [c.canonical_label for c in proposal.concepts]
    assert "low power" not in labels
    assert "microcontroller" in labels