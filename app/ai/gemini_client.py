from __future__ import annotations

import json
import random
import time
from typing import Any, Dict, Optional

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from app.config import (
    GEMINI_API_KEY,
    GEMINI_MAX_OUTPUT_TOKENS,
    GEMINI_MODEL,
)


class GeminiTransientError(RuntimeError):
    """Temporary Gemini problem suitable for fallback/retry."""


class GeminiQuotaError(RuntimeError):
    """Gemini quota/rate-limit exhaustion."""


class GeminiPermanentError(RuntimeError):
    """Gemini error that should not be retried."""


class GeminiTableRow(BaseModel):
    label: str = ""
    values: list[str] = Field(
        default_factory=list
    )


class GeminiHierarchyLevel(BaseModel):
    name: str = ""
    children: list[str] = Field(
        default_factory=list
    )


class GeminiVisualSpec(BaseModel):
    center: str = ""

    components: list[str] = Field(
        default_factory=list
    )

    relationships: list[str] = Field(
        default_factory=list
    )

    nodes: list[str] = Field(
        default_factory=list
    )

    edges: list[str] = Field(
        default_factory=list
    )

    columns: list[str] = Field(
        default_factory=list
    )

    rows: list[GeminiTableRow] = Field(
        default_factory=list
    )

    root: str = ""

    levels: list[GeminiHierarchyLevel] = Field(
        default_factory=list
    )

    chart_type: str = ""

    x: list[str] = Field(
        default_factory=list
    )

    y: list[float] = Field(
        default_factory=list
    )

    x_label: str = ""

    y_label: str = ""

    examples: list[str] = Field(
        default_factory=list
    )

    events: list[str] = Field(
        default_factory=list
    )

    formula: str = ""

    concepts: list[str] = Field(
        default_factory=list
    )


class GeminiSlideResponse(BaseModel):
    title: str

    bullets: list[str] = Field(
        default_factory=list
    )

    summary: str = ""

    keywords: list[str] = Field(
        default_factory=list
    )

    content_type: str = "explanation"

    visual_type: str = "none"

    visual_reason: str = ""

    image_query: str = ""

    visual_spec: GeminiVisualSpec = Field(
        default_factory=GeminiVisualSpec
    )

    diagram: str = ""


class GeminiClient:

    def __init__(
        self,
        api_key: Optional[str] = GEMINI_API_KEY,
        model: str = GEMINI_MODEL,
    ) -> None:

        self.client = (
            genai.Client(
                api_key=api_key
            )
            if api_key
            else None
        )

        self.model = model

        self.calls = 0
        self.successes = 0
        self.failures = 0

        self.total_input_tokens = 0
        self.total_output_tokens = 0

        self.last_status = "NOT_USED"
        self.last_error = ""

    @staticmethod
    def build_prompt(
        topic: str,
        context: str,
    ) -> str:

        return (
            """
You are an expert educational presentation designer
and teacher's copilot.

Create ONE accurate educational PowerPoint slide
representing what the teacher is currently teaching.

TOPIC:
"""
            + topic
            + """

LECTURE CONTEXT:
"""
            + context
            + """

Reason internally before producing the result.

Tasks:
1. Identify the actual educational idea being taught.
2. Ignore conversational filler and irrelevant remarks.
3. Decide the content structure.
4. Decide whether a visual materially improves understanding.
5. Choose the simplest educational visual that teaches the idea.
6. Use only information supported by the lecture.
7. Never invent facts, examples, numbers, relationships, or chronology.

CONTENT TYPES:
definition
explanation
list
examples
comparison
classification
process
sequence
cause_effect
advantages_disadvantages
formula
data
application
summary
mixed

VISUAL TYPES:
none
image
diagram
flowchart
comparison_table
chart
timeline
hierarchy
example_grid
formula
concept_map

VISUAL RULES:
- Definition: concise definition; image only when useful.
- Comparison: use comparison_table.
- Process or sequence: use flowchart.
- Components or architecture: use diagram.
- Classification: use hierarchy.
- Numeric data: use chart when actual numeric values are present.
- Examples: use example_grid.
- Timeline: only for actual chronology.
- Formula: only for an actual equation.
- Relationships: use concept_map when relationships matter.
- Physical/scientific object: image when it materially helps.
- Prefer structured educational visuals over generic photographs.
- Use none when a visual does not improve understanding.

IMPORTANT:
Only populate fields relevant to the selected visual_type.

CONTENT RULES:
- Maximum 6 bullets.
- Keep bullets concise.
- Do not copy the transcript verbatim.
- Do not invent unsupported information.
- Do not repeat the title as a bullet.
- Preserve important distinctions from the teacher.
- Prefer the teacher's explanation over generic filler.

Generate the structured slide now.
""".strip()
        )

    @staticmethod
    def _classify_error(
        error: Exception,
    ) -> Exception:

        text = str(error).lower()

        if any(
            token in text
            for token in (
                "quota_exceeded",
                "quota exhausted",
                "daily quota",
                "resource_exhausted",
                "resource exhausted",
            )
        ):
            return GeminiQuotaError(
                str(error)
            )

        if any(
            token in text
            for token in (
                "503",
                "unavailable",
                "service_unavailable",
                "429",
                "rate_limit",
                "rate limit",
                "timeout",
                "deadline",
                "temporarily unavailable",
            )
        ):
            return GeminiTransientError(
                str(error)
            )

        return GeminiPermanentError(
            str(error)
        )

    @staticmethod
    def _visual_spec_to_dict(
        visual_spec: Any,
    ) -> Dict[str, Any]:

        if isinstance(
            visual_spec,
            GeminiVisualSpec,
        ):

            data = (
                visual_spec.model_dump()
            )

        elif isinstance(
            visual_spec,
            dict,
        ):

            data = dict(
                visual_spec
            )

        else:

            return {}

        cleaned: Dict[str, Any] = {}

        for key, value in data.items():

            if value in (
                "",
                None,
                [],
                {},
            ):
                continue

            if isinstance(
                value,
                list,
            ):

                cleaned[key] = [
                    (
                        item.model_dump()
                        if hasattr(
                            item,
                            "model_dump",
                        )
                        else item
                    )
                    for item in value
                ]

            else:

                cleaned[key] = value

        return cleaned

    @staticmethod
    def _normalize_result(
        result: Any,
    ) -> Dict[str, Any]:

        if isinstance(
            result,
            GeminiSlideResponse,
        ):

            result_dict = (
                result.model_dump()
            )

        elif isinstance(
            result,
            dict,
        ):

            result_dict = dict(
                result
            )

        else:

            raise GeminiPermanentError(
                "Gemini returned an invalid structured response."
            )

        bullets = result_dict.get(
            "bullets",
            [],
        )

        if not isinstance(
            bullets,
            list,
        ):
            bullets = []

        keywords = result_dict.get(
            "keywords",
            [],
        )

        if not isinstance(
            keywords,
            list,
        ):
            keywords = []

        visual_spec = (
            GeminiClient._visual_spec_to_dict(
                result_dict.get(
                    "visual_spec",
                    {},
                )
            )
        )

        return {
            "title": str(
                result_dict.get(
                    "title",
                    "",
                )
                or ""
            ).strip(),

            "bullets": [
                str(item).strip()
                for item in bullets[:6]
                if str(item).strip()
            ],

            "summary": str(
                result_dict.get(
                    "summary",
                    "",
                )
                or ""
            ).strip(),

            "keywords": [
                str(item).strip()
                for item in keywords
                if str(item).strip()
            ],

            "content_type": str(
                result_dict.get(
                    "content_type",
                    "explanation",
                )
                or "explanation"
            ).strip().lower(),

            "visual_type": str(
                result_dict.get(
                    "visual_type",
                    "none",
                )
                or "none"
            ).strip().lower(),

            "visual_reason": str(
                result_dict.get(
                    "visual_reason",
                    "",
                )
                or ""
            ).strip(),

            "image_query": str(
                result_dict.get(
                    "image_query",
                    "",
                )
                or ""
            ).strip(),

            "visual_spec": visual_spec,

            "diagram": str(
                result_dict.get(
                    "diagram",
                    "",
                )
                or ""
            ).strip(),
        }

    def generate_slide(
        self,
        topic: str,
        context: str,
    ) -> Dict[str, Any]:

        if self.client is None:

            raise GeminiPermanentError(
                "GEMINI_API_KEY is not configured."
            )

        prompt = self.build_prompt(
            topic,
            context,
        )

        self.calls += 1

        for attempt in range(2):

            try:

                config = (
                    types.GenerateContentConfig(
                        response_mime_type="application/json",
                        response_schema=GeminiSlideResponse,
                        max_output_tokens=max(
                            GEMINI_MAX_OUTPUT_TOKENS,
                            2000,
                        ),
                        thinking_config=(
                            types.ThinkingConfig(
                                thinking_level="minimal"
                            )
                        ),
                    )
                )

                response = (
                    self.client.models.generate_content(
                        model=self.model,
                        contents=prompt,
                        config=config,
                    )
                )

                usage = getattr(
                    response,
                    "usage_metadata",
                    None,
                )

                if usage is not None:

                    self.total_input_tokens += int(
                        getattr(
                            usage,
                            "prompt_token_count",
                            0,
                        )
                        or 0
                    )

                    self.total_output_tokens += int(
                        getattr(
                            usage,
                            "candidates_token_count",
                            0,
                        )
                        or 0
                    )

                parsed = getattr(
                    response,
                    "parsed",
                    None,
                )

                if parsed is not None:

                    normalized = (
                        self._normalize_result(
                            parsed
                        )
                    )

                else:

                    text = str(
                        response.text
                    ).strip()

                    if not text:

                        raise GeminiPermanentError(
                            "Gemini returned an empty response."
                        )

                    if text.startswith(
                        "```json"
                    ):

                        text = text[7:]

                    elif text.startswith(
                        "```"
                    ):

                        text = text[3:]

                    if text.endswith(
                        "```"
                    ):

                        text = text[:-3]

                    try:

                        parsed_json = json.loads(
                            text.strip()
                        )

                    except json.JSONDecodeError as error:

                        finish_reason = ""

                        try:

                            finish_reason = str(
                                response
                                .candidates[0]
                                .finish_reason
                            )
                        except Exception:
                            pass

                        raise GeminiPermanentError(
                            "Gemini returned malformed structured output. "
                            f"Finish reason: {finish_reason}. "
                            f"Raw output: {text[:500]}"
                        ) from error

                    normalized = (
                        self._normalize_result(
                            parsed_json
                        )
                    )

                self.successes += 1
                self.last_status = "SUCCESS"
                self.last_error = ""

                return normalized

            except Exception as error:

                classified = (
                    self._classify_error(
                        error
                    )
                )

                self.failures += 1
                self.last_error = str(
                    classified
                )

                if (
                    isinstance(
                        classified,
                        GeminiTransientError,
                    )
                    and attempt == 0
                ):

                    time.sleep(
                        0.45
                        + random.uniform(
                            0.0,
                            0.25,
                        )
                    )

                    continue

                self.last_status = (
                    "QUOTA_EXHAUSTED"
                    if isinstance(
                        classified,
                        GeminiQuotaError,
                    )
                    else "ERROR"
                )

                raise classified from error

        raise GeminiTransientError(
            "Gemini request failed after retry."
        )

    def status(
        self,
    ) -> Dict[str, Any]:

        return {
            "model":
                self.model,

            "calls":
                self.calls,

            "successes":
                self.successes,

            "failures":
                self.failures,

            "input_tokens":
                self.total_input_tokens,

            "output_tokens":
                self.total_output_tokens,

            "total_tokens":
                (
                    self.total_input_tokens
                    + self.total_output_tokens
                ),

            "status":
                self.last_status,

            "last_error":
                self.last_error,
        }