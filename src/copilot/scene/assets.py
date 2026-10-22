"""Pictures for a scene's bodies (F-015 L2a): a rocket looks like a rocket, a train like a train.

A body keeps its kind's physics (a rocket is a `car` body); only its picture changes, chosen for the noun the teacher
said, in this order:
    1. an offline icon (web/vendor/icons/scene-icons.js, Tabler Icons, MIT): the noun is one of the icon's words, else
       the nearest icon by meaning (MiniLM embedding, when the app has loaded it) above MIN_SIMILARITY
    2. an LLM glyph: one call draws path data on the icons' 24 x 24 grid; cleaned (path commands and numbers only,
       no script / href / style, <= MAX_GLYPH chars) and cached in data/assets/glyphs/ (a noun is drawn once)
    3. the kind's own drawing (a ball, a block, a car) only when nothing matches: never a car for a rocket
The teacher's pick (/control Picture: an icon, an uploaded image or the kind's drawing) is kept across edits
(`look.pick` "teacher")."""
from __future__ import annotations

import json
import logging
import re
import time
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, Sequence

import numpy as np

from copilot.scene.spec import BODY_KINDS, Entity, SceneSpec

PICTURED = BODY_KINDS + ("thing",)  # F-016: a thing's icon / glyph is its fallback picture (scene.pictures first)

log = logging.getLogger(__name__)

ICONS_JS = Path(__file__).resolve().parents[3] / "web" / "vendor" / "icons" / "scene-icons.js"
GLYPH_DIR = Path("data/assets/glyphs")
MIN_SIMILARITY = 0.63     # noun vs an icon's words (MiniLM cosine): below it, no icon (a glyph is drawn instead)
MAX_GLYPH = 4096
# nouns a kind's own drawing already shows (a ball rolls with its spoke, a block, a car): no icon
OWN = {"ball": "ball", "stone": "ball", "rock": "ball", "pebble": "ball", "marble": "ball", "sphere": "ball",
       "block": "block", "box": "block", "crate": "block", "brick": "block", "cart": "block", "mass": "block",
       "car": "car", "particle": "particle", "body": "particle", "object": "particle", "dot": "particle",
       "point": "particle", "electron": "particle", "proton": "particle", "atom": "particle", "molecule": "particle"}
_IRREGULAR = {"men": "man", "women": "woman", "children": "child", "people": "person", "geese": "goose",
              "mice": "mouse", "feet": "foot", "teeth": "tooth"}
_PATH_OK = re.compile(r"^[MmLlHhVvCcSsQqTtAaZz0-9eE.,\s+-]+$")


@lru_cache(maxsize=1)
def icons() -> dict[str, dict[str, Any]]:
    """The icon set: name -> {words, tags, nodes} (the JS module is the one source for Python and the renderer)."""
    text = ICONS_JS.read_text(encoding="utf-8")
    return json.loads(text[text.index("= {") + 2:text.rindex("}") + 1])


def singular(w: str) -> str:
    w = w.lower()
    if w in _IRREGULAR:
        return _IRREGULAR[w]
    for end, to in (("ies", "y"), ("ses", "s"), ("ches", "ch"), ("shes", "sh"), ("xes", "x"), ("s", "")):
        if w.endswith(end) and len(w) > max(3, len(end) + 1) and not w.endswith(("ss", "us", "is")):
            return w[: -len(end)] + to
    return w


def head(noun: str) -> str:
    """The noun's last word, singular ("two toy trains" -> "train")."""
    words = re.findall(r"[a-z]+", noun.lower())
    return singular(words[-1]) if words else ""


class Pictures:
    """Matches a said noun to an icon. embedder: understanding.embedder (optional: without it, exact words only)."""

    def __init__(self, embedder: Any = None) -> None:
        self.embedder = embedder
        self._vecs: Optional[np.ndarray] = None
        self._names: list[str] = []
        self._word: dict[str, str] = {}
        for name, ic in icons().items():
            for w in ic["words"]:
                self._word.setdefault(w, name)
        self._seen: dict[str, str] = {}

    def _embedded(self) -> Optional[np.ndarray]:
        if self.embedder is None:
            return None
        if self._vecs is None:
            self._names = list(icons())
            self._vecs = self.embedder.embed([" ".join(icons()[n]["words"][:4]) for n in self._names])
        return self._vecs

    def warm(self) -> None:
        """Embed the icon set now (the app calls it off the event loop at start)."""
        self._embedded()

    def ranked(self, noun: str, k: int = 8) -> list[tuple[str, float]]:
        """Icons by meaning (needs the embedder), best first."""
        vecs = self._embedded()
        if vecs is None or not noun.strip():
            return []
        q = self.embedder.embed([noun.strip().lower()])[0]
        sims = vecs @ q
        order = np.argsort(-sims)[:k]
        return [(self._names[i], float(sims[i])) for i in order]

    def match(self, noun: str) -> str:
        """The icon for a said noun, or "" (a noun its kind's drawing shows, or nothing close enough)."""
        h = head(noun)
        if not h or h in OWN:
            return ""
        if h in self._seen:
            return self._seen[h]
        words = [singular(w) for w in re.findall(r"[a-z]+", noun.lower())]
        hit = self._word.get(h) or next((self._word[w] for w in reversed(words) if w in self._word), "")
        if not hit:
            best = self.ranked(h, 1)
            if best and best[0][1] >= MIN_SIMILARITY:
                hit = best[0][0]
        self._seen[h] = hit
        return hit

    def choices(self, noun: str, k: int = 8) -> list[str]:
        """The teacher's choices for a noun: the matched icon, then the nearest by meaning, then word hits."""
        out: list[str] = []
        m = self.match(noun)
        if m:
            out.append(m)
        out += [n for n, _ in self.ranked(head(noun) or noun, k)]
        q = noun.lower().strip()
        if q:
            out += [n for n, ic in icons().items() if any(w.startswith(q) for w in ic["words"] + ic["tags"])]
        return list(dict.fromkeys(out))[:k]

    def resolve(self, scene: SceneSpec, glyph_dir: Optional[Path] = None) -> SceneSpec:
        """Each body's / thing's picture for its noun (the teacher's pick is kept); a cached glyph when no icon
        matches. A thing drawn as a solid (look.form) needs none; a thing that turns into another gets that one's icon."""
        ents: list[Entity] = []
        changed = False
        for e in scene.entities:
            lk = e.look
            if e.kind == "thing" and lk.to_noun and not lk.to_icon and not lk.to_emoji:
                to = self.match(lk.to_noun)
                if to:
                    lk = lk.model_copy(update={"to_icon": to})
                    e = e.model_copy(update={"look": lk})
                    changed = True
            if e.kind not in PICTURED or lk.pick == "teacher" or not lk.noun or lk.icon or lk.glyph or lk.form:
                ents.append(e)
                continue
            icon = self.match(lk.noun)
            glyph = "" if icon else cached_glyph(lk.noun, glyph_dir)
            if icon or glyph:
                e = e.model_copy(update={"look": lk.model_copy(update={"icon": icon, "glyph": glyph})})
                changed = True
            ents.append(e)
        return scene.model_copy(update={"entities": ents}) if changed else scene


def needs_glyph(e: Entity) -> bool:
    """A body whose said noun has no icon and no glyph yet (and is not one its kind's drawing shows)."""
    lk = e.look
    return (e.kind in PICTURED and lk.pick == "auto" and bool(lk.noun) and not lk.icon and not lk.glyph
            and not lk.emoji and not lk.form and head(lk.noun) not in OWN)


# ---- LLM glyphs --------------------------------------------------------------------------------------------------
def _slug(noun: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", head(noun) or noun.lower()).strip("-")[:40]


def cached_glyph(noun: str, glyph_dir: Optional[Path] = None) -> str:
    p = (glyph_dir or GLYPH_DIR) / f"{_slug(noun)}.json"
    try:
        return clean(json.loads(p.read_text(encoding="utf-8")).get("d", ""))
    except (OSError, ValueError, AttributeError):
        return ""


def clean(d: Any) -> str:
    """Path data only: commands and numbers (no script, href, style or tags), <= MAX_GLYPH chars, starting with a
    move, its numbers on the 24 x 24 grid (a little overshoot allowed). Anything else: ""."""
    if not isinstance(d, str):
        return ""
    d = " ".join(d.split())
    if not d or len(d) > MAX_GLYPH or not _PATH_OK.match(d) or d[0] not in "Mm":
        return ""
    nums = [float(x) for x in re.findall(r"-?\d*\.?\d+(?:[eE][-+]?\d+)?", d)]
    if len(nums) < 4 or any(abs(v) > 30 for v in nums):
        return ""
    return d


GLYPH_SYSTEM = """You draw one small line icon for a classroom diagram, on a 24 x 24 grid (like Tabler / Lucide icons:
2 px strokes, no fill). Side view, facing right, simple and recognisable. Output ONLY one JSON object:
{"d": "<SVG path data>"}
Path data uses only M L H V C Q A Z (absolute) with numbers between 1 and 23; at most 12 subpaths, under 1500
characters. No other text."""
GLYPH_MAX_TOKENS = 700
GLYPH_EST = 300


async def glyph(router: Any, noun: str, glyph_dir: Optional[Path] = None) -> str:
    """One LLM call: path data for the noun's head word, cleaned and cached. "" when refused or unusable."""
    word = head(noun)
    if not word or word in OWN:
        return ""
    d = cached_glyph(word, glyph_dir)
    if d:
        return d
    msgs = [{"role": "system", "content": GLYPH_SYSTEM}, {"role": "user", "content": f"Draw: {word}"}]
    r = await router.complete(msgs, est_tokens=GLYPH_EST, max_tokens=GLYPH_MAX_TOKENS,
                              deadline=time.monotonic() + 14, timeout_s=12.0)
    text = r.response.text or ""
    try:
        obj = json.loads(text[text.index("{"):text.rindex("}") + 1])
    except ValueError:
        obj = {}
    d = clean(obj.get("d") if isinstance(obj, dict) else None)
    tokens = r.response.prompt_tokens + r.response.completion_tokens
    log.info("[SCENE] glyph %r: %s (%d tokens)", word, f"{len(d)} chars" if d else "refused (not clean path data)",
             tokens)
    if d:
        p = glyph_dir or GLYPH_DIR
        p.mkdir(parents=True, exist_ok=True)
        (p / f"{_slug(word)}.json").write_text(json.dumps({"noun": word, "d": d}), encoding="utf-8")
    return d


def search(q: str, pictures: Optional[Pictures] = None, k: int = 12) -> list[dict[str, Any]]:
    """/control Picture: icons for the teacher's word (name, its nodes for the preview)."""
    p = pictures or Pictures()
    return [{"name": n, "nodes": icons()[n]["nodes"]} for n in p.choices(q, k)]


__all__: Sequence[str] = ("Pictures", "icons", "clean", "glyph", "cached_glyph", "needs_glyph", "search", "head")
