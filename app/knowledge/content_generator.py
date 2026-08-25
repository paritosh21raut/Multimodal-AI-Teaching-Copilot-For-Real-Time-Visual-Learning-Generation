from __future__ import annotations

from app.ai.gemini_client import (
    GeminiClient,
)

from app.config import (
    GEMINI_API_KEY,
)

from app.slides.slide_models import (
    BulletPoint,
    SlideContent,
    DiagramAsset,
)


class ContentGenerator:

    def __init__(self):

        self.ai = GeminiClient(
            GEMINI_API_KEY
        )

    def generate(
        self,
        topic: str,
        context: str,
    ) -> SlideContent:

        result = (
            self.ai.generate_slide(
                topic=topic,
                context=context,
            )
        )

        bullets = [
            BulletPoint(
                text=item
            )
            for item
            in result.get(
                "bullets",
                [],
            )
        ]

        content_type = (
            result.get(
                "content_type",
                "explanation",
            )
        )

        visual_type = (
            result.get(
                "visual_type",
                "none",
            )
        )

        visual_spec = (
            result.get(
                "visual_spec",
                {},
            )
        )

        visual_reason = (
            result.get(
                "visual_reason",
                "",
            )
        )

        diagram = None

        diagram_text = result.get(
            "diagram"
        )

        if (
            diagram_text
            and visual_type
            in (
                "diagram",
                "flowchart",
                "hierarchy",
                "concept_map",
            )
        ):

            diagram = DiagramAsset(
                title=result.get(
                    "title",
                    topic,
                ),
                description=diagram_text,
                diagram_type=visual_type,
                data=visual_spec,
            )

        print(
            "=" * 60
        )

        print(
            "[ContentGenerator]"
        )

        print(
            f"Content Type : {content_type}"
        )

        print(
            f"Visual Type  : {visual_type}"
        )

        print(
            f"Visual Reason: {visual_reason}"
        )

        print(
            f"Visual Spec  : {visual_spec}"
        )

        print(
            "=" * 60
        )

        return SlideContent(

            title=result.get(
                "title",
                topic,
            ),

            bullets=bullets,

            summary=result.get(
                "summary"
            ),

            image_query=result.get(
                "image_query"
            ),

            keywords=result.get(
                "keywords",
                [],
            ),

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


content_generator = ContentGenerator()