from __future__ import annotations

import sys
from pathlib import Path

from app.ai.gemini_client import GeminiPermanentError
from app.knowledge.content_generator import ContentGenerator
from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_pipeline import LecturePipeline
from app.lecture.lecture_state import lecture_state
from app.llm.llm_orchestrator import LLMOrchestrator
from app.llm.ollama_client import OllamaClient


PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(
        0,
        str(PROJECT_ROOT),
    )


class GeminiDisabledClient:

    def generate_slide(
        self,
        topic,
        context,
    ):
        raise GeminiPermanentError(
            "Gemini intentionally disabled for this test."
        )

    def build_prompt(
        self,
        topic,
        context,
    ):
        return (
            f"TOPIC: {topic}\n"
            f"CONTEXT: {context}"
        )

    def status(self):
        return {
            "model": "disabled",
            "calls": 0,
            "successes": 0,
            "failures": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "status": "DISABLED_FOR_TEST",
            "last_error": "",
        }


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

        print(
            f"[MOCK PPT] Created slide "
            f"{slide.slide_number}"
        )

        return type(
            "Result",
            (),
            {
                "success": True,
                "presentation_path": "TEST_REAL_OLLAMA.pptx",
            },
        )()

    def update_slide(
        self,
        slide,
        content,
    ):

        self.update_calls += 1

        print(
            f"[MOCK PPT] Updated slide "
            f"{slide.slide_number}"
        )

        return type(
            "Result",
            (),
            {
                "success": True,
                "presentation_path": "TEST_REAL_OLLAMA.pptx",
            },
        )()


def main():

    print("=" * 70)
    print(
        "REAL OLLAMA GENERATION AGGREGATION TEST"
    )
    print("=" * 70)

    # ==========================================================
    # REAL OLLAMA
    # ==========================================================

    ollama = OllamaClient()

    print(
        "Ollama model :",
        ollama.model,
    )

    print(
        "Ollama URL   :",
        ollama.base_url,
    )

    if not ollama.is_available():

        raise RuntimeError(
            "Ollama is not available at "
            f"{ollama.base_url}"
        )

    # ==========================================================
    # REAL LLM ORCHESTRATOR
    # Gemini deliberately disabled.
    # ==========================================================

    orchestrator = LLMOrchestrator(
        gemini=GeminiDisabledClient(),
        ollama=ollama,
    )

    orchestrator.primary = "gemini"
    orchestrator.fallback_enabled = True
    orchestrator.ollama_enabled = True

    generator = ContentGenerator(
        llm=orchestrator
    )

    # ==========================================================
    # RESET SHARED STATE
    # ==========================================================

    context_buffer.clear()

    lecture_state.reset()

    pipeline = LecturePipeline()

    pipeline.register_topic_detector(
        MockTopicDetector()
    )

    pipeline.register_content_generator(
        generator
    )

    slide_manager = MockSlideManager()

    pipeline.register_slide_manager(
        slide_manager
    )

    # Make this test slightly easier to observe.
    pipeline.generation_min_words = 30
    pipeline.generation_min_sentences = 2

    # ==========================================================
    # CHUNK 1
    # FIRST TOPIC -> CREATE + REAL OLLAMA
    # ==========================================================

    first_text = (
        "Today we will learn about microcontrollers. "
        "A microcontroller is a small computer on a single chip. "
        "It contains a CPU, memory and input output peripherals."
    )

    print()
    print("=" * 70)
    print("CHUNK 1")
    print("=" * 70)

    result_1 = pipeline.process_transcript(
        first_text
    )

    assert result_1 is not None

    assert result_1.get(
        "content_generated"
    ) is True

    assert result_1.get(
        "slide_action"
    ) == "NEW SLIDE"

    assert orchestrator.last_provider == "OLLAMA"

    assert slide_manager.create_calls == 1

    first_llm_calls = (
        orchestrator.ollama_requests
    )

    print(
        "[PASS] First chunk created slide"
    )

    print(
        "[PASS] Real Ollama generated content"
    )

    # ==========================================================
    # CHUNK 2
    # SAME TOPIC -> ACCUMULATE
    # ==========================================================

    second_text = (
        "Microcontrollers are widely used "
        "in embedded systems and electronic devices."
    )

    print()
    print("=" * 70)
    print("CHUNK 2")
    print("=" * 70)

    result_2 = pipeline.process_transcript(
        second_text
    )

    assert result_2 is not None

    assert result_2.get(
        "slide_action"
    ) == "ACCUMULATE"

    assert result_2.get(
        "generation_pending"
    ) is True

    assert orchestrator.ollama_requests == (
        first_llm_calls
    )

    assert slide_manager.update_calls == 0

    print(
        "[PASS] Same-topic content accumulated"
    )

    print(
        "[PASS] No unnecessary Ollama call"
    )

    # ==========================================================
    # CHUNK 3
    # ENOUGH CONTENT -> REAL OLLAMA UPDATE
    # ==========================================================

    third_text = (
        "The processor executes instructions while memory "
        "stores program data and the input output peripherals "
        "communicate with external hardware."
    )

    print()
    print("=" * 70)
    print("CHUNK 3")
    print("=" * 70)

    result_3 = pipeline.process_transcript(
        third_text
    )

    assert result_3 is not None

    assert result_3.get(
        "content_generated"
    ) is True

    assert result_3.get(
        "slide_action"
    ) == "SAME SLIDE - UPDATE"

    assert orchestrator.last_provider == "OLLAMA"

    assert orchestrator.ollama_requests == (
        first_llm_calls + 1
    )

    assert slide_manager.update_calls == 1

    print(
        "[PASS] Aggregated content triggered "
        "one real Ollama UPDATE"
    )

    # ==========================================================
    # CHUNK 4
    # IRRELEVANT SPEECH
    # ==========================================================

    fourth_text = (
        "I forgot to bring my notebook today."
    )

    print()
    print("=" * 70)
    print("CHUNK 4")
    print("=" * 70)

    result_4 = pipeline.process_transcript(
        fourth_text
    )

    print(
        "Result:",
        result_4,
    )

    # Depending on the semantic model, this should normally
    # be classified as irrelevant. Do not spend an Ollama
    # request if it is ignored.
    if (
        result_4
        and not result_4.get(
            "is_relevant",
            True,
        )
    ):

        assert (
            orchestrator.ollama_requests
            == first_llm_calls + 1
        )

        print(
            "[PASS] Irrelevant speech did not "
            "call Ollama"
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    print()
    print("=" * 70)
    print("REAL OLLAMA AGGREGATION SUMMARY")
    print("=" * 70)

    print(
        "Ollama requests :",
        orchestrator.ollama_requests,
    )

    print(
        "Slides created  :",
        slide_manager.create_calls,
    )

    print(
        "Slides updated  :",
        slide_manager.update_calls,
    )

    print(
        "Last provider   :",
        orchestrator.last_provider,
    )

    print("=" * 70)
    print(
        "REAL OLLAMA GENERATION AGGREGATION TEST PASSED"
    )
    print("=" * 70)


class MockTopicDetector:

    def __init__(self):

        self.current_embedding = None

    def process(
        self,
        latest_text,
        rolling_context,
        current_topic,
        current_embedding,
    ):

        normalized = latest_text.lower()

        if current_embedding is None:

            self.current_embedding = (
                "microcontroller"
            )

            return type(
                "Decision",
                (),
                {
                    "topic": "Microcontrollers",
                    "embedding": (
                        self.current_embedding
                    ),
                    "is_relevant": True,
                    "is_new_topic": True,
                    "similarity": 1.0,
                    "confidence": 1.0,
                    "reason": "initial_topic",
                },
            )()

        if (
            "forgot"
            in normalized
            or "notebook"
            in normalized
        ):

            return type(
                "Decision",
                (),
                {
                    "topic": (
                        current_topic
                        or "Microcontrollers"
                    ),
                    "embedding": (
                        current_embedding
                    ),
                    "is_relevant": False,
                    "is_new_topic": False,
                    "similarity": 0.05,
                    "confidence": 0.0,
                    "reason": "irrelevant_speech",
                },
            )()

        return type(
            "Decision",
            (),
            {
                "topic": (
                    current_topic
                    or "Microcontrollers"
                ),
                "embedding": (
                    current_embedding
                ),
                "is_relevant": True,
                "is_new_topic": False,
                "similarity": 0.85,
                "confidence": 0.85,
                "reason": "relevant_continuation",
            },
        )()


if __name__ == "__main__":
    main()