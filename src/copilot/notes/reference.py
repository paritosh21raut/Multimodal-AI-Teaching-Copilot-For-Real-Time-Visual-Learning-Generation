"""Reference material (F-012): the teacher's My Notes files as a local index, kept apart from the live transcript.

Used only to show what the teacher says more accurately, never to add what was not taught:
    snippet()   one short passage for the interpretation prompt (LLM; not from Private files)
    grounding() passages matched to taught subtopics, for checking quiz facts (LLM; not from Private files)
    figures()   the teacher's own figures for a slide image (0 tokens; before the web search)
    terms()     rare technical words for Whisper's prompt (0 tokens)
Per file, built once in the background (content hash) and cached under data/notes/<id>/:
    ref.npz       chunk vectors + their pages, figure-label vectors (MiniLM, normalised, float16)
    figures.json  [{n, page, label, width, height}];  f<n>.png  the figure, rendered from its page region
"""
from __future__ import annotations

import json
import logging
import re
import threading
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from copilot.core.textutil import approx_tokens
from copilot.notes.library import NoteDoc, NotesLibrary
from copilot.notes.service import Embedder, chunks

log = logging.getLogger(__name__)

FORMAT = 1               # bump when the cached index changes shape
SNIPPET_MIN = 0.5        # MiniLM cosine: a passage clearly about these lines (calibrated in tests/unit/test_reference.py)
SNIPPET_TOKENS = 150
GROUND_MIN = 0.5         # ... clearly about a taught subtopic
GROUND_TOKENS = 400
FIG_LABEL_MIN = 0.5      # figure label ↔ image query, before the CLIP gate ("heart" 0.59, "plant cell" ↔ a
#                          chloroplast 0.47, unrelated < 0.25 on tests/fixtures/notes/reference_biology.pdf)
MAX_CHUNKS = 20000       # in use at a time (a 600-page book ≈ 8000); ≈ 15 MB of vectors
MAX_FIGURES = 40         # per file
MAX_TERMS = 30
BATCH = 64

_BACKGROUND = 0.85       # an image covering this much of the page is its background, not a figure
_MIN_WIDTH = 0.12        # of the page width
_MIN_PX = 140            # the image's longer side, in its own pixels
_REPEATED = 3            # the same image (size + place) on this many pages: a logo / decoration
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9\-]{3,}")


@dataclass
class Figure:
    n: int
    page: int
    label: str
    width: int = 0
    height: int = 0


@dataclass
class Snippet:
    text: str
    doc_id: str
    name: str
    page: int
    score: float

    @property
    def cite(self) -> str:
        return f"{self.name} p.{self.page}"


@dataclass
class FigureMatch:
    score: float       # label ↔ query cosine
    doc: NoteDoc
    figure: Figure
    path: Path


@dataclass
class _Doc:
    vectors: np.ndarray      # (chunks, dim) float32
    pages: np.ndarray        # (chunks,) 1-based page of each chunk
    texts: list[str]
    figures: list[Figure]
    fig_vectors: np.ndarray  # (figures, dim)


def _name_label(name: str) -> str:
    return " ".join(re.sub(r"[_\-.]+", " ", Path(name).stem).split())


def _embed(embedder: Embedder, texts: Sequence[str]) -> np.ndarray:
    if not texts:
        return np.zeros((0, 384), dtype=np.float32)
    return np.concatenate([embedder.embed(texts[i:i + BATCH]) for i in range(0, len(texts), BATCH)])


def extract_figures(pdf_path: Path, out_dir: Path, kind: str, name: str,
                    limit: int = MAX_FIGURES) -> list[Figure]:
    """The figures of a PDF: image objects that are not page backgrounds or repeated decorations, rendered from
    their page region (labels drawn over the picture stay). An image file the teacher added is one figure named by
    the file. The caller holds the library's pdfium lock."""
    import pypdfium2 as pdfium
    import pypdfium2.raw as raw

    pdf = pdfium.PdfDocument(str(pdf_path))
    try:
        boxes: list[tuple[int, tuple[float, float, float, float]]] = []
        seen: Counter = Counter()
        for i in range(len(pdf)):
            page = pdf[i]
            pw, ph = page.get_size()
            for obj in page.get_objects(filter=[raw.FPDF_PAGEOBJ_IMAGE], max_depth=3):
                l, b, r, t = obj.get_bounds()
                l, b, r, t = max(0.0, l), max(0.0, b), min(pw, r), min(ph, t)
                w, h = r - l, t - b
                px = max(obj.get_px_size())
                if w <= 0 or h <= 0:
                    continue
                if kind != "image" and (w * h >= _BACKGROUND * pw * ph or w < _MIN_WIDTH * pw or px < _MIN_PX
                                        or max(w / h, h / w) > 5):
                    continue
                key = (round(l), round(b), round(w), round(h), obj.get_px_size())
                seen[key] += 1
                boxes.append((i, (l, b, r, t)))
            page.close()
        repeated = {k for k, c in seen.items() if c >= _REPEATED}
        out: list[Figure] = []
        out_dir.mkdir(parents=True, exist_ok=True)
        for i, (l, b, r, t) in boxes:
            if len(out) >= limit:
                break
            page = pdf[i]
            pw, ph = page.get_size()
            if kind != "image" and any(k[:4] == (round(l), round(b), round(r - l), round(t - b)) for k in repeated):
                page.close()
                continue
            label = _name_label(name) if kind == "image" else _label(page, (l, b, r, t), name)
            scale = min(4.0, max(1.0, 960 / max(1.0, r - l)))
            img = page.render(scale=scale, crop=(l, b, pw - r, ph - t)).to_pil().convert("RGB")
            page.close()
            n = len(out) + 1
            tmp = out_dir / f"f{n}.tmp"
            img.save(tmp, format="PNG", optimize=True)
            tmp.replace(out_dir / f"f{n}.png")
            out.append(Figure(n, i + 1, label, img.width, img.height))
        return out
    finally:
        pdf.close()


def _label(page, box: tuple[float, float, float, float], name: str) -> str:
    """What the figure is about: its caption (the text just below / above it), the labels on it, the page heading,
    the file name; at most 60 words."""
    l, b, r, t = box
    pw, ph = page.get_size()
    tp = page.get_textpage()
    try:
        below = " ".join(tp.get_text_bounded(0, max(0.0, b - 0.08 * ph), pw, b).split())
        above = " ".join(tp.get_text_bounded(0, t, pw, min(ph, t + 0.04 * ph)).split())
        inside = " ".join(tp.get_text_bounded(l, b, r, t).split()[:25])
        lines = [x.strip() for x in tp.get_text_range().splitlines() if x.strip()]
    finally:
        tp.close()
    heading = " ".join(lines[0].split()[:12]) if lines else ""
    caption = below if re.match(r"\s*(fig|figure|diagram|image|plate)\b", below, re.I) or not above else \
        f"{below} {above}"
    words = " ".join(x for x in (caption, inside, heading, _name_label(name)) if x).split()
    return " ".join(words[:60])


def load_vocab(tokenizer_json: Path) -> set[str]:
    """MiniLM's WordPiece vocabulary (whole words only): a word in it is common English."""
    try:
        vocab = json.loads(tokenizer_json.read_text(encoding="utf-8"))["model"]["vocab"]
    except (OSError, ValueError, KeyError) as e:
        log.warning("reference terms off: vocabulary unreadable (%s)", e)
        return set()
    return {w for w in vocab if not w.startswith("##") and not w.startswith("[")}


def rare_terms(texts: Sequence[str], vocab: set[str], limit: int = MAX_TERMS, min_count: int = 2) -> list[str]:
    """Words the vocabulary does not know (technical terms, names, part numbers), seen ≥ min_count times; the most
    frequent first, in their most frequent spelling."""
    if not vocab:
        return []
    counts: Counter = Counter()
    spelling: dict[str, Counter] = {}
    for text in texts:
        for w in _WORD.findall(text):
            w = w.strip("-")
            low = w.lower()
            if len(low) < 4 or low in vocab or (low.endswith("s") and low[:-1] in vocab):
                continue
            counts[low] += 1
            spelling.setdefault(low, Counter())[w] += 1
    return [spelling[w].most_common(1)[0][0] for w, c in counts.most_common() if c >= min_count][:limit]


class ReferenceIndex:
    def __init__(self, library: NotesLibrary, embedder: Optional[Embedder] = None,
                 vocab: Optional[set[str]] = None) -> None:
        self.library = library
        self.embedder = embedder
        self.vocab = vocab or set()
        self._docs: dict[str, _Doc] = {}
        self._lock = threading.Lock()

    # ---- building ------------------------------------------------------------------------------
    def _file(self, doc_id: str) -> Path:
        return self.library.doc_dir(doc_id) / "ref.npz"

    def is_built(self, doc_id: str) -> bool:
        return doc_id in self._docs or self._file(doc_id).is_file()

    def pending(self) -> list[NoteDoc]:
        """Files in use whose index is not built yet."""
        return [d for d in self.library.docs() if d.active and not self.is_built(d.id)]

    def build(self, doc: NoteDoc, progress: Optional[Callable[[float], None]] = None) -> None:
        """Chunks + figures of one file (blocking; run in a thread)."""
        assert self.embedder is not None
        texts_by_page = self.library.page_texts(doc.id)
        texts, pages = [], []
        for page, t in enumerate(texts_by_page, start=1):
            for c in chunks(t):
                texts.append(c)
                pages.append(page)
        vecs = []
        for i in range(0, len(texts), BATCH):
            vecs.append(self.embedder.embed(texts[i:i + BATCH]))
            if progress:
                progress(0.9 * min(1.0, (i + BATCH) / max(1, len(texts))))
        vectors = np.concatenate(vecs) if vecs else np.zeros((0, 384), dtype=np.float32)
        with self.library.pdf_lock:
            figures = extract_figures(self.library.pdf_path(doc.id), self.library.doc_dir(doc.id), doc.kind, doc.name)
        fig_vectors = _embed(self.embedder, [f.label for f in figures])
        d = self.library.doc_dir(doc.id)
        d.mkdir(parents=True, exist_ok=True)
        (d / "figures.json").write_text(json.dumps([asdict(f) for f in figures]), encoding="utf-8")
        tmp = d / "ref.tmp.npz"
        np.savez(tmp, format=np.array([FORMAT]), vectors=vectors.astype(np.float16),
                 pages=np.array(pages, dtype=np.int32), fig_vectors=fig_vectors.astype(np.float16))
        tmp.replace(self._file(doc.id))
        if progress:
            progress(1.0)
        log.info("reference index %r: %d chunks, %d figures", doc.name, len(texts), len(figures))

    def _load(self, doc: NoteDoc) -> Optional[_Doc]:
        with self._lock:
            if doc.id in self._docs:
                return self._docs[doc.id]
        f = self._file(doc.id)
        if not f.is_file():
            return None
        try:
            z = np.load(f)
            if int(z["format"][0]) != FORMAT:
                f.unlink(missing_ok=True)
                return None
            figs = json.loads((self.library.doc_dir(doc.id) / "figures.json").read_text(encoding="utf-8"))
            texts = [c for t in self.library.page_texts(doc.id) for c in chunks(t)]
            entry = _Doc(z["vectors"].astype(np.float32), z["pages"], texts, [Figure(**x) for x in figs],
                         z["fig_vectors"].astype(np.float32))
        except (OSError, ValueError, KeyError, TypeError) as e:
            log.warning("reference index %s unreadable (%s): rebuilt", doc.id, e)
            f.unlink(missing_ok=True)
            return None
        if len(entry.texts) != len(entry.pages):
            log.warning("reference index %s does not match its text: rebuilt", doc.id)
            f.unlink(missing_ok=True)
            return None
        with self._lock:
            self._docs[doc.id] = entry
        return entry

    def forget(self, doc_id: str) -> None:
        with self._lock:
            self._docs.pop(doc_id, None)

    def _in_use(self, llm: bool) -> list[tuple[NoteDoc, _Doc]]:
        out, total = [], 0
        for doc in self.library.docs():
            if not doc.active or (llm and doc.private):
                continue
            entry = self._load(doc)
            if entry is None:
                continue
            total += len(entry.texts)
            if total > MAX_CHUNKS:
                log.warning("reference %r not used: over %d passages in use", doc.name, MAX_CHUNKS)
                continue
            out.append((doc, entry))
        return out

    def chunk_count(self, doc: NoteDoc) -> int:
        entry = self._load(doc)
        return len(entry.texts) if entry else 0

    # ---- use -----------------------------------------------------------------------------------
    def _best(self, query: str, llm: bool, k: int) -> list[Snippet]:
        if self.embedder is None or not query.strip():
            return []
        docs = self._in_use(llm)
        if not docs:
            return []
        q = self.embedder.embed([query])[0]
        found: list[Snippet] = []
        for doc, entry in docs:
            if not len(entry.texts):
                continue
            sims = entry.vectors @ q
            for i in np.argsort(-sims)[:k]:
                found.append(Snippet(entry.texts[i], doc.id, doc.name, int(entry.pages[i]), float(sims[i])))
        return sorted(found, key=lambda s: -s.score)

    def snippet(self, text: str, max_tokens: int = SNIPPET_TOKENS,
                min_score: float = SNIPPET_MIN) -> Optional[Snippet]:
        """The passage of the files in use (not Private) that is clearly about `text`, ≤ max_tokens; or None.
        A second passage of the same file joins it when it also matches and does not overlap."""
        best = [s for s in self._best(text, True, 3) if s.score >= min_score]
        if not best:
            return None
        top = best[0]
        out = _clip(top.text, max_tokens)
        for s in best[1:]:
            if s.doc_id == top.doc_id and not _overlaps(s.text, top.text) and \
                    approx_tokens(out + " … " + s.text) <= max_tokens:
                out += " … " + s.text
                break
        return Snippet(out, top.doc_id, top.name, top.page, top.score)

    def grounding(self, texts: Sequence[str], max_tokens: int = GROUND_TOKENS,
                  min_score: float = GROUND_MIN) -> list[Snippet]:
        """For each taught text, its clearly matching passage; the best ones first, unique, ≤ max_tokens."""
        picked: dict[str, Snippet] = {}
        for t in texts:
            for s in self._best(t, True, 1):
                if s.score >= min_score and (s.text not in picked or picked[s.text].score < s.score):
                    picked[s.text] = s
        out, used = [], 0
        for s in sorted(picked.values(), key=lambda s: -s.score):
            n = approx_tokens(s.text) + 6
            if used + n > max_tokens:
                continue
            if any(_overlaps(s.text, o.text) for o in out):
                continue
            out.append(s)
            used += n
        return out

    def figures(self, query: str, min_score: float = FIG_LABEL_MIN, k: int = 4) -> list[FigureMatch]:
        """The teacher's figures whose label is clearly about the query (Private files too: nothing leaves the
        laptop), best first."""
        if self.embedder is None or not query.strip():
            return []
        docs = [(d, e) for d, e in self._in_use(False) if len(e.figures)]
        if not docs:
            return []
        q = self.embedder.embed([query])[0]
        out = []
        for doc, entry in docs:
            sims = entry.fig_vectors @ q
            for f, s in zip(entry.figures, sims):
                path = self.library.doc_dir(doc.id) / f"f{f.n}.png"
                if s >= min_score and path.is_file():
                    out.append(FigureMatch(float(s), doc, f, path))
        return sorted(out, key=lambda m: -m.score)[:k]

    def terms(self, limit: int = MAX_TERMS) -> list[str]:
        texts = [t for d in self.library.docs() if d.active for t in self.library.page_texts(d.id)]
        return rare_terms(texts, self.vocab, limit)


def _clip(text: str, max_tokens: int) -> str:
    words = text.split()
    while words and approx_tokens(" ".join(words)) > max_tokens:
        words = words[:-5]
    return " ".join(words)


def _overlaps(a: str, b: str) -> bool:
    wa, wb = set(a.lower().split()), set(b.lower().split())
    return len(wa & wb) > 0.4 * min(len(wa), len(wb))
