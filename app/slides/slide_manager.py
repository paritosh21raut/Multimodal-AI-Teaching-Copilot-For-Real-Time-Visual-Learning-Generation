from __future__ import annotations

from app.ppt.ppt_manager import ppt_manager
from app.slides.slide_models import (
    SlideAction,
    SlideContent,
    SlideRequest,
    SlideResult,
)
from app.images.image_manager import image_manager

class SlideManager:
    """
    Handles slide creation and updates.

    Receives SlideContent from the LecturePipeline and
    forwards it to PPTManager.
    """

    def create_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        print("=" * 60)
        print("IMAGE QUERY:")
        print(content.image_query)
        print("=" * 60)

        image_path = image_manager.get_image(
            content.image_query
        )

        print("IMAGE PATH:", image_path)

        request = SlideRequest(
            action=SlideAction.CREATE,
            slide_number=slide.slide_number,
            topic=slide.topic,
            content=content,
        )

        return self.process_request(
            request,
            image_path=image_path,
        )

    def update_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        image_path = image_manager.get_image(
            content.image_query
        )

        print("IMAGE PATH:", image_path)

        request = SlideRequest(
        action=SlideAction.UPDATE,
        slide_number=slide.slide_number,
        topic=slide.topic,
        content=content,
    )

        return self.process_request(
            request,
            image_path=image_path,
        )

    def process_request(
    self,
    request: SlideRequest,
    image_path: str | None = None,
    ) -> SlideResult:

        try:

            print(request.content.title)

            print(request.content.bullets)

            print([b.text for b in request.content.bullets])

            ppt_manager.create_or_update_slide(
            slide_id=request.slide_number,
            title=request.content.title,
            bullets=[
                bullet.text
                for bullet in request.content.bullets
            ],
            image_path=image_path,
        )

            return SlideResult(
                success=True,
                slide_number=request.slide_number,
                presentation_path=str(
                    ppt_manager.get_path()
                ),
            )

        except Exception as error:

            return SlideResult(
                success=False,
                slide_number=request.slide_number,
                message=str(error),
            )


slide_manager = SlideManager()