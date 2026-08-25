from app.llm.ollama_client import (
    OllamaClient,
    OllamaUnavailableError,
)


def main():

    print("=" * 70)
    print("REAL OLLAMA STRUCTURED OUTPUT TEST")
    print("=" * 70)

    client = OllamaClient()

    print(
        "Model      :",
        client.model,
    )

    print(
        "Base URL   :",
        client.base_url,
    )

    available = (
        client.is_available()
    )

    print(
        "Available  :",
        available,
    )

    if not available:

        raise RuntimeError(
            "Ollama is not available at "
            f"{client.base_url}"
        )

    prompt = """
You are an educational presentation designer.

Create ONE PowerPoint slide about microcontrollers.

Lecture:
A microcontroller is a small computer on a single chip.
It contains a CPU, memory and input/output peripherals.
It is commonly used in embedded systems.

Your response is constrained by a JSON schema.

Return only the requested JSON object.
Do not return markdown.
Do not return explanations.
Do not return reasoning.

The visual type should be a diagram because the lecture
describes the components of a microcontroller.
"""

    try:

        result = (
            client.generate_slide(
                prompt
            )
        )

    except OllamaUnavailableError as error:

        print(
            "[FAIL]",
            error,
        )

        raise

    print()
    print(
        "NORMALIZED RESULT"
    )
    print(
        "=" * 70
    )
    print(
        result
    )
    print(
        "=" * 70
    )

    required_fields = {
        "title",
        "bullets",
        "summary",
        "keywords",
        "content_type",
        "visual_type",
        "visual_reason",
        "image_query",
        "visual_spec",
        "diagram",
    }

    missing = (
        required_fields
        - set(result.keys())
    )

    assert not missing, (
        f"Missing fields: {missing}"
    )

    assert isinstance(
        result["title"],
        str,
    )

    assert isinstance(
        result["bullets"],
        list,
    )

    assert isinstance(
        result["summary"],
        str,
    )

    assert isinstance(
        result["keywords"],
        list,
    )

    assert isinstance(
        result["visual_spec"],
        dict,
    )

    print(
        "[PASS] Required fields"
    )

    print(
        "[PASS] Valid JSON"
    )

    print(
        "[PASS] Normalized output"
    )

    print(
        "[PASS] Structured visual specification"
    )

    print(
        "=" * 70
    )

    print(
        "REAL OLLAMA STRUCTURED OUTPUT TEST PASSED"
    )

    print(
        "=" * 70
    )


if __name__ == "__main__":
    main()