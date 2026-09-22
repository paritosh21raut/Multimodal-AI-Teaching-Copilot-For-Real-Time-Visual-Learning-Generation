from __future__ import annotations

from typing import Any, Dict, List

from app.ai.groq_client import GroqClient
from app.ai.llm_client import LLMError
from app.config import (
    GROQ_API_KEY,
    LLM_BASE_URL,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_REASONING_EFFORT,
    LLM_TEMPERATURE,
    LLM_TIMEOUT,
)
from app.slides.slide_models import (
    BulletPoint,
    DiagramAsset,
    SlideContent,
)
from app.utils.logger import app_logger


SYSTEM_PROMPT = (
    "You are an expert educational presentation designer. "
    "Return exactly one JSON object that conforms to the provided schema. "
    "Do not invent information or numerical data."
)


USER_PROMPT_TEMPLATE = """Given a live lecture segment, decide what should appear on ONE educational PowerPoint slide.

TOPIC:
{topic}

LECTURE CONTEXT:
{context}

Understand what the teacher is explaining, then produce:
- an accurate slide title
- the key educational bullets (max 6, max ~14 words each, no repetition of the title)
- a short summary
- keywords
- a content_type from: definition, explanation, list, examples, comparison, classification, process, sequence, cause_effect, advantages_disadvantages, formula, data, application, summary, mixed
- a visual_type from: none, image, diagram, flowchart, comparison_table, chart, timeline, hierarchy, example_grid, formula, concept_map
- a short visual_reason
- an image_query when visual_type is "image" (otherwise "")
- a structured visual_spec matching the visual_type
- an optional diagram description string (otherwise "")

VISUAL DECISION RULES:
- definition -> definition layout when appropriate
- comparison -> comparison_table
- step-by-step -> flowchart or sequence
- components/architecture -> diagram
- classification -> hierarchy
- numerical data -> chart ONLY if real data is present; never invent values
- examples -> example_grid
- timeline -> timeline
- concept relationships -> concept_map or diagram
- physical/scientific concept -> image when a real image adds value
- otherwise -> none

VISUAL_SPEC SHAPES:
comparison_table: {{"columns": ["A","B"], "rows": [{{"label":"...","values":["...","..."]}}]}}
flowchart: {{"nodes": ["Step 1","Step 2"], "edges": [["Step 1","Step 2"]]}}
diagram: {{"center":"...","components":["..."],"relationships":[["A","B"]]}}
hierarchy: {{"root":"...","levels":[{{"name":"...","children":["...","..."]}}]}}
chart: {{"chart_type":"bar","x":["..."],"y":[1,2],"x_label":"...","y_label":"..."}}

Set unused visual_spec fields to null.
Do not include commentary. Do not include markdown.
"""


_ALLOWED_CONTENT_TYPES = {
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

_ALLOWED_VISUAL_TYPES = {
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

_DIAGRAM_VISUAL_TYPES = {
    "diagram",
    "flowchart",
    "hierarchy",
    "concept_map",
}


def _slide_schema() -> Dict[str, Any]:
    """
    Strict JSON schema for SlideContent.

    Groq strict-mode rules:
    - every property is required
    - additionalProperties: false on every object
    - optional semantic values are nullable rather than omitted
    """

    nullable_string = {"type": ["string", "null"]}

    string_array = {
        "type": "array",
        "items": {"type": "string"},
    }

    comparison_row = {
        "type": "object",
        "additionalProperties": False,
        "required": ["label", "values"],
        "properties": {
            "label": {"type": "string"},
            "values": string_array,
        },
    }

    hierarchy_level = {
        "type": "object",
        "additionalProperties": False,
        "required": ["name", "children"],
        "properties": {
            "name": {"type": "string"},
            "children": string_array,
        },
    }

    visual_spec = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "columns",
            "rows",
            "nodes",
            "edges",
            "center",
            "components",
            "relationships",
            "root",
            "levels",
            "examples",
            "events",
            "formula",
            "chart_type",
            "x",
            "y",
            "x_label",
            "y_label",
        ],
        "properties": {
            "columns": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "rows": {
                "type": ["array", "null"],
                "items": comparison_row,
            },
            "nodes": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "edges": {
                "type": ["array", "null"],
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "center": nullable_string,
            "components": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "relationships": {
                "type": ["array", "null"],
                "items": {
                    "type": "array",
                    "items": {"type": "string"},
                },
            },
            "root": nullable_string,
            "levels": {
                "type": ["array", "null"],
                "items": hierarchy_level,
            },
            "examples": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "events": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "formula": nullable_string,
            "chart_type": nullable_string,
            "x": {
                "type": ["array", "null"],
                "items": {"type": "string"},
            },
            "y": {
                "type": ["array", "null"],
                "items": {"type": "number"},
            },
            "x_label": nullable_string,
            "y_label": nullable_string,
        },
    }

    return {
        "type": "object",
        "additionalProperties": False,
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
        "properties": {
            "title": {"type": "string"},
            "bullets": string_array,
            "summary": nullable_string,
            "keywords": string_array,
            "content_type": {
                "type": "string",
                "enum": sorted(_ALLOWED_CONTENT_TYPES),
            },
            "visual_type": {
                "type": "string",
                "enum": sorted(_ALLOWED_VISUAL_TYPES),
            },
            "visual_reason": nullable_string,
            "image_query": nullable_string,
            "visual_spec": visual_spec,
            "diagram": nullable_string,
        },
    }


def _compact_visual_spec(raw: Any) -> Dict[str, Any]:
    """
    Strip null / empty entries so the renderer receives the same
    shape it received from the Gemini pipeline.
    """

    if not isinstance(raw, dict):
        return {}

    compact: Dict[str, Any] = {}

    for key, value in raw.items():

        if value is None:
            continue

        if isinstance(value, list) and not value:
            continue

        if isinstance(value, str) and not value.strip():
            continue

        compact[key] = value

    return compact


class ContentGenerator:

    def __init__(self, client: GroqClient | None = None):

        self.ai = client or GroqClient(
            api_key=GROQ_API_KEY,
            base_url=LLM_BASE_URL,
            model=LLM_MODEL,
            timeout=LLM_TIMEOUT,
            max_retries=LLM_MAX_RETRIES,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
            reasoning_effort=LLM_REASONING_EFFORT,
        )

    # ----------------------------------------------------------
    # PUBLIC
    # ----------------------------------------------------------

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

        prompt = USER_PROMPT_TEMPLATE.format(
            topic=topic,
            context=context,
        )

        try:

            raw = self.ai.generate_structured(
                prompt=prompt,
                system=SYSTEM_PROMPT,
                schema=_slide_schema(),
                schema_name="slide_content",
            )

        except LLMError as error:

            app_logger.error(
                f"[ContentGenerator] LLM failure: {error}"
            )

            raise

        result = self._validate(raw, topic)

        bullets = [
            BulletPoint(text=item)
            for item in result["bullets"]
        ]

        content_type = result["content_type"]
        visual_type = result["visual_type"]
        visual_spec = result["visual_spec"]
        visual_reason = result["visual_reason"]

        diagram = None

        diagram_text = result.get("diagram")

        if (
            isinstance(diagram_text, str)
            and diagram_text.strip()
            and visual_type in _DIAGRAM_VISUAL_TYPES
        ):

            diagram = DiagramAsset(
                title=result["title"],
                description=diagram_text,
                diagram_type=visual_type,
                data=visual_spec,
            )

        self._log_summary(
            content_type=content_type,
            visual_type=visual_type,
            visual_reason=visual_reason or "",
            visual_spec=visual_spec,
        )

        return SlideContent(
            title=result["title"],
            bullets=bullets,
            summary=result.get("summary"),
            image_query=result.get("image_query"),
            keywords=result["keywords"],
            diagram=diagram,
            content_type=content_type,
            visual_type=visual_type,
            visual_reason=visual_reason,
            visual_spec=visual_spec,
            metadata={
                "content_type": content_type,
                "visual_type": visual_type,
            },
        )

    # ----------------------------------------------------------
    # VALIDATION
    # ----------------------------------------------------------

    def _validate(
        self,
        raw: Dict[str, Any],
        topic: str,
    ) -> Dict[str, Any]:

        if not isinstance(raw, dict):
            raise LLMError(
                "LLM response was not a JSON object"
            )

        title = raw.get("title")
        if not isinstance(title, str) or not title.strip():
            title = topic

        bullets_raw = raw.get("bullets", [])
        if not isinstance(bullets_raw, list):
            bullets_raw = []

        bullets: List[str] = [
            item.strip()
            for item in bullets_raw
            if isinstance(item, str) and item.strip()
        ][:6]

        summary = raw.get("summary")
        if summary is not None and not isinstance(summary, str):
            summary = None

        keywords_raw = raw.get("keywords", [])
        if not isinstance(keywords_raw, list):
            keywords_raw = []

        keywords: List[str] = [
            item.strip()
            for item in keywords_raw
            if isinstance(item, str) and item.strip()
        ]

        content_type = raw.get("content_type", "explanation")
        if (
            not isinstance(content_type, str)
            or content_type not in _ALLOWED_CONTENT_TYPES
        ):
            content_type = "explanation"

        visual_type = raw.get("visual_type", "none")
        if (
            not isinstance(visual_type, str)
            or visual_type not in _ALLOWED_VISUAL_TYPES
        ):
            visual_type = "none"

        visual_spec = _compact_visual_spec(
            raw.get("visual_spec", {})
        )

        visual_reason = raw.get("visual_reason")
        if not isinstance(visual_reason, str):
            visual_reason = None

        image_query = raw.get("image_query")
        if not isinstance(image_query, str) or not image_query.strip():
            image_query = None

        if (
            visual_type not in ("none", "image")
            and not visual_spec
        ):
            app_logger.warning(
                "[ContentGenerator] visual_type="
                f"{visual_type} returned empty visual_spec"
            )

        return {
            "title": title,
            "bullets": bullets,
            "summary": summary,
            "keywords": keywords,
            "content_type": content_type,
            "visual_type": visual_type,
            "visual_reason": visual_reason,
            "visual_spec": visual_spec,
            "image_query": image_query,
            "diagram": raw.get("diagram"),
        }

    # ----------------------------------------------------------
    # LOGGING
    # ----------------------------------------------------------

    @staticmethod
    def _log_summary(
        *,
        content_type: str,
        visual_type: str,
        visual_reason: str,
        visual_spec: Dict[str, Any],
    ) -> None:

        app_logger.info(
            "[ContentGenerator] "
            f"content_type={content_type} "
            f"visual_type={visual_type} "
            f"visual_reason={visual_reason} "
            f"visual_spec_keys={list(visual_spec.keys())}"
        )


content_generator = ContentGenerator()