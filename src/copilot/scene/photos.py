"""Real photos on the canvas (F-016 §4, C1 part 2): a thing's photo cutout and a place's landscape photo.

    thing  -> V1 image search (Wikipedia / Commons, CLIP re-rank: visuals.finder) for the noun, then the background
              removed by U^2-Net small (u2netp, ONNX, CPU, ~0.15 s; Apache-2.0, models/u2netp/, fetched once) -> a
              transparent PNG cached as data/assets/pictures/photo-<slug>.png. A cutout is kept only when the matte
              looks like one object (its share of the picture, not running off the edges, mostly solid) AND CLIP
              names the cutout itself as the noun ahead of concrete distractors (a chair, people, a dog ...: the
              search gave chairs for "table", players for "basketball", a dog with a stick for "stick")
    place  -> the same search for the place's view ("lunar surface", "underwater ocean", "<place> landscape"), a wide
              photo, used as it is (/media/<id>.jpg), drawn dimmed

A person is never searched (no photos of real people on a classroom screen): they keep their 3D picture. Blocked nouns
(scene.safety) are never searched. Everything here blocks: the controller runs it in a thread / as a task, after
the emoji is already shown, and patches the scene when it lands. No network: nothing changes."""
from __future__ import annotations

import logging
import os
import threading
from pathlib import Path
from typing import Any, Optional

import numpy as np

from copilot.core.config import PROJECT_ROOT
from copilot.scene import pictures, safety

log = logging.getLogger(__name__)

MODEL_DIR = PROJECT_ROOT / "models" / "u2netp"
MODEL_URL = "https://github.com/danielgatis/rembg/releases/download/v0.0.0/u2netp.onnx"
SIDE = 320
MEAN = np.array([0.485, 0.456, 0.406], dtype=np.float32)
STD = np.array([0.229, 0.224, 0.225], dtype=np.float32)
MAX_PX = 480              # a cutout is resized to fit this square
MIN_SHARE, MAX_SHARE = 0.04, 0.85   # the object's share of the photo
MAX_EDGE = 0.3            # at most this share of the photo's border may be the object (else it is a scene / a crop)
MAX_SIDE = 0.08           # a side with more of the object than this is a cut; two cut sides: not the whole thing
MIN_SOLID = 0.6           # of the object's pixels, this share fully opaque (a fog of half-alpha is not an object)
MIN_ONE = 0.8             # the biggest connected piece's share of the object (players, two spears, chairs: several)
GRID = 64                 # the matte is checked for pieces on this grid
MIN_ASPECT_PLACE = 1.25   # a place photo is a landscape
TRIES = 3                 # search results tried per noun
MIN_CLIP = 0.2            # the cutout vs "a photo of a <noun>" (CLIP ViT-B/32 cosine)
DISTRACTORS = ("a person", "a group of people", "people playing a sport", "a crowd", "a dog", "a cat", "a bird", "a chair", "a building", "a landscape",
               "a car", "a tree", "a hand", "text or a diagram", "a painting")
# what the backdrop photo of a place type is searched as (else "<place> landscape")
PLACE_QUERY = {"moon": "lunar surface", "mars": "surface of Mars", "water": "underwater ocean coral",
               "space": "outer space stars nebula", "sky": "blue sky clouds", "indoors": "{} interior",
               "street": "{} street"}


class Matting:
    """u2netp on CPU: a photo -> its foreground alpha (0..255), the photo's size."""

    def __init__(self, model_dir: Path = MODEL_DIR, threads: int = 2) -> None:
        self.model_dir = model_dir
        self.threads = threads
        self._sess: Any = None
        self._lock = threading.Lock()

    def ensure_downloaded(self) -> Path:
        path = self.model_dir / "u2netp.onnx"
        if not path.is_file():
            import httpx

            log.info("downloading u2netp -> %s", path)
            self.model_dir.mkdir(parents=True, exist_ok=True)
            r = httpx.get(MODEL_URL, timeout=60.0, follow_redirects=True)
            r.raise_for_status()
            tmp = path.with_suffix(".tmp")
            tmp.write_bytes(r.content)
            os.replace(tmp, path)
        return path

    def _session(self) -> Any:
        with self._lock:
            if self._sess is None:
                import onnxruntime as ort

                opts = ort.SessionOptions()
                opts.intra_op_num_threads = self.threads
                self._sess = ort.InferenceSession(str(self.ensure_downloaded()), opts,
                                                  providers=["CPUExecutionProvider"])
            return self._sess

    def alpha(self, img: Any) -> np.ndarray:
        from PIL import Image

        rgb = img.convert("RGB")
        x = np.asarray(rgb.resize((SIDE, SIDE), Image.BILINEAR), dtype=np.float32)
        x = (x / max(float(x.max()), 1e-6) - MEAN) / STD
        x = x.transpose(2, 0, 1)[None].astype(np.float32)
        sess = self._session()
        pred = sess.run(None, {sess.get_inputs()[0].name: x})[0][0, 0]
        pred = (pred - pred.min()) / max(float(pred.max() - pred.min()), 1e-6)
        m = Image.fromarray((pred * 255).astype(np.uint8)).resize(rgb.size, Image.BILINEAR)
        return np.asarray(m)


def judge(alpha: np.ndarray) -> str:
    """Why a matte is not one clean object ("" = it is)."""
    fg = alpha > 128
    share = float(fg.mean())
    if not MIN_SHARE <= share <= MAX_SHARE:
        return f"object share {share:.2f}"
    border = np.concatenate([fg[0], fg[-1], fg[:, 0], fg[:, -1]])
    if float(border.mean()) > MAX_EDGE:
        return f"runs off the edges ({border.mean():.2f})"
    cut = sum(float(side.mean()) > MAX_SIDE for side in (fg[0], fg[-1], fg[:, 0], fg[:, -1]))
    if cut >= 2:
        return f"cut off on {cut} sides"  # a tree trunk running out of the photo, a close-up
    some = alpha > 24
    solid = float((alpha > 200).sum()) / max(int(some.sum()), 1)
    if solid < MIN_SOLID:
        return f"not solid ({solid:.2f})"
    one = biggest_piece(fg)
    if one < MIN_ONE:
        return f"several objects (the biggest is {one:.2f})"
    return ""


def biggest_piece(fg: np.ndarray) -> float:
    """The biggest 8-connected piece's share of the foreground, on a GRID x GRID copy of the matte."""
    h, w = fg.shape
    ys = (np.arange(GRID) * h // GRID)
    xs = (np.arange(GRID) * w // GRID)
    g = fg[np.ix_(ys, xs)]
    total = int(g.sum())
    if not total:
        return 0.0
    seen = np.zeros_like(g, dtype=bool)
    best = 0
    for y0, x0 in zip(*np.nonzero(g)):
        if seen[y0, x0]:
            continue
        seen[y0, x0] = True
        stack, n = [(y0, x0)], 0
        while stack:
            y, x = stack.pop()
            n += 1
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    yy, xx = y + dy, x + dx
                    if 0 <= yy < GRID and 0 <= xx < GRID and g[yy, xx] and not seen[yy, xx]:
                        seen[yy, xx] = True
                        stack.append((yy, xx))
        best = max(best, n)
    return best / total


def cutout(img: Any, alpha: np.ndarray) -> Any:
    """The photo with the matte as its alpha, cropped to the object (a small margin), at most MAX_PX square."""
    from PIL import Image

    rgba = img.convert("RGBA")
    a = np.where(alpha > 16, alpha, 0).astype(np.uint8)
    rgba.putalpha(Image.fromarray(a))
    ys, xs = np.nonzero(a > 128)
    pad = int(0.03 * max(img.size))
    box = (max(int(xs.min()) - pad, 0), max(int(ys.min()) - pad, 0), min(int(xs.max()) + pad, img.size[0]),
           min(int(ys.max()) + pad, img.size[1]))
    out = rgba.crop(box)
    out.thumbnail((MAX_PX, MAX_PX))
    return out


def slug(noun: str) -> str:
    return "photo-" + pictures.slug(noun)


class Photos:
    """finder: visuals.finder.ImageFinder (search + CLIP); matting: Matting. find() / place() are async (the search
    awaits the network, the matting runs in a thread)."""

    def __init__(self, finder: Any, matting: Optional[Matting] = None, pics_dir: Optional[Path] = None) -> None:
        self.finder = finder
        self.matting = matting or Matting()
        self.pics_dir = pics_dir or pictures.PICS_DIR
        self.misses: set[str] = set()       # nouns whose photos were all judged unusable this run (asked once)
        self.place_misses: set[str] = set()  # places whose photos were all too narrow this run
        self.places: dict[str, str] = {}    # place -> its photo this run

    @staticmethod
    def wanted(noun: str) -> bool:
        """A thing worth a photo: a said noun, not a person, not a shape, not blocked."""
        return bool(noun.strip()) and not pictures.person(noun) and not pictures.form_of(noun) \
            and not safety.blocked(noun)

    def cached(self, noun: str) -> str:
        return pictures.cached(slug(noun), self.pics_dir)

    async def thing(self, noun: str) -> str:
        """The noun's cutout URL, or "" (none good, offline, a person)."""
        import asyncio

        if not self.wanted(noun) or noun in self.misses:
            return ""
        have = self.cached(noun)
        if have:
            return have
        res = await self.finder.find(noun, "photo")
        why = res.reason or "no result"
        for im in res.images[:TRIES]:
            url, why = await asyncio.to_thread(self._cut, noun, self.finder.cache.path(im.id))
            if url:
                log.info("[SCENE] photo %r: %s (%s)", noun, url, im.title[:60])
                return url
        log.info("[SCENE] photo %r: none (%s)", noun, why)
        if res.images:  # only a definite "no good photo"; a failed / slow search may work in the next scene
            self.misses.add(noun)
        return ""

    def _cut(self, noun: str, path: Path) -> tuple[str, str]:
        from PIL import Image

        try:
            img = Image.open(path)
            img.load()
        except Exception as err:  # not on disk / not an image
            return "", f"unreadable: {err}"
        alpha = self.matting.alpha(img)
        why = judge(alpha)
        if why:
            return "", why
        out = cutout(img, alpha)
        why = self._names(noun, out)
        if why:
            return "", why
        self.pics_dir.mkdir(parents=True, exist_ok=True)
        s = slug(noun)
        tmp = self.pics_dir / f".{s}.{threading.get_ident()}.tmp"
        out.save(tmp, "PNG", optimize=True)
        os.replace(tmp, self.pics_dir / f"{s}.png")
        return pictures.URL.format(s), ""

    def _names(self, noun: str, out: Any) -> str:
        """Why CLIP does not see the noun in the cutout ("" = it does: the noun ahead of every distractor)."""
        scorer = getattr(self.finder, "scorer", None)
        if scorer is None:
            return ""  # CLIP not loaded yet: the matte checks only
        from PIL import Image

        flat = Image.new("RGB", out.size, (255, 255, 255))
        flat.paste(out, (0, 0), out)
        h = pictures.assets.head(noun)
        texts = [f"a photo of a {noun}"] + [f"a photo of {d}" for d in DISTRACTORS if h not in d.split()]
        t = scorer.embed_texts(texts)
        v = scorer.embed_images([flat])[0]
        sims = t @ v
        best = int(np.argmax(sims))
        if best != 0:
            return f"CLIP sees {texts[best][11:]!r} ({float(sims[best]):.2f} vs {float(sims[0]):.2f})"
        if float(sims[0]) < MIN_CLIP:
            return f"CLIP {float(sims[0]):.2f} < {MIN_CLIP}"
        return ""

    def cached_place(self, name: str) -> str:
        return self.places.get(name, "")

    async def place(self, name: str) -> str:
        """A landscape photo of the place (/media/<id>.jpg), or ""."""
        if not name.strip() or safety.blocked(name) or name in self.place_misses:
            return ""
        if name in self.places:
            return self.places[name]
        q = PLACE_QUERY.get(pictures.place_type(name), "{} landscape")
        res = await self.finder.find(q.format(name) if "{}" in q else q, "photo")
        im = next((i for i in res.images if i.aspect >= MIN_ASPECT_PLACE), None)
        if im is None:
            if res.images:
                self.place_misses.add(name)
            log.info("[SCENE] place photo %r: none (%s)", name, res.reason or "no wide photo")
            return ""
        log.info("[SCENE] place photo %r: %s (%s)", name, im.url, im.title[:60])
        self.places[name] = im.url
        return im.url
