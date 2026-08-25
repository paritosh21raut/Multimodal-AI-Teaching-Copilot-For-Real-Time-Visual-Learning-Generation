from app.lecture.slide_decision_engine import (
    SlideAction,
    SlideDecisionEngine,
)


def main():

    engine = SlideDecisionEngine(
        max_slide_source_words=40,
        max_updates_per_slide=2,
        min_meaningful_words=4,
    )

    # First meaningful content -> CREATE
    result = engine.decide(
        "A microcontroller is a small computer on a chip.",
        is_new_topic=True,
        current_slide_exists=False,
    )

    assert result.action == SlideAction.CREATE

    engine.record_success(
        "A microcontroller is a small computer on a chip.",
        SlideAction.CREATE,
    )

    # Same topic -> UPDATE
    result = engine.decide(
        "It contains a CPU, memory and input output peripherals.",
        is_new_topic=False,
        current_slide_exists=True,
    )

    assert result.action == SlideAction.UPDATE

    engine.record_success(
        "It contains a CPU, memory and input output peripherals.",
        SlideAction.UPDATE,
    )

    # Filler -> IGNORE
    result = engine.decide(
        "Okay.",
        is_new_topic=False,
        current_slide_exists=True,
    )

    assert result.action == SlideAction.IGNORE

    # Explicit transition -> CREATE
    result = engine.decide(
        "Now let's discuss the types of microcontrollers.",
        is_new_topic=True,
        current_slide_exists=True,
    )

    assert result.action == SlideAction.CREATE

    engine.record_success(
        "Now let's discuss the types of microcontrollers.",
        SlideAction.CREATE,
    )

    # Duplicate -> IGNORE
    result = engine.decide(
        "Now let's discuss the types of microcontrollers.",
        is_new_topic=False,
        current_slide_exists=True,
    )

    assert result.action == SlideAction.IGNORE

    print("=" * 70)
    print("SLIDE DECISION ENGINE TEST")
    print("=" * 70)
    print("[PASS] First content -> CREATE")
    print("[PASS] Same topic -> UPDATE")
    print("[PASS] Filler -> IGNORE")
    print("[PASS] Topic transition -> CREATE")
    print("[PASS] Duplicate -> IGNORE")
    print("=" * 70)
    print("TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()