from __future__ import annotations

from app.ppt.ppt_manager import (
    ppt_manager,
)

from app.slides.slide_models import (
    SlideAction,
    SlideContent,
    SlideRequest,
    SlideResult,
)

from app.images.image_manager import (
    image_manager,
)

from app.dashboard.dashboard_state import (
    dashboard_state,
)


class SlideManager:
    """
    Converts SlideContent into dashboard and PPT output.

    Visual routing:

    image
        -> image manager

    diagram / flowchart / comparison_table /
    chart / hierarchy / example_grid / formula /
    concept_map
        -> native PPT renderer
    """

    # ============================================================
    # IMAGE DECISION
    # ============================================================

    @staticmethod
    def _needs_external_image(
        content: SlideContent,
    ) -> bool:

        return (
            content.visual_type
            == "image"
        )

    # ============================================================
    # CREATE
    # ============================================================

    def create_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        image_path = None

        print(
            "=" * 60
        )

        print(
            "VISUAL TYPE:",
            content.visual_type,
        )

        print(
            "VISUAL REASON:",
            content.visual_reason,
        )

        # --------------------------------------------------------
        # Fetch image ONLY when the planner selected "image".
        # --------------------------------------------------------

        if (
            self._needs_external_image(
                content
            )
            and content.image_query
        ):

            print(
                "IMAGE QUERY:"
            )

            print(
                content.image_query
            )

            image_path = (
                image_manager.get_image(
                    content.image_query
                )
            )

        print(
            "IMAGE PATH:",
            image_path,
        )

        print(
            "=" * 60
        )

        dashboard_state.update_image(
            image_path or ""
        )

        bullets = [
            bullet.text
            for bullet
            in content.bullets
        ]

        dashboard_state.update_slide(
            title=content.title,
            bullets=bullets,
            slide_number=slide.slide_number,
        )

        request = SlideRequest(
            action=SlideAction.CREATE,
            slide_number=slide.slide_number,
            topic=slide.topic,
            content=content,
        )

        return self.process_request(
            request=request,
            image_path=image_path,
        )

    # ============================================================
    # UPDATE
    # ============================================================

    def update_slide(
        self,
        slide,
        content: SlideContent,
    ) -> SlideResult:

        image_path = None

        # --------------------------------------------------------
        # Fetch image ONLY when required.
        # --------------------------------------------------------

        if (
            self._needs_external_image(
                content
            )
            and content.image_query
        ):

            print(
                "IMAGE QUERY:",
                content.image_query,
            )

            image_path = (
                image_manager.get_image(
                    content.image_query
                )
            )

        print(
            "IMAGE PATH:",
            image_path,
        )

        dashboard_state.update_image(
            image_path or ""
        )

        bullets = [
            bullet.text
            for bullet
            in content.bullets
        ]

        dashboard_state.update_slide(
            title=content.title,
            bullets=bullets,
            slide_number=slide.slide_number,
        )

        request = SlideRequest(
            action=SlideAction.UPDATE,
            slide_number=slide.slide_number,
            topic=slide.topic,
            content=content,
        )

        return self.process_request(
            request=request,
            image_path=image_path,
        )

    # ============================================================
    # PROCESS REQUEST
    # ============================================================

    def process_request(
        self,
        request: SlideRequest,
        image_path: str | None = None,
    ) -> SlideResult:

        try:

            content = request.content

            bullets = [
                bullet.text
                for bullet
                in content.bullets
            ]

            print(
                "[SlideManager] Title:",
                content.title,
            )

            print(
                "[SlideManager] Visual:",
                content.visual_type,
            )

            print(
                "[SlideManager] Content:",
                content.content_type,
            )

            # ----------------------------------------------------
            # PPT
            # ----------------------------------------------------

            ppt_manager.create_or_update_slide(
                slide_id=request.slide_number,
                title=content.title,
                bullets=bullets,
                image_path=image_path,
                visual_type=content.visual_type,
                visual_spec=content.visual_spec,
                content_type=content.content_type,
                visual_reason=(
                    content.visual_reason
                    or ""
                ),
            )

            # ----------------------------------------------------
            # Dashboard
            # ----------------------------------------------------

            ppt_path = str(
                ppt_manager.get_path()
            )

            dashboard_state.update_ppt(
                ppt_path=ppt_path,
                slide_count=request.slide_number,
            )

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


slide_manager = SlideManager()