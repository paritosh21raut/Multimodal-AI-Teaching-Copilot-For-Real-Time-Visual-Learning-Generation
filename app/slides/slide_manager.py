from __future__ import annotations

from app.ppt.ppt_manager import ppt_manager
from app.slides.slide_models import (
    SlideAction,
    SlideContent,
    SlideRequest,
    SlideResult,
)


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

        request = SlideRequest(
        action=SlideAction.CREATE,
        slide_number=slide.slide_number,
        topic=slide.topic,
        content=content,
    )

        return self.process_request(request)

    def update_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        request = SlideRequest(
        action=SlideAction.UPDATE,
        slide_number=slide.slide_number,
        topic=slide.topic,
        content=content,
    )

        return self.process_request(request)

    def process_request(
        self,
        request: SlideRequest,
    ) -> SlideResult:

        try:

            ppt_manager.create_or_update_slide(
                slide_id=request.slide_number,
                title=request.content.title,
                bullets=[
                    bullet.text
                    for bullet in request.content.bullets
                ],
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