"""Real-looking pictures for the canvas (F-016 §4) and the 0-token "picturable" filter of Imagine Mode (§6).

Picture ladder for a thing's said noun (the first that answers):
    1. the teacher's pick (/control Picture)                           kept across edits (look.pick "teacher")
    2. a cached picture (data/assets/pictures/<slug>.png)             instant
    3. (C1 part 2) a photo cutout: V1 search + CLIP + ONNX matting
    4. a Fluent 3D emoji (microsoft/fluentui-emoji, MIT): the index (fluent3d.json, tools/fluent_index.py) matched by
       the noun's words, else by meaning (MiniLM); its PNG fetched once (jsDelivr) in a thread, re-encoded, cached
    5. a Tabler icon, then an LLM glyph (scene.assets)
A shape noun (cube, sphere, cylinder ...) is drawn as a shaded solid instead (`look.form`). Blocked nouns
(scene.safety) get no picture. Offline: the cache, the icons and the illustrated backdrops only."""
from __future__ import annotations

import io
import json
import logging
import os
import re
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import numpy as np

from copilot.core.config import PROJECT_ROOT
from copilot.scene import assets, safety

log = logging.getLogger(__name__)

INDEX = Path(__file__).resolve().parent / "fluent3d.json"
PICS_DIR = PROJECT_ROOT / "data" / "assets" / "pictures"
URL = "/scene-pic/{}.png"
SLUG = re.compile(r"[a-z0-9-]{1,60}")
MIN_SIMILARITY = 0.70     # noun vs an emoji's name (MiniLM cosine)
MAX_PX = 320              # a fetched picture is resized to fit this square
MAX_BYTES = 2_000_000
FETCH_TIMEOUT_S = 6.0

FORMS = ("cube", "cuboid", "sphere", "cylinder", "cone", "pyramid", "prism", "hemisphere")
# a place's words -> its backdrop type (stage.backdrop); a place not listed: "plain" with its name
PLACES: dict[str, tuple[str, ...]] = {
    "water": ("ocean", "sea", "underwater", "river", "lake", "pond", "aquarium", "pool", "swimming pool", "water",
              "seabed", "sea bed", "ocean floor", "deep sea"),
    "sky": ("sky", "air", "clouds", "cloud", "atmosphere"),
    "space": ("space", "outer space", "universe", "galaxy", "orbit", "solar system", "moon surface"),
    "mountain": ("mountain", "mountains", "hill", "hills", "valley", "cliff", "volcano"),
    "street": ("street", "road", "city", "town", "highway", "traffic", "bridge", "railway", "track", "station"),
    "nature": ("forest", "jungle", "park", "garden", "field", "farm", "meadow", "grass", "countryside", "village"),
    "indoors": ("room", "classroom", "house", "home", "kitchen", "lab", "laboratory", "office", "library", "hall",
                "bedroom", "school", "inside a bus", "bus", "train", "car", "shop"),
    "beach": ("beach", "shore", "coast", "island"),
    "desert": ("desert", "sand dunes"),
    "snow": ("snow", "ice", "arctic", "antarctica", "glacier", "north pole", "south pole"),
}
# lines that may need the canvas (Imagine Mode): a relation word, a motion verb (0 tokens)
SPATIAL = re.compile(r"\b(?:on top of|on|under(?:neath)?|beneath|inside|in(?:to)?|above|below|over|behind|"
                     r"in front of|next to|beside|near|between|around|holding|attached to|carrying|riding)\b", re.I)
MOTION = re.compile(r"\b(?:fl(?:y|ies|ying|ew)|driv(?:e|es|ing)|drove|walk\w*|run(?:s|ning)?|ran|fall\w*|fell|"
                    r"drop\w*|throw\w*|threw|toss\w*|bounc\w*|sink\w*|sank|float\w*|slid\w*|roll\w*|rotat\w*|"
                    r"spin\w*|spun|grow\w*|shrink\w*|follow\w*|chas\w*|orbit\w*|shak\w*|carr(?:y|ies|ying)|push\w*|"
                    r"pull\w*|brak\w*|stop\w*|turns? into|becom\w*|emit\w*|collid\w*|crash\w*|jump\w*|swim\w*|"
                    r"swam|launch\w*|appear\w*|vanish\w*|disappear\w*)\b", re.I)
UNIT_NUM = re.compile(r"\b\d+(?:\.\d+)?\s*(?:m/s|km/h|kmph|mps|m|cm|km|kg|g|s|seconds?|metres?|meters?|"
                      r"kilometres?|degrees?)\b", re.I)
# emoji / icon words too common in talk to mean "draw something" (a face, a hand, a sign are abstract here)
_NOT_PICTURABLE = {"face", "hand", "hands", "sign", "button", "mark", "symbol", "light", "time", "point", "one",
                   "two", "three", "up", "down", "new", "free", "top", "back", "end", "soon", "on", "id", "ok",
                   "cool", "question", "exclamation", "check", "cross", "record", "play", "pause", "stop", "input",
                   "information", "letter", "keycap", "zone", "type", "power", "level", "matter", "change",
                   "charge", "current", "force", "energy", "work", "mass", "body", "object", "balance", "page",
                   "file", "note", "notes", "wave", "air", "field", "spring", "mean", "value", "case", "order",
                   "class", "set", "range", "rest", "side", "part", "way", "kind", "form", "line", "speed",
                   # classroom talk about the lecture itself
                   "slide", "slides", "board", "screen", "lecture", "chapter", "lesson", "example", "diagram",
                   "human", "machine", "system", "model", "idea", "thing", "things", "stuff"}
# common classroom nouns whose emoji has another name (the said word first, then this name)
ALIAS = {"book": "closed book", "car": "automobile", "plane": "airplane", "aeroplane": "airplane", "jet": "airplane",
         "tree": "deciduous tree", "earth": "globe showing europe-africa", "globe": "globe showing europe-africa",
         "boat": "motor boat", "stone": "rock", "ball": "soccer ball", "football": "soccer ball", "box": "package",
         "parcel": "package", "bulb": "light bulb", "lamp": "light bulb", "planet": "ringed planet",
         "moon": "full moon", "atom": "atom symbol", "phone": "mobile phone", "computer": "desktop computer",
         "cup": "hot beverage", "bottle": "baby bottle", "train": "locomotive", "cloud": "cloud", "wave": "water wave",
         "bike": "bicycle", "cycle": "bicycle", "ship": "passenger ship", "person": "person standing",
         "kid": "child", "flower": "blossom", "mug": "hot beverage", "student": "student", "rain": "cloud with rain",
         "you": "person standing", "me": "person standing", "teacher": "teacher", "passenger": "person standing"}

@lru_cache(maxsize=1)
def index() -> dict[str, str]:
    """Fluent 3D emoji: name ("closed book") -> its PNG path in the repo."""
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        log.warning("[SCENE] no emoji index (%s): pictures are icons only", INDEX)
        return {}
    return {k: v for k, v in data["emoji"].items() if not safety.blocked(k)}


@lru_cache(maxsize=1)
def _base() -> str:
    try:
        return json.loads(INDEX.read_text(encoding="utf-8"))["base"]
    except (OSError, ValueError, KeyError):
        return ""


@lru_cache(maxsize=1)
def words() -> frozenset[str]:
    """Nouns that name a picture: one- and two-word emoji names' last word, the icons' words, places, forms."""
    out: set[str] = set(FORMS)
    for name in index():
        ws = name.split()
        if len(ws) <= 2 and ws[-1].isalpha():
            out.add(ws[-1])
    for ic in assets.icons().values():
        out.update(w for w in ic["words"] if " " not in w)
    for ws in PLACES.values():
        out.update(w for w in ws if " " not in w)
    # a verb's -ing form is not a thing ("a boat crossing a river"), except these nouns
    ing = {"building", "ring", "king", "swing", "wing", "string", "ceiling", "painting"}
    return frozenset(w for w in out if len(w) >= 3 and (not w.endswith("ing") or w in ing)) - _NOT_PICTURABLE


def picturable(text: str, names: Optional[list[str]] = None) -> bool:
    """Imagine Mode's 0-token filter: a picture noun, a relation word next to a noun, a motion verb, a number with a
    unit, or a thing already in the scene. Else the line makes no call."""
    low = text.lower()
    toks = [assets.singular(w) for w in re.findall(r"[a-z]+", low)]
    if any(t in words() for t in toks) or UNIT_NUM.search(text) or MOTION.search(text):
        return True
    return any(n and re.search(rf"\b{re.escape(n.lower())}(?:e?s)?\b", low) for n in (names or []))


def place_type(name: str) -> str:
    low = " ".join(re.findall(r"[a-z]+", (name or "").lower()))
    for typ, ws in PLACES.items():
        if any(re.search(rf"\b{re.escape(w)}\b", low) for w in sorted(ws, key=len, reverse=True)):
            return typ
    return "plain"


def form_of(noun: str) -> str:
    h = assets.head(noun)
    return h if h in FORMS else ""


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:60]


class Emoji:
    """Matches a said noun to a Fluent 3D emoji name. embedder: understanding.embedder (optional)."""

    def __init__(self, embedder: Any = None) -> None:
        self.embedder = embedder
        self._vecs: Optional[np.ndarray] = None
        self._names: list[str] = []
        self._seen: dict[str, str] = {}

    def warm(self) -> None:
        self._embedded()

    def _embedded(self) -> Optional[np.ndarray]:
        if self.embedder is None or not index():
            return None
        if self._vecs is None:
            self._names = list(index())
            self._vecs = self.embedder.embed(self._names)
        return self._vecs

    def match(self, noun: str) -> str:
        """The emoji name for a noun ("" = none): the noun itself, then a name ending in its head word ("closed
        book" for "book"), then one containing it, shortest first; then the nearest by meaning."""
        if not noun.strip() or safety.blocked(noun):
            return ""
        h = assets.head(noun)
        if not h:
            return ""
        key = " ".join(re.findall(r"[a-z]+", noun.lower()))
        if key in self._seen:
            return self._seen[key]
        idx = index()
        hit = ""
        for cand in (key, " ".join(assets.singular(w) for w in key.split()), h, ALIAS.get(h, ""), h + "s"):
            if cand and cand in idx:
                hit = cand
                break
        if not hit:
            ends = sorted((n for n in idx if n.split()[-1] in (h, h + "s")), key=lambda n: (len(n), n))
            has = sorted((n for n in idx if h in n.split()), key=lambda n: (len(n), n))
            hit = (ends or has or [""])[0]
        if not hit:
            vecs = self._vecs  # by meaning only once warm() embedded the index (off the event loop)
            if vecs is not None:
                q = self.embedder.embed([key])[0]
                sims = vecs @ q
                i = int(np.argmax(sims))
                if float(sims[i]) >= MIN_SIMILARITY:
                    hit = self._names[i]
        self._seen[key] = hit
        return hit


def cached(name: str, pics_dir: Optional[Path] = None) -> str:
    """The picture's URL when it is on disk, else ""."""
    s = slug(name)
    return URL.format(s) if s and ((pics_dir or PICS_DIR) / f"{s}.png").is_file() else ""


def fetch(name: str, pics_dir: Optional[Path] = None, client: Any = None) -> str:
    """Blocking (run it in a thread): the emoji's PNG, downloaded once, decoded and re-encoded (≤ MAX_PX, never
    the raw bytes), cached. Its URL, or "" (offline, not found, not an image)."""
    s = slug(name)
    path = index().get(name)
    if not s or not path:
        return ""
    have = cached(name, pics_dir)
    if have:
        return have
    import httpx
    from PIL import Image

    url = _base() + "/".join(_quote(p) for p in path.split("/"))
    try:
        r = (client or httpx).get(url, timeout=FETCH_TIMEOUT_S, follow_redirects=True)
        if r.status_code != 200 or len(r.content) > MAX_BYTES:
            log.info("[SCENE] picture %r: HTTP %s", name, r.status_code)
            return ""
        img = Image.open(io.BytesIO(r.content))
        img.load()
        img = img.convert("RGBA")
        img.thumbnail((MAX_PX, MAX_PX))
    except Exception as err:  # offline, a timeout, not an image: the icon / glyph stays
        log.info("[SCENE] picture %r not fetched: %s", name, err)
        return ""
    d = pics_dir or PICS_DIR
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{s}.{threading.get_ident()}.tmp"  # written whole, then renamed: never seen half-written
    img.save(tmp, "PNG", optimize=True)
    os.replace(tmp, d / f"{s}.png")
    return URL.format(s)


def _quote(part: str) -> str:
    from urllib.parse import quote
    return quote(part)
