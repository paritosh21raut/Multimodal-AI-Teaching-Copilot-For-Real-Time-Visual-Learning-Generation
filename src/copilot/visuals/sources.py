"""Image candidates from free educational sources (F-007b, ADR-0007): Wikipedia page images, Wikimedia Commons
search, Openverse (off by default). No keys. Every call goes through one httpx.AsyncClient with a timeout; the
finder applies the overall time budget. Responses are parsed into `Candidate`s only — no filtering here.
"""
from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass, field
from typing import Optional

import httpx

log = logging.getLogger(__name__)

USER_AGENT = "TeachingCopilot/0.1 (classroom teaching aid prototype; https://github.com/paritosh21raut)"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
THUMB_WIDTH = 960  # enough for the image column on a 1920 px stage; Commons rasterises SVG at this width
_META = "LicenseShortName|Artist|Categories|ImageDescription|Restrictions"


@dataclass
class Candidate:
    source: str            # wikipedia | commons | openverse
    title: str             # "File:Heart diagram-en.svg" (or the Openverse title)
    image_url: str         # the thumbnail we download (never hot-linked by the display)
    page_url: str = ""
    width: int = 0         # original size (0 = unknown; SVG = its nominal size)
    height: int = 0
    mime: str = ""
    licence: str = ""
    author: str = ""
    categories: str = ""   # "|"-joined Commons categories
    description: str = ""
    article: str = ""      # Wikipedia: the article whose lead image this is
    article_description: str = ""  # "Organ found in humans and other animals" / "1992 film by ..."
    rank: int = 0          # position in its source's result list (0 = first)
    meta: dict = field(default_factory=dict)


def client(timeout: float = 6.0, transport: Optional[httpx.AsyncBaseTransport] = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, timeout=timeout, follow_redirects=True,
                             transport=transport)


def _text(value: str) -> str:
    """Commons extmetadata values are HTML ("<a href=...>Author</a>")."""
    return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value or "")).split())


def _from_imageinfo(page: dict, source: str, rank: int) -> Optional[Candidate]:
    infos = page.get("imageinfo") or []
    if not infos:
        return None
    ii = infos[0]
    meta = ii.get("extmetadata") or {}
    get = lambda k: _text((meta.get(k) or {}).get("value", ""))  # noqa: E731
    url = ii.get("thumburl") or ii.get("url") or ""
    if not url:
        return None
    return Candidate(
        source=source, title=page.get("title", ""), image_url=url, page_url=ii.get("descriptionurl", ""),
        width=int(ii.get("width") or 0), height=int(ii.get("height") or 0), mime=ii.get("mime", ""),
        licence=get("LicenseShortName"), author=get("Artist"),
        categories=(meta.get("Categories") or {}).get("value", ""), description=get("ImageDescription")[:300],
        rank=rank, meta={"restrictions": get("Restrictions")},
    )


async def commons_search(c: httpx.AsyncClient, query: str, limit: int = 8, offset: int = 0) -> list[Candidate]:
    r = await c.get(COMMONS_API, params={
        "action": "query", "format": "json", "formatversion": 2, "generator": "search", "gsrnamespace": 6,
        "gsrsearch": f"{query} filetype:bitmap|drawing", "gsrlimit": limit, "gsroffset": offset, "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": THUMB_WIDTH, "iiextmetadatafilter": _META})
    r.raise_for_status()
    pages = sorted((r.json().get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    return [c for i, p in enumerate(pages) if (c := _from_imageinfo(p, "commons", offset + i))]


async def commons_files(c: httpx.AsyncClient, titles: list[str]) -> dict[str, Candidate]:
    """imageinfo (thumbnail, licence, categories) for known file names → {title: Candidate}."""
    if not titles:
        return {}
    r = await c.get(COMMONS_API, params={
        "action": "query", "format": "json", "formatversion": 2, "titles": "|".join(titles), "prop": "imageinfo",
        "iiprop": "url|size|mime|extmetadata", "iiurlwidth": THUMB_WIDTH, "iiextmetadatafilter": _META})
    r.raise_for_status()
    out = {}
    for p in (r.json().get("query") or {}).get("pages") or []:
        cand = _from_imageinfo(p, "wikipedia", 0)
        if cand is not None:
            out[cand.title] = cand
    return out


async def wikipedia_lead_images(c: httpx.AsyncClient, query: str, limit: int = 3) -> list[Candidate]:
    """Lead images (free licences only) of the top articles for the query, with their Commons metadata."""
    r = await c.get(WIKIPEDIA_API, params={
        "action": "query", "format": "json", "formatversion": 2, "generator": "search", "gsrsearch": query,
        "gsrlimit": limit, "prop": "pageimages|description", "piprop": "name", "pilicense": "free"})
    r.raise_for_status()
    pages = sorted((r.json().get("query") or {}).get("pages") or [], key=lambda p: p.get("index", 0))
    wanted = [(i, p) for i, p in enumerate(pages) if p.get("pageimage")]
    files = await commons_files(c, [f"File:{p['pageimage']}" for _, p in wanted])
    out = []
    for i, p in wanted:
        cand = files.get(f"File:{p['pageimage'].replace('_', ' ')}")
        if cand is None:
            continue  # a local (non-Commons) file: not free, skip
        cand.article, cand.article_description, cand.rank = p.get("title", ""), p.get("description", ""), i
        cand.page_url = f"https://en.wikipedia.org/wiki/{p.get('title', '').replace(' ', '_')}"
        out.append(cand)
    return out


async def openverse_search(c: httpx.AsyncClient, query: str, limit: int = 8, page: int = 1) -> list[Candidate]:
    r = await c.get(OPENVERSE_API, params={"q": query, "page_size": limit, "page": page, "mature": "false"})
    r.raise_for_status()
    out = []
    for i, x in enumerate(r.json().get("results") or []):
        url = x.get("thumbnail") or x.get("url")
        if not url:
            continue
        out.append(Candidate(
            source="openverse", title=x.get("title") or "", image_url=url, page_url=x.get("foreign_landing_url", ""),
            width=int(x.get("width") or 0), height=int(x.get("height") or 0), mime=f"image/{x.get('filetype') or ''}",
            licence=f"{(x.get('license') or '').upper()} {x.get('license_version') or ''}".strip(),
            author=x.get("creator") or "", categories="|".join(t.get("name", "") for t in x.get("tags") or []),
            rank=i, meta={"provider": x.get("provider", "")}))
    return out
