from __future__ import annotations

from app.importance.importance_intelligence import (
    ImportanceIntelligence,
)
from app.importance.importance_types import (
    Centrality,
    DevelopmentalRole,
)


class _FakeDecision:
    def __init__(
        self,
        relation="continuation",
        node_id="n1",
        topic="Capacitors",
        parent_node_id=None,
        depth=0,
    ):
        self.relation = relation
        self.node_id = node_id
        self.topic = topic
        self.parent_node_id = parent_node_id
        self.depth = depth


class _FakeContextBuffer:
    def __init__(self):
        self._text = ""

    def rolling_context(self):
        return self._text

    def add(self, t):
        self._text = (self._text + " " + t).strip()


def test_pipeline_fail_open_on_bad_decision():
    sidecar = ImportanceIntelligence(
        context_buffer=_FakeContextBuffer(),
        semantic_ledger=None,
        enabled=True,
    )
    result = sidecar.evaluate(
        chunk_text="A capacitor stores electrical energy.",
        topic_decision=None,
    )
    assert result is not None
    assert result.structural_centrality in {
        Centrality.CORE.value,
        Centrality.SUPPORTING.value,
        Centrality.INCIDENTAL.value,
        Centrality.UNCERTAIN.value,
    }


def test_runtime_chunk1_new_topic_is_core_with_intro():
    """
    Chunk 1 from the runtime report:
    'We will learn about capacitors. compensator stores electrical energy
     An important property is that it opposes certain charges changes in voltage.'
    Expected: CORE, emphasis YES, roles include INTRODUCTION and PROPERTY.
    """
    buffer = _FakeContextBuffer()
    sidecar = ImportanceIntelligence(
        context_buffer=buffer,
        semantic_ledger=None,
        enabled=True,
    )

    text = (
        "We will learn about capacitors. "
        "capacitor stores electrical energy. "
        "An important property is that it opposes certain charges changes in voltage."
    )

    r = sidecar.evaluate(
        chunk_text=text,
        topic_decision=_FakeDecision(
            relation="new_topic", topic="Capacitors", node_id="n1"
        ),
    )
    assert r is not None
    assert r.structural_centrality == Centrality.CORE.value
    assert r.explicit_emphasis == "YES"
    assert DevelopmentalRole.INTRODUCTION.value in r.developmental_roles
    assert DevelopmentalRole.PROPERTY.value in r.developmental_roles


def test_runtime_chunk2_continuation_is_supporting():
    """
    Chunk 2 from the runtime report:
    'learn about capacitor charging. First, the capacitor is connected...
     then current flows... and the capacitor voltage rises.'
    Expected: SUPPORTING, emphasis NO, roles include PROCEDURE.
    """
    buffer = _FakeContextBuffer()
    buffer.add(
        "We will learn about capacitors. capacitor stores electrical energy."
    )
    sidecar = ImportanceIntelligence(
        context_buffer=buffer,
        semantic_ledger=None,
        enabled=True,
    )

    text = (
        "learn about capacitor charging. "
        "First, the capacitor is connected to the source. "
        "then current flows and the capacitor voltage rises."
    )

    r = sidecar.evaluate(
        chunk_text=text,
        topic_decision=_FakeDecision(
            relation="continuation",
            topic="Capacitors",
            node_id="n1",
        ),
    )
    assert r is not None
    assert r.structural_centrality == Centrality.SUPPORTING.value
    assert r.explicit_emphasis == "NO"
    assert DevelopmentalRole.PROCEDURE.value in r.developmental_roles


def test_pipeline_short_lecture_metadata():
    buffer = _FakeContextBuffer()
    sidecar = ImportanceIntelligence(
        context_buffer=buffer,
        semantic_ledger=None,
        enabled=True,
    )

    lecture = [
        (
            "Today we will learn about capacitors.",
            _FakeDecision(relation="new_topic", topic="Capacitors"),
        ),
        (
            "A capacitor stores electrical energy.",
            _FakeDecision(relation="continuation", topic="Capacitors"),
        ),
        (
            "An important property is that it opposes sudden changes in voltage.",
            _FakeDecision(relation="continuation", topic="Capacitors"),
        ),
        (
            "For example, capacitors are used in power supplies.",
            _FakeDecision(relation="continuation", topic="Capacitors"),
        ),
        (
            "By the way, the laboratory uses a 10 microfarad capacitor.",
            _FakeDecision(relation="continuation", topic="Capacitors"),
        ),
        (
            "Now let's learn about capacitor charging.",
            _FakeDecision(relation="new_topic", topic="Capacitor Charging"),
        ),
        (
            "First, the capacitor is connected to the source.",
            _FakeDecision(relation="continuation", topic="Capacitor Charging"),
        ),
        (
            "Then current flows and the capacitor voltage rises.",
            _FakeDecision(relation="continuation", topic="Capacitor Charging"),
        ),
    ]

    results = []
    for text, decision in lecture:
        r = sidecar.evaluate(chunk_text=text, topic_decision=decision)
        assert r is not None
        results.append(r)
        buffer.add(text)

    assert any(r.structural_centrality == Centrality.CORE.value for r in results)
    assert results[4].structural_centrality == Centrality.INCIDENTAL.value
    assert results[2].explicit_emphasis == "YES"
    assert any(
        DevelopmentalRole.PROCEDURE.value in r.developmental_roles
        for r in results
    )


def test_does_not_modify_transcript_or_phase4():
    buffer = _FakeContextBuffer()
    buffer.add("A capacitor stores electrical energy.")
    before = buffer.rolling_context()

    sidecar = ImportanceIntelligence(
        context_buffer=buffer,
        semantic_ledger=None,
        enabled=True,
    )

    sidecar.evaluate(
        chunk_text="Capacitors oppose sudden voltage changes.",
        topic_decision=_FakeDecision(),
    )

    assert buffer.rolling_context() == before