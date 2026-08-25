from __future__ import annotations

import json

from google import genai


class GeminiClient:

    def __init__(
        self,
        api_key: str,
    ):

        self.client = genai.Client(
            api_key=api_key
        )

        self.model = "gemini-3.6-flash"

    # ==========================================================
    # GENERATE SLIDE
    # ==========================================================

    def generate_slide(
        self,
        topic: str,
        context: str,
    ):

        prompt = f"""
You are an expert educational presentation designer.

You are given a live lecture segment and its current context.

Your job is to decide what should appear on ONE educational
PowerPoint slide.

TOPIC:
{topic}

LECTURE CONTEXT:
{context}

IMPORTANT:
Do NOT blindly turn the lecture into generic bullet points.

First understand what the teacher is actually explaining.

Determine:

1. The most accurate slide title.
2. The important educational information.
3. The content type.
4. Whether a visual is useful.
5. What kind of visual is best.

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

VISUAL DECISION RULES:

- Definition:
  Use a definition layout when appropriate.

- Comparison:
  Use comparison_table with two or more columns.

- Step-by-step process:
  Use flowchart or sequence.

- Components / architecture:
  Use diagram.

- Classification:
  Use hierarchy.

- Numerical data:
  Use chart ONLY when actual data is provided.
  Never invent values.

- Examples:
  Use example_grid or structured example list.

- Timeline:
  Use timeline.

- Relationships between concepts:
  Use concept_map or diagram.

- A physical/scientific object or concept:
  Use image when a real/generated educational image
  adds value.

- If a visual does not improve understanding:
  choose none.

CRITICAL:

Do not use a generic stock-photo concept when a diagram,
table, chart, or flowchart would teach the concept better.

Do not invent information.

Do not invent numerical data.

Do not repeat irrelevant speech.

The output must be valid JSON only.

Return exactly this structure:

{{
    "title": "...",

    "bullets": [
        "...",
        "..."
    ],

    "summary": "...",

    "keywords": [
        "..."
    ],

    "content_type": "...",

    "visual_type": "...",

    "visual_reason": "...",

    "image_query": "...",

    "visual_spec": {{}},

    "diagram": ""
}}

BULLET RULES:

- Maximum 6 bullets.
- Maximum approximately 14 words per bullet.
- Make every bullet educationally meaningful.
- Avoid repeating the title.
- Prefer concise statements.
- Do not turn comparisons/processes into ordinary bullets when
  a structured visual is more appropriate.

VISUAL_SPEC RULES:

For comparison_table:

{{
    "columns": ["Column A", "Column B"],
    "rows": [
        {{
            "label": "Feature",
            "values": ["...", "..."]
        }}
    ]
}}

For flowchart:

{{
    "nodes": [
        "Step 1",
        "Step 2",
        "Step 3"
    ],
    "edges": [
        ["Step 1", "Step 2"],
        ["Step 2", "Step 3"]
    ]
}}

For diagram:

{{
    "center": "...",
    "components": [
        "..."
    ],
    "relationships": [
        ["A", "B"]
    ]
}}

For hierarchy:

{{
    "root": "...",
    "levels": [
        {{
            "name": "...",
            "children": ["...", "..."]
        }}
    ]
}}

For chart:

{{
    "chart_type": "bar",
    "x": ["..."],
    "y": [1, 2, 3],
    "x_label": "...",
    "y_label": "..."
}}

Use empty objects when no structured specification is needed.

Return no markdown fences.
"""

        response = (
            self.client.models.generate_content(
                model=self.model,
                contents=prompt,
            )
        )

        text = (
            response.text
            .strip()
        )

        if text.startswith(
            "```json"
        ):

            text = text[7:]

        if text.startswith(
            "```"
        ):

            text = text[3:]

        if text.endswith(
            "```"
        ):

            text = text[:-3]

        return json.loads(
            text.strip()
        )