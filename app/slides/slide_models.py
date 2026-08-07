from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional


class SlideAction(str, Enum):
    CREATE = "create"
    UPDATE = "update"


@dataclass(slots=True)
class BulletPoint:
    text: str
    level: int = 0


@dataclass(slots=True)
class ImageAsset:
    query: str
    local_path: Optional[str] = None
    source: Optional[str] = None
    caption: Optional[str] = None


@dataclass(slots=True)
class DiagramAsset:
    title: str
    description: str
    diagram_type: str = "flowchart"


@dataclass(slots=True)
class SlideContent:
    title: str
    subtitle: Optional[str] = None

    bullets: List[BulletPoint] = field(default_factory=list)

    summary: Optional[str] = None

    notes: Optional[str] = None

    image: Optional[ImageAsset] = None

    diagram: Optional[DiagramAsset] = None

    keywords: List[str] = field(default_factory=list)

    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class SlideRequest:
    action: SlideAction

    slide_number: int

    topic: str

    content: SlideContent

    timestamp: datetime = field(default_factory=datetime.now)


@dataclass(slots=True)
class SlideResult:
    success: bool

    slide_number: int

    message: str = ""

    presentation_path: Optional[str] = None