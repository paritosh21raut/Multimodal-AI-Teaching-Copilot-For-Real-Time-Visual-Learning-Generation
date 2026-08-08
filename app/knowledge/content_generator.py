from __future__ import annotations

from app.ai.gemini_client import GeminiClient
from app.config import GEMINI_API_KEY
from app.slides.slide_models import (
    BulletPoint,
    SlideContent,
    ImageAsset,
    DiagramAsset,
)


class ContentGenerator:

    def __init__(self):

        self.ai = GeminiClient(GEMINI_API_KEY)

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

        result = self.ai.generate_slide(
            topic=topic,
            context=context,
        )

        bullets = [
            BulletPoint(text=item)
            for item in result["bullets"]
        ]

        print("=" * 60)
        print(result)
        print("=" * 60)

        return SlideContent(
            title=result["title"],
            bullets=bullets,
            summary=result.get("summary"),
            image_query=result.get("image_query"),
            keywords=result.get("keywords", []),
        )


content_generator = ContentGenerator()