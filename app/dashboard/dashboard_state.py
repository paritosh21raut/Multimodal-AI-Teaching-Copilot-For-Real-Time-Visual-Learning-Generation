from __future__ import annotations

from dataclasses import dataclass, field
from threading import Lock


@dataclass
class DashboardState:

    title: str = ""

    transcript: str = ""

    image: str = ""

    topic: str = ""

    bullets: list[str] = field(default_factory=list)

    ppt_path: str = ""

    lock: Lock = field(default_factory=Lock)


dashboard_state = DashboardState()