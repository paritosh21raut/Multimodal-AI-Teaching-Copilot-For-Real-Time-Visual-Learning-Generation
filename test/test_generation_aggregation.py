from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_state import lecture_state
from app.lecture.lecture_pipeline import LecturePipeline


class MockTopicDetector:

    def __init__(self):

        self.calls = 0

    def process(
        self,
        latest_text,
        rolling_context,
        current_topic,
        current_embedding,
    ):

        self.calls += 1

        if current_embedding is None:

            return SimpleNamespace(
                topic="Microcontrollers",
                embedding="embedding-1",
                is_relevant=True,
                is_new_topic=True,
                similarity=1.0,
                confidence=1.0,
                reason="initial_topic",
            )

        return SimpleNamespace(
            topic=current_topic or "Microcontrollers",
            embedding="embedding-2",
            is_relevant=True,
            is_new_topic=False,
            similarity=0.85,
            confidence=0.85,
            reason="relevant_continuation",
        )


class MockContentGenerator:

    def __init__(self):

        self.calls = 0
        self.contexts = []

    def generate(
        self,
        topic,
        context,
    ):

        self.calls += 1
        self.contexts.append(context)

        return SimpleNamespace(
            title="Microcontroller Basics",
            bullets=[
                SimpleNamespace(
                    text="Core microcontroller concept"
                ),
                SimpleNamespace(
                    text="CPU, memory and I/O"
                ),
            ],
            image_query=None,
            diagram=None,
            content_type="explanation",
            visual_type="none",
            visual_reason="Test",
            visual_spec={},
        )


class MockSlideManager:

    def __init__(self):

        self.create_calls = 0
        self.update_calls = 0

    def create_slide(
        self,
        slide,
        content,
    ):

        self.create_calls += 1

        return SimpleNamespace(
            success=True,
            presentation_path="TEST.pptx",
        )

    def update_slide(
        self,
        slide,
        content,
    ):

        self.update_calls += 1

        return SimpleNamespace(
            success=True,
            presentation_path="TEST.pptx",
        )


def main():

    print("=" * 70)
    print("GENERATION AGGREGATION TEST")
    print("=" * 70)

    context_buffer.clear()

    lecture_state.reset()

    pipeline = LecturePipeline()

    topic_detector = MockTopicDetector()
    content_generator = MockContentGenerator()
    slide_manager = MockSlideManager()

    pipeline.register_topic_detector(
        topic_detector
    )

    pipeline.register_content_generator(
        content_generator
    )

    pipeline.register_slide_manager(
        slide_manager
    )

    # ==========================================================
    # FIRST CHUNK
    # Must generate immediately.
    # ==========================================================

    result_1 = pipeline.process_transcript(
        "Today we will learn about microcontrollers. "
        "A microcontroller is a small computer on a single chip."
    )

    assert result_1["content_generated"] is True

    assert content_generator.calls == 1

    assert slide_manager.create_calls == 1

    print(
        "[PASS] First meaningful chunk generated immediately"
    )

    # ==========================================================
    # SMALL SAME-TOPIC CHUNK
    # Must NOT call LLM immediately.
    # ==========================================================

    result_2 = pipeline.process_transcript(
        "It contains CPU and memory."
    )

    assert result_2["generation_pending"] is True

    assert content_generator.calls == 1

    assert slide_manager.update_calls == 0

    print(
        "[PASS] Same-topic chunk accumulated"
    )

    # ==========================================================
    # SECOND SAME-TOPIC CHUNK
    # Now enough content should exist.
    # ==========================================================

    result_3 = pipeline.process_transcript(
        "It also contains input output peripherals "
        "and is widely used in embedded systems."
    )

    assert result_3["content_generated"] is True

    assert result_3["slide_action"] == (
        "SAME SLIDE - UPDATE"
    )

    assert content_generator.calls == 2

    assert slide_manager.update_calls == 1

    print(
        "[PASS] Aggregated content triggered one UPDATE"
    )

    # ==========================================================
    # FINAL
    # ==========================================================

    print()
    print("=" * 70)

    print(
        f"LLM calls     : "
        f"{content_generator.calls}"
    )

    print(
        f"Create calls  : "
        f"{slide_manager.create_calls}"
    )

    print(
        f"Update calls  : "
        f"{slide_manager.update_calls}"
    )

    print("=" * 70)
    print("TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()