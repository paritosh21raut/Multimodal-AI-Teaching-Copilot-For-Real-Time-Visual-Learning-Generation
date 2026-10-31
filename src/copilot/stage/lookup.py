"""The lookup ladder (F-017 §4, E3): what draws a said noun on the stage. Never a wrong picture: a rung that is not sure
passes the noun down, and the last rung always draws (a labelled box).

    1 exact      a kit / species / backdrop / cast name or synonym (stage.catalog)
    2 nearest    MiniLM nearest kit name above THRESHOLDS[kind] (set on tests/fixtures/stage/lookup_nouns.json)
    3 near       the LLM's `near` stand-in noun (a catalog name: the validator checks it)
    4 shape      a generic kit shape for a shape word (pole -> rod, barrel -> cylinder, brick -> box)
    5 icon       a Fluent flat icon recoloured to the palette (stage.icons; fetched in the background, cached)
    6 box        a rounded box labelled with the said word

Rungs 2–6 show the said word as a chip on the stage (the picture is a stand-in). A person noun the cast does not know
("doctor") is a person all the same (any cast row); a place the backdrops do not know is the outdoor backdrop. Picks
are cached per noun; nouns that fall to rung 4 or below are logged once to data/assets/stage/misses.jsonl (the kit
grows from them).
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import numpy as np

from copilot.scene import safety, sizes
from copilot.stage import catalog, icons

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
MISSES = ROOT / "data" / "assets" / "stage" / "misses.jsonl"
# MiniLM cosine said noun vs kit name, per kind: the lowest that picks no wrong row of the 157 labelled nouns in
# tests/fixtures/stage/lookup_nouns.json (max wrong: prop 0.742 plug -> rope, animal 0.658 donkey -> horse, place
# 0.499 forest -> garden), rounded up (tests/unit/test_stage_lookup.py checks it)
THRESHOLDS = {"prop": 0.75, "animal": 0.70, "place": 0.55}

# rung 4: shape words -> a generic kit shape (catalog ids); a shape is never a wrong picture of the thing
SHAPES: dict[str, tuple[str, ...]] = {
    "rod": ("rod", "stick", "pole", "bar", "pipe", "beam", "lever", "staff", "baton", "cane", "wand", "shaft", "axle",
            "needle", "skewer", "broom", "mop"),
    "cylinder": ("cylinder", "can", "tin", "drum", "barrel", "tube", "jar", "tank", "canister", "column", "pillar",
                 "log", "roller", "pot"),
    "plate": ("plate", "sheet", "slab", "tray", "disc", "disk", "panel", "card", "mirror", "tile", "lid", "board"),
    "ball": ("sphere", "orb", "marble", "bead", "bubble", "drop", "droplet", "pebble", "pellet", "ball bearing",
             "bowling ball", "cannonball", "cannon ball"),
    "crate": ("block", "cube", "cuboid", "brick", "parcel", "package", "container", "chest", "case", "suitcase",
              "carton", "packet", "weight", "mass"),
    "lens": ("lens", "magnifier", "magnifying glass", "spectacles"),
    "spring": ("coil", "spring", "slinky"),
    "fulcrum": ("wedge", "prism", "doorstop"),
    "cloud": ("smoke", "steam", "fog", "mist", "vapour", "vapor", "gas"),
    "wire": ("string", "thread", "cable", "chain", "cord", "line"),
    "planet": ("star", "asteroid", "comet", "satellite moon"),
}
SHAPE_OF = {w: s for s, ws in SHAPES.items() for w in ws}


@dataclass(frozen=True)
class Pick:
    draw: str                  # kit id | cast:<row> | species:<id> | backdrop:<id> | ground | fluid | icon:<slug> | box
    size: tuple[float, float]  # metres
    rung: int                  # 1..6
    src: str = ""              # icon: its URL
    via: str = ""              # the stand-in name (rungs 2–5)


def _key(w: str) -> str:
    return " ".join(re.findall(r"[a-z]+", w.lower()))


def _head(w: str) -> str:
    k = _key(w).split()
    return k[-1] if k else ""


@dataclass
class Ladder:
    embedder: Any = None          # understanding.embedder (MiniLM); None: rung 2 is skipped
    emoji: Any = None             # scene.pictures.Emoji (name matcher for rung 5); None: a plain name match
    icon_dir: Optional[Path] = None
    misses_path: Optional[Path] = None
    fetch: bool = True            # False: cached icons only (tests, replays)
    log_misses: bool = True
    thresholds: dict[str, float] = field(default_factory=lambda: dict(THRESHOLDS))
    cache: dict[tuple[str, str], Pick] = field(default_factory=dict)
    pending: set[str] = field(default_factory=set)   # icon names being fetched
    failed: set[str] = field(default_factory=set)    # ... and those that did not come
    missed: set[str] = field(default_factory=set)
    on_icon: Any = None           # callback(name) when a fetched icon lands (the controller rebuilds the stage)
    _vecs: dict[str, tuple[list[tuple[str, dict]], np.ndarray]] = field(default_factory=dict)

    # ---------- rung 2 ----------
    def _rows(self, kind: str) -> list[tuple[str, dict]]:
        c = catalog.catalog()
        key = {"animal": "species", "place": "backdrops"}.get(kind, "props")
        return [(n, r) for r in c[key] for n in dict.fromkeys([r["id"].replace("_", " ")] + list(r["names"]))]

    def nearest(self, kind: str, noun: str) -> Optional[tuple[str, dict, float]]:
        """The kit name nearest by meaning, its row and the cosine (None without an embedder)."""
        if self.embedder is None:
            return None
        key = {"animal": "species", "place": "backdrops"}.get(kind, "props")
        if key not in self._vecs:
            rows = self._rows(kind)
            self._vecs[key] = (rows, self.embedder.embed([n for n, _ in rows]))
        rows, vecs = self._vecs[key]
        q = self.embedder.embed([_key(noun)])[0]
        sims = vecs @ q
        i = int(np.argmax(sims))
        return rows[i][0], rows[i][1], float(sims[i])

    def warm(self) -> None:
        for k in ("prop", "animal", "place"):
            self.nearest(k, "box")

    # ---------- the ladder ----------
    def pick(self, kind: str, w: str, near: Optional[str], attr: list[str], used_cast: set[str]) -> Optional[Pick]:
        """What draws the noun (None: a blocked word). Rung 1 for a person is the cast."""
        if safety.blocked(w):
            return None
        if kind == "agent" and not catalog.personish(w):
            kind = "animal" if catalog.species(w) else "prop"  # "rocket" said as an agent: the thing, never a person
        d = catalog.resolve(kind, w, None, attr, used_cast)
        if d is not None:
            return Pick(d.draw, d.size, 1)
        if kind == "agent":  # a person noun the table does not know ("plumber"): a person all the same
            row = catalog.pick_cast("person", attr, used_cast)
            if row is None:
                return None
            c = catalog.cast()[row]
            return Pick(f"cast:{row}", (0.45 * c["height_m"] / 1.75, c["height_m"]), 2, via="person")
        ck = (kind, _key(w) + "|" + (near or ""))
        if ck in self.cache:
            return self.cache[ck]
        p = self._climb(kind, w, near, attr, used_cast)
        if p.rung != 6 or not self._icon_coming(w):
            self.cache[ck] = p
        if p.rung >= 4:
            self._miss(kind, w, near, p)
        return p

    def _climb(self, kind: str, w: str, near: Optional[str], attr: list[str], used_cast: set[str]) -> Pick:
        if kind == "place":
            hit = self.nearest(kind, w)
            if hit and hit[2] >= self.thresholds["place"]:
                return Pick(f"backdrop:{hit[1]['id']}", (0.0, 0.0), 2, via=hit[0])
            if near:
                d = catalog.resolve(kind, near, None, attr, used_cast)
                if d is not None:
                    return Pick(d.draw, d.size, 3, via=near)
            return Pick("backdrop:outdoor", (0.0, 0.0), 4, via="outdoor")
        k2 = "animal" if kind == "animal" else "prop"
        hit = self.nearest(k2, w)
        if hit and hit[2] >= self.thresholds[k2]:
            r = hit[1]
            draw = f"species:{r['id']}" if kind == "animal" else r["id"]
            return Pick(draw, tuple(r["size_m"]), 2, via=hit[0])
        if near:
            d = catalog.resolve(kind if kind != "surface" else "prop", near, None, attr, used_cast)
            if d is None and kind == "animal":
                d = catalog.resolve("prop", near, None, attr, used_cast)
            if d is not None:
                return Pick(d.draw, d.size, 3, via=near)
        h = sizes.typical(w)
        shape = SHAPE_OF.get(_key(w)) or SHAPE_OF.get(_head(w))
        if shape:
            row = catalog.prop(shape)
            if row:
                sw, sh = row["size_m"]
                k = h / max(sw, sh) if _key(w) in sizes.TYPICAL or _head(w) in sizes.TYPICAL else 1.0
                return Pick(row["id"], (round(sw * k, 3), round(sh * k, 3)), 4, via=shape)
        name = self._icon_name(w)
        if name:
            url = icons.cached(name, self.icon_dir)
            if url:
                return Pick(f"icon:{url.rsplit('/', 1)[-1][:-4]}", (h, h), 5, src=url, via=name)
            self.start_fetch(name)
        return Pick("box", (round(max(0.4, h * 1.4), 3), round(max(0.3, h), 3)), 6)

    # ---------- icons ----------
    def _icon_name(self, w: str) -> str:
        """An icon named by the head noun ("flying bird" -> bird, never "flying disc"; test34): the matcher's pick
        counts only when its name holds the head word (or the head's alias); a pick by meaning alone ("stove" ->
        cooking) is not sure, so the noun falls to the labelled box."""
        from copilot.scene import pictures
        h = _head(w)
        if not h:
            return ""
        heads = {h, h + "s", h[:-1] if h.endswith("s") else h}
        alias = pictures.ALIAS.get(h, "")
        if self.emoji is not None:
            hit = self.emoji.match(h)
            return hit if hit and (hit == alias or heads & set(hit.split())) else ""
        idx = pictures.index()
        return h if h in idx else (alias if alias in idx else "")

    def _icon_coming(self, w: str) -> bool:
        name = self._icon_name(w)
        return bool(name) and name in self.pending

    def start_fetch(self, name: str) -> None:
        if not self.fetch or name in self.pending or name in self.failed or not icons.flat_path(name):
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return  # no event loop (a replay, a test): cached icons only
        self.pending.add(name)
        loop.create_task(self._fetch(name), name="stage:icon")

    async def _fetch(self, name: str) -> None:
        try:
            url = await asyncio.to_thread(icons.fetch, name, self.icon_dir)
        except Exception:  # a disk / network fault: not again this session
            log.exception("[STAGE] icon %r: the fetch failed", name)
            url = None
        finally:
            self.pending.discard(name)
        if not url:
            self.failed.add(name)
            return
        self.cache = {k: v for k, v in self.cache.items() if v.rung != 6}
        log.info("[STAGE] icon %r: %s", name, url)
        if self.on_icon is not None:
            try:
                await self.on_icon(name)
            except Exception:
                log.exception("[STAGE] icon %r: the republish failed", name)

    def prefetch(self, noun: str) -> None:
        """The fast path heard a noun the catalog does not know: start its icon now (the LLM's add finds it)."""
        if safety.blocked(noun) or catalog.known(noun) or SHAPE_OF.get(_key(noun)):
            return
        hit = self.nearest("prop", noun)
        if hit and hit[2] >= self.thresholds["prop"]:
            return
        name = self._icon_name(noun)
        if name and not icons.cached(name, self.icon_dir):
            self.start_fetch(name)

    # ---------- misses ----------
    def _miss(self, kind: str, w: str, near: Optional[str], p: Pick) -> None:
        k = _key(w)
        if k in self.missed or not self.log_misses:
            return
        self.missed.add(k)
        path = self.misses_path or MISSES
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"t": round(time.time()), "w": w, "kind": kind, "near": near, "rung": p.rung,
                                    "draw": p.draw}) + "\n")
        except OSError as err:
            log.info("[STAGE] misses log not written: %s", err)


_LADDER = Ladder(fetch=False, log_misses=False)


def ladder() -> Ladder:
    return _LADDER


def set_ladder(lad: Ladder) -> None:
    """The app's ladder (with the embedder, the emoji matcher and fetching on); tests set their own."""
    global _LADDER
    _LADDER = lad
