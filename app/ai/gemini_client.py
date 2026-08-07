from __future__ import annotations

import json

from google import genai


class GeminiClient:

    def __init__(self, api_key: str):

        self.client = genai.Client(api_key=api_key)

        self.model = "gemini-3.6-flash"

    def generate_slide(
        self,
        topic: str,
        context: str,
    ):

        prompt = f"""
    You are an expert university professor.

    Create ONE PowerPoint slide.

    Topic:
    {topic}

    Lecture:
    {context}

    Rules:
    - Max 6 bullets
    - Max 12 words per bullet
    - Don't copy transcript
    - Return ONLY valid JSON.

    Example:

    {{
    "title":"...",
    "bullets":[
    "...",
    "...",
    "..."
    ],
    "summary":"...",
    "keywords":["..."],
    "image_query":"...",
    "diagram":"..."
    }}
    """

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        text = response.text.strip()

        if text.startswith("```json"):
            text = text[7:]

        if text.startswith("```"):
            text = text[3:]

        if text.endswith("```"):
            text = text[:-3]

        return json.loads(text.strip())