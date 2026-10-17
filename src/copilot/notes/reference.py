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
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Optional, Sequence

import numpy as np

from copilot.core.textutil import approx_tokens
from copilot.notes.library import NoteDoc, NotesLibrary
from copilot.notes.service import Embedder, chunks

log = logging.getLogger(__name__)

FORMAT = 3               # bump when the cached index changes shape (2: captions, drawn figures; F-013 S4;
                         # 3: each figure's place on its page, for clicking it in My Notes, F-013 S5)
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
# F-013 S4: "Figure 3.1: The Target Selection wizard" / "Fig. 2 - Block diagram" / "Figure 1: ESP32-WROOM-32 Pin
# Layout": a caption line. "Figure 3.5 shows what appears ..." is a sentence about a figure, not its caption.
_CAPTION = re.compile(r"^\s*(?:fig(?:ure)?\.?|diagram)\s*(\d+(?:[.\-]\d+)*)\s*(?:[:.\-\u2013\u2014|]\s*|\s+(?=[A-Z0-9(]))"
                      r"(?P<text>\S.*)$", re.IGNORECASE)
_TABLE = re.compile(r"^\s*table\s*\d+(?:[.\-]\d+)*\s*[:.\-–]?\s*\S", re.IGNORECASE)
CAPTION_BELOW = 0.12     # of the page height: how far under a figure its caption may sit
CAPTION_ABOVE = 0.06     # ... or over it
# a drawn (vector) figure: the path objects next to a caption line, grown while the gap stays small
DRAW_GAP_PT = 28
DRAW_MIN_PATHS = 8
DRAW_MIN_AREA = 0.04     # of the page
DRAW_PAD_PT = 14         # labels just outside the drawn lines (pin names) stay in the picture


@dataclass
class Figure:
    n: int
    page: int
    label: str
    width: int = 0
    height: int = 0
    caption: str = ""    # F-013 S4: its caption without "Figure N:" ("ESP32-WROOM-32 Pin Layout (Top View)"), "" = none
    drawn: bool = False  # rendered from vector drawing (a datasheet's pin layout / schematic), not an image object
    # F-013 S5: its place on the page as fractions of the rendered page, top-left origin [left, top, right, bottom];
    # empty on a rotated page (the page image is turned, the PDF coordinates are not)
    box: list = field(default_factory=list)


def caption_text(line: str) -> str:
    """The caption's words without its number ("Figure 3.1: The Target Selection wizard - STEP 1" -> "The Target
    Selection wizard - STEP 1"); "" when the line is not a caption."""
    m = _CAPTION.match(line)
    if not m:
        return ""
    text = " ".join(m.group("text").split())
    if not text or text[0].islower() or len(text) > 160:
        return ""
    return text


def _lines(page) -> list[tuple[tuple[float, float, float, float], str]]:
    """The page's text runs merged into lines: ((left, bottom, right, top), text), top of the page first."""
    tp = page.get_textpage()
    try:
        runs = []
        for i in range(tp.count_rects()):
            box = tp.get_rect(i)
            text = " ".join(tp.get_text_bounded(*box).split())
            if text:
                runs.append((box, text))
    finally:
        tp.close()
    rows: list[list] = []  # runs on one baseline (a caption's number and words can be separate runs, any order)
    for run in sorted(runs, key=lambda x: -x[0][1]):
        if rows and abs(rows[-1][0][0][1] - run[0][1]) < 2.5:
            rows[-1].append(run)
        else:
            rows.append([run])
    lines = []
    for row in rows:
        row.sort(key=lambda x: x[0][0])
        cur = [row[0][0], row[0][1]]
        for (l, b, r, t), text in row[1:]:
            if l - cur[0][2] < 60:  # the same line; farther apart: another column
                cur = [(cur[0][0], min(cur[0][1], b), max(cur[0][2], r), max(cur[0][3], t)), f"{cur[1]} {text}"]
            else:
                lines.append((tuple(cur[0]), cur[1]))
                cur = [(l, b, r, t), text]
        lines.append((tuple(cur[0]), cur[1]))
    return lines


def _caption_near(lines, box, ph: float) -> tuple[str, str]:
    """(caption, its whole line) of the figure at `box`: the caption line just under it, else just over it."""
    l, b, r, t = box
    best = None
    for (cl, cb, cr, ct), text in lines:
        cap = caption_text(text)
        if not cap or cr < l - 20 or cl > r + 20:
            continue
        if b - CAPTION_BELOW * ph <= ct <= b + 4:
            d = b - ct
        elif t - 4 <= cb <= t + CAPTION_ABOVE * ph:
            d = (cb - t) + 1000  # under the figure first
        else:
            continue
        if best is None or d < best[0]:
            best = (d, cap, text)
    return (best[1], best[2]) if best else ("", "")


def page_boxes(page, kind: int):
    """(object, (left, bottom, right, top)) of the page's objects of one kind, in PAGE coordinates. pdfium gives an
    object inside a form XObject its bounds in the form's own space (F-013 S4: the ESP-WROOM-32 reset circuit sat
    at y 355-371 of an 842-wide form scaled 1.39 on a portrait page); the forms' matrices put it back in place."""
    import pypdfium2.raw as raw

    chain: dict[int, list] = {}  # level -> matrices of the forms around objects one level deeper, innermost first
    for obj in page.get_objects(max_depth=3):
        outer = chain.get(obj.level - 1, []) if obj.level else []
        if obj.type == raw.FPDF_PAGEOBJ_FORM:
            chain[obj.level] = [obj.get_matrix()] + outer
            continue
        if obj.type != kind:
            continue
        l, b, r, t = obj.get_bounds()
        if outer:
            pts = [(l, b), (l, t), (r, b), (r, t)]
            for m in outer:
                pts = [m.on_point(x, y) for x, y in pts]
            xs, ys = [x for x, _ in pts], [y for _, y in pts]
            l, b, r, t = min(xs), min(ys), max(xs), max(ys)
        yield obj, (l, b, r, t)


def _drawn_regions(page, lines, taken: list) -> list[tuple[tuple[float, float, float, float], str, str]]:
    """Figures drawn with vector paths (F-013 S4, the ESP-WROOM-32 datasheet: 0 image objects; its pin layout and
    schematics are drawings): the page's paths grouped into clusters (boxes closer than DRAW_GAP_PT, never joined
    across another figure's caption), and for each caption line no image figure claimed, the nearest cluster above
    or below it. A table's ruling has a "Table N" caption and is never taken. Rotated pages: not yet (0 figures)."""
    import pypdfium2.raw as raw

    if page.get_rotation() % 360:
        return []
    pw, ph = page.get_size()
    boxes = []
    for _obj, (l, b, r, t) in page_boxes(page, raw.FPDF_PAGEOBJ_PATH):
        l, b, r, t = max(0.0, l), max(0.0, b), min(pw, r), min(ph, t)
        w, h = r - l, t - b
        if w <= 0 or h <= 0 or w * h > 0.5 * pw * ph:  # a page frame / clip box
            continue
        if h < 1.5 and w > 0.6 * pw and (t > 0.9 * ph or b < 0.1 * ph or w > 0.85 * pw):  # header / footer / rule
            continue
        # a frame around text (a "Note:" box): two or more lines of words fill it; not part of a drawing
        inside = [lb for lb, text in lines if lb[0] >= l - 2 and lb[2] <= r + 2 and lb[1] >= b - 2 and lb[3] <= t + 2
                  and len(text.split()) >= 4]
        if len(inside) >= 2 and sum(lb[2] - lb[0] for lb in inside) >= 1.2 * w:
            continue
        boxes.append((l, b, r, t))
    caps = [(box, text, caption_text(text)) for box, text in lines if caption_text(text)]
    tables = [box for box, text in lines if _TABLE.match(text)]
    if not boxes or not caps:
        return []
    # a box crossing a caption or table line (a frame around figure, caption and table) would join them all
    bars = [x[0] for x in caps] + tables
    boxes = [bx for bx in boxes if not any(bx[1] < cb and bx[3] > ct for cl, cb, cr, ct in bars)]

    def between(a, c) -> bool:  # a caption line lies between the two boxes (one over it, one under it)
        for (cl, cb, cr, ct) in [x[0] for x in caps] + tables:  # across the whole width: it ends the figure
            mid = (cb + ct) / 2  # by the boxes' middles: a small mark level with the caption must not bridge it
            if ((a[1] + a[3]) / 2 - mid) * ((c[1] + c[3]) / 2 - mid) < 0:
                return True
        return False

    parent = list(range(len(boxes)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    g = DRAW_GAP_PT / 2
    order = sorted(range(len(boxes)), key=lambda i: boxes[i][0])
    for k, i in enumerate(order):
        a = boxes[i]
        for j in order[k + 1:]:
            c = boxes[j]
            if c[0] - g > a[2] + g:
                break
            if c[1] - g <= a[3] + g and a[1] - g <= c[3] + g and not between(a, c):
                parent[root(j)] = root(i)
    clusters: dict[int, list] = {}
    for i, bx in enumerate(boxes):
        clusters.setdefault(root(i), []).append(bx)
    regions, parts = [], []
    for members in clusters.values():
        l, b = min(m[0] for m in members), min(m[1] for m in members)
        r, t = max(m[2] for m in members), max(m[3] for m in members)
        parts.append((l, b, r, t))  # any size: a drawing's smaller pieces join it (below)
        if len(members) < DRAW_MIN_PATHS:
            continue
        under_table = any(tl - 20 <= r and l <= tr + 20 and 0 <= tb - t <= 40 for tl, tb, tr, tt in tables)
        if (r - l) * (t - b) >= DRAW_MIN_AREA * pw * ph and t - b >= 50 and r - l >= 0.25 * pw and not under_table:
            regions.append((l, b, r, t))
    out, used = [], set()
    for (cl, cb, cr, ct), text, cap in caps:
        if text in taken:
            continue
        best = None
        for k, (l, b, r, t) in enumerate(regions):
            if k in used or cr < l - 20 or cl > r + 20:
                continue
            side = "over" if b >= ct - 3 else "under" if t <= cb + 3 else ""
            gap = b - ct if side == "over" else cb - t if side == "under" else None
            if gap is None and l <= cl and cr <= r and b <= cb and ct <= t:
                side, gap = "over", 0.0  # the caption sits inside the drawing (a framed figure): part of it
            # a caption is under its figure in most books and datasheets: the drawing over it first
            if gap is not None and gap <= 2 * DRAW_GAP_PT + 20 and                     (best is None or (side == "over", -gap) > (best[2] == "over", -best[0])):
                best = (gap, k, side)
        if best is None:
            continue
        used.add(best[1])
        l, b, r, t = regions[best[1]]
        joined: set[int] = set()
        grown = True
        while grown:  # the other pieces of the same drawing on that side (a module outline, its antenna)
            grown = False
            for k, (l2, b2, r2, t2) in enumerate(parts):
                if k in joined or r2 < l - 20 or l2 > r + 20 or (l2, b2, r2, t2) in [regions[u] for u in used]:
                    continue
                if any(c[0] == (l2, b2, r2, t2) for c in out):
                    continue
                if best[2] == "over" and b2 < ct - 3 or best[2] == "under" and t2 > cb + 3:
                    continue
                gap2 = b2 - t if b2 >= t else b - t2 if t2 <= b else 0.0
                if gap2 <= 2 * DRAW_GAP_PT and not between((l, b, r, t), (l2, b2, r2, t2)):
                    joined.add(k)
                    l, b, r, t = min(l, l2), min(b, b2), max(r, r2), max(t, t2)
                    grown = True
        out.append(((max(0.0, l - DRAW_PAD_PT), max(0.0, b - DRAW_PAD_PT), min(pw, r + DRAW_PAD_PT),
                     min(ph, t + DRAW_PAD_PT)), cap, text))
    return out


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
            for obj, (l, b, r, t) in page_boxes(page, raw.FPDF_PAGEOBJ_IMAGE):
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
        page_lines: dict[int, list] = {}
        claimed: dict[int, list[str]] = {}  # page -> caption lines an image figure took

        def lines_of(i: int, page) -> list:
            if i not in page_lines:
                page_lines[i] = _lines(page)
            return page_lines[i]

        def save(page, i: int, box, label: str, caption: str, drawn: bool) -> None:
            l, b, r, t = box
            pw, ph = page.get_size()
            scale = min(4.0, max(1.0, 960 / max(1.0, r - l)))
            img = page.render(scale=scale, crop=(l, b, pw - r, ph - t)).to_pil().convert("RGB")
            n = len(out) + 1
            tmp = out_dir / f"f{n}.tmp"
            img.save(tmp, format="PNG", optimize=True)
            tmp.replace(out_dir / f"f{n}.png")
            place = [round(l / pw, 4), round(1 - t / ph, 4), round(r / pw, 4), round(1 - b / ph, 4)] \
                if not page.get_rotation() else []
            out.append(Figure(n, i + 1, label, img.width, img.height, caption, drawn, place))

        for i, (l, b, r, t) in boxes:
            if len(out) >= limit:
                break
            page = pdf[i]
            pw, ph = page.get_size()
            if kind != "image" and any(k[:4] == (round(l), round(b), round(r - l), round(t - b)) for k in repeated):
                page.close()
                continue
            caption = ""
            if kind == "image":
                label = _name_label(name)
            else:
                caption, line = _caption_near(lines_of(i, page), (l, b, r, t), ph)
                if caption:  # D3: the caption names the figure; the page's other words are noise
                    claimed.setdefault(i, []).append(line)
                    label = " ".join(f"{line} {_heading(lines_of(i, page))} {_name_label(name)}".split()[:40])
                else:
                    label = _label(page, (l, b, r, t), name)
            save(page, i, (l, b, r, t), label, caption, False)
            page.close()
        if kind in ("pdf", "web", "word", "slides"):  # drawn figures: datasheets, exported slides, papers
            for i in range(len(pdf)):
                if len(out) >= limit:
                    break
                page = pdf[i]
                lines = lines_of(i, page)
                if any(caption_text(text) for _, text in lines):
                    for box, cap, line in _drawn_regions(page, lines, claimed.get(i, [])):
                        if len(out) >= limit:
                            break
                        label = " ".join(f"{line} {_heading(lines)} {_name_label(name)}".split()[:40])
                        save(page, i, box, label, cap, True)
                page.close()
        return out
    finally:
        pdf.close()


def page_figures(library, doc_id: str, page: int) -> list[Figure]:
    """The figures found on one page of a file in use, with their place (F-013 S5: the teacher clicks one in My Notes
    to show it); [] when the file has no index of this format (not in use, or not read yet)."""
    d = library.doc_dir(doc_id)
    if not (d / f"ref.v{FORMAT}.npz").is_file():
        return []
    try:
        figs = [Figure(**x) for x in json.loads((d / "figures.json").read_text(encoding="utf-8"))]
    except (OSError, ValueError, TypeError):
        return []
    return [f for f in figs if f.page == page and len(f.box) == 4 and (d / f"f{f.n}.png").is_file()]


def _heading(lines: list) -> str:
    """The page's first line (its section heading, usually), at most 12 words."""
    return " ".join(lines[0][1].split()[:12]) if lines else ""


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
        # the format is in the name: an index of an older format counts as not built, so it is rebuilt (F-013 S4)
        return self.library.doc_dir(doc_id) / f"ref.v{FORMAT}.npz"

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
        old = d / "figures.json"
        if (d / "ref.npz").is_file() and old.is_file() and not (d / "figures.v1.json").exists():
            old.replace(d / "figures.v1.json")  # the format-1 list, kept (user 2026-10-17)
        (d / "figures.json").write_text(json.dumps([asdict(f) for f in figures]), encoding="utf-8")
        tmp = d / "ref.tmp.npz"
        np.savez(tmp, format=np.array([FORMAT]), vectors=vectors.astype(np.float16),
                 pages=np.array(pages, dtype=np.int32), fig_vectors=fig_vectors.astype(np.float16))
        tmp.replace(self._file(doc.id))
        (d / "ref.npz").unlink(missing_ok=True)  # the format-1 index
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
