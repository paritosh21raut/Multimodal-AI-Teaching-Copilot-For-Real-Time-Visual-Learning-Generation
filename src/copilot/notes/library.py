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
import urllib.parse
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MAX_PAGES = 600
RENDER_WIDTHS = (480, 720, 960, 1280, 1920)  # the client asks for one of these (nearest above): a small cache;
# 1920: a page on the projector (F-010b)
_ID = re.compile(r"[0-9a-f]{16}")
MAX_ACTIVE = 10  # reference files in use at a time (F-012)
MIN_TEXT_WORDS = 15  # fewer words in the whole file: a scan / pictures only, nothing to follow the lecture with


def link_name(url: str, title: str = "") -> str:
    """What a saved web page is called (F-013): its title; a page without one (byjus.com sends none) gets the last
    words of its address and the site, "Human Brain · byjus.com", never only the site (5 files were all "byjus.com")."""
    parts = urllib.parse.urlsplit(url or "")
    host = parts.netloc.lower().removeprefix("www.")
    title = " ".join((title or "").split())[:120]
    if title and title.lower().removeprefix("www.") != host:
        return title
    segs = [s for s in parts.path.split("/") if s and not s.isdigit()]
    slug = re.sub(r"\.(html?|php|aspx?)$", "", urllib.parse.unquote(segs[-1]), flags=re.I) if segs else ""
    words = re.sub(r"[-_+]+", " ", slug).strip()
    if not words:
        return host or "web page"
    return f"{' '.join(w if w.isupper() else w.capitalize() for w in words.split())[:90]} · {host}"


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
    active: bool = True    # reference material for the lectures (F-012); at most MAX_ACTIVE files
    private: bool = False  # never sent to the LLM (still used for images and speech recognition)


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
        out = [NoteDoc(**d) for d in self._index()["docs"] if (self.root / f"{d['id']}.pdf").is_file()]
        for d in out:  # pages saved before F-013 are called by their site only ("byjus.com")
            if d.kind == "web" and d.source:
                d.name = link_name(d.source, d.name)
        return out

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
        index = self._index()
        in_use = sum(1 for d in index["docs"] if d.get("active", True))
        doc = NoteDoc(doc_id, name, len(texts), sum(len(t.split()) for t in texts) >= MIN_TEXT_WORDS, time.time(),
                      kind, source, active=in_use < MAX_ACTIVE)
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
        # the folder holds rendered pages and the reference index (F-012: chunks, figures)
        for f in [self.root / f"{doc_id}.pdf", self.root / f"{doc_id}.json", *(self.root / doc_id).glob("*")]:
            f.unlink(missing_ok=True)
        if (self.root / doc_id).is_dir():
            (self.root / doc_id).rmdir()
        return len(index["docs"]) < before

    def set_flags(self, doc_id: str, active: Optional[bool] = None, private: Optional[bool] = None) -> str:
        """Use for lectures / private (F-012). Returns why it was refused ("" = done)."""
        index = self._index()
        d = next((d for d in index["docs"] if d.get("id") == doc_id), None)
        if d is None:
            return "unknown file"
        if active and not d.get("active", True):
            if sum(1 for x in index["docs"] if x.get("active", True)) >= MAX_ACTIVE:
                return f"at most {MAX_ACTIVE} files can be used at a time"
        if active is not None:
            d["active"] = bool(active)
        if private is not None:
            d["private"] = bool(private)
        self._save_index(index)
        return ""

    def pdf_path(self, doc_id: str) -> Path:
        return self.root / f"{doc_id}.pdf"

    def doc_dir(self, doc_id: str) -> Path:
        return self.root / doc_id

    @property
    def pdf_lock(self) -> threading.Lock:
        """pdfium is not thread-safe: every pdfium call in the app holds this."""
        return self._lock

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

    def render_region(self, doc_id: str, page: int, box: list[float], max_px: int = 1600):
        """A part of a page (box: fractions of the page as shown, top-left origin [left, top, right, bottom]) as a PIL
        image about `max_px` wide, rendered from the PDF (sharp, not cut from the preview); None if there is none
        (F-013 S5: the teacher selects a figure the index did not find)."""
        doc = self.get(doc_id) if _ID.fullmatch(doc_id) else None
        if doc is None or not 1 <= page <= doc.pages or len(box) != 4:
            return None
        left, top, right, bottom = (min(1.0, max(0.0, float(x))) for x in box)
        if right - left < 0.01 or bottom - top < 0.01:
            return None
        import pypdfium2 as pdfium

        with self._lock:
            pdf = pdfium.PdfDocument(str(self.root / f"{doc_id}.pdf"))
            try:
                p = pdf[page - 1]
                w = p.get_width() if not p.get_rotation() % 180 else p.get_height()
                # the whole page, then the part: pdfium's crop is taken before a page's rotation (the ESP32
                # datasheet's turned schematic page); at most 4x, an A4 page is then ~8 MP
                scale = min(4.0, max(1.0, max_px / max(1.0, (right - left) * w)))
                full = p.render(scale=scale, draw_annots=True).to_pil().convert("RGB")
                p.close()
                W, H = full.size
                image = full.crop((round(left * W), round(top * H), round(right * W), round(bottom * H)))
            finally:
                pdf.close()
        return image

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
