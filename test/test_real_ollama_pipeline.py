from app.ai.gemini_client import GeminiPermanentError

from app.llm.llm_orchestrator import (
    LLMOrchestrator,
)

from app.llm.ollama_client import (
    OllamaClient,
)

from app.knowledge.content_generator import (
    ContentGenerator,
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


def main():

    print("=" * 70)
    print("REAL OLLAMA CONTENT GENERATION TEST")
    print("=" * 70)

    # ----------------------------------------------------------
    # REAL OLLAMA
    # ----------------------------------------------------------

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

    # ----------------------------------------------------------
    # Gemini intentionally disabled.
    # This raises a Gemini-specific exception so that
    # the real orchestrator enters its fallback path.
    # ----------------------------------------------------------

    gemini = GeminiDisabledClient()

    orchestrator = LLMOrchestrator(
        gemini=gemini,
        ollama=ollama,
    )

    orchestrator.primary = "gemini"
    orchestrator.fallback_enabled = True
    orchestrator.ollama_enabled = True

    # ----------------------------------------------------------
    # REAL CONTENT GENERATOR
    # ----------------------------------------------------------

    generator = ContentGenerator(
        llm=orchestrator
    )

    topic = "Microcontroller Architecture"

    context = """
The teacher is explaining the architecture of a microcontroller.

A microcontroller is a small computer on a single chip.
It contains a CPU, memory and input/output peripherals.
The CPU processes instructions.
Memory stores data and program information.
Input/output peripherals allow the microcontroller to communicate
with external devices.
"""

    print()
    print(
        "Generating slide using REAL Ollama..."
    )

    content = generator.generate(
        topic=topic,
        context=context,
    )

    # ----------------------------------------------------------
    # RESULT
    # ----------------------------------------------------------

    print()
    print("=" * 70)
    print("CONTENT GENERATION RESULT")
    print("=" * 70)

    print(
        "Provider      :",
        orchestrator.last_provider,
    )

    print(
        "Status        :",
        orchestrator.last_status,
    )

    print(
        "Title         :",
        content.title,
    )

    print(
        "Content Type  :",
        content.content_type,
    )

    print(
        "Visual Type   :",
        content.visual_type,
    )

    print(
        "Visual Reason :",
        content.visual_reason,
    )

    print(
        "Visual Spec   :",
        content.visual_spec,
    )

    print(
        "Bullets:"
    )

    for index, bullet in enumerate(
        content.bullets,
        start=1,
    ):

        print(
            f"  {index}. {bullet.text}"
        )

    print(
        "Summary       :",
        content.summary,
    )

    print(
        "Keywords      :",
        content.keywords,
    )

    print(
        "=" * 70
    )

    # ----------------------------------------------------------
    # ASSERTIONS
    # ----------------------------------------------------------

    assert (
        orchestrator.last_provider
        == "OLLAMA"
    )

    assert (
        orchestrator.last_status
        == "OLLAMA_SUCCESS"
    )

    assert content.title.strip()

    assert isinstance(
        content.bullets,
        list,
    )

    assert content.content_type in {
        "definition",
        "explanation",
        "list",
        "examples",
        "comparison",
        "classification",
        "process",
        "sequence",
        "cause_effect",
        "advantages_disadvantages",
        "formula",
        "data",
        "application",
        "summary",
        "mixed",
    }

    assert content.visual_type in {
        "none",
        "image",
        "diagram",
        "flowchart",
        "comparison_table",
        "chart",
        "timeline",
        "hierarchy",
        "example_grid",
        "formula",
        "concept_map",
    }

    assert isinstance(
        content.visual_spec,
        dict,
    )

    print()
    print(
        "[PASS] Gemini disabled"
    )

    print(
        "[PASS] Real Ollama fallback used"
    )

    print(
        "[PASS] Real ContentGenerator worked"
    )

    print(
        "[PASS] Visual validation worked"
    )

    print()
    print("=" * 70)
    print(
        "REAL OLLAMA PIPELINE TEST PASSED"
    )
    print("=" * 70)


if __name__ == "__main__":
    main()