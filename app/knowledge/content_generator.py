from __future__ import annotations

from app.slides.slide_models import (
    BulletPoint,
    SlideContent,
)


class ContentGenerator:
    """
    Temporary content generator.

    Later this will call Gemini/OpenAI.
    """

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

        bullets = []

        sentences = [
            sentence.strip()
            for sentence in context.split(".")
            if sentence.strip()
        ]

        for sentence in sentences[:5]:
            bullets.append(
                BulletPoint(
                    text=sentence
                )
            )

        if not bullets:
            bullets.append(
                BulletPoint(
                    text="No content available."
                )
            )

        return SlideContent(
            title=topic,
            bullets=bullets,
        )


content_generator = ContentGenerator()