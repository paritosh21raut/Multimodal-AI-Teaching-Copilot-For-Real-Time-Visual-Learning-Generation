from __future__ import annotations

from datetime import datetime
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional

from pptx import Presentation
from pptx.slide import Slide

from app.slides.slide_renderer import slide_renderer


class PPTManager:
    """
    Manages a single PowerPoint presentation for one lecture.

    Responsibilities
    ----------------
    - Create one PPT per lecture
    - Create title slide
    - Create content slides
    - Update existing slides
    - Save automatically
    """

    def __init__(self) -> None:
        self._lock = Lock()

        self.presentation: Optional[Presentation] = None
        self.presentation_path: Optional[Path] = None

        self.output_directory = Path("outputs/presentations")
        self.output_directory.mkdir(parents=True, exist_ok=True)

        # Logical slide id -> PPT Slide
        self.slide_map: Dict[int, Slide] = {}

    # ============================================================
    # Presentation
    # ============================================================

    def create_new_presentation(
        self,
        lecture_title: str = "Lecture",
    ) -> Path:
        with self._lock:
            self.presentation = Presentation()
            self.slide_map.clear()

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            filename = (
                lecture_title.replace(" ", "_")
                + "_"
                + timestamp
                + ".pptx"
            )

            self.presentation_path = self.output_directory / filename

            self.save()

            print(f"[PPT] Created: {self.presentation_path}")

            return self.presentation_path

    # ============================================================
    # Title Slide
    # ============================================================

    def add_title_slide(
        self,
        title: str,
        subtitle: str = "",
    ) -> None:
        with self._lock:
            self._ensure_presentation()

            layout = self.presentation.slide_layouts[0]
            slide = self.presentation.slides.add_slide(layout)

            slide_renderer.render_title_slide(
                slide=slide,
                title=title,
                subtitle=subtitle,
            )

            self.save()

            print("[PPT] Title slide created")

    # ============================================================
    # Content Slide
    # ============================================================

    def create_or_update_slide(
        self,
        slide_id: int,
        title: str,
        bullets: List[str],
    ) -> None:
        
        print("[PPT] presentation =", self.presentation)
        print("[PPT] path =", self.presentation_path)

        with self._lock:
            self._ensure_presentation()

            if slide_id in self.slide_map:
                slide = self.slide_map[slide_id]

                self._update_slide(
                    slide,
                    title,
                    bullets,
                )

                print(f"[PPT] Updated Slide {slide_id}")

            else:
                layout = self.presentation.slide_layouts[1]
                slide = self.presentation.slides.add_slide(layout)

                self.slide_map[slide_id] = slide

                self._update_slide(
                    slide,
                    title,
                    bullets,
                )

                print(f"[PPT] Created Slide {slide_id}")

            self.save()

    # ============================================================
    # Internal
    # ============================================================

    def _update_slide(
        self,
        slide: Slide,
        title: str,
        bullets: List[str],
    ) -> None:
        """
        Update an existing slide using SlideRenderer.
        """

        slide_renderer.render_content_slide(
            slide=slide,
            title=title,
            bullets=bullets,
        )

    # ============================================================
    # Save
    # ============================================================

    def save(self) -> None:
        self._ensure_presentation()
        self.presentation.save(self.presentation_path)

    # ============================================================
    # Getters
    # ============================================================

    def get_presentation(self) -> Presentation:
        self._ensure_presentation()
        return self.presentation

    def get_path(self) -> Optional[Path]:
        return self.presentation_path

    def slide_exists(
        self,
        slide_id: int,
    ) -> bool:
        return slide_id in self.slide_map

    def total_slides(self) -> int:
        return len(self.slide_map)

    # ============================================================
    # Validation
    # ============================================================

    def _ensure_presentation(self) -> None:
        if self.presentation is None:
            raise RuntimeError(
                "Presentation has not been created."
            )


ppt_manager = PPTManager()