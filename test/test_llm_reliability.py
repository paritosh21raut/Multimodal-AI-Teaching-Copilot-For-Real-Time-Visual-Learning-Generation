from __future__ import annotations

from app.ai.gemini_client import GeminiPermanentError
from app.knowledge.content_generator import ContentGenerator
from app.llm.llm_orchestrator import LLMOrchestrator


class FakeGemini:
    def __init__(self, should_fail=False):
        self.should_fail = should_fail
        self.calls = 0

    def generate_slide(self, topic, context):
        self.calls += 1
        if self.should_fail:
            raise GeminiPermanentError(
                "simulated Gemini failure"
            )
        return {
            "title": topic,
            "bullets": ["Gemini result"],
            "summary": "",
            "keywords": [],
            "content_type": "explanation",
            "visual_type": "none",
            "visual_reason": "",
            "image_query": "",
            "visual_spec": {},
            "diagram": "",
        }

    def build_prompt(self, topic, context):
        return f"TOPIC: {topic}\nCONTEXT: {context}"

    def status(self):
        return {
            "model": "fake",
            "calls": self.calls,
            "successes": self.calls,
            "failures": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "status": "TEST",
            "last_error": "",
        }


class FakeOllama:
    def __init__(self):
        self.calls = 0

    def is_available(self):
        return True

    def generate_slide(self, prompt):
        self.calls += 1
        return {
            "title": "Fallback slide",
            "bullets": ["Ollama fallback works"],
            "summary": "",
            "keywords": [],
            "content_type": "explanation",
            "visual_type": "none",
            "visual_reason": "Fallback",
            "image_query": "",
            "visual_spec": {},
            "diagram": "",
        }


def main():
    print("=" * 70)
    print("LLM RELIABILITY TEST")
    print("=" * 70)

    gemini = FakeGemini(False)
    ollama = FakeOllama()
    orchestrator = LLMOrchestrator(
        gemini=gemini,
        ollama=ollama,
    )
    orchestrator.ollama_enabled = True

    result = orchestrator.generate_slide(
        "Microcontrollers",
        "A microcontroller is a small computer on a chip.",
    )

    assert result["title"] == "Microcontrollers"
    assert orchestrator.last_provider == "GEMINI"
    assert ollama.calls == 0
    print("[PASS] Gemini primary path")

    failing_gemini = FakeGemini(True)
    fallback_ollama = FakeOllama()
    fallback_orchestrator = LLMOrchestrator(
        gemini=failing_gemini,
        ollama=fallback_ollama,
    )
    fallback_orchestrator.ollama_enabled = True

    result = fallback_orchestrator.generate_slide(
        "Types of Microcontrollers",
        "8-bit, 16-bit and 32-bit controllers.",
    )

    assert result["title"] == "Fallback slide"
    assert fallback_orchestrator.last_provider == "OLLAMA"
    assert fallback_ollama.calls == 1
    print("[PASS] Gemini -> Ollama fallback")

    generator = ContentGenerator(
        llm=fallback_orchestrator
    )

    content = generator.generate(
        "8-bit vs 16-bit",
        "Two controller word sizes are being compared.",
    )

    assert content.visual_type == "none"
    assert content.title == "Fallback slide"
    print("[PASS] Content normalization/validation")

    print("=" * 70)
    print("LLM RELIABILITY TEST PASSED")
    print("=" * 70)


if __name__ == "__main__":
    main()