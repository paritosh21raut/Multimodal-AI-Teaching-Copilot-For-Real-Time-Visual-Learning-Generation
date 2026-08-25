from __future__ import annotations

import json
import time
from pathlib import Path

from app.knowledge.content_generator import (
    ContentGenerator,
)

from app.llm.llm_orchestrator import (
    LLMOrchestrator,
)

from app.llm.ollama_client import (
    OllamaClient,
)


SCENARIOS = [
    {
        "name": "definition",
        "topic": "Microcontroller",
        "context": (
            "A microcontroller is a small computer on a single chip. "
            "It contains a CPU, memory and input/output peripherals. "
            "It is commonly used in embedded systems."
        ),
    },
    {
        "name": "comparison",
        "topic": "Microcontroller vs Microprocessor",
        "context": (
            "A microcontroller combines the CPU, memory and peripherals "
            "on one chip. A microprocessor mainly contains the CPU and "
            "usually depends on external memory and peripherals."
        ),
    },
    {
        "name": "process",
        "topic": "Sensor Data Processing",
        "context": (
            "First the sensor captures the physical signal. "
            "The ADC converts the analog signal into digital data. "
            "The CPU processes the digital data. "
            "Finally the system sends the result to the actuator."
        ),
    },
    {
        "name": "architecture",
        "topic": "Microcontroller Architecture",
        "context": (
            "A microcontroller contains a CPU, RAM, program memory, "
            "input/output ports, timers and communication peripherals. "
            "These components work together inside the microcontroller."
        ),
    },
    {
        "name": "examples",
        "topic": "Examples of Microcontrollers",
        "context": (
            "Examples include Arduino Uno, ESP32, STM32, PIC and AVR "
            "microcontrollers."
        ),
    },
    {
        "name": "numeric_data",
        "topic": "Microcontroller Performance",
        "context": (
            "Controller A operates at 16 MHz, controller B operates at "
            "32 MHz, and controller C operates at 80 MHz."
        ),
    },
]


EXPECTED = {
    "definition": {
        "content": {
            "definition",
            "explanation",
        },
        "visual": {
            "none",
            "image",
            "diagram",
        },
    },
    "comparison": {
        "content": {
            "comparison",
        },
        "visual": {
            "comparison_table",
        },
    },
    "process": {
        "content": {
            "process",
            "sequence",
        },
        "visual": {
            "flowchart",
        },
    },
    "architecture": {
        "content": {
            "explanation",
            "classification",
            "mixed",
        },
        "visual": {
            "diagram",
        },
    },
    "examples": {
        "content": {
            "examples",
            "list",
        },
        "visual": {
            "example_grid",
        },
    },
    "numeric_data": {
        "content": {
            "data",
            "comparison",
        },
        "visual": {
            "chart",
        },
    },
}


def evaluate(
    name: str,
    content,
) -> int:

    score = 0

    expected = EXPECTED[name]

    if content.content_type in expected["content"]:
        score += 1

    if content.visual_type in expected["visual"]:
        score += 2

    if content.title.strip():
        score += 1

    if 2 <= len(content.bullets) <= 6:
        score += 1

    if content.visual_type in {
        "diagram",
        "flowchart",
        "comparison_table",
        "chart",
        "example_grid",
        "timeline",
        "hierarchy",
        "formula",
        "concept_map",
    } and content.visual_spec:
        score += 1

    return score


def main():

    print("=" * 80)
    print("OLLAMA FALLBACK QUALITY TEST")
    print("=" * 80)

    ollama = OllamaClient()

    print(
        "Model      :",
        ollama.model,
    )

    print(
        "Base URL   :",
        ollama.base_url,
    )

    print(
        "Available  :",
        ollama.is_available(),
    )

    if not ollama.is_available():
        raise RuntimeError(
            "Ollama is unavailable."
        )

    results = []

    for scenario in SCENARIOS:

        print()
        print("=" * 80)
        print(
            "SCENARIO:",
            scenario["name"].upper(),
        )
        print(
            "TOPIC:",
            scenario["topic"],
        )
        print("=" * 80)

        # ------------------------------------------------------
        # IMPORTANT:
        # No real GeminiClient is created.
        # No Gemini API call can happen.
        # ------------------------------------------------------

        orchestrator = LLMOrchestrator(
            gemini=None,
            ollama=ollama,
        )

        # Force the fallback path without Gemini API.
        orchestrator.primary = "ollama"
        orchestrator.fallback_enabled = False
        orchestrator.ollama_enabled = True

        generator = ContentGenerator(
            llm=orchestrator
        )

        start = time.perf_counter()

        content = generator.generate(
            topic=scenario["topic"],
            context=scenario["context"],
        )

        latency = (
            time.perf_counter()
            - start
        )

        score = evaluate(
            scenario["name"],
            content,
        )

        print()
        print(
            "Provider     :",
            orchestrator.last_provider,
        )

        print(
            "Latency      :",
            round(latency, 3),
            "seconds",
        )

        print(
            "Content Type :",
            content.content_type,
        )

        print(
            "Visual Type  :",
            content.visual_type,
        )

        print(
            "Title        :",
            content.title,
        )

        print(
            "Bullets      :",
            len(content.bullets),
        )

        print(
            "Visual Spec  :",
            content.visual_spec,
        )

        print(
            "SCORE        :",
            score,
            "/ 6",
        )

        results.append(
            {
                "scenario": scenario,
                "latency_seconds": round(
                    latency,
                    3,
                ),
                "provider": orchestrator.last_provider,
                "content_type": content.content_type,
                "visual_type": content.visual_type,
                "title": content.title,
                "bullets": [
                    bullet.text
                    for bullet
                    in content.bullets
                ],
                "visual_spec": content.visual_spec,
                "score": score,
            }
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    print()
    print("=" * 80)
    print("OLLAMA QUALITY SUMMARY")
    print("=" * 80)

    for item in results:

        print(
            f"{item['scenario']['name']:15}"
            f" {item['score']}/6"
            f" | {item['content_type']:15}"
            f" | {item['visual_type']}"
            f" | {item['latency_seconds']}s"
        )

    output_path = Path(
        "outputs/ollama_quality.json"
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_path.write_text(
        json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "Saved:",
        output_path,
    )


if __name__ == "__main__":
    main()