"""The materials the teacher made (F-010): data/materials/index.json + one file per PDF / PPTX.

Each entry knows which lectures it came from, its name (editable; the download name), whether students may download
it (PDFs, on by default), and — for summary / key-concepts slides — the slide specs, so they can be shown again.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Literal, Optional

from copilot.core.events import new_id

log = logging.getLogger(__name__)

Kind = Literal["summary", "concepts", "notes", "assignment", "pptx"]
EXT = {"notes": ".pdf", "assignment": ".pdf", "pptx": ".pptx"}
LABEL = {"summary": "Summary", "concepts": "Key concepts", "notes": "Notes", "assignment": "Assignment",
         "pptx": "Slides"}
_BAD_NAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
MAX_NAME = 120


def clean_name(name: str, kind: str) -> str:
    """A safe file name with the kind's extension (the teacher may type it with or without)."""
    ext = EXT.get(kind, "")
    name = _BAD_NAME.sub(" ", name or "").strip(" .")
    if ext and name.lower().endswith(ext):
        name = name[: -len(ext)].rstrip(" .")
    name = re.sub(r"\s+", " ", name)[:MAX_NAME].strip(" .")
    return (name or LABEL.get(kind, "Material")) + ext


def joined_title(titles: list[str]) -> str:
    titles = [t for t in dict.fromkeys(titles) if t]
    if not titles:
        return "Lecture"
    if len(titles) <= 2:
        return " + ".join(titles)
    return f"{titles[0]} + {len(titles) - 1} more"


def auto_name(kind: str, title: str, when: Optional[float] = None) -> str:
    """"Photosynthesis - Notes - 7 Oct 2026.pdf" (the same rule as /control's name field)."""
    d = datetime.fromtimestamp(when or time.time())
    return clean_name(f"{title} - {LABEL.get(kind, 'Material')} - {d.day} {d:%b %Y}", kind)


@dataclass
class Material:
    id: str
    kind: str
    name: str
    title: str                      # the lecture title(s) it was made from
    lectures: list[str]             # session ids
    created: float = field(default_factory=time.time)
    status: Literal["working", "ready", "failed"] = "working"
    detail: str = ""                # progress while working, the reason when it failed, a note when ready
    file: str = ""                  # stored file (data/materials/<id>.pdf)
    shared: bool = False            # students may download it from the shared link
    tokens: int = 0                 # LLM tokens it cost
    calls: int = 0
    count: int = 0                  # questions / slides
    options: dict[str, Any] = field(default_factory=dict)
    slides: list[dict[str, Any]] = field(default_factory=list)  # summary / key-concepts slide specs
    slide_ids: list[str] = field(default_factory=list)           # where they are in this run's deck

    def public(self) -> dict[str, Any]:
        """For /control (without the slide specs; no token counts in /control: user 2026-10-07, the terminal and the
        log keep them)."""
        d = asdict(self)
        for key in ("slides", "tokens", "calls"):
            d.pop(key)
        d["has_file"] = bool(self.file)
        return d


class MaterialStore:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._items: dict[str, Material] = {}
        self._lock = threading.Lock()
        self._load()

    @property
    def index(self) -> Path:
        return self.root / "index.json"

    def _load(self) -> None:
        try:
            data = json.loads(self.index.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (OSError, ValueError) as e:
            log.warning("materials index unreadable (%s): starting empty", e)
            return
        for raw in data.get("items", []):
            try:
                m = Material(**raw)
            except TypeError as e:
                log.warning("materials index entry skipped: %s", e)
                continue
            if m.status == "working":  # the app stopped while making it
                m.status, m.detail = "failed", "interrupted (the app was closed)"
            self._items[m.id] = m

    def save(self) -> None:
        with self._lock:
            self.root.mkdir(parents=True, exist_ok=True)
            tmp = self.index.with_suffix(".tmp")
            tmp.write_text(json.dumps({"items": [asdict(m) for m in self._items.values()]}, indent=1),
                           encoding="utf-8")
            tmp.replace(self.index)

    def items(self) -> list[Material]:
        return sorted(self._items.values(), key=lambda m: m.created, reverse=True)

    def get(self, material_id: str) -> Optional[Material]:
        return self._items.get(material_id)

    def new(self, kind: str, name: str, title: str, lectures: list[str], options: Optional[dict] = None) -> Material:
        m = Material(id=new_id(), kind=kind, name=clean_name(name, kind) if name else auto_name(kind, title),
                     title=title, lectures=lectures, options=dict(options or {}))
        self._items[m.id] = m
        self.save()
        return m

    def path(self, m: Material) -> Optional[Path]:
        return self.root / m.file if m.file else None

    def file_for(self, m: Material) -> Path:
        """Where to write this material's file (recorded on the entry)."""
        self.root.mkdir(parents=True, exist_ok=True)
        m.file = f"{m.id}{EXT[m.kind]}"
        return self.root / m.file

    def rename(self, material_id: str, name: str) -> bool:
        m = self._items.get(material_id)
        if m is None or not (name or "").strip():
            return False
        m.name = clean_name(name, m.kind)
        self.save()
        return True

    def share(self, material_id: str, on: bool) -> bool:
        m = self._items.get(material_id)
        if m is None or EXT.get(m.kind) != ".pdf":
            return False
        m.shared = bool(on)
        self.save()
        return True

    def remove(self, material_id: str) -> bool:
        m = self._items.pop(material_id, None)
        if m is None:
            return False
        p = self.path(m)
        if p is not None:
            p.unlink(missing_ok=True)
        self.save()
        return True

    def shared(self) -> list[Material]:
        return [m for m in self.items() if m.shared and m.status == "ready" and m.file]
