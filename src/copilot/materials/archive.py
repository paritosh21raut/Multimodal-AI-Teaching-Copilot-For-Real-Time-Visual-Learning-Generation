"""Past lectures (F-010): each session's final deck and transcript, rebuilt from its event log.

The deck at the end of a lecture = the last DeckState's slide order, each slide at its latest SlidePatch version.
Transcript lines keep their wall-clock time so the materials can tell which topic a line belongs to (the slide that
received content right after it). A rebuilt lecture is cached in `<session>/lecture.json`, keyed by the log's size
and modification time; sessions without a content slide (test starts, empty runs) are not listed.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

log = logging.getLogger(__name__)

CACHE_NAME = "lecture.json"
CACHE_VERSION = 1
MIN_LINES = 3  # fewer transcript lines than this: not a lecture (a test start, a mic check)


@dataclass
class LectureRecord:
    id: str
    title: str
    started: float                  # wall clock of the first event
    minutes: float                  # lecture time of the last transcript line
    theme: str = "light"
    simulated: bool = False         # every line came from the text simulator (a test run)
    slides: list[dict[str, Any]] = field(default_factory=list)      # SlideSpec dumps in deck order
    transcript: list[dict[str, Any]] = field(default_factory=list)  # {t, ts, text}
    patches: list[list[Any]] = field(default_factory=list)          # [ts, slide_id] of every content patch, in order

    @property
    def content_slides(self) -> list[dict[str, Any]]:
        return [s for s in self.slides if taught(s)]

    def summary(self) -> dict[str, Any]:
        """The row in the Lectures list."""
        return {"id": self.id, "title": self.title, "started": self.started, "minutes": round(self.minutes, 1),
                "slides": len(self.slides), "simulated": self.simulated,
                "date": datetime.fromtimestamp(self.started).strftime("%d %b %Y, %H:%M") if self.started else ""}


def topic_name(spec: dict[str, Any]) -> str:
    """The topic a slide belongs to, as the /control structure tree names it (title slide: its title)."""
    if spec.get("layout") == "title":
        return spec.get("title", "")
    return spec.get("subtitle") or spec.get("title", "")


def taught(spec: dict[str, Any]) -> bool:
    """A content slide of the lecture: not the title slide, not a summary / key-concepts slide made from it."""
    return spec.get("layout") != "title" and bool(spec.get("blocks")) and spec.get("origin", "lecture") == "lecture"


_NOT_TEXT = {"id", "type", "url", "image_id", "layout", "kind", "style", "version", "aspect", "source", "provisional",
             "added", "emph", "part", "op", "page_url", "licence", "author", "ghost", "latex", "origin", "alt"}
SEARCH_HITS = 3


def slide_words(spec: dict[str, Any]) -> str:
    """Every visible word of a slide (title, topic, facet, the blocks' text), lower case."""
    out: list[str] = []

    def walk(x: Any, key: str = "") -> None:
        if key in _NOT_TEXT:
            return
        if isinstance(x, str):
            out.append(x)
        elif isinstance(x, dict):
            for k, v in x.items():
                walk(v, k)
        elif isinstance(x, list):
            for v in x:
                walk(v, key)
    for k in ("title", "subtitle", "facet", "blocks"):
        walk(spec.get(k) or "", k)
    return " ".join(" ".join(out).lower().split())


def search(records: list["LectureRecord"], query: str) -> list[dict[str, Any]]:
    """Lectures whose title or slides hold every word of `query` (titles and slide content, never the transcript:
    user 2026-10-07), best first, with up to SEARCH_HITS matching slides each: [{id, hits: [{index, title}]}]."""
    words = [w for w in query.lower().split() if len(w) >= 2] or [w for w in query.lower().split()]
    if not words:
        return []
    found = []
    for rec in records:
        title = rec.title.lower()
        texts = [slide_words(s) for s in rec.slides]
        everything = title + " " + " ".join(texts)
        if not all(w in everything for w in words):
            continue
        hits = [{"index": i, "title": s.get("title", "")} for i, (s, t) in enumerate(zip(rec.slides, texts))
                if all(w in t for w in words)]
        in_title = all(w in title for w in words)
        found.append((not in_title, -len(hits), -rec.started, {"id": rec.id, "hits": hits[:SEARCH_HITS],
                                                                 "count": len(hits), "in_title": in_title}))
    return [f[-1] for f in sorted(found, key=lambda f: f[:3])]


def lecture_title(slides: list[dict[str, Any]]) -> str:
    """The title slide's title; otherwise the topic with the most slides (first seen wins a tie)."""
    for s in slides:
        if s.get("layout") == "title" and s.get("title"):
            return s["title"]
    counts: dict[str, int] = {}
    names: dict[str, str] = {}
    for s in filter(taught, slides):
        name = topic_name(s).strip()
        if name:
            counts[name.lower()] = counts.get(name.lower(), 0) + 1
            names.setdefault(name.lower(), name)
    if not counts:
        return "Untitled lecture"
    best = max(counts, key=lambda k: counts[k])  # max keeps the first of equal counts (dict order = first seen)
    return names[best]


def rebuild(db: Path, session_id: str) -> Optional[LectureRecord]:
    """The lecture in one session's event log, or None when it has no content slide or too little speech."""
    specs: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    transcript: list[dict[str, Any]] = []
    patches: list[list[Any]] = []
    theme = "light"
    started = 0.0
    sources: set[str] = set()
    conn = sqlite3.connect(f"file:{db.as_posix()}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT ts, type, payload FROM events WHERE type IN "
            "('SlidePatch', 'DeckState', 'TranscriptFinal', 'ThemeChanged', 'LifecycleChanged') ORDER BY seq")
        for ts, kind, payload in rows:
            started = started or ts
            data = json.loads(payload)
            if kind == "SlidePatch":
                old = specs.get(data["slide_id"])
                if old is None or data["version"] >= old.get("version", 0):
                    specs[data["slide_id"]] = data["spec"]
                if taught(data["spec"]):
                    patches.append([ts, data["slide_id"]])
                if data["slide_id"] not in order:
                    order.append(data["slide_id"])  # until a DeckState says the order
            elif kind == "DeckState":
                order = list(data.get("slide_ids") or [])
            elif kind == "TranscriptFinal":
                seg = data["segment"]
                sources.add(seg.get("source", "mic"))
                transcript.append({"t": seg.get("start", 0.0), "ts": ts, "text": seg.get("text", "")})
            elif kind == "ThemeChanged":
                theme = data.get("theme", theme)
    finally:
        conn.close()
    slides = [specs[i] for i in order if i in specs]
    if not any(map(taught, slides)) or len(transcript) < MIN_LINES:
        return None
    minutes = max((l["t"] for l in transcript), default=0.0) / 60
    return LectureRecord(id=session_id, title=lecture_title(slides), started=started, minutes=minutes, theme=theme,
                         simulated=sources == {"sim"}, slides=slides, transcript=transcript, patches=patches)


def _stamp(db: Path) -> list[int]:
    """Size + mtime of the log and its write-ahead file: changes whenever an event is written."""
    out: list[int] = []
    for p in (db, db.with_name(db.name + "-wal")):
        st = p.stat() if p.exists() else None
        out += [st.st_size, st.st_mtime_ns] if st else [0, 0]
    return out


class LectureArchive:
    """Past lectures under data/sessions. `hidden_file` lists lectures the teacher took off the list."""

    def __init__(self, sessions_dir: Path, hidden_file: Path, current_id: str = "") -> None:
        self.dir = sessions_dir
        self.hidden_file = hidden_file
        self.current_id = current_id
        self._mem: dict[str, tuple[list[int], Optional[LectureRecord]]] = {}
        self._lock = threading.Lock()

    def _hidden(self) -> set[str]:
        try:
            return set(json.loads(self.hidden_file.read_text(encoding="utf-8")).get("hidden", []))
        except (OSError, ValueError):
            return set()

    def hide(self, session_id: str) -> None:
        with self._lock:
            hidden = self._hidden() | {session_id}
            self.hidden_file.parent.mkdir(parents=True, exist_ok=True)
            self.hidden_file.write_text(json.dumps({"hidden": sorted(hidden)}, indent=1), encoding="utf-8")

    def load(self, session_id: str, cache: bool = True) -> Optional[LectureRecord]:
        """One lecture (cache=False: always from the log, e.g. the lecture still running)."""
        db = self.dir / session_id / "session.sqlite"
        if not db.is_file() or "/" in session_id or "\\" in session_id or session_id.startswith("."):
            return None
        stamp = _stamp(db)
        if cache:
            hit = self._mem.get(session_id)
            if hit and hit[0] == stamp:
                return hit[1]
            disk = self._read_cache(db.parent, stamp)
            if disk is not False:
                self._mem[session_id] = (stamp, disk)  # type: ignore[assignment]
                return disk  # type: ignore[return-value]
        try:
            record = rebuild(db, session_id)
        except (sqlite3.Error, ValueError, KeyError) as e:
            log.warning("lecture %s could not be read: %s", session_id, e)
            record = None
        self._mem[session_id] = (stamp, record)
        if cache:
            self._write_cache(db.parent, stamp, record)
        return record

    @staticmethod
    def _read_cache(folder: Path, stamp: list[int]):
        """The cached record (None = cached "not a lecture"); False when there is no valid cache."""
        try:
            data = json.loads((folder / CACHE_NAME).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return False
        if data.get("version") != CACHE_VERSION or data.get("stamp") != stamp:
            return False
        rec = data.get("record")
        return LectureRecord(**rec) if rec else None

    @staticmethod
    def _write_cache(folder: Path, stamp: list[int], record: Optional[LectureRecord]) -> None:
        try:
            (folder / CACHE_NAME).write_text(json.dumps(
                {"version": CACHE_VERSION, "stamp": stamp, "record": asdict(record) if record else None}),
                encoding="utf-8")
        except OSError as e:
            log.warning("lecture cache not written in %s: %s", folder, e)

    def lectures(self) -> list[LectureRecord]:
        """Past lectures, newest first (not the one running now, not the hidden ones)."""
        if not self.dir.is_dir():
            return []
        hidden = self._hidden()
        out = []
        for folder in self.dir.iterdir():
            if folder.name == self.current_id or folder.name in hidden or not folder.is_dir():
                continue
            rec = self.load(folder.name)
            if rec is not None:
                out.append(rec)
        return sorted(out, key=lambda r: r.started, reverse=True)

    def current(self) -> Optional[LectureRecord]:
        """The lecture running now (always read from its log), None before it has a content slide."""
        return self.load(self.current_id, cache=False) if self.current_id else None
