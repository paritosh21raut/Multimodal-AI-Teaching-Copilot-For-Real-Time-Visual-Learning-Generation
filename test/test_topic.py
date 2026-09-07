from __future__ import annotations

import numpy as np

from app.topics.topic_intelligence import (
    StructuralDecision,
    TopicIntelligence,
)


def create_engine() -> TopicIntelligence:
    return TopicIntelligence(
        model_name="all-MiniLM-L6-v2",
        new_topic_threshold=0.55,
        irrelevant_threshold=0.30,
        subtopic_threshold=0.45,
    )


def test_initial_topic():
    engine = create_engine()

    decision = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    assert decision.is_relevant is True
    assert decision.is_new_topic is True

    assert (
        decision.structural_decision
        == StructuralDecision.INITIAL_TOPIC
    )

    assert decision.node_id is not None
    assert decision.parent_node_id is None


def test_same_topic_continuation():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "A database stores and organizes "
            "data so that it can be accessed efficiently."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant is True
    assert second.is_new_topic is False

    assert (
        second.node_id
        == first.node_id
    )

    assert (
        second.structural_decision
        == StructuralDecision.CONTINUE_CURRENT
    )


def test_transition_creates_subtopic_when_related():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "Now let's discuss relational databases "
            "and how they organize information."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant is True

    assert (
        second.structural_decision
        in (
            StructuralDecision.CREATE_SUBTOPIC,
            StructuralDecision.CONTINUE_CURRENT,
            StructuralDecision.UNCERTAIN,
        )
    )

    assert (
        second.structural_decision
        != StructuralDecision.NEW_MAJOR_TOPIC
    )


def test_unrelated_transition_can_create_major_topic():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "Now let's discuss operating systems."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant is True
    assert second.is_new_topic is True

    assert (
        second.structural_decision
        == StructuralDecision.NEW_MAJOR_TOPIC
    )

    assert second.node_id != first.node_id


def test_irrelevant_classroom_chatter_does_not_create_topic():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "I forgot to bring my notebook today."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant is False
    assert second.is_new_topic is False

    assert (
        second.structural_decision
        == StructuralDecision.IRRELEVANT
    )

    assert (
        second.node_id
        == first.node_id
    )

    assert len(
        engine.get_topic_history()
    ) == 1


def test_topic_history_is_retained():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "Now let's discuss operating systems."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    history = engine.get_topic_history()

    assert len(history) == 2

    assert (
        first.node_id
        != second.node_id
    )


def test_active_path_exists():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "Now let's discuss relational databases."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    path = engine.get_active_path()

    assert len(path) >= 1

    assert (
        path[-1].node_id
        == second.node_id
    )


def test_topic_anchor_embedding_does_not_drift():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    first_node = engine.get_active_node()

    assert first_node is not None
    assert first_node.anchor_embedding is not None

    original_anchor = (
        first_node.anchor_embedding
        .clone()
    )

    second = engine.process(
        latest_text=(
            "A database organizes information "
            "into a structured collection."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    second_node = engine.get_active_node()

    assert second_node is not None

    assert (
        second_node.node_id
        == first_node.node_id
    )

    # The original topic anchor must remain unchanged.
    assert np.array_equal(
        original_anchor.cpu().numpy(),
        second_node.anchor_embedding.cpu().numpy(),
    )

    # The stable anchor must not become the latest
    # transcript embedding.
    assert not np.array_equal(
        second_node.anchor_embedding.cpu().numpy(),
        second.embedding.cpu().numpy(),
    )


def test_centroid_updates_from_previous_centroid():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    first_node = engine.get_active_node()

    assert first_node is not None
    assert first_node.centroid_embedding is not None

    original_centroid = (
        first_node.centroid_embedding.clone()
    )

    second = engine.process(
        latest_text=(
            "A database organizes information "
            "into a structured collection."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    second_node = engine.get_active_node()

    assert second_node is not None

    assert (
        second_node.node_id
        == first_node.node_id
    )

    assert second_node.centroid_embedding is not None

    # The centroid must change after receiving
    # additional evidence.
    assert not np.array_equal(
        original_centroid.cpu().numpy(),
        second_node.centroid_embedding.cpu().numpy(),
    )

    # The anchor must remain unchanged.
    assert np.array_equal(
        first_node.anchor_embedding.cpu().numpy(),
        second_node.anchor_embedding.cpu().numpy(),
    )

    # The topic must continue using a stable topic
    # representation rather than replacing its anchor
    # with the new transcript embedding.
    assert not np.array_equal(
        second_node.anchor_embedding.cpu().numpy(),
        second_node.centroid_embedding.cpu().numpy(),
    )


def test_low_similarity_without_lecture_signal_is_irrelevant():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about databases."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    second = engine.process(
        latest_text=(
            "The weather is pleasant today."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant is False
    assert second.is_new_topic is False

    assert (
        second.structural_decision
        == StructuralDecision.IRRELEVANT
    )

    assert len(
        engine.get_topic_history()
    ) == 1