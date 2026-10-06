"""Disk cache of images the display may show (F-007b). The server serves these files under /media/ — the display
never loads an image from another site (works when the classroom network drops later; no hot-linking).

Every image (downloaded or uploaded by the teacher) is decoded and re-encoded with Pillow: EXIF rotation applied,
transparency flattened onto white, at most MAX_SIDE px, JPEG. Metadata (source, licence, author, query) is stored
next to it as JSON. Query results (the accepted, ranked candidates) are cached too, so a repeated query needs no
network.
"""
from __future__ import annotations

import hashlib
import io
import json
import logging
import warnings
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

MAX_SIDE = 1280
MAX_PIXELS = 40_000_000  # decompression-bomb guard (Pillow default warns at 89 MP)
MEDIA_PREFIX = "/media/"


class BadImage(ValueError):
    pass


@dataclass
class CachedImage:
    id: str                 # file stem (sha1 prefix); the display URL is /media/<id>.jpg
    width: int
    height: int
    alt: str = ""
    source: str = ""        # wikipedia | commons | openverse | teacher
    title: str = ""
    page_url: str = ""
    licence: str = ""
    author: str = ""
    query: str = ""
    score: float = 0.0      # CLIP similarity (+ prior) when ranked
    extra: dict = field(default_factory=dict)

    @property
    def url(self) -> str:
        return f"{MEDIA_PREFIX}{self.id}.jpg"

    @property
    def aspect(self) -> float:
        return self.width / self.height if self.height else 1.0


def decode(data: bytes):
    """bytes → RGB PIL image (rotated, flattened, ≤ MAX_SIDE). Raises BadImage."""
    from PIL import Image, ImageOps

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            img = Image.open(io.BytesIO(data))
            if img.width * img.height > MAX_PIXELS:
                raise BadImage(f"image too large ({img.width}x{img.height})")
            img.load()
    except BadImage:
        raise
    except Exception as e:  # PIL raises many types for broken / unknown files
        raise BadImage(f"not a readable image: {e}") from e
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        bg = Image.new("RGB", img.size, (255, 255, 255))
        bg.paste(img, mask=img.getchannel("A"))
        img = bg
    else:
        img = img.convert("RGB")
    img.thumbnail((MAX_SIDE, MAX_SIDE), Image.LANCZOS)
    return img


class ImageCache:
    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def _ensure(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, image_id: str) -> Path:
        return self.root / f"{image_id}.jpg"

    def store(self, img, key: str, meta: CachedImage) -> CachedImage:
        """Save a decoded PIL image under sha1(key); returns the metadata with id and size filled."""
        self._ensure()
        image_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
        target = self.path(image_id)
        if not target.exists():
            tmp = target.with_suffix(".tmp")
            img.save(tmp, "JPEG", quality=88, optimize=True)
            tmp.replace(target)
        meta.id, meta.width, meta.height = image_id, img.width, img.height
        (self.root / f"{image_id}.json").write_text(json.dumps(asdict(meta), ensure_ascii=False), encoding="utf-8")
        return meta

    def store_bytes(self, data: bytes, key: str, meta: CachedImage) -> CachedImage:
        return self.store(decode(data), key, meta)

    def get(self, image_id: str) -> Optional[CachedImage]:
        f = self.root / f"{image_id}.json"
        if not f.exists() or not self.path(image_id).exists():
            return None
        try:
            return CachedImage(**json.loads(f.read_text(encoding="utf-8")))
        except (ValueError, TypeError):
            log.warning("bad image metadata %s", f)
            return None

    # ---- query results --------------------------------------------------------------------------------------
    def _qfile(self, query: str, kind: str) -> Path:
        return self.root / f"q-{hashlib.sha1(f'{kind}|{query.lower().strip()}'.encode()).hexdigest()[:16]}.json"

    def save_query(self, query: str, kind: str, images: list[CachedImage]) -> None:
        self._ensure()
        self._qfile(query, kind).write_text(json.dumps([i.id for i in images]), encoding="utf-8")

    def load_query(self, query: str, kind: str) -> Optional[list[CachedImage]]:
        """None = never searched; [] = searched, nothing good enough."""
        f = self._qfile(query, kind)
        if not f.exists():
            return None
        ids = json.loads(f.read_text(encoding="utf-8"))
        imgs = [self.get(i) for i in ids]
        return [i for i in imgs if i is not None]
