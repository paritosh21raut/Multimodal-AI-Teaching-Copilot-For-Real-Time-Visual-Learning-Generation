from __future__ import annotations

from typing import List, Optional

from app.topics.lsi import (
    LectureStructureIntelligence,
    normalize_structure_label,
)
from app.topics.lecture_structure import StructureRelation
from app.topics.structural_reasoner import (
    NodeView,
    StructuralProposal,
    StructuralReasoner,
    StructuralReasonerError,
)


# ==========================================================
# MOCK REASONERS
# ==========================================================


class _ScriptedReasoner(StructuralReasoner):
    """
    Emits pre-scripted proposals in order. Records calls.
    Raises when the scripted entry is an exception instance.
    """

    def __init__(self, script: List[object]) -> None:
        self._script = list(script)
        self.calls: List[dict] = []

    def reason(
        self,
        *,
        chunk_text: str,
        context: str,
        current_node: Optional[NodeView],
        candidate_nodes: List[NodeView],
        allowed_relations: List[str],
        allow_return: bool,
        allow_new_root: bool,
    ) -> StructuralProposal:

        self.calls.append(
            {
                "chunk_text": chunk_text,
                "candidate_ids": [n.id for n in candidate_nodes],
                "allowed_relations": list(allowed_relations),
                "allow_return": allow_return,
                "allow_new_root": allow_new_root,
            }
        )

        if not self._script:
            raise StructuralReasonerError("script exhausted")

        item = self._script.pop(0)

        if isinstance(item, Exception):
            raise item

        return item  # type: ignore[return-value]


def _lsi(reasoner: Optional[StructuralReasoner] = None):

    return LectureStructureIntelligence(reasoner=reasoner)


# ==========================================================
# EXISTING TESTS (preserved)
# ==========================================================


def test_initial_topic_creates_root():

    lsi = _lsi()

    decision = lsi.process(
        "Today we are going to learn about the solar system."
    )

    assert decision.relation is StructureRelation.NEW_TOPIC
    assert decision.is_new_topic is True
    assert decision.parent_node_id is None
    assert decision.depth == 0
    assert decision.current_node_id is not None
    assert "solar" in decision.topic_label.lower()


def test_same_topic_continuation():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "The solar system contains the Sun and all the planets."
    )

    assert decision.relation is StructureRelation.CONTINUATION
    assert decision.is_new_topic is False


def test_new_subtopic_under_current():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    lsi.process(
        "The solar system contains the Sun and the planets."
    )

    decision = lsi.process(
        "The inner planets are Mercury Venus Earth and Mars."
    )

    assert decision.is_new_topic is False


def test_new_major_topic_creates_root_sibling():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "Now let's discuss black holes and their event horizons."
    )

    assert decision.relation is StructureRelation.NEW_TOPIC
    assert decision.is_new_topic is True
    assert decision.depth == 0


def test_explicit_transition_detected():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "Moving on to the topic of stellar evolution."
    )

    assert decision.relation is StructureRelation.NEW_TOPIC
    assert decision.is_new_topic is True


def test_related_concept_no_structural_change():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "The solar system is part of a larger structure."
    )

    assert decision.is_new_topic is False
    assert decision.relation in (
        StructureRelation.CONTINUATION,
        StructureRelation.RELATED,
        StructureRelation.SUBTOPIC,
        StructureRelation.DETAIL,
    )


def test_return_to_previous_topic():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    lsi.process(
        "Now let's discuss black holes and their event horizons."
    )

    decision = lsi.process(
        "Coming back to the solar system, the Sun is at its center."
    )

    assert decision.is_return is True
    assert decision.is_new_topic is False


def test_irrelevant_chunk():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "Could you please pass the salt at the dinner table."
    )

    assert decision.relation is StructureRelation.IRRELEVANT


def test_imperfect_whisper_transcript_still_structural():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "so so the system in this and the center of the solar system we have"
    )

    assert decision.is_new_topic is False


def test_domain_independent():

    lsi = _lsi()

    d1 = lsi.process(
        "Today we will study the French Revolution and its causes."
    )

    assert d1.relation is StructureRelation.NEW_TOPIC

    lsi2 = _lsi()

    d2 = lsi2.process(
        "Today we will study Newton's laws of motion."
    )

    assert d2.relation is StructureRelation.NEW_TOPIC


def test_fact_within_subtopic_not_promoted_to_subtopic():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    lsi.process(
        "The inner planets are Mercury Venus Earth and Mars."
    )

    decision = lsi.process(
        "Mercury is the closest planet to the Sun."
    )

    assert decision.is_new_topic is False
    assert decision.relation in (
        StructureRelation.CONTINUATION,
        StructureRelation.DETAIL,
        StructureRelation.RELATED,
    )


def test_asr_corrupted_opening_label_normalized():

    label = normalize_structure_label(
        "level even let's talk about solar system at this point.",
    )

    assert "solar" in label.lower()
    assert label.lower() != "level even let's talk about solar"


def test_compound_chunk_sentence_level_structure():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "so so the system in this. The solar system contains the "
        "Sun and all the planets. The center of the solar system "
        "we have this sun."
    )

    assert decision.relation is not StructureRelation.IRRELEVANT
    assert decision.is_new_topic is False


def test_multi_section_lecture_progression():

    lsi = _lsi()

    lsi.process(
        "Today we will study the laws of thermodynamics."
    )

    d1 = lsi.process(
        "Now let's discuss the first law of thermodynamics and "
        "energy conservation."
    )

    d2 = lsi.process(
        "Now let's discuss the second law of thermodynamics and "
        "entropy."
    )

    d3 = lsi.process(
        "Moving on to a different subject entirely, let's discuss "
        "quantum mechanics and wave-particle duality."
    )

    structural_events = sum(
        1
        for d in (d1, d2, d3)
        if d.is_new_topic or d.is_new_subtopic or d.is_return
    )

    assert structural_events >= 2


# ==========================================================
# NEW TESTS (Phase 3 corrective)
# ==========================================================


def test_confident_continuation_skips_reasoner():

    reasoner = _ScriptedReasoner([])

    lsi = _lsi(reasoner=reasoner)

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    lsi.process(
        "The solar system contains the Sun and all the planets."
    )

    assert reasoner.calls == []


def test_ambiguous_divergence_calls_reasoner_once():

    # Root node exists, chunk is genuinely divergent, no phrase.
    # The fast path does not decide; reasoner is expected to be
    # called exactly once.

    proposal = StructuralProposal(
        relation=StructureRelation.RELATED.value,
        target_node_id=None,     # will fail validation on purpose?
        concept_label=None,
        confidence=0.5,
        reason="test",
    )

    reasoner = _ScriptedReasoner([proposal])

    lsi = _lsi(reasoner=reasoner)

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    # Pre-grab the root id for a valid RELATED proposal.
    root_id = lsi._current_node_id

    # Rebuild the reasoner script with the valid target.
    reasoner._script = [
        StructuralProposal(
            relation=StructureRelation.RELATED.value,
            target_node_id=root_id,
            concept_label=None,
            confidence=0.55,
            reason="test",
        )
    ]
    reasoner.calls.clear()

    lsi.process(
        "Some genuinely divergent but not phrase-marked chunk about "
        "fisheries management in the North Atlantic."
    )

    assert len(reasoner.calls) == 1


def test_reasoner_exception_triggers_fallback():

    reasoner = _ScriptedReasoner(
        [StructuralReasonerError("boom")]
    )

    lsi = _lsi(reasoner=reasoner)

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "A genuinely divergent chunk with no discourse markers."
    )

    # Fallback must not crash; relation must be one of the safe set.
    assert decision.relation in (
        StructureRelation.RELATED,
        StructureRelation.IRRELEVANT,
        StructureRelation.NEW_TOPIC,
    )


def test_reasoner_invalid_proposal_rejected_and_fallback_fires():

    reasoner = _ScriptedReasoner(
        [
            StructuralProposal(
                relation="nonsense_relation",
                target_node_id=None,
                concept_label=None,
                confidence=0.9,
                reason="invalid",
            )
        ]
    )

    lsi = _lsi(reasoner=reasoner)

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    decision = lsi.process(
        "A genuinely divergent chunk with no discourse markers."
    )

    # Rejected proposal must not create a node.
    assert lsi._registry.size() == 1

    # Fallback fired.
    assert decision.reason.startswith("fallback:")


def test_valid_subtopic_proposal_commits():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    root_id = lsi._current_node_id

    reasoner = _ScriptedReasoner(
        [
            StructuralProposal(
                relation=StructureRelation.SUBTOPIC.value,
                target_node_id=root_id,
                concept_label="Asteroid belt",
                confidence=0.9,
                reason="new section",
            )
        ]
    )

    lsi._reasoner = reasoner

    decision = lsi.process(
        "A genuinely divergent chunk with no discourse markers."
    )

    assert decision.relation is StructureRelation.SUBTOPIC
    assert decision.is_new_subtopic is True
    assert lsi._registry.size() == 2


def test_sibling_at_root_collapses_to_new_topic():

    lsi = _lsi()

    lsi.process(
        "Today we are going to learn about the solar system."
    )

    root_id = lsi._current_node_id

    reasoner = _ScriptedReasoner(
        [
            StructuralProposal(
                relation=StructureRelation.SIBLING.value,
                target_node_id=root_id,
                concept_label="Black holes",
                confidence=0.9,
                reason="peer root",
            )
        ]
    )

    lsi._reasoner = reasoner

    decision = lsi.process(
        "A genuinely divergent chunk with no discourse markers."
    )

    # E9: at root level SIBLING collapses to NEW_TOPIC.
    assert decision.relation is StructureRelation.NEW_TOPIC
    assert decision.is_new_topic is True
    assert lsi._registry.size() == 2


def test_lsi_is_domain_independent():

    # Physics
    lsi_a = _lsi()
    a = lsi_a.process(
        "Today we will study transistor biasing."
    )
    assert a.relation is StructureRelation.NEW_TOPIC

    # History
    lsi_b = _lsi()
    b = lsi_b.process(
        "Today we will study the causes of the First World War."
    )
    assert b.relation is StructureRelation.NEW_TOPIC

    # Biology
    lsi_c = _lsi()
    c = lsi_c.process(
        "Today we will study the structure of the cell membrane."
    )
    assert c.relation is StructureRelation.NEW_TOPIC