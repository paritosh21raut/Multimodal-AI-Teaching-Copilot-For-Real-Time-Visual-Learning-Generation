from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MODEL,
    OLLAMA_TIMEOUT_SECONDS,
)


class OllamaUnavailableError(RuntimeError):
    """Local Ollama service/model is unavailable."""


class OllamaClient:

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "title": {"type": "string"},
            "bullets": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 6,
            },
            "summary": {"type": "string"},
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
            },
            "content_type": {"type": "string"},
            "visual_type": {"type": "string"},
            "visual_reason": {"type": "string"},
            "image_query": {"type": "string"},
            "visual_spec": {"type": "object"},
            "diagram": {"type": "string"},
        },
        "required": [
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
        ],
    }

    VALID_CONTENT_TYPES = {
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

    VALID_VISUAL_TYPES = {
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

    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = OLLAMA_MODEL,
        timeout_seconds: float = OLLAMA_TIMEOUT_SECONDS,
    ) -> None:

        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    # ==========================================================
    # HTTP
    # ==========================================================

    def _request(
        self,
        endpoint: str,
        payload: Dict[str, Any],
    ) -> Dict[str, Any]:

        request = Request(
            f"{self.base_url}{endpoint}",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "AI-Teaching-Copilot/1.0",
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self.timeout_seconds,
            ) as response:

                raw = response.read().decode("utf-8")

        except HTTPError as error:

            try:
                message = error.read().decode("utf-8")
            except Exception:
                message = str(error)

            raise OllamaUnavailableError(
                f"Ollama HTTP {error.code}: {message}"
            ) from error

        except (
            URLError,
            TimeoutError,
            OSError,
        ) as error:

            raise OllamaUnavailableError(
                f"Ollama unavailable: {error}"
            ) from error

        try:
            return json.loads(raw)

        except json.JSONDecodeError as error:

            raise OllamaUnavailableError(
                "Ollama returned invalid HTTP JSON."
            ) from error

    # ==========================================================
    # AVAILABILITY
    # ==========================================================

    def is_available(self) -> bool:

        request = Request(
            f"{self.base_url}/api/tags",
            headers={
                "User-Agent": "AI-Teaching-Copilot/1.0"
            },
            method="GET",
        )

        try:

            with urlopen(
                request,
                timeout=2.5,
            ) as response:

                return 200 <= response.status < 300

        except Exception:
            return False

    # ==========================================================
    # SAFE HELPERS
    # ==========================================================

    @staticmethod
    def _safe_string(
        value: Any,
        default: str = "",
    ) -> str:

        if value is None:
            return default

        if isinstance(
            value,
            (dict, list),
        ):
            return default

        return str(value).strip()

    @staticmethod
    def _safe_list(
        value: Any,
    ) -> list:

        return value if isinstance(value, list) else []

    @staticmethod
    def _safe_dict(
        value: Any,
    ) -> Dict[str, Any]:

        return value if isinstance(value, dict) else {}

    # ==========================================================
    # NORMALIZE
    # ==========================================================

    def _normalize_result(
        self,
        result: Any,
    ) -> Dict[str, Any]:

        if not isinstance(result, dict):

            raise OllamaUnavailableError(
                "Ollama returned a JSON value "
                "that is not an object."
            )

        bullets = self._safe_list(
            result.get("bullets", [])
        )

        normalized_bullets = []

        for item in bullets[:6]:

            if isinstance(item, dict):

                text = self._safe_string(
                    item.get("text", "")
                )

            else:

                text = self._safe_string(item)

            if text:
                normalized_bullets.append(text)

        keywords = self._safe_list(
            result.get("keywords", [])
        )

        normalized_keywords = []

        for item in keywords:

            text = self._safe_string(item)

            if text:
                normalized_keywords.append(text)

        content_type = self._safe_string(
            result.get(
                "content_type",
                "explanation",
            ),
            "explanation",
        ).lower()

        visual_type = self._safe_string(
            result.get(
                "visual_type",
                "none",
            ),
            "none",
        ).lower()

        if content_type not in self.VALID_CONTENT_TYPES:
            content_type = "explanation"

        if visual_type not in self.VALID_VISUAL_TYPES:
            visual_type = "none"

        return {
            "title": self._safe_string(
                result.get("title")
            ),
            "bullets": normalized_bullets,
            "summary": self._safe_string(
                result.get("summary")
            ),
            "keywords": normalized_keywords,
            "content_type": content_type,
            "visual_type": visual_type,
            "visual_reason": self._safe_string(
                result.get("visual_reason")
            ),
            "image_query": self._safe_string(
                result.get("image_query")
            ),
            "visual_spec": self._safe_dict(
                result.get("visual_spec", {})
            ),
            "diagram": self._safe_string(
                result.get("diagram")
            ),
        }

    # ==========================================================
    # LOCAL STRUCTURE INFERENCE
    #
    # No Gemini.
    # No API.
    #
    # Uses only topic/context already supplied to Ollama.
    # ==========================================================

    @staticmethod
    def _infer_expected_structure(
        topic: str,
        context: str,
    ) -> Dict[str, str]:

        text = (
            f"{topic} {context}"
        ).lower()

        # ------------------------------------------------------
        # Comparison
        # ------------------------------------------------------

        if (
            " vs " in topic.lower()
            or "versus" in text
            or (
                " compared "
                in f" {text} "
            )
            or (
                "difference between"
                in text
            )
        ):

            return {
                "content_type": "comparison",
                "visual_type": "comparison_table",
            }

        # ------------------------------------------------------
        # Numeric data
        # ------------------------------------------------------

        numeric_units = (
            "mhz",
            "ghz",
            "%",
            "percent",
            "kg",
            "cm",
            "mm",
            "ms",
            "seconds",
            "hours",
        )

        has_numeric_data = (
            any(
                unit in text
                for unit in numeric_units
            )
            and len(
                re.findall(
                    r"\d+(?:\.\d+)?",
                    text,
                )
            ) >= 2
        )

        if has_numeric_data:

            return {
                "content_type": "data",
                "visual_type": "chart",
            }

        # ------------------------------------------------------
        # Process / sequence
        # ------------------------------------------------------

        process_signals = (
            "first",
            "then",
            "next",
            "finally",
            "step",
            "process",
            "pipeline",
            "converts",
            "captures",
            "sends",
            "flows",
        )

        process_hits = sum(
            signal in text
            for signal in process_signals
        )

        if process_hits >= 2:

            return {
                "content_type": "process",
                "visual_type": "flowchart",
            }

        # ------------------------------------------------------
        # Examples
        # ------------------------------------------------------

        example_signals = (
            "examples include",
            "examples are",
            "for example",
            "such as",
            "arduino",
            "esp32",
            "stm32",
            "pic",
            "avr",
        )

        example_hits = sum(
            signal in text
            for signal in example_signals
        )

        if example_hits >= 2:

            return {
                "content_type": "examples",
                "visual_type": "example_grid",
            }

        # ------------------------------------------------------
        # Architecture / components
        # ------------------------------------------------------

        architecture_signals = (
            "architecture",
            "components",
            "cpu",
            "ram",
            "program memory",
            "input/output",
            "i/o",
            "peripherals",
            "timers",
        )

        architecture_hits = sum(
            signal in text
            for signal in architecture_signals
        )

        if (
            "architecture" in text
            or architecture_hits >= 4
        ):

            return {
                "content_type": "explanation",
                "visual_type": "diagram",
            }

        # ------------------------------------------------------
        # Default
        # ------------------------------------------------------

        return {
            "content_type": "explanation",
            "visual_type": "none",
        }

    # ==========================================================
    # REPAIR STRUCTURED RESULT
    # ==========================================================

    def _repair_result(
        self,
        result: Dict[str, Any],
        topic: Optional[str],
        context: Optional[str],
    ) -> Dict[str, Any]:

        if not topic and not context:
            return result

        expected = (
            self._infer_expected_structure(
                topic or "",
                context or "",
            )
        )

        expected_content = expected[
            "content_type"
        ]

        expected_visual = expected[
            "visual_type"
        ]

        current_visual = result[
            "visual_type"
        ]

        current_content = result[
            "content_type"
        ]

        # ------------------------------------------------------
        # Only repair when the local evidence is strong.
        # ------------------------------------------------------

        if (
            expected_content
            != current_content
            or expected_visual
            != current_visual
        ):

            result[
                "content_type"
            ] = expected_content

            result[
                "visual_type"
            ] = expected_visual

            # --------------------------------------------------
            # Build missing structured specification.
            # --------------------------------------------------

            if expected_visual == "comparison_table":

                result["visual_spec"] = (
                    self._build_comparison_spec(
                        context or ""
                    )
                )

            elif expected_visual == "flowchart":

                result["visual_spec"] = (
                    self._build_flowchart_spec(
                        context or ""
                    )
                )

            elif expected_visual == "example_grid":

                result["visual_spec"] = (
                    self._build_example_grid_spec(
                        context or ""
                    )
                )

            elif expected_visual == "chart":

                result["visual_spec"] = (
                    self._build_chart_spec(
                        context or ""
                    )
                )

            elif expected_visual == "diagram":

                result["visual_spec"] = (
                    self._build_diagram_spec(
                        context or ""
                    )
                )

        return result

    # ==========================================================
    # SPEC BUILDERS
    # ==========================================================

    @staticmethod
    def _build_comparison_spec(
        context: str,
    ) -> Dict[str, Any]:

        text = context.lower()

        columns = [
            "Feature",
            "Microcontroller",
            "Microprocessor",
        ]

        rows = []

        if (
            "memory"
            in text
            and "peripherals"
            in text
        ):

            rows.append(
                {
                    "label": (
                        "Memory & Peripherals"
                    ),
                    "values": [
                        (
                            "Integrated on chip"
                        ),
                        (
                            "Usually external"
                        ),
                    ],
                }
            )

        rows.append(
            {
                "label": "CPU",
                "values": [
                    "Integrated",
                    "Mainly CPU",
                ],
            }
        )

        return {
            "columns": columns,
            "rows": rows,
        }

    @staticmethod
    def _build_flowchart_spec(
        context: str,
    ) -> Dict[str, Any]:

        text = context.lower()

        nodes = []

        if "sensor" in text:
            nodes.append(
                "Sensor"
            )

        if "adc" in text:
            nodes.append(
                "ADC"
            )

        if "cpu" in text:
            nodes.append(
                "CPU"
            )

        if "actuator" in text:
            nodes.append(
                "Actuator"
            )

        if len(nodes) < 2:

            nodes = [
                "Step 1",
                "Step 2",
            ]

        edges = []

        for index in range(
            len(nodes) - 1
        ):

            edges.append(
                [
                    nodes[index],
                    nodes[index + 1],
                ]
            )

        return {
            "nodes": nodes[:6],
            "edges": edges[:5],
        }

    @staticmethod
    def _build_example_grid_spec(
        context: str,
    ) -> Dict[str, Any]:

        known = (
            "Arduino Uno",
            "ESP32",
            "STM32",
            "PIC",
            "AVR",
        )

        examples = []

        lower = context.lower()

        for item in known:

            if item.lower() in lower:

                examples.append(item)

        if not examples:

            examples = [
                "Example A",
                "Example B",
            ]

        return {
            "examples": examples[:6]
        }

    @staticmethod
    def _build_chart_spec(
        context: str,
    ) -> Dict[str, Any]:

        pairs = re.findall(
            r"([A-Za-z][A-Za-z ]+?)"
            r"\s+(?:operates at|is)\s+"
            r"(\d+(?:\.\d+)?)",
            context,
            flags=re.IGNORECASE,
        )

        x = []
        y = []

        for name, value in pairs:

            name = name.strip(
                " .,;:"
            )

            if name:
                x.append(name)
                y.append(float(value))

        if not x:

            numbers = re.findall(
                r"\d+(?:\.\d+)?",
                context,
            )

            y = [
                float(value)
                for value in numbers[:6]
            ]

            x = [
                f"Item {index + 1}"
                for index in range(
                    len(y)
                )
            ]

        return {
            "chart_type": "bar",
            "x": x[:6],
            "y": y[:6],
        }

    @staticmethod
    def _build_diagram_spec(
        context: str,
    ) -> Dict[str, Any]:

        text = context.lower()

        candidates = [
            (
                "CPU",
                "cpu",
            ),
            (
                "RAM",
                "ram",
            ),
            (
                "Program Memory",
                "program memory",
            ),
            (
                "Input/Output Ports",
                "input/output",
            ),
            (
                "I/O Ports",
                "i/o",
            ),
            (
                "Timers",
                "timers",
            ),
            (
                "Communication Peripherals",
                "communication peripherals",
            ),
            (
                "Peripherals",
                "peripherals",
            ),
        ]

        components = []

        seen = set()

        for label, signal in candidates:

            if signal in text:

                key = label.lower()

                if key not in seen:

                    seen.add(key)

                    components.append(
                        label
                    )

        if not components:

            components = [
                "CPU",
                "Memory",
                "I/O Peripherals",
            ]

        return {
            "center": "Microcontroller",
            "components": components[:6],
            "relationships": [
                [
                    "Microcontroller",
                    component,
                ]
                for component
                in components[:6]
            ],
        }

    # ==========================================================
    # GENERATE
    # ==========================================================

    def generate_slide(
        self,
        prompt: str,
        topic: Optional[str] = None,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:

        # ------------------------------------------------------
        # When called without topic/context, preserve the old API.
        # ------------------------------------------------------

        effective_prompt = prompt

        if topic and context:

            expected = (
                self._infer_expected_structure(
                    topic,
                    context,
                )
            )

            effective_prompt = f"""
You are the LOCAL FALLBACK slide generator.

The primary cloud model is unavailable.
Generate ONE educational slide from the lecture content.

TOPIC:
{topic}

LECTURE:
{context}

STRICT SEMANTIC RULES:

1. Comparison / "A vs B":
   content_type = "comparison"
   visual_type = "comparison_table"

2. Ordered process / sequence:
   content_type = "process"
   visual_type = "flowchart"

3. Multiple named examples:
   content_type = "examples"
   visual_type = "example_grid"

4. Multiple numeric measurements:
   content_type = "data"
   visual_type = "chart"

5. Internal hardware/software architecture:
   content_type = "explanation"
   visual_type = "diagram"

6. Simple definition:
   content_type = "definition" or "explanation"
   visual_type = "none" unless a visual clearly improves teaching.

IMPORTANT:
- Do NOT use diagram for comparisons.
- Do NOT use comparison_table for processes.
- Do NOT use none when clear numeric data exists.
- Do NOT invent facts.
- Do NOT invent numbers.
- Use only information supported by the lecture.
- Maximum 6 bullets.
- Return ONLY JSON.

Expected fallback classification:
content_type = {expected["content_type"]}
visual_type = {expected["visual_type"]}

Return exactly these fields:
{{
  "title": "...",
  "bullets": ["..."],
  "summary": "...",
  "keywords": ["..."],
  "content_type": "...",
  "visual_type": "...",
  "visual_reason": "...",
  "image_query": "",
  "visual_spec": {{}},
  "diagram": ""
}}
""".strip()

        payload = {
            "model": self.model,
            "prompt": effective_prompt,
            "stream": False,
            "format": self.RESPONSE_SCHEMA,
            "think": False,
            "keep_alive": "10m",
            "options": {
                "temperature": 0,
                "num_predict": 900,
            },
        }

        response = self._request(
            "/api/generate",
            payload,
        )

        text = str(
            response.get(
                "response",
                "",
            )
        ).strip()

        if not text:

            raise OllamaUnavailableError(
                "Ollama returned an empty response."
            )

        if text.startswith("```json"):
            text = text[7:]

        elif text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        try:

            result = json.loads(
                text.strip()
            )

        except json.JSONDecodeError as error:

            preview = text[:1000]

            raise OllamaUnavailableError(
                "Ollama returned malformed JSON. "
                f"Raw response: {preview}"
            ) from error

        result = self._normalize_result(
            result
        )

        result = self._repair_result(
            result=result,
            topic=topic,
            context=context,
        )

        return result