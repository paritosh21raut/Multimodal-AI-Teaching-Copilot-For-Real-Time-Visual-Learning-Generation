"""Flat icons for the lookup ladder's rung 5 (F-017 §4): Microsoft Fluent Emoji **Flat** SVGs (MIT licence,
github.com/microsoft/fluentui-emoji, the same repo and index as scene/fluent3d.json), fetched once per name,
cleaned (only shape and gradient elements, no scripts, links or styles) and recoloured to the stage palette, then
cached as `data/assets/stage/icons/<slug>.svg` and served at /stage-icon/<slug>.svg. The browser draws them with an
<image> element (an SVG drawn that way runs nothing).
"""
from __future__ import annotations

import logging
import os
import re
import threading
from pathlib import Path
from typing import Any, Optional
from xml.etree import ElementTree as ET

from copilot.scene import pictures

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[3]
ICON_DIR = ROOT / "data" / "assets" / "stage" / "icons"
URL = "/stage-icon/{}.svg"
LICENCE = "MIT, microsoft/fluentui-emoji (Flat SVG)"
FETCH_TIMEOUT_S = 6.0
MAX_BYTES = 200_000

# the explainer_flat palette (F-017 §2 colour roles and the kit's fills): every icon colour moves to the nearest one
PALETTE = ("#F07C1A", "#E04A3A", "#2F6BE0", "#1E9E6A", "#8A4FE0", "#3B8FE0", "#33363D", "#5D6672", "#FFFFFF",
           "#D9A066", "#E4572E", "#3F8A4B", "#4E9F5A", "#8A5A3B", "#9C6A43", "#B98256", "#CFE7F5", "#FFE08A",
           "#2F3238", "#C9CDD3", "#EBC895", "#F2C94C", "#F5A3B5", "#A8D8F0", "#9AA3AE", "#E8E2D6", "#6B4A3A")
_KEEP = {"svg", "g", "path", "circle", "ellipse", "rect", "polygon", "polyline", "line", "defs", "linearGradient",
         "radialGradient", "stop"}
_ATTRS = {"d", "fill", "stroke", "stroke-width", "stroke-linecap", "stroke-linejoin", "fill-rule", "clip-rule",
          "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "y1", "x2", "y2", "width", "height", "points", "transform",
          "viewBox", "id", "offset", "stop-color", "stop-opacity", "opacity", "fill-opacity", "gradientUnits",
          "gradientTransform", "fx", "fy"}
_HEX = re.compile(r"#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b")
_URL_REF = re.compile(r"^url\(#[A-Za-z0-9_\-]+\)$")
SVG_NS = "http://www.w3.org/2000/svg"


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def nearest(hex_colour: str) -> str:
    """The palette colour closest to a colour (a weighted RGB distance, close enough to perceived for flat fills)."""
    r, g, b = _rgb(hex_colour)

    def d(p: str) -> float:
        pr, pg, pb = _rgb(p)
        rm = (r + pr) / 2
        return (2 + rm / 256) * (r - pr) ** 2 + 4 * (g - pg) ** 2 + (2 + (255 - rm) / 256) * (b - pb) ** 2

    return min(PALETTE, key=d)


def clean(svg: str) -> Optional[str]:
    """The icon with only shape / gradient elements and drawing attributes, colours moved to the palette; None if it
    is not an SVG."""
    try:
        root = ET.fromstring(svg)
    except ET.ParseError:
        return None
    if root.tag.split("}")[-1] != "svg":
        return None

    def walk(el: ET.Element) -> Optional[ET.Element]:
        tag = el.tag.split("}")[-1]
        if tag not in _KEEP:
            return None
        out = ET.Element(tag)
        for k, v in el.attrib.items():
            k = k.split("}")[-1]
            if k not in _ATTRS:
                continue
            if k in ("fill", "stroke") and v.startswith("url(") and not _URL_REF.match(v):
                continue
            out.set(k, _HEX.sub(lambda m: nearest(m.group(0)), v))
        for c in el:
            w = walk(c)
            if w is not None:
                out.append(w)
        return out

    out = walk(root)
    assert out is not None
    out.set("xmlns", SVG_NS)
    return ET.tostring(out, encoding="unicode")


def flat_path(name: str) -> str:
    """The flat SVG's path in the Fluent repo, from the 3D index row ("" if the name is not there)."""
    p = pictures.index().get(name, "")
    if not p:
        return ""
    return p.replace("/3D/", "/Flat/").replace("_3d_default.png", "_flat_default.svg").replace("_3d.png", "_flat.svg")


def cached(name: str, icon_dir: Optional[Path] = None) -> str:
    s = pictures.slug(name)
    return URL.format(s) if s and ((icon_dir or ICON_DIR) / f"{s}.svg").is_file() else ""


def fetch(name: str, icon_dir: Optional[Path] = None, client: Any = None) -> str:
    """Blocking (run it in a thread): download, clean, recolour and cache one flat icon. Its URL, or "" (offline, not
    found, not an SVG)."""
    have = cached(name, icon_dir)
    if have:
        return have
    path = flat_path(name)
    s = pictures.slug(name)
    if not path or not s:
        return ""
    import httpx

    url = pictures._base() + "/".join(pictures._quote(p) for p in path.split("/"))
    try:
        r = (client or httpx).get(url, timeout=FETCH_TIMEOUT_S, follow_redirects=True)
    except Exception as err:  # offline, a timeout: the rung below draws it
        log.info("[STAGE] icon %r not fetched: %s", name, err)
        return ""
    if r.status_code != 200 or len(r.content) > MAX_BYTES:
        log.info("[STAGE] icon %r: HTTP %s", name, r.status_code)
        return ""
    svg = clean(r.content.decode("utf-8", "replace"))
    if not svg:
        return ""
    d = icon_dir or ICON_DIR
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / f".{s}.{threading.get_ident()}.tmp"  # written whole, then renamed: never seen half-written
    tmp.write_text(svg, encoding="utf-8")
    os.replace(tmp, d / f"{s}.svg")
    return URL.format(s)
