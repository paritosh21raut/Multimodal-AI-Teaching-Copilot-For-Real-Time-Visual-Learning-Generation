from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from threading import Lock, RLock
from typing import List, Optional


@dataclass
class SlideState:
    slide_number: int
    topic: str
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def touch(self) -> None:
        self.updated_at = datetime.now()


class LectureState:
    """
    Thread-safe singleton state manager for a live lecture.

    This class is the single source of truth for:

    - Current lecture
    - Current topic
    - Current slide
    - PPT filename
    - Slide history

    It intentionally contains NO AI logic and NO PowerPoint logic.
    """

    _instance: Optional["LectureState"] = None
    _instance_lock = Lock()

    def __new__(cls) -> "LectureState":
        with cls._instance_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return

        self._lock = RLock()

        self.reset()

        self._initialized = True

    # ------------------------------------------------------------------ #
    # Session Management
    # ------------------------------------------------------------------ #

    def reset(self) -> None:
        with self._lock:
            self.lecture_title: str = ""
            self.start_time: Optional[datetime] = None

            self.output_directory: Path = Path("outputs/presentations")
            self.output_directory.mkdir(parents=True, exist_ok=True)

            self.presentation_path: Optional[Path] = None

            self.current_topic: Optional[str] = None
            self.current_topic_embedding = None

            self.current_slide_number: int = 0

            self.slides: List[SlideState] = []

    def start_new_lecture(self, lecture_title: Optional[str] = None) -> Path:
        with self._lock:

            self.reset()

            self.start_time = datetime.now()

            if lecture_title is None:
                lecture_title = "Today's Lecture"

            self.lecture_title = lecture_title

            filename = (
                lecture_title.replace(" ", "_")
                + "_"
                + self.start_time.strftime("%Y%m%d_%H%M%S")
                + ".pptx"
            )

            self.presentation_path = self.output_directory / filename

            return self.presentation_path

    # ------------------------------------------------------------------ #
    # Slide Management
    # ------------------------------------------------------------------ #

    def create_slide(self, topic: str) -> SlideState:
        with self._lock:

            self.current_slide_number += 1

            slide = SlideState(
                slide_number=self.current_slide_number,
                topic=topic,
            )

            self.slides.append(slide)

            self.current_topic = topic

            return slide

    def update_current_slide(self) -> None:
        with self._lock:

            if not self.slides:
                return

            self.slides[-1].touch()

    # ------------------------------------------------------------------ #
    # Topic Management
    # ------------------------------------------------------------------ #

    def set_current_topic(
        self,
        topic: str,
        embedding=None,
    ) -> None:

        with self._lock:
            self.current_topic = topic
            self.current_topic_embedding = embedding

    # ------------------------------------------------------------------ #
    # Getters
    # ------------------------------------------------------------------ #

    def has_started(self) -> bool:
        with self._lock:
            return self.start_time is not None

    def has_slides(self) -> bool:
        with self._lock:
            return len(self.slides) > 0

    def slide_count(self) -> int:
        with self._lock:
            return len(self.slides)

    def get_current_slide(self) -> Optional[SlideState]:
        with self._lock:

            if not self.slides:
                return None

            return self.slides[-1]

    def get_current_topic(self) -> Optional[str]:
        with self._lock:
            return self.current_topic

    def get_current_embedding(self):
        with self._lock:
            return self.current_topic_embedding

    def get_presentation_path(self) -> Optional[Path]:
        with self._lock:
            return self.presentation_path

    def get_all_slides(self) -> List[SlideState]:
        with self._lock:
            return list(self.slides)

    # ------------------------------------------------------------------ #
    # Debug
    # ------------------------------------------------------------------ #

    def __repr__(self) -> str:
        return (
            f"LectureState("
            f"title={self.lecture_title}, "
            f"slides={len(self.slides)}, "
            f"current_slide={self.current_slide_number}, "
            f"current_topic={self.current_topic})"
        )


lecture_state = LectureState()