from __future__ import annotations

from app.ppt.ppt_manager import ppt_manager

from app.slides.slide_models import (
    SlideAction,
    SlideContent,
    SlideRequest,
    SlideResult,
)

from app.images.image_manager import image_manager

from app.dashboard.dashboard_state import (
    dashboard_state,
)


class SlideManager:
    """
    Handles slide creation and updates.

    Receives SlideContent from the LecturePipeline,
    updates the live dashboard, and forwards the
    content to PPTManager.
    """

    # ========================================================
    # CREATE SLIDE
    # ========================================================

    def create_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        print("=" * 60)

        print("IMAGE QUERY:")
        print(content.image_query)

        print("=" * 60)

        # ----------------------------------------------------
        # Generate / retrieve image
        # ----------------------------------------------------

        image_path = image_manager.get_image(
            content.image_query
        )

        print(
            "IMAGE PATH:",
            image_path,
        )

        # ----------------------------------------------------
        # Update dashboard image
        # ----------------------------------------------------

        dashboard_state.update_image(
            image_path or ""
        )

        # ----------------------------------------------------
        # Update dashboard slide content
        # ----------------------------------------------------

        bullets = [
            bullet.text
            for bullet in content.bullets
        ]

        dashboard_state.update_slide(
            title=content.title,
            bullets=bullets,
            slide_number=slide.slide_number,
        )

        # ----------------------------------------------------
        # Create PPT request
        # ----------------------------------------------------

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

    # ========================================================
    # UPDATE SLIDE
    # ========================================================

    def update_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        # ----------------------------------------------------
        # Generate / retrieve image
        # ----------------------------------------------------

        image_path = image_manager.get_image(
            content.image_query
        )

        print(
            "IMAGE PATH:",
            image_path,
        )

        # ----------------------------------------------------
        # Update dashboard image
        # ----------------------------------------------------

        dashboard_state.update_image(
            image_path or ""
        )

        # ----------------------------------------------------
        # Update dashboard content
        # ----------------------------------------------------

        bullets = [
            bullet.text
            for bullet in content.bullets
        ]

        dashboard_state.update_slide(
            title=content.title,
            bullets=bullets,
            slide_number=slide.slide_number,
        )

        # ----------------------------------------------------
        # Update PPT request
        # ----------------------------------------------------

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

    # ========================================================
    # PROCESS REQUEST
    # ========================================================

    def process_request(
        self,
        request: SlideRequest,
        image_path: str | None = None,
    ) -> SlideResult:

        try:

            print(
                request.content.title
            )

            print(
                request.content.bullets
            )

            bullets = [
                bullet.text
                for bullet in request.content.bullets
            ]

            print(
                bullets
            )

            # ------------------------------------------------
            # Update PPT
            # ------------------------------------------------

            ppt_manager.create_or_update_slide(

                slide_id=request.slide_number,

                title=request.content.title,

                bullets=bullets,

                image_path=image_path,
            )

            # ------------------------------------------------
            # Update dashboard PPT information
            # ------------------------------------------------

            ppt_path = str(
                ppt_manager.get_path()
            )

            dashboard_state.update_ppt(

                ppt_path=ppt_path,

                slide_count=request.slide_number,
            )

            # ------------------------------------------------
            # Pipeline status
            # ------------------------------------------------

            dashboard_state.set_pipeline(
                stage="Slide Generated",
                status="Ready",
            )

            return SlideResult(

                success=True,

                slide_number=request.slide_number,

                presentation_path=ppt_path,
            )

        except Exception as error:

            dashboard_state.set_error(
                str(error)
            )

            dashboard_state.set_pipeline(
                stage="Error",
                status="Failed",
            )

            return SlideResult(

                success=False,

                slide_number=request.slide_number,

                message=str(error),
            )


# ============================================================
# GLOBAL INSTANCE
# ============================================================

slide_manager = SlideManager()