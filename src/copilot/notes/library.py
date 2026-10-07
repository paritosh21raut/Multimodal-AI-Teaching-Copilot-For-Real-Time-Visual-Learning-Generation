"""The teacher's own notes (PDF) on the laptop (F-009 §2): stored under data/notes, rendered page by page for /control.

Never sent to the projector, the students or the LLM. Each file is stored once by content hash:
    data/notes/index.json            [{id, name, pages, has_text, added}], newest first; "open": the last one read
    data/notes/<id>.pdf              the file
    data/notes/<id>.json             page texts (for following the lecture)
    data/notes/<id>/p<n>-w<w>.png    rendered pages (cache)
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MAX_PAGES = 600
RENDER_WIDTHS = (480, 720, 960, 1280, 1920)  # the client asks for one of these (nearest above): a small cache;
# 1920: a page on the projector (F-010b)
_ID = re.compile(r"[0-9a-f]{16}")
MIN_TEXT_WORDS = 15  # fewer words in the whole file: a scan / pictures only, nothing to follow the lecture with


class BadNotes(ValueError):
    """Not a PDF we can open (message is for the teacher)."""


@dataclass
class NoteDoc:
    id: str
    name: str
    pages: int
    has_text: bool
    added: float = 0.0
    kind: str = "pdf"   # what the teacher added (F-010b): pdf | word | slides | text | image | web
    source: str = ""    # web: the link it was saved from


class NotesLibrary:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._lock = threading.Lock()  # pdfium is not thread-safe; renders run in worker threads

    # ---- index -------------------------------------------------------------------------------
    def _index(self) -> dict:
        f = self.root / "index.json"
        if not f.exists():
            return {"docs": [], "open": ""}
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            return {"docs": list(data.get("docs") or []), "open": str(data.get("open") or "")}
        except (OSError, ValueError) as e:
            log.warning("notes index unreadable (%s): starting empty", e)
            return {"docs": [], "open": ""}

    def _save_index(self, index: dict) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        tmp = self.root / "index.json.tmp"
        tmp.write_text(json.dumps(index, indent=1), encoding="utf-8")
        tmp.replace(self.root / "index.json")

    def docs(self) -> list[NoteDoc]:
        return [NoteDoc(**d) for d in self._index()["docs"] if (self.root / f"{d['id']}.pdf").is_file()]

    def get(self, doc_id: str) -> Optional[NoteDoc]:
        return next((d for d in self.docs() if d.id == doc_id), None)

    @property
    def last_open(self) -> str:
        return self._index()["open"]

    def set_open(self, doc_id: str) -> None:
        index = self._index()
        index["open"] = doc_id
        self._save_index(index)

    # ---- add / remove ------------------------------------------------------------------------
    def add(self, data: bytes, name: str, kind: str = "pdf", source: str = "") -> NoteDoc:
        """`data` is a PDF (other files are converted first: notes/convert.py); `name` what the teacher sees."""
        if not data.startswith(b"%PDF"):
            raise BadNotes("this is not a PDF file")
        doc_id = hashlib.sha256(data).hexdigest()[:16]
        known = self.get(doc_id)
        if known is not None:
            return known
        texts = self._extract(data)  # raises BadNotes
        self.root.mkdir(parents=True, exist_ok=True)
        (self.root / f"{doc_id}.pdf").write_bytes(data)
        (self.root / f"{doc_id}.json").write_text(json.dumps(texts), encoding="utf-8")
        name = " ".join((name if kind == "web" else Path(name or "notes.pdf").name).split())[:120] or "notes.pdf"
        doc = NoteDoc(doc_id, name, len(texts), sum(len(t.split()) for t in texts) >= MIN_TEXT_WORDS, time.time(),
                      kind, source)
        index = self._index()
        index["docs"] = [asdict(doc)] + [d for d in index["docs"] if d.get("id") != doc_id]
        self._save_index(index)
        log.info("notes added %r -> %s (%d pages, text: %s)", doc.name, doc_id, doc.pages, doc.has_text)
        return doc

    def remove(self, doc_id: str) -> bool:
        if not _ID.fullmatch(doc_id):
            return False
        index = self._index()
        before = len(index["docs"])
        index["docs"] = [d for d in index["docs"] if d.get("id") != doc_id]
        if index["open"] == doc_id:
            index["open"] = ""
        self._save_index(index)
        for f in [self.root / f"{doc_id}.pdf", self.root / f"{doc_id}.json", *(self.root / doc_id).glob("*.png")]:
            f.unlink(missing_ok=True)
        if (self.root / doc_id).is_dir():
            (self.root / doc_id).rmdir()
        return len(index["docs"]) < before

    # ---- pages -------------------------------------------------------------------------------
    def page_texts(self, doc_id: str) -> list[str]:
        f = self.root / f"{doc_id}.json"
        if not _ID.fullmatch(doc_id) or not f.is_file():
            return []
        return list(json.loads(f.read_text(encoding="utf-8")))

    def render(self, doc_id: str, page: int, width: int) -> Optional[Path]:
        """The page (1-based) as a PNG about `width` px wide (rounded up to a cached size); None if there is none."""
        doc = self.get(doc_id) if _ID.fullmatch(doc_id) else None
        if doc is None or not 1 <= page <= doc.pages:
            return None
        w = next((x for x in RENDER_WIDTHS if x >= width), RENDER_WIDTHS[-1])
        out = self.root / doc_id / f"p{page}-w{w}.png"
        if out.is_file():
            return out
        import pypdfium2 as pdfium

        with self._lock:
            pdf = pdfium.PdfDocument(str(self.root / f"{doc_id}.pdf"))
            try:
                p = pdf[page - 1]
                image = p.render(scale=w / max(1.0, p.get_width()), draw_annots=True).to_pil()
                p.close()
            finally:
                pdf.close()
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(".tmp")
        image.save(tmp, format="PNG", optimize=True)
        tmp.replace(out)
        return out

    def _extract(self, data: bytes) -> list[str]:
        import pypdfium2 as pdfium

        with self._lock:
            try:
                pdf = pdfium.PdfDocument(data)
            except pdfium.PdfiumError as e:
                raise BadNotes(f"the PDF could not be opened ({e})") from e
            try:
                n = len(pdf)
                if n == 0:
                    raise BadNotes("the PDF has no pages")
                if n > MAX_PAGES:
                    raise BadNotes(f"the PDF has {n} pages (at most {MAX_PAGES})")
                texts = []
                for i in range(n):
                    page = pdf[i]
                    tp = page.get_textpage()
                    texts.append(" ".join(tp.get_text_range().split()))
                    tp.close()
                    page.close()
                return texts
            finally:
                pdf.close()
