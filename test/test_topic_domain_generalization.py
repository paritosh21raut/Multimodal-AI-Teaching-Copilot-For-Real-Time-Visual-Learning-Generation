from __future__ import annotations

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
        centroid_update_weight=0.15,
    )


def test_computer_networks_lecture_hierarchy():
    engine = create_engine()

    current_topic = None
    current_embedding = None
    context = ""

    sequence = [
        "Today we are learning about computer networks.",
        "A computer network connects devices so they can communicate.",
        "Now let's discuss network topologies.",
        "Star topology connects devices through a central switch.",
        "Bus topology uses a shared communication medium.",
        "Now let's discuss network protocols.",
        "TCP provides reliable data transmission.",
        "UDP provides faster communication with less overhead.",
        "Now let's look at the OSI model.",
        "The transport layer provides end-to-end communication.",
    ]

    decisions = []

    for text in sequence:
        decision = engine.process(
            latest_text=text,
            rolling_context=context,
            current_topic=current_topic,
            current_embedding=current_embedding,
        )

        decisions.append(decision)

        if decision.is_relevant:
            current_topic = decision.topic
            current_embedding = decision.embedding
            context = f"{context} {text}".strip()

    # ---------------------------------------------------------
    # Basic processing
    # ---------------------------------------------------------

    assert len(decisions) == len(sequence)

    assert decisions[0].structural_decision == (
        StructuralDecision.INITIAL_TOPIC
    )

    # ---------------------------------------------------------
    # Required topics
    # ---------------------------------------------------------

    history = engine.get_topic_history()

    topic_names = {
        node.name.lower(): node
        for node in history
    }

    assert "computer networks" in topic_names
    assert "network topologies" in topic_names
    assert "network protocols" in topic_names
    assert "osi model" in topic_names

    # ---------------------------------------------------------
    # Root topic
    # ---------------------------------------------------------

    computer_networks = topic_names[
        "computer networks"
    ]

    assert computer_networks.parent_id is None
    assert computer_networks.level == 0

    # ---------------------------------------------------------
    # Network Topologies
    # ---------------------------------------------------------

    topologies = topic_names[
        "network topologies"
    ]

    assert topologies.parent_id == (
        computer_networks.node_id
    )

    assert topologies.level == 1

    # ---------------------------------------------------------
    # Network Protocols
    # ---------------------------------------------------------

    protocols = topic_names[
        "network protocols"
    ]

    assert protocols.parent_id == (
        computer_networks.node_id
    )

    assert protocols.level == 1

    # ---------------------------------------------------------
    # OSI Model
    # ---------------------------------------------------------

    osi = topic_names[
        "osi model"
    ]

    assert osi.parent_id is None
    assert osi.level == 0

    # ---------------------------------------------------------
    # Parent → child consistency
    # ---------------------------------------------------------

    assert topologies.node_id in (
        computer_networks.children_ids
    )

    assert protocols.node_id in (
        computer_networks.children_ids
    )

    # ---------------------------------------------------------
    # Development under topics remains relevant
    # ---------------------------------------------------------

    assert decisions[3].is_relevant
    assert decisions[4].is_relevant
    assert decisions[6].is_relevant
    assert decisions[7].is_relevant
    assert decisions[9].is_relevant


def test_computer_networks_does_not_create_duplicate_topic():
    engine = create_engine()

    current_topic = None
    current_embedding = None
    context = ""

    chunks = [
        "Today we are learning about computer networks.",
        "A computer network connects devices together.",
        "Computer networks allow devices to communicate.",
        "Computer networks are used to share information.",
        "A computer network connects many devices.",
    ]

    for text in chunks:
        decision = engine.process(
            latest_text=text,
            rolling_context=context,
            current_topic=current_topic,
            current_embedding=current_embedding,
        )

        if decision.is_relevant:
            current_topic = decision.topic
            current_embedding = decision.embedding
            context = f"{context} {text}".strip()

    history = engine.get_topic_history()

    network_nodes = [
        node
        for node in history
        if "computer network" in node.name.lower()
    ]

    assert len(network_nodes) == 1


def test_computer_networks_irrelevant_sentence_is_ignored():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about computer networks."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    history_before = len(
        engine.get_topic_history()
    )

    second = engine.process(
        latest_text=(
            "The weather is pleasant today."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    history_after = len(
        engine.get_topic_history()
    )

    assert second.is_relevant is False

    assert second.structural_decision == (
        StructuralDecision.IRRELEVANT
    )

    assert history_after == history_before


def test_computer_networks_return_to_previous_topic():
    engine = create_engine()

    first = engine.process(
        latest_text=(
            "Today we are learning about computer networks."
        ),
        rolling_context="",
        current_topic=None,
        current_embedding=None,
    )

    original_topic_id = (
        engine.get_active_node().node_id
    )

    second = engine.process(
        latest_text=(
            "Now let's discuss network protocols."
        ),
        rolling_context=first.topic,
        current_topic=first.topic,
        current_embedding=first.embedding,
    )

    assert second.is_relevant

    third = engine.process(
        latest_text=(
            "Going back to computer networks, "
            "they connect devices for communication."
        ),
        rolling_context=second.topic,
        current_topic=second.topic,
        current_embedding=second.embedding,
    )

    assert third.is_relevant

    active_node = engine.get_active_node()

    assert active_node is not None

    assert active_node.node_id == original_topic_id