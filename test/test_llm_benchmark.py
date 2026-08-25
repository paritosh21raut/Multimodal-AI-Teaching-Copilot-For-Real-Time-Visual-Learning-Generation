from __future__ import annotations

import json
import time
from pathlib import Path

from app.ai.gemini_client import (
    GeminiClient,
    GeminiPermanentError,
    GeminiQuotaError,
    GeminiTransientError,
)

from app.knowledge.content_generator import (
    ContentGenerator,
)

from app.llm.llm_orchestrator import (
    LLMOrchestrator,
)

from app.llm.ollama_client import (
    OllamaClient,
)


# ==============================================================
# TEST SCENARIOS
# ==============================================================

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


# ==============================================================
# DISABLED GEMINI FOR OLLAMA-ONLY BENCHMARK
# ==============================================================

class GeminiDisabledClient:

    def generate_slide(
        self,
        topic,
        context,
    ):
        raise GeminiPermanentError(
            "Gemini intentionally disabled for Ollama benchmark."
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


# ==============================================================
# SLIDECONTENT -> DICT
# ==============================================================

def content_to_dict(
    content,
) -> dict:

    return {
        "title": content.title,
        "bullets": [
            bullet.text
            for bullet in content.bullets
        ],
        "summary": content.summary,
        "keywords": list(
            content.keywords
        ),
        "content_type": content.content_type,
        "visual_type": content.visual_type,
        "visual_reason": (
            content.visual_reason
            or ""
        ),
        "image_query": (
            content.image_query
            or ""
        ),
        "visual_spec": dict(
            content.visual_spec
            or {}
        ),
        "diagram": (
            content.diagram.description
            if content.diagram is not None
            else ""
        ),
    }


# ==============================================================
# SCORE NORMALIZED RESULT
# ==============================================================

def score_result(
    scenario_name: str,
    result: dict,
) -> dict:

    content_type = str(
        result.get(
            "content_type",
            "unknown",
        )
    )

    visual_type = str(
        result.get(
            "visual_type",
            "unknown",
        )
    )

    bullets = result.get(
        "bullets",
        [],
    )

    visual_spec = result.get(
        "visual_spec",
        {},
    )

    score = 0
    reasons = []

    # ----------------------------------------------------------
    # Expected visual
    # ----------------------------------------------------------

    expected_visuals = {
        "definition": {
            "none",
            "image",
            "diagram",
        },
        "comparison": {
            "comparison_table",
        },
        "process": {
            "flowchart",
        },
        "architecture": {
            "diagram",
        },
        "examples": {
            "example_grid",
        },
        "numeric_data": {
            "chart",
        },
    }

    expected = expected_visuals[
        scenario_name
    ]

    if visual_type in expected:

        score += 3

        reasons.append(
            "Correct visual category"
        )

    else:

        reasons.append(
            f"Expected {expected}, got {visual_type}"
        )

    # ----------------------------------------------------------
    # Expected content
    # ----------------------------------------------------------

    expected_content_types = {
        "definition": {
            "definition",
            "explanation",
        },
        "comparison": {
            "comparison",
        },
        "process": {
            "process",
            "sequence",
        },
        "architecture": {
            "explanation",
            "classification",
            "mixed",
        },
        "examples": {
            "examples",
            "list",
        },
        "numeric_data": {
            "data",
            "comparison",
            "list",
        },
    }

    if content_type in expected_content_types[
        scenario_name
    ]:

        score += 2

        reasons.append(
            "Correct content category"
        )

    else:

        reasons.append(
            "Content category mismatch"
        )

    # ----------------------------------------------------------
    # Bullets
    # ----------------------------------------------------------

    if (
        isinstance(
            bullets,
            list,
        )
        and 2 <= len(bullets) <= 6
    ):

        score += 1

        reasons.append(
            "Reasonable bullet count"
        )

    else:

        reasons.append(
            "Poor bullet count"
        )

    # ----------------------------------------------------------
    # Structured visual
    # ----------------------------------------------------------

    if visual_type not in {
        "none",
        "image",
    }:

        if (
            isinstance(
                visual_spec,
                dict,
            )
            and visual_spec
        ):

            score += 2

            reasons.append(
                "Structured visual specification present"
            )

        else:

            reasons.append(
                "Missing structured visual specification"
            )

    else:

        score += 1

    # ----------------------------------------------------------
    # Title
    # ----------------------------------------------------------

    title = str(
        result.get(
            "title",
            "",
        )
    ).strip()

    if title:

        score += 1

        reasons.append(
            "Title present"
        )

    return {
        "score": score,
        "max_score": 9,
        "reasons": reasons,
    }


# ==============================================================
# RUN GEMINI THROUGH COMPLETE CONTENT PIPELINE
# ==============================================================

def run_gemini(
    gemini,
    scenario,
):

    start = time.perf_counter()

    try:

        orchestrator = LLMOrchestrator(
            gemini=gemini,
            ollama=OllamaClient(),
        )

        # ------------------------------------------------------
        # Benchmark Gemini itself.
        #
        # Absolutely do NOT fallback here.
        # We want to know how Gemini performs.
        # ------------------------------------------------------

        orchestrator.primary = "gemini"
        orchestrator.fallback_enabled = False
        orchestrator.ollama_enabled = False

        generator = ContentGenerator(
            llm=orchestrator
        )

        content = generator.generate(
            topic=scenario["topic"],
            context=scenario["context"],
        )

        result = content_to_dict(
            content
        )

        latency = (
            time.perf_counter()
            - start
        )

        evaluation = score_result(
            scenario["name"],
            result,
        )

        return {
            "success": True,
            "latency_seconds": round(
                latency,
                3,
            ),
            "provider": (
                orchestrator.last_provider
            ),
            "result": result,
            "evaluation": evaluation,
        }

    except (
        GeminiQuotaError,
        GeminiTransientError,
        GeminiPermanentError,
    ) as error:

        latency = (
            time.perf_counter()
            - start
        )

        return {
            "success": False,
            "latency_seconds": round(
                latency,
                3,
            ),
            "provider": "GEMINI",
            "error": str(error),
        }

    except Exception as error:

        latency = (
            time.perf_counter()
            - start
        )

        return {
            "success": False,
            "latency_seconds": round(
                latency,
                3,
            ),
            "provider": "GEMINI",
            "error": str(error),
        }


# ==============================================================
# RUN REAL OLLAMA THROUGH COMPLETE CONTENT PIPELINE
# ==============================================================

def run_ollama(
    ollama,
    scenario,
):

    start = time.perf_counter()

    try:

        # ------------------------------------------------------
        # Gemini intentionally disabled.
        #
        # This proves the COMPLETE local fallback path:
        #
        # Gemini failure
        #      ↓
        # LLMOrchestrator
        #      ↓
        # Ollama
        #      ↓
        # ContentGenerator
        #      ↓
        # normalization + repair
        # ------------------------------------------------------

        disabled_gemini = (
            GeminiDisabledClient()
        )

        orchestrator = LLMOrchestrator(
            gemini=disabled_gemini,
            ollama=ollama,
        )

        orchestrator.primary = "gemini"
        orchestrator.fallback_enabled = True
        orchestrator.ollama_enabled = True

        generator = ContentGenerator(
            llm=orchestrator
        )

        content = generator.generate(
            topic=scenario["topic"],
            context=scenario["context"],
        )

        result = content_to_dict(
            content
        )

        latency = (
            time.perf_counter()
            - start
        )

        evaluation = score_result(
            scenario["name"],
            result,
        )

        return {
            "success": True,
            "latency_seconds": round(
                latency,
                3,
            ),
            "provider": (
                orchestrator.last_provider
            ),
            "result": result,
            "evaluation": evaluation,
        }

    except Exception as error:

        latency = (
            time.perf_counter()
            - start
        )

        return {
            "success": False,
            "latency_seconds": round(
                latency,
                3,
            ),
            "provider": "OLLAMA",
            "error": str(error),
        }


# ==============================================================
# PRINT PROVIDER RESULT
# ==============================================================

def print_provider_result(
    provider_name: str,
    result: dict,
):

    if not result["success"]:

        print(
            f"[{provider_name}] FAILED"
        )

        print(
            result.get(
                "error",
                "Unknown error",
            )
        )

        return

    print(
        f"[{provider_name}] Success"
    )

    print(
        "Latency:",
        result[
            "latency_seconds"
        ],
        "seconds",
    )

    print(
        "Provider:",
        result.get(
            "provider"
        ),
    )

    print(
        "Visual:",
        result[
            "result"
        ].get(
            "visual_type"
        ),
    )

    print(
        "Content:",
        result[
            "result"
        ].get(
            "content_type"
        ),
    )

    print(
        "Score:",
        result[
            "evaluation"
        ]["score"],
        "/",
        result[
            "evaluation"
        ]["max_score"],
    )

    print(
        "Reasons:"
    )

    for reason in result[
        "evaluation"
    ]["reasons"]:

        print(
            " -",
            reason,
        )


# ==============================================================
# MAIN
# ==============================================================

def main():

    print("=" * 80)
    print(
        "GEMINI VS OLLAMA "
        "FULL CONTENT PIPELINE BENCHMARK"
    )
    print("=" * 80)

    gemini = GeminiClient()

    ollama = OllamaClient()

    print()

    print(
        "Ollama available:",
        ollama.is_available(),
    )

    if gemini.client is None:

        raise RuntimeError(
            "Gemini API key is not configured."
        )

    results = []

    # ==========================================================
    # SCENARIOS
    # ==========================================================

    for scenario in SCENARIOS:

        print()
        print("=" * 80)

        print(
            f"SCENARIO: "
            f"{scenario['name'].upper()}"
        )

        print(
            f"Topic: "
            f"{scenario['topic']}"
        )

        print("=" * 80)

        # ------------------------------------------------------
        # Gemini
        # ------------------------------------------------------

        print(
            "\n[Gemini] Running..."
        )

        gemini_result = run_gemini(
            gemini,
            scenario,
        )

        print_provider_result(
            "Gemini",
            gemini_result,
        )

        # ------------------------------------------------------
        # Ollama
        # ------------------------------------------------------

        print(
            "\n[Ollama] Running..."
        )

        ollama_result = run_ollama(
            ollama,
            scenario,
        )

        print_provider_result(
            "Ollama",
            ollama_result,
        )

        # ------------------------------------------------------
        # Store
        # ------------------------------------------------------

        results.append(
            {
                "scenario": scenario,
                "gemini": gemini_result,
                "ollama": ollama_result,
            }
        )

    # ==========================================================
    # SUMMARY
    # ==========================================================

    print()
    print()
    print("=" * 80)
    print(
        "BENCHMARK SUMMARY"
    )
    print("=" * 80)

    for item in results:

        name = item[
            "scenario"
        ]["name"]

        gemini_data = item[
            "gemini"
        ]

        ollama_data = item[
            "ollama"
        ]

        print()
        print(
            name.upper()
        )

        # Gemini
        if gemini_data["success"]:

            print(
                " Gemini :",
                gemini_data[
                    "latency_seconds"
                ],
                "sec | score",
                gemini_data[
                    "evaluation"
                ]["score"],
                "/ 9",
                "| visual",
                gemini_data[
                    "result"
                ].get(
                    "visual_type"
                ),
                "| provider",
                gemini_data.get(
                    "provider"
                ),
            )

        else:

            print(
                " Gemini : FAILED"
            )

        # Ollama
        if ollama_data["success"]:

            print(
                " Ollama :",
                ollama_data[
                    "latency_seconds"
                ],
                "sec | score",
                ollama_data[
                    "evaluation"
                ]["score"],
                "/ 9",
                "| visual",
                ollama_data[
                    "result"
                ].get(
                    "visual_type"
                ),
                "| provider",
                ollama_data.get(
                    "provider"
                ),
            )

        else:

            print(
                " Ollama : FAILED"
            )

    # ==========================================================
    # SAVE
    # ==========================================================

    output_path = Path(
        "outputs/llm_benchmark.json"
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
    print("=" * 80)

    print(
        "Benchmark saved to:",
        output_path,
    )

    print("=" * 80)


if __name__ == "__main__":
    main()