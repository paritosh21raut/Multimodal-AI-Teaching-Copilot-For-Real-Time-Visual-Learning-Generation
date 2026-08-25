from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.application import Application
from app.lecture.lecture_pipeline import lecture_pipeline
from app.knowledge.content_generator import content_generator
from app.slides.slide_manager import slide_manager
from app.topics.topic_intelligence import topic_intelligence
from app.llm.llm_orchestrator import LLMOrchestrator


def main():

    print("=" * 80)
    print("APPLICATION WIRING TEST")
    print("=" * 80)

    # ----------------------------------------------------------
    # Create application.
    # ----------------------------------------------------------

    application = Application()

    print()
    print("Checking registered components...")
    print()

    # ----------------------------------------------------------
    # Topic detector
    # ----------------------------------------------------------

    assert (
        lecture_pipeline.topic_detector
        is topic_intelligence
    )

    print(
        "[PASS] TopicIntelligence registered"
    )

    # ----------------------------------------------------------
    # Content generator
    # ----------------------------------------------------------

    assert (
        lecture_pipeline.content_generator
        is content_generator
    )

    print(
        "[PASS] ContentGenerator registered"
    )

    # ----------------------------------------------------------
    # Slide manager
    # ----------------------------------------------------------

    assert (
        lecture_pipeline.slide_manager
        is slide_manager
    )

    print(
        "[PASS] SlideManager registered"
    )

    # ----------------------------------------------------------
    # LLM orchestrator
    # ----------------------------------------------------------

    assert isinstance(
        content_generator.llm,
        LLMOrchestrator,
    )

    print(
        "[PASS] LLMOrchestrator connected"
    )

    print(
        "Primary provider:",
        content_generator.llm.primary,
    )

    print(
        "Fallback enabled:",
        content_generator.llm.fallback_enabled,
    )

    print(
        "Ollama enabled:",
        content_generator.llm.ollama_enabled,
    )

    # ----------------------------------------------------------
    # Required architecture
    # ----------------------------------------------------------

    assert (
        content_generator.llm.primary
        == "gemini"
    )

    assert (
        content_generator.llm.fallback_enabled
        is True
    )

    assert (
        content_generator.llm.ollama_enabled
        is True
    )

    print(
        "[PASS] Gemini is configured as PRIMARY"
    )

    print(
        "[PASS] Ollama fallback is ENABLED"
    )

    # ----------------------------------------------------------
    # Presentation
    # ----------------------------------------------------------

    assert (
        application.pipeline is not None
    )

    print(
        "[PASS] AudioPipeline created"
    )

    print()
    print(
        "PPT:",
        application.pipeline,
    )

    print()
    print("=" * 80)
    print("APPLICATION WIRING TEST PASSED")
    print("=" * 80)


if __name__ == "__main__":
    main()