from __future__ import annotations

import sys
from pathlib import Path

# Add project root to Python path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )

from types import SimpleNamespace

from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_state import lecture_state
from app.lecture.lecture_pipeline import LecturePipeline
from app.topics.topic_intelligence import TopicIntelligence


class MockContentGenerator:

    def generate(
        self,
        topic,
        context,
    ):

        return SimpleNamespace(
            title=f"Test Slide - {topic}",
            bullets=[
                SimpleNamespace(
                    text=f"Key point about {topic}"
                ),
                SimpleNamespace(
                    text=f"Important concept in {topic}"
                ),
            ],
            image_query=None,
            diagram=None,
            content_type="explanation",
            visual_type="none",
            visual_reason="Test mode",
            visual_spec={},
        )


class MockSlideManager:

    def create_slide(
        self,
        slide,
        content,
    ):

        print(
            f"[MOCK PPT] Created Slide "
            f"{slide.slide_number}"
        )

        return SimpleNamespace(
            success=True,
            presentation_path="MOCK_PRESENTATION.pptx",
        )

    def update_slide(
        self,
        slide,
        content,
    ):

        print(
            f"[MOCK PPT] Updated Slide "
            f"{slide.slide_number}"
        )

        return SimpleNamespace(
            success=True,
            presentation_path="MOCK_PRESENTATION.pptx",
        )


def create_pipeline():

    topic_detector = TopicIntelligence(
        model_name="all-MiniLM-L6-v2",
        new_topic_threshold=0.55,
        irrelevant_threshold=0.30,
    )

    pipeline = LecturePipeline()

    pipeline.register_topic_detector(
        topic_detector
    )

    pipeline.register_content_generator(
        MockContentGenerator()
    )

    pipeline.register_slide_manager(
        MockSlideManager()
    )

    return pipeline


def reset_state():

    context_buffer.clear()

    lecture_state.reset()

    lecture_state.start_new_lecture(
        "Test Lecture"
    )


def print_result(
    name,
    text,
    result,
):

    print()
    print("=" * 70)
    print(name)
    print("=" * 70)

    print(
        f"Input      : {text}"
    )

    print(
        f"Relevant   : "
        f"{result.get('is_relevant')}"
    )

    print(
        f"Topic      : "
        f"{result.get('topic')}"
    )

    print(
        f"Confidence : "
        f"{result.get('confidence')}"
    )

    print(
        f"Slide      : "
        f"{result.get('slide_action')}"
    )

    print(
        f"Slide No.  : "
        f"{result.get('slide_number')}"
    )

    print("=" * 70)


def main():

    print()
    print("=" * 70)
    print("REAL LECTURE PIPELINE LOGIC TEST")
    print("=" * 70)

    reset_state()

    pipeline = create_pipeline()

    # ========================================================
    # FIRST TOPIC
    # ========================================================

    first_text = (
        "Today we will learn about microcontrollers. "
        "A microcontroller is a small computer on a single chip. "
        "It contains CPU memory and input output peripherals."
    )

    result_1 = pipeline.process_transcript(
        first_text
    )

    print_result(
        "TEST 1 - FIRST TOPIC",
        first_text,
        result_1,
    )

    assert result_1 is not None
    assert result_1["is_relevant"] is True
    assert result_1["is_new_topic"] is True
    assert result_1["slide_number"] == 1

    # ========================================================
    # SAME TOPIC
    # ========================================================

    second_text = (
        "Microcontrollers are widely used "
        "in embedded systems and electronic devices."
    )

    result_2 = pipeline.process_transcript(
        second_text
    )

    print_result(
        "TEST 2 - SAME TOPIC",
        second_text,
        result_2,
    )

    assert result_2 is not None
    assert result_2["is_relevant"] is True
    assert result_2["is_new_topic"] is False
    assert result_2["slide_number"] == 1

    # ========================================================
    # NEW TOPIC
    # ========================================================

    third_text = (
        "Now let's discuss the types "
        "of microcontrollers. "
        "They include 8 bit, 16 bit and 32 bit controllers."
    )

    result_3 = pipeline.process_transcript(
        third_text
    )

    print_result(
        "TEST 3 - NEW TOPIC",
        third_text,
        result_3,
    )

    assert result_3 is not None
    assert result_3["is_relevant"] is True
    assert result_3["is_new_topic"] is True
    assert result_3["slide_number"] == 2

    # ========================================================
    # IRRELEVANT SPEECH
    # ========================================================

    fourth_text = (
        "I forgot to bring my notebook today."
    )

    result_4 = pipeline.process_transcript(
        fourth_text
    )

    print_result(
        "TEST 4 - IRRELEVANT SPEECH",
        fourth_text,
        result_4,
    )

    assert result_4 is not None
    assert result_4["is_relevant"] is False
    assert result_4["is_new_topic"] is False

    # ========================================================
    # FINAL STATE
    # ========================================================

    print()
    print("=" * 70)
    print("FINAL STATE")
    print("=" * 70)

    print(
        f"Slide Count : "
        f"{lecture_state.slide_count()}"
    )

    print(
        f"Current Topic : "
        f"{lecture_state.get_current_topic()}"
    )

    assert (
        lecture_state.slide_count()
        == 2
    )

    print("=" * 70)
    print("TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()