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


def process(
    engine,
    text,
    context,
    current_topic,
    current_embedding,
):
    return engine.process(
        latest_text=text,
        rolling_context=context,
        current_topic=current_topic,
        current_embedding=current_embedding,
    )


def get_node_by_name(engine, name):
    name = name.lower()

    for node in engine.get_topic_history():
        if node.name.lower() == name:
            return node

    return None


def test_microcontroller_lecture_hierarchy():
    engine = create_engine()

    current_topic = None
    current_embedding = None
    context = ""

    sequence = [
        "Today we are learning about microcontrollers.",
        "A microcontroller is a compact computer used in embedded systems.",
        "Now let's discuss the architecture of a microcontroller.",
        "The CPU executes instructions and controls the operation of the system.",
        "Memory stores the program and data used by the microcontroller.",
        "GPIO pins allow the microcontroller to communicate with external devices.",
        "Now let's discuss communication interfaces.",
        "UART is a serial communication interface used to transmit data.",
        "SPI provides high speed communication between the microcontroller and peripherals.",
        "I2C allows multiple devices to communicate using a shared bus.",
        "Now let's look at the ARM Cortex-M4.",
        "The NVIC manages interrupts inside the Cortex-M4 processor.",
        "CMSIS provides a standard software interface for ARM Cortex microcontrollers.",
        "SysTick provides a timer used for periodic system operations.",
    ]

    decisions = []

    for text in sequence:
        decision = process(
            engine,
            text,
            context,
            current_topic,
            current_embedding,
        )

        decisions.append(decision)

        if decision.is_relevant:
            current_topic = decision.topic
            current_embedding = decision.embedding
            context = f"{context} {text}".strip()

    # ---------------------------------------------------------
    # Basic processing validation
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

    assert "microcontrollers" in topic_names
    assert "architecture of a microcontroller" in topic_names
    assert "communication interfaces" in topic_names
    assert "arm cortex-m4" in topic_names

    # ---------------------------------------------------------
    # Root topic
    # ---------------------------------------------------------

    microcontrollers = topic_names["microcontrollers"]

    assert microcontrollers.parent_id is None
    assert microcontrollers.level == 0

    # ---------------------------------------------------------
    # Architecture hierarchy
    # ---------------------------------------------------------

    architecture = topic_names[
        "architecture of a microcontroller"
    ]

    assert architecture.parent_id == (
        microcontrollers.node_id
    )

    assert architecture.level == 1

    # ---------------------------------------------------------
    # Communication hierarchy
    # ---------------------------------------------------------

    communication = topic_names[
        "communication interfaces"
    ]

    assert communication.parent_id == (
        microcontrollers.node_id
    )

    assert communication.level == 1

    # ---------------------------------------------------------
    # ARM Cortex-M4
    # ---------------------------------------------------------

    arm = topic_names["arm cortex-m4"]

    assert arm.parent_id is None
    assert arm.level == 0

    # ---------------------------------------------------------
    # Children are registered correctly
    # ---------------------------------------------------------

    assert architecture.node_id in (
        microcontrollers.children_ids
    )

    assert communication.node_id in (
        microcontrollers.children_ids
    )

    # ---------------------------------------------------------
    # ARM child concepts should remain relevant
    # ---------------------------------------------------------

    assert decisions[11].is_relevant
    assert decisions[12].is_relevant
    assert decisions[13].is_relevant


def test_irrelevant_classroom_chatter():
    engine = create_engine()

    first = process(
        engine,
        "Today we are learning about microcontrollers.",
        "",
        None,
        None,
    )

    history_before = len(
        engine.get_topic_history()
    )

    decision = process(
        engine,
        "I forgot my notebook and my pen.",
        first.topic,
        first.topic,
        first.embedding,
    )

    history_after = len(
        engine.get_topic_history()
    )

    assert decision.is_relevant is False

    assert decision.structural_decision == (
        StructuralDecision.IRRELEVANT
    )

    assert history_after == history_before


def test_return_to_previous_topic():
    engine = create_engine()

    first = process(
        engine,
        "Today we are learning about microcontrollers.",
        "",
        None,
        None,
    )

    original_topic_id = (
        engine.get_active_node().node_id
    )

    second = process(
        engine,
        "Now let's discuss operating systems.",
        first.topic,
        first.topic,
        first.embedding,
    )

    assert second.is_relevant

    third = process(
        engine,
        "Going back to microcontrollers, they are widely used in embedded systems.",
        second.topic,
        second.topic,
        second.embedding,
    )

    assert third.is_relevant

    active_node = engine.get_active_node()

    assert active_node is not None

    assert active_node.node_id == original_topic_id


def test_topic_hierarchy_parent_relationships():
    engine = create_engine()

    current_topic = None
    current_embedding = None
    context = ""

    sequence = [
        "Today we are learning about microcontrollers.",
        "Now let's discuss the architecture of a microcontroller.",
        "Now let's discuss communication interfaces.",
        "Now let's look at the ARM Cortex-M4.",
    ]

    for text in sequence:
        decision = process(
            engine,
            text,
            context,
            current_topic,
            current_embedding,
        )

        if decision.is_relevant:
            current_topic = decision.topic
            current_embedding = decision.embedding
            context = f"{context} {text}".strip()

    history = engine.get_topic_history()

    node_ids = {
        node.node_id
        for node in history
    }

    for node in history:

        if node.parent_id is not None:
            assert node.parent_id in node_ids

        for child_id in node.children_ids:

            child = next(
                (
                    item
                    for item in history
                    if item.node_id == child_id
                ),
                None,
            )

            assert child is not None

            assert child.parent_id == node.node_id

            assert child.level == node.level + 1


def test_same_topic_does_not_create_duplicate_nodes():
    engine = create_engine()

    current_topic = None
    current_embedding = None
    context = ""

    chunks = [
        "Today we are learning about microcontrollers.",
        "A microcontroller contains a processor and memory.",
        "The processor executes instructions.",
        "The processor controls the embedded system.",
        "Memory stores instructions and data.",
        "Program memory stores firmware.",
        "Data memory stores temporary values.",
        "Microcontrollers are widely used in embedded systems.",
    ]

    for text in chunks:

        decision = process(
            engine,
            text,
            context,
            current_topic,
            current_embedding,
        )

        if decision.is_relevant:
            current_topic = decision.topic
            current_embedding = decision.embedding
            context = f"{context} {text}".strip()

    history = engine.get_topic_history()

    microcontroller_nodes = [
        node
        for node in history
        if "microcontroller" in node.name.lower()
    ]

    assert len(microcontroller_nodes) == 1