from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.knowledge.content_generator import ContentGenerator
from app.lecture.context_buffer import context_buffer
from app.lecture.lecture_pipeline import LecturePipeline
from app.lecture.lecture_state import lecture_state
from app.llm.llm_orchestrator import LLMOrchestrator
from app.llm.ollama_client import OllamaClient
from app.ppt.ppt_manager import ppt_manager
from app.slides.slide_manager import SlideManager
from app.topics.topic_intelligence import TopicIntelligence
from app.ai.gemini_client import GeminiPermanentError


# ==============================================================
# FAKE GEMINI
# ==============================================================


class FakeGemini:

    def __init__(self, should_fail: bool = False):
        self.should_fail = should_fail
        self.calls = 0

    def generate_slide(
        self,
        topic,
        context,
    ):

        self.calls += 1

        if self.should_fail:

            raise GeminiPermanentError(
                "Gemini intentionally failed in integration test."
            )

        return {
            "title": f"{topic} - Gemini Slide",

            "bullets": [
                f"Main idea about {topic}",
                f"Important concept in {topic}",
                f"Application of {topic}",
            ],

            "summary": (
                f"Educational explanation of {topic}."
            ),

            "keywords": [
                topic,
                "education",
            ],

            "content_type": "explanation",

            "visual_type": "none",

            "visual_reason": (
                "Fake Gemini response for integration testing."
            ),

            "image_query": "",

            "visual_spec": {},

            "diagram": "",
        }

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
            "model": "fake-gemini",
            "calls": self.calls,
            "successes": (
                0
                if self.should_fail
                else self.calls
            ),
            "failures": (
                self.calls
                if self.should_fail
                else 0
            ),
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "status": (
                "TEST_FAILURE_MODE"
                if self.should_fail
                else "TEST_SUCCESS_MODE"
            ),
            "last_error": "",
        }


# ==============================================================
# PPT RESET
# ==============================================================


def reset_ppt():

    ppt_manager.presentation = None

    ppt_manager.presentation_path = None

    ppt_manager.slide_map.clear()


# ==============================================================
# PIPELINE FACTORY
# ==============================================================


def create_pipeline(
    gemini,
    ollama,
):

    topic_detector = TopicIntelligence(
        model_name="all-MiniLM-L6-v2",
        new_topic_threshold=0.55,
        irrelevant_threshold=0.30,
    )

    orchestrator = LLMOrchestrator(
        gemini=gemini,
        ollama=ollama,
    )

    orchestrator.primary = "gemini"

    orchestrator.fallback_enabled = True

    orchestrator.ollama_enabled = True

    content_generator = ContentGenerator(
        llm=orchestrator
    )

    pipeline = LecturePipeline()

    pipeline.register_topic_detector(
        topic_detector
    )

    pipeline.register_content_generator(
        content_generator
    )

    pipeline.register_slide_manager(
        SlideManager()
    )

    return pipeline, orchestrator


# ==============================================================
# STATE RESET
# ==============================================================


def reset_lecture_state():

    context_buffer.clear()

    lecture_state.reset()

    reset_ppt()


# ==============================================================
# TEST 1
# GEMINI PRIMARY
# ==============================================================


def test_gemini_primary():

    print()
    print("=" * 80)
    print("TEST 1 - GEMINI PRIMARY PATH")
    print("=" * 80)

    reset_lecture_state()

    fake_gemini = FakeGemini(
        should_fail=False
    )

    ollama = OllamaClient()

    pipeline, orchestrator = create_pipeline(
        fake_gemini,
        ollama,
    )

    text_1 = (
        "Today we will learn about microcontrollers. "
        "A microcontroller is a small computer on a single chip."
    )

    result_1 = pipeline.process_transcript(
        text_1
    )

    print()
    print("[CHECK] First generation")
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Gemini calls:",
        fake_gemini.calls
    )
    print(
        "Ollama calls:",
        orchestrator.ollama_requests
    )

    assert result_1 is not None

    assert result_1["is_relevant"] is True

    assert result_1["is_new_topic"] is True

    assert result_1["slide_number"] == 1

    assert orchestrator.last_provider == "GEMINI"

    assert fake_gemini.calls == 1

    assert orchestrator.ollama_requests == 0

    # ----------------------------------------------------------
    # Same-topic accumulation
    # ----------------------------------------------------------

    text_2 = (
        "It contains CPU memory and input output peripherals."
    )

    result_2 = pipeline.process_transcript(
        text_2
    )

    print()
    print("[CHECK] Same-topic accumulation")
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Gemini calls:",
        fake_gemini.calls
    )

    assert result_2 is not None

    assert result_2["is_relevant"] is True

    # No second LLM call yet.
    assert fake_gemini.calls == 1

    # ----------------------------------------------------------
    # More same-topic content
    # ----------------------------------------------------------

    text_3 = (
        "Microcontrollers are widely used in embedded systems "
        "and electronic devices. "
        "They control sensors and external hardware."
    )

    result_3 = pipeline.process_transcript(
        text_3
    )

    print()
    print("[CHECK] Aggregated same-topic update")
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Gemini calls:",
        fake_gemini.calls
    )
    print(
        "Ollama calls:",
        orchestrator.ollama_requests
    )

    assert result_3 is not None

    assert fake_gemini.calls == 2

    assert orchestrator.ollama_requests == 0

    # ----------------------------------------------------------
    # New topic
    # ----------------------------------------------------------

    text_4 = (
        "Now let's discuss the types of microcontrollers. "
        "They include 8 bit, 16 bit and 32 bit controllers."
    )

    result_4 = pipeline.process_transcript(
        text_4
    )

    print()
    print("[CHECK] New topic")
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Gemini calls:",
        fake_gemini.calls
    )

    assert result_4 is not None

    assert result_4["is_relevant"] is True

    assert result_4["is_new_topic"] is True

    assert result_4["slide_number"] == 2

    assert fake_gemini.calls == 3

    assert orchestrator.ollama_requests == 0

    # ----------------------------------------------------------
    # Irrelevant speech
    # ----------------------------------------------------------

    text_5 = (
        "I forgot to bring my notebook today."
    )

    result_5 = pipeline.process_transcript(
        text_5
    )

    print()
    print("[CHECK] Irrelevant speech")
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Gemini calls:",
        fake_gemini.calls
    )

    assert result_5 is not None

    assert result_5["is_relevant"] is False

    assert fake_gemini.calls == 3

    assert orchestrator.ollama_requests == 0

    print()
    print(
        "[PASS] Gemini primary path works."
    )

    print(
        "[PASS] Same-topic aggregation works."
    )

    print(
        "[PASS] New-topic slide creation works."
    )

    print(
        "[PASS] Irrelevant speech is ignored."
    )

    print(
        "[PASS] Ollama was never called."
    )

    print(
        "PPT:",
        ppt_manager.get_path()
    )


# ==============================================================
# TEST 2
# GEMINI FAILURE -> REAL OLLAMA
# ==============================================================


def test_ollama_fallback():

    print()
    print("=" * 80)
    print("TEST 2 - GEMINI FAILURE -> REAL OLLAMA")
    print("=" * 80)

    reset_lecture_state()

    fake_gemini = FakeGemini(
        should_fail=True
    )

    ollama = OllamaClient()

    if not ollama.is_available():

        raise RuntimeError(
            "Ollama is not available."
        )

    pipeline, orchestrator = create_pipeline(
        fake_gemini,
        ollama,
    )

    text = (
        "Today we will learn about sensor data processing. "
        "First the sensor captures the physical signal. "
        "The ADC converts the analog signal into digital data. "
        "The CPU processes the digital data. "
        "Finally the system sends the result to the actuator."
    )

    result = pipeline.process_transcript(
        text
    )

    print()
    print("[CHECK] Fallback")
    print(
        "Gemini calls:",
        fake_gemini.calls
    )
    print(
        "Ollama calls:",
        orchestrator.ollama_requests
    )
    print(
        "Provider:",
        orchestrator.last_provider
    )
    print(
        "Status:",
        orchestrator.last_status
    )

    assert result is not None

    assert result["is_relevant"] is True

    assert result["is_new_topic"] is True

    assert result["slide_number"] == 1

    assert fake_gemini.calls == 1

    assert orchestrator.ollama_requests == 1

    assert orchestrator.last_provider == "OLLAMA"

    assert (
        orchestrator.last_status
        == "OLLAMA_SUCCESS"
    )

    print()
    print(
        "[PASS] Gemini failure detected."
    )

    print(
        "[PASS] Real Ollama fallback executed."
    )

    print(
        "[PASS] Real slide content generated."
    )

    print(
        "PPT:",
        ppt_manager.get_path()
    )


# ==============================================================
# MAIN
# ==============================================================


def main():

    print()
    print("=" * 80)
    print(
        "CONTROLLED END-TO-END LLM PIPELINE TEST"
    )
    print("=" * 80)

    test_gemini_primary()

    test_ollama_fallback()

    print()
    print("=" * 80)
    print(
        "ALL CONTROLLED INTEGRATION TESTS PASSED"
    )
    print("=" * 80)


if __name__ == "__main__":
    main()