"""Chapters of lectures (F-010b §2): the teacher groups past lectures in chapters and starts a lecture in one.

    data/chapters.json  {"chapters": [{id, name}], "lectures": {session_id: chapter_id}, "last": chapter_id}

The position in `chapters` is the chapter's number ("Chapter 3 · Cell biology"): only the name is stored, so moving a
chapter renumbers it. A lecture in no chapter is Unsorted. Deleting a chapter never deletes a lecture.
"""
from __future__ import annotations

import json
import logging
import secrets
import threading
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

NAME_MAX = 80


def clean(name: str) -> str:
    return " ".join(str(name or "").split())[:NAME_MAX]


def label(number: int, name: str) -> str:
    return f"Chapter {number} · {name}" if name else f"Chapter {number}"


class ChapterBook:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._data = self._read()

    def _read(self) -> dict[str, Any]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {"chapters": [], "lectures": {}, "last": ""}
        except (OSError, ValueError) as e:
            log.warning("chapters file unreadable (%s): starting without chapters", e)
            return {"chapters": [], "lectures": {}, "last": ""}
        chapters = [{"id": str(c["id"]), "name": clean(c.get("name", ""))}
                    for c in data.get("chapters") or [] if isinstance(c, dict) and c.get("id")]
        ids = {c["id"] for c in chapters}
        lectures = {str(k): str(v) for k, v in (data.get("lectures") or {}).items() if v in ids}
        last = data.get("last") if data.get("last") in ids else ""
        return {"chapters": chapters, "lectures": lectures, "last": last}

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=1), encoding="utf-8")
        tmp.replace(self.path)

    # ---- reading ------------------------------------------------------------------------------------------
    def chapters(self) -> list[dict[str, Any]]:
        """[{id, name, number, label}] in order."""
        return [{**c, "number": n, "label": label(n, c["name"])}
                for n, c in enumerate(self._data["chapters"], start=1)]

    def chapter_of(self, lecture_id: str) -> str:
        return self._data["lectures"].get(lecture_id, "")

    def lectures_in(self, chapter_id: str) -> list[str]:
        return [lid for lid, cid in self._data["lectures"].items() if cid == chapter_id]

    def get(self, chapter_id: str) -> Optional[dict[str, Any]]:
        return next((c for c in self.chapters() if c["id"] == chapter_id), None)

    @property
    def last(self) -> str:
        return self._data["last"]

    # ---- changes (each returns True when something changed) ------------------------------------------------
    def create(self, name: str) -> str:
        with self._lock:
            cid = secrets.token_hex(6)
            self._data["chapters"].append({"id": cid, "name": clean(name)})
            self._save()
        return cid

    def rename(self, chapter_id: str, name: str) -> bool:
        with self._lock:
            c = next((c for c in self._data["chapters"] if c["id"] == chapter_id), None)
            if c is None or clean(name) == c["name"]:
                return False
            c["name"] = clean(name)
            self._save()
        return True

    def move(self, chapter_id: str, index: int) -> bool:
        with self._lock:
            chapters = self._data["chapters"]
            at = next((i for i, c in enumerate(chapters) if c["id"] == chapter_id), None)
            index = max(0, min(len(chapters) - 1, int(index)))
            if at is None or at == index:
                return False
            chapters.insert(index, chapters.pop(at))
            self._save()
        return True

    def delete(self, chapter_id: str) -> bool:
        """The chapter goes; its lectures become Unsorted."""
        with self._lock:
            before = len(self._data["chapters"])
            self._data["chapters"] = [c for c in self._data["chapters"] if c["id"] != chapter_id]
            if len(self._data["chapters"]) == before:
                return False
            self._data["lectures"] = {k: v for k, v in self._data["lectures"].items() if v != chapter_id}
            if self._data["last"] == chapter_id:
                self._data["last"] = ""
            self._save()
        return True

    def assign(self, lecture_id: str, chapter_id: str, remember: bool = False) -> bool:
        """Put a lecture in a chapter ("" = Unsorted). remember: the start card preselects it next time."""
        with self._lock:
            if chapter_id and not any(c["id"] == chapter_id for c in self._data["chapters"]):
                return False
            changed = self._data["lectures"].get(lecture_id, "") != chapter_id
            if chapter_id:
                self._data["lectures"][lecture_id] = chapter_id
            else:
                self._data["lectures"].pop(lecture_id, None)
            if remember and chapter_id and self._data["last"] != chapter_id:
                self._data["last"] = chapter_id
                changed = True
            if changed:
                self._save()
        return changed
